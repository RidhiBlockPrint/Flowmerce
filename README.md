# Flowmerce

A unified e-commerce platform to track, manage and act on what happens in the business.

Six planned modules on one shared foundation:

1. Meta & Google Ads
2. SEO & Blog Automation
3. Shipping Tracking & Alerts
4. Creative Strategist
5. Landing Page Builder
6. CRO (Conversion Rate Optimization)

## Current status (2026-10-29)

- **Implemented:** the Python engineering foundation (package, configuration loading, logging setup, CLI `version` / `health`, tests, documentation) and the **SEO & Blog module**, migrated from the standalone `blog-ops` app into `src/flowmerce/modules/seo` (FastAPI + SQLite) with its Next.js/React (JavaScript) UI in `frontend/`. See [ADR 0003](docs/decisions/0003-blog-ops-migration-plan.md).
- **Migration complete (2026-10-29):** the original `blog-ops/` folder was removed after its `.env`, `data/` and `backups/` were moved to the repository root and verified. The module has been smoke-tested but not exercised against live Shopify/Google/Claude credentials.
- **Dashboard (2026-10-29):** the application shell and Home / Morning Brief page are a **Next.js (App Router) + React frontend in JavaScript/JSX** in `frontend/`, calling the Python FastAPI backend through `/api/...`. Only working pages are visible: Home and the SEO & Blog pages (overview, brand workspace, blogs and article editor, topics, publishing, analytics, automation, data and reports, integrations, audit log). Unbuilt projects have no menu entries, no Home cards and no placeholder pages; their old addresses show a normal not-found page with a way back to Home. Home shows real records only. See [ADR 0006](docs/decisions/0006-nextjs-javascript-frontend.md) and the [roadmap](docs/development/roadmap.md).
- **Shipping module (2026-10-30):** delayed-order tracking for the Ridhi store, integrated from the delayed-order-tracker project into `src/flowmerce/modules/shipping` and `/shipping` in the UI (overview, shipments, analytics, checks). Data is stored in Flowmerce's SQLite database and the Shopify sync is read-only. See [ADR 0007](docs/decisions/0007-shipping-module-and-database.md).
- **Local operator mode (2026-10-29):** Flowmerce opens straight to the dashboard (no sign-in) and answers only this computer. See [ADR 0005](docs/decisions/0005-local-operator-mode.md).
- **Not built:** the other five modules, PostgreSQL, Celery/Redis and the shared approval engine (planning only).
- **Planning documents (v0.1):** `docs/01-architecture.md`, `docs/02-connectors-and-apis.md`, `docs/03-data-model.md`, `db/schema.sql`, `architecture-map.html`. These describe the target design, not what is built.

## Technology and approved languages

Python 3.12+ is the primary language (the legacy code was written for 3.10+). Exceptions approved by the owner on 2026-10-29 (see [ADR 0002](docs/decisions/0002-approved-language-exceptions.md) and [ADR 0006](docs/decisions/0006-nextjs-javascript-frontend.md)): the web UI is **Next.js + React in JavaScript/JSX only (no TypeScript)**, and plain `.sql` files are allowed for database schema only. Any other language needs explicit approval first.

## Prerequisites and setup

Python 3.12 or newer, and Node.js with npm (for the web interface). Full steps: [docs/development/setup.md](docs/development/setup.md). Short version (Windows PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,seo]"
copy .env.example .env
python -m flowmerce health
python scripts\run_flowmerce.py   # starts the API and the web interface, then opens http://127.0.0.1:3000
```

## Start Flowmerce (one command)

```powershell
python scripts\run_flowmerce.py
```

Flowmerce is two local services, started and stopped together by that command (`scripts\run_seo.py` still works and forwards to it; `scripts\run_seo.bat` is a double-click wrapper):

| Service | Address | What it is |
|---|---|---|
| API | `http://127.0.0.1:8787` | Python / FastAPI backend (SQLite database, integrations, publishing rules) |
| Web interface | `http://127.0.0.1:3000` | Next.js / React frontend; it forwards `/api/*` to the API |

The launcher creates `.venv`, installs the Python and `frontend/` packages when needed, builds the web interface when it is missing or out of date, opens the browser and stops both services on Ctrl+C. It reports a missing Node.js/npm, failed installs and busy ports. `--dev` runs the frontend in Next.js development mode; `--no-browser` skips opening the browser. Both services listen on `127.0.0.1` only, and the ports are fixed.

## Local operator mode: no sign-in, this computer only

Flowmerce is a local tool. Opening it on your own computer goes straight to the dashboard: there is no email, login ID, password or session, and everything you do is recorded as the local administrator record.

- **It answers only requests from this computer.** Any request from another computer (another machine on your network, or the internet) is refused with HTTP 403 before any page or API is served. The check uses the connecting address only; forwarded-address headers are ignored.
- **Both services bind to `127.0.0.1`** (the Next.js server is started with `-H 127.0.0.1`, the API's default `HOST`). **Never expose Flowmerce to a network or the internet**, and never put a reverse proxy or tunnel in front of it: there is no password to fall back on.
- **The one exception to the API's address check is the workflow webhook** `POST /api/hooks/workflow`, which agents outside this computer may call because it has its own `X-Workflow-Secret` check (set `WORKFLOW_WEBHOOK_SECRET` to enable it).
- Roles and passwords no longer restrict access. User records stay in the database (they are used for audit history and article assignments); the Users page lists them.
- Live publishing is still switched off unless `ALLOW_LIVE_PUBLISH` is set, and it still needs the `PUBLISH` confirmation.
- An old `data/initial-admin.txt` (git-ignored) is not deleted and is no longer used.

## Run tests and checks

```powershell
pytest
ruff check .
mypy
cd frontend; npm run build; cd ..
python scripts\ci_smoke.py --web
```

## Documentation

- [System overview](docs/architecture/system-overview.md)
- [Folder structure](docs/architecture/folder-structure.md)
- [File registry](docs/FILE_REGISTRY.md)
- [Setup](docs/development/setup.md) · [Coding standards](docs/development/coding-standards.md)
- [Troubleshooting](docs/operations/troubleshooting.md) · [CI/CD](docs/operations/ci-cd.md) (what CI checks and how to run it locally)
- [Project rules](PROJECT_RULES.md) (permanent engineering standards) · [Roadmap](docs/development/roadmap.md) (actual status and open decisions)
- [Architecture decisions](docs/decisions/)
- [Changelog](CHANGELOG.md)
- Target design (planning v0.1): [architecture](docs/01-architecture.md), [connectors](docs/02-connectors-and-apis.md), [data model](docs/03-data-model.md)
