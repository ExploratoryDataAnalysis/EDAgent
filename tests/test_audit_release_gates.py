"""Regression checks for audit release gates and the eligible site-year frame."""

import csv
import gzip
import importlib.util
from pathlib import Path

import pytest

from edagent.exposure.panel import SiteYearPanelBuilder


@pytest.mark.parametrize("script", [
    "build_crosswalk", "assess_traffic_exposure", "run_frequency_modelling",
    "generate_concentration_visualizations",
])
def test_unreviewed_release_scripts_fail_closed(script):
    spec = importlib.util.spec_from_file_location(script, Path("scripts") / f"{script}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(RuntimeError, match="blocked"):
        module.main()


def test_panel_requires_independent_frame_and_includes_never_crashed_site(tmp_path):
    path = tmp_path / "crosswalk.csv.gz"
    with gzip.open(path, "wt", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["primary_site_id", "crash_year", "road_class", "site_type"])
        writer.writeheader()
        writer.writerow({"primary_site_id": "SEG:02:SR0001:0001", "crash_year": "2021", "road_class": "STATE_ROUTE", "site_type": "SEGMENT"})
    with pytest.raises(ValueError, match="eligible site-year frame"):
        SiteYearPanelBuilder(str(path), 2020, 2021).build_panel()
    frame = {("SEG:02:SR0001:0001", 2021), ("SEG:02:SR0002:0001", 2020)}
    rows = SiteYearPanelBuilder(str(path), 2020, 2021, eligible_site_years=frame, observed_site_years=frame).build_panel()
    assert {(r["site_id"], r["year"], r["crash_count"]) for r in rows} == {
        ("SEG:02:SR0001:0001", 2021, 1), ("SEG:02:SR0002:0001", 2020, 0)
    }
    assert all(r["traffic_exposure"] is None for r in rows)
    rows = SiteYearPanelBuilder(str(path), 2020, 2021, eligible_site_years=frame, observed_site_years={('SEG:02:SR0001:0001', 2021)}).build_panel()
    unknown = next(r for r in rows if r['site_id'] == 'SEG:02:SR0002:0001')
    assert unknown['crash_count'] is None and unknown['is_zero_crash_observation'] is None
