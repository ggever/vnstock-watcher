# app/worker/poller.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

import pandas as pd

from app.core.ticks import filter_big_orders

MIN_NOTIFY_GAP_SECONDS = 30
BACKOFF_AFTER_FAILURES = 5
BACKOFF_SECONDS = 300


class Poller:
    def __init__(self, notifier, fetch_fn, append_fn, chat_id_fn, log: Callable[[str], None] = print):
        self.notifier = notifier
        self.fetch_fn = fetch_fn
        self.append_fn = append_fn
        self.chat_id_fn = chat_id_fn
        self.log = log
        self._last_seen: dict[str, pd.Timestamp] = {}
        self._first_poll: set[str] = set()
        self._last_notified: dict[tuple[int, str], datetime] = {}
        self._fail_count: dict[str, int] = {}
        self._next_retry_at: dict[str, datetime] = {}

    def process_symbol(self, symbol: str, specs: list[dict], page_size: int, now: datetime) -> None:
        retry_at = self._next_retry_at.get(symbol)
        if retry_at and now < retry_at:
            return
        try:
            ticks = self.fetch_fn(symbol, page_size)
            if ticks is None or ticks.empty:
                self._record_success(symbol)
                return

            last_seen = self._last_seen.get(symbol)

            if symbol not in self._first_poll:
                self._first_poll.add(symbol)
                self._last_seen[symbol] = ticks["_sort_time"].max()
                self.log(f"{symbol}: mốc ban đầu, bỏ qua dữ liệu cũ.")
                self._record_success(symbol)
                return

            new_ticks = ticks[ticks["_sort_time"] > last_seen] if last_seen is not None else ticks
            if new_ticks.empty:
                self._record_success(symbol)
                return

            notified = False
            for spec in specs:
                if self._fan_out(symbol, spec, new_ticks, now):
                    notified = True
            if notified:
                self._last_seen[symbol] = new_ticks["_sort_time"].max()
            self._record_success(symbol)
        except Exception as exc:  # noqa: BLE001
            self._record_failure(symbol)
            self.log(f"{symbol}: lỗi khi lấy dữ liệu - {exc}")

    def _fan_out(self, symbol: str, spec: dict, new_ticks: pd.DataFrame, now: datetime) -> bool:
        big = filter_big_orders(new_ticks, spec["threshold"], spec["side"])
        if big.empty:
            return False
        user_id = spec["user_id"]
        key = (user_id, symbol)
        last = self._last_notified.get(key)
        if last and (now - last).total_seconds() < MIN_NOTIFY_GAP_SECONDS:
            return False
        self.append_fn(user_id, symbol, big)
        chat_id = self.chat_id_fn(user_id)
        if chat_id:
            self.notifier.notify_big_order(chat_id, symbol, big, spec["threshold"], spec["side"])
        self._last_notified[key] = now
        return True

    def _record_success(self, symbol: str) -> None:
        self._fail_count.pop(symbol, None)
        self._next_retry_at.pop(symbol, None)

    def _record_failure(self, symbol: str) -> None:
        count = self._fail_count.get(symbol, 0) + 1
        if count < BACKOFF_AFTER_FAILURES:
            self._fail_count[symbol] = count
            return
        self._fail_count[symbol] = 0
        self._next_retry_at[symbol] = datetime.now() + timedelta(seconds=BACKOFF_SECONDS)
        self.log(f"{symbol}: tạm dừng {BACKOFF_SECONDS // 60} phút do lỗi liên tiếp.")
