"""EDAgent coordinates package.

Provides official GPS decoding, quality validation, and coordinate lifecycle management.
"""

from edagent.coordinates.decoder import GPSDecoder, haversine_distance_meters
from edagent.coordinates.models import (
    CoordinateFormat,
    CoordinateRecord,
    CoordinateSource,
    DecodedCoordinate,
    ValidationFlag,
    ValidationStatus,
)
from edagent.coordinates.pipeline import CoordinatePipeline
from edagent.coordinates.validator import CoordinateValidator

__all__ = [
    "GPSDecoder",
    "CoordinateValidator",
    "CoordinatePipeline",
    "CoordinateRecord",
    "DecodedCoordinate",
    "ValidationStatus",
    "ValidationFlag",
    "CoordinateFormat",
    "CoordinateSource",
    "haversine_distance_meters",
]
