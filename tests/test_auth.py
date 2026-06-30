# tests/test_auth.py
import pytest
from app.web import deps


def test_require_user_redirects_when_no_session():
    from starlette.requests import Request
    scope = {"type": "http", "session": {}, "headers": []}
    req = Request(scope)
    with pytest.raises(deps.RedirectToLogin):
        deps.require_user(req)
