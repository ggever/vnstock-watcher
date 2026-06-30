# app/web/deps.py
from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse

from app.db import repo


class RedirectToLogin(Exception):
    pass


def current_user(request: Request) -> dict | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return repo.get_user(user_id)


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise RedirectToLogin()
    return user


def require_admin(request: Request) -> dict:
    user = require_user(request)
    if not user.get("is_admin"):
        raise RedirectToLogin()
    return user


def redirect_login() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)
