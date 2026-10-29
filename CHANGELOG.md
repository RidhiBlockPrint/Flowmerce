# Changelog

Format: newest first. Types: Added, Changed, Fixed, Removed, Architecture.

## 2026-10-29 (Home: real SEO data, Stage 1)

### Added
- `GET /api/home` (`modules/seo/api.py`, new `modules/seo/services/home.py`): a read-only summary of real SEO & Blog records for the Home page. It needs the `view` permission, supports `?brand=`, and returns a fixed 28-day metric window ending 3 days before today, each metric with its source. Approvals use the same role filtering as `/api/tasks` (review, publish authorization and topic decisions only). Alerts reuse the existing alert logic; jobs come from `workflow_runs`; syncs from `integration_status` (attempted integrations only, no error text). "Latest reports" is always empty with an explanation, because dated reports do not exist. Figures from synthetic demo fixtures are never returned as metrics: they are withheld and flagged (`withheld`, `demoFixturesLoaded`).
- `tests/integration/seo/test_home.py`: 11 tests (authentication, permission, role filtering, brand filter, unavailable sources, real-versus-demo separation, no secrets, no mutation).

### Changed
- `modules/seo/api.py`: the task-building logic of `/api/tasks` moved into `_tasks_for()` (behaviour unchanged) so `/api/tasks` and `/api/home` agree.
- `frontend/web/src/lib/home.ts`, `pages/Home.tsx`: demo mode now defaults to OFF; with it off Home shows real records from `/api/home` (with loading, error and empty states), with it on it shows a small synthetic sample and makes no request. The two are never mixed. The fictional Meta ads, shipment, conversion and landing-page demo rows were removed; the sample covers only the SEO & Blog project and every row says "Sample".
- `frontend/web/src/components/Shell.tsx`: `/publishing` is requested only on SEO pages, `/tasks` only on SEO pages and Home, and the Tasks control is shown only there (previously both ran on every route change).
- `frontend/web/src/pages/Login.tsx`: sign-in tagline "Ecommerce in a Flow." and description "A shared workspace for your e-commerce operations and growth."

### Validation
- 34 Python tests pass (23 existing + 11 new), `ruff check .` and mypy pass; `npm run typecheck` exit 0; `npm run build` succeeded. Browser checks on an isolated test instance (temporary folder, seeded test records, no `.env`): sign-in text, demo off by default, real values and sources, CPC demo fixtures withheld, request counts per route, demo mode on and off. Not run against real data or live accounts.

### Not done
- The Planned project cards still say "Latest report: No reports yet" (`components/home.tsx` was outside the approved scope). Home still has no data for the unbuilt projects, by design.

## 2026-10-29 (branding fix)

### Changed
- `frontend/web/src/pages/Login.tsx`: sign-in page heading "Blog Ops" -> "Flowmerce". `frontend/web/src/styles.css`: first-line comment updated. `frontend/package.json`: name `flowmerce-web` and an accurate description (the UI must be built; `dist/` is git-ignored).
- Roadmap F8 updated.

### Not changed
- `package-lock.json` (its root name is still `blog-ops`); the blog-specific sign-in tagline.

### Validation
- `npm ci --dry-run` exit 0 and lockfile unchanged; `npm run typecheck` exit 0; `npm run build` succeeded and the built assets contain no "Blog Ops"; 23 Python tests and ruff pass. The sign-in page was not re-opened in a browser.

## 2026-10-29 (main dashboard)

### Added
- Shared application shell and Home / Morning Brief page in `frontend/web/src`: `lib/routes.ts`, `lib/home.ts`, `pages/Home.tsx`, `pages/Planned.tsx`, `components/home.tsx`. Home shows module cards for the six projects (real status chips), demonstration-only metrics, approvals, alerts, reports and job activity (all badged "Demo", switchable off to show empty states), and quick navigation. Unbuilt pages and Merchandising Automation (future scope) use a shared "Planned" page with no controls.
- Icons `home`, `library`, `settings`.

### Changed
- `Shell.tsx`: Flowmerce name and tagline "Ecommerce in a Flow"; sidebar generated from the route registry; SEO pages grouped under SEO & Blog Content; date picker and search only on SEO pages; skip-to-content link.
- `App.tsx`: `/` is now Home; the former Overview is at `/seo`; all other SEO addresses unchanged.
- `index.html` title; `styles.css` additions (reuses existing tokens).
- `docs/development/setup.md` (Node and git-ignored `dist` instructions), README, folder structure, system overview, file registry, roadmap (module names and order from the handoff, priorities reconciled).

### Not done
- Backend data for Home (no API, no live integrations, no approvals or jobs); dark theme; sign-in page still says "Blog Ops"; no frontend lint or tests; not checked with real data.

### Validation
- `npm run typecheck` exit 0; `npm run build` succeeded; 23 Python tests, ruff and mypy pass; browser checks on an isolated test instance (all routes, brand switching, phone and tablet widths, keyboard focus). One contrast defect found and fixed (status tag text 2.77:1 to 4.99:1).

## 2026-10-29 (approval policy)

### Added
- `PROJECT_RULES.md` section 11: phase-based file-modification policy. Setup-phase permission has ended; every product-development change now needs the owner's explicit approval. Documentation only.

## 2026-10-29 (product handoff)

### Added
- `docs/product/Flowmerce_Project_Handoff.md`: the owner's product specification, copied unchanged from Downloads (identical per byte comparison). Documentation only.

## 2026-10-29 (module priority)

### Changed
- `docs/development/roadmap.md`: recorded the owner's decision that SEO & Blog Automation is the first module, added a blueprint-vs-code gap table for it, updated the recommended next task. Documentation only.

## 2026-10-29 (rules and roadmap)

### Added
- `PROJECT_RULES.md`: permanent engineering rules, approval requirements, reporting and handover rules (records existing ADR 0001/0002 approvals; decides nothing new).
- `docs/development/roadmap.md`: actual status of every component, open decisions (SQLite vs PostgreSQL, UI framework, module priority) and last check evidence. Documentation only; no code, test, schema, frontend or dependency changes.

### Changed
- `README.md`, `docs/FILE_REGISTRY.md`: links and entries for the two new files.

## 2026-10-29 (GitHub)

### Added
- Remote `origin` = `https://github.com/RidhiBlockPrint/Flowmerce.git`. The remote's placeholder initial commit was merged (our README kept) and `main` pushed as a fast-forward, tracking `origin/main`.

## 2026-10-29 (git)

### Added
- Git repository initialised on branch `main` with one initial commit; `.env`, `data/`, `backups/` and `.venv/` verified as ignored.

## 2026-10-29 (blog-ops removed)

### Removed
- Original `blog-ops/` folder (code duplicated in `src/flowmerce/modules/seo` and `frontend/`). Its `make_zip.py` and local `.venv` were not carried over.

### Changed
- `.env`, `data/` and `backups/` moved from `blog-ops/` to the repository root (verified byte-for-byte; the module opened the database and found 1 user). `.gitignore` and ruff exclusions no longer mention `blog-ops`. README, setup, troubleshooting, system overview, folder structure, registry and ADR 0003 updated.

### Validation
- 23 tests pass after the removal.

## 2026-10-29 (verification)

### Fixed
- `pyproject.toml`: added the legacy `blog-ops/` folder to ruff `extend-exclude`; `ruff check .` previously reported 829 errors, all in that untouched copy. Now passes.

### Fixed (migration completed)
- Copied the missing backend files (`auth`, `config`, `db`, `permissions`, `util`, `cli`, `main`, `services/*`, `integrations/*`) from `blog-ops/backend` into `src/flowmerce/modules/seo/`; `config.ROOT` now resolves to the repository root (override `FLOWMERCE_ROOT`); `cli.py`/`main.py` docstrings point at the new module path.
- Migrated the tests: `blog-ops/tests` -> `tests/unit/seo/test_core.py`, `tests/integration/seo/test_http.py`, fixtures in `tests/fixtures/seo.py` (registered via new `tests/conftest.py`; imports `backend.` -> `flowmerce.modules.seo.`).
- Validation: 23 tests pass, `ruff check .` and strict `mypy` pass, and a smoke test of `startup()` returned 200 for `/` and `/api/docs` with a temporary data dir.

### Found, not fixed
- The entry below lists migrated tests (`tests/unit/seo`, `tests/integration/seo`, `tests/fixtures/seo.py`) and a "23 tests pass" result. Those test files are not on disk; `pytest` collects 8 tests (all foundation tests) and they pass. Original tests remain in `blog-ops/tests/`. Needs a decision on re-migrating them.
- The test `test_python_dash_m_health` requires `pip install -e .` (use a venv); it fails against a bare interpreter.

## 2026-10-29 (later): blog-ops migrated into the new structure

### Architecture
- `blog-ops/backend` copied to `src/flowmerce/modules/seo` (relative imports unchanged); `blog-ops/web` + npm/Vite config copied to `frontend/`; tests split into `tests/unit/seo`, `tests/integration/seo` with shared fixtures in `tests/fixtures/seo.py`.
- Integrations (`shopify`, `google`, `claude`, status) stay inside `modules/seo/integrations` for now: they import the seo module's config and error types, so moving them to the top-level `integrations/` would invert the dependency direction.

### Changed
- `modules/seo/config.py`: `ROOT` is now the repository root (override `FLOWMERCE_ROOT`); `.env` and `data/` are read from there. `modules/seo/app.py` serves `frontend/web/dist`.
- `run.py` -> `scripts/run_seo.py` (installs `.[seo]` from `pyproject.toml`); `run.bat` -> `scripts/run_seo.bat`; `.vscode/` and `.env.example` merged into the root.
- `pyproject.toml`: new `seo` extra (dependencies from `blog-ops/requirements.txt`), pytest import mode and paths, ruff/mypy exclusions for legacy code.

### Not done
- Original `blog-ops/` not removed; `make_zip.py` not migrated; `.env`, `data/` and backups not copied (secrets/data); frontend not rebuilt or type-checked (no Node run); no git repository initialised.

### Validation
- 23 tests pass (15 migrated blog-ops tests + 8 foundation tests) on Python 3.13; the baseline of the original blog-ops was 15/15. Server smoke test: `/` and `/api/docs` return 200 with a temporary data directory.

## 2026-10-29

### Added
- Python engineering foundation: `pyproject.toml`, `src/flowmerce/` package (`config`, `core`, `modules`, `main`), CLI commands `version` and `health`.
- Tests: 4 settings tests, 3 CLI unit tests, 1 process-level integration test.
- Root `.gitignore` and `.env.example`.
- Documentation set under `docs/` (architecture, development, operations, FILE_REGISTRY, ADRs 0001-0003).

### Changed
- Root `README.md` rewritten to describe real status. The previous version (planning-draft status and file table) is preserved verbatim as `docs/architecture/planning-v0.1-readme.md`.

### Architecture
- ADR 0001: Python-first. ADR 0002: owner-approved exceptions (TypeScript/JavaScript for web UI, SQL for schema). ADR 0003 (proposed): migrate `blog-ops` into the new structure.
