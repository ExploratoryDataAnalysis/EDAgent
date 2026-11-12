"""Unit tests for crosswalk quality control and reconciliation modules.

Governed by Project Plan v2 (§12–15) and Phase 3 Module D requirements.
"""

import json
from pathlib import Path
import pytest

from edagent.crosswalk.ambiguous_reviewer import AmbiguousRecordReviewer
from edagent.crosswalk.centerline_loader import epsg2272_to_wgs84
from edagent.crosswalk.disagreement_analyzer import CoordinateDisagreementAnalyzer
from edagent.crosswalk.reconciler import CrosswalkReconciler, compute_sha256
from edagent.roadway.schema import (
    CandidateSite,
    CrosswalkRecord,
    MatchConfidence,
    MatchMethod,
    MatchStatus,
    RoadClass,
    SiteType,
)


class TestGeodesicConversion:
    """Tests for Pennsylvania State Plane South (EPSG:2272) to WGS84 conversion."""

    def test_pittsburgh_conversion(self):
        # Known point in Downtown Pittsburgh: approx X=1344000, Y=410000 ftUS
        lat, lon = epsg2272_to_wgs84(1344000.0, 410000.0)
        assert 40.40 <= lat <= 40.50
        assert -80.05 <= lon <= -79.95

    def test_northern_county_conversion(self):
        # Point in Richland Township (Record 1): approx X=1359030, Y=475430 ftUS
        lat, lon = epsg2272_to_wgs84(1359030.0, 475430.0)
        assert 40.60 <= lat <= 40.65
        assert -79.96 <= lon <= -79.92


class TestDisagreementAnalyzer:
    """Tests for CoordinateDisagreementAnalyzer."""

    def test_baseline_conflict_detection(self):
        analyzer = CoordinateDisagreementAnalyzer()
        cw = CrosswalkRecord(
            crash_id=2007016949,
            crash_year=2007,
            primary_site_id=None,
            site_type=SiteType.UNMATCHED,
            road_class=RoadClass.STATE_ROUTE,
            match_method=MatchMethod.AMBIGUOUS_CONFLICT,
            match_status=MatchStatus.AMBIGUOUS,
            match_confidence=MatchConfidence.NONE,
            candidate_site_count=0,
        )
        baseline = {
            "difference_m": 48466.7,
            "candidate_police_lat": 40.391,
            "candidate_police_lon": -79.179,
        }
        res = analyzer.analyze_record({"CRASH_CRN": 2007016949}, cw, baseline_conflict=baseline)
        assert res is not None
        assert res["discrepancy_type"] == "POLICE_STATE_COORDINATE_CONFLICT"
        assert res["distance_meters"] == 48466.7
        assert res["review_status"] == "FLAGGED_CONFLICT"

    def test_concordant_record_returns_none(self):
        analyzer = CoordinateDisagreementAnalyzer()
        cw = CrosswalkRecord(
            crash_id=2005001001,
            crash_year=2018,
            primary_site_id="SEG:02:SR0022:0040",
            site_type=SiteType.SEGMENT,
            road_class=RoadClass.STATE_ROUTE,
            match_method=MatchMethod.EXACT_LRS,
            match_status=MatchStatus.MATCHED,
            match_confidence=MatchConfidence.HIGH,
            candidate_site_count=1,
            snap_distance_meters=12.5,
        )
        res = analyzer.analyze_record({"CRASH_CRN": 2005001001}, cw, baseline_conflict=None)
        assert res is None


class TestAmbiguousRecordReviewer:
    """Tests for AmbiguousRecordReviewer ledger extraction."""

    def test_extract_conflict_record(self):
        cw = CrosswalkRecord(
            crash_id=2007016949,
            crash_year=2007,
            primary_site_id=None,
            site_type=SiteType.UNMATCHED,
            road_class=RoadClass.STATE_ROUTE,
            match_method=MatchMethod.AMBIGUOUS_CONFLICT,
            match_status=MatchStatus.AMBIGUOUS,
            match_confidence=MatchConfidence.NONE,
            candidate_site_count=0,
        )
        crash_data = {
            "CRASH_CRN": 2007016949,
            "LATITUDE": "40 23:29.000",
            "LONGITUDE": "79 10:45.370",
            "DEC_LAT": "40.4355011",
            "DEC_LONG": "-79.74880219",
            "STREET_NAME": "PENN AVE",
        }
        res = AmbiguousRecordReviewer.extract_review_record(crash_data, cw)
        assert res is not None
        assert res["crash_id"] == 2007016949
        assert res["reason_for_ambiguity"] == "COORDINATE_CONFLICT_OVER_500M"
        assert res["recommended_review_status"] == "FLAGGED_DISCREPANCY"

    def test_extract_multi_candidate_tie(self):
        cand1 = CandidateSite("SEG:AC:RCL101", SiteType.SEGMENT, 14.2, 1.0, "AC_1")
        cand2 = CandidateSite("SEG:AC:RCL102", SiteType.SEGMENT, 14.5, 1.0, "AC_2")
        cw = CrosswalkRecord(
            crash_id=2005002002,
            crash_year=2019,
            primary_site_id=None,
            site_type=SiteType.UNMATCHED,
            road_class=RoadClass.LOCAL_STREET,
            match_method=MatchMethod.AMBIGUOUS_MULTI_CANDIDATE,
            match_status=MatchStatus.AMBIGUOUS,
            match_confidence=MatchConfidence.NONE,
            candidate_site_count=2,
            secondary_candidates=[cand1, cand2],
        )
        crash_data = {"CRASH_CRN": 2005002002, "STREET_NAME": "CENTRE AVE"}
        res = AmbiguousRecordReviewer.extract_review_record(crash_data, cw)
        assert res is not None
        assert res["reason_for_ambiguity"] == "EQUIDISTANT_MULTI_CANDIDATE_TIE"
        assert "SEG:AC:RCL101" in res["candidate_sites"]
        assert "SEG:AC:RCL102" in res["candidate_sites"]

    def test_matched_record_returns_none(self):
        cw = CrosswalkRecord(
            crash_id=2005003003,
            crash_year=2020,
            primary_site_id="INT:02101:CRAFT AVE:FORBES AVE",
            site_type=SiteType.INTERSECTION,
            road_class=RoadClass.LOCAL_STREET,
            match_method=MatchMethod.INTERSECTION_JUNCTION,
            match_status=MatchStatus.MATCHED,
            match_confidence=MatchConfidence.HIGH,
            candidate_site_count=1,
        )
        res = AmbiguousRecordReviewer.extract_review_record({}, cw)
        assert res is None
