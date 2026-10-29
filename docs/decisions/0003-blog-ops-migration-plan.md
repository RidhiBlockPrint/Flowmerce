# ADR 0003: Migrate blog-ops into the Flowmerce structure

- Status: approved by owner ("migrate now"); implemented 2026-10-29: code copied, then `.env`, `data/` and `backups/` moved to the root and verified, and `blog-ops/` deleted.
- Date: 2026-10-29

## Decision
Move `blog-ops/` into the new layout in reviewed steps, keeping it runnable and its tests passing after each step.

## Mapping as implemented

| Today (`blog-ops/`) | Now |
|---|---|
| `backend/*.py`, `backend/services/*`, `backend/integrations/*` | `src/flowmerce/modules/seo/` (same internal layout; relative imports unchanged) |
| `backend/config.py` | `src/flowmerce/modules/seo/config.py` (ROOT now the repository root). **Deviation:** not merged into `flowmerce.config`, to avoid behaviour changes; follow-up. |
| integrations to top-level `integrations/` | **Deviation:** kept in `modules/seo/integrations/`: they import seo config/errors, so moving them would make a top-level package depend on a module. Follow-up: decouple, then move. |
| `tests/*` | `tests/unit/seo/test_core.py`, `tests/integration/seo/test_http.py`, shared fixtures `tests/fixtures/seo.py` |
| `web/`, `package.json`, `package-lock.json`, `vite.config.ts`, `.npmrc` | `frontend/` (folder name chosen by owner's go-ahead; internal `web/` layout kept so no TS/config edits were needed) |
| `run.py` | `scripts/run_seo.py` |
| `run.bat` | `scripts/run_seo.bat` (non-Python, kept as-is; owner decision pending) |
| `.vscode/`, `.env.example`, `.gitignore` entries | merged into the repository root |
| `make_zip.py` | not migrated (zips the old folder; obsolete) |
| `data/`, `backups/`, `.env`, `.venv` | not copied (live data and secrets); see setup.md for how to move them |

## Rationale
Single structure, single set of docs and tests, as required by the project rules.

## Alternatives considered
Leave blog-ops as a sibling indefinitely (rejected by owner).

## Advantages
One codebase to reason about.

## Disadvantages
Risk of breaking a working app; SQLite (blog-ops) vs PostgreSQL (planned) reconciliation is unresolved and is a separate decision.

## Consequences and dependencies
- Original `blog-ops/` deleted on 2026-10-29 after byte-for-byte verification of `.env`, the SQLite database and backups at the root; its `make_zip.py` and local `.venv` were not carried over.
- `git init` run on 2026-10-29 (branch `main`); the blog-ops history before this point was not preserved because no repository existed.
- Not verified: the frontend was not rebuilt or type-checked; the migrated app was only exercised with the test suite and a smoke test on a temporary data directory, not with real credentials or data.
- Open: SQLite vs PostgreSQL; Next.js vs the existing Vite/React app; keep or replace `run_seo.bat`; decouple and move integrations; lint/type cleanup of legacy code.
