# Setup

Tested here on Python 3.13 (Linux). The project requires Python 3.12+. Not yet run on Windows.

## Install (Windows PowerShell, from the repository root)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,seo]"
copy .env.example .env
```

On macOS/Linux use `source .venv/bin/activate` and `cp .env.example .env`.

## Dependencies

Runtime dependencies of the core package: none (standard library only). The `seo` extra (fastapi, uvicorn, httpx, openpyxl, anthropic, google-auth, requests; carried over from blog-ops) is needed for the SEO module. Dev tools: `pytest` (tests), `ruff` (lint and format), `mypy` (strict type checking). Add any new dependency to `pyproject.toml` and record the reason here.

## Configuration

| Variable | Default | Allowed values |
|---|---|---|
| `FLOWMERCE_ENV` | `development` | development, test, production |
| `FLOWMERCE_LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR, CRITICAL |

Settings are read from the process environment. The code does not load `.env` itself; export the variables in your shell (or add a loader via an approved ADR).

## Run

```powershell
python -m flowmerce version
python -m flowmerce health
```

## Test and check

```powershell
pytest
ruff check .
ruff format --check .
mypy
```

## SEO / Blog Ops module

```powershell
python scripts\run_seo.py                # creates .venv if needed, installs ".[seo]", opens http://localhost:8787
python scripts\run_seo.py --no-browser --reload
```

Credentials and options are in `.env` (see the SEO section of `.env.example`). The module reads `.env` from the repository root and keeps its SQLite database in `data/` (`data/blog-ops.sqlite`, `data/initial-admin.txt`).

**Moving from the original blog-ops folder** (done 2026-10-29; the folder no longer exists): `.env`, `data/` and `backups/` now live in the repository root. Both are git-ignored; keep your own copy of `.env` and back up `data/` and `backups/`.

**Changing the UI** (needs Node.js): from `frontend\` run `npm install`, `npm run dev` (Vite on :5173 proxying `/api` to :8787), then `npm run build` to refresh `frontend\web\dist`. The original `README` is archived at `docs/architecture/legacy-blog-ops-README.md`.
