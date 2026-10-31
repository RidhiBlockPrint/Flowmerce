"""Shipping tables. Idempotent (CREATE ... IF NOT EXISTS) and versioned in shipping_meta, so it is independent of
the SEO migration counter and can be re-run safely. Column names match the original Supabase schema.sql, which keeps
a later move to Postgres/Supabase a one-to-one copy."""

from __future__ import annotations

from ..seo.db import all_rows, get, run

VERSION = 3

TABLES = """
CREATE TABLE IF NOT EXISTS shipping_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shipping_shipments (
  id INTEGER PRIMARY KEY,
  shopify_order_id TEXT NOT NULL,
  order_number TEXT NOT NULL,
  fulfillment_id TEXT NOT NULL,
  tracking_number TEXT NOT NULL DEFAULT '',
  carrier_name TEXT NOT NULL DEFAULT '',
  tracking_url TEXT NOT NULL DEFAULT '',
  order_created_at TEXT,
  fulfilled_at TEXT,
  expected_delivery_at TEXT,
  raw_tracking_status TEXT NOT NULL DEFAULT '',
  normalized_tracking_status TEXT NOT NULL DEFAULT '',
  exception TEXT NOT NULL DEFAULT '',
  last_scan_at TEXT,
  last_scan_description TEXT NOT NULL DEFAULT '',
  last_scan_location TEXT NOT NULL DEFAULT '',
  tracking_source TEXT NOT NULL DEFAULT 'shopify',
  last_checked_at TEXT,
  carrier_error TEXT NOT NULL DEFAULT '',
  delivered_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (fulfillment_id, tracking_number)
);
CREATE INDEX IF NOT EXISTS shipping_shipments_order_idx ON shipping_shipments (order_number);
CREATE INDEX IF NOT EXISTS shipping_shipments_status_idx ON shipping_shipments (normalized_tracking_status);
CREATE INDEX IF NOT EXISTS shipping_shipments_scan_idx ON shipping_shipments (last_scan_at);
CREATE TABLE IF NOT EXISTS shipping_sync_runs (
  id INTEGER PRIMARY KEY,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  sync_status TEXT NOT NULL,
  orders_processed INTEGER NOT NULL DEFAULT 0,
  shipments_created INTEGER NOT NULL DEFAULT 0,
  shipments_updated INTEGER NOT NULL DEFAULT 0,
  exceptions_count INTEGER NOT NULL DEFAULT 0,
  error_summary TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS shipping_manual_status (
  order_number TEXT NOT NULL,
  tracking_number TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK (status IN ('delivered','lost','failed','in_transit')),
  updated_by TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  PRIMARY KEY (order_number, tracking_number)
);
CREATE TABLE IF NOT EXISTS shipping_order_checks (
  order_number TEXT PRIMARY KEY,
  order_created_at TEXT,
  fulfillment_status TEXT NOT NULL DEFAULT '',
  financial_status TEXT NOT NULL DEFAULT '',
  cancelled INTEGER NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT '',
  order_total REAL,
  order_currency TEXT NOT NULL DEFAULT '',
  imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shipping_notes (
  order_number TEXT PRIMARY KEY,
  note TEXT NOT NULL,
  updated_by TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
)
"""


UPGRADES = {
    # version 2: order total / currency on each shipment (value at risk) and the Shopify id on order checks
    2: [
        ("shipping_shipments", "order_total", "REAL"),
        ("shipping_shipments", "order_currency", "TEXT NOT NULL DEFAULT ''"),
        ("shipping_order_checks", "shopify_order_id", "TEXT NOT NULL DEFAULT ''"),
    ],
    # version 3: when the order was archived (closed) in Shopify; archived orders count as delivered
    3: [("shipping_order_checks", "closed_at", "TEXT")],
}


def _columns(table: str) -> set[str]:
    return {r["name"] for r in all_rows(f"PRAGMA table_info({table})")}


def ensure_schema() -> None:
    for stmt in [s.strip() for s in TABLES.split(";") if s.strip()]:
        run(stmt)
    for version in sorted(UPGRADES):
        for table, column, ddl in UPGRADES[version]:
            if column not in _columns(table):
                run(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    run(
        "INSERT INTO shipping_meta (key, value) VALUES ('schema_version', ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        str(VERSION),
    )


def schema_version() -> int:
    row = get("SELECT value FROM shipping_meta WHERE key = 'schema_version'")
    return int(row["value"]) if row else 0


def table_counts() -> dict[str, int]:
    names = (
        "shipping_shipments",
        "shipping_sync_runs",
        "shipping_manual_status",
        "shipping_order_checks",
        "shipping_notes",
    )
    return {n: all_rows(f"SELECT COUNT(*) AS c FROM {n}")[0]["c"] for n in names}
