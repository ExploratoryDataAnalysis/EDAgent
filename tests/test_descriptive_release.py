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
from build_descriptive_release import GUIDE, KIND, PHASE3, coordinate_summary, findings, severity_group, severity_summary
from road_safety_command import ROOT, digest
from app.api.v1.endpoints.frequency import router
from app.api.v1.endpoints.overview import MANIFEST_SHA256
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


FINDING_POPULATIONS = {
    "Dataset integrity / provenance": (2004, 2024, "All source reports"),
    "Severity definition / missingness": (2004, 2024, "All source reports"),
    "Time and environmental field coverage": (2024, 2024, "2024 source reports"),
    "Historic codebook gate": (2018, 2019, "Weather and road-surface code transition"),
    "Formal categorical association": (2016, 2023, "Known-severity source reports"),
    "County-screened historical location": (2004, 2024, "Source reports and polygon-screened state decimals"),
    "Retrospective known-crash severity ranking": (2022, 2024, "Known-severity test reports"),
    "Site-year frequency, EB and CMF gates": (2004, 2024, "v3 site-analysis scope"),
}


def render_findings(ledger):
    return findings(
        ({"finding": label} for label in ledger), 205544,
        {"reported_crashes": 248810, "mapped_crashes": 238281}, 77476,
        {"valid_hour": 387, "reported": 10228},
        {"codebook_team_attested": False, "police_gps_format_verified": False,
         "conditional_site_frequency_gate": False, "candidate_dms_pairs_n": 238517,
         "candidate_dms_disagreements_over_500m_n": 2146},
    )


def test_findings_keep_canonical_order_when_ledger_is_reordered():
    canonical = render_findings(FINDING_POPULATIONS)
    assert render_findings(reversed(FINDING_POPULATIONS)) == canonical
    assert [row["finding"] for row in canonical] == list(FINDING_POPULATIONS)


@pytest.mark.parametrize(("replacement", "error"), [
    ([], "missing=\\['Dataset integrity / provenance'\\]"),
    (["Severity definition / missingness"], "duplicate=\\['Severity definition / missingness'\\]"),
    (["Other finding"], "unexpected=\\['Other finding'\\]"),
])
def test_findings_reject_invalid_labels(replacement, error):
    with pytest.raises(ValueError, match=error):
        render_findings([*replacement, *list(FINDING_POPULATIONS)[1:]])


@pytest.fixture
def candidate():
    path = os.environ.get("DESCRIPTIVE_STAGE")
    if not path:
        pytest.skip("Set DESCRIPTIVE_STAGE to validate the built D7 candidate")
    path = Path(path)
    return path, json.loads((path / "manifest.json").read_bytes())


def test_data_dictionary_provenance(candidate):
    path, manifest = candidate
    bundled = path / manifest["data_dictionary"]
    source_sha = manifest["inputs"][GUIDE.relative_to(ROOT).as_posix()]
    assert bundled.name == GUIDE.name
    assert bundled.read_bytes() == GUIDE.read_bytes()
    assert source_sha == manifest["outputs"][bundled.name] == digest(bundled)


def test_built_candidate(candidate):
    path, manifest = candidate
    assert digest(path / "manifest.json") == MANIFEST_SHA256
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
    for row in tables["county_periods"]:
        if row["period_start"] < 2016:
            assert row["serious_fatal_crashes"] is row["serious_fatal_percent_of_known"] is None
        else:
            assert row["serious_fatal_percent_of_known"] is not None
    composition = {row["severity_code"]: row for row in tables["severity_composition"]
                   if row["period_grain"] == "county" and row["severity_code"] is not None}
    assert (composition[8]["crashes"], composition[9]["crashes"]) == (32946, 10320)
    assert all(composition[code]["percent_of_denominator"] is None for code in (2, 3, 4))
    for era in (row for row in tables["county_periods"] if row["period_grain"] == "era"):
        groups = [row for row in tables["severity_composition"]
                  if row["period_grain"] == "era" and row["period_start"] == era["period_start"]]
        for population, denominator, subtotal in (
            ("known severity", era["known_severity_crashes"], era["known_severity_crashes"]),
            ("all reports", era["reported_crashes"], era["unknown_severity_crashes"]),
        ):
            selected = [row for row in groups if row["denominator_population"] == population]
            assert sum(row["crashes"] for row in selected) == subtotal
            assert all(row["denominator_crashes"] == denominator for row in selected)
    coverage = tables["coordinate_coverage"][0]
    assert coverage["unusable_decimal_crashes"] == 10254 and coverage["outside_county_crashes"] == 275
    assert (coverage["missing_decimal_pair_crashes"], coverage["invalid_decimal_pair_crashes"],
            coverage["placeholder_decimal_pair_crashes"]) == (10232, 10, 12)
    assert coverage["reported_crashes"] - coverage["mapped_crashes"] == 10529
    grid = tables["historical_grid"]
    assert len(grid) == 38332 and sum(row["mapped_crashes"] for row in grid) == 238281
    fields = {row["metric_id"]: row for row in tables["field_coverage_by_year"] if row["period_start"] == 2024}
    assert fields["valid_hour"]["covered_crashes"] == 387
    assert fields["nonmissing_illumination"]["covered_crashes"] == 0
    assert fields["nonmissing_illumination"]["reported_crashes"] == 10228
    assert fields["valid_hour"]["reported_crashes"] == 10228
    for row in tables["severity_associations"]:
        assert (row["period_start"], row["period_end"]) == (2016, 2023)
        assert row["tested_crashes"] == row["known_severity_crashes_in_period"] == 77476
        assert row["reported_crashes_in_period"] == 93662
        assert row["min_expected_cell"] >= 5
        assert (row["fdr_bh_q"] is None) == row["fdr_bh_q_underflow"] == (row["feature"] == "COLLISION_LABEL")
    assert [row["finding_id"] for row in tables["findings"]] == list(range(1, 9))
    assert [(row["finding"], (row["period_start"], row["period_end"], row["population"]))
            for row in tables["findings"]] == list(FINDING_POPULATIONS.items())
    assert [row["review_state"] for row in tables["findings"]] == [
        "REVIEW_CANDIDATE", "REVIEW_CANDIDATE", "REVIEW_CANDIDATE", "UNVERIFIED",
        "REVIEW_CANDIDATE", "REVIEW_CANDIDATE", "REVIEW_ONLY", "OUT_OF_SCOPE_NO_GO",
    ]
    map_text = (path / "county_grid.svg").read_text(encoding="utf-8")
    for caption in ("Reported-crash concentration", "2004–2024", "0.001° cells clipped", "exposure unmeasured"):
        assert caption in map_text
    assert all(not any(term in name for term in ("crosswalk", "375", "conflict", "junction"))
               for name in manifest["outputs"])


def test_phase8_exact_candidate_grid_geometry(candidate):
    from shapely.geometry import box, shape

    path, manifest = candidate
    boundary = json.loads((path / "county_boundary.geojson").read_bytes())
    assert boundary["properties"] == {"geoid": "42003", "vintage": 2024}
    county = shape(boundary["geometry"])
    scope = manifest["grid"]
    assert scope["crs"] == "EPSG:4326" and scope["side_degrees"] == 0.001
    assert list(county.bounds) == scope["county_bbox_wsen"]
    rows = json.loads((path / "historical_grid.json").read_bytes())
    keys = {(f"{row['lon_bin']:.3f}", f"{row['lat_bin']:.3f}") for row in rows}
    assert len(keys) == scope["occupied_cells"] == len(rows)
    half = scope["side_degrees"] / 2
    clipped_cells = 0
    for row in rows:
        lon, lat = row["lon_bin"], row["lat_bin"]
        assert (lon, lat) == (round(lon, 3), round(lat, 3))
        cell = box(lon - half, lat - half, lon + half, lat + half)
        if not county.covers(cell):
            clipped = cell.intersection(county)
            assert 0 < clipped.area < cell.area
            clipped_cells += 1
    assert clipped_cells > 0


def test_d7_publication_checks_exact_approval_and_artifact_bytes(candidate, tmp_path, monkeypatch):
    path, manifest = candidate
    ledger = tmp_path / "approvals.json"
    destination = tmp_path / "published"
    with pytest.raises(ReleaseUnavailable, match="blocked"):
        publish_release(path, destination, ledger, KIND)
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
