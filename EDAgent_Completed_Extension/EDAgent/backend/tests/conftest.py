"""
Pytest fixtures for EDAgent.

The environment is configured *before* the app is imported so every test run uses a throw-away
SQLite database and temporary storage folders, never the developer's real data. Rate limiting
is switched off here and tested explicitly in its own test.
"""

import os
import shutil
import tempfile
import uuid

_TMP = tempfile.mkdtemp(prefix="edagent-tests-")
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": f"sqlite+aiosqlite:///{_TMP}/test.db",
        "LOCAL_STORAGE_PATH": f"{_TMP}/uploads",
        "EXPORTS_STORAGE_PATH": f"{_TMP}/exports",
        "SAMPLES_PATH": os.path.join(_BACKEND, "data", "samples"),
        "RATE_LIMIT_PER_MINUTE": "0",
        "AUTH_RATE_LIMIT_PER_MINUTE": "0",
        "ANALYSIS_RATE_LIMIT_PER_MINUTE": "0",
        "LLM_PROVIDER": "mock",
        "LLM_API_KEY": "",
        "SECRET_KEY": "test-secret-key-that-is-long-enough-for-hs256-0123456789",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.ai.llm import set_llm_client_override  # noqa: E402

PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session")
def _session_client():
    # One client (one event loop) for the whole run keeps the async SQLite engine happy.
    with TestClient(app) as c:
        yield c
    shutil.rmtree(_TMP, ignore_errors=True)


def register_user(c: TestClient, email: str | None = None) -> dict:
    """Creates a user and returns {'headers': {...}, 'id': ..., 'email': ...}."""
    email = email or f"user-{uuid.uuid4().hex[:10]}@example.com"
    r = c.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "full_name": "Test User"}, headers={})
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    return {"headers": {"Authorization": f"Bearer {data['access_token']}"}, "id": data["user"]["id"], "email": email}


@pytest.fixture
def client(_session_client):
    """Test client already signed in as a fresh user (headers are replaced for each test)."""
    user = register_user(_session_client)
    _session_client.headers.pop("Authorization", None)
    _session_client.headers.update(user["headers"])
    _session_client.current_user = user  # type: ignore[attr-defined]
    yield _session_client
    _session_client.headers.pop("Authorization", None)


@pytest.fixture
def anon_client(_session_client):
    """Client with no credentials."""
    saved = _session_client.headers.pop("Authorization", None)
    yield _session_client
    if saved:
        _session_client.headers["Authorization"] = saved


@pytest.fixture
def second_user(_session_client):
    """Another registered user; use `headers=second_user['headers']` per request."""
    return register_user(_session_client)


@pytest.fixture(autouse=True)
def _reset_llm():
    set_llm_client_override(None)
    yield
    set_llm_client_override(None)


@pytest.fixture
def sample_csv_path() -> str:
    """Absolute path to the benchmark sample dataset shipped with the repository."""
    root = os.path.abspath(os.path.join(_BACKEND, ".."))
    path = os.path.join(root, "data", "samples", "baseline_benchmark.csv")
    assert os.path.exists(path), f"Benchmark file missing at: {path}"
    return path


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td
