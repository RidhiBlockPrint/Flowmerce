# File registry

Source and significant configuration files of the new foundation. The migrated SEO module is listed by group; it was moved with only path/import edits and was not reviewed line by line.

| File path | Responsibility | Main components | Dependencies | Dependents | Tests | Status | Notes |
|---|---|---|---|---|---|---|---|
| `pyproject.toml` | Packaging, dependencies, tool config | project metadata, `seo` extra, ruff/mypy/pytest settings (legacy exclusions) | setuptools | all | n/a | Active | Version lives here and in `src/flowmerce/__init__.py`; keep both in sync. |
| `.gitignore` | Excludes secrets, data, logs, caches | n/a | n/a | git | n/a | Active | Also excludes `data/`, `frontend/node_modules/` and the original `blog-ops` secrets/data. |
| `.env.example` | Documents environment variables | `FLOWMERCE_*` plus the SEO module variables | n/a | operators | n/a | Active | Keep in sync with `settings.py`. No real values. |
| `src/flowmerce/__init__.py` | Package marker and version | `__version__` | none | `main.py` | `tests/unit/test_main.py` | Active | |
| `src/flowmerce/__main__.py` | Enables `python -m flowmerce` | calls `main()` | `main.py` | operators | `tests/integration/test_cli_process.py` | Active | |
| `src/flowmerce/main.py` | CLI entry point | `build_parser`, `main` | config, core.logging | console script `flowmerce` | `tests/unit/test_main.py`, integration test | Active | Exit codes: 0 ok, 2 bad config. |
| `src/flowmerce/config/__init__.py` | Public config API | re-exports | `settings.py` | `main.py` | via settings tests | Active | |
| `src/flowmerce/config/settings.py` | Load and validate settings from environment | `Settings`, `ConfigError`, `load_settings` | stdlib | `main.py` | `tests/conftest.py` | Registers `tests/fixtures/seo.py` as a pytest plugin | `pytest_plugins` | pytest | all tests | n/a | Active | The fixture's network block is skipped if the `seo` extra (httpx) is not installed. |
| `tests/unit/test_settings.py` | Active | Add new variables here, in `.env.example` and in setup.md. |
| `src/flowmerce/core/logging.py` | Logging format/setup | `configure_logging`, `LOG_FORMAT` | stdlib | `main.py` | exercised by `health` tests | Active | No direct unit test yet. |
| `src/flowmerce/modules/__init__.py` | Home for business modules | docstring only | none | none | n/a | Active | No module implemented yet. |
| `tests/unit/test_settings.py` | Settings tests | 4 tests | pytest | n/a | n/a | Active | |
| `tests/unit/test_main.py` | CLI unit tests | 3 tests | pytest | n/a | n/a | Active | |
| `tests/integration/test_cli_process.py` | CLI as a real process | 1 test | pytest, subprocess | n/a | n/a | Active | Requires package installed (`pip install -e .`). |
| `README.md`, `CHANGELOG.md` | Overview, history | n/a | n/a | developers | n/a | Active | |
| `docs/**` | Documentation (this set plus ADRs 0001-0003; `architecture/legacy-blog-ops-README.md` is the archived original blog-ops README) | n/a | n/a | developers | n/a | Active | |
| `docs/01-architecture.md`, `02-connectors-and-apis.md`, `03-data-model.md` | Planning v0.1 design | n/a | n/a | developers | n/a | Planned design | Pre-existing; describes target, not current build. |
| `docs/architecture/planning-v0.1-readme.md` | Verbatim copy of the pre-existing root README (planning v0.1) | n/a | n/a | none | n/a | Archived | Says "nothing is built" and lists Next.js; superseded by README.md and ADRs. |
| `db/schema.sql` | Planned PostgreSQL schema | n/a | PostgreSQL 16 | none yet | none | Planned | Pre-existing. SQL approved for schema only (ADR 0002). |
| `architecture-map.html` | Interactive architecture map | n/a | n/a | none | none | Planned design | Pre-existing; contains browser script, not inspected. |
| `src/flowmerce/modules/seo/api.py` | All HTTP endpoints, each guarded by a permission check | FastAPI `api` router | auth, db, services, integrations, permissions, util | `app.py` | `tests/integration/seo/test_http.py` | Active (legacy code) | Largest file (~43 KB); candidate for splitting by feature. |
| `src/flowmerce/modules/seo/app.py` | App factory, startup, serves `frontend/web/dist` | `create_app`, `startup` | api, auth, db, services | `main.py`, `scripts/run_seo.py` | `tests/integration/seo/test_http.py` | Active (legacy code) | `DIST` path points at `frontend/web/dist`. |
| `src/flowmerce/modules/seo/main.py` | ASGI entry (`uvicorn flowmerce.modules.seo.main:app`) | `app` | `app.py` | launcher | n/a | Active | |
| `src/flowmerce/modules/seo/config.py` | Settings from environment / `.env`; brand definitions | `config`, `BrandConfig`, `env`, `flag` | stdlib | nearly all seo files | via other tests | Active (legacy code) | `ROOT` = repository root (`FLOWMERCE_ROOT` overrides). Separate from `flowmerce.config`; merge is a follow-up. |
| `src/flowmerce/modules/seo/db.py` | SQLite schema, migrations, query helpers | `open_db`, `get`, `all_rows`, `run`, `tx`, `MIGRATIONS` | config | api, services, auth, audit | `tests/fixtures/seo.py` | Active (legacy code) | Add schema changes as new `MIGRATIONS` entries; never edit old ones. |
| `src/flowmerce/modules/seo/auth.py`, `src/flowmerce/modules/seo/permissions.py`, `src/flowmerce/modules/seo/audit.py` | Sessions and password hashing; role permissions; audit log | `hash_password`, `can`, `audit` | config, db, util | api, app, services | `tests/unit/seo/test_core.py` | Active (legacy code) | |
| `src/flowmerce/modules/seo/util.py`, `src/flowmerce/modules/seo/cli.py` | Shared helpers and `HttpError`; create/reset a user from a terminal | `HttpError`, `slugify`, `norm_keyword` | stdlib | seo files | `tests/unit/seo/test_core.py` | Active (legacy code) | CLI: `python -m flowmerce.modules.seo.cli`. |
| `src/flowmerce/modules/seo/services/*.py` | Business logic: articles, brands, publishing, workflow, sync, analytics, excel import/export, demo data, runs, scheduler | one module each | db, integrations, audit, util | api | `tests/unit/seo/test_core.py` | Active (legacy code) | Publishing is gated by approvals and `ALLOW_LIVE_PUBLISH` (default off). Scheduler only reads data. |
| `src/flowmerce/modules/seo/integrations/*.py` | Shopify Admin and public-feed, Google Search Console/GA4, Claude clients; `status.py` records integration health | `shopify`, `shopify_public`, `google`, `claude`, `status` | seo config, util, db | services, api | `tests/unit/seo/test_core.py` (public feed parser) | Active (legacy code) | Network is blocked in tests. Move to top-level `integrations/` after decoupling. |
| `frontend/` | React/TypeScript UI (approved exception) | `web/src` pages, components, lib; `web/dist` built copy | npm packages (react, vite, ...) | served by `src/flowmerce/modules/seo/app.py` | none (no JS tests exist) | Active (legacy code) | Not rebuilt or type-checked during migration. |
| `scripts/run_seo.py`, `scripts/run_seo.bat` | Launcher (venv, install, UI build check, start server) | `main`, `ensure_venv`, `ensure_frontend` | uvicorn, seo config | operators | none | Active (legacy code) | `.bat` is non-Python; decision pending. |
| `tests/unit/seo/`, `tests/integration/seo/`, `tests/fixtures/seo.py` | Migrated blog-ops tests (15) and shared fixtures | pytest tests | pytest, seo module | n/a | n/a | Active | In-memory SQLite; no network. |
| `.vscode/` | Editor run/test configuration | launch, settings | n/a | developers | n/a | Active | |
| ~~`blog-ops/`~~ | Original app, removed 2026-10-29 | n/a | n/a | n/a | n/a | Removed | Superseded by `modules/seo` and `frontend/`; `make_zip.py` was not migrated. |
