# tests/conftest.py
import os
import pytest
from app.db import repo

TEST_DSN = os.environ.get("TEST_DATABASE_URL", "postgresql://vnstock:vnstock@localhost:5432/vnstock_test")


@pytest.fixture()
def db(monkeypatch):
    monkeypatch.setattr(repo, "_dsn", lambda: TEST_DSN)
    repo.init_db()
    with repo.connect() as conn:
        conn.execute("TRUNCATE orders, symbols, users, allowed_emails RESTART IDENTITY CASCADE")
        conn.execute("DELETE FROM poller_state")
        conn.execute("UPDATE settings SET interval = 10 WHERE id = 1")
    yield repo
