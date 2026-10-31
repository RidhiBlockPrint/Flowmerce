# Changelog

Format: newest first. Types: Added, Changed, Fixed, Removed, Architecture.

## 2026-10-31 (Shipping: master database schema, schema only)

- Added the planned **master database schema** from the owner's "Ridhi Shopify Database" design ([ADR 0008](docs/decisions/0008-master-database-for-shipping.md)): the tables `stores`, `orders`, `items`, `shipments` and `events` with the design's names and columns, created empty in `data/master.sqlite` at startup, plus the matching Postgres DDL for Supabase (`db/master_shipping.sql`). **Nothing fills the tables.**
- Removed an overreach from the first attempt (a Shopify sync into the tables, a "Sync master data" card, API endpoints and a 6-hourly background job). The filled database (54 MB, with customer details) was moved to `backups/` and not deleted.
- 3 schema tests.

## 2026-10-31 (Shipping rebuilt around orders, and the rules added since)

Owner decisions: classify by delivery status, delay measured in days from the fulfilled date, the same days for every carrier.

- **Order-level model** (`modules/shipping/orders.py`, `/api/shipping/orders...`): every order is in one group: Delivered, In transit (0-3 days), Delayed (yellow 4-5, orange 6-8, red 9-12, critical 13+), Not refreshed, Unfulfilled, Lost / missing (team mark, or no carrier update for 14+ days), No tracking ID and No carrier tracking. Needs action is an overlay: no scan for 5+ days and a delivery that took 13+ days. Pages: Overview, Orders (with an order drawer and a team check per shipment) and Analytics (transit time per carrier).
- **Unfulfilled** orders are their own section with no delay tier: the app tracks the shipment, so the clock starts when the order is marked fulfilled.
- **Delivered by rule:** an order whose note says DONE while Shopify shows it unfulfilled is Amazon MCF and counts as delivered once 5+ days old (tag "Amazon MCF"); a mixed order whose partner-carrier parcels (DHL, USPS, FedEx, ...) are delivered and whose only open parcels are Amazon's counts as delivered (tag "Amazon part unconfirmed"). A team mark of lost still wins.
- **Not refreshed:** Shopify only returns orders from the last 60 days, so an older open order stops updating (e.g. #4368). Such an order is no longer counted as In transit / Delayed; the real fix is the `read_all_orders` scope.
- **Tracking-service lookup** (`tracking.py`, "Check with tracking service", `TRACK17_API_KEY`) for parcels Shopify never marks delivered. Not verified against the live service.
- Tried and **reverted** at the owner's request: counting archived Shopify orders as delivered (it emptied Delayed), keeping lost/missing out of every total, hiding phantom rows with a re-check button.
- Current data (orders): delivered 2,985; in transit 209; delayed 322; not refreshed 10; unfulfilled 392; lost / missing 16; needs action 29.

## 2026-10-30 (Shipping: packages fulfilled by hand)

- New category **"Fulfilled by hand, tracked package delivered"** (`covered`). A package with no tracking number (marked fulfilled by hand in Shopify, e.g. MCF orders) used to stay "carrier unconfirmed" even when the order's tracked packages were delivered. It is now covered when Shopify says the whole order is FULFILLED and every package that has a tracking number is delivered. It leaves the unconfirmed queue and the active counts, has its own tag, count (Overview legend, Shipments tile, quick view, Checks tile) and `view=covered` filter, and a team mark on the package still overrides it. Nothing is changed in Shopify or deleted. On the current data: 108 packages covered, unconfirmed 811 -> 700 (e.g. order #5311). Amazon tracking is a separate piece of work.

## 2026-10-30 (Shipping live data import)

- Imported the live tracker data from Supabase (read-only): 4,409 shipments, 35 sync runs, 3,753 order checks, 38 manual marks; the 104 stale rows from the old 17 Oct snapshot were removed with the new `--prune` option (backups taken first). Counts now match the owner's live dashboard (1,089 active, 786 unconfirmed, 21 stuck, 195 on track, 32 yellow; critical and orange differ by one because a shipment crossed a threshold between the screenshot and the import).

## 2026-10-30 (Shipping data capture, second pass)

### Fixed / Added
- Compared with the owner's live tracker screenshots: the classification logic matches the original dashboard exactly (cross-checked against the original JavaScript on the same file: identical counts), so the differences came from data. The delivered `shipments.json` is a 17 Oct snapshot (the newer zip's copy is byte-identical), and the live dashboard also reads Supabase tables that were not in either zip.
- Ported the newer tracker code: order total / currency on every shipment (value at risk), order checks (Shopify note, fulfilment and financial status) saved on each sync, cancelled / refunded orders left out, hourly refresh when credentials are set, the daily alert digest (`alerts.py`, manual `POST /api/shipping/alerts/send`; needs SMTP in `.env`, nothing is scheduled).
- `scripts/import_shipping_data.py --from-supabase`: read-only copy of shipments, sync runs, order checks and manual status from Supabase (needs `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in `.env`; dry run, backup and verification as before). Schema version 2 adds the new columns to existing databases.
- Overview: "Since your last visit" banner, Print summary, a 7 / 30 day / all-dates range for the weekly chart, and a Delivered link.
- Tests: 12 new (order totals, order checks, schema upgrade, Supabase import with a fake server, alert digest).

### Not done
- Command palette (Ctrl+K), notifications bell and the dark theme toggle from the original dashboard; the live Supabase data itself (needs the owner's credentials or exports).

## 2026-10-30 (Shipping module)

### Added
- **Shipping module** integrated from the delayed-order-tracker project ([ADR 0007](docs/decisions/0007-shipping-module-and-database.md)): `src/flowmerce/modules/shipping/` (repo, schema, aging, normalize, carriers, shopify, sync, service, importer, api), endpoints under `/api/shipping/...`, and the `/shipping` pages (overview, shipments, analytics, checks) in Flowmerce's design with a shipment drawer, quick views, filters, server-side paging, CSV exports (escalation, verify, filtered), team check for Amazon/unknown carriers, notes and a Home card.
- Five `shipping_*` tables in the Flowmerce SQLite database (SEO schema untouched); `scripts/import_shipping_data.py` (dry run, backup, verification). 3,524 shipments and 5 sync runs imported and verified.
- Read-only Shopify sync (`read_orders`, `read_fulfillments`, client-credentials token); scheduler refresh every 12 hours when credentials exist; `shipping:update` permission; `SHIPPING_*` settings in `.env.example`.
- Ported tracker tests (42) and new HTTP tests; `ci_smoke.py` checks the shipping API and routes.

### Changed
- Lost on purpose: the Supabase login, the GitHub Actions daily trigger and the Chart.js CDN; notes moved from browser storage to the database. Ruff and mypy exceptions added for the ported code (roadmap B8).

### Validation
- `pytest -q` 129 passed; `ruff check .` and `mypy` pass; `npm run build` succeeds; `ci_smoke.py --web` all 42 checks pass; browser check on the real imported data (overview, shipments with filters, paging and drawer, analytics, checks).
- **Not verified:** a live Shopify sync, `manual_status` / `order_checks` data, Supabase, and the GitHub CI run.

## 2026-10-30 (Ridhi keyword workbook, read-only)

### Added
- `modules/seo/services/keyword_file.py` and `GET /api/keyword-file`: read the newest `data/ridhi-keyword-db-*.xlsx` (sheets Keyword DB, New keywords, Opportunities) without writing to the database or the file. Numbers are taken only from the sheet (blank stays blank). Ridhi only.
- `frontend/src/views/KeywordFile.jsx`: "Ridhi keyword research" section on Topics & keywords (All / Opportunities / New this run, cluster filter, search, volume, KD, Search Console figures, recommended action).
- `tests/unit/seo/test_keyword_file.py`.

### Validation
- `pytest -q` 78 passed, `ruff` and `mypy` pass, `npm run build` succeeds; browser check against the real workbook showed 170 keywords (44 opportunities, 55 new).

## 2026-10-29 (Next.js JavaScript frontend, one launcher)

### Changed
- **Frontend migrated from Vite + React Router + TypeScript to Next.js 15 (App Router) + React 19 in JavaScript/JSX only** ([ADR 0006](docs/decisions/0006-nextjs-javascript-frontend.md)). All 33 files under `frontend/web/src` were converted to `.js`/`.jsx` under `frontend/src` (`pages/` became `views/` so it cannot clash with Next.js's Pages Router) and routing moved to real route folders in `frontend/src/app/` (`blogs/[id]`, `workspace/[brand]`, ...). `frontend/web/` (including `index.html`, `tsconfig.json`, `dist/`), `vite.config.ts`, `main.tsx` and `App.tsx` were removed; `package.json` now depends on `next`, `react` and `react-dom` only, with scripts bound to `127.0.0.1`.
- `frontend/next.config.mjs` forwards `/api/*` to `http://127.0.0.1:8787`, redirects `/login` to Home and adds basic security headers. `components/Providers.jsx` loads the local operator (`/api/auth/me`) and opens the dashboard directly.
- **Only working pages are visible.** The sidebar and Home list Home and the SEO & Blog pages. Planned projects, shared "planned" pages, future-scope entries and Home's demonstration-data mode were removed from the UI; unknown addresses (including `/users`, `/shipping`, `/approvals`) show a not-found page with a link to Home. `Login`, `Planned` and `Users` sources are kept but not mounted. No database rows were touched.
- `modules/seo/app.py` no longer serves `frontend/web/dist` (API only; strict `default-src 'none'` CSP on its responses).
- `scripts/run_flowmerce.py` (new) starts the API on 127.0.0.1:8787 and Next.js on 127.0.0.1:3000, opens the browser and stops both on Ctrl+C, with clear errors for missing Node/npm, failed installs and busy ports. `scripts/run_seo.py` forwards to it; `run_seo.bat` calls the new launcher.
- `scripts/ci_smoke.py` rewritten for local operator mode (no sign-in; `--web` also starts the built frontend and checks its routes). `.github/workflows/ci.yml`: the frontend job runs `npm ci` and `npm run build` (no type-check); the smoke job builds the frontend and runs `ci_smoke.py --web`. `.gitignore`: `frontend/.next/`, `frontend/out/`.
- Documentation: `PROJECT_RULES.md` (Python backend, Next.js/JavaScript frontend), README, setup, roadmap, system overview, folder structure, file registry, CI and troubleshooting guides, ADR 0002 note, ADR 0005 update and new ADR 0006.

### Added
- `tests/unit/test_frontend_javascript_only.py`: fails if TypeScript or Vite files or dependencies return, if the App Router routes are missing, or if unfinished pages are mounted.

### Validation
- `pytest -q`: 75 passed. `ruff check .` and `mypy`: pass. `npm run build` (Next.js 15.5.28): succeeded. `python scripts/ci_smoke.py --web`: all 35 checks passed (run on port 8799). A browser check on an isolated instance confirmed `/login` lands on Home with no sign-in, Home shows real empty records and the sidebar lists only working pages.
- **Not verified:** a full `run_flowmerce.py` start on ports 8787/3000 (an older API process, not started by this work, occupied 8787 and was left running; only the "port in use" error path was exercised), the GitHub CI run, a connection from another computer, and anything against the real database or live services.

### Not done
- No frontend unit tests or linting; Next.js 16 not adopted; `.env.example` may still mention the ignored `ADMIN_PASSWORD`; the `Host`-header check against DNS rebinding (F14).

## 2026-10-29 (local operator mode)

### Changed
- **No sign-in; local computer only** ([ADR 0005](docs/decisions/0005-local-operator-mode.md)). The dashboard opens without an email, password or session. `modules/seo/app.py` refuses every request that does not come from a loopback address (403 `local_only`) before serving the dashboard, its assets or any API path; missing or unparsable addresses fail closed and forwarded-IP headers are ignored. The only exemption is `POST /api/hooks/workflow`, which keeps its own `X-Workflow-Secret` check. The CSRF header, permission checks, audit log and live-publishing safeguards are unchanged.
- Local requests act as the first active administrator record (`auth.local_operator`). `GET /api/auth/me` returns it with its permissions; `POST /api/auth/login` and `/api/auth/password` answer 410 and verify nothing; `/api/auth/logout` is harmless.
- First-run bootstrap creates an administrator record if no active administrator exists, even when other users exist, and never generates, shows, logs or writes a password (`ADMIN_PASSWORD` is ignored; an old `data/initial-admin.txt` is left in place and unused).
- Frontend: `App.tsx` loads the operator and opens the dashboard directly (`/login` redirects to Home); `Shell.tsx` shows a "Local operator mode" indicator instead of the account menu, password change and sign-out; `Users.tsx` is a read-only list with a note.
- Tests: `tests/integration/seo/test_http.py` rewritten and `test_home.py` updated for loopback and remote clients; `tests/fixtures/seo.py` gained client helpers.

### Validation
- 70 Python tests pass (34 before), `ruff check .` and mypy pass, `npm run typecheck` exit 0, `npm run build` succeeded. A browser check on an isolated test instance confirmed the dashboard opens directly, `/login` redirects, the controls are gone and the existing SEO pages load.
- **Failing / not verified:** `scripts/ci_smoke.py` now fails (it signs in with the old first-run password), so the CI `Smoke test` job would fail if pushed; a connection from another computer over a real network was not tried; nothing was run against the real database.

### Not done
- `scripts/ci_smoke.py`, `docs/operations/ci-cd.md`, `docs/operations/troubleshooting.md` and `.env.example` still describe sign-in (outside the approved files). `Login.tsx` is unused but kept. A `Host`-header check against DNS rebinding was not added.

## 2026-10-29 (CI, Stage A)

### Added
- `.github/workflows/ci.yml`: continuous integration on GitHub Actions. Jobs: `Python 3.12` and `Python 3.14` (`pip install -e ".[dev,seo]"`, `ruff check .`, `mypy`, `pytest -q`); `Frontend` (Node 24, `npm ci`, `npm run typecheck`, `npm run build`, built UI saved as an artifact); `Smoke test` (boots the app on a throwaway folder). No secrets, read-only permissions, Actions pinned to commit hashes.
- `.github/dependabot.yml`: weekly update pull requests for pip, npm and GitHub Actions.
- `scripts/ci_smoke.py`: Python smoke test (12 checks) usable locally and in CI.
- `docs/operations/ci-cd.md` and `docs/decisions/0004-ci-cd-github-actions.md`.

### Changed
- Roadmap F1 (CI) now Implemented, not yet run on GitHub; new F12 (deployment) recorded as Planned and awaiting approval. README, setup and file registry updated.

### Validation
- `scripts/ci_smoke.py` ran locally twice (with and without the built UI): all checks passed, no temporary folders left behind; `ruff check .` passes; the 34 Python tests, mypy, `npm run typecheck` and the build still pass. The pinned Action hashes were verified against GitHub's API.
- **Not validated:** the workflows have not run on GitHub; the YAML could not be machine-parsed locally; Python 3.12 and Linux have not been exercised.

### Not done
- Deployment, release artifacts and a container image (not approved); GitHub settings (branch protection, Dependabot alerts) are manual steps for the owner; `docs/architecture/folder-structure.md` does not yet list the new `.github/` folder.

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
