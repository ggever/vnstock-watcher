from __future__ import annotations

from typing import Callable


class WindowsNotifier:
    def __init__(
        self,
        app_id: str = "VNStock Watcher",
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self.app_id = app_id
        self._on_error = on_error

    def notify_big_order(self, symbol: str, rows) -> None:
        if rows.empty:
            return

        count = len(rows)
        total_volume = int(rows["volume"].sum())
        total_value = float((rows["volume"] * rows["price"]).sum())
        sides = ", ".join(sorted(set(rows["match_type"].astype(str))))
        title = f"{symbol}: {count} lệnh lớn"
        message = (
            f"Chiều {sides} | KL {total_volume:,} | "
            f"GT {total_value:,.0f}"
        )
        self.notify(title, message)

    def notify(self, title: str, message: str) -> None:
        try:
            from winotify import Notification

            toast = Notification(app_id=self.app_id, title=title, msg=message)
            toast.show()
        except Exception as exc:
            # Toast failure must never stop monitoring.
            if self._on_error:
                self._on_error(f"Toast thất bại: {exc}")
            return
