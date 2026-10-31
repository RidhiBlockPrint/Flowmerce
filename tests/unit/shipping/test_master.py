"""The master database (orders, items, shipments, events) and its Shopify sync. No network: Shopify is a fake."""

import json

import pytest

from flowmerce.modules.shipping import master_db as mdb
from flowmerce.modules.shipping import master_sync as ms
from flowmerce.modules.shipping.shopify import ShopifyError


def money(v):
    return {"shopMoney": {"amount": str(v), "currencyCode": "USD"}}


def order(n=1001, updated="2026-10-20T10:00:00Z", status="PARTIALLY_FULFILLED"):
    return {
        "id": f"gid://shopify/Order/{n}",
        "legacyResourceId": str(n),
        "name": f"#{n}",
        "createdAt": "2026-10-10T08:00:00Z",
        "updatedAt": updated,
        "cancelledAt": None,
        "cancelReason": None,
        "closedAt": None,
        "displayFulfillmentStatus": status,
        "displayFinancialStatus": "PARTIALLY_REFUNDED",
        "currencyCode": "USD",
        "subtotalPriceSet": money(100),
        "totalDiscountsSet": money(5),
        "totalShippingPriceSet": money(10),
        "totalTaxSet": money(8),
        "totalPriceSet": money(118),
        "totalRefundedSet": money(20),
        "tags": ["vip"],
        "note": "Gift",
        "email": "ann@example.com",
        "phone": "+1 555 0100",
        "shippingAddress": {
            "name": "Ann Lee",
            "address1": "1 Main St",
            "address2": None,
            "city": "Austin",
            "provinceCode": "TX",
            "zip": "78701",
            "countryCodeV2": "US",
        },
        "billingAddress": {"name": "Ann Lee"},
        "lineItems": {
            "edges": [
                {
                    "node": {
                        "id": "gid://shopify/LineItem/1",
                        "sku": "SKU-A",
                        "title": "Napkins",
                        "variantTitle": "Set of 4",
                        "quantity": 3,
                        "currentQuantity": 2,
                        "unfulfilledQuantity": 1,
                        "originalUnitPriceSet": money(25),
                        "totalDiscountSet": money(5),
                        "image": {"url": "https://cdn.example/a.jpg"},
                    }
                },
                {
                    "node": {
                        "id": "gid://shopify/LineItem/2",
                        "sku": "SKU-B",
                        "title": "Runner",
                        "variantTitle": None,
                        "quantity": 1,
                        "currentQuantity": 1,
                        "unfulfilledQuantity": 1,
                        "originalUnitPriceSet": money(43),
                        "totalDiscountSet": money(0),
                        "image": None,
                    }
                },
            ]
        },
        "refunds": [
            {
                "refundLineItems": {
                    "edges": [
                        {"node": {"quantity": 1, "lineItem": {"id": "gid://shopify/LineItem/1"}}}
                    ]
                }
            }
        ],
        "fulfillments": [
            {
                "id": "gid://shopify/Fulfillment/77",
                "legacyResourceId": "77",
                "status": "SUCCESS",
                "createdAt": "2026-10-11T09:00:00Z",
                "displayStatus": "IN_TRANSIT",
                "estimatedDeliveryAt": "2026-10-18T00:00:00Z",
                "deliveredAt": None,
                "trackingInfo": [{"number": "TRK77", "company": "DHL Express", "url": ""}],
                "fulfillmentLineItems": {
                    "edges": [
                        {"node": {"quantity": 2, "lineItem": {"id": "gid://shopify/LineItem/1"}}}
                    ]
                },
                "events": {
                    "edges": [
                        {
                            "node": {
                                "id": "gid://shopify/FulfillmentEvent/1",
                                "status": "IN_TRANSIT",
                                "happenedAt": "2026-10-12T05:00:00Z",
                                "message": "Picked up",
                                "city": "Jaipur",
                                "province": None,
                                "country": "India",
                            }
                        },
                        {
                            "node": {
                                "id": "gid://shopify/FulfillmentEvent/2",
                                "status": "IN_TRANSIT",
                                "happenedAt": "2026-10-13T05:00:00Z",
                                "message": "Departed facility",
                                "city": "Delhi",
                                "province": None,
                                "country": "India",
                            }
                        },
                    ]
                },
            },
            {
                "id": "gid://shopify/Fulfillment/78",
                "legacyResourceId": "78",
                "status": "CANCELLED",
                "createdAt": "2026-10-11T10:00:00Z",
                "displayStatus": None,
                "estimatedDeliveryAt": None,
                "deliveredAt": None,
                "trackingInfo": [],
                "fulfillmentLineItems": {"edges": []},
                "events": {"edges": []},
            },
        ],
    }


@pytest.fixture(autouse=True)
def master():
    mdb.open_master(":memory:")
    yield


def test_schema_has_the_five_tables_with_the_designed_columns_and_postgres_ddl():
    cols = {t["name"]: {c["n"] for c in t["cols"]} for t in mdb.spec()}
    assert set(cols) == {"stores", "orders", "items", "shipments", "events"}
    assert {"id", "name", "placed_at", "financial_status", "stage", "hold_reason", "raw"} <= cols[
        "orders"
    ]
    assert {"sku", "open_qty", "route", "ppc_route"} <= cols["items"]
    assert {
        "tracking",
        "carrier",
        "step",
        "delivered_at",
        "last_scan_text",
        "gst_invoice_no",
    } <= cols["shipments"]
    assert {"external_id", "alert_kind", "assigned_to"} <= cols["events"]
    for t in cols:
        assert {r["name"] for r in mdb.all_rows(f'PRAGMA table_info("{t}")')} == cols[t]
    ddl = mdb.postgres_ddl()
    assert (
        'create table if not exists "orders"' in ddl
        and "text[]" in ddl
        and "jsonb" in ddl
        and "uuid" in ddl
    )


def test_a_shopify_order_is_copied_into_orders_items_shipments_and_events():
    counts = ms.save_order(order())
    assert counts == {
        "orders": 1,
        "items": 2,
        "shipments": 1,
        "events": 2,
    }  # the cancelled fulfillment is ignored
    o = mdb.get('SELECT * FROM "orders" WHERE "id" = 1001')
    assert (o["store"], o["name"], o["fulfillment_status"], o["financial_status"]) == (
        "RBP",
        "#1001",
        "partial",
        "partially_refunded",
    )
    assert (o["customer_name"], o["email"], o["ship_city"], o["ship_country"]) == (
        "Ann Lee",
        "ann@example.com",
        "Austin",
        "US",
    )
    assert (o["total"], o["refunded_amount"]) == (118.0, 20.0) and json.loads(o["tags"]) == ["vip"]
    assert (
        o["customer_id"] is None and o["risk_level"] is None and o["stage"] == "transit"
    )  # not provided: stays empty / default
    items = {r["sku"]: r for r in mdb.all_rows('SELECT * FROM "items"')}
    a = items["SKU-A"]
    assert (a["qty"], a["current_qty"], a["refunded_qty"], a["fulfilled_qty"], a["open_qty"]) == (
        3,
        2,
        1,
        2,
        1,
    )
    assert a["product_id"] is None and items["SKU-B"]["fulfilled_qty"] == 0
    s = mdb.get('SELECT * FROM "shipments"')
    assert (s["seq"], s["carrier"], s["eta"], s["last_scan_place"], s["last_scan_text"]) == (
        1,
        "DHL Express",
        "2026-10-18",
        "Delhi, India",
        "Departed facility",
    )
    assert json.loads(s["tracking"]) == ["TRK77"] and json.loads(s["cities"]) == ["Jaipur", "Delhi"]
    assert json.loads(s["items"]) == [{"item_id": 1, "qty": 2}]
    assert mdb.get('SELECT COUNT(*) c FROM "events" WHERE "type" = \'scan\'')["c"] == 2


def test_resync_is_idempotent_ignores_older_messages_and_never_touches_our_columns():
    ms.save_order(order())
    mdb.run(
        'UPDATE "orders" SET "hold_reason" = ?, "stage" = ? WHERE "id" = 1001',
        "Address problem",
        "checked",
    )
    mdb.run('UPDATE "items" SET "route" = ? WHERE "id" = 1', "mcf")
    mdb.run(
        'UPDATE "shipments" SET "kind" = ?, "step" = ?, "responsible" = ?',
        "mcf",
        "packed",
        "packer@example.com",
    )
    again = ms.save_order({**order(), "note": "Updated note", "updatedAt": "2026-10-21T10:00:00Z"})
    assert again["events"] == 0  # a scan already stored is not stored twice
    assert (
        mdb.counts()["orders"] == 1
        and mdb.counts()["items"] == 2
        and mdb.counts()["shipments"] == 1
        and mdb.counts()["events"] == 2
    )
    o = mdb.get('SELECT * FROM "orders"')
    assert (
        o["note"] == "Updated note"
        and o["hold_reason"] == "Address problem"
        and o["stage"] == "checked"
    )
    assert mdb.get('SELECT "route" FROM "items" WHERE "id" = 1')["route"] == "mcf"
    s = mdb.get('SELECT * FROM "shipments"')
    assert (s["kind"], s["step"], s["responsible"]) == ("mcf", "packed", "packer@example.com")
    ms.save_order(
        {**order(), "note": "OLD", "updatedAt": "2026-10-01T00:00:00Z"}
    )  # a late, older message
    assert mdb.get('SELECT "note" FROM "orders"')["note"] == "Updated note"


def test_a_new_scan_adds_one_event_and_the_shipment_is_refreshed():
    ms.save_order(order())
    o = order()
    f = o["fulfillments"][0]
    f["displayStatus"], f["deliveredAt"] = "DELIVERED", "2026-10-15T12:00:00Z"
    f["events"]["edges"].append(
        {
            "node": {
                "id": "gid://shopify/FulfillmentEvent/3",
                "status": "DELIVERED",
                "happenedAt": "2026-10-15T12:00:00Z",
                "message": "Delivered",
                "city": "Austin",
                "province": "TX",
                "country": "US",
            }
        }
    )
    assert ms.save_order({**o, "updatedAt": "2026-10-22T00:00:00Z"})["events"] == 1
    s = mdb.get('SELECT * FROM "shipments"')
    assert (
        s["delivered_at"] == "2026-10-15T12:00:00Z"
        and s["last_scan_text"] == "Delivered"
        and mdb.counts()["events"] == 3
    )


class FakeShopify:
    """Pages of orders; refuses customer fields (like a Shopify app without that access) when `deny_pii` is set."""

    def __init__(self, orders, deny_pii=False):
        self.orders, self.deny_pii, self.queries = orders, deny_pii, []

    def _post(self, payload):
        self.queries.append(payload["query"])
        if self.deny_pii and "shippingAddress" in payload["query"]:
            raise ShopifyError("Shopify GraphQL error: Access denied for shippingAddress field.")
        cursor = payload["variables"]["cursor"]
        start = int(cursor or 0)
        chunk = self.orders[start : start + ms.PAGE]
        if (
            "shippingAddress" not in payload["query"]
        ):  # Shopify only returns the fields that were asked for
            hidden = ("email", "phone", "shippingAddress", "billingAddress")
            chunk = [{k: v for k, v in o.items() if k not in hidden} for o in chunk]
        more = start + ms.PAGE < len(self.orders)
        return {
            "orders": {
                "pageInfo": {"hasNextPage": more, "endCursor": str(start + ms.PAGE)},
                "edges": [{"node": o} for o in chunk],
            }
        }


def test_master_sync_pages_through_all_orders_and_logs_the_run():
    shop = FakeShopify([order(2000 + i) for i in range(30)])
    r = ms.run_master_sync(shop, since="2026-10-01")
    assert (
        r["status"] == "success"
        and r["orders"] == 30
        and r["items"] == 60
        and r["customer_data"] is True
    )
    assert ms.status()["last_sync"]["status"] == "success" and mdb.counts()["orders"] == 30


def test_master_sync_carries_on_without_customer_details_when_shopify_refuses_them():
    shop = FakeShopify([order(3001)], deny_pii=True)
    r = ms.run_master_sync(shop, since="2026-10-01")
    assert (
        r["status"] == "success"
        and r["customer_data"] is False
        and "shippingAddress" not in shop.queries[-1]
    )
    o = mdb.get('SELECT * FROM "orders"')
    assert o["email"] is None and o["ship_city"] is None and o["name"] == "#3001"


def test_master_sync_without_credentials_fails_cleanly_and_calls_nothing(monkeypatch):
    from flowmerce.modules.shipping import master_sync

    class NoCreds:
        has_shopify_credentials = False
        shop_domain = "x.myshopify.com"
        orders_since = "2026-10-01"

    monkeypatch.setattr(master_sync, "load_config", lambda: NoCreds())
    r = ms.run_master_sync()
    assert r["status"] == "failed" and "credentials" in r["error"] and mdb.counts()["orders"] == 0
