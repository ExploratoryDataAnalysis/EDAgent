"""Security behaviour: auth, SSRF on URL import, rate limiting, upload limits, export sanitising, secrets."""

import io
import json

import pytest

from app.core.config import settings
from app.core.security import hash_password, verify_password
from tests.conftest import PASSWORD


def test_registration_login_and_password_handling(anon_client):
    c = anon_client
    email = "alice.sec@example.com"
    assert c.post("/api/v1/auth/register", json={"email": email, "password": "short"}).status_code == 422
    assert c.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD}).status_code == 201
    assert c.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD}).status_code == 409
    bad = c.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
    unknown = c.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"})
    assert bad.status_code == unknown.status_code == 401 and bad.json()["message"] == unknown.json()["message"]
    ok = c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).json()["data"]
    assert "hashed_password" not in json.dumps(ok)
    assert c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ok['access_token']}"}).json()["data"]["email"] == email
    assert c.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.token"}).status_code == 401
    h = hash_password(PASSWORD)
    assert h != PASSWORD and verify_password(PASSWORD, h) and not verify_password("x", h)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/data.csv", "http://localhost:8000/data.csv", "http://169.254.169.254/latest/meta-data",
    "http://[::1]/x.csv", "http://10.0.0.5/x.csv", "file:///etc/passwd", "ftp://example.com/x.csv", "http://user:pw@example.com/x.csv",
    "http://[::ffff:127.0.0.1]/x.csv",
])
def test_url_import_blocks_internal_targets(client, url):
    r = client.post("/api/v1/datasets/import-url", json={"url": url})
    assert r.status_code == 400 and r.json()["error_code"] == "URL_NOT_ALLOWED"


def test_url_import_redirect_to_internal_is_blocked(client, monkeypatch):
    """A public-looking URL that redirects to an internal address must be refused on the second hop."""
    import httpx

    from app.core import security
    from app.services import dataset_service

    real = security.validate_url_safe
    monkeypatch.setattr(dataset_service, "validate_url_safe", lambda u: (True, "") if "public.example" in u else real(u))

    def handler(request: httpx.Request):
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})

    orig = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: orig(transport=httpx.MockTransport(handler), **kw))
    r = client.post("/api/v1/datasets/import-url", json={"url": "http://public.example/data.csv"})
    assert r.status_code == 400 and r.json()["error_code"] == "URL_NOT_ALLOWED"


def test_url_import_success_and_size_limit(client, monkeypatch):
    import httpx

    from app.services import dataset_service

    monkeypatch.setattr(dataset_service, "validate_url_safe", lambda u: (True, ""))
    body = b"a,b\n1,2\n3,4\n"
    orig = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: orig(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=body)), **kw))
    r = client.post("/api/v1/datasets/import-url", json={"url": "http://public.example/files/data.csv"})
    assert r.status_code == 200 and r.json()["data"]["name"].endswith(".csv")
    monkeypatch.setattr(settings, "URL_IMPORT_MAX_MB", 0)
    r = client.post("/api/v1/datasets/import-url", json={"url": "http://public.example/files/data.csv"})
    assert r.status_code == 413


def test_upload_limits_and_type_checks(client, monkeypatch):
    assert client.post("/api/v1/datasets/upload", files={"file": ("x.exe", io.BytesIO(b"MZ"), "application/octet-stream")}).status_code == 400
    assert client.post("/api/v1/datasets/upload", files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")}).status_code == 400
    fake_xlsx = client.post("/api/v1/datasets/upload", files={"file": ("fake.xlsx", io.BytesIO(b"not a zip"), "application/octet-stream")})
    assert fake_xlsx.status_code == 400
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 0)
    assert client.post("/api/v1/datasets/upload", files={"file": ("big.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")}).status_code == 413
    traversal = None
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 100)
    r = client.post("/api/v1/datasets/upload", files={"file": ("../../etc/evil.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")})
    assert r.status_code == 200 and ".." not in r.json()["data"]["storage_uri"]


def test_dataset_quota(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_DATASETS_PER_USER", 1)
    assert client.post("/api/v1/datasets/upload", files={"file": ("a.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")}).status_code == 200
    r = client.post("/api/v1/datasets/upload", files={"file": ("b.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")})
    assert r.status_code == 409 and r.json()["error_code"] == "QUOTA_EXCEEDED"


def test_rate_limiting(anon_client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_PER_MINUTE", 3)
    codes = [anon_client.post("/api/v1/auth/login", json={"email": "rl@example.com", "password": "whatever123"}).status_code for _ in range(6)]
    assert codes[:3] == [401, 401, 401] and 429 in codes[3:]
    r = anon_client.post("/api/v1/auth/login", json={"email": "rl@example.com", "password": "whatever123"})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_exports_neutralise_spreadsheet_formulas(client):
    csv = "name,score\n=HYPERLINK(\"http://evil.test\"),1\n+cmd|' /C calc'!A0,2\n@SUM(A1),3\nsafe,4\n"
    ds = client.post("/api/v1/datasets/upload", files={"file": ("inj.csv", io.BytesIO(csv.encode()), "text/csv")}).json()["data"]["dataset_id"]
    sid = client.post("/api/v1/sessions", json={"dataset_id": ds}).json()["data"]["id"]
    res = client.post("/api/v1/analysis/execute", json={"session_id": sid, "plan": {"operation": "filter_rows", "target_columns": ["name", "score"],
                      "filters": {"logic": "and", "conditions": [{"column": "score", "operator": "gte", "value": 1}]}}}).json()["data"]
    out = client.get(f"/api/v1/exports/results/{res['id']}/tables/0?format=csv").content.decode("utf-8-sig")
    for line in out.splitlines()[1:]:
        assert not line.lstrip('"').startswith(("=", "+", "@")), line
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(client.get(f"/api/v1/exports/results/{res['id']}/tables/0?format=xlsx").content))
    for row in wb.active.iter_rows(min_row=2, values_only=True):
        assert not str(row[0]).startswith(("=", "+", "@"))
        assert all(c.data_type != "f" for c in next(wb.active.iter_rows(min_row=2, max_row=2)))


def test_no_secrets_in_api_responses(client, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "sk-super-secret-value")
    blob = json.dumps(client.get("/api/v1/chat/status").json()) + json.dumps(client.get("/api/v1/health").json()) + json.dumps(client.get("/api/v1/auth/me").json())
    assert "sk-super-secret-value" not in blob and settings.SECRET_KEY not in blob


def test_unexpected_errors_do_not_leak_internals(client, monkeypatch):
    from app.services import dataset_service

    def boom(*a, **k):
        raise RuntimeError("secret internal path /srv/app/db.sqlite")

    monkeypatch.setattr(dataset_service, "list_samples", boom)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        c.headers.update(client.headers)
        r = c.get("/api/v1/datasets/samples")
    assert r.status_code == 500 and "secret internal path" not in r.text
