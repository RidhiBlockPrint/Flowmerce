"""Boot the real Flowmerce app on a throwaway data folder and probe it over HTTP.

Used by CI and runnable locally::

    python scripts/ci_smoke.py                          # API checks only
    python scripts/ci_smoke.py --dist frontend/web/dist # also checks the built UI is served

Safety: the app runs with FLOWMERCE_ROOT pointing at a fresh temporary folder, so it never reads
the repository's .env or data/, has no credentials, keeps the scheduler and live publishing off
and binds to 127.0.0.1. The only request that changes anything is the sign-in to the throwaway
instance. Exit code 0 means every check passed; 1 means at least one failed (each is printed).
"""

from __future__ import annotations

import argparse
import http.cookiejar
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


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Client:
    """Tiny HTTP client that keeps the session cookie."""

    def __init__(self, base: str) -> None:
        self.base = base
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def request(self, path: str, body: dict | None = None) -> tuple[int, str]:
        data = json.dumps(body).encode() if body is not None else None
        headers = dict(
            HEADERS, **({"Content-Type": "application/json"} if body is not None else {})
        )
        req = urllib.request.Request(  # noqa: S310 - fixed http://127.0.0.1 URL
            self.base + path,
            data=data,
            headers=headers,
            method="POST" if body is not None else "GET",
        )
        try:
            with self.opener.open(req, timeout=15) as r:  # noqa: S310 - fixed http://127.0.0.1 URL
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")


def wait_ready(client: Client, proc: subprocess.Popen, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        try:
            if client.request("/api/docs")[0] == 200:
                return True
        except OSError:
            pass
        time.sleep(0.5)
    return False


def first_admin(data_dir: Path) -> tuple[str, str]:
    """The throwaway instance writes its generated first-admin sign-in here; it is never printed."""
    values = dict(
        line.split(": ", 1)
        for line in (data_dir / "initial-admin.txt").read_text(encoding="utf-8").splitlines()
        if ": " in line
    )
    return values["email"], values["password"]


def run_checks(client: Client, data_dir: Path, with_ui: bool) -> list[str]:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        log.info("%s  %s", "PASS" if ok else "FAIL", name)
        if not ok:
            failures.append(f"{name} {detail}".strip())

    status, _ = client.request("/api/docs")
    check("API docs are served", status == 200, f"(got {status})")
    if with_ui:
        status, body = client.request("/login")
        check(
            "Built UI is served at /login", status == 200 and "Flowmerce" in body, f"(got {status})"
        )
    status, _ = client.request("/api/home")
    check("/api/home refuses an unauthenticated request", status == 401, f"(got {status})")
    status, _ = client.request("/api/auth/me")
    check("/api/auth/me refuses an unauthenticated request", status == 401, f"(got {status})")

    email, password = first_admin(data_dir)
    status, _ = client.request("/api/auth/login", {"email": email, "password": password})
    check("First admin can sign in", status == 200, f"(got {status})")
    status, body = client.request("/api/auth/me")
    check(
        "/api/auth/me works after sign-in and exposes no secrets",
        status == 200 and not any(m in body for m in SECRET_MARKERS),
        f"(got {status})",
    )

    status, body = client.request("/api/home")
    check("/api/home answers after sign-in", status == 200, f"(got {status})")
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
    return failures


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
        "--dist", type=Path, help="Built UI folder (frontend/web/dist) to serve and check"
    )
    parser.add_argument(
        "--timeout", type=float, default=40, help="Seconds to wait for the app to start"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.dist and not (args.dist / "index.html").is_file():
        log.error(
            "--dist %s has no index.html; build the UI first (npm run build in frontend/).",
            args.dist,
        )
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="flowmerce-smoke-"))
    proc: subprocess.Popen | None = None
    try:
        if args.dist:
            shutil.copytree(args.dist, tmp / "frontend" / "web" / "dist")
        port = free_port()
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
            proc = subprocess.Popen(  # noqa: S603 - fixed argument list, no user input
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
        client = Client(f"http://127.0.0.1:{port}")
        if not wait_ready(client, proc, args.timeout):
            log.error(
                "The app did not start. Last server output:\n%s",
                server_log.read_text(encoding="utf-8", errors="replace")[-2000:],
            )
            return 1
        failures = run_checks(client, tmp / "data", with_ui=bool(args.dist))
        if failures:
            log.error("%d check(s) failed:\n  - %s", len(failures), "\n  - ".join(failures))
            return 1
        log.info("All smoke checks passed.")
        return 0
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        remove_tree(tmp)


if __name__ == "__main__":
    sys.exit(main())
