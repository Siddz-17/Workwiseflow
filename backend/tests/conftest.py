import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="wfw-tests-")
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
        "AUTH_MODE": "dev",
        "APP_ENV": "test",
        "LLM_PROVIDER": "local",
        "EMBEDDING_PROVIDER": "local",
        "GEMINI_API_KEY": "",
        "STORAGE_BACKEND": "local",
        "LOCAL_STORAGE_DIR": f"{_tmp}/uploads",
        "REDIS_URL": "",
        "STALE_AFTER_DAYS": "120",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, get_engine, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    init_db()
    yield
    Base.metadata.drop_all(get_engine())


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def auth(email: str) -> dict:
    return {"Authorization": f"Bearer dev:{email}"}


@pytest.fixture
def alice():
    return auth("alice@acme.test")


@pytest.fixture
def bob():
    return auth("bob@acme.test")


@pytest.fixture
def workspace(client, alice):
    r = client.post("/api/workspaces", json={"name": "Acme"}, headers=alice)
    assert r.status_code == 201, r.text
    return r.json()["id"]
