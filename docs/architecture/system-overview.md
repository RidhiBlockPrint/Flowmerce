# System overview

Status legend: **Implemented** = exists and is tested. **Legacy** = exists outside the new structure. **Planned** = documented design only.

## Implemented

- **Entry point:** `python -m flowmerce <command>` (or the `flowmerce` console script) in `src/flowmerce/main.py`. Commands: `version`, `health`.
- **Configuration:** `src/flowmerce/config/settings.py` reads `FLOWMERCE_ENV` and `FLOWMERCE_LOG_LEVEL` from the environment, validates them and returns an immutable `Settings`.
- **Logging:** `src/flowmerce/core/logging.py` configures one consistent format. Credentials and customer data must never be logged.
- **Data flow (foundation CLI):** environment variables -> `load_settings()` -> `main()` -> log + stdout. The SEO module separately uses SQLite (`data/blog-ops.sqlite`), Shopify, Google Search Console/GA4 and the Claude API.

## Implemented: two local services (Python API + Next.js frontend)

Flowmerce runs as two services on this computer, started together by `scripts/run_flowmerce.py` (ADR [0005](../decisions/0005-local-operator-mode.md), [0006](../decisions/0006-nextjs-javascript-frontend.md)):

| Service | Address | Role |
|---|---|---|
| Python API | `127.0.0.1:8787` | FastAPI backend (`modules/seo/app.py`): all business logic, SQLite, integrations, publishing safeguards. Returns JSON only; it no longer serves any frontend files. |
| Next.js frontend | `127.0.0.1:3000` | React UI in JavaScript/JSX (App Router). Renders the pages and forwards `/api/*` to the API through a Next.js rewrite (`frontend/next.config.mjs`). Holds no credentials and no business logic. |

The shell and Home / Morning Brief page live in `frontend/src`. Routes are folders in `frontend/src/app/` (`/`, `/seo`, `/workspace/[brand]`, `/blogs`, `/blogs/[id]`, `/topics`, `/publishing`, `/analytics`, `/automation`, `/data`, `/integrations`, `/audit`); `/login` redirects to Home; every other address gets the not-found page (`app/not-found.jsx`) with a link back to Home. **Only working features are visible:** the sidebar (`lib/routes.js`, `components/Shell.jsx`) lists Home and the SEO & Blog pages; there are no entries, Home cards or placeholder pages for unbuilt projects, and the demonstration-data mode of Home was removed. `views/Login.jsx`, `views/Planned.jsx` and `views/Users.jsx` are kept as source but are not mounted. The brand switcher (All, Ridhi, CPC) and date range are client state (`lib/app.jsx`). Home reads `GET /api/home` (`modules/seo/services/home.py`), which returns real records only, each metric with its source.

## Implemented: Shipping module (`flowmerce.modules.shipping`)

Delayed-order tracking for the Ridhi store (ADR [0007](../decisions/0007-shipping-module-and-database.md)). Layers: `repo.py` (the only storage code, SQLite today, Supabase later), `schema.py` (the five `shipping_*` tables), `aging.py` / `normalize.py` / `carriers.py` / `shopify.py` (ported from the tracker, with their tests), `sync.py` (Shopify -> normalize -> carrier check -> save; read-only), `service.py` (classification and every summary the pages need, ported from the original dashboard), `importer.py` (idempotent import with backup and verification) and `api.py` (`/api/shipping/...`, mounted by the SEO app behind the same guards). The UI is `/shipping` (overview), `/shipping/shipments`, `/shipping/analytics` and `/shipping/checks`, with a shipment drawer, quick views, server-side paging and CSV exports. Flow rules: not dispatched, the clock runs from the order date; dispatched, from the dispatch date; a scan never resets it; Amazon / unknown carriers are "carrier unconfirmed" until the team marks them.

## Implemented: local operator mode (request boundary and identity)

Decision: [ADR 0005](../decisions/0005-local-operator-mode.md). Flowmerce is a local tool, so there is no sign-in. Every API request passes the guard in `modules/seo/app.py` first (the Next.js server itself is bound to `127.0.0.1`, so it cannot be reached from the network; its proxied requests reach the API from loopback):
1. **Boundary.** Unless the connecting address is a loopback address (`auth.is_loopback_client`: 127.0.0.0/8, `::1`, IPv4-mapped loopback; a missing or unparsable address fails closed; forwarded-IP headers are never read), the response is HTTP 403 (`local_only`). This applies to every path the API serves, before anything is answered, and it still applies if the API's `HOST` is changed.
2. **Webhook exception.** `POST /api/hooks/workflow` (exact method and path) skips the boundary because it verifies its own `X-Workflow-Secret`. It also keeps its existing CSRF exemption. Nothing else is exempt.
3. **Identity.** A local API request acts as `auth.local_operator()`: the first active administrator record. That record supplies permissions, audit attribution and record ownership. `GET /api/auth/me` returns it with its permissions and `localOperator: true`; the UI loads it and opens the dashboard directly.
4. **Unchanged safeguards.** Ordinary mutating requests still need `X-Requested-With: blog-ops`; every endpoint still checks a permission; the audit log and the live-publishing safeguards (the `PUBLISH` confirmation, `ALLOW_LIVE_PUBLISH`, the stale-content check) are untouched.
5. **Retired.** `POST /api/auth/login` and `/api/auth/password` return 410 and verify or change nothing; `/api/auth/logout` is harmless. Startup creates an administrator record only if none is active, with a hash that can never verify. Existing users, password hashes and sessions are kept and unused.

Known limits: the protection is "being on this computer" (any local program acts as the administrator); a reverse proxy or tunnel on this computer would look local; and DNS rebinding is not covered. See the ADR and roadmap F14.

## Implemented: SEO & Blog module (`flowmerce.modules.seo`, migrated from blog-ops)

FastAPI + SQLite app for the blog pipeline of two Shopify stores (topic research, approval, drafting, Shopify drafts, gated publishing, Search Console/GA4 reporting). Entry points: `scripts/run_flowmerce.py` (launcher for both services) or `uvicorn flowmerce.modules.seo.main:app`. Structure: `api.py` (HTTP endpoints), `app.py` (app factory and request guard; API only), `services/` (business logic), `integrations/` (Shopify, Google, Claude clients and health status), `db.py` (SQLite schema and migrations), `auth.py` / `permissions.py` / `audit.py`. The Next.js/React (JavaScript) UI is in `frontend/`. Publishing is gated by approvals and the `ALLOW_LIVE_PUBLISH` switch (off by default); see the legacy README text in `docs/architecture/legacy-blog-ops-README.md`.

Known gaps: not typed/linted to project standards (excluded in `pyproject.toml`), integrations still depend on the seo module's config, uses SQLite rather than the planned PostgreSQL, and `config.py` has its own `.env` reader separate from `flowmerce.config`.

## Legacy copy

The original `blog-ops/` folder was removed on 2026-10-29 after `.env`, `data/` and `backups/` were moved to the repository root.

## Planned (not built)

The six-module platform with PostgreSQL, Celery + Redis, a shared approval engine and external integrations is described in `docs/01-architecture.md`, `docs/02-connectors-and-apis.md`, `docs/03-data-model.md` and `db/schema.sql`. Those documents are a v0.1 planning draft; where they differ from the ADRs in `docs/decisions/`, the ADRs win.

## Module boundaries and integration strategy

- Each business module lives in `src/flowmerce/modules/<name>/` and owns its code and tests.
- Each external platform should live in its own sub-package of `src/flowmerce/integrations/` (not created yet; the SEO module still holds its own clients in `modules/seo/integrations/`).
- Modules do not import each other's internals; shared concepts go in `shared/` only once two modules genuinely need them.
