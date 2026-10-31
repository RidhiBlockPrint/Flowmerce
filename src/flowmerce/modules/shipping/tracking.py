"""Tracking-service lookup for parcels whose delivery Shopify never acknowledges (mainly Amazon, and shipments of mixed
orders). A provider takes tracking numbers and returns what the carrier says; only real answers are saved, and
anything the provider cannot tell is left as it was (nothing is invented).

Providers sit behind one small interface, so the service can be swapped. The one built in is 17TRACK. NOTE: it was
written from the published 17TRACK API description and tested only against a fake server. It has NOT been run against
the live service yet (no API key was available), so treat the first real run as the verification.

The lookup is explicit (a button / endpoint), limited per run, and orders the most delayed parcels first, because most
services bill per tracking number."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any, Protocol

from ..seo.config import env
from . import orders, repo
from .carriers import CarrierAdapter, TrackingResult
from .sync import _apply_carrier

TRACK17_BASE = "https://api.17track.net/track/v2.4"
BATCH = 40  # 17TRACK accepts up to 40 numbers per request
DEFAULT_LIMIT = 40


class TrackingProvider(Protocol):
    name: str

    def lookup(self, numbers: list[str]) -> dict[str, TrackingResult | None]: ...


def _when(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


class Track17:
    """17TRACK Tracking API. Tracking numbers must be registered once; the answer for a number registered just now
    arrives on a later lookup, so a number the service does not know yet is registered and returns None this time."""

    name = "17TRACK"

    def __init__(self, api_key: str, opener=None, base: str = TRACK17_BASE) -> None:
        self.key, self.base = api_key, base.rstrip("/")
        self._open = opener or urllib.request.urlopen

    def _post(self, path: str, body: list[dict]) -> dict:
        req = urllib.request.Request(  # noqa: S310 - fixed https URL
            f"{self.base}{path}",
            data=json.dumps(body).encode(),
            method="POST",
            headers={"17token": self.key, "Content-Type": "application/json"},
        )
        try:
            with self._open(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"17TRACK {path} failed: HTTP {exc.code}") from exc

    @staticmethod
    def parse(item: dict) -> TrackingResult | None:
        info = item.get("track_info") or {}
        status = str((info.get("latest_status") or {}).get("status") or "")
        event = info.get("latest_event") or {}
        at = _when(event.get("time_utc") or event.get("time_iso"))
        text = str(event.get("description") or "")
        place = str(event.get("location") or "")
        if status == "Delivered":
            return TrackingResult("DELIVERED", at, text, place, delivered_at=at)
        if status in ("InTransit", "OutForDelivery", "InfoReceived", "AvailableForPickup"):
            return TrackingResult(status.upper(), at, text, place)
        if status in ("DeliveryFailure", "Exception"):
            return TrackingResult(status.upper(), at, text, place, exception="failed_delivery")
        return None  # NotFound / Expired / unknown: say nothing rather than guess

    def lookup(self, numbers: list[str]) -> dict[str, TrackingResult | None]:
        out: dict[str, TrackingResult | None] = {}
        for i in range(0, len(numbers), BATCH):
            chunk = numbers[i : i + BATCH]
            data = (self._post("/gettrackinfo", [{"number": n} for n in chunk]).get("data")) or {}
            for item in data.get("accepted") or []:
                out[str(item.get("number"))] = self.parse(item)
            unknown = [str(r.get("number")) for r in data.get("rejected") or []]
            if unknown:
                self._post("/register", [{"number": n} for n in unknown])
                out.update({n: None for n in unknown})
        return out


def configured_provider() -> TrackingProvider | None:
    key = env("TRACK17_API_KEY")
    return Track17(key) if key else None


class _Answers(CarrierAdapter):
    """Hands sync's carrier step the answers a provider already returned."""

    def __init__(self, answers: dict[str, TrackingResult | None]) -> None:
        self.answers = answers

    def track(self, tracking_number: str) -> TrackingResult | None:
        return self.answers.get(tracking_number)


def candidates(now: datetime | None = None, limit: int = DEFAULT_LIMIT) -> list[dict]:
    """Tracked, undelivered shipments of in-transit and delayed orders, most delayed first (one per number)."""
    rank = {"critical": 0, "red": 1, "orange": 2, "yellow": 3, None: 4}
    seen: set[str] = set()
    picked: list[tuple[int, int, dict]] = []
    for o in orders.build_orders(now):
        if o["group"] not in ("delayed", "in_transit"):
            continue
        for s in o["shipments"]:
            if s["tracked"] and not s["delivered"] and s["tracking_number"] not in seen:
                seen.add(s["tracking_number"])
                picked.append(
                    (rank[o["tier"]], -(o["days"] or 0), {"order": o["order_number"], **s})
                )
    picked.sort(key=lambda p: (p[0], p[1]))
    return [p[2] for p in picked[:limit]]


def check_open_orders(
    provider: TrackingProvider | None = None,
    limit: int = DEFAULT_LIMIT,
    now: datetime | None = None,
) -> dict:
    """Ask the tracking service about the most delayed open parcels and save what it reports."""
    provider = provider or configured_provider()
    if provider is None:
        raise RuntimeError("No tracking service is set up: add TRACK17_API_KEY to .env.")
    todo = candidates(now, limit)
    answers = provider.lookup([c["tracking_number"] for c in todo])
    adapter = _Answers(answers)
    existing = repo.load_shipments()
    errors: list[str] = []
    changed = delivered = 0
    for c in todo:
        key = f"{c['fulfillment_id']}|{c['tracking_number']}"
        rec = dict(existing.get(key) or {})
        if not rec or answers.get(c["tracking_number"]) is None:
            continue
        before = (
            rec.get("delivered_at"),
            rec.get("last_scan_at"),
            rec.get("normalized_tracking_status"),
        )
        rec = _apply_carrier(rec, lambda _carrier, a=adapter: a, errors)
        if (
            rec.get("delivered_at"),
            rec.get("last_scan_at"),
            rec.get("normalized_tracking_status"),
        ) != before:
            repo.save_shipments([rec])
            changed += 1
            delivered += 1 if rec.get("normalized_tracking_status") == "delivered" else 0
    answered = sum(1 for c in todo if answers.get(c["tracking_number"]) is not None)
    return {
        "provider": provider.name,
        "asked": len(todo),
        "answered": answered,
        "updated": changed,
        "now_delivered": delivered,
        "not_known_yet": len(todo) - answered,
    }
