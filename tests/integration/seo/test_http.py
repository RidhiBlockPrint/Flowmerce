"""End-to-end checks through the real HTTP stack: sessions, CSRF header and role enforcement on the
server regardless of what the UI shows."""
import pytest
from fastapi.testclient import TestClient

from flowmerce.modules.seo.app import create_app
from tests.fixtures.seo import PASSWORD

H = {"X-Requested-With": "blog-ops"}


@pytest.fixture(scope="module")
def app():
    return create_app()


def login(app, email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": PASSWORD}, headers=H)
    assert r.status_code == 200, r.text
    return c


def test_unauthenticated_refused(app):
    assert TestClient(app).get("/api/articles").status_code == 401


def test_wrong_password_and_cookie_flags(app):
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": "manager@test.local", "password": "nope nope nope"}, headers=H).status_code == 401
    r = c.post("/api/auth/login", json={"email": "manager@test.local", "password": PASSWORD}, headers=H)
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


def test_csrf_header_required(app):
    m = login(app, "manager@test.local")
    assert m.post("/api/articles", json={"brand_id": "ridhi", "title": "x"}).status_code == 403


def test_roles_enforced_by_api(app):
    m, r = login(app, "manager@test.local"), login(app, "reviewer@test.local")
    res = m.post("/api/articles", json={"brand_id": "ridhi", "title": "Server-side roles"}, headers=H)
    assert res.status_code == 200
    aid = res.json()["id"]
    assert r.patch(f"/api/articles/{aid}", json={"title": "hijack"}, headers=H).status_code == 403
    assert m.post(f"/api/articles/{aid}/review", json={"decision": "approve", "version": 1}, headers=H).status_code == 403
    assert m.get("/api/users").status_code == 200
    assert m.post("/api/users", json={"email": "x@y.z", "name": "x", "role": "admin", "password": "aaaaaaaaaaaaaa"}, headers=H).status_code == 403
    assert r.post("/api/admin/demo", json={"action": "load"}, headers=H).status_code == 403
    assert m.post("/api/integrations/test", json={"key": "claude"}, headers=H).status_code == 403


def test_me_exposes_no_secrets(app):
    a = login(app, "admin@test.local")
    body = a.get("/api/auth/me").text
    for secret in ("shpat_", "private_key", "sk-ant", "password_hash", "admin_token"):
        assert secret not in body
    assert len(a.get("/api/auth/me").json()["brands"]) == 2
