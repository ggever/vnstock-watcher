# tests/test_repo.py
import pytest
from app.db import repo


def test_init_and_interval(db):
    repo.set_interval(42)
    assert repo.get_interval() == 42


def test_set_interval_clamps_minimum(db):
    repo.set_interval(1)
    assert repo.get_interval() == 3


def test_poller_state_roundtrip(db):
    from datetime import datetime, timezone
    ts = datetime(2026, 6, 22, 9, 15, 0, tzinfo=timezone.utc)
    assert repo.get_poller_last_seen("VNM") is None
    repo.set_poller_last_seen("VNM", ts)
    result = repo.get_poller_last_seen("VNM")
    assert result is not None
    repo.set_poller_last_seen("VNM", datetime(2026, 6, 22, 9, 20, 0, tzinfo=timezone.utc))
    result2 = repo.get_poller_last_seen("VNM")
    assert result2 > result


from app import config


def test_get_or_create_user_respects_whitelist(db, monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_EMAILS", {"ok@x.com"})
    monkeypatch.setattr(config, "ADMIN_EMAILS", {"ok@x.com"})
    user = repo.get_or_create_user("OK@x.com", "Boss")
    assert user["email"] == "ok@x.com"
    assert user["is_admin"] is True
    again = repo.get_or_create_user("ok@x.com", "Boss")
    assert again["id"] == user["id"]


def test_get_or_create_user_rejects_unlisted(db, monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_EMAILS", set())
    with pytest.raises(PermissionError):
        repo.get_or_create_user("stranger@x.com", "Nope")


def test_allowed_email_table_grants_access(db, monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_EMAILS", set())
    repo.add_allowed_email("Friend@x.com")
    assert repo.is_email_allowed("friend@x.com") is True
    assert "friend@x.com" in repo.list_allowed_emails()
    repo.remove_allowed_email("friend@x.com")
    assert repo.is_email_allowed("friend@x.com") is False


def test_set_telegram_chat_id(db, monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_EMAILS", {"a@x.com"})
    monkeypatch.setattr(config, "ADMIN_EMAILS", set())
    user = repo.get_or_create_user("a@x.com", "A")
    repo.set_telegram_chat_id(user["id"], "12345")
    assert repo.get_user(user["id"])["telegram_chat_id"] == "12345"
