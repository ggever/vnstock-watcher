from __future__ import annotations

import os
import pandas as pd

os.environ.setdefault("HOME", "/tmp")


_INTRADAY_SOURCES = ("vci", "kbs")


def _fetch_from_source(symbol: str, source: str, page_size: int) -> pd.DataFrame:
    if source == "vci":
        # vnstock's top-level Quote dispatcher always injects a `page` kwarg,
        # which the VCI provider's intraday() doesn't accept, so call it directly.
        from vnstock.explorer.vci.quote import Quote

        frame = Quote(symbol=symbol).intraday(page_size=page_size)
    else:
        from vnstock import Quote

        frame = Quote(symbol=symbol, source=source).intraday(page_size=page_size)
    return normalize_ticks(frame)


def fetch_intraday(symbol: str, page_size: int = 100) -> pd.DataFrame:
    errors = []
    for i, source in enumerate(_INTRADAY_SOURCES):
        try:
            ticks = _fetch_from_source(symbol, source, page_size)
        except Exception as exc:
            errors.append(f"{source}: {exc}")
            continue
        if ticks.empty:
            errors.append(f"{source}: dữ liệu rỗng")
            continue
        if i > 0:
            print(f"{symbol}: nguồn {_INTRADAY_SOURCES[0]} không có dữ liệu, dùng '{source}' thay thế.")
        return ticks

    raise ValueError(f"Không lấy được dữ liệu intraday cho mã {symbol} ({'; '.join(errors)})")


def page_size_for_interval(interval: int) -> int:
    return max(100, int(interval) * 10)


def normalize_ticks(frame) -> pd.DataFrame:
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

    # Strip timezone if present, then normalize to ns precision so comparisons
    # with pd.Timestamp and Python datetime are always valid across pandas versions.
    if ticks["_sort_time"].dt.tz is not None:
        ticks["_sort_time"] = ticks["_sort_time"].dt.tz_convert(None)
    ticks["_sort_time"] = ticks["_sort_time"].astype("datetime64[ns]")

    ticks = ticks.dropna(subset=["_sort_time"])
    return ticks.sort_values("_sort_time")


def filter_big_orders(ticks: pd.DataFrame, threshold: int, side: str) -> pd.DataFrame:
    if ticks.empty:
        return ticks
    big = ticks[ticks["volume"] >= int(threshold)]
    if side in {"Mua", "Bán"}:
        big = big[big["match_type"] == side]
    return big
