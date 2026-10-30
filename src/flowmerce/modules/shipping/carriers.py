"""Carrier tracking adapters.

Every carrier is one class with a `track()` method that returns a TrackingResult
with real scan data, or None when no scan data is available.

Rules:
- Never invent a scan time. The sync run time is not a scan.
- Never infer a scan from the absence of an update.
- If an adapter fails, the sync keeps the last saved scan.

To add a carrier: subclass CarrierAdapter, set `companies`, implement track(),
and register it in ADAPTERS.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TrackingResult:
    raw_status: str
    last_scan_at: datetime | None  # timezone-aware, from the carrier event
    last_scan_description: str = ""
    last_scan_location: str = ""
    delivered_at: datetime | None = None
    exception: str = ""  # e.g. "FAILED_DELIVERY", "RETURNED"
    carrier_event_id: str = ""


class CarrierAdapter:
    companies: tuple = ()

    def track(self, tracking_number: str) -> TrackingResult | None:
        raise NotImplementedError


class NotConfiguredAdapter(CarrierAdapter):
    """Used when no carrier API key is set. Returns no scan data, on purpose."""

    companies = ()

    def track(self, tracking_number):
        return None


ADAPTERS = {}  # e.g. {"dhl": DhlAdapter()} once a carrier API is configured


def get_adapter(company: str) -> CarrierAdapter:
    name = (company or "").lower()
    for key, adapter in ADAPTERS.items():
        if key in name:
            return adapter
    return NotConfiguredAdapter()
