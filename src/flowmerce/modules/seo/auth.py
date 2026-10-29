"""Sessions: a random token in an HttpOnly, SameSite=Strict cookie; the database keeps only its SHA-256.
Passwords are scrypt hashes (same format as the earlier build). Mutating requests must carry the
X-Requested-With header, which a cross-site form cannot set — that is the CSRF guard."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import Request, Response

from .config import config
from .db import get, now, run
from .permissions import can
from .util import HttpError, sha256

COOKIE = "bo_session"


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=16384, r=8, p=1, dklen=64, maxmem=64 * 1024 * 1024)
    return f"scrypt$16384${base64.b64encode(salt).decode()}${base64.b64encode(h).decode()}"


def verify_password(pw: str, stored: str) -> bool:
    parts = str(stored).split("$")
    if len(parts) != 4 or parts[0] != "scrypt":
        return False
    salt, expected = base64.b64decode(parts[2]), base64.b64decode(parts[3])
    actual = hashlib.scrypt(pw.encode(), salt=salt, n=int(parts[1]), r=8, p=1, dklen=len(expected), maxmem=64 * 1024 * 1024)
    return hmac.compare_digest(expected, actual)


def validate_password(pw: object) -> str | None:
    if not isinstance(pw, str) or len(pw) < 12:
        return "Password must be at least 12 characters."
    return None


def create_session(response: Response, user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=config.session_hours)
    run("INSERT INTO sessions (id, user_id, created_at, expires_at) VALUES (?,?,?,?)",
        sha256(token), user_id, now(), expires.isoformat(timespec="milliseconds").replace("+00:00", "Z"))
    run("DELETE FROM sessions WHERE expires_at < ?", now())
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=config.cookie_secure,
                        path="/", max_age=config.session_hours * 3600)


def destroy_session(request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        run("DELETE FROM sessions WHERE id = ?", sha256(token))
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict", secure=config.cookie_secure)


def load_user(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    row = get(
        """SELECT u.id, u.email, u.name, u.role FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.id = ? AND s.expires_at > ? AND u.active = 1""",
        sha256(token), now(),
    )
    return row


def require_user(request: Request) -> dict:
    u = getattr(request.state, "user", None)
    if not u:
        raise HttpError(401, "Sign in to continue.", "unauthenticated")
    return u


def require_perm(request: Request, perm: str) -> dict:
    u = require_user(request)
    if not can(u["role"], perm):
        raise HttpError(403, "Your role does not allow this action.", "forbidden", {"perm": perm})
    return u


# Login throttling: 8 failures per email+IP in 15 minutes locks that pair out for the window.
_failures: dict[str, list[float]] = {}


def login_throttle(key: str) -> None:
    cutoff = time.time() - 15 * 60
    lst = [t for t in _failures.get(key, []) if t > cutoff]
    _failures[key] = lst
    if len(lst) >= 8:
        raise HttpError(429, "Too many failed sign-in attempts. Try again in 15 minutes.", "throttled")


def login_failed(key: str) -> None:
    _failures.setdefault(key, []).append(time.time())


def login_succeeded(key: str) -> None:
    _failures.pop(key, None)
