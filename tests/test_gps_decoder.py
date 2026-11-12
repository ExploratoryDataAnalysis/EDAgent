"""Unit tests for GPSDecoder and coordinate parsing.

Uses official PennDOT test fixtures from PennDOT Crash Data Dictionary (2026)
and EDA v6 baseline outputs.
"""

import math
import pytest
from edagent.coordinates.decoder import GPSDecoder, haversine_distance_meters
from edagent.coordinates.models import CoordinateFormat, ValidationFlag


@pytest.fixture
def decoder() -> GPSDecoder:
    return GPSDecoder(latitude_hemisphere="N", longitude_hemisphere="W")


class TestGPSDecoderDMS:
    """Tests for official PennDOT DMS format: 'DD MM:SS.ddd'."""

    def test_valid_penn_dot_official_latitude(self, decoder: GPSDecoder):
        # Verified sample from analysis/outputs/spatial/police_coordinate_encoding_audit.csv
        raw = "40 19:05.530"
        result = decoder.decode_dms_text(raw, is_longitude=False)

        assert result.is_valid is True
        assert result.is_missing is False
        assert result.format_detected == CoordinateFormat.DMS_TEXT
        assert result.raw_value == raw

        # Expected: 40 + 19/60 + 5.530/3600 = 40.31820277777778
        expected = 40.0 + (19.0 / 60.0) + (5.530 / 3600.0)
        assert result.decoded_value is not None
        assert math.isclose(result.decoded_value, expected, rel_tol=1e-9)

    def test_valid_penn_dot_official_longitude(self, decoder: GPSDecoder):
        # Verified sample from police_coordinate_encoding_audit.csv
        raw = "79 54:27.197"
        result = decoder.decode_dms_text(raw, is_longitude=True)

        assert result.is_valid is True
        assert result.is_missing is False
        assert result.format_detected == CoordinateFormat.DMS_TEXT

        # Longitude in Western hemisphere must be negative
        expected = -(79.0 + (54.0 / 60.0) + (27.197 / 3600.0))
        assert result.decoded_value is not None
        assert math.isclose(result.decoded_value, expected, rel_tol=1e-9)
        assert result.decoded_value < 0  # Verified Western hemisphere

    def test_additional_audit_pairs(self, decoder: GPSDecoder):
        # Test additional known rows from v6 audit
        lat_res = decoder.decode_dms_text("40 29:18.923", is_longitude=False)
        lon_res = decoder.decode_dms_text("80 20:13.631", is_longitude=True)

        assert lat_res.is_valid is True
        assert lon_res.is_valid is True

        expected_lat = 40.0 + (29.0 / 60.0) + (18.923 / 3600.0)
        expected_lon = -(80.0 + (20.0 / 60.0) + (13.631 / 3600.0))
        assert math.isclose(lat_res.decoded_value, expected_lat, rel_tol=1e-9)
        assert math.isclose(lon_res.decoded_value, expected_lon, rel_tol=1e-9)

    def test_malformed_formats(self, decoder: GPSDecoder):
        bad_inputs = [
            "40-19-05.530",     # Hyphens instead of spaces/colons
            "40:19:05.530",     # Two colons
            "N40 19:05.530",    # Prefixed hemisphere letter
            "40 19 05.530",     # No colon
            "40 deg 19 min",    # Prose
            "abc def:gh.ijk",   # Text
        ]
        for bad in bad_inputs:
            res = decoder.decode_dms_text(bad, is_longitude=False)
            assert res.is_valid is False
            assert res.decoded_value is None
            assert ValidationFlag.MALFORMED_LATITUDE_FORMAT in res.flags

    def test_out_of_range_minutes(self, decoder: GPSDecoder):
        # 60 minutes is invalid (must be 0-59)
        res = decoder.decode_dms_text("40 60:15.000", is_longitude=False)
        assert res.is_valid is False
        assert ValidationFlag.MINUTES_OUT_OF_RANGE in res.flags

        res2 = decoder.decode_dms_text("40 75:15.000", is_longitude=False)
        assert res2.is_valid is False
        assert ValidationFlag.MINUTES_OUT_OF_RANGE in res2.flags

    def test_out_of_range_seconds(self, decoder: GPSDecoder):
        # 60 seconds is invalid (must be 0-59.999...)
        res = decoder.decode_dms_text("40 15:60.000", is_longitude=False)
        assert res.is_valid is False
        assert ValidationFlag.SECONDS_OUT_OF_RANGE in res.flags

        res2 = decoder.decode_dms_text("40 15:99.999", is_longitude=False)
        assert res2.is_valid is False
        assert ValidationFlag.SECONDS_OUT_OF_RANGE in res2.flags

    def test_out_of_global_degrees(self, decoder: GPSDecoder):
        # Latitude cannot exceed 90 degrees
        res_lat = decoder.decode_dms_text("95 10:15.000", is_longitude=False)
        assert res_lat.is_valid is False
        assert ValidationFlag.LATITUDE_OUT_OF_GLOBAL_RANGE in res_lat.flags

        # Longitude cannot exceed 180 degrees
        res_lon = decoder.decode_dms_text("185 10:15.000", is_longitude=True)
        assert res_lon.is_valid is False
        assert ValidationFlag.LONGITUDE_OUT_OF_GLOBAL_RANGE in res_lon.flags


class TestGPSDecoderDecimal:
    """Tests for decimal degree coordinate parsing (e.g. State Route coordinates)."""

    def test_valid_decimal_coordinates(self, decoder: GPSDecoder):
        res_lat = decoder.decode_decimal_degrees("40.4355011", is_longitude=False)
        res_lon = decoder.decode_decimal_degrees("-79.74880219", is_longitude=True)

        assert res_lat.is_valid is True
        assert res_lat.decoded_value == 40.4355011
        assert res_lat.format_detected == CoordinateFormat.DECIMAL_DEGREES

        assert res_lon.is_valid is True
        assert res_lon.decoded_value == -79.74880219
        assert res_lon.format_detected == CoordinateFormat.DECIMAL_DEGREES

    def test_out_of_range_decimal(self, decoder: GPSDecoder):
        res = decoder.decode_decimal_degrees("95.5", is_longitude=False)
        assert res.is_valid is False
        assert ValidationFlag.LATITUDE_OUT_OF_GLOBAL_RANGE in res.flags

        res_lon = decoder.decode_decimal_degrees("-195.5", is_longitude=True)
        assert res_lon.is_valid is False
        assert ValidationFlag.LONGITUDE_OUT_OF_GLOBAL_RANGE in res_lon.flags


class TestMissingAndPlaceholders:
    """Tests for missing and placeholder coordinate identification."""

    @pytest.mark.parametrize(
        "placeholder",
        [None, "", "   ", "0", "0.0", "0 00:00.000", "nan", "None", "null", "99.9999"],
    )
    def test_placeholders_identified_as_missing(self, decoder: GPSDecoder, placeholder):
        res = decoder.decode_coordinate(placeholder, is_longitude=False)
        assert res.is_missing is True
        assert res.is_valid is False
        assert res.decoded_value is None
        assert ValidationFlag.MISSING_POLICE_LATITUDE in res.flags


class TestHaversineDistance:
    """Tests for spherical distance calculations."""

    def test_zero_distance_identical_points(self):
        d = haversine_distance_meters(40.4406, -79.9959, 40.4406, -79.9959)
        assert d == 0.0

    def test_known_discrepancy_pair(self):
        # Known discrepancy from candidate_coordinate_disagreements_review.csv (CRN 2007016949)
        # Police: (40.39138888888889, -79.17926944444444)
        # State:  (40.4355011, -79.74880219)
        # Frozen difference: 48,466.70 meters
        d = haversine_distance_meters(
            40.39138888888889, -79.17926944444444, 40.4355011, -79.74880219
        )
        assert math.isclose(d, 48466.70, rel_tol=1e-3)
