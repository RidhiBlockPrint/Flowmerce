# ADR 0008: Master database schema (stores, orders, items, shipments, events)

- Status: approved (owner, 2026-10-31); schema only
- Date: 2026-10-31

## Decision
1. **Source design.** The owner's "Ridhi Shopify Database" design (8 tables, 3 views) is the planned master database. For the Shipping module the owner chose five of its tables: **stores, orders, items, shipments, events** (customer columns included).
2. **Schema only.** This step adds the **schema** and nothing else. The tables are created empty in their own SQLite file, `data/master.sqlite` (git-ignored, separate from the SEO database), at startup. **Nothing fills them**: there is no sync, no import, no scheduled job and no page for them. Filling them (from Shopify, the ERP or the carriers) is a separate decision.
3. **Same names.** The tables keep the design's table and column names (`modules/shipping/master_spec.json`, extracted from the design). `master_db.postgres_ddl()` writes the matching Postgres DDL, committed as `db/master_shipping.sql`, so the planned move to Supabase is a copy.
4. **Not included now.** `people`, `settings`, `stock` and the three views (`stock_free`, `alert_board`, `daily`): Flowmerce has its own users and settings, there is no ERP connection for stock, and views are worked out in code.

## Consequences
- The existing `shipping_*` tables and the order classification are unchanged.
- A first attempt also copied Shopify data into these tables (3,367 orders with customer details), added a sync button and a background job. The owner only wanted the schema, so all of that was removed; the filled file was moved to `backups/` (not deleted) and `data/master.sqlite` is a fresh empty schema.
