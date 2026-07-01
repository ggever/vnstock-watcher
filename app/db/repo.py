# app/db/repo.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app import config
from app.core.market_hours import now_vn
from app.core.symbol_config import clean_symbol, normalize_side


def _dsn() -> str:
    return config.DATABASE_URL


_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            _dsn(),
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row, "autocommit": True},
        )
    return _pool


def connect():
    return _get_pool().connection()


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


def is_email_allowed(email: str) -> bool:
    email = (email or "").strip().lower()
    if not email:
        return False
    if email in config.ALLOWED_EMAILS:
        return True
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM allowed_emails WHERE email = %s", (email,)
        ).fetchone()
    return row is not None


def get_or_create_user(email: str, name: str) -> dict:
    email = (email or "").strip().lower()
    if not is_email_allowed(email):
        raise PermissionError(email)
    is_admin = email in config.ADMIN_EMAILS
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = %s", (email,)).fetchone()
        if row:
            return row
        return conn.execute(
            "INSERT INTO users (email, name, is_admin) VALUES (%s, %s, %s) RETURNING *",
            (email, name or "", is_admin),
        ).fetchone()


def get_user(user_id: int) -> dict | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()


def set_telegram_chat_id(user_id: int, chat_id: str | None) -> None:
    chat_id = (chat_id or "").strip() or None
    with connect() as conn:
        conn.execute(
            "UPDATE users SET telegram_chat_id = %s WHERE id = %s", (chat_id, user_id)
        )


def list_allowed_emails() -> list[str]:
    with connect() as conn:
        rows = conn.execute("SELECT email FROM allowed_emails ORDER BY email").fetchall()
    return [r["email"] for r in rows]


def add_allowed_email(email: str) -> None:
    email = (email or "").strip().lower()
    if not email:
        return
    with connect() as conn:
        conn.execute(
            "INSERT INTO allowed_emails (email) VALUES (%s) ON CONFLICT DO NOTHING",
            (email,),
        )


def remove_allowed_email(email: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM allowed_emails WHERE email = %s", ((email or "").strip().lower(),))


def list_symbols(user_id: int) -> list[dict]:
    with connect() as conn:
        return conn.execute(
            "SELECT symbol, threshold, side FROM symbols WHERE user_id = %s ORDER BY symbol",
            (user_id,),
        ).fetchall()


def upsert_symbol(user_id: int, symbol: str, threshold: int, side: str) -> None:
    symbol = clean_symbol(symbol)
    threshold = int(threshold)
    side = normalize_side(side)
    if not symbol or threshold <= 0:
        return
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO symbols (user_id, symbol, threshold, side)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, symbol)
            DO UPDATE SET threshold = EXCLUDED.threshold, side = EXCLUDED.side
            """,
            (user_id, symbol, threshold, side),
        )


def delete_symbol(user_id: int, symbol: str) -> None:
    with connect() as conn:
        conn.execute(
            "DELETE FROM symbols WHERE user_id = %s AND symbol = %s",
            (user_id, clean_symbol(symbol)),
        )


def watch_specs() -> dict[str, list[dict]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT user_id, symbol, threshold, side FROM symbols"
        ).fetchall()
    specs: dict[str, list[dict]] = {}
    for r in rows:
        specs.setdefault(r["symbol"], []).append(
            {"user_id": r["user_id"], "threshold": r["threshold"], "side": r["side"]}
        )
    return specs


_HISTORY_KEYS = ["time", "symbol", "side", "volume", "price", "value"]


def history_time(value) -> str:
    if value is None:
        return now_vn().replace(microsecond=0).isoformat()
    text = str(value).strip()
    if not text:
        return now_vn().replace(microsecond=0).isoformat()
    try:
        return datetime.fromisoformat(text).replace(microsecond=0).isoformat()
    except ValueError:
        pass
    if len(text) <= 8 and ":" in text:
        return f"{now_vn().date().isoformat()}T{text}"
    return text


def append_rows(user_id: int, symbol: str, rows) -> int:
    records = []
    for _, row in rows.iterrows():
        volume = int(row.get("volume", 0) or 0)
        price = float(row.get("price", 0) or 0)
        records.append((
            user_id,
            history_time(row.get("time")),
            symbol.upper(),
            str(row.get("match_type", "")),
            volume,
            price,
            volume * price,
        ))
    if not records:
        return 0
    with connect() as conn:
        conn.cursor().executemany(
            """
            INSERT INTO orders (user_id, time, symbol, side, volume, price, value)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            records,
        )
    return len(records)


def load_history(user_id: int, symbol_filter=None, date_filter=None, limit: int = 500) -> list[dict]:
    sql = "SELECT time, symbol, side, volume, price, value FROM orders WHERE user_id = %s"
    params: list = [user_id]
    symbol = (symbol_filter or "").strip().upper()
    if symbol and symbol != "ALL":
        sql += " AND symbol = %s"
        params.append(symbol)
    date_text = (date_filter or "").strip()
    if date_text:
        sql += " AND time >= %s"
        params.append(date_text)
    sql += " ORDER BY time DESC LIMIT %s"
    params.append(max(1, int(limit)))
    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def clear_history(user_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM orders WHERE user_id = %s", (user_id,))


def distinct_symbols(user_id: int) -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT symbol FROM orders WHERE user_id = %s ORDER BY symbol",
            (user_id,),
        ).fetchall()
    return [r["symbol"] for r in rows]
