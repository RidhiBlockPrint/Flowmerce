"""Aging rules. Pure functions, no I/O, so they are easy to test.

Complete days = whole 24-hour periods between the last *physical* carrier scan
and "now". Both timestamps are timezone-aware and compared in UTC.
"""

from datetime import UTC, datetime, timedelta

DEFAULT_THRESHOLDS = {"grey": 2, "yellow": 4, "orange": 6, "red": 9}

CATEGORY_LABELS = {
    "on_track": "On Track",
    "grey": "Grey 2-3 days",
    "yellow": "Yellow 4-5 days",
    "orange": "Orange 6-8 days",
    "red": "Red 9+ days",
    "no_scan": "No scan data",
    "delivered": "Delivered",
}

ACTIONS = {
    "on_track": "Continue monitoring.",
    "grey": "Continue monitoring.",
    "yellow": "Review if carrier SLA or expected delivery date shows a problem.",
    "orange": "Prioritize for investigation.",
    "red": "Add to urgent escalation list.",
    "no_scan": "Verify tracking details or wait for the first carrier scan.",
    "delivered": "None. Delivered.",
}


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)


def complete_days(last_scan_at, now: datetime):
    """Whole 24h periods since the last physical scan. None when there is no scan."""
    if last_scan_at is None:
        return None
    delta = to_utc(now) - to_utc(last_scan_at)
    return max(0, int(delta // timedelta(hours=24)))


def categorize(
    last_scan_at, now: datetime, thresholds: dict = None, delivered: bool = False
) -> str:
    """Aging category key. Delivered wins. A missing scan is never 'on track'."""
    if delivered:
        return "delivered"
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    days = complete_days(last_scan_at, now)
    if days is None:
        return "no_scan"
    if days >= t["red"]:
        return "red"
    if days >= t["orange"]:
        return "orange"
    if days >= t["yellow"]:
        return "yellow"
    if days >= t["grey"]:
        return "grey"
    return "on_track"


def recommended_action(category: str, exception: str = "") -> str:
    if exception:
        return f"Carrier exception ({exception}): review the reason and decide the next step."
    return ACTIONS.get(category, "Review manually.")


# ---------------------------------------------------------------------------
# Flow rules (agreed with operations)
#   Not dispatched yet : clock starts at ORDER date.   grey 2-3, yellow 4-5, orange 6-8, red 9+
#   Dispatched         : clock starts at DISPATCH date (Shopify fulfilled date).
#                        on track 0-3, yellow 4-5, orange 6-8, red 9+ (critical alert)
#   Scans do NOT reset the clock. A parcel still red after 9 days stays red.
#   Delivered          : leaves the active queue.
# ---------------------------------------------------------------------------
def flow_category(
    order_created_at, dispatched_at, now: datetime, thresholds: dict = None, delivered: bool = False
):
    """Returns (category, days, stage). stage is 'pre_dispatch', 'dispatched' or 'delivered'."""
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    if delivered:
        return "delivered", None, "delivered"
    if dispatched_at is None:
        days = complete_days(order_created_at, now)
        stage = "pre_dispatch"
        if days is None:
            return "no_scan", None, stage
        if days >= t["red"]:
            return "red", days, stage
        if days >= t["orange"]:
            return "orange", days, stage
        if days >= t["yellow"]:
            return "yellow", days, stage
        if days >= t["grey"]:
            return "grey", days, stage
        return "on_track", days, stage
    days = complete_days(dispatched_at, now)
    stage = "dispatched"
    if days >= t["red"]:
        return "red", days, stage
    if days >= t["orange"]:
        return "orange", days, stage
    if days >= t["yellow"]:
        return "yellow", days, stage
    return "on_track", days, stage


NO_MOVE_DAYS = 5


def is_no_movement(
    last_scan_at, now: datetime, delivered: bool = False, days: int = NO_MOVE_DAYS
) -> bool:
    """True when a shipment is not delivered and its last carrier scan is 5+ complete days old.
    A shipment with no scan at all is NOT flagged here (we do not know its movement)."""
    if delivered or last_scan_at is None:
        return False
    return (complete_days(last_scan_at, now) or 0) >= days
