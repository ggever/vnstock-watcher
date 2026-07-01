from __future__ import annotations

from typing import Callable

import httpx


def build_message(symbol: str, rows, threshold: int, side: str) -> str:
    count = len(rows)
    if side == "Mua":
        side_label = "Mua 🟢"
    elif side == "Bán":
        side_label = "Bán 🔴"
    else:
        side_label = "Mua 🟢/Bán 🔴"

    top = rows.nlargest(5, "volume")
    lines = [
        f"{symbol}:",
        f"  {count} lệnh {side_label} >= Khối lượng {threshold:,}, {len(top)} lệnh lớn nhất:",
    ]
    for i, (_, row) in enumerate(top.iterrows(), 1):
        emoji = "🟢" if row["match_type"] == "Mua" else "🔴"
        dt = row["_sort_time"].strftime("%Y/%m/%d %H:%M:%S")
        lines.append(f"     {i}. {dt} {emoji} KL:{int(row['volume'])} Giá: {row['price']:.2f}")
    return "\n".join(lines)


class TelegramNotifier:
    def __init__(self, token: str, on_error: Callable[[str], None] | None = None) -> None:
        self.token = token
        self._on_error = on_error

    def notify_big_order(self, chat_id, symbol: str, rows, threshold: int, side: str) -> bool:
        if rows is None or rows.empty:
            return False
        return self.notify(chat_id, build_message(symbol, rows, threshold, side))

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
