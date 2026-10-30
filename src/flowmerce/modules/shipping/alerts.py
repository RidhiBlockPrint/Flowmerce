"""Daily team alert: email the list of critical shipments (9+ days in stage) and no-movement ones.

Runs after each successful sync. Does nothing if SMTP is not configured, or if nothing is critical.
Uses the same stage rules as the dashboard (dispatch date after dispatch, order date before).
"""

import os
import re
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage

from .aging import flow_category, is_no_movement


def _dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def alert_due(event_name: str, local_hour: int, alert_hour: int = 2) -> bool:
    """Scheduled runs send the alert once, at the 2 AM IST run. Manual runs always send (for testing)."""
    if event_name != "schedule":
        return True
    return local_hour == alert_hour


def _unconfirmed(r) -> bool:
    c = str(r.get("carrier_name") or "").strip().lower()
    return c == "" or "amazon" in c or c == "unknown"


def build_digest(records, now: datetime, thresholds: dict = None):
    """records: iterable of shipment dicts (from the store). Returns (critical_rows, stuck_rows)."""
    critical, stuck = [], []
    for r in records:
        if r.get("normalized_tracking_status") == "delivered" or r.get("delivered_at"):
            continue
        if _unconfirmed(
            r
        ):  # Amazon / Unknown carriers: no delivery data, never counted as critical or stuck
            continue
        order_at = _dt(r.get("order_created_at"))
        disp_at = _dt(r.get("fulfilled_at"))
        cat, days, stage = flow_category(order_at, disp_at, now, thresholds)
        row = {
            "order": r.get("order_number", ""),
            "carrier": r.get("carrier_name", ""),
            "days": days,
            "stage": stage,
            "tracking": r.get("tracking_number", ""),
        }
        if cat == "red":
            critical.append(row)
        last_scan = _dt(r.get("last_scan_at"))
        if last_scan and is_no_movement(last_scan, now):
            stuck.append({**row, "scan_days": (now - last_scan).days})
    critical.sort(key=lambda x: -(x["days"] or 0))
    stuck.sort(key=lambda x: -x["scan_days"])
    return critical, stuck


MCF_LEVELS = [(10, "critical"), (7, "watch"), (5, "alert")]  # 10+ days critical, 7+ watch, 5+ alert


def build_mcf(checks, now: datetime):
    """Orders whose notes say DONE while Shopify still shows them as not fulfilled, 5+ days after the order."""
    out = []
    for c in checks or []:
        note = c.get("note") or ""
        if not re.search(r"\bdone\b", note, re.I):
            continue
        if c.get("cancelled") or (c.get("financial_status") or "").upper() == "REFUNDED":
            continue
        if (c.get("fulfillment_status") or "").upper() == "FULFILLED":
            continue
        created = _dt(c.get("order_created_at"))
        if not created:
            continue
        age = (now - created).days
        level = next((label for days, label in MCF_LEVELS if age >= days), None)
        if level:
            out.append(
                {
                    "order": c.get("order_number", ""),
                    "age": age,
                    "status": c.get("fulfillment_status") or "NOT FULFILLED",
                    "level": level,
                }
            )
    return sorted(out, key=lambda x: -x["age"])


def build_body(critical, stuck, today, mcf=None):
    lines = [f"Shipping alert for {today}", ""]
    lines.append(f"CRITICAL (9+ days in stage): {len(critical)} shipment(s)")
    for c in critical[:100]:
        lines.append(
            f"  - {c['order']} | {c['carrier'] or '-'} | {c['days']} days | {c['stage'].replace('_', ' ')}"
        )
    if len(critical) > 100:
        lines.append(f"  ...and {len(critical) - 100} more (see dashboard)")
    lines += ["", f"NO MOVEMENT (no carrier scan for 5+ days): {len(stuck)} shipment(s)"]
    for s in stuck[:100]:
        lines.append(
            f"  - {s['order']} | {s['carrier'] or '-'} | last scan {s['scan_days']} days ago"
        )
    if mcf:
        lines += ["", f"NOTES SAY DONE, SHOPIFY NOT FULFILLED (5+ days): {len(mcf)} order(s)"]
        for m in mcf[:100]:
            lines.append(f"  - {m['order']} | {m['age']} days | {m['status']} | {m['level']}")
    lines += ["", "Open the dashboard to act on these. Shopify and customers were not changed."]
    return "\n".join(lines)


def send_email(subject: str, body: str, env=os.environ, smtp_factory=smtplib.SMTP):
    """Sends only when SMTP settings exist. Returns a short status string."""
    host, user, pwd = env.get("SMTP_HOST", ""), env.get("SMTP_USER", ""), env.get("SMTP_PASS", "")
    to = [x.strip() for x in env.get("ALERT_TO", "").split(",") if x.strip()]
    missing = [
        name
        for name, val in (
            ("SMTP_HOST", host),
            ("SMTP_USER", user),
            ("SMTP_PASS", pwd),
            ("ALERT_TO", ",".join(to)),
        )
        if not val
    ]
    if missing:  # names only, never values
        return "alert skipped: empty or missing setting(s): " + ", ".join(missing)
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = env.get("ALERT_FROM", user)
    msg["To"] = ", ".join(to)
    msg.set_content(body)
    port = int(env.get("SMTP_PORT", "587"))
    with smtp_factory(host, port, timeout=30) as s:
        s.starttls()
        s.login(user, pwd)
        s.send_message(msg)
    return f"alert sent to {len(to)} recipient(s)"


def run_alerts(
    records, now=None, thresholds=None, env=os.environ, smtp_factory=smtplib.SMTP, checks=None
) -> str:
    now = now or datetime.now(UTC)
    critical, stuck = build_digest(records, now, thresholds)
    mcf = build_mcf(checks, now)
    if not critical and not stuck and not mcf:
        return "no critical, stuck or notes-mismatch shipments: no alert"
    today = now.astimezone().strftime("%d %b %Y")
    subject = f"[ALERT] {len(critical)} critical, {len(stuck)} no movement, {len(mcf)} notes-mismatch: {today}"
    return send_email(subject, build_body(critical, stuck, today, mcf), env, smtp_factory)
