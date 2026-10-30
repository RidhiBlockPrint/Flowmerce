"""The only file that reads or writes shipping data. Everything else (sync, service, API, importer) goes through
these functions, so moving storage to Supabase later means rewriting this file, not the module."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from ..seo import db
from ..seo.db import all_rows, get, run
from .schema import ensure_schema

SHIPMENT_FIELDS = (
    "shopify_order_id",
    "order_number",
    "fulfillment_id",
    "tracking_number",
    "carrier_name",
    "tracking_url",
    "order_created_at",
    "fulfilled_at",
    "expected_delivery_at",
    "raw_tracking_status",
    "normalized_tracking_status",
    "exception",
    "last_scan_at",
    "last_scan_description",
    "last_scan_location",
    "tracking_source",
    "last_checked_at",
    "carrier_error",
    "delivered_at",
    "order_total",
    "order_currency",
)
TEXT_DEFAULT = {
    "tracking_number",
    "carrier_name",
    "tracking_url",
    "raw_tracking_status",
    "normalized_tracking_status",
    "exception",
    "last_scan_description",
    "last_scan_location",
    "tracking_source",
    "carrier_error",
    "order_currency",
}
RUN_FIELDS = (
    "started_at",
    "completed_at",
    "sync_status",
    "orders_processed",
    "shipments_created",
    "shipments_updated",
    "exceptions_count",
    "error_summary",
)
CHECK_FIELDS = (
    "order_number",
    "shopify_order_id",
    "order_created_at",
    "fulfillment_status",
    "financial_status",
    "cancelled",
    "note",
    "order_total",
    "order_currency",
)
CHECK_TEXT = (
    "shopify_order_id",
    "fulfillment_status",
    "financial_status",
    "note",
    "order_currency",
)

_ready_for: object = None


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ready() -> None:
    """Create the shipping tables on the open connection once (the connection changes between tests/restarts)."""
    global _ready_for
    conn = db._db()
    if _ready_for is not conn:
        ensure_schema()
        _ready_for = conn


def _iso(v: Any) -> Any:
    return v.isoformat() if isinstance(v, datetime) else v


def row_key(rec: dict) -> str:
    return "|".join(str(rec.get(k) or "") for k in ("fulfillment_id", "tracking_number"))


# ---------------- shipments ----------------
def load_shipments() -> dict[str, dict]:
    ready()
    return {row_key(r): r for r in all_rows("SELECT * FROM shipping_shipments ORDER BY id")}


def all_shipments() -> list[dict]:
    ready()
    return all_rows("SELECT * FROM shipping_shipments ORDER BY id")


def save_shipments(records: Iterable[dict]) -> tuple[int, int]:
    """Upsert by (fulfillment_id, tracking_number). Returns (created, updated)."""
    ready()
    now = _now()
    created = updated = 0
    with db.tx():
        for rec in records:
            vals = []
            for f in SHIPMENT_FIELDS:
                v = _iso(rec.get(f))
                vals.append("" if v is None and f in TEXT_DEFAULT else v)
            exists = get(
                "SELECT id FROM shipping_shipments WHERE fulfillment_id = ? AND tracking_number = ?",
                rec["fulfillment_id"],
                rec.get("tracking_number") or "",
            )
            if exists:
                sets = ", ".join(f"{f} = ?" for f in SHIPMENT_FIELDS)
                run(
                    f"UPDATE shipping_shipments SET {sets}, updated_at = ? WHERE id = ?",
                    *vals,
                    now,
                    exists["id"],
                )
                updated += 1
            else:
                cols = ", ".join(SHIPMENT_FIELDS)
                marks = ", ".join("?" for _ in SHIPMENT_FIELDS)
                run(
                    f"INSERT INTO shipping_shipments ({cols}, created_at, updated_at) VALUES ({marks}, ?, ?)",
                    *vals,
                    now,
                    now,
                )
                created += 1
    return created, updated


def delete_shipments_not_in(keep: set[str]) -> int:
    """Delete shipments whose (fulfillment_id|tracking_number) is not in `keep`. Used only by the Supabase mirror import."""
    ready()
    stale = [
        r["id"]
        for r in all_rows("SELECT id, fulfillment_id, tracking_number FROM shipping_shipments")
        if row_key(r) not in keep
    ]
    with db.tx():
        for i in stale:
            run("DELETE FROM shipping_shipments WHERE id = ?", i)
    return len(stale)


# ---------------- sync runs ----------------
def record_run(run_row: dict) -> int:
    ready()
    vals = []
    for f in RUN_FIELDS:
        v = _iso(run_row.get(f))
        if v is None and f in (
            "orders_processed",
            "shipments_created",
            "shipments_updated",
            "exceptions_count",
        ):
            v = 0
        if v is None and f == "error_summary":
            v = ""
        vals.append(v)
    cols = ", ".join(RUN_FIELDS)
    marks = ", ".join("?" for _ in RUN_FIELDS)
    return run(f"INSERT INTO shipping_sync_runs ({cols}) VALUES ({marks})", *vals).last_id


def list_runs(limit: int = 5) -> list[dict]:
    ready()
    return all_rows(
        "SELECT * FROM shipping_sync_runs ORDER BY started_at DESC, id DESC LIMIT ?", limit
    )


# ---------------- manual status, checks, notes ----------------
def manual_statuses() -> dict[str, dict]:
    ready()
    return {
        f"{r['order_number']}|{r['tracking_number']}": r
        for r in all_rows("SELECT * FROM shipping_manual_status")
    }


def set_manual_status(order_number: str, tracking_number: str, status: str, user: str) -> None:
    ready()
    run(
        """INSERT INTO shipping_manual_status (order_number, tracking_number, status, updated_by, updated_at)
           VALUES (?,?,?,?,?)
           ON CONFLICT (order_number, tracking_number) DO UPDATE SET status = excluded.status,
             updated_by = excluded.updated_by, updated_at = excluded.updated_at""",
        order_number,
        tracking_number,
        status,
        user,
        _now(),
    )


def order_checks() -> list[dict]:
    ready()
    return all_rows("SELECT * FROM shipping_order_checks ORDER BY order_number")


def upsert_order_checks(rows: Iterable[dict]) -> int:
    ready()
    now = _now()
    n = 0
    with db.tx():
        for r in rows:
            vals = []
            for f in CHECK_FIELDS:
                v = r.get(f)
                if f == "cancelled":
                    v = 1 if v else 0
                elif v is None and f in CHECK_TEXT:
                    v = ""
                vals.append(v)
            run(
                """INSERT INTO shipping_order_checks (order_number, shopify_order_id, order_created_at, fulfillment_status,
                     financial_status, cancelled, note, order_total, order_currency, imported_at) VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT (order_number) DO UPDATE SET shopify_order_id = excluded.shopify_order_id,
                     order_created_at = excluded.order_created_at,
                     fulfillment_status = excluded.fulfillment_status, financial_status = excluded.financial_status,
                     cancelled = excluded.cancelled, note = excluded.note, order_total = excluded.order_total,
                     order_currency = excluded.order_currency, imported_at = excluded.imported_at""",
                *vals,
                now,
            )
            n += 1
    return n


def notes() -> dict[str, dict]:
    ready()
    return {r["order_number"]: r for r in all_rows("SELECT * FROM shipping_notes")}


def set_note(order_number: str, text: str, user: str) -> None:
    ready()
    if not text.strip():
        run("DELETE FROM shipping_notes WHERE order_number = ?", order_number)
        return
    run(
        """INSERT INTO shipping_notes (order_number, note, updated_by, updated_at) VALUES (?,?,?,?)
           ON CONFLICT (order_number) DO UPDATE SET note = excluded.note, updated_by = excluded.updated_by,
             updated_at = excluded.updated_at""",
        order_number,
        text.strip()[:2000],
        user,
        _now(),
    )


# ---------------- store protocol used by sync.run_sync ----------------
class SqliteStore:
    """The three methods the original JSON/Supabase stores exposed: load(), save(records), record_run(run)."""

    def load(self) -> dict:
        return load_shipments()

    def save(self, records: list) -> None:
        save_shipments(records)

    def record_run(self, run_row: dict) -> None:
        record_run(run_row)

    def save_checks(self, records: list) -> None:
        upsert_order_checks(records)

    def load_checks(self) -> list:
        return order_checks()
