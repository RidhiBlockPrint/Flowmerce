"""Fill the master database (master_db.py) from Shopify. Read-only against Shopify.

What Shopify provides is copied into the columns the design assigns to the Shopify sync; the columns owned by people
or backend jobs (stage, hold, route, step, responsible ...) are never touched. Nothing is invented: anything Shopify
does not return stays empty. With the access this app has, Shopify refuses the customer record (needs read_customers)
and product / variant ids (needs read_products), so customer_id, product_id and variant_id stay empty; the customer's
name, email, phone and address come from the order itself. The risk level is not available either."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from . import master_db as mdb
from .config import load_config
from .shopify import ShopifyError

STORE_ID = "RBP"
PAGE = 25
UUID_NS = uuid.UUID("6f1f4a53-2d2c-4a77-9e51-3c0f6b0f2a11")
M = "shopMoney{amount currencyCode}"
PII_FIELDS = "email phone shippingAddress{name address1 address2 city provinceCode zip countryCodeV2} billingAddress{name}"
ORDER_FIELDS = f"""id legacyResourceId name createdAt updatedAt cancelledAt cancelReason closedAt
 displayFulfillmentStatus displayFinancialStatus currencyCode
 subtotalPriceSet{{{M}}} totalDiscountsSet{{{M}}} totalShippingPriceSet{{{M}}} totalTaxSet{{{M}}}
 totalPriceSet{{{M}}} totalRefundedSet{{{M}}} tags note
 lineItems(first:50){{edges{{node{{id sku title variantTitle quantity currentQuantity unfulfilledQuantity
   originalUnitPriceSet{{{M}}} totalDiscountSet{{{M}}} image{{url}}}}}}}}
 refunds{{refundLineItems(first:50){{edges{{node{{quantity lineItem{{id}}}}}}}}}}
 fulfillments(first:20){{id legacyResourceId status createdAt displayStatus estimatedDeliveryAt deliveredAt
   trackingInfo(first:10){{number company url}}
   fulfillmentLineItems(first:50){{edges{{node{{quantity lineItem{{id}}}}}}}}
   events(first:50){{edges{{node{{id status happenedAt message city province country}}}}}}}}"""


def _query(with_pii: bool) -> str:
    fields = ORDER_FIELDS + (" " + PII_FIELDS if with_pii else "")
    return (
        f"query($cursor:String,$q:String!){{orders(first:{PAGE},after:$cursor,query:$q,sortKey:CREATED_AT)"
        f"{{pageInfo{{hasNextPage endCursor}} edges{{node{{{fields}}}}}}}}}"
    )


def _legacy(gid: str | None) -> int | None:
    try:
        return int(str(gid).rsplit("/", 1)[1])
    except (ValueError, IndexError):
        return None


def _money(node: dict | None, key: str) -> float | None:
    try:
        v = ((node or {}).get(key) or {}).get("shopMoney", {}).get("amount")
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _iso(v: Any) -> str | None:
    return str(v) if v else None


def _lower(v: Any) -> str | None:
    return str(v).lower() if v else None


FULFILLMENT_STATUS = {
    "FULFILLED": "fulfilled",
    "UNFULFILLED": "unfulfilled",
    "PARTIALLY_FULFILLED": "partial",
}


PARCEL_AUTO_STEPS = (
    "shipped",
    "transit",
    "out",
    "delivered",
)  # steps this sync may set (the design's parcel steps)
ORDER_AUTO_STAGES = (
    "new",
    "shipped",
    "transit",
    "delivered",
    "cancelled",
)  # stages this sync may set
_STEP_RANK = {"shipped": 0, "transit": 1, "out": 1, "delivered": 2}


def parcel_step(status: str | None, delivered_at: str | None) -> str:
    """Parcel step from what Shopify says: delivered, out for delivery, in transit, otherwise marked shipped."""
    s = str(status or "").upper()
    if delivered_at or s == "DELIVERED":
        return "delivered"
    if s == "OUT_FOR_DELIVERY":
        return "out"
    if s == "IN_TRANSIT":
        return "transit"
    return "shipped"


def order_stage(steps: list[str], cancelled: bool) -> str:
    """The design's order stage, worked out from its shipments (the slowest one). Only the parts Shopify can tell."""
    if cancelled:
        return "cancelled"
    if not steps:
        return "new"
    slowest = min(steps, key=lambda x: _STEP_RANK.get(x, 0))
    return {
        "shipped": "shipped",
        "transit": "transit",
        "out": "transit",
        "delivered": "delivered",
    }.get(slowest, "shipped")


def map_order(o: dict, now: str) -> dict:
    ship = o.get("shippingAddress") or {}
    bill = o.get("billingAddress") or {}
    fs = str(o.get("displayFulfillmentStatus") or "")
    return {
        "id": _legacy(o["id"]),
        "store": STORE_ID,
        "name": o["name"],
        "customer_id": None,  # needs the read_customers scope
        "customer_name": ship.get("name") or bill.get("name") or None,
        "email": o.get("email"),
        "phone": o.get("phone") or ship.get("phone"),
        "ship_name": ship.get("name"),
        "ship_address1": ship.get("address1"),
        "ship_address2": ship.get("address2"),
        "ship_city": ship.get("city"),
        "ship_province": ship.get("provinceCode"),
        "ship_zip": ship.get("zip"),
        "ship_country": ship.get("countryCodeV2"),
        "placed_at": _iso(o.get("createdAt")),
        "shop_updated_at": _iso(o.get("updatedAt")),
        "cancelled_at": _iso(o.get("cancelledAt")),
        "cancel_reason": _lower(o.get("cancelReason")),
        "financial_status": _lower(o.get("displayFinancialStatus")),
        "fulfillment_status": FULFILLMENT_STATUS.get(fs, fs.lower() or None),
        "currency": o.get("currencyCode") or "USD",
        "subtotal": _money(o, "subtotalPriceSet"),
        "discounts": _money(o, "totalDiscountsSet"),
        "shipping_charged": _money(o, "totalShippingPriceSet"),
        "tax": _money(o, "totalTaxSet"),
        "total": _money(o, "totalPriceSet"),
        "refunded_amount": _money(o, "totalRefundedSet") or 0,
        "tags": json.dumps(o.get("tags") or []),
        "note": o.get("note") or None,
        "risk_level": None,  # not available to this app
        "raw": json.dumps(o, default=str),
        "synced_at": now,
    }


def map_items(o: dict) -> list[dict]:
    order_id = _legacy(o["id"])
    refunded: dict[str, int] = {}
    for r in o.get("refunds") or []:
        for e in (r.get("refundLineItems") or {}).get("edges", []):
            n = e["node"]
            refunded[n["lineItem"]["id"]] = refunded.get(n["lineItem"]["id"], 0) + int(
                n["quantity"] or 0
            )
    shipped: dict[str, int] = {}
    for f in o.get("fulfillments") or []:
        if f.get("status") not in (None, "SUCCESS"):
            continue
        for e in (f.get("fulfillmentLineItems") or {}).get("edges", []):
            n = e["node"]
            shipped[n["lineItem"]["id"]] = shipped.get(n["lineItem"]["id"], 0) + int(
                n["quantity"] or 0
            )
    out = []
    for e in (o.get("lineItems") or {}).get("edges", []):
        li = e["node"]
        out.append(
            {
                "id": _legacy(li["id"]),
                "order_id": order_id,
                "store": STORE_ID,
                "sku": li.get("sku"),
                "title": li.get("title") or "",
                "variant_title": li.get("variantTitle"),
                "product_id": None,
                "variant_id": None,  # need the read_products scope
                "image_url": (li.get("image") or {}).get("url"),
                "qty": li.get("quantity"),
                "current_qty": li.get("currentQuantity"),
                "refunded_qty": refunded.get(li["id"], 0),
                "fulfilled_qty": shipped.get(li["id"], 0),
                "open_qty": li.get("unfulfilledQuantity"),
                "price": _money(li, "originalUnitPriceSet"),
                "discount": _money(li, "totalDiscountSet") or 0,
            }
        )
    return out


def _place(ev: dict) -> str | None:
    parts = [p for p in (ev.get("city"), ev.get("country")) if p]
    return ", ".join(parts) or None


def map_shipments(o: dict) -> list[dict]:
    order_id = _legacy(o["id"])
    out = []
    fulfillments = sorted(
        (f for f in o.get("fulfillments") or [] if f.get("status") in (None, "SUCCESS")),
        key=lambda f: f.get("createdAt") or "",
    )
    for f in fulfillments:
        tracking = [t["number"] for t in f.get("trackingInfo") or [] if t.get("number")]
        company = next(
            (t["company"] for t in f.get("trackingInfo") or [] if t.get("company")), None
        )
        events = sorted(
            (e["node"] for e in (f.get("events") or {}).get("edges", [])),
            key=lambda e: e["happenedAt"],
        )
        latest = events[-1] if events else None
        cities: list[str] = []
        for e in events:
            if e.get("city") and (not cities or cities[-1] != e["city"]):
                cities.append(e["city"])
        out.append(
            {
                "id": str(uuid.uuid5(UUID_NS, f["id"])),
                "order_id": order_id,
                "store": STORE_ID,
                "items": json.dumps(
                    [
                        {
                            "item_id": _legacy(e["node"]["lineItem"]["id"]),
                            "qty": e["node"]["quantity"],
                        }
                        for e in (f.get("fulfillmentLineItems") or {}).get("edges", [])
                    ]
                ),
                "carrier": company,
                # the design's kinds: Amazon Logistics is MCF; DHL, FedEx and the rest ship from India
                "kind": "mcf" if "amazon" in (company or "").lower() else "india",
                "step": parcel_step(f.get("displayStatus"), f.get("deliveredAt")),
                "step_at": _iso(latest["happenedAt"]) if latest else _iso(f.get("createdAt")),
                "tracking": json.dumps(tracking),
                "shopify_fulfillment_id": _legacy(f["id"]),
                "eta": (f.get("estimatedDeliveryAt") or "")[:10] or None,
                "delivered_at": _iso(f.get("deliveredAt")),
                "last_scan_at": _iso(latest["happenedAt"]) if latest else None,
                "last_scan_place": _place(latest) if latest else None,
                "last_scan_text": (latest.get("message") or latest.get("status"))
                if latest
                else None,
                "cities": json.dumps(cities),
                "created_at": _iso(f.get("createdAt")),
                "_events": events,
                "_gid": f["id"],
            }
        )
    return out


# ---------------- writing ----------------
def _upsert_order(row: dict) -> None:
    cols = list(row)
    sets = ", ".join(f'"{c}" = excluded."{c}"' for c in cols if c != "id")
    mdb.run(
        f'INSERT INTO "orders" ({", ".join(chr(34) + c + chr(34) for c in cols)}) VALUES ({", ".join("?" for _ in cols)}) '
        f'ON CONFLICT ("id") DO UPDATE SET {sets} WHERE excluded."shop_updated_at" >= "orders"."shop_updated_at"',
        *row.values(),
    )


def _upsert_item(row: dict) -> None:
    cols = list(row)
    sets = ", ".join(f'"{c}" = excluded."{c}"' for c in cols if c != "id")
    mdb.run(
        f'INSERT INTO "items" ({", ".join(chr(34) + c + chr(34) for c in cols)}) VALUES ({", ".join("?" for _ in cols)}) '
        f'ON CONFLICT ("id") DO UPDATE SET {sets}',
        *row.values(),
    )


_SHIPMENT_REFRESH = (
    "carrier",
    "tracking",
    "eta",
    "delivered_at",
    "last_scan_at",
    "last_scan_place",
    "last_scan_text",
    "cities",
)


def _upsert_shipment(row: dict) -> str:
    """Insert a Shopify-made shipment, or refresh only the carrier-written columns of an existing one."""
    existing = mdb.get(
        'SELECT "id", "step" FROM "shipments" WHERE "shopify_fulfillment_id" = ?',
        row["shopify_fulfillment_id"],
    )
    if existing:
        sets = ", ".join(f'"{c}" = ?' for c in _SHIPMENT_REFRESH)
        mdb.run(
            f'UPDATE "shipments" SET {sets}, "updated_at" = ? WHERE "id" = ?',
            *[row[c] for c in _SHIPMENT_REFRESH],
            datetime.now(UTC).isoformat(timespec="seconds"),
            existing["id"],
        )
        if existing["step"] in PARCEL_AUTO_STEPS and existing["step"] != row["step"]:
            # production, return and blocked steps are set by people and are left alone
            mdb.run(
                'UPDATE "shipments" SET "step" = ?, "step_at" = ? WHERE "id" = ?',
                row["step"],
                row["step_at"],
                existing["id"],
            )
        return existing["id"]
    seq = (
        mdb.get(
            'SELECT COALESCE(MAX("seq"), 0) + 1 AS n FROM "shipments" WHERE "order_id" = ?',
            row["order_id"],
        )
        or {"n": 1}
    )["n"]
    cols = [c for c in row if not c.startswith("_")] + ["seq"]
    vals = [row[c] for c in cols[:-1]] + [seq]
    mdb.run(
        f'INSERT INTO "shipments" ({", ".join(chr(34) + c + chr(34) for c in cols)}) VALUES ({", ".join("?" for _ in cols)})',
        *vals,
    )
    return row["id"]


def _insert_events(order: dict, shipment_id: str, shipment: dict, store: str = STORE_ID) -> int:
    n = 0
    for e in shipment["_events"]:
        cur = mdb.run(
            'INSERT OR IGNORE INTO "events" ("at", "store", "order_id", "shipment_id", "type", "by", "title", "data", "external_id") '
            "VALUES (?,?,?,?,?,?,?,?,?)",
            e["happenedAt"],
            store,
            shipment["order_id"],
            shipment_id,
            "scan",
            (shipment["carrier"] or "carrier").lower(),
            (e.get("message") or e.get("status") or "Tracking update")[:300],
            json.dumps(
                {
                    "status": e.get("status"),
                    "city": e.get("city"),
                    "province": e.get("province"),
                    "country": e.get("country"),
                }
            ),
            f"shopify-event:{e['id']}",
        )
        n += cur.rowcount or 0
    return n


def save_order(o: dict, now: str | None = None) -> dict:
    now = now or datetime.now(UTC).isoformat(timespec="seconds")
    mdb.run(
        'INSERT OR IGNORE INTO "stores" ("id", "name", "shopify_domain") VALUES (?,?,?)',
        STORE_ID,
        "Ridhi Block Print",
        load_config().shop_domain,
    )
    counts = {"orders": 1, "items": 0, "shipments": 0, "events": 0}
    with mdb.transaction():
        _upsert_order(map_order(o, now))
        for item in map_items(o):
            _upsert_item(item)
            counts["items"] += 1
        shipments = map_shipments(o)
        for s in shipments:
            sid = _upsert_shipment(s)
            counts["shipments"] += 1
            counts["events"] += _insert_events(o, sid, s)
        # the order stage is worked out from its shipments (slowest one); only the stages Shopify can tell are written
        stage = order_stage([s["step"] for s in shipments], bool(o.get("cancelledAt")))
        current = mdb.get('SELECT "stage" FROM "orders" WHERE "id" = ?', _legacy(o["id"]))
        if current and current["stage"] in ORDER_AUTO_STAGES and current["stage"] != stage:
            mdb.run(
                'UPDATE "orders" SET "stage" = ?, "stage_at" = ? WHERE "id" = ?',
                stage,
                now,
                _legacy(o["id"]),
            )
    return counts


# ---------------- Shopify read ----------------
def fetch(shopify, since: str):
    """Yield orders created on/after `since`, with customer contact details when Shopify allows them. Returns via the
    generator's `customer_data` attribute on the returned object."""
    state = {"pii": True}

    def pages():
        cursor = None
        while True:
            try:
                data = shopify._post(
                    {
                        "query": _query(state["pii"]),
                        "variables": {"cursor": cursor, "q": f"created_at:>='{since}'"},
                    }
                )
            except ShopifyError as exc:
                if state["pii"] and "Access denied" in str(exc):
                    state["pii"] = (
                        False  # customer details are not allowed for this app: carry on without them
                    )
                    continue
                raise
            conn = data["orders"]
            yield from (e["node"] for e in conn["edges"])
            if not conn["pageInfo"]["hasNextPage"]:
                return
            cursor = conn["pageInfo"]["endCursor"]

    gen = pages()

    class _It:
        customer_data = property(lambda self: state["pii"])

        def __iter__(self):
            return gen

    return _It()


def run_master_sync(shopify=None, since: str | None = None) -> dict:
    from .sync import build_shopify

    cfg = load_config()
    started = datetime.now(UTC).isoformat(timespec="seconds")
    log_id = mdb.run(
        "INSERT INTO master_sync_log (started_at, status) VALUES (?, ?)", started, "running"
    ).lastrowid
    total = {"orders": 0, "items": 0, "shipments": 0, "events": 0}
    try:
        if shopify is None:
            if not cfg.has_shopify_credentials:
                raise ShopifyError("Shopify credentials are not set in .env.")
            shopify = build_shopify(cfg)
        it = fetch(shopify, since or cfg.orders_since)
        for o in it:
            for k, v in save_order(o).items():
                total[k] += v
        status, error, pii = "success", "", int(it.customer_data)
    except Exception as exc:  # noqa: BLE001 - recorded on the log row
        status, error, pii = "failed", f"{type(exc).__name__}: {exc}"[:500], 0
    mdb.run(
        "UPDATE master_sync_log SET finished_at=?, status=?, orders=?, items=?, shipments=?, events=?, customer_data=?, error=? WHERE id=?",
        datetime.now(UTC).isoformat(timespec="seconds"),
        status,
        total["orders"],
        total["items"],
        total["shipments"],
        total["events"],
        pii,
        error,
        log_id,
    )
    return {"status": status, "error": error, "customer_data": bool(pii), **total}


def status() -> dict:
    last = mdb.get("SELECT * FROM master_sync_log ORDER BY id DESC LIMIT 1")
    return {"counts": mdb.counts(), "last_sync": last}


def tick(every_hours: int = 6) -> None:
    """Background refresh: copy from Shopify when credentials exist and the last successful run is old enough."""
    if not load_config().has_shopify_credentials:
        return
    last = mdb.get(
        "SELECT finished_at FROM master_sync_log WHERE status = 'success' ORDER BY id DESC LIMIT 1"
    )
    if last and last["finished_at"]:
        done = datetime.fromisoformat(last["finished_at"].replace("Z", "+00:00"))
        if done.tzinfo is None:
            done = done.replace(tzinfo=UTC)
        if (datetime.now(UTC) - done).total_seconds() < every_hours * 3600:
            return
    run_master_sync()
