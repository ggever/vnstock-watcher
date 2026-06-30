# tests/test_web.py
import pytest
from starlette.testclient import TestClient


@pytest.fixture()
def client(db, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "ALLOWED_EMAILS", {"a@x.com"})
    monkeypatch.setattr(config, "ADMIN_EMAILS", set())
    from app.web.main import app
    return TestClient(app, raise_server_exceptions=True)


def test_root_redirects_to_login_when_anonymous(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_login_page_renders(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "Google" in resp.text
