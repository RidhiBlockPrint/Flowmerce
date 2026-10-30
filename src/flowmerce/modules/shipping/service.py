"""Shipping dashboard logic: classify every shipment, then build the summaries the pages need.

Ported from the original dashboard's JavaScript so the numbers match what the operations team already uses:
  - aging colours come from aging.flow_category (not dispatched: clock from the order date; dispatched: from the
    dispatch date; a scan never resets the clock; delivered leaves the queue);
  - "No movement" = not delivered and the last carrier scan is 5+ complete days old;
  - Amazon / unknown carriers send no delivery event to Shopify, so they are "carrier unconfirmed" until the team
    marks them (delivered / lost / couldn't deliver / in transit);
  - cancelled and refunded orders (from the order checks) are left out;
  - "Notes say DONE, Shopify not fulfilled" lists order checks whose note says done but Shopify is not fulfilled.
Nothing here is invented: a missing scan stays missing, and totals come only from the saved rows."""

from __future__ import annotations

import csv
import io
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from . import repo
from .aging import NO_MOVE_DAYS, complete_days, flow_category
from .config import load_config

CAT_LABEL = {
    "on_track": "On track",
    "unconfirmed": "Carrier unconfirmed",
    "lost": "Lost (team confirmed)",
    "failed": "Couldn't deliver (team confirmed)",
    "grey": "Grey 2-3 days",
    "yellow": "Yellow 4-5 days",
    "orange": "Orange 6-8 days",
    "red": "Red 9+ days",
    "no_scan": "No scan data",
    "delivered": "Delivered",
    "covered": "Fulfilled by hand, tracked package delivered",
}
RANK = {
    "red": 0,
    "orange": 1,
    "yellow": 2,
    "grey": 3,
    "no_scan": 4,
    "on_track": 5,
    "delivered": 6,
    "covered": 7,
}
MANUAL_STATUSES = ("delivered", "lost", "failed", "in_transit")
MCF_LEVELS = ((10, "critical", "Critical"), (7, "watch", "Watch"), (5, "alert", "Alert"))
STALE_HOURS = 26


def _dt(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def is_unconfirmed(carrier: str | None) -> bool:
    c = str(carrier or "").lower().strip()
    return c == "" or "amazon" in c or c == "unknown"


def track_url(r: dict) -> str:
    if r.get("tracking_url"):
        return r["tracking_url"]
    n = str(r.get("tracking_number") or "").strip()
    if not n or n.startswith("EMPTY"):
        return ""
    c = str(r.get("carrier_name") or "").lower()
    if "dhl" in c:
        return f"https://www.dhl.com/in-en/home/tracking/tracking-express.html?submit=1&tracking-id={n}"
    if "usps" in c:
        return f"https://tools.usps.com/go/TrackConfirmAction?tLabels={n}"
    if "fedex" in c:
        return f"https://www.fedex.com/fedextrack/?trknbr={n}"
    if "amazon" in c:
        return f"https://track.amazon.com/tracking/{n}"
    return ""


def shopify_order_url(r: dict) -> str:
    oid = str(r.get("shopify_order_id") or "").split("/")[-1]
    shop = load_config().shop_domain.split(".")[0]
    return f"https://admin.shopify.com/store/{shop}/orders/{oid}" if oid else ""


def action_text(cat: str, exc: str, stage: str) -> str:
    if exc:
        return "Carrier exception: review the reason and decide the next step."
    if stage == "pre_dispatch" and cat != "on_track":
        return "Not dispatched yet. Check packing and dispatch from the location."
    return {
        "on_track": "Continue monitoring.",
        "grey": "Continue monitoring.",
        "yellow": "Review if carrier SLA or expected delivery shows a problem.",
        "orange": "Prioritize for investigation.",
        "red": "Add to urgent escalation list.",
        "no_scan": "Verify tracking details or wait for first carrier scan.",
        "delivered": "None. Delivered.",
        "covered": "Marked fulfilled by hand without tracking. Every tracked package on this order is delivered, so there is nothing to check.",
        "unconfirmed": "Open the carrier page, check the parcel and mark it here.",
        "lost": "Team confirmed lost. Decide on reship or refund.",
        "failed": "Team confirmed it could not be delivered. Decide the next step.",
    }.get(cat, "Review manually.")


def classify(now: datetime | None = None) -> list[dict]:
    """Every saved shipment with its aging category, flags and team marks. Cancelled/refunded orders are dropped."""
    now = now or datetime.now(UTC)
    cfg = load_config()
    thresholds = cfg.thresholds
    manual = repo.manual_statuses()
    checks = {c["order_number"]: c for c in repo.order_checks()}
    bad = {
        n
        for n, c in checks.items()
        if c["cancelled"] or str(c["financial_status"]).upper() == "REFUNDED"
    }
    note_map = repo.notes()
    rows = [r for r in repo.all_shipments() if r["order_number"] not in bad]
    pkgs = Counter(r["order_number"] for r in rows)
    out = []
    for r in rows:
        created, fulfilled, last_scan = (
            _dt(r["order_created_at"]),
            _dt(r["fulfilled_at"]),
            _dt(r["last_scan_at"]),
        )
        delivered = r["normalized_tracking_status"] == "delivered" or bool(r["delivered_at"])
        cat, days, stage = (
            flow_category(created, fulfilled, now, thresholds, delivered)
            if (created or fulfilled or delivered)
            else ("no_scan", None, "pre_dispatch")
        )
        unconf = is_unconfirmed(r["carrier_name"])
        scan_age = complete_days(last_scan, now)
        no_move = (
            cat != "delivered" and not unconf and scan_age is not None and scan_age >= NO_MOVE_DAYS
        )
        final = "unconfirmed" if (cat != "delivered" and unconf) else cat
        m = manual.get(f"{r['order_number']}|{r['tracking_number']}")
        if m and unconf:
            if m["status"] == "delivered":
                final = "delivered"
            elif m["status"] == "lost":
                final = "lost"
            elif m["status"] == "failed":
                final = "failed"
        row = {
            **{
                k: r[k]
                for k in (
                    "id",
                    "shopify_order_id",
                    "order_number",
                    "fulfillment_id",
                    "tracking_number",
                    "carrier_name",
                    "order_created_at",
                    "fulfilled_at",
                    "expected_delivery_at",
                    "last_scan_at",
                    "last_scan_description",
                    "last_scan_location",
                    "last_checked_at",
                    "carrier_error",
                    "normalized_tracking_status",
                    "exception",
                    "delivered_at",
                )
            },
            "shopify_delivered": delivered,
            "cat": final,
            "cat_label": CAT_LABEL.get(final, final),
            "days": days,
            "stage": stage,
            "scan_age": scan_age,
            "no_move": no_move,
            "unconfirmed": unconf,
            "packages": pkgs[r["order_number"]],
            "manual": (
                {
                    "status": m["status"],
                    "updated_by": m["updated_by"],
                    "updated_at": m["updated_at"],
                }
                if m
                else None
            ),
            "track_url": track_url(r),
            "shopify_url": shopify_order_url(r),
            "tracking_missing": (not r["tracking_number"])
            or str(r["tracking_number"]).startswith("EMPTY"),
            "note": (note_map.get(r["order_number"]) or {}).get("note", ""),
            "order_total": r["order_total"]
            if r["order_total"] is not None
            else (checks.get(r["order_number"]) or {}).get("order_total"),
            "order_currency": r["order_currency"]
            or (checks.get(r["order_number"]) or {}).get("order_currency", ""),
        }
        row["action"] = action_text(final, r["exception"], stage)
        out.append(row)
    _mark_covered(out, checks)
    return out


def _mark_covered(rows: list[dict], checks: dict) -> None:
    """A package marked fulfilled by hand (no tracking number) is "covered" when Shopify says the whole order is
    FULFILLED and every package of the order that has a tracking number is delivered. It leaves the unconfirmed
    queue under its own tag. A team mark on the package always wins, and nothing is changed in Shopify."""
    by_order: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_order[r["order_number"]].append(r)
    for order_number, pkgs in by_order.items():
        if (
            str((checks.get(order_number) or {}).get("fulfillment_status", "")).upper()
            != "FULFILLED"
        ):
            continue
        tracked = [p for p in pkgs if not p["tracking_missing"]]
        if not tracked or any(p["cat"] != "delivered" for p in tracked):
            continue
        for p in pkgs:
            if p["cat"] == "unconfirmed" and p["tracking_missing"] and not p["manual"]:
                p["cat"] = "covered"
                p["cat_label"] = CAT_LABEL["covered"]
                p["action"] = action_text("covered", "", p["stage"])


def _active(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["cat"] not in ("delivered", "covered")]


def week_key(iso: Any) -> str | None:
    d = _dt(iso)
    if not d:
        return None
    d = d.astimezone(UTC)
    return (d - timedelta(days=d.weekday())).date().isoformat()


# ---------------- list ----------------
def _matches(
    r: dict, view: str, carrier: str, status: str, q: str, days: int, now: datetime
) -> bool:
    if days:
        created = _dt(r["order_created_at"])
        if not created or created < now - timedelta(days=days):
            return False
    if view == "nomove":
        if not r["no_move"]:
            return False
    elif view == "noscan":
        if r["last_scan_at"] or r["cat"] in ("delivered", "covered"):
            return False
    elif view == "exception":
        if not r["exception"] or r["cat"] in ("delivered", "covered"):
            return False
    elif view:
        if r["cat"] != view:
            return False
    elif r["cat"] in ("delivered", "covered"):
        return False  # delivered shipments leave the active queue
    if carrier and r["carrier_name"] != carrier:
        return False
    if status and r["normalized_tracking_status"] != status:
        return False
    if (
        q
        and q.lower() not in str(r["order_number"]).lower()
        and q.lower() not in str(r["tracking_number"]).lower()
    ):
        return False
    return True


def _sort(rows: list[dict], key: str) -> list[dict]:
    if key == "stuck":
        return sorted(rows, key=lambda r: (not r["no_move"], -(r["scan_age"] or 0)))
    if key == "order":
        return sorted(
            rows,
            key=lambda r: [
                int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(r["order_number"]))
            ],
        )
    if key == "oldest":
        return sorted(rows, key=lambda r: -(r["days"] if r["days"] is not None else -1))
    return sorted(
        rows,
        key=lambda r: (
            0 if r["exception"] else 1,
            0 if r["no_move"] else 1,
            RANK.get(r["cat"], 7),
            -(r["days"] or 0),
        ),
    )


def filtered(
    view: str = "",
    carrier: str = "",
    status: str = "",
    q: str = "",
    days: int = 0,
    sort: str = "priority",
    now: datetime | None = None,
) -> tuple[list[dict], list[dict]]:
    now = now or datetime.now(UTC)
    rows = classify(now)
    return _sort(
        [r for r in rows if _matches(r, view, carrier, status, q.strip(), days, now)], sort
    ), rows


def list_shipments(
    view: str = "",
    carrier: str = "",
    status: str = "",
    q: str = "",
    days: int = 0,
    sort: str = "priority",
    page: int = 0,
    size: int = 10,
    now: datetime | None = None,
) -> dict:
    size = max(1, min(size, 200))
    rows, all_rows_ = filtered(view, carrier, status, q, days, sort, now)
    pages = max(1, -(-len(rows) // size))
    page = max(0, min(page, pages - 1))
    return {
        "rows": rows[page * size : (page + 1) * size],
        "total": len(rows),
        "page": page,
        "size": size,
        "pages": pages,
        "facets": {
            "carriers": sorted({r["carrier_name"] for r in all_rows_ if r["carrier_name"]}),
            "statuses": sorted(
                {
                    r["normalized_tracking_status"]
                    for r in _active(
                        all_rows_
                    )  # delivered shipments are not listed, so "delivered" is not an option
                    if r["normalized_tracking_status"]
                }
            ),
        },
        "counts": kpi_counts(all_rows_),
        "empty": not all_rows_,
    }


def kpi_counts(rows: list[dict]) -> dict:
    active = _active(rows)
    c = Counter(r["cat"] for r in active)
    return {
        "active": len(active),
        "on_track": c["on_track"],
        "grey": c["grey"],
        "yellow": c["yellow"],
        "orange": c["orange"],
        "red": c["red"],
        "no_scan": c["no_scan"],
        "unconfirmed": c["unconfirmed"],
        "exception": sum(1 for r in active if r["exception"]),
        "nomove": sum(1 for r in active if r["no_move"]),
        "delivered": sum(1 for r in rows if r["cat"] == "delivered"),
        "covered": sum(1 for r in rows if r["cat"] == "covered"),
    }


def detail(order_number: str, key: str = "") -> dict | None:
    rows = [r for r in classify() if r["order_number"] == order_number]
    if not rows:
        return None
    cur = next((r for r in rows if f"{r['fulfillment_id']}|{r['tracking_number']}" == key), rows[0])
    return {"shipment": cur, "packages": rows}


# ---------------- summary / analytics ----------------
def carrier_table(rows: list[dict]) -> list[dict]:
    by: dict[str, dict] = defaultdict(
        lambda: {
            "active": 0,
            "critical": 0,
            "stuck": 0,
            "exceptions": 0,
            "days": [],
            "cats": Counter(),
        }
    )
    for r in rows:
        name = r["carrier_name"] or "Unknown"
        c = by[name]
        if r["cat"] not in ("delivered", "covered"):
            c["active"] += 1
            c["cats"][r["cat"]] += 1
            if r["days"] is not None:
                c["days"].append(r["days"])
            if r["no_move"]:
                c["stuck"] += 1
        if r["cat"] == "red":
            c["critical"] += 1
        if r["exception"]:
            c["exceptions"] += 1
    out = []
    for name, c in by.items():
        if not c["active"]:
            continue
        pct = round(c["critical"] / c["active"] * 100)
        out.append(
            {
                "name": name,
                "active": c["active"],
                "critical": c["critical"],
                "critical_pct": pct,
                "stuck": c["stuck"],
                "exceptions": c["exceptions"],
                "avg_days": round(sum(c["days"]) / len(c["days"])) if c["days"] else 0,
                "health": "Needs action" if pct > 50 else "Watch" if pct > 20 else "Healthy",
                "cats": dict(c["cats"]),
            }
        )
    return sorted(out, key=lambda x: -x["active"])


def weeks(rows: list[dict], limit: int) -> list[dict]:
    w: Counter = Counter()
    for r in rows:
        k = week_key(r["order_created_at"])
        if k:
            w[k] += 1
    return [{"week": k, "count": n} for k, n in sorted(w.items())[-limit:]]


def _when(v: Any) -> str:
    d = _dt(v)
    return d.strftime("%d %b %Y %H:%M UTC") if d else str(v)


def last_run_info(now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    runs = repo.list_runs(5)
    last = runs[0] if runs else None
    warn = None
    if not last:
        warn = {"level": "stale", "message": "No sync has run yet."}
    elif last["sync_status"] == "failed":
        warn = {
            "level": "error",
            "message": f"Last sync FAILED at {_when(last['started_at'])}: {last['error_summary'] or 'unknown error'}. Showing previous saved data.",
        }
    else:
        started = _dt(last["started_at"])
        if started and (now - started).total_seconds() > STALE_HOURS * 3600:
            warn = {
                "level": "stale",
                "message": f"Data is stale. The last sync started {_when(last['started_at'])}.",
            }
    return {"last": last, "runs": runs, "warning": warn}


def mcf_list(now: datetime | None = None) -> list[dict]:
    """Orders whose Shopify note says DONE while Shopify shows them as not fulfilled, by age."""
    now = now or datetime.now(UTC)
    out = []
    for c in repo.order_checks():
        if (
            not re.search(r"\bdone\b", c["note"] or "", re.I)
            or str(c["fulfillment_status"]).upper() == "FULFILLED"
        ):
            continue
        if c["cancelled"] or str(c["financial_status"]).upper() == "REFUNDED":
            continue
        created = _dt(c["order_created_at"])
        if not created:
            continue
        age = (now - created).days
        lv = next((lv for lv in MCF_LEVELS if age >= lv[0]), None)
        if lv:
            out.append({**c, "age": age, "level": lv[1], "level_label": lv[2]})
    return sorted(out, key=lambda x: -x["age"])


def checklist(rows: list[dict]) -> dict:
    group = [r for r in rows if r["unconfirmed"] and r["cat"] != "covered"]
    st = Counter((r["manual"] or {}).get("status", "") for r in group)
    return {
        "total": len(group),
        "delivered": st["delivered"],
        "lost": st["lost"],
        "failed": st["failed"],
        "in_transit": st["in_transit"],
        "unchecked": sum(1 for r in group if not r["manual"]),
        "tracking_missing": sum(1 for r in group if r["tracking_missing"]),
        "covered": sum(1 for r in rows if r["cat"] == "covered"),
    }


def summary(now: datetime | None = None, week_days: int = 0) -> dict:
    now = now or datetime.now(UTC)
    rows = classify(now)
    active = _active(rows)
    k = kpi_counts(rows)
    confirmed = len(active) - k["unconfirmed"]
    mcf = mcf_list(now)
    return {
        "asOf": now.isoformat(timespec="seconds"),
        "timezone": load_config().timezone,
        "empty": not rows,
        "kpis": k,
        "confirmed": confirmed,
        "total": len(rows),
        "health": [
            {"key": key, "count": k[key]}
            for key in ("red", "orange", "yellow", "grey", "on_track", "no_scan")
        ],
        "weeks": weeks(
            [
                r
                for r in active
                if not week_days
                or ((c := _dt(r["order_created_at"])) and c >= now - timedelta(days=week_days))
            ],
            10,
        ),
        "carriers": [
            {
                "name": c["name"],
                "active": c["active"],
                "critical": c["critical"],
                "stuck": c["stuck"],
            }
            for c in carrier_table(rows)[:5]
        ],
        "mcf": {
            "total": len(mcf),
            "counts": dict(Counter(x["level"] for x in mcf)),
            "rows": mcf[:5],
        },
        "checklist": checklist(rows),
        "run": last_run_info(now),
    }


def analytics(now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    rows = classify(now)
    active = _active(rows)
    k = kpi_counts(rows)
    with_days = [r for r in active if r["days"] is not None]
    table = carrier_table(rows)
    crit_orders: dict[str, tuple[float, str]] = {}
    for r in rows:
        if (
            r["cat"] == "red"
            and r["order_total"] is not None
            and r["order_number"] not in crit_orders
        ):
            crit_orders[r["order_number"]] = (float(r["order_total"]), r["order_currency"])
    risk = sum(v for v, _ in crit_orders.values()) if crit_orders else None
    currencies = {c for _, c in crit_orders.values() if c}
    day_names = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    tot: Counter = Counter()
    crit: Counter = Counter()
    for r in active:
        f = _dt(r["fulfilled_at"])
        name = day_names[f.astimezone(UTC).weekday()] if f else "No date"
        tot[name] += 1
        if r["cat"] == "red":
            crit[name] += 1
    order = [d for d in day_names if tot[d]] + (["No date"] if tot["No date"] else [])
    stages = {
        "pre_dispatch": sum(1 for r in rows if r["stage"] == "pre_dispatch"),
        "dispatched": sum(1 for r in rows if r["stage"] == "dispatched"),
        "delivered": k["delivered"],
    }
    wk = weeks(active, 12)
    tips = []
    if k["red"]:
        tips.append(
            f"{k['red']} active shipments are 9+ days in stage. Escalate these first (view: Critical)."
        )
    worst = max(table, key=lambda c: c["critical"], default=None)
    if worst and worst["critical"]:
        tips.append(
            f"{worst['name']} has the most critical shipments ({worst['critical']}). Check them with this carrier first."
        )
    if k["nomove"]:
        tips.append(
            f"{k['nomove']} shipments have had no carrier scan for 5+ days. These may be stuck or lost."
        )
    if k["exception"]:
        tips.append(
            f"{k['exception']} carrier exception(s) need a decision (failed delivery or return)."
        )
    if wk:
        top = max(wk, key=lambda w: w["count"])
        tips.append(
            f"Most active shipments were created in the week of {top['week']} ({top['count']}). Check why intake spiked."
        )
    return {
        "empty": not rows,
        "kpis": {
            "active": len(active),
            "critical": k["red"],
            "critical_pct": round(k["red"] / len(active) * 100) if active else 0,
            "on_track_pct": round(k["on_track"] / len(active) * 100) if active else 0,
            "avg_days": round(sum(r["days"] for r in with_days) / len(with_days))
            if with_days
            else 0,
            "stuck": k["nomove"],
            "carriers": len(table),
            "value_at_risk": risk,
            "value_currency": next(iter(currencies)) if len(currencies) == 1 else "",
        },
        "aging": [
            {"key": key, "count": k[key]}
            for key in ("red", "orange", "yellow", "grey", "on_track", "no_scan")
        ],
        "weeks": wk,
        "carriers": table,
        "stages": stages,
        "dispatch_days": [
            {"day": d, "critical": crit[d], "other": tot[d] - crit[d]} for d in order
        ],
        "tips": tips,
    }


def checks_page(now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    rows = classify(now)
    mcf = mcf_list(now)
    return {
        "mcf": mcf,
        "mcf_counts": dict(Counter(x["level"] for x in mcf)),
        "checklist": checklist(rows),
        "unconfirmed": sorted(
            [r for r in rows if r["cat"] == "unconfirmed"],
            key=lambda r: (not r["tracking_missing"], -(r["days"] or 0)),
        ),
    }


# ---------------- CSV exports ----------------
def _safe(v: Any) -> Any:
    """Stop spreadsheet formulas: a text cell starting with = + @ is prefixed with an apostrophe."""
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "@") else v


def _csv(head: list[str], body: list[list[Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL)
    w.writerow(head)
    w.writerows([[_safe(c) for c in row] for row in body])
    return buf.getvalue()


def export_csv(kind: str, **filters: Any) -> tuple[str, str]:
    """(filename, csv text). kind: filtered | escalation | verify."""
    if kind == "escalation":
        rows = sorted(
            [r for r in classify() if r["cat"] == "red" or r["no_move"]],
            key=lambda r: -(r["days"] or 0),
        )
        head = [
            "order_number",
            "carrier_name",
            "tracking_number",
            "days_in_stage",
            "reason",
            "last_scan_at",
            "shopify_order_url",
        ]
        return "escalation_list.csv", _csv(
            head,
            [
                [
                    r["order_number"],
                    r["carrier_name"],
                    r["tracking_number"],
                    r["days"],
                    "Critical" if r["cat"] == "red" else "Stuck",
                    r["last_scan_at"],
                    r["shopify_url"],
                ]
                for r in rows
            ],
        )
    if kind == "verify":
        rows = sorted(
            [r for r in classify() if r["cat"] == "unconfirmed"],
            key=lambda r: (not r["tracking_missing"], -(r["days"] or 0)),
        )
        head = [
            "action",
            "order_number",
            "carrier_name",
            "tracking_number",
            "dispatched",
            "days_in_stage",
            "last_scan_at",
            "team_status",
            "track_url",
            "shopify_order_url",
        ]
        return "amazon_unknown_to_verify.csv", _csv(
            head,
            [
                [
                    "ADD TRACKING NUMBER IN SHOPIFY"
                    if r["tracking_missing"]
                    else "Check carrier page",
                    r["order_number"],
                    r["carrier_name"],
                    "" if r["tracking_missing"] else r["tracking_number"],
                    r["fulfilled_at"],
                    r["days"],
                    r["last_scan_at"],
                    (r["manual"] or {}).get("status", "not checked"),
                    "" if r["tracking_missing"] else r["track_url"],
                    r["shopify_url"],
                ]
                for r in rows
            ],
        )
    rows, _ = filtered(**filters)
    head = [
        "order_number",
        "tracking_number",
        "carrier_name",
        "fulfilled_at",
        "last_scan_at",
        "days",
        "normalized_tracking_status",
        "category",
        "last_checked_at",
        "tracking_url",
    ]
    return "delayed_orders_filtered.csv", _csv(
        head,
        [
            [
                r["order_number"],
                r["tracking_number"],
                r["carrier_name"],
                r["fulfilled_at"],
                r["last_scan_at"],
                r["days"],
                r["normalized_tracking_status"],
                r["cat_label"],
                r["last_checked_at"],
                r["track_url"],
            ]
            for r in rows
        ],
    )
