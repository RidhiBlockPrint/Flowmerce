"""One-time / repeatable import of existing shipping data into the Flowmerce database.

Sources (all optional, all read-only):
  - data/shipments.json from the original tracker ({"shipments": [...], "sync_runs": [...]})
  - manual_status and order_checks exports from Supabase (JSON array or CSV) once the owner provides them

The import is idempotent (shipments upsert on fulfillment_id + tracking_number), a dry run reports what would
change without writing, a real run backs the database up first, and counts are verified afterwards. Source files
are never modified."""

from __future__ import annotations

import csv
import json
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from ..seo import db
from ..seo.config import config, env
from . import repo
from .repo import SHIPMENT_FIELDS, row_key
from .schema import table_counts

MANUAL_OK = ("delivered", "lost", "failed", "in_transit")


def _read_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("rows") or data.get("shipments") or []


def backup_database() -> Path:
    """Copy the live SQLite database into backups/ (refuses to continue if that fails)."""
    folder = config.root / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"blog-ops-before-shipping-import-{datetime.now():%Y%m%d-%H%M%S}.sqlite"
    dest = sqlite3.connect(target)
    try:
        with db._lock:
            db._db().backup(dest)
    finally:
        dest.close()
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError("Database backup failed; nothing was imported.")
    return target


def _shipment_rows(rows: list[dict]) -> tuple[list[dict], list[str]]:
    out: dict[str, dict] = {}
    problems: list[str] = []
    for i, r in enumerate(rows):
        if not r.get("fulfillment_id") or not r.get("order_number"):
            problems.append(f"row {i + 1}: missing fulfillment_id or order_number (skipped)")
            continue
        rec = {f: r.get(f) for f in SHIPMENT_FIELDS}
        rec["tracking_number"] = rec["tracking_number"] or ""
        out[row_key(rec)] = rec  # a duplicate key keeps the last row, like the original sync
    return list(out.values()), problems


def import_shipments(path: Path, dry_run: bool = False) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows, problems = _shipment_rows(data.get("shipments", []) if isinstance(data, dict) else data)
    runs = data.get("sync_runs", []) if isinstance(data, dict) else []
    repo.ready()
    existing = repo.load_shipments()
    new = sum(1 for r in rows if row_key(r) not in existing)
    report: dict[str, Any] = {
        "source": str(path),
        "dry_run": dry_run,
        "shipments_in_file": len(rows),
        "would_create": new,
        "would_update": len(rows) - new,
        "sync_runs_in_file": len(runs),
        "problems": problems,
    }
    if dry_run:
        return report
    report["backup"] = str(backup_database())
    before = table_counts()
    created, updated = repo.save_shipments(rows)
    known = {r["started_at"] for r in repo.list_runs(1000)}
    for r in runs:
        if r.get("started_at") and r["started_at"] not in known:
            repo.record_run(r)
    after = table_counts()
    stored = repo.load_shipments()
    missing = [k for k in (row_key(r) for r in rows) if k not in stored]
    report.update(
        {
            "created": created,
            "updated": updated,
            "counts_before": before,
            "counts_after": after,
            "verified": not missing and len(stored) >= len(rows),
            "missing_after_import": len(missing),
        }
    )
    return report


def import_manual_status(path: Path, dry_run: bool = False) -> dict:
    rows = _read_rows(path)
    good = [r for r in rows if r.get("order_number") and r.get("status") in MANUAL_OK]
    report: dict[str, Any] = {
        "source": str(path),
        "dry_run": dry_run,
        "rows_in_file": len(rows),
        "valid": len(good),
        "skipped": len(rows) - len(good),
    }
    if dry_run:
        return report
    report["backup"] = str(backup_database())
    for r in good:
        repo.set_manual_status(
            str(r["order_number"]),
            str(r.get("tracking_number") or ""),
            r["status"],
            str(r.get("updated_by") or "imported"),
        )
    report["imported"] = len(good)
    return report


def import_order_checks(path: Path, dry_run: bool = False) -> dict:
    rows = _read_rows(path)

    def num(v: Any) -> float | None:
        try:
            return float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None

    good = []
    for r in rows:
        if not r.get("order_number"):
            continue
        cancelled = str(r.get("cancelled", "")).strip().lower() in ("1", "true", "t", "yes")
        good.append({**r, "cancelled": cancelled, "order_total": num(r.get("order_total"))})
    report: dict[str, Any] = {
        "source": str(path),
        "dry_run": dry_run,
        "rows_in_file": len(rows),
        "valid": len(good),
    }
    if dry_run:
        return report
    report["backup"] = str(backup_database())
    report["imported"] = repo.upsert_order_checks(good)
    return report


def default_shipments_file() -> Path | None:
    for p in (config.data_dir / "shipments.json", config.root / "data" / "shipments.json"):
        if p.exists():
            return p
    return None


def _supabase_get(base: str, key: str, table: str, order: str, opener=None) -> list[dict]:
    """Read every row of one Supabase table (GET only, paged by 1000). The key is sent as a header and never printed."""
    open_url = opener or urllib.request.urlopen
    headers = {"apikey": key}
    if not key.startswith(
        "sb_"
    ):  # legacy JWT keys also need Bearer; new sb_ keys go in apikey only
        headers["Authorization"] = f"Bearer {key}"
    out: list[dict] = []
    offset = 0
    while True:
        url = (
            f"{base.rstrip('/')}/rest/v1/{table}?select=*&order={order}&limit=1000&offset={offset}"
        )
        try:
            with open_url(urllib.request.Request(url, headers=headers), timeout=30) as resp:
                rows = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Supabase read of {table} failed: HTTP {exc.code}") from exc
        out.extend(rows)
        if len(rows) < 1000:
            return out
        offset += 1000


def import_from_supabase(dry_run: bool = False, opener=None, prune: bool = False) -> dict:
    """Copy the live tracker data (shipments, sync runs, order checks, manual status) from Supabase into Flowmerce.
    Needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env. Read-only against Supabase; idempotent here.
    prune=True also removes local shipments that Supabase no longer has (after the backup), so Flowmerce mirrors it."""
    url, key = env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and key):
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are not set in .env.")
    shipments = _supabase_get(url, key, "shipments", "id.asc", opener)
    runs = _supabase_get(url, key, "sync_runs", "started_at.asc", opener)
    checks = _supabase_get(url, key, "order_checks", "order_number.asc", opener)
    manual = _supabase_get(url, key, "manual_status", "order_number.asc", opener)
    rows, problems = _shipment_rows(shipments)
    repo.ready()
    existing = repo.load_shipments()
    new = sum(1 for r in rows if row_key(r) not in existing)
    good_manual = [m for m in manual if m.get("order_number") and m.get("status") in MANUAL_OK]
    report: dict[str, Any] = {
        "source": "supabase",
        "dry_run": dry_run,
        "shipments": len(rows),
        "would_create": new,
        "would_update": len(rows) - new,
        "sync_runs": len(runs),
        "order_checks": len(checks),
        "manual_status": len(good_manual),
        "problems": problems,
        "stale_local_rows": sum(1 for k in existing if k not in {row_key(r) for r in rows}),
    }
    if dry_run:
        return report
    report["backup"] = str(backup_database())
    before = table_counts()
    created, updated = repo.save_shipments(rows)
    known = {r["started_at"] for r in repo.list_runs(1000)}
    for r in runs:
        if r.get("started_at") and r["started_at"] not in known:
            repo.record_run(r)
    repo.upsert_order_checks(
        [{**c, "cancelled": bool(c.get("cancelled"))} for c in checks if c.get("order_number")]
    )
    for m in good_manual:
        repo.set_manual_status(
            str(m["order_number"]),
            str(m.get("tracking_number") or ""),
            m["status"],
            str(m.get("updated_by") or "imported"),
        )
    if prune:
        report["pruned"] = repo.delete_shipments_not_in({row_key(r) for r in rows})
    stored = repo.load_shipments()
    missing = [k for k in (row_key(r) for r in rows) if k not in stored]
    report.update(
        {
            "created": created,
            "updated": updated,
            "counts_before": before,
            "counts_after": table_counts(),
            "verified": not missing,
            "missing_after_import": len(missing),
        }
    )
    return report
