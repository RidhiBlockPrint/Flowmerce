"""Shared fixtures for the SEO module tests (in-memory DB, three role users, network blocked). Loaded as a pytest plugin from tests/conftest.py."""
import os

import pytest

os.environ["SCHEDULER"] = "false"
os.environ.pop("ALLOW_LIVE_PUBLISH", None)

from flowmerce.modules.seo.auth import hash_password  # noqa: E402
from flowmerce.modules.seo.db import now, open_db, run  # noqa: E402

PASSWORD = "correct horse battery"


@pytest.fixture(scope="session", autouse=True)
def database():
    open_db(":memory:")
    users = {}
    for email, role in (("admin@test.local", "admin"), ("manager@test.local", "seo_manager"), ("reviewer@test.local", "reviewer")):
        uid = run("INSERT INTO users (email, name, role, password_hash, created_at) VALUES (?,?,?,?,?)",
                  email, email.split("@")[0], role, hash_password(PASSWORD), now()).last_id
        users[role] = {"id": uid, "email": email, "name": email.split("@")[0], "role": role}
    return users


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test may reach a real outside service."""
    httpx = pytest.importorskip("httpx")

    def blocked(*_a, **_k):
        raise RuntimeError("network disabled in tests")
    monkeypatch.setattr(httpx, "get", blocked)
    monkeypatch.setattr(httpx, "post", blocked)


@pytest.fixture
def users(database):
    return database
