"""Check the D7 candidate's denominators, nulls and release boundary."""

import csv
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path("scripts").resolve()))
from build_descriptive_release import KIND, PHASE3, coordinate_summary, severity_group, severity_summary
from road_safety_command import ROOT, digest
from app.api.v1.endpoints.frequency import router
from app.road_safety_release import ReleaseUnavailable, publish_release


def test_severity_denominators_and_coding_boundary():
    values = Counter(map(severity_group, ("0", "1", "2", "8", "9", "", "99")))
    assert values == {"0": 1, "1": 1, "2": 1, "8": 1, "9": 1, "missing": 1, "other": 1}
    old = severity_summary(values, 2015, 2015)
    new = severity_summary(values, 2016, 2016)
    assert old["known_severity_percent_of_reported"] == 300 / 7
    assert old["unknown_severity_crashes"] == 4
    assert old["fatal_percent_of_known"] == 100 / 3
    assert old["serious_fatal_crashes"] is old["serious_fatal_percent_of_known"] is None
    assert new["serious_fatal_percent_of_known"] == 200 / 3
    assert severity_summary(Counter({"9": 1}), 2016, 2016)["fatal_percent_of_known"] is None


def test_coordinate_denominators():
    counts = Counter(state_route_decimal=5, outside_county=1, inside_county=4,
                     missing_decimal_pair=3, invalid_decimal_pair=1, decimal_placeholder=1)
    result = coordinate_summary(counts, 10, 2004, 2004)
    assert result["mapped_percent_of_reported"] == 40
    assert result["outside_percent_of_usable"] == 20
    assert result["unusable_decimal_crashes"] == 5
    with pytest.raises(ValueError, match="Coordinate populations"):
        coordinate_summary(counts, 11, 2004, 2004)


@pytest.fixture
def candidate():
    path = os.environ.get("DESCRIPTIVE_STAGE")
    if not path:
        pytest.skip("Set DESCRIPTIVE_STAGE to validate the built D7 candidate")
    path = Path(path)
    return path, json.loads((path / "manifest.json").read_bytes())


def test_built_candidate(candidate):
    path, manifest = candidate
    assert manifest["status"] == "REVIEW_CANDIDATE" and manifest["approval"] is None
    assert set(manifest["outputs"]) == {file.name for file in path.iterdir()} - {"manifest.json"}
    for name, sha in manifest["outputs"].items():
        assert digest(path / name) == sha
    for name, sha in manifest["inputs"].items():
        source = PHASE3 / name.removeprefix("phase3/") if name.startswith("phase3/") else ROOT / name
        assert digest(source) == sha
    tables = {}
    for name, spec in manifest["tables"].items():
        rows = json.loads((path / f"{name}.json").read_bytes())
        with (path / f"{name}.csv").open(encoding="utf-8", newline="") as file:
            csv_rows = csv.DictReader(file)
            assert csv_rows.fieldnames == list(rows[0])
            for csv_row, json_row in zip(csv_rows, rows, strict=True):
                assert csv_row == {key: "" if value is None else str(value) for key, value in json_row.items()}
        assert len(rows) == spec["rows"]
        tables[name] = rows

    county = tables["county_periods"][0]
    assert county["reported_crashes"] == 248810
    assert county["known_severity_crashes"] == 205544
    assert county["unknown_severity_crashes"] == 43266
    assert county["fatal_crashes"] == 1396
    coverage = tables["coordinate_coverage"][0]
    assert coverage["unusable_decimal_crashes"] == 10254 and coverage["outside_county_crashes"] == 275
    grid = tables["historical_grid"]
    assert len(grid) == 38332 and sum(row["mapped_crashes"] for row in grid) == 238281
    fields = {row["metric_id"]: row for row in tables["field_coverage_by_year"] if row["period_start"] == 2024}
    assert fields["valid_hour"]["covered_crashes"] == 387
    assert fields["nonmissing_illumination"]["covered_crashes"] == 0
    assert fields["nonmissing_illumination"]["reported_crashes"] == 10228
    assert [row["review_state"] for row in tables["findings"]][-2:] == ["REVIEW_ONLY", "OUT_OF_SCOPE_NO_GO"]
    assert all(not any(term in name for term in ("crosswalk", "375", "conflict", "junction"))
               for name in manifest["outputs"])


def test_d7_publication_checks_exact_approval_and_artifact_bytes(candidate, tmp_path, monkeypatch):
    path, manifest = candidate
    ledger = tmp_path / "approvals.json"
    destination = tmp_path / "published"
    decision = {"reviewer": "Fixture reviewer", "date": "2026-11-13", "decision": "PENDING",
                "manifest_sha256": digest(path / "manifest.json")}
    ledger.write_text(json.dumps({KIND: decision}), encoding="utf-8")
    with pytest.raises(ReleaseUnavailable, match="blocked"):
        publish_release(path, destination, ledger, KIND)
    decision.update(decision="APPROVED", manifest_sha256="0" * 64)
    ledger.write_text(json.dumps({KIND: decision}), encoding="utf-8")
    with pytest.raises(ReleaseUnavailable, match="blocked"):
        publish_release(path, destination, ledger, KIND)
    assert not destination.exists()
    decision["manifest_sha256"] = digest(path / "manifest.json")
    ledger.write_text(json.dumps({KIND: decision}), encoding="utf-8")
    with pytest.raises(ReleaseUnavailable, match="blocked"):
        publish_release(path, destination, ledger, "visualizations")
    copy = shutil.copytree(path, tmp_path / KIND)
    (copy / "county_periods.csv").write_text("tampered", encoding="utf-8")
    with pytest.raises(ReleaseUnavailable, match="Artifact checksum mismatch"):
        publish_release(copy, destination, ledger, KIND)
    assert not destination.exists()
    publish_release(path, destination, ledger, KIND)
    assert set(file.name for file in destination.iterdir()) == {"manifest.json", *manifest["outputs"]}
    destination.rename(tmp_path / "visualizations")
    ledger.write_text(json.dumps({KIND: decision, "visualizations": decision}), encoding="utf-8")
    monkeypatch.setenv("ROAD_SAFETY_RELEASE_ROOT", str(tmp_path))
    monkeypatch.setenv("ROAD_SAFETY_APPROVALS", str(ledger))
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get("/concentration/geojson").status_code == 503
        assert client.get("/severity/retrospective").status_code == 503
