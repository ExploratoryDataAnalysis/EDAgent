import pytest
from edagent.exposure.join import join_site_year_exposure


def test_join_preserves_zero_and_unknown_and_reports_unmatched():
    panel = [dict(site_id='a', year=2020, crash_count=0), dict(site_id='b', year=2020, crash_count=None)]
    obs = [dict(site_id='a', year=2020, aadt=2500, source_id='count'), dict(site_id='c', year=2020, aadt=500, source_id='count')]
    rows, unmatched = join_site_year_exposure(panel, obs)
    assert rows[0]['crash_count'] == 0 and rows[0]['traffic_exposure'] == 2500
    assert rows[1]['crash_count'] is None and rows[1]['traffic_exposure'] is None
    assert unmatched == [('c', 2020)]


def test_duplicate_traffic_and_panel_keys_rejected():
    obs = dict(site_id='a', year=2020, aadt=2500, source_id='count')
    with pytest.raises(ValueError, match='Duplicate traffic'):
        join_site_year_exposure([], [obs, obs])
    with pytest.raises(ValueError, match='Duplicate panel'):
        join_site_year_exposure([dict(site_id='a', year=2020)] * 2, [])
