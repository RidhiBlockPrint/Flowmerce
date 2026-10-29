"""End-to-end checks through the real HTTP stack in local operator mode.

There is no sign-in: a request from a loopback address acts as the local administrator, and a request from
anywhere else is refused (403) before any page or API is served, except the secret-protected workflow
webhook. The CSRF header, the server-side permission checks and the live-publishing safeguards still apply.

Starlette's TestClient reports its peer as "testclient", which is not a loopback address, so every client
here is built with an explicit peer address (tests/fixtures/seo.py: local_client, remote_client, make_client).
"""
import pytest
from starlette.requests import Request

from flowmerce.modules.seo import permissions
from flowmerce.modules.seo.app import bootstrap_admin, create_app
from flowmerce.modules.seo.auth import LOCAL_OPERATOR_PASSWORD_HASH, is_loopback_client, local_operator, verify_password
from flowmerce.modules.seo.config import config
from flowmerce.modules.seo.db import all_rows, get, now, run
from flowmerce.modules.seo.util import sha256
from tests.fixtures.seo import PASSWORD, local_client, make_client, remote_client

H = {"X-Requested-With": "blog-ops"}
SECRET_MARKERS = ("shpat_", "private_key", "sk-ant", "password_hash", "admin_token")
WEBHOOK_SECRET = "test-webhook-secret-value"


@pytest.fixture(scope="module")
def app():
    return create_app()


def _count(table):
    return all_rows(f"SELECT COUNT(*) n FROM {table}")[0]["n"]


# ---------------- local operator ----------------

def test_local_client_needs_no_login(app, users):
    c = local_client(app)
    r = c.get("/api/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["localOperator"] is True
    assert body["user"]["id"] == users["admin"]["id"] and body["user"]["role"] == "admin"
    assert set(body["permissions"]) == set(permissions.PERMISSIONS)   # administrator permissions
    assert "set-cookie" not in r.headers                              # no session is created
    assert c.get("/api/articles").status_code == 200                  # ordinary endpoints work without signing in
    assert c.get("/api/home").status_code == 200


def test_permission_checks_still_run_for_the_operator(app, monkeypatch):
    monkeypatch.setitem(permissions.ROLE_PERMS, "admin", ["audit:view"])
    assert local_client(app).get("/api/articles").status_code == 403


# ---------------- local-only boundary ----------------

@pytest.mark.parametrize("path", [
    "/", "/login", "/seo", "/assets/app.js", "/favicon.svg",
    "/api/auth/me", "/api/articles", "/api/home", "/api/users", "/api/docs", "/api/openapi.json",
])
def test_remote_client_is_refused_for_the_dashboard_and_every_ordinary_api_path(app, path):
    r = remote_client(app).get(path)
    assert r.status_code == 403
    assert r.json()["code"] == "local_only"


def test_remote_mutations_are_refused_and_change_nothing(app):
    before = _count("articles")
    r = remote_client(app).post("/api/articles", json={"brand_id": "ridhi", "title": "from elsewhere"}, headers=H)
    assert r.status_code == 403 and r.json()["code"] == "local_only"
    assert _count("articles") == before


@pytest.mark.parametrize(("peer", "expected"), [
    (("127.0.0.1", 50000), 200),
    (("::1", 50000), 200),
    (("::ffff:127.0.0.1", 50000), 200),
    (("10.0.0.5", 50000), 403),
    (("8.8.8.8", 50000), 403),
    (("fe80::1", 50000), 403),
    (("testclient", 50000), 403),     # the test client's default peer is not an IP address: fail closed
    (("not-an-ip", 50000), 403),
    (("", 50000), 403),
])
def test_only_loopback_peers_are_local(app, peer, expected):
    assert make_client(app, peer).get("/api/auth/me").status_code == expected


def test_a_missing_client_address_fails_closed():
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b"", "client": None}
    assert is_loopback_client(Request(scope)) is False


def test_forwarded_headers_never_make_a_remote_client_local(app):
    headers = {"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1", "Forwarded": "for=127.0.0.1"}
    r = remote_client(app).get("/api/auth/me", headers=headers)
    assert r.status_code == 403 and r.json()["code"] == "local_only"


# ---------------- obsolete sign-in endpoints ----------------

def test_login_and_password_endpoints_do_not_verify_or_change_credentials(app, users):
    c = local_client(app)

    def snapshot():
        return all_rows("SELECT id, password_hash, last_login_at FROM users ORDER BY id"), _count("sessions")

    before = snapshot()
    right = c.post("/api/auth/login", json={"email": "admin@test.local", "password": PASSWORD}, headers=H)
    wrong = c.post("/api/auth/login", json={"email": "admin@test.local", "password": "nope nope nope"}, headers=H)
    for r in (right, wrong):                       # both answer the same: nothing is checked
        assert r.status_code == 410 and r.json()["code"] == "login_disabled"
        assert "set-cookie" not in r.headers
    changed = c.post("/api/auth/password", json={"current": PASSWORD, "next": "a brand new password 1"}, headers=H)
    assert changed.status_code == 410 and changed.json()["code"] == "password_disabled"
    assert snapshot() == before                    # no hash changed, no login recorded, no session created


def test_logout_is_harmless_and_deletes_no_session_record(app, users):
    token = "leftover-cookie-token"
    run("INSERT INTO sessions (id, user_id, created_at, expires_at) VALUES (?,?,?,?)",
        sha256(token), users["admin"]["id"], now(), "2999-01-01T00:00:00.000Z")
    try:
        c = local_client(app)
        c.cookies.set("bo_session", token)
        assert c.post("/api/auth/logout", headers=H).json() == {"ok": True}
        assert get("SELECT 1 FROM sessions WHERE id = ?", sha256(token)) is not None
    finally:
        run("DELETE FROM sessions WHERE id = ?", sha256(token))


# ---------------- workflow webhook (the one external path) ----------------

def test_webhook_is_reachable_from_other_computers_and_checks_its_own_secret(app, monkeypatch):
    monkeypatch.setattr(config, "workflow_webhook_secret", WEBHOOK_SECRET)
    runs_before = _count("workflow_runs")
    r = remote_client(app)                         # no CSRF header and no sign-in: the webhook needs neither
    assert r.post("/api/hooks/workflow", json={}).status_code == 401
    wrong = r.post("/api/hooks/workflow", json={}, headers={"X-Workflow-Secret": "wrong"})
    assert wrong.status_code == 401 and "Bad secret" in wrong.text
    # With the right secret the request is accepted for processing; this body is rejected before anything is written.
    ok = r.post("/api/hooks/workflow", json={"brand": "nope", "stage": "x"}, headers={"X-Workflow-Secret": WEBHOOK_SECRET})
    assert ok.status_code == 400
    assert _count("workflow_runs") == runs_before


def test_webhook_is_off_without_a_configured_secret(app, monkeypatch):
    monkeypatch.setattr(config, "workflow_webhook_secret", "")
    assert remote_client(app).post("/api/hooks/workflow", json={}).status_code == 404


@pytest.mark.parametrize(("method", "path"), [
    ("GET", "/api/hooks/workflow"),
    ("PUT", "/api/hooks/workflow"),
    ("POST", "/api/hooks/workflow/"),
    ("POST", "/api/hooks/other"),
    ("POST", "/api/hooks"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/articles"),
])
def test_no_other_path_or_method_is_exempt_from_the_local_only_rule(app, monkeypatch, method, path):
    monkeypatch.setattr(config, "workflow_webhook_secret", WEBHOOK_SECRET)
    r = remote_client(app).request(method, path, json={}, headers={"X-Workflow-Secret": WEBHOOK_SECRET, **H})
    assert r.status_code == 403 and r.json()["code"] == "local_only"


# ---------------- CSRF, secrets, publishing safeguards ----------------

def test_csrf_header_still_required_for_ordinary_mutating_requests(app):
    c = local_client(app)
    before = _count("articles")
    for r in (c.post("/api/articles", json={"brand_id": "ridhi", "title": "x"}), c.patch("/api/articles/1", json={"title": "x"})):
        assert r.status_code == 403 and r.json()["code"] == "csrf"
    assert _count("articles") == before
    assert c.get("/api/articles").status_code == 200   # safe methods need no header


def test_responses_expose_no_secrets(app, monkeypatch):
    monkeypatch.setattr(config, "workflow_webhook_secret", WEBHOOK_SECRET)
    c = local_client(app)
    for path in ("/api/auth/me", "/api/brands", "/api/users", "/api/integrations", "/api/home"):
        r = c.get(path)
        assert r.status_code == 200, path
        for marker in (*SECRET_MARKERS, WEBHOOK_SECRET):
            assert marker not in r.text, (path, marker)
    assert len(c.get("/api/auth/me").json()["brands"]) == 2


@pytest.fixture
def pending_publish(users):
    ts = now()
    aid = run("""INSERT INTO articles (brand_id, title, handle, status, content_hash, approved_hash, created_at, updated_at)
                 VALUES ('ridhi', 'Safeguard test', 'safeguard-test', 'publish_requested', 'h1', 'h1', ?, ?)""", ts, ts).last_id
    rid = run("""INSERT INTO publish_requests (article_id, brand_id, mode, content_hash, version, status, requested_by, requested_at)
                 VALUES (?, 'ridhi', 'publish_now', 'h1', 1, 'pending', ?, ?)""", aid, users["seo_manager"]["id"], ts).last_id
    yield aid, rid
    run("DELETE FROM publish_requests WHERE id = ?", rid)
    run("DELETE FROM articles WHERE id = ?", aid)


def test_live_publishing_safeguards_still_apply(app, pending_publish):
    aid, rid = pending_publish
    assert config.allow_live_publish is False
    c = local_client(app)
    wrong = c.post(f"/api/publish-requests/{rid}/authorize", json={"confirm": "yes"}, headers=H)
    assert wrong.status_code == 400 and wrong.json()["code"] == "confirmation_required"
    right = c.post(f"/api/publish-requests/{rid}/authorize", json={"confirm": "PUBLISH"}, headers=H)
    assert right.status_code == 423 and right.json()["code"] == "publishing_disabled"   # ALLOW_LIVE_PUBLISH is off
    assert get("SELECT status FROM publish_requests WHERE id = ?", rid)["status"] == "pending"
    assert get("SELECT shopify_published FROM articles WHERE id = ?", aid)["shopify_published"] == 0


# ---------------- first-run bootstrap ----------------

def test_bootstrap_creates_an_operator_record_even_when_other_users_exist(app, users, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "data_dir", tmp_path)
    monkeypatch.setattr(config, "admin_password", "this-password-must-be-ignored")
    before = all_rows("SELECT * FROM users ORDER BY id")
    run("UPDATE users SET active = 0 WHERE role = 'admin'")        # no active administrator, other users remain
    created = None
    try:
        bootstrap_admin()
        created = get("SELECT * FROM users WHERE role = 'admin' AND active = 1")
        assert created is not None and created["id"] not in {u["id"] for u in before}
        assert created["password_hash"] == LOCAL_OPERATOR_PASSWORD_HASH
        assert not verify_password("this-password-must-be-ignored", created["password_hash"])
        assert list(tmp_path.iterdir()) == []                      # no initial-admin.txt, no password written anywhere
        assert local_operator()["id"] == created["id"]
        for u in before:                                            # every existing record is untouched (except the admin flag set above)
            now_row = get("SELECT * FROM users WHERE id = ?", u["id"])
            assert now_row == {**u, "active": 0} if u["role"] == "admin" else now_row == u
    finally:
        if created:
            run("DELETE FROM users WHERE id = ?", created["id"])
        run("UPDATE users SET active = 1 WHERE id = ?", users["admin"]["id"])
    assert local_operator()["id"] == users["admin"]["id"]


def test_bootstrap_does_not_touch_an_existing_record_that_holds_the_default_email(app, users, monkeypatch):
    monkeypatch.setattr(config, "admin_email", "")
    taken = run("INSERT INTO users (email, name, role, password_hash, created_at, active) VALUES (?,?,?,?,?,0)",
                "admin@blog-ops.local", "Old default", "reviewer", "scrypt$1$x$y", now()).last_id
    run("UPDATE users SET active = 0 WHERE role = 'admin'")
    created = None
    try:
        bootstrap_admin()
        created = get("SELECT * FROM users WHERE role = 'admin' AND active = 1")
        assert created["email"] == "local-operator@flowmerce.local"
        old = get("SELECT * FROM users WHERE id = ?", taken)
        assert old["role"] == "reviewer" and old["active"] == 0 and old["name"] == "Old default"
    finally:
        if created:
            run("DELETE FROM users WHERE id = ?", created["id"])
        run("DELETE FROM users WHERE id = ?", taken)
        run("UPDATE users SET active = 1 WHERE id = ?", users["admin"]["id"])
