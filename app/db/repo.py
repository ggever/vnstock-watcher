# app/db/repo.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app import config


def _dsn() -> str:
    return config.DATABASE_URL


def connect() -> psycopg.Connection:
    return psycopg.connect(_dsn(), row_factory=dict_row, autocommit=True)


def _schema_sql() -> str:
    return (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")


def init_db() -> None:
    with connect() as conn:
        conn.execute(_schema_sql())


def get_interval() -> int:
    with connect() as conn:
        row = conn.execute("SELECT interval FROM settings WHERE id = 1").fetchone()
    return int(row["interval"]) if row else 10


def set_interval(value: int) -> None:
    value = max(3, int(value))
    with connect() as conn:
        conn.execute("UPDATE settings SET interval = %s WHERE id = 1", (value,))


def get_poller_last_seen(symbol: str):
    with connect() as conn:
        row = conn.execute(
            "SELECT last_seen_at FROM poller_state WHERE symbol = %s", (symbol.upper(),)
        ).fetchone()
    return row["last_seen_at"] if row else None


def set_poller_last_seen(symbol: str, ts: datetime) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO poller_state (symbol, last_seen_at)
            VALUES (%s, %s)
            ON CONFLICT (symbol) DO UPDATE SET last_seen_at = EXCLUDED.last_seen_at
            """,
            (symbol.upper(), ts),
        )
