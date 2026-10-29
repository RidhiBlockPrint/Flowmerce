from __future__ import annotations

import json
from typing import Any

from .db import now, run


def audit(user: dict | None, action: str, entity_type: str = "", entity_id: Any = "", brand_id: str = "",
          summary: str = "", details: Any = None, ip: str | None = None) -> None:
    """Append one line to the audit log. user=None means the scheduler, a webhook or the system acted.
    Never put tokens or passwords in details."""
    run(
        """INSERT INTO audit_log (ts, user_id, user_email, action, entity_type, entity_id, brand_id, summary, details_json, ip)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        now(), user["id"] if user else None, user["email"] if user else "system", action, entity_type,
        "" if entity_id is None else str(entity_id), brand_id or "", summary or "", json.dumps(details or {}, default=str), ip,
    )
