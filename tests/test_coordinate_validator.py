"""Unit tests for CoordinateValidator quality checks and spatial validation."""

import pytest
from edagent.coordinates.decoder import GPSDecoder
from edagent.coordinates.models import (
    CoordinateSource,
    ValidationFlag,
    ValidationStatus,
)
from edagent.coordinates.validator import CoordinateValidator


@pytest.fixture
def validator() -> CoordinateValidator:
    decoder = GPSDecoder(latitude_hemisphere="N", longitude_hemisphere="W")
    return CoordinateValidator(decoder=decoder, concentration_threshold=5)


class TestCoordinateValidatorSingleRecords:
    """Tests for validating individual crash records."""

    def test_valid_concordant_crash_record(self, validator: CoordinateValidator):
        # Realistic Monroeville intersection crash on SR 0022
        rec = validator.process_crash_record(
            crash_crn=2015001234,
            crash_year=2015,
            raw_latitude="40 26:07.800",
            raw_longitude="79 45:10.800",
            raw_dec_lat="40.435501",
            raw_dec_long="-79.753000",
            is_state_route=True,
        )

        assert rec.validation_status == ValidationStatus.VALID
        assert rec.coordinate_source == CoordinateSource.STATE_ROUTE_DECIMAL
        assert rec.decoded_latitude is not None
        assert rec.decoded_longitude is not None
        assert rec.pair_distance_meters is not None
        assert rec.pair_distance_meters < 500.0
        assert ValidationFlag.COORDINATE_PAIR_CONFLICT not in rec.validation_reasons

    def test_coordinate_pair_conflict_gated(self, validator: CoordinateValidator):
        # Known discrepancy from CRN 2007016949 (48.47 km apart)
        rec = validator.process_crash_record(
            crash_crn=2007016949,
            crash_year=2007,
            raw_latitude="40 23:29.000",    # ~40.3914
            raw_longitude="79 10:45.370",   # ~ -79.1793 (Westmoreland County)
            raw_dec_lat="40.435501",
            raw_dec_long="-79.748802",       # Monroeville, Allegheny County
            is_state_route=True,
        )

        assert rec.validation_status == ValidationStatus.CONFLICT
        assert rec.coordinate_source == CoordinateSource.NONE
        assert ValidationFlag.COORDINATE_PAIR_CONFLICT in rec.validation_reasons
        assert rec.pair_distance_meters is not None
        assert rec.pair_distance_meters > 40000.0  # >40km

    def test_local_road_police_coordinates_only(self, validator: CoordinateValidator):
        # Local road crash where state route decimal coordinates are not present
        rec = validator.process_crash_record(
            crash_crn=2019054321,
            crash_year=2019,
            raw_latitude="40 26:30.000",
            raw_longitude="79 58:45.000",
            raw_dec_lat=None,
            raw_dec_long=None,
            is_state_route=False,
        )

        assert rec.validation_status == ValidationStatus.VALID
        assert rec.coordinate_source == CoordinateSource.POLICE_DMS
        assert rec.decoded_latitude is not None
        assert rec.decoded_longitude is not None
        assert rec.pair_distance_meters is None

    def test_outside_county_warning(self, validator: CoordinateValidator):
        # Armstrong / Butler County coordinates (within Western PA region, but outside Allegheny County)
        # Lat 40.7848, Lon -79.5814 (from actual CRN 2005006334)
        rec = validator.process_crash_record(
            crash_crn=2005006334,
            crash_year=2004,
            raw_latitude="40 47:05.280",
            raw_longitude="79 34:53.040",
            raw_dec_lat="40.784800",
            raw_dec_long="-79.581400",
        )

        assert rec.validation_status == ValidationStatus.WARNING
        assert ValidationFlag.OUTSIDE_COUNTY_BOUNDARY in rec.validation_reasons

    def test_outside_regional_bounds_invalid(self, validator: CoordinateValidator):
        # Miami, Florida coordinates (Lat 25.76, Lon -80.19)
        rec = validator.process_crash_record(
            crash_crn=2018088888,
            crash_year=2018,
            raw_latitude="25 45:36.000",
            raw_longitude="80 11:24.000",
            raw_dec_lat=None,
            raw_dec_long=None,
        )

        assert rec.validation_status == ValidationStatus.INVALID
        assert ValidationFlag.LATITUDE_OUT_OF_REGIONAL_BOUNDS in rec.validation_reasons

    def test_missing_coordinates(self, validator: CoordinateValidator):
        rec = validator.process_crash_record(
            crash_crn=2004000001,
            crash_year=2004,
            raw_latitude=None,
            raw_longitude=None,
            raw_dec_lat=None,
            raw_dec_long=None,
        )

        assert rec.validation_status == ValidationStatus.MISSING
        assert rec.decoded_latitude is None
        assert rec.decoded_longitude is None
        assert ValidationFlag.MISSING_POLICE_COORDINATES in rec.validation_reasons


class TestCoordinateValidatorBatchAudit:
    """Tests for concentration and duplicate coordinate detection."""

    def test_concentration_and_duplicate_detection(self, validator: CoordinateValidator):
        records = []
        # Create 6 identical records (exceeding the fixture's threshold of 5)
        for i in range(6):
            rec = validator.process_crash_record(
                crash_crn=2017000000 + i,
                crash_year=2017,
                raw_latitude="40 26:30.000",
                raw_longitude="79 58:45.000",
            )
            records.append(rec)

        # Add 1 distinct crash
        records.append(
            validator.process_crash_record(
                crash_crn=2017000099,
                crash_year=2017,
                raw_latitude="40 30:00.000",
                raw_longitude="80 05:00.000",
            )
        )

        audited = validator.audit_concentration_and_duplicates(records)

        # The 6 clustered records should have DUPLICATE and SUSPICIOUS_HIGH_CONCENTRATION flags
        for r in audited[:6]:
            assert ValidationFlag.DUPLICATE_COORDINATE in r.validation_reasons
            assert ValidationFlag.SUSPICIOUS_HIGH_CONCENTRATION in r.validation_reasons
            assert r.validation_status == ValidationStatus.WARNING

        # The single distinct record should remain clean
        assert ValidationFlag.DUPLICATE_COORDINATE not in audited[6].validation_reasons
        assert ValidationFlag.SUSPICIOUS_HIGH_CONCENTRATION not in audited[6].validation_reasons
        assert audited[6].validation_status == ValidationStatus.VALID


class TestFrozenBaselineReconciliation:
    """Tests reconciling against frozen v6 research outputs."""

    def test_reconcile_2146_frozen_disagreements(self, validator: CoordinateValidator):
        import csv
        from pathlib import Path
        csv_path = Path("analysis/outputs/spatial/candidate_coordinate_disagreements_review.csv")
        if not csv_path.is_file():
            pytest.skip("Frozen disagreements review CSV not found")

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                count += 1
                rec = validator.process_crash_record(
                    crash_crn=int(row["CRASH_CRN"]),
                    crash_year=int(row["CRASH_YEAR"]),
                    raw_dec_lat=row["state_decimal_lat"],
                    raw_dec_long=row["state_decimal_lon"],
                    # Feed pre-parsed decimal police coords as decimal input to test validator
                    raw_latitude=row["candidate_police_lat"],
                    raw_longitude=row["candidate_police_lon"],
                    is_state_route=True,
                )
                assert rec.validation_status == ValidationStatus.CONFLICT
                assert ValidationFlag.COORDINATE_PAIR_CONFLICT in rec.validation_reasons
                assert rec.pair_distance_meters is not None
                assert rec.pair_distance_meters > 500.0
                assert pytest.approx(rec.pair_distance_meters, rel=1e-5) == float(row["difference_m"])

            assert count == 2146

