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

The same checks run automatically on GitHub (see [CI/CD](../operations/ci-cd.md), which also lists the frontend commands and the local smoke test, `python scripts/ci_smoke.py`). CI runs `ruff check .` but not `ruff format --check .`, because the migrated SEO code is not formatted yet.

## Running Flowmerce locally

```powershell
python scripts\run_flowmerce.py             # API on 127.0.0.1:8787 + web interface on 127.0.0.1:3000, opens the browser
python scripts\run_flowmerce.py --dev       # frontend in Next.js development mode
python scripts\run_flowmerce.py --no-browser
```

`scripts\run_seo.py` and `scripts\run_seo.bat` still work and forward to the same launcher. The launcher creates `.venv` if needed, installs `".[seo]"`, runs `npm install` in `frontend\` when `node_modules` is missing, builds the web interface when it is missing or older than its sources, starts both services, opens `http://127.0.0.1:3000` and stops both on Ctrl+C. It needs **Python 3.12+** and **Node.js with npm** (Next.js 15 needs Node 18.18+; the project was last built with v26.13.0); it prints a clear message if Node.js/npm is missing, a package install or build fails, or port 8787 or 3000 is already in use.

Credentials and options are in `.env` (see the SEO section of `.env.example`). The module reads `.env` from the repository root and keeps its SQLite database in `data/` (`data/blog-ops.sqlite`).

**Two services.** The **API** is the Python FastAPI app (`flowmerce.modules.seo.main:app`); it returns JSON only and serves no pages. The **web interface** is the Next.js app in `frontend\` (React, JavaScript/JSX only, App Router). `frontend\next.config.mjs` forwards `/api/*` to `http://127.0.0.1:8787` (override at build time with `FLOWMERCE_API_ORIGIN`). The frontend holds no credentials.

**Local operator mode (no sign-in).** The dashboard opens without credentials. The web interface listens on `127.0.0.1` only, and the API answers only connections from this computer (loopback addresses); any other address gets HTTP 403 for every API path, even if the API's `HOST` is changed. Run it on `127.0.0.1` (the default) and do not expose it to a network or put a proxy or tunnel in front of it. The single exception is `POST /api/hooks/workflow`, the external workflow webhook, which has its own `X-Workflow-Secret` check and is reachable from other computers if the API is reachable. Local requests act as the first active administrator record, which the server creates at startup if none exists (no password is generated, shown or saved; `ADMIN_PASSWORD` is ignored). The old `/api/auth/login` and `/api/auth/password` endpoints answer 410. An existing `data/initial-admin.txt` is not deleted and is no longer used. Scripts that call the API from this computer still need the `X-Requested-With: blog-ops` header for mutating requests. See [ADR 0005](../decisions/0005-local-operator-mode.md).

**Moving from the original blog-ops folder** (done 2026-10-29; the folder no longer exists): `.env`, `data/` and `backups/` now live in the repository root. Both are git-ignored; keep your own copy of `.env` and back up `data/` and `backups/`.

**Building the UI** (needs Node.js; `frontend\.next` and `frontend\node_modules` are git-ignored, so a fresh clone must install and build): from `frontend\` run `npm ci` (installs exactly what `package-lock.json` specifies) and `npm run build` (the Next.js build). There is no TypeScript type check: the frontend is JavaScript/JSX only. There is no frontend lint or test suite yet; `python scripts\ci_smoke.py --web` starts the built frontend and checks its routes.

**Changing the UI**: start the API (`python scripts\run_flowmerce.py --dev` does both), edit files in `frontend\src\`, and the page reloads. Routes are folders under `frontend\src\app\`; page implementations are in `frontend\src\views\`. The original `README` is archived at `docs/architecture/legacy-blog-ops-README.md`.
