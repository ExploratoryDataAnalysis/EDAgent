"""Exercise staged exposure, screening and publication through a controlled approval chain."""

import csv
import importlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path("scripts").resolve()))
from road_safety_command import digest, write_manifest
from phase4_staging import stage_exposure, stage_screening, stage_visualizations
from app.api.v1.endpoints.frequency import router
from app.road_safety_release import ReleaseUnavailable, publish_release


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns.split(","))
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def approve(ledger, kind, directory):
    entries = json.loads(ledger.read_bytes()) if ledger.exists() else {}
    entries[kind] = {"decision": "APPROVED", "reviewer": "Fixture reviewer", "date": "2026-11-12",
                     "manifest_sha256": digest(directory / "manifest.json")}
    ledger.write_text(json.dumps(entries), encoding="utf-8")


@pytest.fixture(scope="module")
def staged(tmp_path_factory):
    base = tmp_path_factory.mktemp("screening")
    ledger = base / "approvals.json"
    crosswalk = base / "crosswalk"
    crosswalk.mkdir()
    start, end = "2020-01-01", "2021-12-31"
    write_csv(crosswalk / "site_inventory.csv",
              "site_id,road_class,site_type,length_m,valid_from,valid_through,route,segment,direction", [
                  ("seg", "STATE_ROUTE", "SEGMENT", 500, start, end, "0001", "0010", "B"),
                  ("junc", "LOCAL", "INTERSECTION", "", start, end, "", "", ""),
              ])
    write_csv(crosswalk / "crosswalk.csv", "crash_id,crash_year,primary_site_id,match_status,reference_version", [
        ("1", 2020, "seg", "MATCHED", "fixture-v1"), ("2", 2020, "junc", "MATCHED", "fixture-v1"),
        ("3", 2021, "junc", "MATCHED", "fixture-v1"), ("4", 2021, "", "UNMATCHED", "fixture-v1"),
    ])
    (crosswalk / "network.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"site_id": "seg"},
         "geometry": {"type": "LineString", "coordinates": [[-80, 40], [-80.1, 40.1]]}},
        {"type": "Feature", "properties": {"site_id": "junc"},
         "geometry": {"type": "Point", "coordinates": [-80, 40]}},
    ]}), encoding="utf-8")
    write_manifest(crosswalk, "crosswalk", "fixture-v1", {"county": "Fixture", "crash_years": [2020, 2021]},
                   {"fixture_crashes": "a" * 64})
    approve(ledger, "crosswalk", crosswalk)
    keys = [("seg", 2020), ("seg", 2021), ("junc", 2020), ("junc", 2021)]
    write_csv(base / "eligibility.csv", "site_id,year,crosswalk_version,evidence_id,valid_from,valid_through",
              [(s, y, "fixture-v1", "independent-network", start, end) for s, y in keys])
    write_csv(base / "observation.csv", "site_id,year,crosswalk_version,evidence_id,valid_from,valid_through",
              [(s, y, "fixture-v1", "independent-census", start, end) for s, y in keys[:3]])
    write_csv(base / "linked_annual_aadt.csv",
              "site_id,year,crosswalk_version,evidence_id,aadt,site_type,route,segment,direction,station_id,measure,quality", [
                  ("seg", 2020, "fixture-v1", "annual", 2000, "SEGMENT", "0001", "0010", "B", "a", "AADT", "OBSERVED"),
                  ("seg", 2021, "fixture-v1", "annual", 2100, "SEGMENT", "0001", "0010", "B", "a", "AADT", "ESTIMATED"),
                  ("junc", 2020, "fixture-v1", "annual", 2000, "INTERSECTION", "", "", "", "b", "AADT", "OBSERVED"),
                  ("none", 2020, "fixture-v1", "annual", 2000, "SEGMENT", "0002", "0010", "B", "c", "AADT", "OBSERVED"),
              ])
    for kind, builder in (("exposure", stage_exposure), ("concentration", stage_screening),
                          ("visualizations", stage_visualizations)):
        builder(base / kind, base, ledger)
        approve(ledger, kind, base / kind)
    return base, ledger


def test_panel_reconciliation_and_coverage(staged):
    base, _ = staged
    rows = read_csv(base / "exposure/site_year_panel.csv")
    assert len(rows) == 4 and sum(int(row["attributed_crashes"]) for row in rows) == 3
    assert {(r["site_id"], r["year"], r["crash_count"], r["exposure_status"]) for r in rows} == {
        ("seg", "2020", "1", "OBSERVED"), ("seg", "2021", "0", "ESTIMATED"),
        ("junc", "2020", "1", "MISSING"), ("junc", "2021", "", "MISSING"),
    }
    coverage = read_csv(base / "exposure/coverage.csv")
    assert sum(int(row["eligible"]) for row in coverage) == 4
    assert all(sum(float(row[k + "_fraction"]) for k in ("observed", "estimated", "missing")) == 1
               for row in coverage)
    assert {r["reason"] for r in read_csv(base / "exposure/unlinked_exposure.csv")} == {
        "INCOMPATIBLE_OR_INVALID_EXPOSURE", "OUTSIDE_ELIGIBILITY_FRAME",
    }


def test_screening_denominators_and_strata(staged):
    base, _ = staged
    path = base / "concentration"
    rows = {r["site_id"]: r for r in read_csv(path / "historical_crash_concentration.csv")}
    assert rows["seg"]["screening_measure"] == "CRASHES_PER_KM_YEAR"
    assert rows["seg"]["screening_value"] == "1.0"
    assert rows["junc"]["screening_measure"] == "CRASHES_PER_INTERSECTION_YEAR"
    assert rows["junc"]["segment_length_km"] == ""
    for group in ("year", "road_class", "site_type"):
        summary = read_csv(path / f"historical_concentration_by_{group}.csv")
        assert sum(int(r["eligible_site_years"]) for r in summary) == 4
        assert sum(int(r["observed_site_years"]) for r in summary) == 3
        assert sum(int(r["crashes"]) for r in summary) == 2


@pytest.fixture
def published(staged, tmp_path, monkeypatch):
    base, ledger = staged
    export_root = tmp_path / "release"
    commands = {"crosswalk": "build_crosswalk", "exposure": "assess_traffic_exposure",
                "concentration": "run_frequency_modelling", "visualizations": "generate_concentration_visualizations"}
    for kind, command in commands.items():
        importlib.import_module(command).main(
            ["--publish", str(base / kind), "--approvals", str(ledger), "--release-root", str(export_root)]
        )
    approval = tmp_path / "approvals.json"
    approval.write_bytes(ledger.read_bytes())
    monkeypatch.setenv("ROAD_SAFETY_RELEASE_ROOT", str(export_root))
    monkeypatch.setenv("ROAD_SAFETY_APPROVALS", str(approval))
    app = FastAPI()
    app.include_router(router)
    return export_root, approval, TestClient(app)


def test_approved_http_and_retrospective_absence(published):
    _, _, client = published
    for endpoint in ("concentration/annual", "concentration/breakdown", "concentration/top",
                     "concentration/geojson", "concentration/seg"):
        response = client.get("/" + endpoint)
        assert response.status_code == 200
        metadata = response.json()["data"]["metadata"]
        assert metadata["crosswalk_version"] == "fixture-v1"
        assert metadata["analysis_period"] == "2020-2021" and metadata["is_predictive"] is False
    assert client.get("/concentration/absent").status_code == 404
    collection = client.get("/concentration/geojson").json()["data"]
    assert collection["type"] == "FeatureCollection"
    assert {feature["properties"]["site_id"]: feature["geometry"]["type"]
            for feature in collection["features"]} == {"seg": "LineString", "junc": "Point"}
    assert client.get("/concentration/top?site_type=INTERSECTION").json()["data"]["sites"][0]["site_id"] == "junc"
    assert client.get("/severity/retrospective").status_code == 503
    prediction = client.get("/predictions/seg").json()["data"]
    assert prediction["expected_crash_frequency"] is None
    assert prediction["historical_concentration_alternative"]["site_id"] == "seg"
    assert client.get("/status").json()["data"]["mandated_active_pathway"]["status"] == "AVAILABLE"


def test_approved_severity_remains_retrospective(published):
    root, ledger, client = published
    directory = root / "visualizations"
    write_csv(directory / "severity_retrospective_associations.csv", "metric,value", [("fixture_only", 0.1)])
    manifest = json.loads((directory / "manifest.json").read_bytes())
    (directory / "manifest.json").unlink()
    write_manifest(directory, "visualizations", manifest["version"], manifest["scope"], manifest["inputs"])
    approve(ledger, "visualizations", directory)
    response = client.get("/severity/retrospective")
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["is_predictive"] is False and result["is_causal"] is False
    assert result["results"] == [{"metric": "fixture_only", "value": "0.1"}]


@pytest.mark.parametrize("case", ["missing", "provisional", "mismatch", "tampered", "pending"])
def test_unapproved_http_and_publication(published, tmp_path, case):
    export, ledger, client = published
    directory = export / "visualizations"
    manifest_path = directory / "manifest.json"
    if case == "missing":
        manifest_path.unlink()
    elif case == "provisional":
        manifest = json.loads(manifest_path.read_bytes())
        manifest["status"] = "PROVISIONAL"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        approve(ledger, "visualizations", directory)
    elif case in {"mismatch", "pending"}:
        decisions = json.loads(ledger.read_bytes())
        key, value = ("manifest_sha256", "0" * 64) if case == "mismatch" else ("decision", "PENDING")
        decisions["visualizations"][key] = value
        ledger.write_text(json.dumps(decisions), encoding="utf-8")
    else:
        (directory / "historical_crash_concentration.csv").write_text("tampered", encoding="utf-8")
    assert client.get("/concentration/top").status_code == 503
    with pytest.raises(ReleaseUnavailable, match="blocked"):
        publish_release(directory, tmp_path / "never-published", ledger, "visualizations")


def test_v3_diagnostics_cannot_feed_site_release(tmp_path, monkeypatch):
    stage = os.environ.get("PROVISIONAL_STAGE")
    if not stage:
        pytest.skip("Set PROVISIONAL_STAGE to validate generated artifacts")
    stage = Path(stage)
    ledger = tmp_path / "approvals.json"
    approve(ledger, "crosswalk", stage)
    published = tmp_path / "published"
    with pytest.raises(ReleaseUnavailable, match="blocked"):
        publish_release(stage, published, ledger, "crosswalk")
    assert not published.exists()
    exposure = tmp_path / "exposure"
    stage_exposure(exposure, stage, ledger)
    decision = json.loads((exposure / "decision.json").read_bytes())
    assert decision["decision"] == "NO_GO" and decision["eligible_site_years"] is None
    assert not (exposure / "site_year_panel.csv").exists()

    # Simulate an operator putting the diagnostic manifest in the site map directory.
    visualizations = tmp_path / "visualizations"
    visualizations.mkdir()
    shutil.copyfile(stage / "manifest.json", visualizations / "manifest.json")
    approve(ledger, "visualizations", visualizations)
    monkeypatch.setenv("ROAD_SAFETY_RELEASE_ROOT", str(tmp_path))
    monkeypatch.setenv("ROAD_SAFETY_APPROVALS", str(ledger))
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        for endpoint in ("concentration/annual", "concentration/breakdown", "concentration/top",
                         "concentration/geojson", "concentration/375", "severity/retrospective"):
            assert client.get("/" + endpoint).status_code == 503
        assert client.get("/predictions/375").json()["data"]["expected_crash_frequency"] is None
