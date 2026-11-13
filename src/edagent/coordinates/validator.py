"""Coordinate validation and quality assurance module.

Implements range checks, county boundary containment, concentration detection,
and pairwise conflict detection as originally specified in Project Plan v2 (§12-14); v3 governs release scope.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from edagent.coordinates.decoder import GPSDecoder, haversine_distance_meters
from edagent.coordinates.models import (
    CoordinateRecord,
    CoordinateSource,
    DecodedCoordinate,
    ValidationFlag,
    ValidationStatus,
)

# Regional bounding box for Western Pennsylvania (broad screening envelope)
REGIONAL_LAT_MIN = 38.0
REGIONAL_LAT_MAX = 43.0
REGIONAL_LON_MIN = -82.0
REGIONAL_LON_MAX = -78.0

# Strict rectangular envelope for Allegheny County, PA
ALLEGHENY_LAT_MIN = 40.10
ALLEGHENY_LAT_MAX = 40.75
ALLEGHENY_LON_MIN = -80.40
ALLEGHENY_LON_MAX = -79.60

# Pairwise conflict distance threshold in meters (from EDA v6 baseline)
CONFLICT_DISTANCE_THRESHOLD_METERS = 500.0


class CoordinateValidator:
    """Validates geographic coordinates, tests spatial boundaries, and audits discrepancies."""

    def __init__(
        self,
        decoder: Optional[GPSDecoder] = None,
        county_polygon: Optional[Any] = None,
        concentration_threshold: int = 50,
    ) -> None:
        self.decoder = decoder or GPSDecoder()
        self.county_polygon = county_polygon
        self.concentration_threshold = concentration_threshold
        # Cache of coordinate frequencies for concentration auditing
        self.coordinate_frequencies: Dict[Tuple[float, float], int] = {}
        self.known_placeholders = {
            (0.0, 0.0),
            (99.9999, 99.9999),
            (-99.9999, -99.9999),
            (40.0, -80.0),  # Rounded whole degree grid placeholder
        }

    def check_regional_bounds(
        self, lat: float, lon: float
    ) -> List[ValidationFlag]:
        """Check if coordinates lie within the broader regional bounding envelope."""
        flags = []
        if not (REGIONAL_LAT_MIN <= lat <= REGIONAL_LAT_MAX):
            flags.append(ValidationFlag.LATITUDE_OUT_OF_REGIONAL_BOUNDS)
        if not (REGIONAL_LON_MIN <= lon <= REGIONAL_LON_MAX):
            flags.append(ValidationFlag.LONGITUDE_OUT_OF_REGIONAL_BOUNDS)
        return flags

    def check_county_boundary(
        self, lat: float, lon: float
    ) -> bool:
        """Check if coordinates fall within Allegheny County."""
        # First check rectangular envelope
        in_envelope = (
            ALLEGHENY_LAT_MIN <= lat <= ALLEGHENY_LAT_MAX
            and ALLEGHENY_LON_MIN <= lon <= ALLEGHENY_LON_MAX
        )
        if not in_envelope:
            return False

        # If a detailed Shapely polygon is provided, check point-in-polygon
        if self.county_polygon is not None:
            try:
                from shapely.geometry import Point
                pt = Point(lon, lat)
                return bool(self.county_polygon.covers(pt))
            except Exception:
                return in_envelope

        return True

    def validate_single_pair(
        self,
        lat_coord: DecodedCoordinate,
        lon_coord: DecodedCoordinate,
    ) -> Tuple[bool, List[ValidationFlag]]:
        """Validate a single pair of latitude and longitude coordinates."""
        flags: List[ValidationFlag] = []
        flags.extend(lat_coord.flags)
        flags.extend(lon_coord.flags)

        if not lat_coord.is_valid or not lon_coord.is_valid:
            return False, flags

        lat, lon = lat_coord.decoded_value, lon_coord.decoded_value
        if lat is None or lon is None:
            return False, flags

        # Check placeholders
        rounded = (round(lat, 4), round(lon, 4))
        if rounded in self.known_placeholders:
            flags.append(ValidationFlag.KNOWN_PLACEHOLDER_COORDINATES)
            return False, flags

        # Regional bounds
        reg_flags = self.check_regional_bounds(lat, lon)
        if reg_flags:
            flags.extend(reg_flags)
            return False, flags

        # County boundary
        if not self.check_county_boundary(lat, lon):
            flags.append(ValidationFlag.OUTSIDE_COUNTY_BOUNDARY)

        return True, flags

    def process_crash_record(
        self,
        crash_crn: int,
        crash_year: Optional[int] = None,
        raw_latitude: Optional[Any] = None,
        raw_longitude: Optional[Any] = None,
        raw_dec_lat: Optional[Any] = None,
        raw_dec_long: Optional[Any] = None,
        is_state_route: bool = False,
    ) -> CoordinateRecord:
        """Decode, reconcile, and validate all coordinates for a single crash record."""
        # 1. Decode police coordinates
        pol_lat = self.decoder.decode_coordinate(raw_latitude, is_longitude=False)
        pol_lon = self.decoder.decode_coordinate(raw_longitude, is_longitude=True)
        police_valid, police_flags = self.validate_single_pair(pol_lat, pol_lon)

        # 2. Decode state route decimal coordinates
        state_lat = self.decoder.decode_coordinate(raw_dec_lat, is_longitude=False)
        state_lon = self.decoder.decode_coordinate(raw_dec_long, is_longitude=True)
        state_valid, state_flags = self.validate_single_pair(state_lat, state_lon)

        # 3. Pairwise comparison and discrepancy detection
        distance_m: Optional[float] = None
        has_conflict = False

        if police_valid and state_valid:
            p_lat, p_lon = pol_lat.decoded_value, pol_lon.decoded_value
            s_lat, s_lon = state_lat.decoded_value, state_lon.decoded_value
            if (
                p_lat is not None
                and p_lon is not None
                and s_lat is not None
                and s_lon is not None
            ):
                distance_m = haversine_distance_meters(p_lat, p_lon, s_lat, s_lon)
                if distance_m > CONFLICT_DISTANCE_THRESHOLD_METERS:
                    has_conflict = True

        # 4. Synthesize status, reasons, and primary selected coordinate
        combined_flags: List[ValidationFlag] = []
        status: ValidationStatus
        chosen_lat: Optional[float] = None
        chosen_lon: Optional[float] = None
        chosen_source: CoordinateSource = CoordinateSource.NONE

        if has_conflict:
            status = ValidationStatus.CONFLICT
            combined_flags.append(ValidationFlag.COORDINATE_PAIR_CONFLICT)
            combined_flags.extend(police_flags)
            combined_flags.extend(state_flags)
            chosen_source = CoordinateSource.NONE
        elif state_valid:
            chosen_lat = state_lat.decoded_value
            chosen_lon = state_lon.decoded_value
            chosen_source = CoordinateSource.STATE_ROUTE_DECIMAL
            combined_flags.extend(state_flags)
            if ValidationFlag.OUTSIDE_COUNTY_BOUNDARY in state_flags:
                status = ValidationStatus.WARNING
            else:
                status = ValidationStatus.VALID
        elif police_valid:
            chosen_lat = pol_lat.decoded_value
            chosen_lon = pol_lon.decoded_value
            chosen_source = CoordinateSource.POLICE_DMS
            combined_flags.extend(police_flags)
            if ValidationFlag.OUTSIDE_COUNTY_BOUNDARY in police_flags:
                status = ValidationStatus.WARNING
            else:
                status = ValidationStatus.VALID
        elif pol_lat.is_missing and pol_lon.is_missing and state_lat.is_missing and state_lon.is_missing:
            status = ValidationStatus.MISSING
            combined_flags.append(ValidationFlag.MISSING_POLICE_COORDINATES)
            combined_flags.append(ValidationFlag.MISSING_STATE_COORDINATES)
        else:
            status = ValidationStatus.INVALID
            combined_flags.extend(police_flags)
            combined_flags.extend(state_flags)

        # Deduplicate flags while preserving order
        unique_flags = list(dict.fromkeys(combined_flags))

        return CoordinateRecord(
            crash_crn=crash_crn,
            crash_year=crash_year,
            raw_latitude=str(raw_latitude) if raw_latitude is not None else None,
            raw_longitude=str(raw_longitude) if raw_longitude is not None else None,
            raw_dec_lat=str(raw_dec_lat) if raw_dec_lat is not None else None,
            raw_dec_long=str(raw_dec_long) if raw_dec_long is not None else None,
            decoded_latitude=chosen_lat,
            decoded_longitude=chosen_lon,
            police_latitude=pol_lat.decoded_value,
            police_longitude=pol_lon.decoded_value,
            state_latitude=state_lat.decoded_value,
            state_longitude=state_lon.decoded_value,
            coordinate_source=chosen_source,
            crs="EPSG:4326",
            decoder_version=self.decoder.VERSION,
            validation_status=status,
            validation_reasons=unique_flags,
            pair_distance_meters=distance_m,
            source_dataset_version="2c13021f-74a9-4289-a1e5-fe0472c89881",
        )

    def audit_concentration_and_duplicates(
        self, records: List[CoordinateRecord]
    ) -> List[CoordinateRecord]:
        """Audit a batch of records for identical duplicates and suspicious clustering heaps."""
        counts: Dict[Tuple[float, float], int] = {}

        # First pass: count non-null decoded coordinates
        for rec in records:
            if rec.decoded_latitude is not None and rec.decoded_longitude is not None:
                pt = (round(rec.decoded_latitude, 5), round(rec.decoded_longitude, 5))
                counts[pt] = counts.get(pt, 0) + 1

        # Second pass: tag records that share duplicate or clustered locations
        for rec in records:
            if rec.decoded_latitude is not None and rec.decoded_longitude is not None:
                pt = (round(rec.decoded_latitude, 5), round(rec.decoded_longitude, 5))
                n = counts[pt]
                if n > 1:
                    if ValidationFlag.DUPLICATE_COORDINATE not in rec.validation_reasons:
                        rec.validation_reasons.append(ValidationFlag.DUPLICATE_COORDINATE)
                if n >= self.concentration_threshold:
                    if ValidationFlag.SUSPICIOUS_HIGH_CONCENTRATION not in rec.validation_reasons:
                        rec.validation_reasons.append(ValidationFlag.SUSPICIOUS_HIGH_CONCENTRATION)
                    if rec.validation_status == ValidationStatus.VALID:
                        rec.validation_status = ValidationStatus.WARNING

        return records
