"""The master database for orders, order lines, shipments and their event timeline.

It follows the owner's "Ridhi Shopify Database" design (master_spec.json, five of its tables: stores, orders, items,
shipments, events) with the same table and column names, so the move to Supabase later is a copy: postgres_ddl() writes
the matching Postgres DDL. It lives in its own SQLite file (data/master.sqlite), separate from the SEO database.

Column ownership comes from the design: "shopify" columns are written only by the Shopify sync, "ours" columns only by
people through the app, "system" by backend jobs. The sync therefore never overwrites an "ours" or "system" column
(stage, hold, route, step, responsible ...); it fills what Shopify actually provides and leaves the rest empty."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from ..seo.config import config

SPEC_FILE = Path(__file__).with_name("master_spec.json")
_conn: sqlite3.Connection | None = None
_lock = threading.RLock()


def spec() -> list[dict]:
    return json.loads(SPEC_FILE.read_text(encoding="utf-8"))["tables"]


def table_spec(name: str) -> dict:
    return next(t for t in spec() if t["name"] == name)


def writer_columns(table: str, writer: str) -> list[str]:
    return [c["n"] for c in table_spec(table)["cols"] if c["w"] == writer]


# ---------------- SQLite ----------------
_SQLITE_TYPE = {
    "uuid": "TEXT",
    "text": "TEXT",
    "text[]": "TEXT",
    "jsonb": "TEXT",
    "timestamptz": "TEXT",
    "date": "TEXT",
    "boolean": "INTEGER",
    "int": "INTEGER",
    "bigint": "INTEGER",
    "bigserial": "INTEGER",
}


def _sqlite_type(t: str) -> str:
    return "REAL" if t.startswith("numeric") else _SQLITE_TYPE[t]


def _sqlite_default(t: str, default: str) -> str | None:
    if not default or default in ("gen_random_uuid()",):
        return None
    if default == "now()":
        return "(strftime('%Y-%m-%dT%H:%M:%SZ','now'))"
    if default in ("true", "false"):
        return "1" if default == "true" else "0"
    if t.endswith("[]"):
        inner = default.strip("'").strip("{}")
        return "'" + json.dumps([x for x in inner.split(",") if x]) + "'"
    if t == "jsonb":
        return "'{}'"
    return default


def sqlite_ddl() -> list[str]:
    out = []
    for t in spec():
        cols, constraints = [], []
        for c in t["cols"]:
            ty = _sqlite_type(c["t"])
            parts = [f'"{c["n"]}"', ty]
            if c["pk"]:
                parts.append(
                    "PRIMARY KEY AUTOINCREMENT" if c["t"] == "bigserial" else "PRIMARY KEY"
                )
            elif c["nn"]:
                parts.append("NOT NULL")
            d = _sqlite_default(c["t"], c["def"])
            if d is not None:
                parts.append(f"DEFAULT {d}")
            cols.append(" ".join(parts))
            if c["u"] and not c["pk"]:
                constraints.append(f'UNIQUE ("{c["n"]}")')
            if c["fk"] and not c["fk"].startswith("auth."):
                ref_table, ref_col = c["fk"].split(".")
                constraints.append(
                    f'FOREIGN KEY ("{c["n"]}") REFERENCES "{ref_table}" ("{ref_col}")'
                )
        if t["name"] == "shipments":
            constraints.append('UNIQUE ("order_id", "seq")')
        out.append(
            f'CREATE TABLE IF NOT EXISTS "{t["name"]}" (\n  '
            + ",\n  ".join(cols + constraints)
            + "\n)"
        )
    out.append('CREATE INDEX IF NOT EXISTS orders_store_placed ON "orders" ("store", "placed_at")')
    out.append('CREATE INDEX IF NOT EXISTS items_order ON "items" ("order_id")')
    out.append('CREATE INDEX IF NOT EXISTS shipments_order ON "shipments" ("order_id")')
    out.append('CREATE INDEX IF NOT EXISTS events_order ON "events" ("order_id", "at")')
    out.append(
        'CREATE UNIQUE INDEX IF NOT EXISTS events_external ON "events" ("external_id") WHERE "external_id" IS NOT NULL'
    )
    out.append(
        "CREATE TABLE IF NOT EXISTS master_sync_log (id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, "
        "status TEXT NOT NULL, orders INTEGER DEFAULT 0, items INTEGER DEFAULT 0, shipments INTEGER DEFAULT 0, "
        "events INTEGER DEFAULT 0, customer_data INTEGER DEFAULT 0, error TEXT DEFAULT '')"
    )
    return out


def postgres_ddl() -> str:
    """The same tables as Postgres / Supabase DDL (types exactly as in the design)."""
    lines = [
        "-- Master database for orders, items, shipments and events (generated from master_spec.json).",
        "",
    ]
    for t in spec():
        cols = []
        for c in t["cols"]:
            parts = [f'  "{c["n"]}"', c["t"]]
            if c["pk"]:
                parts.append("primary key")
            elif c["nn"]:
                parts.append("not null")
            if c["def"]:
                parts.append(f"default {c['def']}")
            if c["u"] and not c["pk"]:
                parts.append("unique")
            if c["fk"] and not c["fk"].startswith("auth."):
                rt, rc = c["fk"].split(".")
                parts.append(f'references "{rt}" ("{rc}")')
            cols.append(" ".join(parts))
        if t["name"] == "shipments":
            cols.append('  unique ("order_id", "seq")')
        lines.append(f'create table if not exists "{t["name"]}" (\n' + ",\n".join(cols) + "\n);")
        lines.append(
            f"comment on table \"{t['name']}\" is '{t['desc'].replace(chr(39), chr(39) * 2)}';"
        )
        lines.append("")
    lines.append(
        'create unique index if not exists events_external on "events" ("external_id") where "external_id" is not null;'
    )
    return "\n".join(lines) + "\n"


def open_master(file: str | None = None) -> sqlite3.Connection:
    global _conn
    target = file or str(config.data_dir / "master.sqlite")
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(target, check_same_thread=False, isolation_level=None)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode = WAL")
    _conn.execute("PRAGMA foreign_keys = ON")
    _conn.execute("PRAGMA busy_timeout = 5000")
    for stmt in sqlite_ddl():
        _conn.execute(stmt)
    return _conn


def conn() -> sqlite3.Connection:
    if _conn is None:
        open_master()
    if _conn is None:  # open_master() always sets it
        raise RuntimeError("The master database is not open.")
    return _conn


def all_rows(sql: str, *params: Any) -> list[dict]:
    with _lock:
        return [dict(r) for r in conn().execute(sql, params).fetchall()]


def get(sql: str, *params: Any) -> dict | None:
    with _lock:
        r = conn().execute(sql, params).fetchone()
        return dict(r) if r else None


def run(sql: str, *params: Any) -> sqlite3.Cursor:
    with _lock:
        return conn().execute(sql, params)


def transaction():
    """Context manager: one transaction on the master database."""
    from contextlib import contextmanager

    @contextmanager
    def _tx():
        with _lock:
            c = conn()
            c.execute("BEGIN")
            try:
                yield c
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise

    return _tx()


def counts() -> dict[str, int]:
    return {t["name"]: all_rows(f'SELECT COUNT(*) AS c FROM "{t["name"]}"')[0]["c"] for t in spec()}
