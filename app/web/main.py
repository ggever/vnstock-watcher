# app/web/main.py
from __future__ import annotations

from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import config
from app.db import repo
from app.notify.telegram import TelegramNotifier
from app.web import auth
from app.web.deps import RedirectToLogin, require_admin, require_user, redirect_login

app = FastAPI(title="VNStock Watcher")
app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET)
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
app.include_router(auth.router)
templates = Jinja2Templates(directory="app/web/templates")


@app.on_event("startup")
def _startup():
    repo.init_db()


@app.exception_handler(RedirectToLogin)
async def _redirect_login(request: Request, exc: RedirectToLogin):
    return redirect_login()


@app.get("/")
def config_page(request: Request):
    user = require_user(request)
    return templates.TemplateResponse("config.html", {
        "request": request,
        "user": user,
        "symbols": repo.list_symbols(user["id"]),
    })


@app.post("/symbols")
def add_symbol(request: Request, symbol: str = Form(...), threshold: int = Form(...), side: str = Form("Cả hai")):
    user = require_user(request)
    repo.upsert_symbol(user["id"], symbol, threshold, side)
    return RedirectResponse(url="/", status_code=303)


@app.post("/symbols/delete")
def del_symbol(request: Request, symbol: str = Form(...)):
    user = require_user(request)
    repo.delete_symbol(user["id"], symbol)
    return RedirectResponse(url="/", status_code=303)


@app.post("/telegram")
def save_telegram(request: Request, chat_id: str = Form("")):
    user = require_user(request)
    repo.set_telegram_chat_id(user["id"], chat_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/telegram/test")
def test_telegram(request: Request):
    user = require_user(request)
    chat_id = user.get("telegram_chat_id") or ""
    if not chat_id:
        return JSONResponse({"ok": False, "error": "Chưa lưu Chat ID."}, status_code=400)
    tg = TelegramNotifier(token=config.TELEGRAM_BOT_TOKEN)
    ok = tg.notify(chat_id, "✅ VNStock Watcher: kết nối Telegram thành công!")
    if ok:
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False, "error": "Gửi thất bại. Kiểm tra bot token và chat ID."}, status_code=502)


@app.get("/history")
def history_page(request: Request, symbol: str = "ALL", date: str = ""):
    user = require_user(request)
    return templates.TemplateResponse("history.html", {
        "request": request,
        "user": user,
        "rows": repo.load_history(user["id"], symbol, date),
        "symbols": repo.distinct_symbols(user["id"]),
        "symbol": symbol,
        "date": date,
    })


@app.get("/history/rows")
def history_rows(request: Request, symbol: str = "ALL", date: str = ""):
    user = require_user(request)
    return templates.TemplateResponse("_history_rows.html", {
        "request": request,
        "rows": repo.load_history(user["id"], symbol, date),
    })


@app.post("/history/clear")
def clear_history(request: Request):
    user = require_user(request)
    repo.clear_history(user["id"])
    return RedirectResponse(url="/history", status_code=303)


@app.get("/admin")
def admin_page(request: Request):
    require_admin(request)
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "allowed": repo.list_allowed_emails(),
        "interval": repo.get_interval(),
    })


@app.post("/admin/email")
def admin_add_email(request: Request, email: str = Form(...)):
    require_admin(request)
    repo.add_allowed_email(email)
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/email/delete")
def admin_del_email(request: Request, email: str = Form(...)):
    require_admin(request)
    repo.remove_allowed_email(email)
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/interval")
def admin_interval(request: Request, interval: int = Form(...)):
    require_admin(request)
    repo.set_interval(interval)
    return RedirectResponse(url="/admin", status_code=303)
