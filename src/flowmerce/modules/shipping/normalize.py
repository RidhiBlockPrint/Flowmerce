"""Turn Shopify order nodes into shipment rows. One row per fulfillment + tracking number."""

from collections.abc import Iterable
from datetime import datetime

from .aging import to_utc

# Shopify displayStatus -> our normalized status
STATUS_MAP = {
    "DELIVERED": "delivered",
    "IN_TRANSIT": "in_transit",
    "OUT_FOR_DELIVERY": "out_for_delivery",
    "ATTEMPTED_DELIVERY": "failed_delivery",
    "FAILURE": "failed_delivery",
    "RETURNED": "returned",
    "RETURN_TO_SENDER": "returned",
    "FULFILLED": "fulfilled",
    "LABEL_PRINTED": "fulfilled",
    "LABEL_PURCHASED": "fulfilled",
    "READY_FOR_PICKUP": "fulfilled",
}
EXCEPTION_STATUSES = {"failed_delivery", "returned"}


def parse_ts(value):
    if not value:
        return None
    return to_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _money(order):
    return (order.get("totalPriceSet") or {}).get("shopMoney") or {}


def _order_total(order):
    try:
        return (
            float(_money(order).get("amount"))
            if _money(order).get("amount") not in (None, "")
            else None
        )
    except (TypeError, ValueError):
        return None


def _order_currency(order):
    return _money(order).get("currencyCode") or ""


def normalize_orders(orders: Iterable[dict]):
    """Yield one shipment dict per (fulfillment, tracking number). Orders without
    fulfillments yield nothing (nothing to track yet)."""
    for order in orders:
        if order.get("cancelledAt"):
            continue
        order_id = order["id"]
        for f in order.get("fulfillments") or []:
            if f.get("status") not in (None, "SUCCESS"):
                continue
            raw = f.get("displayStatus") or "FULFILLED"
            events = [
                e["node"] for e in ((f.get("events") or {}).get("edges") or []) if e.get("node")
            ]
            events = [e for e in events if e.get("happenedAt")]
            latest = max(events, key=lambda e: e["happenedAt"]) if events else None
            status = STATUS_MAP.get(raw, "fulfilled")
            tracks = f.get("trackingInfo") or [{"number": "", "company": "", "url": ""}]
            for t in tracks:
                number = (t.get("number") or "").strip()
                yield {
                    "shopify_order_id": order_id,
                    "order_number": order["name"],
                    "fulfillment_id": f["id"],
                    "tracking_number": number,
                    "carrier_name": t.get("company") or "",
                    "tracking_url": t.get("url") or "",
                    "order_created_at": parse_ts(order.get("createdAt")),
                    "order_total": _order_total(order),
                    "order_currency": _order_currency(order),
                    "fulfilled_at": parse_ts(f.get("createdAt")),
                    "expected_delivery_at": parse_ts(f.get("estimatedDeliveryAt")),
                    "delivered_at": parse_ts(f.get("deliveredAt")),
                    "raw_tracking_status": raw,
                    "normalized_tracking_status": status,
                    "exception": status if status in EXCEPTION_STATUSES else "",
                    "tracking_source": "shopify_events" if latest else "shopify",
                    "last_scan_at": parse_ts(latest["happenedAt"]) if latest else None,
                    "last_scan_description": (latest.get("message") or "") if latest else "",
                    "last_scan_location": "",
                }


def normalize_order_checks(orders: Iterable[dict]):
    """One record per (non-cancelled) order: Shopify fulfillment status plus the order note.
    Used to catch orders whose notes say DONE while Shopify still shows them as not fulfilled."""
    for order in orders:
        if not order.get("name"):
            continue
        yield {
            "order_number": order["name"],
            "shopify_order_id": order.get("id") or "",
            "order_created_at": parse_ts(order.get("createdAt")),
            "fulfillment_status": (order.get("displayFulfillmentStatus") or "").upper(),
            "financial_status": (order.get("displayFinancialStatus") or "").upper(),
            "cancelled": bool(order.get("cancelledAt")),
            "closed_at": parse_ts(
                order.get("closedAt")
            ),  # set when the order is archived (closed) in Shopify
            "note": (order.get("note") or "").strip(),
            "order_total": _order_total(order),
            "order_currency": _order_currency(order),
        }
