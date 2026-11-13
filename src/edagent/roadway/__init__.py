"""Roadway crosswalk, normalization, and stable site identification package.

Developed under historical Project Plan v2 (§12–15) and Phase 3 Module C requirements; v3 governs release scope.
"""

from edagent.roadway.intersections import (
    DEFAULT_INTERSECTION_RADIUS_METERS,
    IntersectionIdentifier,
    IntersectionSite,
)
from edagent.roadway.matching import (
    MAX_SNAP_DISTANCE_METERS,
    TIE_DISTANCE_TOLERANCE_METERS,
    CrashSiteMatcher,
)
from edagent.roadway.normalization import (
    DIRECTIONAL_MAP,
    STREET_SUFFIX_MAP,
    map_road_class,
    normalize_route_number,
    normalize_street_name,
    parse_intersection_streets,
)
from edagent.roadway.registry import SiteRegistry
from edagent.roadway.schema import (
    CandidateSite,
    CrosswalkRecord,
    MatchConfidence,
    MatchMethod,
    MatchStatus,
    RoadClass,
    SiteRecord,
    SiteType,
)
from edagent.roadway.segments import (
    DEFAULT_MAX_SNAP_DISTANCE_METERS,
    RoadSegmentSite,
    SegmentIdentifier,
    point_to_line_segment_distance,
)

__all__ = [
    # Schemas
    "SiteType",
    "RoadClass",
    "MatchMethod",
    "MatchStatus",
    "MatchConfidence",
    "CandidateSite",
    "SiteRecord",
    "CrosswalkRecord",
    # Normalization
    "STREET_SUFFIX_MAP",
    "DIRECTIONAL_MAP",
    "normalize_street_name",
    "normalize_route_number",
    "parse_intersection_streets",
    "map_road_class",
    # Intersections
    "DEFAULT_INTERSECTION_RADIUS_METERS",
    "IntersectionIdentifier",
    "IntersectionSite",
    # Segments
    "DEFAULT_MAX_SNAP_DISTANCE_METERS",
    "SegmentIdentifier",
    "RoadSegmentSite",
    "point_to_line_segment_distance",
    # Registry
    "SiteRegistry",
    # Matching
    "MAX_SNAP_DISTANCE_METERS",
    "TIE_DISTANCE_TOLERANCE_METERS",
    "CrashSiteMatcher",
]
