# app/worker/__main__.py
from __future__ import annotations

import time

from app import config
from app.core import ticks
from app.core.market_hours import is_trading_time, now_vn
from app.db import repo
from app.notify.telegram import TelegramNotifier
from app.worker.poller import Poller


def _chat_id(user_id: int):
    user = repo.get_user(user_id)
    return user["telegram_chat_id"] if user else None


def main() -> None:
    print("Worker starting; initializing DB...")
    repo.init_db()
    notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, on_error=print)
    poller = Poller(
        notifier=notifier,
        fetch_fn=ticks.fetch_intraday,
        append_fn=repo.append_rows,
        chat_id_fn=_chat_id,
    )

    while True:
        interval = max(3, repo.get_interval())
        if not (config.IGNORE_MARKET_HOURS or is_trading_time()):
            time.sleep(60)
            continue
        specs = repo.watch_specs()
        if not specs:
            time.sleep(interval)
            continue
        page_size = ticks.page_size_for_interval(interval)
        now = now_vn().replace(tzinfo=None)
        for symbol, symbol_specs in specs.items():
            poller.process_symbol(symbol, symbol_specs, page_size, now)
        time.sleep(interval)


if __name__ == "__main__":
    main()
