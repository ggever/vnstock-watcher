import pandas as pd
from app.notify.telegram import TelegramNotifier, build_message


def _rows():
    return pd.DataFrame([
        {"volume": 5000, "price": 10.0, "match_type": "Mua"},
        {"volume": 3000, "price": 12.0, "match_type": "Bán"},
    ])


def test_build_message_matches_legacy_format():
    title, body = build_message("VNM", _rows())
    assert title == "VNM: 2 lệnh lớn"
    assert body == "Chiều Bán, Mua | KL 8,000 | GT 86,000"


def test_notify_big_order_posts_payload(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        class R:
            status_code = 200
            def raise_for_status(self): pass
        return R()

    monkeypatch.setattr("app.notify.telegram.httpx.post", fake_post)
    n = TelegramNotifier(token="TOK")
    ok = n.notify_big_order("999", "VNM", _rows())
    assert ok is True
    assert captured["url"] == "https://api.telegram.org/botTOK/sendMessage"
    assert captured["json"]["chat_id"] == "999"
    assert "VNM: 2 lệnh lớn" in captured["json"]["text"]


def test_notify_big_order_skips_empty():
    n = TelegramNotifier(token="TOK")
    assert n.notify_big_order("999", "VNM", pd.DataFrame()) is False


def test_notify_swallows_errors(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr("app.notify.telegram.httpx.post", boom)
    errors = []
    n = TelegramNotifier(token="TOK", on_error=errors.append)
    assert n.notify("1", "hi") is False
    assert errors and "network down" in errors[0]
