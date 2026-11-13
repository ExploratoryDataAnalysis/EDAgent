import importlib.util
import csv
import json
import os
from pathlib import Path
import pytest
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree
from edagent.roadway.network_review import cluster_junctions, line_edges, match_reviewed_site, segment_lineage

spec = importlib.util.spec_from_file_location('provisional', Path('scripts/build_provisional_crosswalk.py'))
provisional = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provisional)


def test_distances_follow_lines_and_keep_parallel_candidates():
    lines = [LineString([(0, 0), (1000, 0)]), LineString([(0, 30), (1000, 30)])]
    sites = [{'site_id': 'first'}, {'site_id': 'parallel'}]
    result = provisional.candidate_for_point(Point(10, 10), STRtree(lines), sites)
    assert [s for _, s in result] == ['first', 'parallel']
    assert abs(result[0][0] - 10 * 1200 / 3937) < 1e-8


def test_crossing_geometry_alone_does_not_assign_at_grade():
    # A planar crossing is only candidate evidence; no primary assignments are produced.
    lines = [LineString([(-100, 0), (100, 0)]), LineString([(0, -100), (0, 100)])]
    result = provisional.candidate_for_point(Point(0, 0), STRtree(lines), [{'site_id':'a'}, {'site_id':'b'}])
    assert len(result) == 2 and result[0][0] == result[1][0] == 0


def test_matcher_withholds_parallel_ties_grade_and_conflicting_lrs():
    line = LineString([(0, 0), (100, 0)])
    point = Point(20, 4)
    segment = {"site_id": "a", "geometry": line, "valid_from": 2019, "valid_through": 2021,
               "road_class": "STATE_ROUTE", "site_type": "SEGMENT", "directions": {"E"}}
    parallel = {**segment, "site_id": "b", "geometry": LineString([(0, 8), (100, 8)])}
    params = dict(when=2020, road_class="STATE_ROUTE", direction="E", site_type="SEGMENT",
                  coordinate_quality="VERIFIED", acceptance_m=10, tie_m=2,
                  metres_per_unit=provisional.FEET_TO_METRES)
    assert match_reviewed_site(point, [segment, parallel], lrs_site_ids=None, **params)[:3] == (
        "AMBIGUOUS", None, "GEOMETRY_TIE")
    assert match_reviewed_site(point, [segment, parallel], lrs_site_ids={"b"}, **params)[:3] == (
        "MATCHED", "b", "INDEPENDENT_LRS_AND_GEOMETRY")
    result = match_reviewed_site(point, [segment], lrs_site_ids={"b"}, **{**params, "when": 2005})
    assert result[2] == "LRS_GEOMETRY_DISAGREE_OR_UNRESOLVED"
    assert result[3][0][2] == "OUTSIDE_EFFECTIVE_DATES"
    junction = {**segment, "site_type": "INTERSECTION", "geometry": point}
    options = {**params, "site_type": "INTERSECTION"}
    assert match_reviewed_site(point, [junction], lrs_site_ids=None, **options)[3][0][2] == "AT_GRADE_UNVERIFIED"
    junction["at_grade_evidence"] = "fixture grade and connectivity evidence"
    assert match_reviewed_site(point, [junction], lrs_site_ids=None, **options)[:2] == ("MATCHED", "a")


def test_lineage_and_junction_clustering_are_evidence_based():
    whole = line_edges(LineString([(0, 0), (10, 0), (20, 0)]))
    first = line_edges(LineString([(10, 0), (0, 0)]))
    second = line_edges(LineString([(10, 0), (20, 0)]))
    before = {"a": ("Main", whole)}
    after = {"a": ("Main", first), "b": ("Main", second)}
    assert list(segment_lineage(before, after)) == [
        ("a", "a", "SPLIT_CANDIDATE"), ("a", "b", "SPLIT_CANDIDATE")]
    assert all(link[2] == "MERGE_CANDIDATE" for link in segment_lineage(after, before))
    assert list(segment_lineage(before, {"c": ("Main", whole)})) == [("a", "c", "RENUMBERING_CANDIDATE")]
    nodes = [{"x": x, "y": 0, "segments": {str(x)}, "roads": {"Main", "Other"}} for x in (0, 10, 20)]
    sites = {str(x): {"ramp": False} for x in (0, 10, 20)}
    assert cluster_junctions(nodes, sites, 12) == [[0, 1], [2]]


def test_staged_population_and_candidate_references():
    path = os.environ.get('PROVISIONAL_STAGE')
    if not path:
        pytest.skip('Set PROVISIONAL_STAGE to validate generated artifacts')
    path = Path(path)
    with (path / 'site_inventory.csv').open(encoding='utf8', newline='') as f:
        sites = {r['site_id'] for r in csv.DictReader(f)}
    with (path / 'crosswalk.csv').open(encoding='utf8', newline='') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len({r['crash_id'] for r in rows}) == 248810
    assert all(not r['primary_site_id'] for r in rows)
    assert all(not r['candidate_site_id'] or r['candidate_site_id'] in sites for r in rows)
    assert sum(r['decision_reason'] == 'V6_COORDINATE_CONFLICT_WITHHELD' for r in rows) == 2146
    by_id = {r['crash_id']: r for r in rows}
    assert by_id['2007016949']['route'] and by_id['2007016949']['match_status'] == 'AMBIGUOUS'
    assert by_id['2004000022']['decision_reason'] == 'MISSING_OR_INVALID_COORDINATES'
    assert by_id['2004000001']['decision_reason'] == 'HISTORICAL_VALIDITY_AND_TOPOLOGY_UNREVIEWED'


def test_police_format_metadata_keeps_frozen_parser_unverified():
    config = Path("data/reference/coordinates/police_gps_format.json")
    assert json.loads(config.read_bytes())["verified"] is False


def test_v3_diagnostic_handoff_and_pilot():
    path = os.environ.get("PROVISIONAL_STAGE")
    if not path:
        pytest.skip("Set PROVISIONAL_STAGE to validate generated artifacts")
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_bytes())
    assert manifest["status"] == "PROVISIONAL"
    assert manifest["scope"]["supported_assignment_scope"] == []
    assert manifest["scope"]["PRIMARY_SITE_ASSIGNMENTS_ACCEPTED"] == 0
    for name, checksum in manifest["outputs"].items():
        assert provisional.digest(path / name) == checksum

    qa = json.loads((path / "diagnostic_qa.json").read_bytes())
    assert qa["unique_crns"] == 248810
    assert qa["PRIMARY_SITE_ASSIGNMENTS_ACCEPTED"] == 0
    assert qa["police_gps_parser_status"] == "UNVERIFIED"
    assert qa["conflicts_with_withheld_disposition"] == 2146
    assert qa["coverage"]["inside_county"] == 238281
    assert qa["coverage"]["outside_county"] == 275
    assert qa["grid_cells"] == 38332
    with (path / "conflict_review.csv").open(encoding="utf-8", newline="") as file:
        conflicts = list(csv.DictReader(file))
    assert len({r["CRASH_CRN"] for r in conflicts}) == len(conflicts) == 2146
    assert all(r["disposition"].startswith("WITHHELD") and not r["primary_site_id"] for r in conflicts)
    junctions = json.loads((path / "junction_review.geojson").read_bytes())
    assert all(f["properties"]["grade_status"] == "AT_GRADE_UNVERIFIED" for f in junctions["features"])
    assert "Reported-crash concentration" in (path / "county_grid.svg").read_text(encoding="utf-8")
    assert "Police DMS hypothesis" in (path / "coordinate_conflicts.svg").read_text(encoding="utf-8")

    pilot = json.loads((path / "station_375_pilot.json").read_bytes())
    assert pilot["status"] == "INTERNAL_DIAGNOSTIC"
    assert pilot["observed_crash_count_status"] == "UNKNOWN"
    assert pilot["observed_crash_count"] is pilot["site_year_exposure"] is None
    section = pilot["traffic_section"]
    assert section["status"] == "ARCHIVED_TRAFFIC_SECTION_ONLY"
    assert (section["BASE_ADT_Y"], section["BASE_ADT"], section["contains_segment"]) == (2023, 11072, "0080")
    assert "linked_annual_aadt.csv" not in manifest["outputs"]
