"""Shipping module: delayed-order tracking for the Ridhi store (integrated from the delayed-order-tracker project).

Reads Shopify orders and fulfilments (read-only), works out how overdue each shipment is, and shows it in the
Flowmerce dashboard. Storage is SQLite today (repo.py is the only file that touches the database, so a later move
to Supabase changes one file). Depends on the SEO module only for shared plumbing (db, auth, audit, config)."""
