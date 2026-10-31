"""Order-level classification: the groups, delay tiers, flags and mixed-carrier handling agreed with the owner."""

from datetime import UTC, datetime, timedelta

import pytest
from tests.fixtures.seo import local_client, remote_client

from flowmerce.modules.seo.app import create_app
from flowmerce.modules.seo.db import run
from flowmerce.modules.shipping import orders, repo

H = {"X-Requested-With": "blog-ops"}
NOW = datetime.now(UTC)
TABLES = (
    "shipping_shipments",
    "shipping_sync_runs",
    "shipping_manual_status",
    "shipping_order_checks",
    "shipping_notes",
)


def iso(days_ago):
    return (NOW - timedelta(days=days_ago)).isoformat()


def ship(
    n,
    *,
    fid=None,
    carrier="DHL Express",
    tracking=None,
    ordered=30,
    fulfilled=None,
    delivered=None,
    scan=None,
    status=None,
    checked=None,
):
    tracking = f"TRK{n}" if tracking is None else tracking
    return {
        "shopify_order_id": f"gid://shopify/Order/{n}",
        "order_number": f"#{n}",
        "fulfillment_id": fid or f"F{n}",
        "tracking_number": tracking,
        "carrier_name": carrier,
        "order_created_at": iso(ordered),
        "fulfilled_at": iso(fulfilled) if fulfilled is not None else None,
        "delivered_at": iso(delivered) if delivered is not None else None,
        "last_scan_at": iso(scan) if scan is not None else None,
        "normalized_tracking_status": status
        or ("delivered" if delivered is not None else "in_transit"),
        "last_checked_at": checked or iso(0),
    }


def check(n, status="FULFILLED", note="", ordered=30, cancelled=False, paid="PAID"):
    return {
        "order_number": f"#{n}",
        "order_created_at": iso(ordered),
        "fulfillment_status": status,
        "note": note,
        "cancelled": cancelled,
        "financial_status": paid,
        "shopify_order_id": f"gid://shopify/Order/{n}",
    }


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(autouse=True)
def clean(database):
    repo.ready()
    for t in TABLES:
        run(f"DELETE FROM {t}")


def groups():
    return {o["order_number"]: o for o in orders.build_orders()}


def test_delivered_orders_show_transit_time_and_highlight_slow_ones():
    repo.save_shipments(
        [
            ship(1, fulfilled=10, delivered=7),
            ship(2, fulfilled=12, delivered=6),
            ship(3, fulfilled=30, delivered=16),
        ]
    )
    g = groups()
    assert (
        g["#1"]["group"] == "delivered" and g["#1"]["transit_days"] == 3 and g["#1"]["tier"] is None
    )
    assert (
        g["#2"]["transit_days"] == 6 and g["#2"]["tier"] == "orange"
    )  # took longer than expected: highlighted
    assert (
        g["#3"]["transit_days"] == 14
        and g["#3"]["tier"] == "critical"
        and g["#3"]["flags"] == ["delivered_late"]
    )
    assert g["#3"]["needs_action"] is True and not g["#1"]["needs_action"]


def test_in_transit_and_the_four_delay_tiers_use_days_since_fulfilled():
    repo.save_shipments(
        [
            ship(10, fulfilled=2),
            ship(11, fulfilled=3),
            ship(12, fulfilled=4),
            ship(13, fulfilled=5),
            ship(14, fulfilled=6),
            ship(15, fulfilled=8),
            ship(16, fulfilled=9),
            ship(17, fulfilled=12),
            ship(18, fulfilled=13),
            ship(19, fulfilled=40),
        ]
    )
    g = groups()
    assert (g["#10"]["group"], g["#11"]["group"]) == ("in_transit", "in_transit")
    got = {n: (g[f"#{n}"]["group"], g[f"#{n}"]["tier"]) for n in range(12, 20)}
    assert got == {
        12: ("delayed", "yellow"),
        13: ("delayed", "yellow"),
        14: ("delayed", "orange"),
        15: ("delayed", "orange"),
        16: ("delayed", "red"),
        17: ("delayed", "red"),
        18: ("delayed", "critical"),
        19: ("delayed", "critical"),
    }


def test_every_carrier_uses_the_same_delay_days():
    repo.save_shipments(
        [
            ship(20, carrier="Amazon Logistics", fulfilled=10),
            ship(21, carrier="DHL Express", fulfilled=10),
            ship(22, carrier="USPS", fulfilled=10),
            ship(23, carrier="FedEx", fulfilled=10),
        ]
    )
    assert {groups()[f"#{n}"]["tier"] for n in (20, 21, 22, 23)} == {"red"}


def test_unfulfilled_orders_come_from_the_order_checks_and_amazon_mcf_counts_as_delivered():
    repo.upsert_order_checks(
        [
            check(30, "UNFULFILLED", ordered=20),
            check(31, "UNFULFILLED", note="MCF DONE", ordered=20),
            check(32, "UNFULFILLED", ordered=1),
            check(
                33, "UNFULFILLED", note="MCF DONE", ordered=1
            ),  # handed to Amazon only yesterday: not yet
            check(34, "PARTIALLY_FULFILLED", note="DONE", ordered=20),
        ]
    )
    repo.save_shipments(
        [ship(34, fulfilled=15, carrier="DHL Express")]
    )  # an open DHL package, still delayed
    repo.save_shipments([ship(35, fulfilled=15, carrier="USPS")])
    repo.set_manual_status("#35", "TRK35", "lost", "team")
    repo.upsert_order_checks([check(35, "PARTIALLY_FULFILLED", note="DONE", ordered=20)])
    g = groups()
    assert (
        g["#30"]["group"] == "unfulfilled"
        and g["#30"]["tier"] is None  # waiting to be fulfilled is not a delay: no tier
        and g["#30"]["days"] == 20
        and not g["#30"]["flags"]
    )
    assert (
        g["#31"]["group"] == "delivered"
        and g["#31"]["delivered_by"] == "amazon_mcf"
        and not g["#31"]["needs_action"]
    )
    assert g["#32"]["group"] == "unfulfilled" and g["#32"]["tier"] is None
    assert g["#33"]["group"] == "unfulfilled" and g["#33"]["delivered_by"] is None
    assert (
        g["#34"]["group"] == "delivered" and g["#34"]["delivered_by"] == "amazon_mcf"
    )  # delayed DHL part does not hold it back
    assert g["#35"]["group"] == "lost_missing"  # a team mark of lost still wins


def test_lost_missing_by_team_mark_or_no_update_for_14_days():
    repo.save_shipments(
        [
            ship(40, fulfilled=10, scan=1),
            ship(41, fulfilled=30, scan=15),
            ship(42, fulfilled=30, scan=6),
            ship(43, carrier="Amazon Logistics", fulfilled=10),
            ship(44, carrier="Amazon Logistics", fulfilled=10),
        ]
    )
    repo.set_manual_status("#40", "TRK40", "lost", "team")
    repo.set_manual_status("#43", "TRK43", "failed", "team")
    repo.set_manual_status("#44", "TRK44", "delivered", "team")
    g = groups()
    assert g["#40"]["group"] == "lost_missing" and g["#43"]["group"] == "lost_missing"
    assert g["#41"]["group"] == "lost_missing"  # last scan 15 days ago
    assert g["#42"]["group"] == "delayed" and g["#42"]["flags"] == [
        "no_movement"
    ]  # 6 days: needs action, not lost
    assert g["#44"]["group"] == "delivered"  # a team mark can confirm any carrier


def test_no_tracking_id_and_no_carrier_groups_look_at_the_whole_order():
    repo.save_shipments(
        [
            ship(
                50, carrier="Amazon Logistics", tracking="", fulfilled=5
            ),  # carrier known, no tracking id
            ship(51, carrier="", tracking="", fulfilled=5),  # nothing at all
            ship(52, carrier="DHL Express", fulfilled=9, delivered=5),  # tracked and delivered ...
            ship(
                52, fid="F52b", carrier="", tracking="", fulfilled=9
            ),  # ... plus a hand-fulfilled package: still delivered
            ship(53, carrier="Amazon Logistics", tracking="TBA53", fulfilled=2),  # open tracked ...
            ship(
                53, fid="F53b", carrier="", tracking="", fulfilled=2
            ),  # ... untracked package does not make it "no carrier"
        ]
    )
    g = groups()
    assert g["#50"]["group"] == "no_tracking_id" and g["#51"]["group"] == "no_carrier"
    assert g["#52"]["group"] == "delivered" and g["#52"]["carriers"] == ["DHL Express"]
    assert g["#53"]["group"] == "in_transit" and g["#53"]["carriers"] == ["Amazon Logistics"]


def test_rows_shopify_no_longer_reports_do_not_create_phantom_shipments_and_cancelled_orders_are_excluded():
    repo.save_shipments(
        [
            ship(
                60, fid="F60", tracking="", fulfilled=5, checked=iso(8)
            ),  # tracking was added to this fulfillment later
            ship(60, fid="F60", tracking="TRK60", fulfilled=5),
            ship(
                61, fid="F61", tracking="GONE61", fulfilled=5, checked=iso(8)
            ),  # fulfillment Shopify stopped returning
            ship(61, fid="F61b", tracking="KEEP61", fulfilled=5),
            ship(62, fulfilled=5),
        ]
    )
    repo.upsert_order_checks([check(62, cancelled=True)])
    g = groups()
    assert [s["tracking_number"] for s in g["#60"]["shipments"]] == ["TRK60"]
    assert [s["tracking_number"] for s in g["#61"]["shipments"]] == ["KEEP61"]
    assert "#62" not in g
    assert len(repo.load_shipments()) == 5  # nothing was deleted


def test_orders_api_groups_paging_filters_and_access(app):
    repo.save_shipments(
        [ship(70 + i, fulfilled=15) for i in range(12)] + [ship(90, fulfilled=10, delivered=8)]
    )
    c = local_client(app)
    r = c.get("/api/shipping/orders?group=delayed&size=10").json()
    assert (
        r["total"] == 12
        and len(r["rows"]) == 10
        and r["pages"] == 2
        and r["counts"]["delayed_tiers"]["critical"] == 12
    )
    assert c.get("/api/shipping/orders?group=delivered").json()["total"] == 1
    assert c.get("/api/shipping/orders?group=needs_action").json()["total"] == 0
    assert c.get("/api/shipping/orders?group=bogus").status_code == 400
    assert c.get("/api/shipping/orders?tier=bogus").status_code == 400
    assert c.get("/api/shipping/orders/detail?order=%2370").json()["order_number"] == "#70"
    assert c.get("/api/shipping/orders/detail?order=%23nope").status_code == 404
    assert c.get("/api/shipping/orders/overview").json()["counts"]["delayed"] == 12
    a = c.get("/api/shipping/orders/analytics").json()
    assert a["carriers"][0]["name"] == "DHL Express" and a["delivered_shipments"] == 1
    assert c.get("/api/shipping/orders/export?group=delayed").text.count("\n") == 13
    assert remote_client(app).get("/api/shipping/orders").status_code == 403


def test_partner_carrier_delivered_and_only_amazon_open_counts_as_delivered():
    repo.save_shipments(
        [
            ship(80, carrier="DHL Express", fulfilled=12, delivered=8),  # partner delivered ...
            ship(
                80, fid="F80b", carrier="Amazon Logistics", tracking="TBA80", fulfilled=12
            ),  # ... Amazon never acknowledged
            ship(81, carrier="USPS", fulfilled=12),  # a partner parcel is still open: stays delayed
            ship(81, fid="F81b", carrier="Amazon Logistics", tracking="TBA81", fulfilled=12),
            ship(
                82, carrier="Amazon Logistics", tracking="TBA82", fulfilled=12
            ),  # Amazon only: still delayed
            ship(83, carrier="FedEx", fulfilled=12, delivered=8),
            ship(83, fid="F83b", carrier="Amazon Logistics", tracking="TBA83", fulfilled=12),
        ]
    )
    repo.set_manual_status("#83", "TBA83", "lost", "team")  # a team mark of lost still wins
    g = groups()
    assert g["#80"]["group"] == "delivered" and g["#80"]["delivered_by"] == "amazon_unconfirmed"
    assert g["#80"]["transit_days"] == 4 and g["#80"]["tier"] == "yellow"
    assert g["#81"]["group"] == "delayed" and g["#81"]["delivered_by"] is None
    assert g["#82"]["group"] == "delayed"
    assert g["#83"]["group"] == "lost_missing"


def test_open_orders_shopify_stopped_refreshing_are_not_counted_as_delayed():
    old = iso(5)
    repo.save_shipments(
        [
            ship(
                90, fulfilled=40, checked=iso(0)
            ),  # refreshed by the latest sync: genuinely delayed
            ship(
                91, fulfilled=40, checked=old
            ),  # older than Shopify's 60-day window: frozen five days ago
            ship(92, fulfilled=40, delivered=30, checked=old),  # delivered: its age does not matter
            ship(93, fulfilled=40, checked=old),  # team marked lost: the mark wins
            ship(
                94, carrier="Amazon Logistics", tracking="", fulfilled=40, checked=old
            ),  # no tracking id group is unchanged
        ]
    )
    repo.set_manual_status("#93", "TRK93", "lost", "team")
    g = groups()
    assert g["#90"]["group"] == "delayed" and g["#91"]["group"] == "stale"
    assert (
        g["#91"]["tier"] is None
        and g["#91"]["days"] == 40
        and "has not refreshed" in g["#91"]["action"]
    )
    assert g["#92"]["group"] == "delivered" and g["#93"]["group"] == "lost_missing"
    assert g["#94"]["group"] == "no_tracking_id"
    assert orders.counts(list(g.values()))["stale"] == 1
