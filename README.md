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

- **Implemented:** the Python engineering foundation (package, configuration loading, logging setup, CLI `version` / `health`, tests, documentation) and the **SEO & Blog module**, migrated from the standalone `blog-ops` app into `src/flowmerce/modules/seo` (FastAPI + SQLite) with its React/TypeScript UI in `frontend/`. See [ADR 0003](docs/decisions/0003-blog-ops-migration-plan.md).
- **Migration complete (2026-10-29):** the original `blog-ops/` folder was removed after its `.env`, `data/` and `backups/` were moved to the repository root and verified. The module has been smoke-tested but not exercised against live Shopify/Google/Claude credentials.
- **Not built:** the other five modules, PostgreSQL, Celery/Redis and the shared approval engine (planning only).
- **Planning documents (v0.1):** `docs/01-architecture.md`, `docs/02-connectors-and-apis.md`, `docs/03-data-model.md`, `db/schema.sql`, `architecture-map.html`. These describe the target design, not what is built.

## Technology and approved languages

Python 3.12+ is the primary language (the legacy code was written for 3.10+). Exceptions approved by the owner on 2026-10-29 (see [ADR 0002](docs/decisions/0002-approved-language-exceptions.md)): TypeScript/JavaScript for the web UI only, and plain `.sql` files for database schema only. Any other language needs explicit approval first.

## Prerequisites and setup

Python 3.12 or newer. Full steps: [docs/development/setup.md](docs/development/setup.md). Short version (Windows PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,seo]"
copy .env.example .env
python -m flowmerce health
python scripts\run_seo.py      # starts the SEO / Blog Ops dashboard on http://localhost:8787
```

## Run tests and checks

```powershell
pytest
ruff check .
mypy
```

## Documentation

- [System overview](docs/architecture/system-overview.md)
- [Folder structure](docs/architecture/folder-structure.md)
- [File registry](docs/FILE_REGISTRY.md)
- [Setup](docs/development/setup.md) · [Coding standards](docs/development/coding-standards.md)
- [Troubleshooting](docs/operations/troubleshooting.md)
- [Architecture decisions](docs/decisions/)
- [Changelog](CHANGELOG.md)
- Target design (planning v0.1): [architecture](docs/01-architecture.md), [connectors](docs/02-connectors-and-apis.md), [data model](docs/03-data-model.md)
