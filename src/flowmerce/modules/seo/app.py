"""FastAPI application: security headers, session loading, CSRF guard, the /api router, and the built
React app (frontend/web/dist) served for every other path."""
from __future__ import annotations

import secrets
import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import api
from .audit import audit
from .auth import hash_password, load_user
from .config import config
from .db import get, now, open_db, run
from .services.runs import sweep_interrupted_runs
from .services.scheduler import start_scheduler
from .util import HttpError

CSP = "; ".join([
    "default-src 'self'", "script-src 'self'", "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com", "img-src 'self' https: data:", "connect-src 'self'",
    "frame-src 'self' about:", "frame-ancestors 'none'", "base-uri 'none'", "form-action 'self'",
])
DIST = config.root / "frontend" / "web" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="Blog Ops", docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api"):
            request.state.user = load_user(request)
            if request.method not in ("GET", "HEAD", "OPTIONS") and not path.startswith("/api/hooks/") \
                    and request.headers.get("X-Requested-With") != "blog-ops":
                resp = JSONResponse({"error": "Missing request header.", "code": "csrf"}, status_code=403)
            else:
                resp = await call_next(request)
            resp.headers["Cache-Control"] = "no-store"
        else:
            resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not path.startswith("/api/docs"):
            resp.headers["Content-Security-Policy"] = CSP
        return resp

    @app.exception_handler(HttpError)
    async def http_error(_request: Request, e: HttpError):
        return JSONResponse({"error": e.message, "code": e.code, "details": e.details}, status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def bad_request(_request: Request, e: RequestValidationError):
        return JSONResponse({"error": "The request body is not valid JSON.", "code": "bad_request"}, status_code=400)

    @app.exception_handler(Exception)
    async def server_error(request: Request, e: Exception):
        ref = secrets.token_hex(4)
        print(f"[{ref}] {request.method} {request.url.path}\n{traceback.format_exc()}")
        return JSONResponse({"error": f"Something went wrong on the server (ref {ref}). {str(e)[:300]}".strip(), "code": "server_error"}, status_code=500)

    app.include_router(api)

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
    def api_not_found(rest: str):
        raise HttpError(404, "Not found.")

    if DIST.exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            f = (DIST / full_path).resolve()
            if full_path and f.is_file() and DIST.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(DIST / "index.html")
    return app


def bootstrap_admin() -> None:
    """First start: create the admin from ADMIN_EMAIL / ADMIN_PASSWORD, or with a generated password
    written to data/initial-admin.txt (git-ignored) so it never appears in logs."""
    if get("SELECT 1 FROM users LIMIT 1"):
        return
    email = (config.admin_email or "admin@blog-ops.local").lower()
    password = config.admin_password or secrets.token_urlsafe(12)
    run("INSERT INTO users (email, name, role, password_hash, created_at) VALUES (?,?,?,?,?)", email, "Administrator", "admin", hash_password(password), now())
    audit(None, "user.bootstrap_admin", "user", summary=email)
    if not config.admin_password:
        f = Path(config.data_dir) / "initial-admin.txt"
        f.write_text(f"First admin account\nemail: {email}\npassword: {password}\n\nSign in, create named users, change this password, then delete this file.\n", encoding="utf-8")
        print(f"Created the first admin ({email}). Its password is in {f}")


def startup(with_scheduler: bool = True) -> FastAPI:
    open_db()
    bootstrap_admin()
    swept = sweep_interrupted_runs()
    if swept:
        print(f"Marked {swept} interrupted workflow run(s) as failed.")
    if with_scheduler and config.scheduler:
        start_scheduler()
    return create_app()
