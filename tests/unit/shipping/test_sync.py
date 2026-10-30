"""Sync behaviour (ported from the original tracker tests) against the Flowmerce SQLite store."""

from datetime import UTC, datetime

import pytest

from flowmerce.modules.seo.db import run
from flowmerce.modules.shipping import repo
from flowmerce.modules.shipping.carriers import CarrierAdapter, TrackingResult
from flowmerce.modules.shipping.config import ShippingConfig
from flowmerce.modules.shipping.shopify import ShopifyError
from flowmerce.modules.shipping.sync import run_sync

NOW = datetime(2026, 10, 17, 2, 0, tzinfo=UTC)


def sample_order(oid="gid://shopify/Order/1", fid="gid://shopify/Fulfillment/10", number="A1"):
    return {
        "id": oid,
        "name": "#1001",
        "createdAt": "2026-10-01T04:00:00Z",
        "cancelledAt": None,
        "fulfillments": [
            {
                "id": fid,
                "status": "SUCCESS",
                "createdAt": "2026-10-02T06:00:00Z",
                "displayStatus": "IN_TRANSIT",
                "estimatedDeliveryAt": None,
                "deliveredAt": None,
                "trackingInfo": [{"number": number, "company": "DHL Express", "url": ""}],
            }
        ],
    }


class FakeShopify:
    def __init__(self, orders=None, fail=None):
        self.orders, self.fail = orders or [], fail

    def fetch_orders(self, since):
        if self.fail:
            raise ShopifyError(self.fail)
        yield from self.orders


class OkCarrier(CarrierAdapter):
    def __init__(self, scan_at):
        self.scan_at = scan_at

    def track(self, n):
        return TrackingResult(
            raw_status="IN_TRANSIT", last_scan_at=self.scan_at, last_scan_description="Hub"
        )


class FailingCarrier(CarrierAdapter):
    def track(self, n):
        raise RuntimeError("carrier 503")


def cfg():
    return ShippingConfig(
        "shop.myshopify.com", "", "", "", "2026-01", "2026-07-01", "Asia/Kolkata", 2, 4, 6, 9
    )


@pytest.fixture(autouse=True)
def clean(database):
    repo.ready()
    for t in (
        "shipping_shipments",
        "shipping_sync_runs",
        "shipping_manual_status",
        "shipping_order_checks",
        "shipping_notes",
    ):
        run(f"DELETE FROM {t}")


def one():
    return list(repo.load_shipments().values())[0]


def test_first_run_creates_and_second_run_does_not_duplicate():
    store, shop = repo.SqliteStore(), FakeShopify([sample_order()])
    r1 = run_sync(cfg(), shop, store, lookup=lambda c: OkCarrier(None), now=NOW)
    r2 = run_sync(cfg(), shop, store, lookup=lambda c: OkCarrier(None), now=NOW)
    assert r1["sync_status"] == "success" and r1["shipments_created"] == 1
    assert r2["shipments_created"] == 0 and r2["shipments_updated"] == 1
    assert len(store.load()) == 1


def test_duplicate_orders_in_one_fetch_are_processed_once():
    run_ = run_sync(
        cfg(), FakeShopify([sample_order(), sample_order()]), repo.SqliteStore(), now=NOW
    )
    assert run_["shipments_created"] == 1 and len(repo.load_shipments()) == 1


def test_shopify_failure_keeps_previously_saved_data():
    store = repo.SqliteStore()
    run_sync(cfg(), FakeShopify([sample_order()]), store, now=NOW)
    before = store.load()
    bad = run_sync(cfg(), FakeShopify(fail="Shopify HTTP 503"), store, now=NOW)
    assert bad["sync_status"] == "failed" and "503" in bad["error_summary"]
    assert store.load() == before
    assert repo.list_runs(1)[0]["sync_status"] == "failed"


def test_carrier_scan_is_saved_and_labelled():
    scan = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
    run_sync(
        cfg(),
        FakeShopify([sample_order()]),
        repo.SqliteStore(),
        lookup=lambda c: OkCarrier(scan),
        now=NOW,
    )
    rec = one()
    assert rec["tracking_source"] == "carrier" and rec["last_scan_at"] == scan.isoformat()


def test_carrier_failure_preserves_previous_scan():
    scan = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
    store = repo.SqliteStore()
    run_sync(cfg(), FakeShopify([sample_order()]), store, lookup=lambda c: OkCarrier(scan), now=NOW)
    run_ = run_sync(
        cfg(), FakeShopify([sample_order()]), store, lookup=lambda c: FailingCarrier(), now=NOW
    )
    rec = one()
    assert rec["last_scan_at"] == scan.isoformat() and "503" in rec["carrier_error"]
    assert run_["sync_status"] == "partial"


def test_no_carrier_configured_never_invents_a_scan():
    run_sync(cfg(), FakeShopify([sample_order()]), repo.SqliteStore(), now=NOW)
    rec = one()
    assert rec["last_scan_at"] is None and rec["tracking_source"] == "shopify"
