from __future__ import annotations

from typing import Callable

import httpx


def build_message(symbol: str, rows) -> tuple[str, str]:
    count = len(rows)
    total_volume = int(rows["volume"].sum())
    total_value = float((rows["volume"] * rows["price"]).sum())
    sides = ", ".join(sorted(set(rows["match_type"].astype(str))))
    title = f"{symbol}: {count} lệnh lớn"
    body = f"Chiều {sides} | KL {total_volume:,} | GT {total_value:,.0f}"
    return title, body


class TelegramNotifier:
    def __init__(self, token: str, on_error: Callable[[str], None] | None = None) -> None:
        self.token = token
        self._on_error = on_error

    def notify_big_order(self, chat_id, symbol: str, rows) -> bool:
        if rows is None or rows.empty:
            return False
        title, body = build_message(symbol, rows)
        return self.notify(chat_id, f"{title}\n{body}")

    def notify(self, chat_id, text: str) -> bool:
        if not self.token or not chat_id:
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            resp = httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as exc:
            if self._on_error:
                self._on_error(f"Telegram thất bại: {exc}")
            return False
