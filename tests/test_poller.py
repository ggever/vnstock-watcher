# tests/test_poller.py
from datetime import datetime, timedelta
import pandas as pd
from app.worker.poller import Poller


def _ticks(rows):
    from app.core.ticks import normalize_ticks
    return normalize_ticks(pd.DataFrame(rows))


def test_first_poll_is_baseline_then_fans_out():
    sent = []
    saved = []

    class FakeNotifier:
        def notify_big_order(self, chat_id, symbol, rows):
            sent.append((chat_id, symbol, len(rows)))
            return True

    data = {"call": 0}
    batch1 = [{"time": "2026-06-22 09:15:00", "volume": "9000", "price": "10", "match_type": "BU"}]
    batch2 = batch1 + [{"time": "2026-06-22 09:20:00", "volume": "9000", "price": "10", "match_type": "BU"}]

    def fetch_fn(symbol, page_size):
        data["call"] += 1
        return _ticks(batch1 if data["call"] == 1 else batch2)

    p = Poller(
        notifier=FakeNotifier(),
        fetch_fn=fetch_fn,
        append_fn=lambda uid, sym, rows: saved.append((uid, sym, len(rows))) or len(rows),
        chat_id_fn=lambda uid: f"chat-{uid}",
    )
    specs = [
        {"user_id": 1, "threshold": 3000, "side": "Cả hai"},
        {"user_id": 2, "threshold": 100000, "side": "Cả hai"},  # never triggers
    ]
    now = datetime(2026, 6, 22, 9, 21, 0)

    p.process_symbol("VNM", specs, page_size=100, now=now)  # baseline
    assert sent == [] and saved == []

    p.process_symbol("VNM", specs, page_size=100, now=now)  # one new tick
    assert sent == [("chat-1", "VNM", 1)]      # only user 1 (threshold met)
    assert saved == [(1, "VNM", 1)]


def test_cooldown_per_user_symbol():
    sent = []

    class FakeNotifier:
        def notify_big_order(self, chat_id, symbol, rows):
            sent.append(chat_id)
            return True

    seq = [
        [{"time": "2026-06-22 09:15:00", "volume": "9000", "price": "10", "match_type": "BU"}],
        [{"time": "2026-06-22 09:15:00", "volume": "9000", "price": "10", "match_type": "BU"},
         {"time": "2026-06-22 09:16:00", "volume": "9000", "price": "10", "match_type": "BU"}],
        [{"time": "2026-06-22 09:15:00", "volume": "9000", "price": "10", "match_type": "BU"},
         {"time": "2026-06-22 09:16:00", "volume": "9000", "price": "10", "match_type": "BU"},
         {"time": "2026-06-22 09:17:00", "volume": "9000", "price": "10", "match_type": "BU"}],
    ]
    calls = {"n": 0}

    def fetch_fn(symbol, page_size):
        i = min(calls["n"], len(seq) - 1)
        calls["n"] += 1
        return _ticks(seq[i])

    p = Poller(FakeNotifier(), fetch_fn,
               append_fn=lambda *a: 1, chat_id_fn=lambda uid: "c1")
    specs = [{"user_id": 1, "threshold": 3000, "side": "Cả hai"}]

    base = datetime(2026, 6, 22, 9, 18, 0)
    p.process_symbol("VNM", specs, 100, now=base)               # baseline
    p.process_symbol("VNM", specs, 100, now=base + timedelta(seconds=5))   # send
    p.process_symbol("VNM", specs, 100, now=base + timedelta(seconds=10))  # cooldown -> skip
    assert sent == ["c1"]
    p.process_symbol("VNM", specs, 100, now=base + timedelta(seconds=40))  # past cooldown
    assert sent == ["c1", "c1"]
