# Flowmerce development roadmap

Last updated: 2026-10-29. This reflects the repository as it is today. Rules for keeping it current: [PROJECT_RULES.md](../../PROJECT_RULES.md). Update it in the same task as any change that moves an item's status.

## Status values

| Status | Meaning |
|---|---|
| Planned | Described in documents; no code. |
| Awaiting Approval | Needs an owner decision before work can start. |
| In Progress | Being worked on now. |
| Implemented | Code exists; not independently verified. |
| Testing | Implemented and partly checked; known gaps remain. |
| Verified | Checked with evidence recorded below. |
| Blocked | Cannot proceed until a named dependency is resolved. |

## Evidence of the last checks

| Check | Result | When and how |
|---|---|---|
| `pytest -q` | 75 passed | 2026-10-29, `.venv` (Python 3.14), after the Next.js migration. Includes the local operator mode tests (`test_http.py`, `test_home.py`) and `tests/unit/test_frontend_javascript_only.py` |
| `ruff check .` | All checks passed | Same run. Legacy SEO paths are excluded in `pyproject.toml` |
| `mypy` (strict) | No issues in 37 source files | Same run. The SEO module is exempt via `ignore_errors` |
| `npm run build` in `frontend/` (Next.js 15.5.28) | Succeeded; all 13 routes built | Same session, Node v26.13.0 |
| `python scripts/ci_smoke.py --web --api-port 8799` | All 35 checks passed (API: operator context, 410 login/password, CSRF, webhook refusal, `/api/home`; frontend: 11 working routes render, 5 unbuilt routes are not-found, `/login` redirects, `/api` is forwarded) | Same session, throwaway folder, with the frontend built against port 8799 because an older API process (not started by this work, left running) occupied 8787. It was rebuilt afterwards for the default port. |
| Dashboard in a browser | `/login` landed on Home with no sign-in; Home showed real (empty) SEO & Blog records with no demonstration data; the sidebar listed only Home and the SEO & Blog pages; `/blogs` rendered | Same session, isolated instance (empty temporary data folder, API 8799 / frontend 3055). Not run against the real database. |
| `scripts/run_flowmerce.py` | **Only the "port in use" path was exercised** (it stopped with a clear message because 8787 was already occupied). A full start on 8787/3000, browser opening and Ctrl+C shutdown were **not verified** | Same session. The occupying process was not mine, so it was not stopped. |
| GitHub CI after the changes | **Not run** (nothing was pushed) | n/a |

The previous inspection report (Phase 1) quoted these results without re-running them. They were re-run for this roadmap, and the table above is the evidence. Nothing below has been exercised with real credentials or production data.

## A. What exists

| # | Item | Status | Evidence and notes |
|---|---|---|---|
| A1 | Python application foundation: `src/flowmerce` package, settings loading, logging, CLI `version` / `health` | **Verified** (for what it covers) | 8 foundation tests pass; `python -m flowmerce health` printed `flowmerce 0.1.0 OK` earlier in this session. Small scope: no web server, database or business logic of its own. |
| A2 | SEO & Blog Automation module (`src/flowmerce/modules/seo`, code name `seo`), migrated from the old blog-ops app; FastAPI + SQLite | **Testing** | 15 migrated tests pass; server started and answered 200 on a temporary data directory. Not exercised with the real database through the UI, and not with live credentials (see C1). Uses SQLite, not the PostgreSQL design (see B1). |
| A3 | Next.js + React web UI in JavaScript/JSX (`frontend/`, ADR 0006) | **Verified** (build, route smoke test, browser check) | Next.js 15.5, React 19, no TypeScript, no Vite, no React Router. `frontend/.next` and `node_modules` are git-ignored: a fresh clone runs `npm ci` and `npm run build` (the launcher does this). There is no frontend unit-test or lint suite. |
| A6 | Shared application shell and Home / Morning Brief dashboard (`frontend/src`: `components/Shell.jsx`, `views/Home.jsx`, `lib/routes.js`, `lib/home.js`, `components/home.jsx`) with `GET /api/home` (`modules/seo/services/home.py`) | **Testing** | Home shows **real SEO & Blog records** only (metrics with sources, role-filtered approvals, alerts, pipeline runs, syncs); the demonstration-data mode and all unbuilt-project cards and links were removed. Backend tests for `/api/home` pass; browser-checked on an empty isolated instance only, not with real data (C2). |
| A8 | Local operator mode: loopback-only access, no sign-in, local administrator identity, secret-protected webhook kept (`auth.py`, `app.py`, `api.py`, `Providers.jsx`, `Shell.jsx`; [ADR 0005](../decisions/0005-local-operator-mode.md)) | **Testing** | Backend tests, smoke test and an isolated-instance browser check pass. **Not verified:** a real connection from another computer over a network; DNS rebinding is not covered (F14). |
| A4 | Documentation and engineering tools: README, system overview, folder structure, file registry, setup, coding standards, troubleshooting, ADRs 0001-0003, changelog, this roadmap and `PROJECT_RULES.md`; pytest, ruff, mypy; GitHub remote | **Implemented** | `main` is pushed to RidhiBlockPrint/Flowmerce. |
| A5 | Planning documents (v0.1): `docs/01-architecture.md`, `02-connectors-and-apis.md`, `03-data-model.md`, `db/schema.sql`, `architecture-map.html` | **Planned** (design only) | Describe the target design, not what is built. Kept unchanged. |

## B. Outstanding debt and decisions

| # | Item | Status | Notes |
|---|---|---|---|
| B1 | **Database: PostgreSQL 16 (planning documents, `db/schema.sql`) versus SQLite (the working SEO module)** | **Awaiting Approval** | Unresolved owner decision. Do not start the shared data model until decided. See [ADR 0003](../decisions/0003-blog-ops-migration-plan.md). |
| B2 | Lint and type debt in legacy SEO code: `src/flowmerce/modules/seo`, `tests/unit/seo`, `tests/integration/seo`, `tests/fixtures/seo.py` and `scripts/run_seo.py` are excluded from ruff, and the module is exempt from mypy | **Planned** | Remove the exclusions in `pyproject.toml` as files are cleaned up. Ruff once reported 829 findings (mostly line length) on the old `blog-ops` copy of this same code; that was a one-time count and the migrated files have not been re-linted. |
| B3 | Decouple SEO integrations (`modules/seo/integrations`) so they can move to the top-level `integrations/` | **Planned** | Recorded as a follow-up in ADR 0003. |
| B4 | Merge SEO configuration into `flowmerce.config` | **Planned** | Deviation recorded in ADR 0003. |
| B5 | Web UI framework | **Approved** (2026-10-29) | The owner chose Next.js + React in JavaScript/JSX (no TypeScript, no Vite); see [ADR 0006](../decisions/0006-nextjs-javascript-frontend.md). Hosting (Vercel) and the rest of the handoff's Appendix A stack remain undecided. |
| B6 | `scripts/run_seo.bat` is a non-Python file | **Awaiting Approval** | Kept as-is; owner decision pending (ADR 0003). |
| B7 | Other open planning decisions: hosting, primary shipment tracker, A/B testing approach, landing-page theme route, Google Ads developer token level, data retention, product naming | **Awaiting Approval** | Listed in section 10 of `docs/01-architecture.md`. None are decided here. |

## C. Verification still needed

| # | Item | Status | Notes |
|---|---|---|---|
| C1 | Real Shopify, Google (Search Console, GA4) and Claude integrations | **Planned** (untested) | Code exists in `modules/seo/integrations`, but tests block the network and no live-credential test has been run. Needs the owner's credentials in `.env` and agreement on a safe test (the module has gated publishing). |
| C2 | Dashboard with the real migrated database | **Planned** (untested) | Sign-in no longer exists (local operator mode); the real database has not been opened through the new dashboard by this project's checks. |

## D. Planned platform pieces (not built)

Per the planning documents:

| # | Item | Status | Notes |
|---|---|---|---|
| D1 | Shared database design (schemas such as `core`, `integration`, `raw`, `ops`; master data for products, pages, orders, taxonomy, brand rules) | **Planned**, depends on B1 | `docs/03-data-model.md` and `db/schema.sql`. |
| D2 | Approval engine ("ops engine": signal to recommendation to approved action to measured result) | **Planned**, depends on D1 | `docs/01-architecture.md` section 6. |

## E. Business modules

Names and order are from the product handoff (`docs/product/Flowmerce_Project_Handoff.md`, sections 2.1 and 9.1); code names are from `docs/01-architecture.md`. The planning document uses older names for some modules (for example "Shipping Tracking & Alerts", "Landing Page Builder"); the handoff is the product specification. The SEO module is the migrated one (A2). The handoff says a Shipping operations prototype exists outside this repository; none of it is in this repository.

| # | Project | Code name | Status |
|---|---|---|---|
| 1 | SEO & Blog Content | `seo` | See A2 and A6 |
| 2 | Shipping & Customer Experience | `ship` | **Planned** |
| 3 | Meta & Google Ads Performance | `ads` | **Planned** |
| 4 | Creative Strategist | `creative` | **Planned** |
| 5 | Landing Page Automation | `page` | **Planned** |
| 6 | Conversion Rate Optimization (CRO) | `cro` | **Planned** |
| Future | Merchandising Automation | n/a | **Future scope** (not a current priority; links to other projects to be confirmed) |

**Priorities (owner, 2026-10-29):** (1) the main dashboard and shared application shell (built as A6), (2) connecting the existing modules to that shell, (3) the remaining projects in the order above. SEO & Blog remains the first project; the dashboard is the first deliverable. The next planned task is a review of how the SEO module connects to the shell.

### SEO & Blog Automation: planned blueprint vs. code (keyword search of the code, not tested behaviour)

Blueprint: `docs/01-architecture.md` section 7.2.

| Blueprint item | Evidence in code today | Status |
|---|---|---|
| Search Console and GA4 reading | References in `integrations/google.py`, `services/analytics.py` | Implemented, not tested live |
| Hidden Shopify blog drafts; publishing as a separate approved step | `integrations/shopify.py`, `services/publishing.py` | Implemented, not tested live |
| Topic scoring | `services/workflow.py` mentions scoring; whether it matches the blueprint's 7-criterion score has not been checked | Unverified |
| Internal link suggestions | Referenced in `services/analytics.py`, `workflow.py`, `integrations/claude.py` | Unverified |
| Semrush data | Only an Excel import path (`services/excel.py`); no Semrush API connection found | Planned (API) |
| Google Trends, Judge.me reviews and questions, decay detection on existing articles | No matches found in the module | Planned |
| Moving to the planned shared PostgreSQL schema | Uses SQLite | Depends on B1 |

## F. Engineering improvements

| # | Item | Status | Notes |
|---|---|---|---|
| F1 | Continuous integration (GitHub Actions): `.github/workflows/ci.yml` (ruff, mypy, pytest on Python 3.12 and 3.14; frontend type check and build on Node 24; a Python smoke test), `.github/dependabot.yml`, `scripts/ci_smoke.py` | **Implemented** (not yet run on GitHub) | See [ADR 0004](../decisions/0004-ci-cd-github-actions.md) and [CI/CD](../operations/ci-cd.md). The smoke script was run locally and passes; the workflow YAML could not be machine-validated locally and the pinned Action hashes were checked against GitHub's API. **Python 3.12 has never been run**, so the first run may fail there. Branch protection and other GitHub settings are manual steps for the owner. Deployment is not included (see F12). |
| F2 | Install Node.js to rebuild and type-check the UI | **Verified** | Installed by the owner; Node v26.13.0, npm 12.2.1. This session's shell does not have Node on its PATH (open a new terminal). |
| F3 | `.gitattributes` for consistent line endings | **Planned** | Git warns that LF will become CRLF on Windows. |
| F4 | Real commit author identity | **Planned** | Commits so far use the placeholder `Flowmerce <it@thefabricrush.com>`; configure `user.name` and `user.email`. |
| F5 | Direct unit test for `core/logging.py` | **Planned** | Noted in the file registry as having no direct test. |
| F6 | Backup and restore procedure for `data/` | **Planned** | Live data is git-ignored, so Git does not protect it. Not documented beyond the existing backups folder. |
| F7 | Dependency pinning (lock file) for the `seo` extra | **Planned** | Currently minimum versions only in `pyproject.toml`. |
| F8 | Branding leftovers: sign-in page, `styles.css` comment and `frontend/package.json` name said "Blog Ops" | **Verified** (fixed 2026-10-29) | Now "Flowmerce" / `flowmerce-web`. Remaining: the lockfile's root name is still `blog-ops` and its `engines: node >=24` entry disagrees with `package.json` (left unchanged; `npm ci --dry-run` still passes). The sign-in tagline ("One desk for every story…") is still blog-specific. |
| F9 | The UI is not in Git (`frontend/.next` is git-ignored) | **Implemented** | `scripts/run_flowmerce.py` installs packages and builds the UI when needed; fresh clones need Node.js. |
| F10 | Planned project cards on Home | **Verified** (removed 2026-10-29) | Home shows only the SEO & Blog project card; unbuilt projects have no cards. |
| F11 | Shared Home aggregate: Home reads only the SEO app's `/api/home`; the shell still sits inside the SEO app (its local operator identity and loopback guard) | **Planned** | Extract a shared host when the second project starts or the database decision (B1) is made; any hosted deployment needs real authentication (ADR 0005). |
| F12 | Deployment and release automation (release artifacts, container image, deploy job with manual approval) | **Planned**, **Awaiting Approval** | Blocked on the hosting decision and the database decision (B1). Release artifacts and a container image were proposed as an optional Stage B and not approved. |
| F13 | CI smoke test and docs depended on sign-in | **Verified** (fixed 2026-10-29) | `scripts/ci_smoke.py`, `ci-cd.md`, `troubleshooting.md` and the CI workflow were rewritten for local operator mode and the Next.js frontend. Not yet run on GitHub. `.env.example` may still mention `ADMIN_PASSWORD` (ignored). |
| F14 | Harden local operator mode against DNS rebinding by checking the `Host` header (accept only localhost, 127.0.0.1 and [::1]) | **Awaiting Approval** | Not requested in this phase; the tests' default `Host` would need adjusting. Documented as a known limit in ADR 0005. |

## Recommended next task

Stage 1 of the SEO-to-shell connection is implemented (A6). Open owner decisions: commit the work, **B1** (SQLite or PostgreSQL) and the handoff's Appendix A stack, and **C2** (check the real data in the dashboard). A natural next task is to run the dashboard against the real database in a read-only way, then decide what the Planned cards should say (F10).