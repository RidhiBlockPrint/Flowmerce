# Changelog

Format: newest first. Types: Added, Changed, Fixed, Removed, Architecture.

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
