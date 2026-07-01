from __future__ import annotations

import os
import pandas as pd

os.environ.setdefault("HOME", "/tmp")


def fetch_intraday(symbol: str, page_size: int = 100) -> pd.DataFrame:
    from vnstock import Quote
    quote = Quote(symbol=symbol, source="kbs")
    frame = quote.intraday(page_size=page_size)
    return normalize_ticks(frame)


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
