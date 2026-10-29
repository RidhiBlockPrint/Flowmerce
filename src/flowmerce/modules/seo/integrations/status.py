"""One row per integration (and brand): configured or not, mode, last attempt, last success, last error.
Failures are also written to the audit log so they are not lost when the next sync works."""
from __future__ import annotations

import json

from ..audit import audit
from ..db import Row, all_rows, get, now, run
from ..util import safe_json


def mark_attempt(key: str, brand_id: str, mode: str) -> None:
    run("""INSERT INTO integration_status (key, brand_id, status, mode, last_attempt_at) VALUES (?,?,?,?,?)
           ON CONFLICT(key, brand_id) DO UPDATE SET status='syncing', mode=excluded.mode, last_attempt_at=excluded.last_attempt_at""",
        key, brand_id, "syncing", mode, now())


def mark_success(key: str, brand_id: str, mode: str, details: dict | None = None) -> None:
    t = now()
    run("""INSERT INTO integration_status (key, brand_id, status, mode, last_attempt_at, last_success_at, last_error, details_json)
           VALUES (?,?,?,?,?,?,NULL,?)
           ON CONFLICT(key, brand_id) DO UPDATE SET status='connected', mode=excluded.mode, last_attempt_at=excluded.last_attempt_at,
             last_success_at=excluded.last_success_at, last_error=NULL, details_json=excluded.details_json""",
        key, brand_id, "connected", mode, t, t, json.dumps(details or {}, default=str))


def mark_error(key: str, brand_id: str, mode: str, err: object) -> None:
    message = str(err)
    run("""INSERT INTO integration_status (key, brand_id, status, mode, last_attempt_at, last_error) VALUES (?,?,?,?,?,?)
           ON CONFLICT(key, brand_id) DO UPDATE SET status='error', mode=excluded.mode, last_attempt_at=excluded.last_attempt_at, last_error=excluded.last_error""",
        key, brand_id, "error", mode, now(), message[:1000])
    audit(None, "integration.failure", "integration", key, brand_id, message[:300])


def mark_pending(key: str, brand_id: str, reason: str) -> None:
    run("""INSERT INTO integration_status (key, brand_id, status, mode, details_json) VALUES (?,?,?,?,?)
           ON CONFLICT(key, brand_id) DO UPDATE SET status='pending_setup', details_json=excluded.details_json""",
        key, brand_id, "pending_setup", "", json.dumps({"reason": reason}))


def status_of(key: str, brand_id: str) -> Row | None:
    r = get("SELECT * FROM integration_status WHERE key = ? AND brand_id = ?", key, brand_id)
    return {**r, "details": safe_json(r["details_json"], {})} if r else None


def all_statuses() -> list[Row]:
    return [{**r, "details": safe_json(r["details_json"], {})} for r in all_rows("SELECT * FROM integration_status")]
