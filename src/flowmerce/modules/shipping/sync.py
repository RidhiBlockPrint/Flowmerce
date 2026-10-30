"""Shipping sync: Shopify fetch -> normalize -> carrier check (if configured) -> merge with saved data -> save ->
log the run. A failure before the save leaves the saved data untouched. Read-only against Shopify: nothing in
Shopify is ever created, changed or cancelled by this module."""

from __future__ import annotations

from datetime import UTC, datetime

from .carriers import get_adapter
from .config import ShippingConfig, load_config
from .normalize import normalize_order_checks, normalize_orders
from .repo import SqliteStore, list_runs, row_key
from .shopify import ShopifyClient, ShopifyError, TokenProvider

SCAN_FIELDS = {"last_scan_at", "last_scan_description", "last_scan_location"}


def _iso(dt):
    return dt.isoformat() if dt else None


def _merge(prev: dict | None, new: dict) -> dict:
    """New Shopify data overwrites old, but never blanks out a saved scan."""
    out = dict(prev or {})
    for k, v in new.items():
        if k in SCAN_FIELDS and v is None and prev and prev.get(k) is not None:
            continue
        out[k] = v
    return out


def _apply_carrier(rec: dict, lookup, errors: list) -> dict:
    if not rec["tracking_number"]:
        return rec
    adapter = lookup(rec["carrier_name"])
    try:
        result = adapter.track(rec["tracking_number"])
    except Exception as exc:  # noqa: BLE001 - a carrier outage must not stop the whole sync
        errors.append(f"{rec['tracking_number']}: {exc}"[:200])
        rec["carrier_error"] = str(exc)[:200]
        return rec
    if result is None:
        return rec
    rec["carrier_error"] = ""
    rec["tracking_source"] = "carrier"
    rec["raw_tracking_status"] = result.raw_status
    if result.last_scan_at:
        rec["last_scan_at"] = result.last_scan_at
        rec["last_scan_description"] = result.last_scan_description
        rec["last_scan_location"] = result.last_scan_location
    if result.delivered_at:
        rec["delivered_at"] = result.delivered_at
        rec["normalized_tracking_status"] = "delivered"
    if result.exception:
        rec["exception"] = result.exception
        rec["normalized_tracking_status"] = result.exception
    return rec


def run_sync(cfg: ShippingConfig, shopify, store, lookup=get_adapter, now=None) -> dict:
    now = now or datetime.now(UTC)
    run = {
        "started_at": _iso(now),
        "completed_at": None,
        "sync_status": "running",
        "orders_processed": 0,
        "shipments_created": 0,
        "shipments_updated": 0,
        "exceptions_count": 0,
        "error_summary": "",
    }
    try:
        orders = list(shopify.fetch_orders(cfg.orders_since))  # may raise
        run["orders_processed"] = len(orders)
        existing = store.load()  # may raise
        errors, out = [], {}
        for row in normalize_orders(orders):
            key = row_key(row)
            if key in out:  # same fulfillment seen twice in one run: process once
                continue
            prev = existing.get(key)
            rec = _merge(prev, {**row, "last_checked_at": now})
            rec = _apply_carrier(rec, lookup, errors)
            if rec.get("exception"):
                run["exceptions_count"] += 1
            if prev:
                run["shipments_updated"] += 1
            else:
                run["shipments_created"] += 1
            out[key] = rec
        store.save(list(out.values()))  # only after success
        try:
            store.save_checks(list(normalize_order_checks(orders)))
        except Exception as exc:  # noqa: BLE001 - shipments are saved; report the order-check problem only
            errors.append(f"order checks not saved: {type(exc).__name__}")
        run["sync_status"] = "partial" if errors else "success"
        run["error_summary"] = "; ".join(errors)[:1000]
    except Exception as exc:  # noqa: BLE001 - recorded on the run
        run["sync_status"] = "failed"
        run["error_summary"] = f"{type(exc).__name__}: {exc}"[:1000]
    run["completed_at"] = _iso(datetime.now(UTC))
    store.record_run(run)
    return run


def build_shopify(cfg: ShippingConfig) -> ShopifyClient:
    if cfg.client_id and cfg.client_secret:
        provider = TokenProvider(cfg.shop_domain, cfg.client_id, cfg.client_secret)
        return ShopifyClient(cfg.shop_domain, api_version=cfg.api_version, token_provider=provider)
    return ShopifyClient(cfg.shop_domain, cfg.token, cfg.api_version)


def sync_now() -> dict:
    """Run one sync with the configured credentials and save into the Flowmerce database."""
    cfg = load_config()
    store = SqliteStore()
    if not cfg.has_shopify_credentials:
        run = {
            "started_at": _iso(datetime.now(UTC)),
            "completed_at": _iso(datetime.now(UTC)),
            "sync_status": "failed",
            "error_summary": "Shopify credentials are not set (SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET, "
            "or the SHIPPING_ versions of them, in .env).",
        }
        store.record_run(run)
        return run
    try:
        shopify = build_shopify(cfg)
    except ShopifyError as exc:
        run = {
            "started_at": _iso(datetime.now(UTC)),
            "completed_at": _iso(datetime.now(UTC)),
            "sync_status": "failed",
            "error_summary": str(exc),
        }
        store.record_run(run)
        return run
    return run_sync(cfg, shopify, store)


def tick(every_hours: int = 1) -> None:
    """Background refresh: sync when credentials exist and the last run is older than `every_hours`."""
    if not load_config().has_shopify_credentials:
        return
    runs = list_runs(1)
    if runs:
        try:
            started = datetime.fromisoformat(str(runs[0]["started_at"]).replace("Z", "+00:00"))
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            if (datetime.now(UTC) - started).total_seconds() < every_hours * 3600:
                return
        except ValueError:
            pass
    sync_now()


class _OrdersByName:
    """Gives run_sync the orders for a fixed list of names instead of the open-orders search."""

    def __init__(self, shopify, names: list[str]):
        self.shopify, self.names = shopify, names

    def fetch_orders(self, since: str):
        yield from self.shopify.fetch_orders_by_name(self.names)


class _QuietStore(SqliteStore):
    """A re-check updates the shipments but is not a full sync, so it does not write a sync-run row."""

    def record_run(self, run_row: dict) -> None:
        return None


def recheck_missing(shopify=None) -> dict:
    """Ask Shopify again (read-only) about every order that is listed as missing a tracking number.

    The normal sync only looks at open orders, so a tracking number added later to an older order can be missed.
    This fetches exactly those orders by name and saves what Shopify says now."""
    from . import service  # local import: service does not depend on sync

    names = sorted({r["order_number"] for r in service.issues()["missing"]})
    if not names:
        return {
            "requested": 0,
            "found": 0,
            "fixed": 0,
            "sync_status": "success",
            "error_summary": "",
        }
    cfg = load_config()
    if shopify is None:
        if not cfg.has_shopify_credentials:
            return {
                "requested": len(names),
                "found": 0,
                "fixed": 0,
                "sync_status": "failed",
                "error_summary": "Shopify credentials are not set in .env.",
            }
        shopify = build_shopify(cfg)
    result = run_sync(cfg, _OrdersByName(shopify, names), _QuietStore())
    still = {r["order_number"] for r in service.issues()["missing"]}
    return {
        "requested": len(names),
        "found": result["orders_processed"],
        "fixed": len(set(names) - still),
        "still_missing": len(set(names) & still),
        "sync_status": result["sync_status"],
        "error_summary": result["error_summary"],
    }
