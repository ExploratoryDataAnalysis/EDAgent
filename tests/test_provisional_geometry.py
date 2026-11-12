import importlib.util
import csv
import os
from pathlib import Path
import pytest
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

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
