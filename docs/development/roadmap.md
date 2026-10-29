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
| `pytest` | 34 passed (23 existing + 11 new `/api/home` tests) | Run 2026-10-29 after Stage 1, in `.venv` (Python 3.14.7) |
| `ruff check .` | All checks passed | Same run. Legacy SEO paths are excluded in `pyproject.toml` |
| `mypy` (strict) | No issues in 36 source files | Same run. The SEO module is exempt via `ignore_errors` |
| SEO app smoke test | `/` and `/api/docs` returned 200 | Earlier in this session, against a temporary data directory; not repeated |
| `npm run typecheck` (`tsc --noEmit`) | Exit 0, no errors | 2026-10-29, Node v26.13.0, after Stage 1 |
| `npm run build` (Vite 7) | Built successfully, `frontend/web/dist` regenerated | Same run |
| Dashboard in a browser | Sign-in text, Home with demo off by default, real seeded records and sources, synthetic CPC fixtures withheld, `/publishing` and `/tasks` request counts per route, demo mode on and off; earlier: all routes, SEO pages, phone and tablet widths, keyboard focus | 2026-10-29, against an isolated test instance (temporary folder, seeded test records, no `.env`); not against real data. There is no automated frontend test suite. |

The previous inspection report (Phase 1) quoted these results without re-running them. They were re-run for this roadmap, and the table above is the evidence. Nothing below has been exercised with real credentials or production data.

## A. What exists

| # | Item | Status | Evidence and notes |
|---|---|---|---|
| A1 | Python application foundation: `src/flowmerce` package, settings loading, logging, CLI `version` / `health` | **Verified** (for what it covers) | 8 foundation tests pass; `python -m flowmerce health` printed `flowmerce 0.1.0 OK` earlier in this session. Small scope: no web server, database or business logic of its own. |
| A2 | SEO & Blog Automation module (`src/flowmerce/modules/seo`, code name `seo`), migrated from the old blog-ops app; FastAPI + SQLite | **Testing** | 15 migrated tests pass; server started and answered 200 on a temporary data directory. Not exercised with the real database through the UI, and not with live credentials (see C1). Uses SQLite, not the PostgreSQL design (see B1). |
| A3 | React/TypeScript web UI (`frontend/`) | **Verified** (build and type-check) | Node v26.13.0 and npm 12.2.1 are installed; `node_modules` matches `package-lock.json`; type check and build pass. `frontend/web/dist` is git-ignored, so a fresh clone must run `npm ci` and `npm run build`. Framework: React 19, Vite 7, React Router 7, TypeScript 5.9. |
| A6 | Shared application shell and Home / Morning Brief dashboard (`frontend/web/src`: `Shell.tsx`, `pages/Home.tsx`, `pages/Planned.tsx`, `lib/routes.ts`, `lib/home.ts`, `components/home.tsx`) with `GET /api/home` (`modules/seo/services/home.py`) | **Testing** | Home shows **real SEO & Blog records** (metrics with sources, role-filtered approvals, alerts, pipeline runs, syncs) when demo mode is off, which is the default; demo mode shows a small synthetic SEO-only sample and never mixes with real data. Unbuilt projects appear as Planned only. "Latest reports" is empty with an explanation (no dated reports exist). Tested with 11 backend tests and browser checks on an isolated instance; **not checked with the real database or live accounts**, and there are no automated frontend tests. |
| A4 | Documentation and engineering tools: README, system overview, folder structure, file registry, setup, coding standards, troubleshooting, ADRs 0001-0003, changelog, this roadmap and `PROJECT_RULES.md`; pytest, ruff, mypy; GitHub remote | **Implemented** | `main` is pushed to RidhiBlockPrint/Flowmerce. |
| A5 | Planning documents (v0.1): `docs/01-architecture.md`, `02-connectors-and-apis.md`, `03-data-model.md`, `db/schema.sql`, `architecture-map.html` | **Planned** (design only) | Describe the target design, not what is built. Kept unchanged. |

## B. Outstanding debt and decisions

| # | Item | Status | Notes |
|---|---|---|---|
| B1 | **Database: PostgreSQL 16 (planning documents, `db/schema.sql`) versus SQLite (the working SEO module)** | **Awaiting Approval** | Unresolved owner decision. Do not start the shared data model until decided. See [ADR 0003](../decisions/0003-blog-ops-migration-plan.md). |
| B2 | Lint and type debt in legacy SEO code: `src/flowmerce/modules/seo`, `tests/unit/seo`, `tests/integration/seo`, `tests/fixtures/seo.py` and `scripts/run_seo.py` are excluded from ruff, and the module is exempt from mypy | **Planned** | Remove the exclusions in `pyproject.toml` as files are cleaned up. Ruff once reported 829 findings (mostly line length) on the old `blog-ops` copy of this same code; that was a one-time count and the migrated files have not been re-linted. |
| B3 | Decouple SEO integrations (`modules/seo/integrations`) so they can move to the top-level `integrations/` | **Planned** | Recorded as a follow-up in ADR 0003. |
| B4 | Merge SEO configuration into `flowmerce.config` | **Planned** | Deviation recorded in ADR 0003. |
| B5 | Web UI framework: existing Vite/React app versus the Next.js dashboard named in the planning documents and in Appendix A of the handoff | **Awaiting Approval** (deferred) | The dashboard was built on the existing Vite/React app. Next.js is not approved. The owner plans to revisit the UI after the first module. The handoff's Appendix A stack (Next.js, Vercel, Supabase, Trigger.dev) conflicts with the Python-first rule and is not adopted; it also bears on B1. |
| B6 | `scripts/run_seo.bat` is a non-Python file | **Awaiting Approval** | Kept as-is; owner decision pending (ADR 0003). |
| B7 | Other open planning decisions: hosting, primary shipment tracker, A/B testing approach, landing-page theme route, Google Ads developer token level, data retention, product naming | **Awaiting Approval** | Listed in section 10 of `docs/01-architecture.md`. None are decided here. |

## C. Verification still needed

| # | Item | Status | Notes |
|---|---|---|---|
| C1 | Real Shopify, Google (Search Console, GA4) and Claude integrations | **Planned** (untested) | Code exists in `modules/seo/integrations`, but tests block the network and no live-credential test has been run. Needs the owner's credentials in `.env` and agreement on a safe test (the module has gated publishing). |
| C2 | Dashboard sign-in with the real migrated database | **Planned** (untested) | Sign-in was verified only on an isolated test instance. The real database was opened earlier (one user found) but the UI login with real data has not been tried. |

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
| F1 | Continuous integration (for example GitHub Actions running pytest, ruff and mypy) | **Planned** | None exists. Planning documents list GitHub Actions for CI/CD; the choice has not been made. |
| F2 | Install Node.js to rebuild and type-check the UI | **Verified** | Installed by the owner; Node v26.13.0, npm 12.2.1. This session's shell does not have Node on its PATH (open a new terminal). |
| F3 | `.gitattributes` for consistent line endings | **Planned** | Git warns that LF will become CRLF on Windows. |
| F4 | Real commit author identity | **Planned** | Commits so far use the placeholder `Flowmerce <it@thefabricrush.com>`; configure `user.name` and `user.email`. |
| F5 | Direct unit test for `core/logging.py` | **Planned** | Noted in the file registry as having no direct test. |
| F6 | Backup and restore procedure for `data/` | **Planned** | Live data is git-ignored, so Git does not protect it. Not documented beyond the existing backups folder. |
| F7 | Dependency pinning (lock file) for the `seo` extra | **Planned** | Currently minimum versions only in `pyproject.toml`. |
| F8 | Branding leftovers: sign-in page, `styles.css` comment and `frontend/package.json` name said "Blog Ops" | **Verified** (fixed 2026-10-29) | Now "Flowmerce" / `flowmerce-web`. Remaining: the lockfile's root name is still `blog-ops` and its `engines: node >=24` entry disagrees with `package.json` (left unchanged; `npm ci --dry-run` still passes). The sign-in tagline ("One desk for every story…") is still blog-specific. |
| F9 | Docs and the `run_seo.py` comment say the UI "ships pre-built", but `frontend/web/dist` is git-ignored and not in GitHub | **Planned** | Fresh clones must build the UI (Node required). `docs/development/setup.md` is updated; the `run_seo.py` comment is not. |
| F10 | The Planned project cards on Home still read "Latest report: No reports yet" (`components/home.tsx`) | **Planned** | Truthful but could be read as a working project with no reports; would need a one-line change in a file outside the Stage 1 scope. |
| F11 | Shared Home aggregate: Home reads only the SEO app's `/api/home`; the shell still sits inside the SEO app's sign-in | **Planned** | Extract a shared host when the second project starts or the database decision (B1) is made. |

## Recommended next task

Stage 1 of the SEO-to-shell connection is implemented (A6). Open owner decisions: commit the work, **B1** (SQLite or PostgreSQL) and the handoff's Appendix A stack, and **C2** (check the real data in the dashboard). A natural next task is to run the dashboard against the real database in a read-only way, then decide what the Planned cards should say (F10).