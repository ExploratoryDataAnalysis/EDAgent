"""Unit tests for roadway reference normalization engine.

Developed under historical Project Plan v2 (§12–15) and Phase 3 Module C requirements; v3 governs release scope.
"""

import pytest
from edagent.roadway.normalization import (
    map_road_class,
    normalize_route_number,
    normalize_street_name,
    parse_intersection_streets,
)
from edagent.roadway.schema import RoadClass


class TestStreetNameNormalization:
    """Tests for USPS Pub 28 street name standardization."""

    def test_basic_suffix_normalization(self):
        assert normalize_street_name("Forbes Avenue") == "FORBES AVE"
        assert normalize_street_name("Liberty Ave.") == "LIBERTY AVE"
        assert normalize_street_name("Penn Street") == "PENN ST"
        assert normalize_street_name("Centre Blvd") == "CENTRE BLVD"
        assert normalize_street_name("Fifth Boulevard") == "FIFTH BLVD"
        assert normalize_street_name("Bigelow Road") == "BIGELOW RD"
        assert normalize_street_name("Craig Way") == "CRAIG WAY"
        assert normalize_street_name("Smithfield Street") == "SMITHFIELD ST"

    def test_directional_token_normalization(self):
        assert normalize_street_name("North Craig Street") == "N CRAIG ST"
        assert normalize_street_name("S. Highland Ave") == "S HIGHLAND AVE"
        assert normalize_street_name("East Carson St") == "E CARSON ST"
        assert normalize_street_name("West Liberty Avenue") == "W LIBERTY AVE"
        assert normalize_street_name("Fifth Ave NW") == "FIFTH AVE NW"

    def test_duplicate_suffix_deduplication(self):
        # Common data-entry glitch: 'MAIN ST ST' -> 'MAIN ST'
        assert normalize_street_name("Main Street St") == "MAIN ST"
        assert normalize_street_name("Penn Ave Ave") == "PENN AVE"

    def test_punctuation_and_whitespace(self):
        assert normalize_street_name("  Grant   St.  ") == "GRANT ST"
        assert normalize_street_name("St. Clair Ave") == "ST CLAIR AVE"
        assert normalize_street_name("") == ""
        assert normalize_street_name(None) == ""


class TestRouteNumberNormalization:
    """Tests for State Route 4-digit zero-padding."""

    def test_route_padding(self):
        assert normalize_route_number("22") == "0022"
        assert normalize_route_number("28") == "0028"
        assert normalize_route_number("SR 28") == "0028"
        assert normalize_route_number("Route 8") == "0008"
        assert normalize_route_number("I-376") == "0376"
        assert normalize_route_number("376") == "0376"
        assert normalize_route_number("8001") == "8001"
        assert normalize_route_number("0022") == "0022"

    def test_invalid_routes(self):
        assert normalize_route_number("") is None
        assert normalize_route_number(None) is None
        assert normalize_route_number("Local") is None


class TestIntersectionStreetParsing:
    """Tests for multi-approach street parsing and order invariance."""

    def test_ampersand_separator(self):
        res1 = parse_intersection_streets("FORBES AVE & CRAFT AVE")
        res2 = parse_intersection_streets("CRAFT AVE & FORBES AVE")
        assert res1 == ["CRAFT AVE", "FORBES AVE"]
        assert res2 == ["CRAFT AVE", "FORBES AVE"]
        assert res1 == res2

    def test_slash_and_at_separators(self):
        res1 = parse_intersection_streets("PENN AVE / 5TH AVE")
        res2 = parse_intersection_streets("PENN AVE AT 5TH AVE")
        res3 = parse_intersection_streets("5TH AVE AND PENN AVE")
        assert res1 == ["5TH AVE", "PENN AVE"]
        assert res2 == ["5TH AVE", "PENN AVE"]
        assert res3 == ["5TH AVE", "PENN AVE"]

    def test_multi_leg_junction(self):
        res = parse_intersection_streets("LIBERTY AVE & 7TH ST / PENN AVE")
        assert res == ["7TH ST", "LIBERTY AVE", "PENN AVE"]

    def test_empty_and_single_token(self):
        assert parse_intersection_streets("") == []
        assert parse_intersection_streets(None) == []
        assert parse_intersection_streets("SINGLE STREET") == ["SINGLE ST"]


class TestRoadClassMapping:
    """Tests for road classification mapping from PennDOT codes and FCC."""

    def test_state_route_and_interstate_by_number(self):
        assert map_road_class(route="376") == RoadClass.INTERSTATE
        assert map_road_class(route="79") == RoadClass.INTERSTATE
        assert map_road_class(route="28") == RoadClass.STATE_ROUTE
        assert map_road_class(route="8001") == RoadClass.RAMP

    def test_penndot_owner_code_mapping(self):
        assert map_road_class(road_owner=1) == RoadClass.INTERSTATE
        assert map_road_class(road_owner=2) == RoadClass.STATE_ROUTE
        assert map_road_class(road_owner=3) == RoadClass.COUNTY_ROAD
        assert map_road_class(road_owner=4) == RoadClass.LOCAL_STREET

    def test_centerline_fcc_mapping(self):
        assert map_road_class(fcc="A10") == RoadClass.INTERSTATE
        assert map_road_class(fcc="A20") == RoadClass.STATE_ROUTE
        assert map_road_class(fcc="A30") == RoadClass.COUNTY_ROAD
        assert map_road_class(fcc="A40") == RoadClass.LOCAL_STREET
        assert map_road_class(fcc="A63") == RoadClass.RAMP
