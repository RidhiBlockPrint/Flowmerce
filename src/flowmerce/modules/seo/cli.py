"""Create or reset a user from the command line:
    python -m flowmerce.modules.seo.cli --email you@example.com --name "Your Name" --role admin
The password is read from BLOG_OPS_PASSWORD, or generated and printed once. Roles: admin, seo_manager, reviewer."""
from __future__ import annotations

import argparse
import os
import secrets
import sys

from .audit import audit
from .auth import hash_password, validate_password
from .db import get, now, open_db, run
from .permissions import is_role


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--email", required=True)
    p.add_argument("--name", default="")
    p.add_argument("--role", default="seo_manager")
    a = p.parse_args()
    email = a.email.strip().lower()
    if not is_role(a.role):
        sys.exit("Role must be admin, seo_manager or reviewer.")
    password = os.environ.get("BLOG_OPS_PASSWORD") or ""
    generated = not password
    password = password or secrets.token_urlsafe(12)
    if err := validate_password(password):
        sys.exit(err)
    open_db()
    existing = get("SELECT id FROM users WHERE email = ?", email)
    if existing:
        run("UPDATE users SET name = ?, role = ?, password_hash = ?, active = 1 WHERE id = ?", a.name or email, a.role, hash_password(password), existing["id"])
        run("DELETE FROM sessions WHERE user_id = ?", existing["id"])
    else:
        run("INSERT INTO users (email, name, role, password_hash, created_at) VALUES (?,?,?,?,?)", email, a.name or email, a.role, hash_password(password), now())
    audit(None, "user.reset_cli" if existing else "user.create_cli", "user", summary=f"{email} as {a.role}")
    print(f"{'Updated' if existing else 'Created'} {email} ({a.role})." + (f" Password: {password}" if generated else ""))


if __name__ == "__main__":
    main()
