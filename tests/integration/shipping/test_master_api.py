"""Master database endpoints: behind the same loopback guard and CSRF header; no live Shopify call."""

import pytest
from tests.fixtures.seo import local_client, remote_client

from flowmerce.modules.seo.app import create_app
from flowmerce.modules.shipping import master_db, master_sync

H = {"X-Requested-With": "blog-ops"}


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(autouse=True)
def memory_master():
    master_db.open_master(":memory:")  # never the real data/master.sqlite
    yield


def test_status_schema_and_access(app):
    c = local_client(app)
    s = c.get("/api/shipping/master/status").json()
    assert (
        set(s["counts"]) == {"stores", "orders", "items", "shipments", "events"}
        and s["last_sync"] is None
    )
    ddl = c.get("/api/shipping/master/schema")
    assert ddl.status_code == 200 and 'create table if not exists "shipments"' in ddl.text
    assert remote_client(app).get("/api/shipping/master/status").status_code == 403
    assert remote_client(app).post("/api/shipping/master/sync", headers=H).status_code == 403


def test_sync_needs_the_csrf_header_and_fails_cleanly_without_credentials(app, monkeypatch):
    class NoCreds:
        has_shopify_credentials = False
        shop_domain = "x.myshopify.com"
        orders_since = "2026-10-01"

    monkeypatch.setattr(master_sync, "load_config", lambda: NoCreds())
    c = local_client(app)
    assert c.post("/api/shipping/master/sync").status_code == 403
    r = c.post("/api/shipping/master/sync", headers=H).json()
    assert r["status"] == "failed" and "credentials" in r["error"]
    assert c.get("/api/shipping/master/status").json()["last_sync"]["status"] == "failed"
