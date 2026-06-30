# app/web/auth.py
from __future__ import annotations

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import config
from app.db import repo

oauth = OAuth()
oauth.register(
    name="google",
    client_id=config.GOOGLE_CLIENT_ID,
    client_secret=config.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

router = APIRouter()
_templates = Jinja2Templates(directory="app/web/templates")


@router.get("/login")
async def login(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    return _templates.TemplateResponse("login.html", {"request": request})


@router.get("/auth/login")
async def auth_login(request: Request):
    return await oauth.google.authorize_redirect(request, config.OAUTH_REDIRECT_URL)


@router.get("/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    info = token.get("userinfo") or {}
    email = (info.get("email") or "").lower()
    name = info.get("name") or ""
    try:
        user = repo.get_or_create_user(email, name)
    except PermissionError:
        return _templates.TemplateResponse(
            "denied.html", {"request": request, "email": email}, status_code=403
        )
    request.session["user_id"] = user["id"]
    return RedirectResponse(url="/", status_code=303)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
