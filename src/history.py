from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from market_hours import now_vn
from paths import data_dir


HEADERS = ["time", "symbol", "side", "volume", "price", "value"]
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    time    TEXT NOT NULL,
    symbol  TEXT NOT NULL,
    side    TEXT NOT NULL,
    volume  INTEGER NOT NULL,
    price   REAL NOT NULL,
    value   REAL NOT NULL
)
"""
CREATE_INDEX_SQL = "CREATE INDEX IF NOT EXISTS idx_symbol_time ON orders (symbol, time)"


def history_path() -> Path:
    return db_path()


def db_path() -> Path:
    return data_dir() / "history.db"


def csv_history_path() -> Path:
    return data_dir() / "history.csv"


def append_rows(symbol: str, rows) -> int:
    _init_db()
    records = []
    for _, row in rows.iterrows():
        volume = int(row.get("volume", 0) or 0)
        price = float(row.get("price", 0) or 0)
        records.append(
            (
                _history_time(row.get("time")),
                symbol.upper(),
                str(row.get("match_type", "")).upper(),
                volume,
                price,
                volume * price,
            )
        )

    if not records:
        return 0

    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO orders (time, symbol, side, volume, price, value)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            records,
        )
    return len(records)


def load_history(
    symbol_filter: str | None = None,
    date_filter: str | None = None,
    limit: int = 500,
) -> list[dict[str, object]]:
    _init_db()
    sql = "SELECT time, symbol, side, volume, price, value FROM orders WHERE 1=1"
    params: list[object] = []

    symbol = (symbol_filter or "").strip().upper()
    if symbol and symbol != "ALL":
        sql += " AND symbol = ?"
        params.append(symbol)

    date_text = (date_filter or "").strip()
    if date_text:
        sql += " AND time >= ?"
        params.append(date_text)

    sql += " ORDER BY time DESC LIMIT ?"
    params.append(max(1, int(limit)))

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(zip(HEADERS, row)) for row in rows]


def clear_history() -> None:
    _init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM orders")


def distinct_symbols() -> list[str]:
    _init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT DISTINCT symbol FROM orders ORDER BY symbol").fetchall()
    return [row[0] for row in rows]


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    return conn


def _init_db() -> None:
    is_new = not db_path().exists()
    with _connect() as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.execute(CREATE_INDEX_SQL)
    if is_new:
        _migrate_from_csv()


def _migrate_from_csv() -> None:
    csv_path = csv_history_path()
    if not csv_path.exists():
        return

    records = []
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                volume = int(float(row.get("volume", 0) or 0))
                price = float(row.get("price", 0) or 0)
                value = float(row.get("value", volume * price) or volume * price)
            except ValueError:
                continue
            records.append(
                (
                    row.get("time", ""),
                    row.get("symbol", "").upper(),
                    row.get("side", "").upper(),
                    volume,
                    price,
                    value,
                )
            )

    if records:
        with _connect() as conn:
            conn.executemany(
                """
                INSERT INTO orders (time, symbol, side, volume, price, value)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                records,
            )

    backup_path = csv_path.with_suffix(".csv.bak")
    if backup_path.exists():
        backup_path.unlink()
    csv_path.rename(backup_path)


def _history_time(value) -> str:
    if value is None:
        return now_vn().replace(microsecond=0).isoformat()

    text = str(value).strip()
    if not text:
        return now_vn().replace(microsecond=0).isoformat()

    try:
        parsed = datetime.fromisoformat(text)
        return parsed.replace(microsecond=0).isoformat()
    except ValueError:
        pass

    if len(text) <= 8 and ":" in text:
        today = now_vn().date().isoformat()
        return f"{today}T{text}"

    return text
