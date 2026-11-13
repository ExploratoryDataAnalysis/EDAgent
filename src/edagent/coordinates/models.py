"""Coordinate models, status enumerations, and validation flags.

Developed under the PennDOT Crash Data Dictionary (2026) and historical Project Plan v2; v3 governs release scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ValidationStatus(str, Enum):
    """Validation lifecycle status for a decoded coordinate pair."""
    VALID = "VALID"
    WARNING = "WARNING"
    CONFLICT = "CONFLICT"
    INVALID = "INVALID"
    MISSING = "MISSING"


class ValidationFlag(str, Enum):
    """Specific standardized reason codes for coordinate validation outcomes."""
    # Missingness
    MISSING_POLICE_COORDINATES = "MISSING_POLICE_COORDINATES"
    MISSING_POLICE_LATITUDE = "MISSING_POLICE_LATITUDE"
    MISSING_POLICE_LONGITUDE = "MISSING_POLICE_LONGITUDE"
    MISSING_STATE_COORDINATES = "MISSING_STATE_COORDINATES"
    KNOWN_PLACEHOLDER_COORDINATES = "KNOWN_PLACEHOLDER_COORDINATES"

    # Syntax and format malformations
    MALFORMED_LATITUDE_FORMAT = "MALFORMED_LATITUDE_FORMAT"
    MALFORMED_LONGITUDE_FORMAT = "MALFORMED_LONGITUDE_FORMAT"
    NON_NUMERIC_COORDINATE_VALUE = "NON_NUMERIC_COORDINATE_VALUE"
    INVALID_DMS_COMPONENT = "INVALID_DMS_COMPONENT"

    # Mathematical and global domain constraints
    LATITUDE_OUT_OF_GLOBAL_RANGE = "LATITUDE_OUT_OF_GLOBAL_RANGE"
    LONGITUDE_OUT_OF_GLOBAL_RANGE = "LONGITUDE_OUT_OF_GLOBAL_RANGE"
    MINUTES_OUT_OF_RANGE = "MINUTES_OUT_OF_RANGE"
    SECONDS_OUT_OF_RANGE = "SECONDS_OUT_OF_RANGE"

    # Regional and geographical boundaries
    LATITUDE_OUT_OF_REGIONAL_BOUNDS = "LATITUDE_OUT_OF_REGIONAL_BOUNDS"
    LONGITUDE_OUT_OF_REGIONAL_BOUNDS = "LONGITUDE_OUT_OF_REGIONAL_BOUNDS"
    OUTSIDE_COUNTY_BOUNDARY = "OUTSIDE_COUNTY_BOUNDARY"

    # Spatial consistency and quality
    COORDINATE_PAIR_CONFLICT = "COORDINATE_PAIR_CONFLICT"
    SUSPICIOUS_HIGH_CONCENTRATION = "SUSPICIOUS_HIGH_CONCENTRATION"
    DUPLICATE_COORDINATE = "DUPLICATE_COORDINATE"


class CoordinateFormat(str, Enum):
    """Supported coordinate input formats."""
    DMS_TEXT = "dms_text"                      # 'DD MM:SS.ddd' (PennDOT 2026 official)
    DECIMAL_DEGREES = "decimal_degrees"        # Standard signed floats (-79.95, 40.44)
    DDMMSS = "ddmmss"                          # Packed numeric (401905.53 / 795427.20)
    DEGREES_DECIMAL_MINUTES = "degrees_decimal_minutes"  # 'DD MM.mmmm'


class CoordinateSource(str, Enum):
    """Origin of the primary selected coordinate."""
    POLICE_DMS = "police_dms"
    STATE_ROUTE_DECIMAL = "state_route_decimal"
    NONE = "none"


@dataclass
class DecodedCoordinate:
    """Result of decoding a single coordinate axis (latitude or longitude)."""
    raw_value: Optional[str]
    decoded_value: Optional[float]
    format_detected: Optional[CoordinateFormat]
    is_valid: bool
    is_missing: bool
    flags: List[ValidationFlag] = field(default_factory=list)


@dataclass
class CoordinateRecord:
    """Traceable, normalized coordinate record for a single crash incident.

    Maintains full provenance from raw input to validated coordinates.
    """
    crash_crn: int
    crash_year: Optional[int] = None
    raw_latitude: Optional[str] = None
    raw_longitude: Optional[str] = None
    raw_dec_lat: Optional[str] = None
    raw_dec_long: Optional[str] = None

    decoded_latitude: Optional[float] = None
    decoded_longitude: Optional[float] = None

    police_latitude: Optional[float] = None
    police_longitude: Optional[float] = None
    state_latitude: Optional[float] = None
    state_longitude: Optional[float] = None

    coordinate_source: CoordinateSource = CoordinateSource.NONE
    crs: str = "EPSG:4326"
    decoder_version: str = "1.0.0"
    validation_status: ValidationStatus = ValidationStatus.MISSING
    validation_reasons: List[ValidationFlag] = field(default_factory=list)

    pair_distance_meters: Optional[float] = None
    source_dataset_version: str = "2c13021f-74a9-4289-a1e5-fe0472c89881"

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to serialized dictionary."""
        return {
            "crash_crn": self.crash_crn,
            "crash_year": self.crash_year,
            "raw_latitude": self.raw_latitude,
            "raw_longitude": self.raw_longitude,
            "raw_dec_lat": self.raw_dec_lat,
            "raw_dec_long": self.raw_dec_long,
            "decoded_latitude": self.decoded_latitude,
            "decoded_longitude": self.decoded_longitude,
            "police_latitude": self.police_latitude,
            "police_longitude": self.police_longitude,
            "state_latitude": self.state_latitude,
            "state_longitude": self.state_longitude,
            "coordinate_source": self.coordinate_source.value,
            "crs": self.crs,
            "decoder_version": self.decoder_version,
            "validation_status": self.validation_status.value,
            "validation_reasons": [f.value for f in self.validation_reasons],
            "pair_distance_meters": self.pair_distance_meters,
            "source_dataset_version": self.source_dataset_version,
        }
