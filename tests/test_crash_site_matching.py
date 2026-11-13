"""Unit tests for staged crash-to-site matching engine.

Developed under historical Project Plan v2 (§12–15) and Phase 3 Module C requirements; v3 governs release scope.
Enforces the strict One-Primary-Site Rule:
- Exactly 1 primary site ID when resolved (MATCHED).
- Zero primary site matches when unresolved (AMBIGUOUS or UNMATCHED).
- Never double-counts crashes in site-level analyses.
"""

import pytest
from edagent.coordinates.models import CoordinateRecord, ValidationFlag, ValidationStatus
from edagent.roadway.intersections import IntersectionSite
from edagent.roadway.matching import CrashSiteMatcher
from edagent.roadway.registry import SiteRegistry
from edagent.roadway.schema import (
    MatchConfidence,
    MatchMethod,
    MatchStatus,
    RoadClass,
    SiteType,
)
from edagent.roadway.segments import RoadSegmentSite


@pytest.fixture
def test_registry() -> SiteRegistry:
    """Build a populated SiteRegistry with test intersections and segments."""
    reg = SiteRegistry()

    # 1. State Route Segments
    seg1 = RoadSegmentSite.from_penndot_lrs(
        county_code="02",
        route="0022",
        segment="0040",
        street_name="WILLIAM PENN HWY",
        municipality_code="02101",
        start_coord=(40.4300, -79.8500),
        end_coord=(40.4310, -79.8400),
        source_reference_id="PENNDOT_RMS_02_0022_0040",
    ).to_site_record()
    reg.register(seg1)

    seg2 = RoadSegmentSite.from_penndot_lrs(
        county_code="02",
        route="0028",
        segment="0010",
        street_name="ALLEGHENY VALLEY EXPWY",
        municipality_code="02102",
        start_coord=(40.4800, -79.9100),
        end_coord=(40.4850, -79.9050),
        source_reference_id="PENNDOT_RMS_02_0028_0010",
    ).to_site_record()
    reg.register(seg2)

    # 2. Intersections
    int1 = IntersectionSite.from_streets(
        muni_code="02101",
        street_names=["FORBES AVE", "CRAFT AVE"],
        centroid_lat=40.4385,
        centroid_lon=-79.9630,
        municipality_name="Pittsburgh",
        source_reference_ids=["INT_REF_02101_001"],
    ).to_site_record()
    reg.register(int1)

    int2 = IntersectionSite.from_streets(
        muni_code="02101",
        street_names=["PENN AVE", "STANWIX ST"],
        centroid_lat=40.4420,
        centroid_lon=-80.0030,
        municipality_name="Pittsburgh",
        source_reference_ids=["INT_REF_02101_002"],
    ).to_site_record()
    reg.register(int2)

    # 3. Local Centerline Segments
    local1 = RoadSegmentSite.from_centerline(
        feature_key="RCL1001",
        street_name="FIFTH AVE",
        road_class=RoadClass.LOCAL_STREET,
        municipality_code="02101",
        start_coord=(40.4400, -79.9600),
        end_coord=(40.4410, -79.9550),
        source_reference_id="AC_CENTERLINE_RCL1001",
    ).to_site_record()
    reg.register(local1)

    # Symmetrical dual segments for testing ambiguous multi-candidate tie
    tie_seg_a = RoadSegmentSite.from_centerline(
        feature_key="RCL999A",
        street_name="CENTRE AVE",
        road_class=RoadClass.LOCAL_STREET,
        municipality_code="02101",
        start_coord=(40.4500, -79.9500),
        end_coord=(40.4500, -79.9400),
        source_reference_id="AC_CENTERLINE_RCL999A",
    ).to_site_record()
    reg.register(tie_seg_a)

    tie_seg_b = RoadSegmentSite.from_centerline(
        feature_key="RCL999B",
        street_name="CENTRE AVE",
        road_class=RoadClass.LOCAL_STREET,
        municipality_code="02101",
        start_coord=(40.4500, -79.9500),
        end_coord=(40.4500, -79.9400),
        source_reference_id="AC_CENTERLINE_RCL999B",
    ).to_site_record()
    reg.register(tie_seg_b)

    return reg


class TestStagedMatchingPipeline:
    """Tests for each stage of the staged matching strategy."""

    def test_stage1_exact_lrs_match(self, test_registry):
        matcher = CrashSiteMatcher(test_registry)
        crash = {
            "CRN": 2005001001,
            "CRASH_YEAR": 2018,
            "ROUTE": "0022",
            "SEGMENT": "0040",
            "OFFSET": "0120",
            "STREET_NAME": "WILLIAM PENN HWY",
            "ROAD_OWNER": 2,
        }
        res = matcher.match(crash)

        assert res.match_status == MatchStatus.MATCHED
        assert res.match_method == MatchMethod.EXACT_LRS
        assert res.primary_site_id == "SEG:02:SR0022:0040"
        assert res.site_type == SiteType.SEGMENT
        assert res.match_confidence == MatchConfidence.HIGH
        assert res.source_reference_id == "PENNDOT_RMS_02_0022_0040"

    def test_stage2_validated_intersection_match(self, test_registry):
        matcher = CrashSiteMatcher(test_registry)
        crash = {
            "CRN": 2005002002,
            "CRASH_YEAR": 2019,
            "INTERSECTION": "1",
            "STREET_NAME": "FORBES AVE & CRAFT AVE",
            "MUNICIPALITY": "02101",
            "DEC_LAT": 40.43851,  # ~1 meter from centroid
            "DEC_LONG": -79.96301,
        }
        res = matcher.match(crash)

        assert res.match_status == MatchStatus.MATCHED
        assert res.match_method == MatchMethod.INTERSECTION_JUNCTION
        assert res.primary_site_id == "INT:02101:CRAFT AVE:FORBES AVE"
        assert res.site_type == SiteType.INTERSECTION
        assert res.match_confidence == MatchConfidence.HIGH
        assert res.snap_distance_meters is not None
        assert res.snap_distance_meters < 5.0

    def test_stage3_validated_segment_spatial_snap(self, test_registry):
        matcher = CrashSiteMatcher(test_registry)
        # Point near local1 (midpoint of 40.4400, -79.9600 and 40.4410, -79.9550 is ~40.4405, -79.9575)
        crash = {
            "CRN": 2005003003,
            "CRASH_YEAR": 2020,
            "INTERSECTION": "0",
            "STREET_NAME": "FIFTH AVE",
            "MUNICIPALITY": "02101",
            "DEC_LAT": 40.44051,
            "DEC_LONG": -79.95751,
        }
        res = matcher.match(crash)

        assert res.match_status == MatchStatus.MATCHED
        assert res.match_method == MatchMethod.SEGMENT_SPATIAL_SNAP
        assert res.primary_site_id == "SEG:AC:RCL1001"
        assert res.site_type == SiteType.SEGMENT
        assert res.match_confidence in (MatchConfidence.MEDIUM, MatchConfidence.LOW)
        assert res.snap_distance_meters is not None
        assert res.snap_distance_meters <= 50.0

    def test_stage4a_ambiguous_coordinate_conflict_gated(self, test_registry):
        matcher = CrashSiteMatcher(test_registry)
        # CoordinateRecord with CONFLICT status (>500m discrepancy)
        coord_rec = CoordinateRecord(
            crash_crn=2007016949,
            validation_status=ValidationStatus.CONFLICT,
            validation_reasons=[ValidationFlag.COORDINATE_PAIR_CONFLICT],
            decoded_latitude=40.4385,
            decoded_longitude=-79.9630,
        )
        crash = {
            "CRN": 2007016949,
            "CRASH_YEAR": 2021,
            "STREET_NAME": "FORBES AVE & CRAFT AVE",
        }
        res = matcher.match(crash, coord_rec=coord_rec)

        assert res.match_status == MatchStatus.AMBIGUOUS
        assert res.match_method == MatchMethod.AMBIGUOUS_CONFLICT
        assert res.primary_site_id is None
        assert res.site_type == SiteType.UNMATCHED
        assert res.match_confidence == MatchConfidence.NONE
        assert res.coordinate_validation_status == "CONFLICT"

    def test_stage4b_ambiguous_multi_candidate_tie(self, test_registry):
        matcher = CrashSiteMatcher(test_registry)
        # Point equidistant to RCL999A and RCL999B
        crash = {
            "CRN": 2005004004,
            "CRASH_YEAR": 2022,
            "INTERSECTION": "0",
            "STREET_NAME": "CENTRE AVE",
            "MUNICIPALITY": "02101",
            "DEC_LAT": 40.4500,
            "DEC_LONG": -79.9450,
        }
        res = matcher.match(crash)

        assert res.match_status == MatchStatus.AMBIGUOUS
        assert res.match_method == MatchMethod.AMBIGUOUS_MULTI_CANDIDATE
        assert res.primary_site_id is None
        assert res.site_type == SiteType.UNMATCHED
        assert res.match_confidence == MatchConfidence.NONE
        assert res.candidate_site_count >= 2
        assert len(res.secondary_candidates) >= 2

    def test_stage5a_unmatched_distance(self, test_registry):
        matcher = CrashSiteMatcher(test_registry)
        # Coordinates in the middle of nowhere / forest (>50m from any segment)
        crash = {
            "CRN": 2005005005,
            "CRASH_YEAR": 2023,
            "STREET_NAME": "UNKNOWN WOODS RD",
            "DEC_LAT": 40.6000,
            "DEC_LONG": -80.1500,
        }
        res = matcher.match(crash)

        assert res.match_status == MatchStatus.UNMATCHED
        assert res.match_method == MatchMethod.UNMATCHED_DISTANCE
        assert res.primary_site_id is None
        assert res.site_type == SiteType.UNMATCHED
        assert res.match_confidence == MatchConfidence.NONE

    def test_stage5b_unmatched_missing_coordinates(self, test_registry):
        matcher = CrashSiteMatcher(test_registry)
        crash = {
            "CRN": 2005006006,
            "CRASH_YEAR": 2023,
            "STREET_NAME": "LOCAL STREET",
            "DEC_LAT": None,
            "DEC_LONG": None,
        }
        res = matcher.match(crash)

        assert res.match_status == MatchStatus.UNMATCHED
        assert res.match_method == MatchMethod.UNMATCHED_MISSING
        assert res.primary_site_id is None
        assert res.site_type == SiteType.UNMATCHED

    def test_stage5c_unmatched_out_of_bounds(self, test_registry):
        matcher = CrashSiteMatcher(test_registry)
        coord_rec = CoordinateRecord(
            crash_crn=2005007007,
            validation_status=ValidationStatus.INVALID,
            validation_reasons=[ValidationFlag.OUTSIDE_COUNTY_BOUNDARY],
            decoded_latitude=45.0,  # Far north
            decoded_longitude=-70.0,
        )
        crash = {"CRN": 2005007007}
        res = matcher.match(crash, coord_rec=coord_rec)

        assert res.match_status == MatchStatus.UNMATCHED
        assert res.match_method == MatchMethod.UNMATCHED_OUT_OF_BOUNDS
        assert res.primary_site_id is None


class TestOnePrimarySiteInvariant:
    """Rigorous invariant testing: Under NO circumstance may a single crash

    receive multiple primary site IDs or a primary ID when unresolved.
    """

    def test_invariant_across_diverse_cohort(self, test_registry):
        matcher = CrashSiteMatcher(test_registry)

        simulated_records = [
            # Exact LRS
            {"CRN": 101, "ROUTE": "22", "SEGMENT": "40"},
            {"CRN": 102, "ROUTE": "28", "SEGMENT": "10"},
            # Intersections
            {"CRN": 201, "INTERSECTION": "1", "STREET_NAME": "FORBES AVE & CRAFT AVE", "MUNICIPALITY": "02101", "DEC_LAT": 40.4385, "DEC_LONG": -79.9630},
            {"CRN": 202, "INTERSECTION": "1", "STREET_NAME": "PENN AVE & STANWIX ST", "MUNICIPALITY": "02101", "DEC_LAT": 40.4420, "DEC_LONG": -80.0030},
            # Segment Snaps
            {"CRN": 301, "INTERSECTION": "0", "STREET_NAME": "FIFTH AVE", "DEC_LAT": 40.4405, "DEC_LONG": -79.9575},
            # Multi-candidate ties
            {"CRN": 401, "INTERSECTION": "0", "STREET_NAME": "CENTRE AVE", "DEC_LAT": 40.4500, "DEC_LONG": -79.9450},
            # Missing
            {"CRN": 501, "DEC_LAT": None, "DEC_LONG": None},
            {"CRN": 502, "DEC_LAT": "nan", "DEC_LONG": "nan"},
            # Far out / Unmatched
            {"CRN": 601, "DEC_LAT": 40.6500, "DEC_LONG": -80.2000, "STREET_NAME": "REMOTE RD"},
        ]

        for record in simulated_records:
            cw = matcher.match(record)

            # Invariant 1: Exactly 1 primary site ID if MATCHED; None if AMBIGUOUS or UNMATCHED
            if cw.match_status == MatchStatus.MATCHED:
                assert cw.primary_site_id is not None
                assert isinstance(cw.primary_site_id, str)
                assert len(cw.primary_site_id) > 0
                assert cw.match_confidence in (MatchConfidence.HIGH, MatchConfidence.MEDIUM, MatchConfidence.LOW)
            else:
                assert cw.primary_site_id is None
                assert cw.match_confidence == MatchConfidence.NONE
                assert cw.match_status in (MatchStatus.AMBIGUOUS, MatchStatus.UNMATCHED)

            # Invariant 2: Candidate site count matches secondary candidates if ambiguous
            if cw.match_method == MatchMethod.AMBIGUOUS_MULTI_CANDIDATE:
                assert len(cw.secondary_candidates) >= 2
                assert cw.candidate_site_count == len(cw.secondary_candidates)

            # Invariant 3: Serialization produces all required crosswalk fields
            d = cw.to_dict()
            required_keys = {
                "crash_id",
                "crash_year",
                "primary_site_id",
                "site_type",
                "road_class",
                "match_method",
                "match_status",
                "match_confidence",
                "candidate_site_count",
                "source_reference_id",
                "coordinate_validation_status",
                "crosswalk_version",
            }
            assert required_keys.issubset(set(d.keys()))
