import hashlib
import json

import pytest

from app.api.v1.endpoints import overview
from app.road_safety_release import digest
from tests.overview_fixture import FIXTURE_VERSION, write_decision, write_fixture

BASE = "/api/v1/road-safety/overview"


@pytest.fixture
def release(tmp_path, monkeypatch):
    path = write_fixture(tmp_path / "root")
    ledger = tmp_path / "external-ledger.json"
    fingerprint = digest(path / "manifest.json")
    write_decision(ledger, fingerprint)
    monkeypatch.setenv("ROAD_SAFETY_RELEASE_ROOT", str(path.parent))
    monkeypatch.setenv("ROAD_SAFETY_APPROVALS", str(ledger))
    monkeypatch.setattr(overview, "MANIFEST_SHA256", fingerprint)
    monkeypatch.setattr(overview, "VERSION", FIXTURE_VERSION)
    return path, ledger, fingerprint


def test_verified_overview_tables_and_assets(anon_client, release):
    path, _, fingerprint = release
    provenance = anon_client.get(f"{BASE}/provenance").json()["data"]
    assert provenance["manifest_status"] == "REVIEW_CANDIDATE"
    assert provenance["grid"]["mapped_crashes"] == 20
    assert provenance["grid"]["reported_crashes"] == 24
    for table in overview.TABLES:
        r = anon_client.get(f"{BASE}/tables/{table}")
        assert r.status_code == 200, r.text
        assert r.headers["cache-control"] == "no-store"
        data = r.json()["data"]
        assert data["rows"] == json.loads((path / f"{table}.json").read_bytes())
        assert data["schema_version"] == 1
        assert data["bundle"]["manifest_sha256"] == fingerprint
        assert data["bundle"]["approval_state"] == "APPROVED_AGGREGATE_RELEASE"
        r = anon_client.get(f"{BASE}/downloads/{table}")
        assert r.content == (path / f"{table}.csv").read_bytes()
        assert r.headers["x-artifact-sha256"] == hashlib.sha256(r.content).hexdigest()
    for name, media in overview.ASSETS.items():
        r = anon_client.get(f"{BASE}/assets/{name}")
        assert r.content == (path / name).read_bytes()
        assert r.headers["content-type"].startswith(media)
        assert r.headers["x-manifest-sha256"] == fingerprint
        assert r.headers["link"] == '<../provenance>; rel="describedby"'


def test_metric_ratios_and_nulls(anon_client, release):
    county = f"{BASE}/tables/county_periods/metrics"
    key = {"period_grain": "county", "period_start": 2004, "period_end": 2024}
    metric = anon_client.get(f"{county}/known_severity_percent_of_reported", params=key).json()["data"]
    assert metric["units"] == "percent"
    assert metric["numerator"]["count"] == 18
    assert metric["denominator"]["count"] == 24
    assert metric["coverage"]["unknown_severity_crashes"] == 6
    metric = anon_client.get(f"{county}/serious_fatal_percent_of_known", params=key).json()["data"]
    assert metric["value"] is metric["numerator"] is metric["denominator"] is None
    assert metric["value_state"] == "UNAVAILABLE"
    assert metric["reason_code"] == "SEVERITY_CODING_BREAK_2016"
    field = f"{BASE}/tables/field_coverage_by_year/metrics/covered_percent_of_reported"
    metric = anon_client.get(field, params={"period_start": 2024, "metric_id": "nonmissing_illumination"}).json()["data"]
    assert metric["value"] == 0 and metric["value_state"] == "AVAILABLE"
    assert metric["caveats"][0]["code"] == "NO_2024_ILLUMINATION_COVERAGE"
    data = anon_client.get(f"{BASE}/tables/severity_composition").json()["data"]
    assert data["annotations"]["3"]["nulls"]["severity_code"]["value_state"] == "UNKNOWN"
    data = anon_client.get(f"{BASE}/tables/severity_associations").json()["data"]
    assert (data["period_start"], data["period_end"]) == (2016, 2023)


@pytest.mark.parametrize("failure", ["unconfigured_ledger", "missing_ledger", "pending", "wrong_approval_hash", "altered_manifest",
                                     "unsupported_schema", "unsupported_kind", "tampered", "missing"])
def test_unavailable_without_exact_verified_release(anon_client, release, monkeypatch, failure):
    path, ledger, fingerprint = release
    if failure == "unconfigured_ledger":
        monkeypatch.delenv("ROAD_SAFETY_APPROVALS")
    elif failure == "missing_ledger":
        ledger.unlink()
    elif failure == "pending":
        write_decision(ledger, fingerprint, "PENDING")
    elif failure == "wrong_approval_hash":
        write_decision(ledger, "0" * 64)
    elif failure in {"altered_manifest", "unsupported_schema", "unsupported_kind"}:
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest.update({"unsupported_schema": {"schema_version": 2}, "unsupported_kind": {"kind": "visualizations"},
                         "altered_manifest": {"run_id": "changed"}}[failure])
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        write_decision(ledger, digest(manifest_path))
        if failure != "altered_manifest":
            monkeypatch.setattr(overview, "MANIFEST_SHA256", digest(manifest_path))
    elif failure == "tampered":
        (path / "county_periods.json").write_text("[]", encoding="utf-8")
    else:
        (path / "county_grid.svg").unlink()
    for route in ("/provenance", "/tables/county_periods", "/downloads/county_periods", "/assets/county_grid.svg"):
        r = anon_client.get(f"{BASE}{route}")
        assert r.status_code == 503
        assert r.json()["detail"] == overview.UNAVAILABLE
        assert r.headers["cache-control"] == "no-store"


def test_d7_cannot_serve_internal_or_legacy_site_artifacts(anon_client, release):
    for route in ("/spatial/hotspots", "/models/comparison", "/concentration/road-classes"):
        assert anon_client.get(f"{BASE}{route}").status_code == 404
    for route in ("/assets/manifest.json", "/assets/county_points_review.csv", "/tables/crosswalk", "/downloads/conflicts"):
        assert anon_client.get(f"{BASE}{route}").status_code == 503
    for route in ("annual", "breakdown", "geojson", "top", "Station%20375"):
        assert anon_client.get(f"/api/v1/frequency/concentration/{route}").status_code == 503
    assert anon_client.get("/api/v1/frequency/severity/retrospective").status_code == 503
    assert anon_client.get("/api/v1/frequency/predictions/Station%20375").json()["data"]["expected_crash_frequency"] is None


def test_release_change_between_verification_and_response(anon_client, release, monkeypatch):
    path, _, _ = release
    verify = overview.verify_release

    def replace_after_verification(*args, **kwargs):
        manifest = verify(*args, **kwargs)
        (path / "county_periods.json").write_text("[]", encoding="utf-8")
        return manifest

    monkeypatch.setattr(overview, "verify_release", replace_after_verification)
    response = anon_client.get(f"{BASE}/tables/county_periods")
    assert response.status_code == 503
    assert response.json()["detail"] == overview.UNAVAILABLE


def test_default_release_pin_excludes_fixture(anon_client, tmp_path, monkeypatch):
    path = write_fixture(tmp_path / "root")
    ledger = tmp_path / "external-ledger.json"
    write_decision(ledger, digest(path / "manifest.json"))
    monkeypatch.setenv("ROAD_SAFETY_RELEASE_ROOT", str(path.parent))
    monkeypatch.setenv("ROAD_SAFETY_APPROVALS", str(ledger))
    response = anon_client.get(f"{BASE}/provenance")
    assert response.status_code == 503
    assert response.json()["detail"] == overview.UNAVAILABLE


def test_phase7b_annual_and_coverage_slice_contract(anon_client, release):
    path, _, fingerprint = release
    # 1. County periods table and annotations
    res_county = anon_client.get(f"{BASE}/tables/county_periods")
    assert res_county.status_code == 200
    county_data = res_county.json()["data"]
    assert county_data["table_id"] == "county_periods"
    assert county_data["row_key"] == ["period_grain", "period_start", "period_end"]
    annual_rows = [r for r in county_data["rows"] if r["period_grain"] == "year"]
    assert len(annual_rows) >= 2
    row_2015 = next(r for r in annual_rows if r["period_start"] == 2015)
    row_2024 = next(r for r in annual_rows if r["period_start"] == 2024)
    # 2016 seam: pre-2016 serious/fatal is null
    assert row_2015["serious_fatal_crashes"] is None
    assert row_2015["serious_fatal_percent_of_known"] is None
    # 2016 seam: post-2016 serious/fatal is available
    assert row_2024["serious_fatal_crashes"] == 2
    assert row_2024["serious_fatal_percent_of_known"] is not None

    # 2. Coordinate coverage joinable by year
    res_coord = anon_client.get(f"{BASE}/tables/coordinate_coverage")
    assert res_coord.status_code == 200
    coord_data = res_coord.json()["data"]
    assert coord_data["row_key"] == ["period_grain", "period_start", "period_end"]
    coord_2024 = next(r for r in coord_data["rows"] if r["period_grain"] == "year" and r["period_start"] == 2024)
    assert coord_2024["mapped_crashes"] == 10
    assert coord_2024["reported_crashes"] == 12

    # 3. Field coverage caveats: 2024 valid hour and illumination
    res_fields = anon_client.get(f"{BASE}/tables/field_coverage_by_year")
    assert res_fields.status_code == 200
    fields_data = res_fields.json()["data"]
    assert fields_data["row_key"] == ["period_start", "metric_id"]
    hour_2024 = next(r for r in fields_data["rows"] if r["period_start"] == 2024 and r["metric_id"] == "valid_hour")
    light_2024 = next(r for r in fields_data["rows"] if r["period_start"] == 2024 and r["metric_id"] == "nonmissing_illumination")
    assert hour_2024["covered_crashes"] == 1
    assert light_2024["covered_crashes"] == 0  # Measured zero count

    # 4. Verified CSV export route bound to release identity
    res_csv = anon_client.get(f"{BASE}/downloads/county_periods")
    assert res_csv.status_code == 200
    assert res_csv.headers["content-type"].startswith("text/csv")
    assert res_csv.headers["x-manifest-sha256"] == fingerprint
    assert "reported_crashes" in res_csv.text

