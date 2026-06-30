from fastapi import FastAPI
from fastapi.responses import JSONResponse
from mangum import Mangum
from app.db import repo
from app.core import ticks
from app.core.market_hours import is_trading_time, now_vn
from app import config
from app.notify.telegram import TelegramNotifier
from app.worker.poller import Poller

cron_app = FastAPI()

@cron_app.get("/api/cron")
def run_cron():
    if not (config.IGNORE_MARKET_HOURS or is_trading_time()):
        return JSONResponse({"skipped": "market closed"})
    specs = repo.watch_specs()
    if not specs:
        return JSONResponse({"skipped": "no symbols"})

    notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN)

    def fetch_fn(symbol, page_size):
        df = ticks.fetch_intraday(symbol, page_size)
        # inject last_seen từ DB thay vì in-memory
        last_seen = repo.get_poller_last_seen(symbol)
        if last_seen is not None and not df.empty:
            df = df[df["_sort_time"] > last_seen]
        return df

    def append_fn(user_id, symbol, rows):
        count = repo.append_rows(user_id, symbol, rows)
        # cập nhật last_seen vào DB
        if not rows.empty:
            repo.set_poller_last_seen(symbol, rows["_sort_time"].max())
        return count

    def chat_id_fn(user_id):
        user = repo.get_user(user_id)
        return user["telegram_chat_id"] if user else None

    poller = Poller(notifier, fetch_fn, append_fn, chat_id_fn)
    now = now_vn().replace(tzinfo=None)
    for symbol, symbol_specs in specs.items():
        page_size = ticks.page_size_for_interval(60)
        poller.process_symbol(symbol, symbol_specs, page_size, now)

    return JSONResponse({"ok": True, "symbols": list(specs.keys())})

handler = Mangum(cron_app)
