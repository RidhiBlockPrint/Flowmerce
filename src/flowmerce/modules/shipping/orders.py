"""Order-level shipping classification (the structure agreed with the owner on 2026-10-31).

The unit is the ORDER, with its shipments (fulfillment + tracking number) underneath. Every order lands in exactly
one primary group, and a few "needs action" flags are laid over the top.

Primary groups, in the order they are decided:
  excluded         cancelled / refunded orders are left out entirely
  lost_missing     a shipment the team marked lost or "couldn't deliver", or a shipped parcel with no carrier update
                   for 14+ days
  unfulfilled      not fulfilled in Shopify yet (or only part of the order, with the shipped part delivered). Shipping is
                   tracked from the fulfilled date, so there is no delay clock or tier here, just the days waiting
  delivered        every tracked shipment is delivered (Shopify status, delivered date or a team mark); a shipment with
                   no tracking number does not hold the order back when another one is tracked and delivered
  no_carrier       fulfilled, but no tracking number and no carrier anywhere on the order
  no_tracking_id   fulfilled, a carrier is known, but no tracking number anywhere on the order
  in_transit       fulfilled, not delivered, 0-3 days since fulfilled
  delayed          the same, 4+ days: tier yellow (4-5), orange (6-8), red (9-12), critical (13+)

The delay is always measured in whole days from the fulfilled date (to now, or to the delivered date for a delivered
order), and the thresholds are the same for every carrier. Nothing is estimated or invented: a missing date stays
missing. Needs-action flags: no carrier scan for 5+ days, and a delivery that took 13+ days. An order whose note
says DONE while Shopify shows it unfulfilled is Amazon MCF (Amazon ships and delivers it itself): it counts as delivered
once it is 5+ days old and is tagged "Amazon MCF". A team mark of lost / could not deliver still wins.
A mixed order whose partner-carrier parcels are delivered and whose only open parcels are Amazon's also counts as delivered
(tag "Amazon part unconfirmed"), because Shopify never acknowledges Amazon deliveries."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from . import repo
from .aging import complete_days
from .config import load_config
from .service import _dt, shopify_order_url, track_url

IN_TRANSIT_MAX_DAYS = 3
NO_MOVEMENT_DAYS = 5
LOST_AFTER_DAYS = 14
LATE_DELIVERY_DAYS = 13
NOTE_DONE_MIN_AGE_DAYS = 5
STALE_AFTER_DAYS = 2

GROUPS = (
    "delivered",
    "in_transit",
    "delayed",
    "stale",
    "unfulfilled",
    "lost_missing",
    "no_tracking_id",
    "no_carrier",
)
TIERS = ("yellow", "orange", "red", "critical")
FLAGS = ("no_movement", "delivered_late")
GROUP_LABEL = {
    "delivered": "Delivered",
    "in_transit": "In transit",
    "delayed": "Delayed",
    "stale": "Not refreshed",
    "unfulfilled": "Unfulfilled",
    "lost_missing": "Lost / missing",
    "no_tracking_id": "No tracking ID",
    "no_carrier": "No carrier tracking",
}
FLAG_LABEL = {
    "no_movement": "No carrier scan for 5+ days",
    "delivered_late": "Delivered late (13+ days)",
}


def tier_for(days: int | None) -> str | None:
    """Delay tier for whole days in the current stage (None while still within the expected time)."""
    if days is None:
        return None
    t = load_config()
    if days >= t.critical_days:
        return "critical"
    if days >= t.red_days:
        return "red"
    if days >= t.orange_days:
        return "orange"
    if days >= t.yellow_days:
        return "yellow"
    return None


def _tracked(s: dict) -> bool:
    return bool(s["tracking_number"]) and not str(s["tracking_number"]).startswith("EMPTY")


def drop_superseded(rows: list[dict]) -> list[dict]:
    """Leave out saved rows that Shopify no longer reports (nothing is deleted).

    Rows are keyed by fulfillment + tracking number, so a tracking number added later to a fulfillment leaves the old
    empty-tracking row behind, and a replaced or cancelled fulfillment keeps its old row. (1) An empty-tracking row is
    superseded when its fulfillment has a tracking number. (2) Every row seen in one sync shares the same
    last_checked_at, so a row of an order that was checked later than this row was not returned by that later sync."""
    with_tracking = {r["fulfillment_id"] for r in rows if r["tracking_number"]}
    latest: dict[str, datetime] = {}
    for r in rows:
        d = _dt(r["last_checked_at"])
        if d and (r["order_number"] not in latest or d > latest[r["order_number"]]):
            latest[r["order_number"]] = d
    keep = []
    for r in rows:
        if not r["tracking_number"] and r["fulfillment_id"] in with_tracking:
            continue
        d = _dt(r["last_checked_at"])
        if d and (latest[r["order_number"]] - d) > timedelta(minutes=1):
            continue
        keep.append(r)
    return keep


def _shipment(r: dict, manual: dict, now: datetime) -> dict:
    fulfilled, delivered_at, last_scan = (
        _dt(r["fulfilled_at"]),
        _dt(r["delivered_at"]),
        _dt(r["last_scan_at"]),
    )
    m = manual.get(f"{r['order_number']}|{r['tracking_number']}")
    mark = m["status"] if m else None
    delivered = (
        r["normalized_tracking_status"] == "delivered" or bool(delivered_at) or mark == "delivered"
    )
    return {
        "fulfillment_id": r["fulfillment_id"],
        "tracking_number": r["tracking_number"],
        "carrier_name": r["carrier_name"],
        "tracked": _tracked(r),
        "track_url": track_url(r),
        "status": r["normalized_tracking_status"],
        "raw_status": r["raw_tracking_status"],
        "exception": r["exception"],
        "fulfilled_at": r["fulfilled_at"],
        "delivered_at": r["delivered_at"],
        "last_scan_at": r["last_scan_at"],
        "last_scan_description": r["last_scan_description"],
        "tracking_source": r["tracking_source"],
        "delivered": delivered,
        "mark": (
            {"status": mark, "updated_by": m["updated_by"], "updated_at": m["updated_at"]}
            if m
            else None
        ),
        "lost": mark in ("lost", "failed"),
        "scan_age": complete_days(last_scan, now) if last_scan and not delivered else None,
        "days_since_fulfilled": complete_days(fulfilled, now)
        if fulfilled and not delivered
        else None,
        "transit_days": (
            max(0, (delivered_at - fulfilled).days) if delivered_at and fulfilled else None
        ),
    }


def _order(
    number: str,
    base: dict | None,
    ships: list[dict],
    manual: dict,
    now: datetime,
    stale_days: int | None = None,
) -> dict:
    base = base or {}
    shipments = [_shipment(r, manual, now) for r in ships]
    created = _dt(base.get("order_created_at") or (ships[0]["order_created_at"] if ships else None))
    status = str(base.get("fulfillment_status") or "").upper()
    note = base.get("note") or ""
    carriers = sorted({s["carrier_name"] for s in shipments if s["carrier_name"]})
    tracked = [s for s in shipments if s["tracked"]]
    open_tracked = [s for s in tracked if not s["delivered"]]
    flags: list[str] = []
    days: int | None = None
    transit: int | None = None
    # Amazon MCF: the team's note says DONE (the order was handed to Amazon, which ships and delivers it itself) while
    # Shopify still shows the order unfulfilled. Such an order is treated as delivered once it is a few days old.
    amazon_mcf = bool(
        re.search(r"\bdone\b", note, re.I)
        and status
        and status != "FULFILLED"
        and created
        and complete_days(created, now) >= NOTE_DONE_MIN_AGE_DAYS
    )

    # Mixed order: a partner carrier (DHL, USPS, FedEx, UPS, ...) delivered its part and the only parcels still open are
    # Amazon's. Shopify never acknowledges delivery of Amazon parcels, so they cannot hold the order back.
    def _amazon(s: dict) -> bool:
        return "amazon" in (s["carrier_name"] or "").lower()

    partner_delivered = any(s["delivered"] and not _amazon(s) for s in shipments)
    amazon_unconfirmed = (
        bool(open_tracked) and all(_amazon(s) for s in open_tracked) and partner_delivered
    )

    archived = bool(base.get("closed_at"))  # archived (closed) in Shopify

    if any(s["lost"] for s in shipments):
        group, action = (
            "lost_missing",
            "Team marked it lost or couldn't deliver. Decide on a reship or refund.",
        )
    elif archived:
        group, action = (
            "delivered",
            "Archived in Shopify, so it is treated as delivered.",
        )
    elif amazon_mcf:
        group, action = (
            "delivered",
            "Fulfilled by Amazon (MCF): the note says DONE and Amazon delivers it itself, so it is treated as delivered. "
            "Shopify still shows the order as not fulfilled.",
        )
    elif amazon_unconfirmed:
        group, action = (
            "delivered",
            "Delivered by the partner carrier. The remaining Amazon package has no delivery event in Shopify, so it is "
            "treated as delivered with it. Open its tracking page if you want to check.",
        )
    elif open_tracked and stale_days is not None and stale_days >= STALE_AFTER_DAYS:
        group, action = (
            "stale",
            f"Shopify has not refreshed this order for {stale_days} days (Shopify only gives this app orders from the "
            "last 60 days), so its delivery status is unknown. Check the carrier tracking page and mark it, or use "
            "the tracking-service check.",
        )
        days = max(
            (
                s["days_since_fulfilled"]
                for s in open_tracked
                if s["days_since_fulfilled"] is not None
            ),
            default=None,
        )
    elif any(s["scan_age"] is not None and s["scan_age"] >= LOST_AFTER_DAYS for s in open_tracked):
        group, action = (
            "lost_missing",
            f"No carrier update for {LOST_AFTER_DAYS}+ days. Check with the carrier and mark it.",
        )
    elif not shipments or (
        status == "PARTIALLY_FULFILLED"
        and not open_tracked
        and all(s["delivered"] for s in shipments)
    ):
        group, action = (
            "unfulfilled",
            "Not fulfilled in Shopify yet. This is the fulfilment step, not shipping, so no delay is tracked here.",
        )
        days = complete_days(created, now) if created else None
    elif tracked and not open_tracked:
        group, action = "delivered", "Delivered."
    elif not tracked and any(s["delivered"] for s in shipments):
        group, action = "delivered", "Delivered."
    elif not tracked:
        if carriers:
            group = "no_tracking_id"
            action = "Add the tracking number on this order in Shopify, then sync picks it up."
        else:
            group = "no_carrier"
            action = "No carrier and no tracking number on the order. Add them in Shopify, then sync picks them up."
        fulfilled = min((d for d in (_dt(s["fulfilled_at"]) for s in shipments) if d), default=None)
        days = complete_days(fulfilled, now) if fulfilled else None
    else:
        worst = max(
            (
                s["days_since_fulfilled"]
                for s in open_tracked
                if s["days_since_fulfilled"] is not None
            ),
            default=None,
        )
        days = worst
        if worst is not None and worst > IN_TRANSIT_MAX_DAYS:
            group = "delayed"
            action = "Delayed. Open the carrier tracking page; if it is delivered, mark it delivered here, otherwise escalate."
        else:
            group, action = "in_transit", "On the way. Continue monitoring."

    if group == "delivered":
        times = [s["transit_days"] for s in shipments if s["transit_days"] is not None]
        transit = max(times) if times else None
        days = transit
        if transit is not None and transit >= LATE_DELIVERY_DAYS:
            flags.append("delivered_late")
    if any(
        s["scan_age"] is not None and NO_MOVEMENT_DAYS <= s["scan_age"] < LOST_AFTER_DAYS
        for s in open_tracked
    ):
        flags.append("no_movement")

    exception = next(
        (s["exception"] for s in shipments if s["exception"] and not s["delivered"]), ""
    )
    delivered_dates = [d for d in (_dt(s["delivered_at"]) for s in shipments) if d]
    fulfilled_dates = [d for d in (_dt(s["fulfilled_at"]) for s in shipments) if d]
    return {
        "order_number": number,
        "shopify_order_id": base.get("shopify_order_id")
        or (ships[0]["shopify_order_id"] if ships else ""),
        "shopify_url": shopify_order_url(
            {
                "shopify_order_id": base.get("shopify_order_id")
                or (ships[0]["shopify_order_id"] if ships else "")
            }
        ),
        "created_at": created.isoformat() if created else None,
        "fulfillment_status": status,
        "group": group,
        "group_label": GROUP_LABEL[group],
        "tier": tier_for(days)
        if group in ("delayed", "no_tracking_id", "no_carrier", "delivered")
        else None,
        "days": days,
        "transit_days": transit,
        "fulfilled_at": min(fulfilled_dates).isoformat() if fulfilled_dates else None,
        "delivered_at": max(delivered_dates).isoformat()
        if delivered_dates and group == "delivered"
        else None,
        "carriers": carriers,
        "tracking_numbers": [s["tracking_number"] for s in tracked],
        "shipments": shipments,
        "flags": flags,
        "delivered_by": (
            "archived"
            if (archived and group == "delivered")
            else "amazon_mcf"
            if (amazon_mcf and group == "delivered" and not archived)
            else "amazon_unconfirmed"
            if (amazon_unconfirmed and group == "delivered")
            else None
        ),
        "exception": exception,
        "needs_action": bool(flags),
        "note": note,
        "order_total": base.get("order_total"),
        "order_currency": base.get("order_currency") or "",
        "action": action,
        "team_note": "",
    }


def build_orders(now: datetime | None = None) -> list[dict]:
    """Every order (except cancelled / refunded) with its group, tier, flags and shipments."""
    now = now or datetime.now(UTC)
    checks = {c["order_number"]: c for c in repo.order_checks()}
    bad = {
        n
        for n, c in checks.items()
        if c["cancelled"] or str(c["financial_status"]).upper() == "REFUNDED"
    }
    manual = repo.manual_statuses()
    team_notes = repo.notes()
    by_order: dict[str, list[dict]] = defaultdict(list)
    rows = drop_superseded(repo.all_shipments())
    for r in rows:
        by_order[r["order_number"]].append(r)
    # Shopify only returns orders from the last 60 days, so an older order stops being refreshed. Compare each order's
    # last refresh with the newest refresh of any order (not with the clock, so a stopped sync does not mark everything).
    refreshed = [d for r in rows if (d := _dt(r["last_checked_at"]))]
    latest = max(refreshed, default=None)
    out = []
    for number in sorted(set(checks) | set(by_order)):
        if number in bad:
            continue
        mine = [d for r in by_order.get(number, []) if (d := _dt(r["last_checked_at"]))]
        gap = (latest - max(mine)).days if latest and mine else None
        o = _order(number, checks.get(number), by_order.get(number, []), manual, now, gap)
        o["team_note"] = (team_notes.get(number) or {}).get("note", "")
        out.append(o)
    return out


# ---------------- queries ----------------
def counts(orders: list[dict]) -> dict[str, Any]:
    g = Counter(o["group"] for o in orders)
    tiers = Counter(o["tier"] for o in orders if o["group"] == "delayed")
    return {
        "total": len(orders),
        **{k: g[k] for k in GROUPS},
        "delayed_tiers": {t: tiers[t] for t in TIERS},
        "needs_action": sum(1 for o in orders if o["needs_action"]),
        "flags": {f: sum(1 for o in orders if f in o["flags"]) for f in FLAGS},
    }


def _matches(o: dict, group: str, tier: str, carrier: str, q: str, flag: str) -> bool:
    if group == "needs_action":
        if not o["needs_action"]:
            return False
    elif group and o["group"] != group:
        return False
    if tier and o["tier"] != tier:
        return False
    if flag and flag not in o["flags"]:
        return False
    if carrier and carrier not in o["carriers"]:
        return False
    if q:
        ql = q.lower()
        if ql not in o["order_number"].lower() and not any(
            ql in t.lower() for t in o["tracking_numbers"]
        ):
            return False
    return True


_TIER_RANK = {"critical": 0, "red": 1, "orange": 2, "yellow": 3, None: 4}


def _sort(rows: list[dict], key: str) -> list[dict]:
    if key == "order":
        return sorted(
            rows,
            key=lambda o: [
                int(t) if t.isdigit() else t for t in re.split(r"(\d+)", o["order_number"])
            ],
        )
    if key == "newest":
        return sorted(rows, key=lambda o: o["created_at"] or "", reverse=True)
    return sorted(rows, key=lambda o: (_TIER_RANK[o["tier"]], -(o["days"] or 0), o["order_number"]))


def list_orders(
    group: str = "",
    tier: str = "",
    carrier: str = "",
    q: str = "",
    flag: str = "",
    sort: str = "priority",
    page: int = 0,
    size: int = 10,
    now: datetime | None = None,
) -> dict:
    orders = build_orders(now)
    rows = _sort([o for o in orders if _matches(o, group, tier, carrier, q.strip(), flag)], sort)
    size = max(1, min(size, 200))
    pages = max(1, -(-len(rows) // size))
    page = max(0, min(page, pages - 1))
    return {
        "rows": rows[page * size : (page + 1) * size],
        "total": len(rows),
        "page": page,
        "size": size,
        "pages": pages,
        "counts": counts(orders),
        "facets": {"carriers": sorted({c for o in orders for c in o["carriers"]})},
        "empty": not orders,
    }


def order_detail(number: str, now: datetime | None = None) -> dict | None:
    return next((o for o in build_orders(now) if o["order_number"] == number), None)


# ---------------- overview, analytics, export ----------------
def _week(iso: Any) -> str | None:
    d = _dt(iso)
    if not d:
        return None
    d = d.astimezone(UTC)
    return (d - timedelta(days=d.weekday())).date().isoformat()


def overview(now: datetime | None = None) -> dict:
    from .service import last_run_info  # local import: service does not depend on orders

    now = now or datetime.now(UTC)
    orders = build_orders(now)
    open_orders = [o for o in orders if o["group"] in ("in_transit", "delayed")]
    by_carrier: dict[str, Counter] = defaultdict(Counter)
    for o in open_orders:
        for c in o["carriers"] or ["No carrier"]:
            by_carrier[c]["open"] += 1
            if o["group"] == "delayed":
                by_carrier[c]["delayed"] += 1
            if o["tier"] == "critical":
                by_carrier[c]["critical"] += 1
    weeks: Counter = Counter(w for o in open_orders if (w := _week(o["fulfilled_at"])))
    return {
        "empty": not orders,
        "counts": counts(orders),
        "weeks": [{"week": k, "count": v} for k, v in sorted(weeks.items())[-10:]],
        "carriers": sorted(
            (
                {"name": k, "open": v["open"], "delayed": v["delayed"], "critical": v["critical"]}
                for k, v in by_carrier.items()
            ),
            key=lambda c: -c["open"],
        )[:6],
        "run": last_run_info(now),
    }


def _percentile(sorted_values: list[int], p: float) -> int:
    return sorted_values[min(len(sorted_values) - 1, int(len(sorted_values) * p))]


def analytics(now: datetime | None = None) -> dict:
    """Transit time (fulfilled to delivered) and delays, from the delivered and open orders."""
    now = now or datetime.now(UTC)
    orders = build_orders(now)
    per_carrier: dict[str, list[int]] = defaultdict(list)
    for o in orders:
        for s in o["shipments"]:
            if s["delivered"] and s["transit_days"] is not None:
                per_carrier[s["carrier_name"] or "No carrier"].append(s["transit_days"])
    cfg = load_config()
    table = []
    for name, v in per_carrier.items():
        v.sort()
        table.append(
            {
                "name": name,
                "delivered": len(v),
                "avg_days": round(sum(v) / len(v), 1),
                "median_days": _percentile(v, 0.5),
                "p90_days": _percentile(v, 0.9),
                "slow": sum(1 for x in v if x >= cfg.yellow_days),
                "slow_pct": round(100 * sum(1 for x in v if x >= cfg.yellow_days) / len(v)),
                "late": sum(1 for x in v if x >= LATE_DELIVERY_DAYS),
            }
        )
    all_days = [x for v in per_carrier.values() for x in v]
    buckets = [("0-3", 0, 3), ("4-5", 4, 5), ("6-8", 6, 8), ("9-12", 9, 12), ("13+", 13, 10**6)]
    c = counts(orders)
    return {
        "empty": not orders,
        "counts": c,
        "delivered_shipments": len(all_days),
        "avg_transit_days": round(sum(all_days) / len(all_days), 1) if all_days else None,
        "distribution": [
            {"label": lab, "count": sum(1 for x in all_days if lo <= x <= hi)}
            for lab, lo, hi in buckets
        ],
        "carriers": sorted(table, key=lambda r: -r["delivered"]),
        "delayed_tiers": c["delayed_tiers"],
    }


def export_csv(**filters: Any) -> tuple[str, str]:
    from .service import _csv

    orders = _sort(
        [
            o
            for o in build_orders()
            if _matches(
                o,
                filters.get("group", ""),
                filters.get("tier", ""),
                filters.get("carrier", ""),
                filters.get("q", "").strip(),
                filters.get("flag", ""),
            )
        ],
        filters.get("sort", "priority"),
    )
    head = [
        "order_number",
        "group",
        "tier",
        "days",
        "carriers",
        "tracking_numbers",
        "fulfilled_at",
        "delivered_at",
        "transit_days",
        "flags",
        "shopify_order_url",
    ]
    body = [
        [
            o["order_number"],
            o["group_label"],
            o["tier"] or "",
            o["days"],
            "; ".join(o["carriers"]),
            "; ".join(o["tracking_numbers"]),
            o["fulfilled_at"],
            o["delivered_at"],
            o["transit_days"],
            "; ".join(FLAG_LABEL[f] for f in o["flags"]),
            o["shopify_url"],
        ]
        for o in orders
    ]
    return "orders.csv", _csv(head, body)
