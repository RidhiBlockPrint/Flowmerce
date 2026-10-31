"""The planned master database schema (stores, orders, items, shipments, events) from the owner's design.
Only the schema: nothing in the app fills these tables."""

import pytest

from flowmerce.modules.shipping import master_db as mdb


@pytest.fixture(autouse=True)
def master():
    mdb.open_master(":memory:")  # never the real data/master.sqlite
    yield


def test_schema_has_the_five_tables_with_the_designed_columns():
    cols = {t["name"]: {c["n"] for c in t["cols"]} for t in mdb.spec()}
    assert set(cols) == {"stores", "orders", "items", "shipments", "events"}
    assert {
        "id",
        "name",
        "placed_at",
        "financial_status",
        "stage",
        "hold_reason",
        "raw",
        "email",
        "ship_city",
    } <= cols["orders"]
    assert {"sku", "open_qty", "route", "ppc_route"} <= cols["items"]
    assert {
        "tracking",
        "carrier",
        "step",
        "delivered_at",
        "last_scan_text",
        "gst_invoice_no",
    } <= cols["shipments"]
    assert {"external_id", "alert_kind", "assigned_to"} <= cols["events"]
    for t, expected in cols.items():
        assert {r["name"] for r in mdb.all_rows(f'PRAGMA table_info("{t}")')} == expected
    assert (
        len(cols["stores"]),
        len(cols["orders"]),
        len(cols["items"]),
        len(cols["shipments"]),
        len(cols["events"]),
    ) == (6, 47, 25, 38, 24)


def test_the_tables_start_empty_and_enforce_the_designs_keys():
    assert mdb.counts() == {"stores": 0, "orders": 0, "items": 0, "shipments": 0, "events": 0}
    mdb.run(
        'INSERT INTO "stores" ("id", "name", "shopify_domain") VALUES (?,?,?)',
        "RBP",
        "Ridhi Block Print",
        "x.myshopify.com",
    )
    with pytest.raises(Exception):  # noqa: B017 - an order must belong to a known store
        mdb.run(
            'INSERT INTO "orders" ("id", "store", "name", "placed_at", "shop_updated_at") VALUES (1, \'XXX\', \'#1\', \'t\', \'t\')'
        )
    mdb.run(
        'INSERT INTO "orders" ("id", "store", "name", "placed_at", "shop_updated_at") VALUES (1, \'RBP\', \'#1\', \'t\', \'t\')'
    )
    with pytest.raises(Exception):  # noqa: B017 - a repeated tracking event is refused
        for _ in range(2):
            mdb.run(
                'INSERT INTO "events" ("store", "type", "by", "title", "external_id") VALUES (\'RBP\', \'scan\', \'dhl\', \'x\', \'e1\')'
            )


def test_postgres_ddl_for_the_later_supabase_move():
    ddl = mdb.postgres_ddl()
    for t in ("stores", "orders", "items", "shipments", "events"):
        assert f'create table if not exists "{t}"' in ddl
    assert "text[]" in ddl and "jsonb" in ddl and "uuid" in ddl and "timestamptz" in ddl
    assert (
        open(mdb.SPEC_FILE.parents[4] / "db" / "master_shipping.sql", encoding="utf-8").read()
        == ddl
    )  # the committed file is current
