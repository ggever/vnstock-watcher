import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum
from app.db import repo
from app.core import ticks
from app.core.market_hours import is_trading_time, now_vn
from app import config
from app.notify.telegram import TelegramNotifier
from app.worker.poller import Poller

app = FastAPI()

@app.get("/api/cron")
def run_cron(request: Request):
    if config.CRON_SECRET and request.headers.get("Authorization") != f"Bearer {config.CRON_SECRET}":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not (config.IGNORE_MARKET_HOURS or is_trading_time()):
        return JSONResponse({"skipped": "market closed"})
    specs = repo.watch_specs()
    if not specs:
        return JSONResponse({"skipped": "no symbols"})

    notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN)

    fetched_max: dict = {}

    def fetch_fn(symbol, page_size):
        df = ticks.fetch_intraday(symbol, page_size)
        last_seen = repo.get_poller_last_seen(symbol)
        if last_seen is not None and not df.empty:
            cutoff = pd.Timestamp(last_seen)
            if cutoff.tzinfo is not None:
                cutoff = cutoff.tz_convert(None)
            df = df[df["_sort_time"] > cutoff]
        if not df.empty:
            fetched_max[symbol] = df["_sort_time"].max()
        return df

    def append_fn(user_id, symbol, rows):
        return repo.append_rows(user_id, symbol, rows)

    def chat_id_fn(user_id):
        user = repo.get_user(user_id)
        return user["telegram_chat_id"] if user else None

    poller = Poller(notifier, fetch_fn, append_fn, chat_id_fn)
    # Pre-seed _first_poll so the baseline phase is skipped; fetch_fn already
    # filters by DB last_seen, so all returned rows are genuinely new.
    # Intentionally leave poller._last_seen unpopulated: process_symbol's
    # in-memory filter degenerates to a no-op (last_seen is None → new_ticks = ticks),
    # which is correct because fetch_fn already applied the DB cursor.
    for symbol in specs:
        poller._first_poll.add(symbol)

    now = now_vn().replace(tzinfo=None)
    for symbol, symbol_specs in specs.items():
        page_size = ticks.page_size_for_interval(60)
        poller.process_symbol(symbol, symbol_specs, page_size, now)
        if symbol in fetched_max:
            repo.set_poller_last_seen(symbol, fetched_max[symbol])

    return JSONResponse({"ok": True, "symbols": list(specs.keys())})

handler = Mangum(app)
