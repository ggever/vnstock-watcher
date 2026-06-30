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
