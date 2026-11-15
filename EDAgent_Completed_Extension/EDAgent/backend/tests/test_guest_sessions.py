import threading
import time
import uuid
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.sync_db import sync_session
from app.models.analysis import AnalysisResult
from app.models.job import BackgroundJob
from app.models.user import GuestLease, User
from app.services import guest_sessions
from app.services.analysis import engine
from app.services.export import report
from app.services.jobs import runner
from tests.conftest import register_user

API = "/api/v1"
GUEST = f"{API}/auth/guest-session"


def start(c):
    response = c.post(GUEST)
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    data = response.json()["data"]
    return uuid.UUID(data["user"]["id"]), {"Authorization": f"Bearer {data['access_token']}"}


def upload(c, auth, seed):
    return c.post(f"{API}/datasets/upload", headers=auth, files={
        "file": ("invented.csv", f"category,amount\nA,{seed}\nA,{seed+4}\nB,{seed+8}\nB,{seed+12}\n", "text/csv"),
    })


def workspace(c, auth, seed):
    res = upload(c, auth, seed)
    assert res.status_code == 200, res.text
    dataset = res.json()["data"]["dataset_id"]
    res = c.post(f"{API}/sessions", headers=auth, json={"dataset_id": dataset, "title": f"Invented {seed}"})
    assert res.status_code == 201, res.text
    session = res.json()["data"]["id"]
    req = {"session_id": session, "plan": {"operation": "descriptive_stats", "column": "amount"}}
    res = c.post(f"{API}/analysis/execute", headers=auth, json=req)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["dataset_id"] == dataset
    assert data["tables"][0]["rows"][0]["median"] == seed + 6
    return dataset, session, data["id"], req


def test_identical_uploads_keep_account_results_on_their_own_dataset(anon_client):
    first = register_user(anon_client)["headers"]
    second = register_user(anon_client)["headers"]
    first_dataset, _, _, request = workspace(anon_client, first, 25)
    second_dataset, _, _, _ = workspace(anon_client, second, 25)
    assert first_dataset != second_dataset
    repeated = anon_client.post(f"{API}/analysis/execute", headers=first, json=request)
    assert repeated.json()["data"]["dataset_id"] == first_dataset
    assert repeated.json()["data"]["execution"]["cache_hit"] is True


def wait_job(c, auth, job_id):
    for _ in range(100):
        response = c.get(f"{API}/jobs/{job_id}", headers=auth)
        assert response.status_code == 200, response.text
        if response.json()["data"]["status"] in ("SUCCESS", "FAILURE", "REVOKED"):
            return response.json()["data"]
        time.sleep(0.05)
    raise AssertionError("Job did not finish")


def generate_report(c, auth, session):
    res = c.post(f"{API}/reports/generate", headers=auth, json={
        "session_id": session, "title": "Invented report", "format": "html",
        "included_sections": ["cover", "user_analyses"],
    })
    assert res.status_code == 202, res.text
    return res.json()["data"]


def test_guest_owners_limits_and_clear(anon_client, monkeypatch):
    c = anon_client
    assert c.post(GUEST).status_code == 403
    monkeypatch.setattr(settings, "ALLOW_GUEST_SESSIONS", True)
    owners = [start(c), start(c)]
    account = register_user(c)
    owners.append((uuid.UUID(account["id"]), account["headers"]))
    assert len({owner for owner, _ in owners}) == 3
    workspaces = [workspace(c, auth, seed) for (_, auth), seed in zip(owners, (10, 30, 70))]

    for i, ((owner, auth), (dataset, session, result, _)) in enumerate(zip(owners, workspaces)):
        other = owners[(i + 1) % 3][1]
        generated = generate_report(c, auth, session)
        assert wait_job(c, auth, generated["job_id"])["status"] == "SUCCESS"
        download = f"{API}/reports/{generated['report_id']}/download"
        table = f"{API}/exports/results/{result}/tables/0"
        assert c.get(download, headers=auth).status_code == 200
        assert c.get(table, headers=auth).status_code == 200
        for path in (download, table, f"{API}/datasets/{dataset}/preview", f"{API}/sessions/{session}",
                     f"{API}/analysis/results/{result}", f"{API}/jobs/{generated['job_id']}"):
            assert c.get(path, headers=other).status_code == 404
            assert c.get(path).status_code == 401
        assert Path(settings.LOCAL_STORAGE_PATH, str(owner), dataset, "invented.csv").is_file()
        if i < 2:
            assert c.get(download, headers=auth).headers["cache-control"] == "no-store"
            assert c.get(f"{API}/chat/status", headers=auth).status_code == 403
            assert c.get(f"{API}/auth/me", headers=auth).json()["data"]["guest"]["max_datasets"] == settings.GUEST_MAX_DATASETS

    owner, auth = owners[0]
    assert c.get(f"{API}/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert c.delete(GUEST, headers=account["headers"]).status_code == 401
    monkeypatch.setattr(settings, "GUEST_MAX_UPLOAD_BYTES", 64)
    response = c.post(f"{API}/datasets/upload", headers=auth, files={"file": ("too-big.csv", b"x,y\n" * 32)})
    assert response.status_code == 413
    response = c.post(f"{API}/datasets/upload", headers=auth, files={"file": ("unsupported.xlsx", b"invalid")})
    assert response.status_code == 400
    assert len(list(Path(settings.LOCAL_STORAGE_PATH, str(owner)).iterdir())) == 1
    monkeypatch.setattr(settings, "GUEST_MAX_DATASETS", 1)
    assert upload(c, auth, 50).status_code == 409
    monkeypatch.setattr(settings, "GUEST_MAX_ACTIONS", 1)
    assert c.post(f"{API}/analysis/execute", headers=auth, json=workspaces[0][3]).status_code == 429

    monkeypatch.setattr(settings, "ALLOW_GUEST_SESSIONS", False)
    assert c.post(GUEST).status_code == 403
    assert c.delete(GUEST, headers=auth).status_code == 204
    assert c.delete(GUEST, headers=auth).status_code == 204
    assert c.get(f"{API}/auth/me", headers=auth).status_code == 401
    assert not Path(settings.LOCAL_STORAGE_PATH, str(owner)).exists()
    assert not Path(settings.EXPORTS_STORAGE_PATH, "reports", str(owner)).exists()
    assert c.get(f"{API}/analysis/results/{workspaces[2][2]}", headers=account["headers"]).status_code == 200
    assert c.delete(GUEST, headers=owners[1][1]).status_code == 204


def test_guest_revocation_during_worker_and_restart(anon_client, monkeypatch):
    c = anon_client
    monkeypatch.setattr(settings, "ALLOW_GUEST_SESSIONS", True)
    owner, auth = start(c)
    _, session, result_id, payload = workspace(c, auth, 100)

    computing = threading.Event()
    resume = threading.Event()
    computed = []
    original = engine.run_analysis

    def paused(*args, **kwargs):
        computing.set()
        assert resume.wait(10)
        result = original(*args, **kwargs)
        computed.append(result.id)
        return result

    monkeypatch.setattr(engine, "run_analysis", paused)
    res = c.post(f"{API}/analysis/execute-async", headers=auth, json=payload)
    assert res.status_code == 202, res.text
    job_id = uuid.UUID(res.json()["data"]["job_id"])
    try:
        assert computing.wait(5)
        assert c.post(f"{API}/analysis/execute-async", headers=auth, json=payload).status_code == 429
        assert c.delete(GUEST, headers=auth).status_code == 204
        assert c.get(f"{API}/analysis/results/{result_id}", headers=auth).status_code == 401
    finally:
        resume.set()
    runner._pool.submit(lambda: None).result(10)
    for _ in range(100):
        if computed:
            break
        time.sleep(0.02)
    assert computed
    with sync_session() as db:
        assert db.get(User, owner) is None
        assert db.get(BackgroundJob, job_id) is None
        assert db.get(AnalysisResult, computed[0]) is None

    # A restarted worker cannot replay a missing job or restore the deleted state.
    attempted = threading.Event()
    runner.submit(job_id, lambda _: attempted.set(), guest=True)
    monkeypatch.setattr(engine, "run_analysis", original)
    owner, auth = start(c)
    _, session, _, _ = workspace(c, auth, 140)
    orphan = Path(settings.LOCAL_STORAGE_PATH, str(owner), str(uuid.uuid4()), "partial.csv")
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"partial")
    c.portal.call(guest_sessions.recover_after_restart)
    assert not orphan.exists()
    assert not attempted.is_set()

    # Expiry during report rendering must prevent file publication.
    rendering = threading.Event()
    resume.clear()
    render = report.render_html

    def paused_render(*args, **kwargs):
        rendering.set()
        assert resume.wait(10)
        return render(*args, **kwargs)

    monkeypatch.setattr(report, "render_html", paused_render)
    queued = generate_report(c, auth, session)
    try:
        assert rendering.wait(5)
        with sync_session() as db:
            db.get(GuestLease, owner).expires_at = guest_sessions.timestamp()
        assert c.get(f"{API}/jobs/{queued['job_id']}", headers=auth).status_code == 401
        c.portal.call(guest_sessions.recover_after_restart)
        assert not Path(settings.LOCAL_STORAGE_PATH, str(owner)).exists()
    finally:
        resume.set()
    runner._pool.submit(lambda: None).result(10)
    assert c.delete(GUEST, headers=auth).status_code == 204
    assert not Path(settings.EXPORTS_STORAGE_PATH, "reports", str(owner)).exists()
    with sync_session() as db:
        assert db.scalar(select(GuestLease).where(GuestLease.user_id == owner)) is None
