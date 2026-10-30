"""Shipping endpoints through the real HTTP stack: local operator access, loopback-only, CSRF, classification,
paging, exports and the read-only guarantees. No network: sync is tested with credentials absent."""

from datetime import UTC, datetime, timedelta

import pytest
from tests.fixtures.seo import local_client, remote_client

from flowmerce.modules.seo.app import create_app
from flowmerce.modules.seo.db import run
from flowmerce.modules.shipping import repo, service, sync
from flowmerce.modules.shipping.config import ShippingConfig

H = {"X-Requested-With": "blog-ops"}
NOW = datetime.now(UTC)


def iso(days_ago):
    return (NOW - timedelta(days=days_ago)).isoformat()


def rec(
    n,
    carrier="DHL Express",
    ordered=1,
    fulfilled=None,
    status="in_transit",
    scan=None,
    delivered=None,
    exc="",
    tracking=None,
):
    return {
        "shopify_order_id": f"gid://shopify/Order/{n}",
        "order_number": f"#{n}",
        "fulfillment_id": f"F{n}",
        "tracking_number": tracking if tracking is not None else f"TRK{n}",
        "carrier_name": carrier,
        "order_created_at": iso(ordered),
        "fulfilled_at": iso(fulfilled) if fulfilled is not None else None,
        "normalized_tracking_status": status,
        "last_scan_at": iso(scan) if scan is not None else None,
        "delivered_at": iso(delivered) if delivered is not None else None,
        "exception": exc,
    }


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(autouse=True)
def seeded(database):
    repo.ready()
    for t in (
        "shipping_shipments",
        "shipping_sync_runs",
        "shipping_manual_status",
        "shipping_order_checks",
        "shipping_notes",
    ):
        run(f"DELETE FROM {t}")
    repo.save_shipments(
        [
            rec(1, ordered=12),  # not dispatched 12 days -> red
            rec(2, ordered=20, fulfilled=10, scan=1),  # dispatched 10 days ago -> red
            rec(3, ordered=20, fulfilled=7, scan=6),  # orange + no movement (scan 6 days old)
            rec(4, ordered=3, fulfilled=1, scan=0),  # on track
            rec(5, ordered=30, fulfilled=20, status="delivered", delivered=2),
            rec(6, carrier="Amazon Logistics", ordered=15, fulfilled=12),  # unconfirmed
            rec(
                7, ordered=10, fulfilled=9, exc="failed_delivery", status="failed_delivery", scan=0
            ),
        ]
        + [rec(100 + i, ordered=2, fulfilled=1, scan=0) for i in range(15)]
    )
    repo.upsert_order_checks(
        [{"order_number": "#4", "cancelled": True, "financial_status": "PAID"}]
    )
    yield


def get(app, path):
    return local_client(app).get(path)


def by_order(app, view=""):
    r = get(app, f"/api/shipping/shipments?size=200&view={view}")
    assert r.status_code == 200
    return {x["order_number"]: x for x in r.json()["rows"]}


def test_flow_rules_and_flags(app):
    rows = by_order(app)
    assert rows["#1"]["cat"] == "red" and rows["#1"]["stage"] == "pre_dispatch"
    assert rows["#2"]["cat"] == "red" and rows["#2"]["stage"] == "dispatched"
    assert rows["#3"]["cat"] == "orange" and rows["#3"]["no_move"] is True
    assert rows["#6"]["cat"] == "unconfirmed"
    assert "#4" not in rows  # cancelled order is left out
    assert "#5" not in rows  # delivered leaves the active queue
    assert by_order(app, "delivered")["#5"]["cat"] == "delivered"
    assert "#7" in by_order(app, "exception")


def test_summary_counts_match_rows(app):
    s = get(app, "/api/shipping/summary").json()
    k = s["kpis"]
    assert k["red"] == 3 and k["unconfirmed"] == 1 and k["nomove"] == 1 and k["delivered"] == 1
    assert s["total"] == 21 and s["empty"] is False


def test_paging_is_server_side(app):
    r = get(app, "/api/shipping/shipments?size=10&page=1").json()
    assert len(r["rows"]) == 10 and r["total"] == 20 and r["pages"] == 2 and r["page"] == 1
    assert get(app, "/api/shipping/shipments?view=bogus").status_code == 400


def test_manual_status_needs_csrf_and_overrides_unconfirmed_only(app):
    c = local_client(app)
    body = {"order_number": "#6", "tracking_number": "TRK6", "status": "delivered"}
    assert c.post("/api/shipping/shipments/manual", json=body).status_code == 403  # no CSRF header
    assert c.post("/api/shipping/shipments/manual", json=body, headers=H).status_code == 200
    assert "#6" not in by_order(app)  # now delivered
    bad = c.post("/api/shipping/shipments/manual", json={**body, "status": "nonsense"}, headers=H)
    assert bad.status_code == 400
    missing = c.post(
        "/api/shipping/shipments/manual", json={**body, "order_number": "#999"}, headers=H
    )
    assert missing.status_code == 404
    c.post(
        "/api/shipping/shipments/manual",
        json={"order_number": "#1", "tracking_number": "TRK1", "status": "delivered"},
        headers=H,
    )
    assert by_order(app)["#1"]["cat"] == "red"  # a DHL shipment is not overridden by a manual mark


def test_notes_and_detail(app):
    c = local_client(app)
    assert (
        c.post(
            "/api/shipping/notes",
            json={"order_number": "#1", "note": "Called the carrier"},
            headers=H,
        ).status_code
        == 200
    )
    d = get(app, "/api/shipping/shipments/detail?order=%231").json()
    assert d["shipment"]["note"] == "Called the carrier" and len(d["packages"]) == 1
    assert get(app, "/api/shipping/shipments/detail?order=%23nope").status_code == 404


def test_exports_and_formula_safety(app):
    r = get(app, "/api/shipping/export/escalation")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert '"#1"' in r.text and '"#2"' in r.text
    repo.save_shipments(
        [rec(500, tracking="=HYPERLINK(1)", carrier="Amazon Logistics", ordered=15, fulfilled=12)]
    )
    v = get(app, "/api/shipping/export/verify").text
    assert "'=HYPERLINK(1)" in v and '"=HYPERLINK' not in v
    assert get(app, "/api/shipping/export/other").status_code == 404


def test_analytics_and_checks_have_real_numbers(app):
    a = get(app, "/api/shipping/analytics").json()
    assert (
        a["kpis"]["critical"] == 3 and a["kpis"]["value_at_risk"] is None
    )  # no order totals loaded: not invented
    assert sum(x["count"] for x in a["aging"]) == 20 - 1  # unconfirmed is not in the aging bands
    c = get(app, "/api/shipping/checks").json()
    assert c["checklist"]["total"] == 1 and c["mcf"] == []


def test_remote_clients_are_refused(app):
    r = remote_client(app).get("/api/shipping/summary")
    assert r.status_code == 403 and r.json()["code"] == "local_only"
    assert remote_client(app).post("/api/shipping/sync", headers=H).status_code == 403


def test_sync_without_credentials_records_a_failed_run_and_calls_nothing(app, monkeypatch):
    nocreds = ShippingConfig(
        "shop.myshopify.com", "", "", "", "2026-01", "2026-07-01", "Asia/Kolkata", 2, 4, 6, 9
    )
    monkeypatch.setattr(sync, "load_config", lambda: nocreds)
    before = len(repo.load_shipments())
    r = local_client(app).post("/api/shipping/sync", headers=H)
    assert r.status_code == 200 and r.json()["sync_status"] == "failed"
    assert len(repo.load_shipments()) == before
    assert get(app, "/api/shipping/runs").json()["warning"]["level"] == "error"


def test_package_fulfilled_by_hand_is_covered_when_tracked_packages_are_delivered(app):
    def pkg(n, fid, tracking, carrier, status="in_transit", delivered=None):
        return rec(
            n,
            carrier=carrier,
            ordered=30,
            fulfilled=20,
            status=status,
            delivered=delivered,
            tracking=tracking,
        ) | {"fulfillment_id": fid}

    repo.save_shipments(
        [
            pkg(900, "F900a", "DHL900", "DHL Express", "delivered", 5),
            pkg(900, "F900b", "", ""),  # covered
            pkg(901, "F901a", "DHL901", "DHL Express", "in_transit"),
            pkg(901, "F901b", "", ""),  # tracked not delivered
            pkg(902, "F902a", "DHL902", "DHL Express", "delivered", 5),
            pkg(902, "F902b", "", ""),  # order not FULFILLED
            pkg(903, "F903a", "DHL903", "DHL Express", "delivered", 5),
            pkg(903, "F903b", "", ""),  # team already marked it
            pkg(904, "F904a", "", ""),  # nothing tracked at all
        ]
    )
    done = {"fulfillment_status": "FULFILLED", "financial_status": "PAID", "cancelled": False}
    repo.upsert_order_checks(
        [
            {**done, "order_number": "#900"},
            {**done, "order_number": "#901"},
            {**done, "order_number": "#902", "fulfillment_status": "PARTIALLY_FULFILLED"},
            {**done, "order_number": "#903"},
            {**done, "order_number": "#904"},
        ]
    )
    repo.set_manual_status("#903", "", "in_transit", "team")
    cats = {(r["order_number"], r["fulfillment_id"]): r["cat"] for r in service.classify()}
    assert cats[("#900", "F900b")] == "covered"
    assert cats[("#901", "F901b")] == "unconfirmed"  # a tracked package is still in transit
    assert (
        cats[("#902", "F902b")] == "unconfirmed"
    )  # Shopify does not say the whole order is fulfilled
    assert cats[("#903", "F903b")] == "unconfirmed"  # the team's own mark wins
    assert cats[("#904", "F904a")] == "unconfirmed"  # no tracked package to rely on
    assert "#900" not in by_order(app) and "#900" in by_order(app, "covered")
    k = get(app, "/api/shipping/summary").json()["kpis"]
    assert k["covered"] == 1 and get(app, "/api/shipping/shipments?view=covered").status_code == 200


def test_status_filter_offers_only_statuses_that_have_listed_shipments(app):
    statuses = get(app, "/api/shipping/shipments").json()["facets"]["statuses"]
    assert "delivered" not in statuses and "in_transit" in statuses
