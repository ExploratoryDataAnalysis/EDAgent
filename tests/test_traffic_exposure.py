"""Unit tests for Phase 4 Module A traffic exposure and feasibility modules.

Governed by Phase 4 Module A requirements and Project Plan v2 (§8, §14, §18).
"""

import csv
from pathlib import Path
import pytest

from edagent.exposure.coverage import TrafficCoverageAssessment
from edagent.exposure.feasibility import (
    FeasibilityCriterion,
    FeasibilityStatus,
    OverallDecision,
    TrafficFeasibilityEvaluator,
)
from edagent.exposure.panel import SiteYearPanelBuilder
from edagent.exposure.sources import (
    ExposureCoverageLevel,
    ExposureTemporalType,
    get_official_traffic_sources,
)


class TestTrafficExposureSources:
    """Tests for traffic exposure sources registry."""

    def test_sources_count_and_keys(self):
        sources = get_official_traffic_sources()
        assert len(sources) >= 5

        source_ids = {s.source_id for s in sources}
        assert "EXP-SRC-001" in source_ids  # PennDOT RMSSEG
        assert "EXP-SRC-002" in source_ids  # PennDOT TMS
        assert "EXP-SRC-004" in source_ids  # Allegheny County Centerlines

    def test_penndot_rmsseg_properties(self):
        sources = {s.source_id: s for s in get_official_traffic_sources()}
        rms = sources["EXP-SRC-001"]
        assert rms.coverage_level == ExposureCoverageLevel.STATE_ROUTES_ONLY
        assert rms.temporal_type == ExposureTemporalType.CROSS_SECTIONAL_SNAPSHOT
        assert rms.local_road_coverage is False
        assert rms.annual_panel_available is False
        assert len(rms.known_limitations) >= 3

    def test_county_centerlines_properties(self):
        sources = {s.source_id: s for s in get_official_traffic_sources()}
        cc = sources["EXP-SRC-004"]
        assert cc.coverage_level == ExposureCoverageLevel.NONE
        assert cc.temporal_type == ExposureTemporalType.UNAVAILABLE
        assert cc.network_coverage_percent == 0.0


class TestTrafficCoverageAssessment:
    """Tests for empirical coverage metrics calculation."""

    @pytest.fixture
    def sample_crosswalk_path(self):
        return "data/exports/crosswalk/crosswalk_v1.0.0.csv.gz"

    def test_compute_metrics(self, sample_crosswalk_path):
        assessor = TrafficCoverageAssessment(sample_crosswalk_path)
        metrics = assessor.compute_coverage_metrics()

        cohort = metrics["cohort_summary"]
        assert cohort["total_crashes"] == 248810
        assert cohort["matched_crashes"] == 187068
        assert cohort["total_unique_sites"] == 24209
        assert cohort["potential_site_years_universe"] == 508389

        evals = metrics["coverage_evaluations"]
        assert evals["verified_annual_historical_panel"]["sites_covered_pct"] == 0.0
        assert evals["verified_annual_historical_panel"]["site_years_covered_pct"] == 0.0
        assert evals["modern_cross_sectional_proxy_scenario"]["local_road_sites_covered_pct"] == 0.0


class TestSiteYearPanelBuilder:
    """Tests for site-year panel prototype generation and zero-crash handling."""

    @pytest.fixture
    def sample_crosswalk_path(self):
        return "data/exports/crosswalk/crosswalk_v1.0.0.csv.gz"

    def test_build_panel_structure(self, sample_crosswalk_path):
        builder = SiteYearPanelBuilder(sample_crosswalk_path, start_year=2016, end_year=2024)
        # Process a small subset of state route sites
        panel = builder.build_panel(max_sites=20, focus_state_routes_only=True)

        assert len(panel) == 20 * 9  # 20 sites * 9 years (2016 to 2024)

        # Check required schema fields
        sample = panel[0]
        required_keys = {
            "site_id",
            "year",
            "crash_count",
            "is_zero_crash_observation",
            "road_class",
            "site_type",
            "traffic_exposure",
            "exposure_source",
            "exposure_year",
            "exposure_quality_status",
            "observability_status",
            "crosswalk_version",
        }
        assert required_keys.issubset(set(sample.keys()))

        # Verify no fabricated exposure
        for row in panel:
            assert row["traffic_exposure"] is None
            assert row["exposure_source"] == "UNAVAILABLE"
            assert row["exposure_quality_status"] == "MISSING_EXPOSURE"
            if row["crash_count"] == 0:
                assert row["is_zero_crash_observation"] is True
            else:
                assert row["is_zero_crash_observation"] is False


class TestTrafficFeasibilityEvaluator:
    """Tests for feasibility decision and criteria evaluation."""

    def test_evaluator_decision_is_no_go(self):
        result = TrafficFeasibilityEvaluator.evaluate()
        assert result["overall_decision"] == OverallDecision.NO_GO.value
        assert result["criteria_evaluated_n"] == 5
        assert result["criteria_failed_n"] == 5
        assert "HISTORICAL_CRASH_CONCENTRATION_ALTERNATIVE" in result["mandated_alternative"]

    def test_all_criteria_fail(self):
        criteria = TrafficFeasibilityEvaluator.get_standard_criteria()
        for crit in criteria:
            assert crit.status == FeasibilityStatus.FAIL
            assert crit.violates_guidelines_if_proceeded is True
