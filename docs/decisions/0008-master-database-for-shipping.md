# ADR 0008: Master database for orders, items, shipments and events

- Status: approved (owner, 2026-10-31); implemented on branch `feature/shipping-module`
- Date: 2026-10-31

## Decision
1. **Source design.** The owner's "Ridhi Shopify Database" design (8 tables, 3 views) is the master database. For the Shipping module the owner chose five of its tables: **stores, orders, items, shipments, events**, with customer details included. `people`, `settings`, `stock` and the three views (`stock_free`, `alert_board`, `daily`) are not part of this step: Flowmerce has its own users and settings, there is no ERP connection for stock, and views are worked out in code.
2. **Same names, own file.** The tables keep the design's table and column names (`modules/shipping/master_spec.json`, extracted from the design) in their own SQLite file, `data/master.sqlite` (git-ignored, separate from the SEO database). `master_db.postgres_ddl()` writes the matching Postgres DDL (`db/master_shipping.sql`), so the planned move to Supabase is a copy.
3. **Who writes what.** The design gives every column a writer: Shopify, our team, a backend job, the ERP or the carrier. The Shopify sync (`modules/shipping/master_sync.py`, read-only) writes only the Shopify and carrier columns, never the "ours" or "system" ones (stage after it is set by people, hold, route, step, responsible, ...). Rules of the design are kept: a late, older Shopify message is ignored (`shop_updated_at`), and a repeated tracking event is refused (`events.external_id`).
4. **What is filled.** Orders with totals, status, tags, note and (as chosen) the customer's name, email, phone and shipping address; order lines with SKU, quantities (refunded and shipped worked out from Shopify's refunds and fulfillments), price and open quantity; one shipment per successful Shopify fulfillment with carrier, tracking numbers, ETA, delivered time, last scan and the route, and one `scan` event per Shopify tracking event. Shopify's full order is kept in `orders.raw`.
5. **Mappings that are ours, not Shopify's.** `shipments.kind`: Amazon Logistics = `mcf`, every other carrier = `india` (the design's DHL / FedEx / MCF split). `shipments.step` and `orders.stage` use the design's parcel steps (`shipped`, `transit`, `out`, `delivered`) worked out from Shopify's delivery status and the slowest shipment, and are only changed while they hold one of those values, so a step set by a person is left alone.
6. **What Shopify does not give this app.** Customer id (needs `read_customers`), product and variant ids (need `read_products`) and the risk level stay empty, and Shopify returns only orders from the last 60 days (`read_all_orders` would lift that). The sync keeps going without customer details if Shopify ever refuses them.

## Consequences
- The existing `shipping_*` tables and the order classification keep working unchanged; moving them onto the master tables is a later step.
- The first fill took about 3.5 minutes (3,367 orders, 5,651 items, 3,610 shipments, 49,908 events); the scheduler repeats it every 6 hours when Shopify credentials exist, and "Sync master data" on the Shipping overview runs it on demand.
- The database file holds customer personal data. It stays in `data/` (git-ignored) and is covered by the backups of that folder.
