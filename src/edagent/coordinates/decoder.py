"""GPS coordinate decoding engine.

Implements official PennDOT DMS coordinate parsing, decimal coordinate parsing,
and spherical distance calculation with rigorous error categorization.
"""

from __future__ import annotations

import math
import re
from typing import Optional, Tuple

from edagent.coordinates.models import (
    CoordinateFormat,
    DecodedCoordinate,
    ValidationFlag,
)

# Regex pattern for official PennDOT DMS text format: DD MM:SS.ddd
# Allows 1-3 digits of degrees, 1-2 digits of minutes, and seconds with optional fractional digits.
DMS_TEXT_PATTERN = re.compile(r"^(\d{1,3})\s+(\d{1,2}):(\d{1,2}(?:\.\d+)?)$")

# Regex pattern for degrees and decimal minutes: DD MM.mmmm
DDM_PATTERN = re.compile(r"^(\d{1,3})\s+(\d{1,2}(?:\.\d+)?)$")

# Regex pattern for standard signed decimal degrees
DECIMAL_PATTERN = re.compile(r"^[+-]?\d{1,3}(?:\.\d+)?$")

# Placeholder strings that signify missing or uninitialized coordinates
PLACEHOLDER_STRINGS = {
    "",
    "0",
    "0.0",
    "0.00",
    "0.000",
    "0.0000",
    "0 00:00.000",
    "0 00:00.00",
    "0 00:00.0",
    "0 00:00",
    "nan",
    "none",
    "null",
    "undefined",
    "99.9999",
    "-99.9999",
    "99 99:99.999",
}


def haversine_distance_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate the great-circle distance between two points in meters.

    Uses the standard Haversine formula on a spherical Earth (R = 6,371,000m).
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    # Clip to prevent numerical domain errors in asin
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return 6371000.0 * c


class GPSDecoder:
    """Decodes police GPS and roadway coordinates into normalized WGS 84 decimal degrees."""

    VERSION = "1.0.0"

    def __init__(
        self,
        latitude_hemisphere: str = "N",
        longitude_hemisphere: str = "W",
        primary_format: CoordinateFormat = CoordinateFormat.DMS_TEXT,
    ) -> None:
        if latitude_hemisphere not in {"N", "S"}:
            raise ValueError(f"Invalid latitude hemisphere: {latitude_hemisphere}")
        if longitude_hemisphere not in {"E", "W"}:
            raise ValueError(f"Invalid longitude hemisphere: {longitude_hemisphere}")

        self.latitude_hemisphere = latitude_hemisphere
        self.longitude_hemisphere = longitude_hemisphere
        self.primary_format = primary_format

    def is_placeholder_or_missing(self, raw: Optional[str]) -> bool:
        """Check if raw string is None, empty, or a recognized placeholder."""
        if raw is None:
            return True
        cleaned = str(raw).strip().lower()
        return cleaned in PLACEHOLDER_STRINGS

    def decode_dms_text(
        self, raw: str, is_longitude: bool = False
    ) -> DecodedCoordinate:
        """Decode DMS text in official PennDOT format: 'DD MM:SS.ddd'."""
        cleaned = raw.strip()
        flags = []

        match = DMS_TEXT_PATTERN.match(cleaned)
        if not match:
            flags.append(
                ValidationFlag.MALFORMED_LONGITUDE_FORMAT
                if is_longitude
                else ValidationFlag.MALFORMED_LATITUDE_FORMAT
            )
            return DecodedCoordinate(
                raw_value=raw,
                decoded_value=None,
                format_detected=None,
                is_valid=False,
                is_missing=False,
                flags=flags,
            )

        deg_str, min_str, sec_str = match.groups()

        try:
            degrees = float(deg_str)
            minutes = float(min_str)
            seconds = float(sec_str)
        except ValueError:
            flags.append(ValidationFlag.NON_NUMERIC_COORDINATE_VALUE)
            return DecodedCoordinate(
                raw_value=raw,
                decoded_value=None,
                format_detected=CoordinateFormat.DMS_TEXT,
                is_valid=False,
                is_missing=False,
                flags=flags,
            )

        # Minute and second validation: must be [0, 60)
        has_error = False
        if not (0.0 <= minutes < 60.0):
            flags.append(ValidationFlag.MINUTES_OUT_OF_RANGE)
            has_error = True
        if not (0.0 <= seconds < 60.0):
            flags.append(ValidationFlag.SECONDS_OUT_OF_RANGE)
            has_error = True

        # Global degree range validation
        max_deg = 180.0 if is_longitude else 90.0
        if not (0.0 <= degrees <= max_deg):
            flags.append(
                ValidationFlag.LONGITUDE_OUT_OF_GLOBAL_RANGE
                if is_longitude
                else ValidationFlag.LATITUDE_OUT_OF_GLOBAL_RANGE
            )
            has_error = True

        if has_error:
            return DecodedCoordinate(
                raw_value=raw,
                decoded_value=None,
                format_detected=CoordinateFormat.DMS_TEXT,
                is_valid=False,
                is_missing=False,
                flags=flags,
            )

        # Calculate decimal degrees
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)

        # Apply hemisphere sign
        if is_longitude:
            if self.longitude_hemisphere == "W":
                decimal = -decimal
        else:
            if self.latitude_hemisphere == "S":
                decimal = -decimal

        return DecodedCoordinate(
            raw_value=raw,
            decoded_value=decimal,
            format_detected=CoordinateFormat.DMS_TEXT,
            is_valid=True,
            is_missing=False,
            flags=flags,
        )

    def decode_decimal_degrees(
        self, raw: str, is_longitude: bool = False
    ) -> DecodedCoordinate:
        """Decode literal decimal degree numbers (e.g. state route coordinates)."""
        cleaned = raw.strip()
        flags = []

        if not DECIMAL_PATTERN.match(cleaned):
            flags.append(
                ValidationFlag.MALFORMED_LONGITUDE_FORMAT
                if is_longitude
                else ValidationFlag.MALFORMED_LATITUDE_FORMAT
            )
            return DecodedCoordinate(
                raw_value=raw,
                decoded_value=None,
                format_detected=None,
                is_valid=False,
                is_missing=False,
                flags=flags,
            )

        try:
            val = float(cleaned)
        except ValueError:
            flags.append(ValidationFlag.NON_NUMERIC_COORDINATE_VALUE)
            return DecodedCoordinate(
                raw_value=raw,
                decoded_value=None,
                format_detected=CoordinateFormat.DECIMAL_DEGREES,
                is_valid=False,
                is_missing=False,
                flags=flags,
            )

        max_val = 180.0 if is_longitude else 90.0
        if not (-max_val <= val <= max_val):
            flags.append(
                ValidationFlag.LONGITUDE_OUT_OF_GLOBAL_RANGE
                if is_longitude
                else ValidationFlag.LATITUDE_OUT_OF_GLOBAL_RANGE
            )
            return DecodedCoordinate(
                raw_value=raw,
                decoded_value=None,
                format_detected=CoordinateFormat.DECIMAL_DEGREES,
                is_valid=False,
                is_missing=False,
                flags=flags,
            )

        return DecodedCoordinate(
            raw_value=raw,
            decoded_value=val,
            format_detected=CoordinateFormat.DECIMAL_DEGREES,
            is_valid=True,
            is_missing=False,
            flags=flags,
        )

    def decode_coordinate(
        self, raw: Optional[Any], is_longitude: bool = False
    ) -> DecodedCoordinate:
        """Decode a single coordinate axis, automatically detecting the representation."""
        if raw is None or self.is_placeholder_or_missing(str(raw)):
            return DecodedCoordinate(
                raw_value=str(raw) if raw is not None else None,
                decoded_value=None,
                format_detected=None,
                is_valid=False,
                is_missing=True,
                flags=[
                    ValidationFlag.MISSING_POLICE_LONGITUDE
                    if is_longitude
                    else ValidationFlag.MISSING_POLICE_LATITUDE
                ],
            )

        str_val = str(raw).strip()

        # Try DMS text first if colon is present
        if ":" in str_val or " " in str_val:
            return self.decode_dms_text(str_val, is_longitude=is_longitude)

        # Otherwise try decimal degrees
        return self.decode_decimal_degrees(str_val, is_longitude=is_longitude)

    def decode_police_pair(
        self, raw_lat: Optional[Any], raw_lon: Optional[Any]
    ) -> Tuple[DecodedCoordinate, DecodedCoordinate]:
        """Decode a full pair of police GPS coordinates."""
        lat_res = self.decode_coordinate(raw_lat, is_longitude=False)
        lon_res = self.decode_coordinate(raw_lon, is_longitude=True)
        return lat_res, lon_res
