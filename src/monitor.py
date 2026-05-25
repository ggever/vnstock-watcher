from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

import pandas as pd
from vnstock import Quote

from config import AppConfig, SymbolConfig
from history import append_rows
from market_hours import is_trading_time
from notifier import WindowsNotifier


StatusCallback = Callable[[str], None]
LogCallback = Callable[[str], None]
HistoryCallback = Callable[[], None]
MIN_NOTIFY_GAP_SECONDS = 30
BACKOFF_AFTER_FAILURES = 5
BACKOFF_SECONDS = 300


@dataclass
class MonitorService:
    config_getter: Callable[[], AppConfig]
    notifier: WindowsNotifier
    on_status: StatusCallback = lambda message: None
    on_log: LogCallback = lambda message: None
    on_history_updated: HistoryCallback = lambda: None
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _last_seen: dict[str, pd.Timestamp] = field(default_factory=dict, init=False)
    _first_poll: set[str] = field(default_factory=set, init=False)
    _last_notified: dict[str, datetime] = field(default_factory=dict, init=False)
    _fail_count: dict[str, int] = field(default_factory=dict, init=False)
    _next_retry_at: dict[str, datetime] = field(default_factory=dict, init=False)

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return

        self._stop_event.clear()
        self._last_seen.clear()
        self._first_poll.clear()
        self._last_notified.clear()
        self._fail_count.clear()
        self._next_retry_at.clear()
        self._thread = threading.Thread(target=self._loop, name="VNStockMonitor", daemon=True)
        self._thread.start()
        self.on_status("Đang theo dõi")
        self.on_log("Đã bắt đầu theo dõi.")

    def stop(self) -> None:
        if not self.running:
            self.on_status("Đã dừng")
            return

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        self.on_status("Đã dừng")
        self.on_log("Đã dừng theo dõi.")

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            config = self.config_getter()
            interval = max(3, int(config.interval or 10))

            if not config.symbols:
                self.on_status("Chưa có mã để theo dõi")
                self._stop_event.wait(interval)
                continue

            if not is_trading_time():
                self.on_status("Thị trường đóng cửa")
                self._stop_event.wait(60)
                continue

            self.on_status("Đang quét lệnh")
            for symbol_config in config.symbols:
                if self._stop_event.is_set():
                    break
                self._poll_symbol(symbol_config, interval)

            self._stop_event.wait(interval)

    def _poll_symbol(self, symbol_config: SymbolConfig, interval: int) -> None:
        symbol = symbol_config.symbol.upper()
        retry_at = self._next_retry_at.get(symbol)
        if retry_at and datetime.now() < retry_at:
            return

        try:
            ticks = _fetch_intraday(symbol, page_size=_page_size_for_interval(interval))
            if ticks.empty:
                self.on_log(f"{symbol}: không có dữ liệu intraday.")
                self._record_success(symbol)
                return

            last_seen = self._last_seen.get(symbol)
            newest_seen = ticks["_sort_time"].max()
            self._last_seen[symbol] = newest_seen

            if symbol not in self._first_poll:
                self._first_poll.add(symbol)
                self.on_log(f"{symbol}: đã lấy mốc ban đầu, bỏ qua dữ liệu cũ.")
                self._record_success(symbol)
                return

            new_ticks = ticks[ticks["_sort_time"] > last_seen] if last_seen is not None else ticks
            if new_ticks.empty:
                self._record_success(symbol)
                return

            big_orders = _filter_big_orders(new_ticks, symbol_config)
            if big_orders.empty:
                self._record_success(symbol)
                return

            saved = append_rows(symbol, big_orders)
            self._notify_if_allowed(symbol, big_orders)
            self.on_log(f"{symbol}: phát hiện {len(big_orders)} lệnh lớn, đã ghi {saved} dòng.")
            self.on_history_updated()
            self._record_success(symbol)
        except Exception as exc:
            self._record_failure(symbol)
            self.on_log(f"{symbol}: lỗi khi lấy dữ liệu - {exc}")

    def _notify_if_allowed(self, symbol: str, big_orders: pd.DataFrame) -> None:
        now = datetime.now()
        last_notified = self._last_notified.get(symbol)
        if last_notified and (now - last_notified).total_seconds() < MIN_NOTIFY_GAP_SECONDS:
            self.on_log(f"{symbol}: bỏ qua toast do cooldown {MIN_NOTIFY_GAP_SECONDS}s.")
            return

        self.notifier.notify_big_order(symbol, big_orders)
        self._last_notified[symbol] = now

    def _record_success(self, symbol: str) -> None:
        self._fail_count.pop(symbol, None)
        self._next_retry_at.pop(symbol, None)

    def _record_failure(self, symbol: str) -> None:
        fail_count = self._fail_count.get(symbol, 0) + 1
        if fail_count < BACKOFF_AFTER_FAILURES:
            self._fail_count[symbol] = fail_count
            return

        self._fail_count[symbol] = 0
        self._next_retry_at[symbol] = datetime.now() + timedelta(seconds=BACKOFF_SECONDS)
        self.on_log(f"{symbol}: tạm dừng {BACKOFF_SECONDS // 60} phút do lỗi liên tiếp.")


def _fetch_intraday(symbol: str, page_size: int = 100) -> pd.DataFrame:
    quote = _build_quote(symbol)
    frame = quote.intraday(page_size=page_size)
    return _normalize_ticks(frame)


def _build_quote(symbol: str):
    return Quote(symbol=symbol, source="kbs")


def _page_size_for_interval(interval: int) -> int:
    return max(100, int(interval) * 10)


def _normalize_ticks(frame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()

    ticks = frame.copy()
    ticks.columns = [str(column).lower() for column in ticks.columns]
    required = {"time", "volume", "price", "match_type"}
    if not required.issubset(set(ticks.columns)):
        missing = ", ".join(sorted(required - set(ticks.columns)))
        raise ValueError(f"thiếu cột dữ liệu: {missing}")

    ticks["volume"] = pd.to_numeric(ticks["volume"], errors="coerce").fillna(0).astype(int)
    ticks["price"] = pd.to_numeric(ticks["price"], errors="coerce").fillna(0)
    ticks["match_type"] = (
        ticks["match_type"].astype(str).str.upper()
        .replace({"BUY": "Mua", "SELL": "Bán", "BU": "Mua", "SD": "Bán"})
    )
    ticks["_sort_time"] = pd.to_datetime(ticks["time"], errors="coerce")

    if ticks["_sort_time"].isna().all():
        today = pd.Timestamp.today().date().isoformat()
        ticks["_sort_time"] = pd.to_datetime(today + " " + ticks["time"].astype(str), errors="coerce")

    ticks = ticks.dropna(subset=["_sort_time"])
    return ticks.sort_values("_sort_time")


def _filter_big_orders(ticks: pd.DataFrame, symbol_config: SymbolConfig) -> pd.DataFrame:
    big = ticks[ticks["volume"] >= int(symbol_config.threshold)]
    if symbol_config.side in {"Mua", "Bán"}:
        big = big[big["match_type"] == symbol_config.side]
    return big
