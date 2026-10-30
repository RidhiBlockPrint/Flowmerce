# ADR 0007: Shipping module and its database

- Status: approved (owner, 2026-10-30); implemented on branch `feature/shipping-module`
- Date: 2026-10-30

## Decision
1. **Shipping is a separate module** (`src/flowmerce/modules/shipping/`) mounted in the same FastAPI app at `/api/shipping/...`, so it inherits the loopback guard, CSRF header, local operator identity, audit log and permission checks. Its UI is under `/shipping/...` in the Next.js frontend, in Flowmerce's own components (no Chart.js, no new dependencies).
2. **Database: merged into Flowmerce's SQLite file** (`data/blog-ops.sqlite`) as five new, prefixed tables: `shipping_shipments`, `shipping_sync_runs`, `shipping_manual_status`, `shipping_order_checks`, `shipping_notes` (plus `shipping_meta` for the schema version). The SEO tables and the SEO migration counter are untouched: the shipping tables are created by `shipping/schema.py` with `CREATE ... IF NOT EXISTS` and versioned separately. Column names and unique keys match the original Supabase `schema.sql`.
3. **One storage file.** `shipping/repo.py` is the only code that reads or writes shipping data. The owner plans to move storage to **Supabase** later; that change is a rewrite of `repo.py` (plus a data upload), not of the module.
4. **Import, not migration of the source.** `scripts/import_shipping_data.py` loads `data/shipments.json` (3,524 shipments, 5 sync runs) idempotently, supports `--dry-run`, backs the database up into `backups/` first and verifies the counts. It also accepts `manual_status` and `order_checks` exports (JSON or CSV) once the owner provides them: those two tables exist only in Supabase, not in the delivered project. The source files are never modified.
5. **Read-only Shopify.** The sync uses the Dev Dashboard client credentials (scopes `read_orders`, `read_fulfillments`) and never creates, changes or cancels anything in Shopify. Without credentials a sync records a failed run and calls nothing.
6. **Behaviour is preserved.** Aging rules, stuck / exception flags, the Amazon-unknown "team check", the "Notes say DONE" list and the CSV lists were ported from the original dashboard into Python (`service.py`) so the numbers match, and the original `aging`, `normalize`, `carriers` and `shopify` modules and their tests were carried over unchanged. Team notes moved from the browser's local storage to the database (`shipping_notes`).
7. **Removed on purpose:** the Supabase email/password login (local operator mode replaces it), the GitHub Actions daily trigger (Flowmerce's own scheduler runs the sync when credentials are set), and the Chart.js CDN dependency.

## Alternatives considered
- Keep Supabase now: rejected for the build phase (owner: build locally first); the repository layer keeps this option cheap.
- A separate `shipping.sqlite`: simpler isolation, but a second file to back up and no cross-module reads; the tables are independent anyway.
- Fold shipments into a shared "orders" table: rejected; the SEO module has no orders and a shared model is the open decision B1.

## Advantages and risks
- One database, one backup, one start command; the SEO schema is unchanged.
- Risk: **the saved shipments are a snapshot** (last sync 2026-10-17), so every shipment older than nine days shows as critical until a sync runs. Needs the Shopify scopes and credentials.
- Risk: the ported code is not yet typed or line-length clean (ruff and mypy exceptions in `pyproject.toml`, roadmap debt).
- No carrier adapter is live: scan-based flags only use scans Shopify provides (DHL events).
