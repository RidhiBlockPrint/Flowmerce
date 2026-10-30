"""Import existing Shipping data into the Flowmerce database (data/blog-ops.sqlite). Safe to re-run.

    python scripts/import_shipping_data.py --dry-run                      report only, writes nothing
    python scripts/import_shipping_data.py                                import data/shipments.json
    python scripts/import_shipping_data.py --file path/to/shipments.json
    python scripts/import_shipping_data.py --manual manual_status.csv --checks order_checks.csv
    python scripts/import_shipping_data.py --from-supabase [--dry-run]    live data, once SUPABASE_* is in .env

A real run first copies the database into backups/ and stops if the copy fails. Shipments are upserted on
(fulfillment_id, tracking_number), so running it twice creates no duplicates. Source files are never modified.
manual_status / order_checks exports (JSON array or CSV from Supabase) are optional."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Import Shipping data into Flowmerce.")
    ap.add_argument("--file", type=Path, help="shipments.json (default: data/shipments.json)")
    ap.add_argument("--manual", type=Path, help="manual_status export (.json or .csv)")
    ap.add_argument("--checks", type=Path, help="order_checks export (.json or .csv)")
    ap.add_argument(
        "--from-supabase",
        action="store_true",
        help="read shipments, sync runs, order checks and manual status from Supabase (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env)",
    )
    ap.add_argument(
        "--prune",
        action="store_true",
        help="with --from-supabase: also remove local shipments Supabase no longer has",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="report what would change; write nothing"
    )
    args = ap.parse_args()

    from flowmerce.modules.seo.db import open_db
    from flowmerce.modules.shipping import importer

    open_db()
    reports = []
    if args.from_supabase:
        reports.append(importer.import_from_supabase(args.dry_run, prune=args.prune))
        print(json.dumps(reports, indent=2, default=str))
        return 0 if reports[0].get("verified", True) else 1
    src = args.file or importer.default_shipments_file()
    if src and src.exists():
        reports.append(importer.import_shipments(src, args.dry_run))
    elif not (args.manual or args.checks):
        print(
            "No shipments file found. Put shipments.json in data/ or pass --file.", file=sys.stderr
        )
        return 1
    if args.manual:
        reports.append(importer.import_manual_status(args.manual, args.dry_run))
    if args.checks:
        reports.append(importer.import_order_checks(args.checks, args.dry_run))
    print(json.dumps(reports, indent=2, default=str))
    return 0 if all(r.get("verified", True) for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
