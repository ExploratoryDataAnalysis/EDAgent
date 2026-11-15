from app.api.v1.endpoints import overview
from app.road_safety_release import digest
from tests.overview_fixture import FIXTURE_VERSION, write_decision, write_fixture

BASE = "/api/v1/analyser/samples"


def test_analyser_samples_and_withdrawal(anon_client, tmp_path, monkeypatch):
    path = write_fixture(tmp_path / "releases")
    ledger = tmp_path / "approvals.json"
    identity = digest(path / "manifest.json")
    monkeypatch.setenv("ROAD_SAFETY_RELEASE_ROOT", str(path.parent))
    monkeypatch.setenv("ROAD_SAFETY_APPROVALS", str(ledger))
    monkeypatch.setattr(overview, "MANIFEST_SHA256", identity)
    monkeypatch.setattr(overview, "VERSION", FIXTURE_VERSION)
    params = {"operation": "descriptive_stats", "manifest_sha256": identity}
    county = f"{BASE}/county"
    teaching = f"{BASE}/teaching"

    assert anon_client.get(BASE).json()["data"]["county"] is None
    assert anon_client.post(f"{county}/analysis", params=params).status_code == 503
    write_decision(ledger, identity)
    visible = anon_client.get(BASE).json()["data"]["county"]
    assert visible["bundle"]["manifest_sha256"] == identity
    assert visible["approval_date"] == "2026-11-13"
    assert visible["scope"]["geoid"] == "42003"
    assert "invented-test-rows" in visible["source"]
    assert anon_client.get(f"{county}/download", params={**params, "manifest_sha256": "wrong"}).status_code == 503
    result = anon_client.post(f"{county}/analysis", params=params)
    assert result.headers["cache-control"] == "no-store"
    payload = result.json()["data"]
    assert payload["provenance"] == visible
    assert payload["result"]["columns_used"] == ["reported_crashes"]
    assert payload["result"]["records_examined"] == 2
    assert not payload["result"]["execution"]["cache_hit"]
    download = anon_client.get(f"{county}/download", params=params)
    assert download.headers["cache-control"] == "no-store"
    assert download.json()["provenance"] == visible
    assert download.json()["tables"] == payload["result"]["tables"]
    monkeypatch.setenv("ALLOW_COUNTY_ANALYSER_SAMPLE", "false")
    assert anon_client.get(f"{county}/download", params=params).status_code == 503
    monkeypatch.delenv("ALLOW_COUNTY_ANALYSER_SAMPLE")
    write_decision(ledger, identity, "WITHDRAWN")
    assert anon_client.get(BASE).json()["data"]["county"] is None
    assert anon_client.post(f"{county}/analysis", params=params).status_code == 503
    assert anon_client.get(f"{county}/download", params=params).status_code == 503

    first, second = [anon_client.post(f"{teaching}/analysis", params=params).json()["data"] for _ in range(2)]
    assert first["result"]["dataset_id"] != second["result"]["dataset_id"]
    assert first["provenance"]["title"] == "Invented teaching dataset"
    assert first["result"]["tables"][0]["rows"][0]["median"] == 8.5
    export = anon_client.get(f"{teaching}/download", params={**params, "instance_id": first["result"]["dataset_id"]})
    assert export.json()["provenance"] == first["provenance"]
    assert export.json()["tables"] == first["result"]["tables"]
    assert export.json()["analysis"]["dataset_id"] == first["result"]["dataset_id"]
