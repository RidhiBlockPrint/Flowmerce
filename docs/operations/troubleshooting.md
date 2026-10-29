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
| Sign-in password unknown | Admin password is generated into `data/initial-admin.txt` on first start | Read that file, or create a user: `python -m flowmerce.modules.seo.cli --email you@example.com --name "You" --role admin`. |
| Fresh empty dashboard, no users or articles | The module reads `data/` under the repository root (or `FLOWMERCE_ROOT` / `DATA_DIR`), and that folder is missing or empty | Restore `data/blog-ops.sqlite` from `backups/` or your own backup (see setup.md). |
| Integrations show "pending setup" | `.env` not in the repository root | Move/copy `.env` to the root; restart. |
| Browser shows API only / UI missing | `frontend/web/dist` missing and Node not installed | Install Node.js, then build the UI (see setup.md). |
| `ModuleNotFoundError: fastapi` | `seo` extra not installed | `pip install -e ".[dev,seo]"`. |
| npm install fails on TLS | Office network blocks the default registry | `frontend/.npmrc` points to registry.yarnpkg.com; delete that line on other networks. |
| Other issues | | The original troubleshooting notes are in `docs/architecture/legacy-blog-ops-README.md`. |
