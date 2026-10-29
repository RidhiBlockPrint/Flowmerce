# Troubleshooting

Only issues that are known or directly observable from the current code are listed.

| Symptom | Likely cause | What to do |
|---|---|---|
| `configuration error: FLOWMERCE_ENV must be one of ...` (exit code 2) | Invalid environment variable value | Fix the variable; see allowed values in `docs/development/setup.md`. |
| `No module named flowmerce` | Package not installed in the active environment | Activate `.venv`, then `pip install -e ".[dev]"`. |
| `python` not found or older than 3.12 | Wrong interpreter on PATH | Install Python 3.12+ and recreate `.venv`. |
| Changes to `.env` have no effect | Code reads the process environment, not `.env` | Export the variables in your shell (see setup.md). |
| `mypy`/`ruff` not found | Dev extras not installed | `pip install -e ".[dev]"`. |
| No log output | `FLOWMERCE_LOG_LEVEL` too high, or the command logs nothing (`version` does not log) | Set `FLOWMERCE_LOG_LEVEL=DEBUG` and run `health`. |

SEO module:

| Symptom | Likely cause | What to do |
|---|---|---|
| Asked for a sign-in or password | There is none: Flowmerce runs in local operator mode ([ADR 0005](../decisions/0005-local-operator-mode.md)) | Open http://127.0.0.1:3000 on this computer. A 403 `local_only` means the request came from another computer. |
| Fresh empty dashboard, no users or articles | The module reads `data/` under the repository root (or `FLOWMERCE_ROOT` / `DATA_DIR`), and that folder is missing or empty | Restore `data/blog-ops.sqlite` from `backups/` or your own backup (see setup.md). |
| Integrations show "pending setup" | `.env` not in the repository root | Move/copy `.env` to the root; restart. |
| "Port 8787 / 3000 is already in use" or the page shows a connection error | An earlier Flowmerce window, or an old API process, is still running | Close it (Ctrl+C in its window) and run `python scripts\run_flowmerce.py` again. |
| "Node.js and npm are required" or the frontend build fails | Node.js is not installed, or packages did not install | Install Node.js LTS, then run `npm install` and `npm run build` in `frontend\`. |
| `ModuleNotFoundError: fastapi` | `seo` extra not installed | `pip install -e ".[dev,seo]"`. |
| npm install fails on TLS | Office network blocks the default registry | `frontend/.npmrc` points to registry.yarnpkg.com; delete that line on other networks. |
| Other issues | | The original troubleshooting notes are in `docs/architecture/legacy-blog-ops-README.md`. |
