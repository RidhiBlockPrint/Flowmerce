"""GET /api/home: the read-only summary behind the Home page.

Runs against the shared in-memory database from tests/fixtures/seo.py with the network blocked. Each test
seeds its own rows through a fixture that deletes them afterwards, so nothing leaks into other tests.
"""
import json

import pytest
from fastapi.testclient import TestClient

from flowmerce.modules.seo import permissions
from flowmerce.modules.seo.app import create_app
from flowmerce.modules.seo.db import all_rows, now, run
from flowmerce.modules.seo.services.home import REPORTS_NOTE, metric_window
from tests.fixtures.seo import PASSWORD

H = {"X-Requested-With": "blog-ops"}
SECRET_MARKERS = ("shpat_", "private_key", "sk-ant", "password_hash", "admin_token", "ANTHROPIC_API_KEY")


@pytest.fixture(scope="module")
def app():
    return create_app()


def login(app, email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": PASSWORD}, headers=H)
    assert r.status_code == 200, r.text
    return c


def _article(brand, handle, status, ts):
    return run("INSERT INTO articles (brand_id, title, handle, status, created_at, updated_at) VALUES (?,?,?,?,?,?)",
               brand, f"Home test {handle}", handle, status, ts, ts).last_id


@pytest.fixture
def approvals_seed(users):
    """A validated topic (ridhi), an article in review (cpc) and a publish request raised by the reviewer (ridhi)."""
    ts = now()
    topic = run("""INSERT INTO topics (brand_id, title, primary_keyword, keyword_norm, status, created_at, updated_at)
                   VALUES ('ridhi', 'Home test topic', 'home test kw', 'home test kw', 'validated', ?, ?)""", ts, ts).last_id
    review = _article("cpc", "home-test-review", "in_review", ts)
    pub = _article("ridhi", "home-test-publish", "approved", ts)
    req = run("""INSERT INTO publish_requests (article_id, brand_id, mode, content_hash, version, status, requested_by, requested_at)
                 VALUES (?, 'ridhi', 'publish_now', 'h', 1, 'pending', ?, ?)""", pub, users["reviewer"]["id"], ts).last_id
    yield {"topic": topic, "review": review, "pub": pub, "req": req}
    run("DELETE FROM publish_requests WHERE id = ?", req)
    run("DELETE FROM articles WHERE id IN (?, ?)", review, pub)
    run("DELETE FROM topics WHERE id = ?", topic)


@pytest.fixture
def analytics_seed():
    """Real (api) rows for ridhi inside the window, one row just outside it, and demo-fixture rows for cpc."""
    frm, to = metric_window()
    from flowmerce.modules.seo.util import add_days
    outside = add_days(frm, -1)
    ts = now()

    def gsc(brand, day, page, clicks, imps, src):
        run("INSERT INTO gsc_page_daily (brand_id, date, page, clicks, impressions, ctr, position, source, imported_at) VALUES (?,?,?,?,?,?,?,?,?)",
            brand, day, page, clicks, imps, 0.1, 5.0, src, ts)

    def ga4(brand, day, path, sessions, src):
        run("""INSERT INTO ga4_page_daily (brand_id, date, page_path, sessions, engaged_sessions, engagement_rate, avg_engagement_seconds, key_events, source, imported_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""", brand, day, path, sessions, sessions // 2, 0.5, 30.0, 1, src, ts)

    gsc("ridhi", to, "/p/a", 10, 100, "api")
    gsc("ridhi", frm, "/p/b", 5, 50, "api")
    gsc("ridhi", outside, "/p/c", 1000, 9000, "api")      # outside the window: must not count
    gsc("ridhi", to, "/p/d", 424242, 898989, "demo")      # demo rows must never be used when real rows exist
    ga4("ridhi", to, "/p/a", 40, "api")
    gsc("cpc", to, "/p/z", 777777, 999999, "demo")        # demo only: must be withheld entirely
    ga4("cpc", to, "/p/z", 555555, "demo")
    yield {"from": frm, "to": to}
    run("DELETE FROM gsc_page_daily WHERE page LIKE '/p/%'")
    run("DELETE FROM ga4_page_daily WHERE page_path LIKE '/p/%'")


def _metrics(body, brand):
    return {m["key"]: m for m in body["metrics"] if m["brand"] == brand}


def _table_counts():
    names = [r["name"] for r in all_rows("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    return {n: all_rows(f"SELECT COUNT(*) n FROM {n}")[0]["n"] for n in names}


def test_unauthenticated_refused(app):
    assert TestClient(app).get("/api/home").status_code == 401


def test_view_permission_required(app, monkeypatch):
    r = login(app, "reviewer@test.local")
    assert r.get("/api/home").status_code == 200
    monkeypatch.setitem(permissions.ROLE_PERMS, "reviewer", ["audit:view"])
    assert r.get("/api/home").status_code == 403


def test_approvals_filtered_by_role(app, approvals_seed):
    def kinds(email):
        body = login(app, email).get("/api/home").json()
        assert body["approvalsTotal"] == len(body["approvals"])
        return {a["kind"] for a in body["approvals"] if a["title"].startswith("Home test")}

    assert kinds("manager@test.local") == {"topic"}            # topic:decide only
    assert kinds("reviewer@test.local") == {"review"}          # may not authorize their own publish request
    assert kinds("admin@test.local") == {"topic", "review", "authorize"}


def test_approvals_carry_links_not_actions(app, approvals_seed):
    body = login(app, "admin@test.local").get("/api/home").json()
    mine = [a for a in body["approvals"] if a["title"].startswith("Home test")]
    assert mine and all(a["to"].startswith("/") for a in mine)
    # Home only links to the SEO pages where deciding is permission-checked and audited; it carries no action endpoints.
    assert all(set(a) == {"id", "brand", "module", "kind", "label", "title", "action", "to", "since"} for a in mine)


def test_brand_filter(app, approvals_seed, analytics_seed):
    a = login(app, "admin@test.local")
    cpc = a.get("/api/home?brand=cpc").json()
    assert cpc["brands"] == ["cpc"]
    assert {m["brand"] for m in cpc["metrics"]} == {"cpc"}
    assert {x["brand"] for x in cpc["approvals"] if x["title"].startswith("Home test")} == {"cpc"}
    both = a.get("/api/home?brand=all").json()
    assert both["brands"] == ["ridhi", "cpc"]
    assert a.get("/api/home?brand=nope").status_code == 400


def test_unavailable_sources_are_empty_not_zero(app):
    body = login(app, "admin@test.local").get("/api/home").json()
    for m in body["metrics"]:
        assert m["value"] is None and m["withheld"] is False
        assert m["source"]["kind"] is None
    assert body["reports"] == [] and body["reportsNote"] == REPORTS_NOTE
    assert body["window"]["days"] == 28


def test_window_and_real_values(app, analytics_seed):
    body = login(app, "admin@test.local").get("/api/home").json()
    assert body["window"]["from"] == analytics_seed["from"] and body["window"]["to"] == analytics_seed["to"]
    m = _metrics(body, "ridhi")
    assert m["gsc_clicks"]["value"] == 15 and m["gsc_impressions"]["value"] == 150 and m["ga4_sessions"]["value"] == 40
    assert m["gsc_clicks"]["source"]["kind"] == "api"


def test_demo_fixtures_never_appear_as_metrics(app, analytics_seed):
    r = login(app, "admin@test.local").get("/api/home")
    body = r.json()
    cpc = _metrics(body, "cpc")
    assert all(x["value"] is None and x["withheld"] is True and x["source"]["kind"] == "demo" for x in cpc.values())
    assert body["demoFixturesLoaded"] is True
    for synthetic in ("777777", "999999", "555555", "424242", "898989"):
        assert synthetic not in r.text


def test_jobs_and_syncs_are_real_records_only(app):
    ts = now()
    run("INSERT INTO workflow_runs (brand_id, stage, status, trigger_kind, message, started_at, finished_at) VALUES ('ridhi','performance_tracking','succeeded','scheduler','ok',?,?)", ts, ts)
    run("INSERT INTO workflow_runs (brand_id, stage, status, trigger_kind, message, error, started_at, finished_at) VALUES ('ridhi','topic_research','failed','manual','x','boom',?,?)", ts, ts)
    run("INSERT OR REPLACE INTO integration_status (key, brand_id, status, last_attempt_at, last_success_at) VALUES ('gsc','ridhi','connected',?,?)", ts, ts)
    run("INSERT OR REPLACE INTO integration_status (key, brand_id, status, last_attempt_at, last_error) VALUES ('ga4','ridhi','error',?,'secret-looking detail')", ts)
    run("INSERT OR REPLACE INTO integration_status (key, brand_id, status) VALUES ('shopify','ridhi','pending_setup')")
    try:
        r = login(app, "admin@test.local").get("/api/home?brand=ridhi")
        body = r.json()
        jobs = {j["name"]: j for j in body["jobs"]}
        assert jobs["Performance tracking"]["status"] == "succeeded" and jobs["Performance tracking"]["lastSuccessAt"] == ts
        assert jobs["Topic research"]["status"] == "failed"
        assert "error" not in jobs["Topic research"] and "boom" not in json.dumps(body["jobs"])
        syncs = {s["key"]: s for s in body["syncs"]}
        assert set(syncs) == {"gsc", "ga4"}                      # the never-attempted shopify row is not shown
        assert all("lastError" not in s and "last_error" not in s for s in body["syncs"])
        assert "secret-looking detail" not in json.dumps(body["syncs"])
    finally:
        run("DELETE FROM workflow_runs WHERE message IN ('ok','x')")
        run("DELETE FROM integration_status WHERE brand_id = 'ridhi' AND key IN ('gsc','ga4','shopify')")


def test_no_credentials_or_setup_text_in_response(app, approvals_seed, analytics_seed):
    text = login(app, "admin@test.local").get("/api/home").text
    for marker in SECRET_MARKERS:
        assert marker not in text
    assert "setup" not in json.loads(text) and "configured" not in text


def test_endpoint_does_not_mutate_data(app, approvals_seed, analytics_seed):
    c = login(app, "admin@test.local")
    before = _table_counts()
    assert c.get("/api/home").status_code == 200
    assert c.get("/api/home?brand=ridhi").status_code == 200
    assert _table_counts() == before
