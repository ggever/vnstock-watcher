import pandas as pd
from app.notify.telegram import TelegramNotifier, build_message


def _rows():
    return pd.DataFrame([
        {"volume": 5000, "price": 10.0, "match_type": "Mua", "_sort_time": pd.Timestamp("2026-07-01 10:01:05")},
        {"volume": 3000, "price": 12.0, "match_type": "Bán", "_sort_time": pd.Timestamp("2026-07-01 10:02:00")},
    ])


def test_build_message_format():
    text = build_message("VNM", _rows(), threshold=2000, side="")
    assert text.startswith("VNM:")
    assert "2 lệnh Mua 🟢/Bán 🔴 >= Khối lượng 2,000" in text
    assert "🟢 KL:5000 Giá: 10.00" in text
    assert "🔴 KL:3000 Giá: 12.00" in text


def test_build_message_single_side():
    text = build_message("VNM", _rows(), threshold=1000, side="Mua")
    assert "Mua 🟢 >= Khối lượng 1,000" in text


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
    ok = n.notify_big_order("999", "VNM", _rows(), threshold=2000, side="")
    assert ok is True
    assert captured["url"] == "https://api.telegram.org/botTOK/sendMessage"
    assert captured["json"]["chat_id"] == "999"
    assert "VNM:" in captured["json"]["text"]


def test_notify_big_order_skips_empty():
    n = TelegramNotifier(token="TOK")
    assert n.notify_big_order("999", "VNM", pd.DataFrame(), threshold=2000, side="") is False


def test_notify_swallows_errors(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr("app.notify.telegram.httpx.post", boom)
    errors = []
    n = TelegramNotifier(token="TOK", on_error=errors.append)
    assert n.notify("1", "hi") is False
    assert errors and "network down" in errors[0]
