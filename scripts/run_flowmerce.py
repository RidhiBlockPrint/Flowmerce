"""Flowmerce local launcher: starts the Python API and the Next.js frontend with one command.

    python scripts/run_flowmerce.py              build the UI if needed, start both services, open the browser
    python scripts/run_flowmerce.py --dev        run the frontend in Next.js development mode (slower start)
    python scripts/run_flowmerce.py --no-browser

Services (both listen on 127.0.0.1 only; this launcher never binds to the network):
    API       http://127.0.0.1:8787   FastAPI backend (flowmerce.modules.seo)
    Frontend  http://127.0.0.1:3000   Next.js UI; forwards /api/* to the API

On first run it creates .venv and installs the project with the "seo" extra, and runs `npm install` in
frontend/. Requirements: Python 3.10+ and Node.js with npm. Press Ctrl+C to stop both services.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import socket
import subprocess  # noqa: S404 - starts our own services with fixed argument lists
import sys
import threading
import time
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
VENV = ROOT / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
STAMP = VENV / ".requirements.sha256"
HOST = "127.0.0.1"
API_PORT = 8787
WEB_PORT = 3000
API_URL = f"http://{HOST}:{API_PORT}"
WEB_URL = f"http://{HOST}:{WEB_PORT}"


def fail(message: str) -> None:
    print(f"\nFlowmerce cannot start: {message}", file=sys.stderr)
    sys.exit(1)


def ensure_venv() -> None:
    """Create .venv and install the project when pyproject.toml is new or changed, then re-run inside it."""
    if sys.version_info < (3, 10):
        fail("Python 3.10 or newer is required.")
    want = hashlib.sha256((ROOT / "pyproject.toml").read_bytes()).hexdigest()
    if not VENV_PY.exists():
        print("Creating the Python environment in .venv ...")
        venv.EnvBuilder(with_pip=True).create(VENV)
    if not STAMP.exists() or STAMP.read_text().strip() != want:
        print("Installing Python packages (first run or pyproject.toml changed) ...")
        subprocess.check_call(  # noqa: S603
            [
                str(VENV_PY),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-q",
                "-e",
                f"{ROOT}[seo]",
            ]
        )
        STAMP.write_text(want)
    if Path(sys.prefix).resolve() != VENV.resolve():
        os.chdir(ROOT)
        sys.exit(subprocess.call([str(VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]]))  # noqa: S603


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, port))
        except OSError:
            return False
    return True


def port_open(port: int) -> bool:
    try:
        with socket.create_connection((HOST, port), timeout=0.5):
            return True
    except OSError:
        return False


def check_ports() -> None:
    for name, port in (("API", API_PORT), ("frontend", WEB_PORT)):
        if not port_free(port):
            fail(
                f"port {port} (needed by the {name}) is already in use. Close the program using it "
                "(an earlier Flowmerce window?) and try again."
            )


def newest_source_mtime() -> float:
    files = [p for d in ("src", "public") for p in (FRONTEND / d).rglob("*") if p.is_file()]
    files += [FRONTEND / n for n in ("package.json", "next.config.mjs", "jsconfig.json")]
    return max((p.stat().st_mtime for p in files if p.exists()), default=0.0)


def prepare_frontend(dev: bool) -> list[str]:
    """Install packages and build when needed; return the command that runs the frontend."""
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        fail(
            "Node.js and npm are required for the web interface but were not found on PATH. "
            "Install Node.js (https://nodejs.org), reopen this window and run the command again."
        )
    lock = FRONTEND / "package-lock.json"
    marker = FRONTEND / "node_modules" / ".package-lock.json"
    if not marker.exists() or (lock.exists() and lock.stat().st_mtime > marker.stat().st_mtime + 1):
        print("Installing frontend packages (npm install) ...")
        if subprocess.call([npm, "install", "--no-audit", "--no-fund"], cwd=FRONTEND) != 0:  # noqa: S603
            fail("npm install failed. Check your internet connection and the messages above.")
    next_bin = FRONTEND / "node_modules" / "next" / "dist" / "bin" / "next"
    if not next_bin.exists():
        fail(
            "the Next.js package is missing from frontend/node_modules. Run `npm install` in frontend/."
        )
    if dev:
        return [node, str(next_bin), "dev", "-H", HOST, "-p", str(WEB_PORT)]
    build_id = FRONTEND / ".next" / "BUILD_ID"
    if not build_id.exists() or build_id.stat().st_mtime < newest_source_mtime():
        print("Building the web interface (npm run build) ...")
        if subprocess.call([npm, "run", "build"], cwd=FRONTEND) != 0:  # noqa: S603
            fail("the frontend build failed. Fix the errors above and run the command again.")
    return [node, str(next_bin), "start", "-H", HOST, "-p", str(WEB_PORT)]


def stop(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def open_when_ready(open_browser: bool) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if port_open(API_PORT) and port_open(WEB_PORT):
            print(f"\n  Flowmerce is ready: {WEB_URL}\n  Press Ctrl+C to stop both services.\n")
            if open_browser:
                webbrowser.open(WEB_URL)
            return
        time.sleep(0.5)
    print("  The services are taking longer than expected to start; check the messages above.")


def main() -> None:
    ensure_venv()
    parser = argparse.ArgumentParser(
        description="Start Flowmerce (API + web interface) on this computer."
    )
    parser.add_argument(
        "--dev", action="store_true", help="run the frontend in Next.js development mode"
    )
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)

    from flowmerce.modules.seo.config import config

    check_ports()
    web_cmd = prepare_frontend(args.dev)
    print("\nStarting Flowmerce:")
    print(f"  API       {API_URL}   (FastAPI, this computer only)")
    print(f"  Frontend  {WEB_URL}   (Next.js, this computer only)")
    print(
        f"  Live publishing: {'ENABLED' if config.allow_live_publish else 'disabled (ALLOW_LIVE_PUBLISH not set)'}"
    )

    api_env = {**os.environ, "HOST": HOST, "PORT": str(API_PORT)}
    web_env = {**os.environ, "NEXT_TELEMETRY_DISABLED": "1", "FLOWMERCE_API_ORIGIN": API_URL}
    api = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "flowmerce.modules.seo.main:app",
            "--host",
            HOST,
            "--port",
            str(API_PORT),
            "--log-level",
            "warning",
        ],
        cwd=ROOT,
        env=api_env,
    )
    web: subprocess.Popen[bytes] | None = None
    try:
        web = subprocess.Popen(web_cmd, cwd=FRONTEND, env=web_env)  # noqa: S603
        threading.Thread(target=open_when_ready, args=(not args.no_browser,), daemon=True).start()
        while True:
            if api.poll() is not None:
                fail(
                    f"the API stopped unexpectedly (exit code {api.returncode}). See the messages above."
                )
            if web.poll() is not None:
                fail(
                    f"the frontend stopped unexpectedly (exit code {web.returncode}). See the messages above."
                )
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Flowmerce ...")
    finally:
        stop(web)
        stop(api)


if __name__ == "__main__":
    main()
