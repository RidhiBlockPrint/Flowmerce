"""Blog Ops (flowmerce.modules.seo) launcher. Run from the repository root.

    python scripts/run_seo.py              start the dashboard and open it in the browser
    python scripts/run_seo.py --reload     restart automatically when backend code changes (development)
    python scripts/run_seo.py --port 9000  use another port
    python scripts/run_seo.py --no-browser

On first run it creates a local virtual environment (.venv) and installs the project with the "seo" extra (pyproject.toml), so the only
thing you need is Python 3.10+. Business credentials go in .env (copy .env.example) — see docs/development/setup.md."""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import threading
import time
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repository root
FRONTEND = ROOT / "frontend"
VENV = ROOT / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
REQ = ROOT / "pyproject.toml"
STAMP = VENV / ".requirements.sha256"


def in_venv() -> bool:
    return Path(sys.prefix).resolve() == VENV.resolve()


def ensure_venv() -> None:
    """Create .venv and install the project when pyproject.toml is new or changed, then re-run inside it."""
    if sys.version_info < (3, 10):
        sys.exit("Python 3.10 or newer is required.")
    want = hashlib.sha256(REQ.read_bytes()).hexdigest()
    if not VENV_PY.exists():
        print("Creating virtual environment in .venv …")
        venv.EnvBuilder(with_pip=True).create(VENV)
    if not STAMP.exists() or STAMP.read_text().strip() != want:
        print("Installing Python packages (first run or pyproject.toml changed) …")
        subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-e", f"{ROOT}[seo]"])
        STAMP.write_text(want)
    if not in_venv():
        os.chdir(ROOT)
        sys.exit(subprocess.call([str(VENV_PY), str(ROOT / "scripts" / "run_seo.py"), *sys.argv[1:]]))


def ensure_frontend() -> None:
    """The React UI ships pre-built in frontend/web/dist. Rebuild only if it is missing and Node is available."""
    if (FRONTEND / "web" / "dist" / "index.html").exists():
        return
    npm = shutil.which("npm")
    if not npm:
        print("! frontend/web/dist is missing and Node.js is not installed, so the UI cannot be built. The API still runs at /api.")
        return
    print("Building the web UI (one time) …")
    if not (FRONTEND / "node_modules").exists():
        subprocess.check_call([npm, "install", "--no-audit", "--no-fund"], cwd=FRONTEND)
    subprocess.check_call([npm, "run", "build"], cwd=FRONTEND)


def main() -> None:
    ensure_venv()
    p = argparse.ArgumentParser(description="Start the Blog Ops dashboard.")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--host", default=None)
    p.add_argument("--reload", action="store_true", help="auto-restart on backend code changes")
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()
    if args.port:
        os.environ["PORT"] = str(args.port)
    if args.host:
        os.environ["HOST"] = args.host
    os.chdir(ROOT)
    ensure_frontend()

    import uvicorn
    from flowmerce.modules.seo.config import config

    url = f"http://{'localhost' if config.host in ('127.0.0.1', '0.0.0.0') else config.host}:{config.port}"
    print(f"\n  Blog Ops is starting on {url}")
    print(f"  Live publishing: {'ENABLED' if config.allow_live_publish else 'disabled (ALLOW_LIVE_PUBLISH not set)'}")
    print("  Press Ctrl+C to stop.\n")
    if not args.no_browser:
        threading.Thread(target=lambda: (time.sleep(2), webbrowser.open(url)), daemon=True).start()
    uvicorn.run("flowmerce.modules.seo.main:app", host=config.host, port=config.port, reload=args.reload,
                reload_dirs=[str(ROOT / "src")] if args.reload else None, log_level="info")


if __name__ == "__main__":
    main()
