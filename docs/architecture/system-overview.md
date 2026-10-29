# System overview

Status legend: **Implemented** = exists and is tested. **Legacy** = exists outside the new structure. **Planned** = documented design only.

## Implemented

- **Entry point:** `python -m flowmerce <command>` (or the `flowmerce` console script) in `src/flowmerce/main.py`. Commands: `version`, `health`.
- **Configuration:** `src/flowmerce/config/settings.py` reads `FLOWMERCE_ENV` and `FLOWMERCE_LOG_LEVEL` from the environment, validates them and returns an immutable `Settings`.
- **Logging:** `src/flowmerce/core/logging.py` configures one consistent format. Credentials and customer data must never be logged.
- **Data flow (foundation CLI):** environment variables -> `load_settings()` -> `main()` -> log + stdout. The SEO module separately uses SQLite (`data/blog-ops.sqlite`), Shopify, Google Search Console/GA4 and the Claude API.

## Implemented: shared application shell and Home dashboard (`frontend/`)

The React/Vite UI is served by the SEO module's FastAPI app (`modules/seo/app.py` returns `index.html` for every non-API path) and sits behind that module's sign-in. Navigation, routes and status come from one registry, `frontend/web/src/lib/routes.ts`: the six projects in handoff order, six shared pages and the future-scope Merchandising page. Only the SEO & Blog area is built; every other destination renders `pages/Planned.tsx`, which states that it does not exist yet and offers no controls. The brand switcher (All, Ridhi, CPC) is browser state, as before. `pages/Home.tsx` (Morning Brief) reads `lib/home.ts`. With demo mode off (the default) it requests `GET /api/home`, a read-only endpoint in the SEO app (`modules/seo/api.py`, shaped by `services/home.py`): metrics from Search Console and GA4 for a fixed 28-day window ending 3 days ago, each with its source; approvals (review, publish authorization, topic decisions) filtered for the signed-in role with the same logic as `/api/tasks`; alerts from the existing alert logic; recent pipeline runs; and the syncs that have actually been attempted. Dated reports do not exist, so that list is always empty with an explanation. Synthetic demo fixtures that may sit in the analytics tables are withheld and flagged, never reported as metrics. With demo mode on, the page shows a small synthetic SEO-only sample and makes no request; real and sample data are never mixed. Only the SEO & Blog project contributes data; the other projects appear as Planned. The shell requests `/publishing` only on SEO pages and `/tasks` only on SEO pages and Home. The SEO pages keep their original addresses and the shell shows their date picker and search only on those pages.

## Implemented: SEO & Blog module (`flowmerce.modules.seo`, migrated from blog-ops)

FastAPI + SQLite app for the blog pipeline of two Shopify stores (topic research, approval, drafting, Shopify drafts, gated publishing, Search Console/GA4 reporting). Entry points: `scripts/run_seo.py` (launcher) or `uvicorn flowmerce.modules.seo.main:app`. Structure: `api.py` (HTTP endpoints), `app.py` (app factory, serves the UI from `frontend/web/dist`), `services/` (business logic), `integrations/` (Shopify, Google, Claude clients and health status), `db.py` (SQLite schema and migrations), `auth.py` / `permissions.py` / `audit.py`. The React/TypeScript UI is in `frontend/`. Publishing is gated by approvals and the `ALLOW_LIVE_PUBLISH` switch (off by default); see the legacy README text in `docs/architecture/legacy-blog-ops-README.md`.

Known gaps: not typed/linted to project standards (excluded in `pyproject.toml`), integrations still depend on the seo module's config, uses SQLite rather than the planned PostgreSQL, and `config.py` has its own `.env` reader separate from `flowmerce.config`.

## Legacy copy

The original `blog-ops/` folder was removed on 2026-10-29 after `.env`, `data/` and `backups/` were moved to the repository root.

## Planned (not built)

The six-module platform with PostgreSQL, Celery + Redis, a shared approval engine and external integrations is described in `docs/01-architecture.md`, `docs/02-connectors-and-apis.md`, `docs/03-data-model.md` and `db/schema.sql`. Those documents are a v0.1 planning draft; where they differ from the ADRs in `docs/decisions/`, the ADRs win.

## Module boundaries and integration strategy

- Each business module lives in `src/flowmerce/modules/<name>/` and owns its code and tests.
- Each external platform should live in its own sub-package of `src/flowmerce/integrations/` (not created yet; the SEO module still holds its own clients in `modules/seo/integrations/`).
- Modules do not import each other's internals; shared concepts go in `shared/` only once two modules genuinely need them.
