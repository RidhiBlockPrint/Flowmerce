"""Order totals, order checks, the schema upgrade, the Supabase import and the alert digest.
No network: Shopify and Supabase are replaced by fakes, SMTP is never reached."""

import json
from datetime import UTC, datetime

import pytest

from flowmerce.modules.seo.db import all_rows, run
from flowmerce.modules.shipping import alerts, importer, repo, schema, service
from flowmerce.modules.shipping.config import ShippingConfig
from flowmerce.modules.shipping.normalize import normalize_order_checks, normalize_orders
from flowmerce.modules.shipping.sync import run_sync

NOW = datetime(2026, 10, 30, 6, 0, tzinfo=UTC)
TABLES = (
    "shipping_shipments",
    "shipping_sync_runs",
    "shipping_manual_status",
    "shipping_order_checks",
    "shipping_notes",
)


def order(n=1, note="", fulfillment="UNFULFILLED", cancelled=None, paid="PAID", total="120.50"):
    return {
        "id": f"gid://shopify/Order/{n}",
        "name": f"#{n}",
        "createdAt": "2026-10-01T04:00:00Z",
        "cancelledAt": cancelled,
        "displayFulfillmentStatus": fulfillment,
        "displayFinancialStatus": paid,
        "note": note,
        "totalPriceSet": {"shopMoney": {"amount": total, "currencyCode": "USD"}},
        "fulfillments": [
            {
                "id": f"gid://shopify/Fulfillment/{n}",
                "status": "SUCCESS",
                "createdAt": "2026-10-02T06:00:00Z",
                "displayStatus": "IN_TRANSIT",
                "estimatedDeliveryAt": None,
                "deliveredAt": None,
                "trackingInfo": [{"number": f"T{n}", "company": "DHL Express", "url": ""}],
            }
        ],
    }


def cfg():
    return ShippingConfig(
        "shop.myshopify.com", "", "", "", "2026-01", "2026-07-01", "Asia/Kolkata", 2, 4, 6, 9
    )


class FakeShopify:
    def __init__(self, orders):
        self.orders = orders

    def fetch_orders(self, since):
        yield from self.orders


@pytest.fixture(autouse=True)
def clean(database):
    repo.ready()
    for t in TABLES:
        run(f"DELETE FROM {t}")


def test_normalize_keeps_order_total_and_builds_order_checks():
    row = next(normalize_orders([order(5)]))
    assert row["order_total"] == 120.5 and row["order_currency"] == "USD"
    check = next(normalize_order_checks([order(5, note="DONE", cancelled="2026-10-03T00:00:00Z")]))
    assert (
        check["note"] == "DONE"
        and check["cancelled"] is True
        and check["fulfillment_status"] == "UNFULFILLED"
    )
    assert check["financial_status"] == "PAID" and check["order_total"] == 120.5


def test_sync_saves_totals_and_order_checks_and_value_at_risk_is_real():
    store = repo.SqliteStore()
    result = run_sync(cfg(), FakeShopify([order(1, note="done"), order(2)]), store, now=NOW)
    assert result["sync_status"] == "success"
    assert len(repo.order_checks()) == 2 and repo.load_shipments()
    a = service.analytics(NOW)
    assert a["kpis"]["value_at_risk"] == pytest.approx(
        241.0
    )  # both orders are 9+ days old: 2 x 120.50
    assert [m["order_number"] for m in service.mcf_list(NOW)] == [
        "#1"
    ]  # only the one whose note says done


def test_cancelled_and_refunded_orders_are_left_out():
    run_sync(
        cfg(),
        FakeShopify(
            [order(1), order(2, paid="REFUNDED"), order(3, cancelled="2026-10-04T00:00:00Z")]
        ),
        repo.SqliteStore(),
        now=NOW,
    )
    assert {r["order_number"] for r in service.classify(NOW)} == {"#1"}


def test_schema_upgrade_adds_columns_to_a_version_1_database():
    run("DROP TABLE shipping_notes")
    run("ALTER TABLE shipping_shipments DROP COLUMN order_total")
    run("ALTER TABLE shipping_shipments DROP COLUMN order_currency")
    schema.ensure_schema()
    cols = {r["name"] for r in all_rows("PRAGMA table_info(shipping_shipments)")}
    assert {"order_total", "order_currency"} <= cols and schema.schema_version() == schema.VERSION


class FakeResponse:
    def __init__(self, rows):
        self.body = json.dumps(rows).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


def fake_supabase(tables):
    seen = []

    def opener(req, timeout=0):
        seen.append(req.get_method())
        name = req.full_url.split("/rest/v1/")[1].split("?")[0]
        return FakeResponse(tables[name])

    return opener, seen


def test_supabase_import_is_read_only_idempotent_and_verified(monkeypatch):
    monkeypatch.setattr(
        importer,
        "env",
        lambda k, d="": {
            "SUPABASE_URL": "https://x.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_test",
        }.get(k, d),
    )
    monkeypatch.setattr(importer, "backup_database", lambda: "memory")
    shipment = {f: None for f in repo.SHIPMENT_FIELDS} | {
        "shopify_order_id": "o1",
        "order_number": "#1",
        "fulfillment_id": "f1",
        "tracking_number": "T1",
        "order_total": 99.0,
        "order_currency": "USD",
        "order_created_at": "2026-10-20T00:00:00+00:00",
    }
    tables = {
        "shipments": [shipment],
        "sync_runs": [
            {
                "started_at": "2026-10-30T00:00:00+00:00",
                "completed_at": None,
                "sync_status": "success",
            }
        ],
        "order_checks": [
            {
                "order_number": "#1",
                "note": "DONE",
                "cancelled": False,
                "fulfillment_status": "UNFULFILLED",
                "order_total": 99.0,
            }
        ],
        "manual_status": [
            {
                "order_number": "#1",
                "tracking_number": "T1",
                "status": "delivered",
                "updated_by": "team",
            },
            {"order_number": "#2", "status": "bogus"},
        ],
    }
    opener, methods = fake_supabase(tables)
    dry = importer.import_from_supabase(dry_run=True, opener=opener)
    assert dry["would_create"] == 1 and dry["manual_status"] == 1 and not repo.load_shipments()
    first = importer.import_from_supabase(opener=opener)
    second = importer.import_from_supabase(opener=opener)
    assert (
        first["created"] == 1
        and first["verified"]
        and second["created"] == 0
        and second["updated"] == 1
    )
    assert set(methods) == {"GET"}  # Supabase is only ever read
    assert (
        len(repo.order_checks()) == 1 and repo.manual_statuses()["#1|T1"]["status"] == "delivered"
    )
    assert len(repo.list_runs(10)) == 1  # the same run is not added twice


def test_supabase_import_without_credentials_fails_with_a_clear_message(monkeypatch):
    monkeypatch.setattr(importer, "env", lambda k, d="": d)
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        importer.import_from_supabase(dry_run=True)


def test_alert_digest_matches_the_dashboard_rules_and_never_emails_without_smtp():
    records = [
        {
            "order_number": "#1",
            "carrier_name": "DHL Express",
            "tracking_number": "T1",
            "order_created_at": "2026-10-01T00:00:00+00:00",
            "fulfilled_at": "2026-10-02T00:00:00+00:00",
            "normalized_tracking_status": "in_transit",
        },
        {
            "order_number": "#2",
            "carrier_name": "Amazon Logistics",
            "tracking_number": "T2",
            "order_created_at": "2026-10-01T00:00:00+00:00",
            "fulfilled_at": "2026-10-02T00:00:00+00:00",
            "normalized_tracking_status": "in_transit",
        },
    ]
    critical, stuck = alerts.build_digest(records, NOW)
    assert [c["order"] for c in critical] == [
        "#1"
    ] and stuck == []  # Amazon is never counted as critical
    assert alerts.run_alerts(records, now=NOW, env={}).startswith("alert skipped")


def test_prune_removes_only_rows_supabase_no_longer_has(monkeypatch):
    monkeypatch.setattr(
        importer,
        "env",
        lambda k, d="": {
            "SUPABASE_URL": "https://x.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_test",
        }.get(k, d),
    )
    monkeypatch.setattr(importer, "backup_database", lambda: "memory")
    base = {f: None for f in repo.SHIPMENT_FIELDS}
    repo.save_shipments(
        [
            base
            | {
                "shopify_order_id": "gid://old",
                "order_number": "#old",
                "fulfillment_id": "fold",
                "tracking_number": "OLD",
            }
        ]
    )
    live = base | {
        "shopify_order_id": "gid://1",
        "order_number": "#1",
        "fulfillment_id": "f1",
        "tracking_number": "T1",
        "order_created_at": "2026-10-20T00:00:00+00:00",
    }
    opener, _ = fake_supabase(
        {"shipments": [live], "sync_runs": [], "order_checks": [], "manual_status": []}
    )
    dry = importer.import_from_supabase(dry_run=True, opener=opener, prune=True)
    assert (
        dry["stale_local_rows"] == 1 and len(repo.load_shipments()) == 1
    )  # a dry run deletes nothing
    keep = importer.import_from_supabase(opener=opener)
    assert (
        len(repo.load_shipments()) == 2 and "pruned" not in keep
    )  # without --prune nothing is removed
    done = importer.import_from_supabase(opener=opener, prune=True)
    assert done["pruned"] == 1 and set(repo.load_shipments()) == {"f1|T1"}


def test_config_accepts_the_original_tracker_setting_names(monkeypatch):
    from flowmerce.modules.shipping import config as shipping_config

    values = {
        "SHOPIFY_STORE_DOMAIN": "orig.myshopify.com",
        "SHOPIFY_CLIENT_ID": "id1",
        "SHOPIFY_CLIENT_SECRET": "sec1",
        "ORDERS_SINCE": "2026-08-01",
        "RED_THRESHOLD_DAYS": "10",
    }
    monkeypatch.setattr(shipping_config, "env", lambda k, d="": values.get(k, d))
    c = shipping_config.load_config()
    assert (c.shop_domain, c.client_id, c.orders_since, c.red_days) == (
        "orig.myshopify.com",
        "id1",
        "2026-08-01",
        10,
    )
    assert c.has_shopify_credentials
    values["SHIPPING_SHOPIFY_CLIENT_ID"] = "id2"  # the Shipping name wins when both exist
    assert shipping_config.load_config().client_id == "id2"


def test_recheck_asks_shopify_about_missing_orders_and_picks_up_added_tracking():
    from flowmerce.modules.shipping.sync import recheck_missing

    base = {f: None for f in repo.SHIPMENT_FIELDS}
    repo.save_shipments(
        [
            base
            | {
                "shopify_order_id": "gid://shopify/Order/70",
                "order_number": "#70",
                "fulfillment_id": "gid://shopify/Fulfillment/70",
                "tracking_number": "",
                "carrier_name": "",
                "order_created_at": "2026-09-01T00:00:00+00:00",
                "fulfilled_at": "2026-09-02T00:00:00+00:00",
                "last_checked_at": "2026-10-01T00:00:00+00:00",
            }
        ]
    )
    assert [r["order_number"] for r in service.issues(NOW)["missing"]] == ["#70"]
    asked = []

    class FakeShopify:
        def fetch_orders_by_name(self, names):
            asked.extend(names)
            o = order(70)
            o["name"], o["id"] = "#70", "gid://shopify/Order/70"
            o["fulfillments"][0]["id"] = "gid://shopify/Fulfillment/70"
            yield o

    result = recheck_missing(FakeShopify())
    assert asked == ["#70"] and result["fixed"] == 1 and result["still_missing"] == 0
    assert (
        service.issues(NOW)["missing"] == []
    )  # the old empty-tracking row is superseded by the new one
    assert not repo.list_runs(10) or all(
        r["started_at"] != "" for r in repo.list_runs(10)
    )  # no sync-run row required
