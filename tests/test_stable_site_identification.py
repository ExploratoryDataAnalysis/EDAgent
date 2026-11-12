"""Unit tests for stable site identification and geometry modules.

Governed by Project Plan v2 (§12–15) and Phase 3 Module C requirements.
Verifies determinism, order invariance, PennDOT direction conventions, and spatial metrics.
"""

import pytest
from edagent.roadway.intersections import (
    IntersectionIdentifier,
    IntersectionSite,
)
from edagent.roadway.registry import SiteRegistry
from edagent.roadway.schema import RoadClass, SiteType
from edagent.roadway.segments import (
    RoadSegmentSite,
    SegmentIdentifier,
    point_to_line_segment_distance,
)


class TestIntersectionIdentification:
    """Tests for intersection stable identifier generation and catchment geometry."""

    def test_order_invariance(self):
        id1 = IntersectionIdentifier.generate_id("02101", ["Forbes Avenue", "Craft Ave"])
        id2 = IntersectionIdentifier.generate_id("02101", ["Craft Ave", "Forbes Avenue"])
        assert id1 == "INT:02101:CRAFT AVE:FORBES AVE"
        assert id1 == id2

    def test_deterministic_hash_id(self):
        h1 = IntersectionIdentifier.generate_hash_id("02101", ["Forbes Avenue", "Craft Ave"])
        h2 = IntersectionIdentifier.generate_hash_id("02101", ["Craft Ave", "Forbes Avenue"])
        assert h1.startswith("INT-02101-")
        assert h1 == h2

    def test_canonical_name(self):
        name1 = IntersectionIdentifier.generate_canonical_name(
            ["Penn Ave", "Fifth Ave"], muni_name="Pittsburgh"
        )
        assert name1 == "FIFTH AVE & PENN AVE (Pittsburgh)"

    def test_fewer_than_two_streets_raises(self):
        with pytest.raises(ValueError, match="at least 2 distinct"):
            IntersectionIdentifier.generate_id("02101", ["Forbes Avenue"])

        with pytest.raises(ValueError, match="muni_code must not be empty"):
            IntersectionIdentifier.generate_id("", ["Forbes Avenue", "Craft Ave"])

    def test_intersection_site_catchment_matching(self):
        site = IntersectionSite.from_streets(
            muni_code="02101",
            street_names=["FORBES AVE", "CRAFT AVE"],
            centroid_lat=40.4385,
            centroid_lon=-79.9630,
            radius_meters=30.48,
        )
        # Point 10 meters away -> within catchment
        # At latitude 40.4385, 0.0001 deg lat is ~11.1 meters
        is_within, dist = site.matches_point(40.4386, -79.9630)
        assert is_within is True
        assert dist < 30.48

        # Point 100 meters away -> outside catchment
        is_within_far, dist_far = site.matches_point(40.4400, -79.9630)
        assert is_within_far is False
        assert dist_far > 30.48

    def test_intersection_street_corroboration(self):
        site = IntersectionSite.from_streets(
            muni_code="02101",
            street_names=["FORBES AVE", "CRAFT AVE"],
        )
        # Full match
        assert site.corroborates_streets(["FORBES AVE", "CRAFT AVE"]) == 1.0
        # Partial match
        assert site.corroborates_streets(["FORBES AVE", "HALKET ST"]) == 0.5
        # No match
        assert site.corroborates_streets(["FIFTH AVE", "HALKET ST"]) == 0.0


class TestSegmentIdentification:
    """Tests for road segment stable IDs and PennDOT LRS direction conventions."""

    def test_penndot_state_segment_id(self):
        seg_id = SegmentIdentifier.generate_state_segment_id("02", "22", "40")
        assert seg_id == "SEG:02:SR0022:0040"

        seg_id2 = SegmentIdentifier.generate_state_segment_id("2", "SR 28", "10")
        assert seg_id2 == "SEG:02:SR0028:0010"

    def test_penndot_direction_convention(self):
        # Divided route: even = North/East, odd = South/West
        assert SegmentIdentifier.determine_penndot_direction("0040", is_divided=True) == "NORTH_EAST"
        assert SegmentIdentifier.determine_penndot_direction("0041", is_divided=True) == "SOUTH_WEST"
        assert SegmentIdentifier.determine_penndot_direction("0020", is_divided=False) == "BIDIRECTIONAL"

    def test_centerline_segment_id(self):
        seg_id = SegmentIdentifier.generate_centerline_segment_id("RCL100234")
        assert seg_id == "SEG:AC:RCL100234"

    def test_local_segment_id(self):
        seg_id = SegmentIdentifier.generate_local_segment_id("02101", "Main Street", "0100")
        assert seg_id == "SEG:02101:MAIN ST:0100"

    def test_point_to_line_segment_distance(self):
        # Line segment running along latitude 40.4400 from lon -80.000 to -79.990
        # Point is exactly on the line at midpoint (-79.995)
        dist_on, lat_c, lon_c = point_to_line_segment_distance(
            40.4400, -79.9950,
            40.4400, -80.0000,
            40.4400, -79.9900,
        )
        assert dist_on < 0.1  # Virtually 0 meters

        # Point is offset by ~0.0001 deg lat (approx 11.1 meters north)
        dist_off, _, _ = point_to_line_segment_distance(
            40.4401, -79.9950,
            40.4400, -80.0000,
            40.4400, -79.9900,
        )
        assert 10.0 < dist_off < 12.0


class TestSiteRegistry:
    """Tests for SiteRegistry indexing, lookups, and serialization."""

    def test_register_and_lookup_intersection(self):
        registry = SiteRegistry()
        site = IntersectionSite.from_streets(
            muni_code="02101",
            street_names=["FORBES AVE", "CRAFT AVE"],
            centroid_lat=40.4385,
            centroid_lon=-79.9630,
        ).to_site_record()

        registry.register(site)
        assert registry.size() == 1

        # Lookup by reverse street order
        found = registry.find_intersection("02101", ["CRAFT AVE", "FORBES AVE"])
        assert found is not None
        assert found.site_id == "INT:02101:CRAFT AVE:FORBES AVE"

    def test_register_and_lookup_lrs_segment(self):
        registry = SiteRegistry()
        seg_site = RoadSegmentSite.from_penndot_lrs(
            county_code="02",
            route="0022",
            segment="0040",
            street_name="WILLIAM PENN HWY",
            start_coord=(40.4300, -79.8500),
            end_coord=(40.4310, -79.8400),
        ).to_site_record()

        registry.register(seg_site)
        assert registry.size() == 1

        found = registry.find_segment_by_lrs("02", "22", "40")
        assert found is not None
        assert found.site_id == "SEG:02:SR0022:0040"

    def test_spatial_proximity_query(self):
        registry = SiteRegistry()
        site1 = IntersectionSite.from_streets(
            muni_code="02101",
            street_names=["FORBES AVE", "CRAFT AVE"],
            centroid_lat=40.4385,
            centroid_lon=-79.9630,
        ).to_site_record()
        site2 = IntersectionSite.from_streets(
            muni_code="02101",
            street_names=["PENN AVE", "STANWIX ST"],
            centroid_lat=40.4420,
            centroid_lon=-80.0030,
        ).to_site_record()

        registry.register(site1)
        registry.register(site2)

        # Query near site 1
        nearby = registry.find_nearby_sites(40.43851, -79.96301, max_distance_meters=50.0)
        assert len(nearby) == 1
        assert nearby[0][0].site_id == site1.site_id
        assert nearby[0][1] < 10.0
