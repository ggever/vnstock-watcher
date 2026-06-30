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
