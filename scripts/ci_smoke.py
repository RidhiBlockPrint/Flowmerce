"""Boot the real Flowmerce app on a throwaway data folder and probe it over HTTP.

Used by CI and runnable locally::

    python scripts/ci_smoke.py            # API checks only
    python scripts/ci_smoke.py --web      # also starts the built Next.js frontend (npm run build first)

Safety: the app runs with FLOWMERCE_ROOT pointing at a fresh temporary folder, so it never reads
the repository's .env or data/, has no credentials, keeps the scheduler and live publishing off
and binds to 127.0.0.1. Nothing is signed in to: Flowmerce runs in local operator mode. With --web the API
uses port 8787 by default (where the frontend's /api proxy points; see --api-port) and the frontend a free port, both on 127.0.0.1.
Exit code 0 means every check passed; 1 means at least one failed (each is printed).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import socket
import subprocess  # noqa: S404 - starts our own app with a fixed argument list
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger("ci_smoke")

API_PORT = 8787
HEADERS = {"X-Requested-With": "blog-ops", "Accept": "application/json"}
SECRET_ENV = (
    "ANTHROPIC_API_KEY",
    "RIDHI_SHOPIFY_ADMIN_TOKEN",
    "CPC_SHOPIFY_ADMIN_TOKEN",
    "WORKFLOW_WEBHOOK_SECRET",
    "ADMIN_PASSWORD",
    "GOOGLE_SERVICE_ACCOUNT_FILE",
)
SECRET_MARKERS = ("shpat_", "private_key", "sk-ant", "password_hash", "admin_token")
HOME_KEYS = {
    "generatedAt",
    "window",
    "brands",
    "demoFixturesLoaded",
    "brief",
    "metrics",
    "approvals",
    "approvalsTotal",
    "alerts",
    "reports",
    "reportsNote",
    "jobs",
    "syncs",
}
WEB_ROUTES = (
    "/",
    "/seo",
    "/blogs",
    "/topics",
    "/publishing",
    "/analytics",
    "/automation",
    "/data",
    "/integrations",
    "/audit",
    "/workspace/ridhi",
)
WEB_MISSING = ("/users", "/shipping", "/approvals", "/merchandising", "/no-such-page")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Client:
    """Tiny HTTP client. `request` returns (status, body); `final_url` is where redirects ended."""

    def __init__(self, base: str) -> None:
        self.base = base
        self.final_url = ""

    def request(
        self,
        path: str,
        body: dict | None = None,
        headers: dict | None = None,
        method: str | None = None,
    ) -> tuple[int, str]:
        data = json.dumps(body).encode() if body is not None else None
        merged = dict(HEADERS if headers is None else headers)
        if body is not None:
            merged["Content-Type"] = "application/json"
        req = urllib.request.Request(  # noqa: S310 - fixed http://127.0.0.1 URL
            self.base + path,
            data=data,
            headers=merged,
            method=method or ("POST" if body is not None else "GET"),
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - fixed http://127.0.0.1 URL
                self.final_url = r.geturl()
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")


def wait_ready(
    client: Client, proc: subprocess.Popen, seconds: float, path: str = "/api/docs"
) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        try:
            if client.request(path, headers={})[0] == 200:
                return True
        except OSError:
            pass
        time.sleep(0.5)
    return False


class Checker:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def __call__(self, name: str, ok: bool, detail: str = "") -> None:
        log.info("%s  %s", "PASS" if ok else "FAIL", name)
        if not ok:
            self.failures.append(f"{name} {detail}".strip())


def run_checks(client: Client, data_dir: Path) -> list[str]:
    check = Checker()

    status, _ = client.request("/api/docs")
    check("API docs are served", status == 200, f"(got {status})")
    status, _ = client.request("/")
    check("The API does not serve a frontend", status == 404, f"(got {status})")

    status, body = client.request("/api/auth/me")
    me = json.loads(body) if status == 200 else {}
    check("/api/auth/me answers without signing in", status == 200, f"(got {status})")
    check(
        "The local operator is an administrator with permissions",
        me.get("user", {}).get("role") == "admin" and bool(me.get("permissions")),
    )
    check("/api/auth/me exposes no secrets", not any(m in body for m in SECRET_MARKERS))
    check("No first-run password file is written", not (data_dir / "initial-admin.txt").exists())
    status, _ = client.request("/api/auth/login", {"email": "x@example.com", "password": "x"})
    check("Login endpoint is disabled (410)", status == 410, f"(got {status})")
    status, _ = client.request("/api/auth/password", {"password": "x"})
    check("Password endpoint is disabled (410)", status == 410, f"(got {status})")
    status, _ = client.request("/api/auth/logout", {})
    check("Logout is harmless", status < 500, f"(got {status})")
    status, _ = client.request("/api/auth/logout", {}, headers={"Accept": "application/json"})
    check("Mutating requests need the CSRF header", status == 403, f"(got {status})")
    status, _ = client.request("/api/hooks/workflow", {}, headers={"Accept": "application/json"})
    check(
        "The workflow webhook refuses a request without its secret",
        status in (401, 403, 404, 503),
        f"(got {status})",
    )

    status, body = client.request("/api/home")
    check("/api/home answers without signing in", status == 200, f"(got {status})")
    if status == 200:
        home = json.loads(body)
        check(
            "/api/home has the expected fields",
            HOME_KEYS <= set(home),
            f"(missing {sorted(HOME_KEYS - set(home))})",
        )
        check("/api/home uses a 28-day window", home.get("window", {}).get("days") == 28)
        check(
            "/api/home reports no invented data on an empty database",
            home.get("reports") == []
            and home.get("approvals") == []
            and home.get("jobs") == []
            and all(
                m["value"] is None and m["source"]["kind"] is None for m in home.get("metrics", [])
            ),
        )
        check("/api/home exposes no secrets", not any(m in body for m in SECRET_MARKERS))
    status, _ = client.request("/api/home?brand=nope")
    check("/api/home rejects an unknown brand", status == 400, f"(got {status})")
    return check.failures


def run_web_checks(web: Client) -> list[str]:
    check = Checker()
    for route in WEB_ROUTES:
        status, body = web.request(route, headers={})
        check(
            f"Frontend route {route} renders",
            status == 200 and "Flowmerce" in body,
            f"(got {status})",
        )
    for route in WEB_MISSING:
        status, body = web.request(route, headers={})
        check(
            f"Frontend route {route} is a normal not-found page",
            status == 404 and "Back to Home" in body,
            f"(got {status})",
        )
    status, _ = web.request("/login", headers={})
    check(
        "/login redirects to Home",
        status == 200 and web.final_url.rstrip("/") == web.base,
        f"(ended at {web.final_url})",
    )
    status, body = web.request("/api/auth/me")
    check(
        "/api is forwarded to the Python backend",
        status == 200 and '"permissions"' in body,
        f"(got {status})",
    )
    return check.failures


def remove_tree(path: Path) -> None:
    """Delete the throwaway folder.

    On Windows the database file can stay locked for a moment after the app exits.
    """
    for _ in range(10):
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return
        time.sleep(0.5)
    log.warning("Could not remove %s; delete it manually.", path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Boot Flowmerce on a throwaway folder and probe it."
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="also start the built Next.js frontend and check its routes",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=API_PORT,
        help="API port for --web; it must match the FLOWMERCE_API_ORIGIN the frontend was built with",
    )
    parser.add_argument(
        "--timeout", type=float, default=60, help="Seconds to wait for each service to start"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    frontend = Path(__file__).resolve().parent.parent / "frontend"
    next_bin = frontend / "node_modules" / "next" / "dist" / "bin" / "next"
    node = shutil.which("node")
    if args.web and not (
        (frontend / ".next" / "BUILD_ID").is_file() and next_bin.is_file() and node
    ):
        log.error(
            "--web needs Node.js and a built frontend: run `npm ci && npm run build` in frontend/ first."
        )
        return 1

    if args.web:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", args.api_port)) == 0:
                log.error("Port %d is already in use; stop the other process first.", args.api_port)
                return 1

    tmp = Path(tempfile.mkdtemp(prefix="flowmerce-smoke-"))
    procs: list[subprocess.Popen] = []
    try:
        port = args.api_port if args.web else free_port()
        env = {k: v for k, v in os.environ.items() if k not in SECRET_ENV}
        env.update(
            FLOWMERCE_ROOT=str(tmp),
            HOST="127.0.0.1",
            PORT=str(port),
            SCHEDULER="false",
            ALLOW_LIVE_PUBLISH="false",
        )
        server_log = tmp / "server.log"
        with server_log.open("w", encoding="utf-8") as out:
            api_proc = subprocess.Popen(  # noqa: S603 - fixed argument list, no user input
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "flowmerce.modules.seo.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--log-level",
                    "warning",
                ],
                cwd=tmp,
                env=env,
                stdout=out,
                stderr=subprocess.STDOUT,
            )
        procs.append(api_proc)
        client = Client(f"http://127.0.0.1:{port}")
        if not wait_ready(client, api_proc, args.timeout):
            log.error(
                "The app did not start. Last server output:\n%s",
                server_log.read_text(encoding="utf-8", errors="replace")[-2000:],
            )
            return 1
        failures = run_checks(client, tmp / "data")
        if args.web:
            web_port = free_port()
            web_log = tmp / "web.log"
            with web_log.open("w", encoding="utf-8") as out:
                web_proc = subprocess.Popen(  # noqa: S603 - fixed argument list, no user input
                    [str(node), str(next_bin), "start", "-H", "127.0.0.1", "-p", str(web_port)],
                    cwd=frontend,
                    env={**env, "NEXT_TELEMETRY_DISABLED": "1"},
                    stdout=out,
                    stderr=subprocess.STDOUT,
                )
            procs.append(web_proc)
            web = Client(f"http://127.0.0.1:{web_port}")
            if not wait_ready(web, web_proc, args.timeout, "/"):
                log.error(
                    "The frontend did not start. Last output:\n%s",
                    web_log.read_text(encoding="utf-8", errors="replace")[-2000:],
                )
                return 1
            failures += run_web_checks(web)
        if failures:
            log.error("%d check(s) failed:\n  - %s", len(failures), "\n  - ".join(failures))
            return 1
        log.info("All smoke checks passed.")
        return 0
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        remove_tree(tmp)


if __name__ == "__main__":
    sys.exit(main())
