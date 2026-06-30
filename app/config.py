from __future__ import annotations

import os


def csv_emails(value: str) -> set[str]:
    return {part.strip().lower() for part in (value or "").split(",") if part.strip()}


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://vnstock:vnstock@postgres:5432/vnstock"
)
SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-insecure-secret-change-me")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
OAUTH_REDIRECT_URL = os.environ.get("OAUTH_REDIRECT_URL", "http://localhost:8000/auth/callback")

ALLOWED_EMAILS = csv_emails(os.environ.get("ALLOWED_EMAILS", ""))
ADMIN_EMAILS = csv_emails(os.environ.get("ADMIN_EMAILS", ""))

DEFAULT_POLL_INTERVAL = max(3, int(os.environ.get("POLL_INTERVAL", "10") or "10"))
IGNORE_MARKET_HOURS = os.environ.get("IGNORE_MARKET_HOURS", "") == "1"
CRON_SECRET = os.environ.get("CRON_SECRET", "")
