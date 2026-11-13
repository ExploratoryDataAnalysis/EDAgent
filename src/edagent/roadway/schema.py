"""Schema definitions for roadway crosswalk, sites, and matching lifecycle.

Developed under historical Project Plan v2 (§12–15); v3 governs release scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SiteType(str, Enum):
    """Categorization of a roadway physical location."""
    INTERSECTION = "INTERSECTION"
    SEGMENT = "SEGMENT"
    UNMATCHED = "UNMATCHED"


class RoadClass(str, Enum):
    """Functional and administrative classification of a roadway."""
    INTERSTATE = "INTERSTATE"
    STATE_ROUTE = "STATE_ROUTE"
    COUNTY_ROAD = "COUNTY_ROAD"
    LOCAL_STREET = "LOCAL_STREET"
    RAMP = "RAMP"
    UNKNOWN = "UNKNOWN"


class MatchMethod(str, Enum):
    """Specific methodological stage that resolved or rejected a site match."""
    EXACT_LRS = "EXACT_LRS"                              # Stage 1: State Route + Segment + Offset match
    INTERSECTION_JUNCTION = "INTERSECTION_JUNCTION"      # Stage 2: Validated intersection approach & node
    SEGMENT_SPATIAL_SNAP = "SEGMENT_SPATIAL_SNAP"        # Stage 3: Distance-bounded centerline snap
    AMBIGUOUS_CONFLICT = "AMBIGUOUS_CONFLICT"            # Stage 4: Police vs state decimal coordinate conflict >500m
    AMBIGUOUS_MULTI_CANDIDATE = "AMBIGUOUS_MULTI_CANDIDATE" # Stage 4: Multiple equidistant candidates with equal evidence
    UNMATCHED_DISTANCE = "UNMATCHED_DISTANCE"            # Stage 5: Exceeds maximum distance threshold (>50m)
    UNMATCHED_MISSING = "UNMATCHED_MISSING"              # Stage 5: Missing crash coordinates
    UNMATCHED_OUT_OF_BOUNDS = "UNMATCHED_OUT_OF_BOUNDS"  # Stage 5: Coordinates outside project boundary


class MatchStatus(str, Enum):
    """Resolution status of the crosswalk link."""
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED = "UNMATCHED"


class MatchConfidence(str, Enum):
    """Documented categorical confidence tiers (not calibrated statistical probabilities)."""
    HIGH = "HIGH"        # Exact LRS match or intersection match with corroborating street name & distance <= 30m
    MEDIUM = "MEDIUM"    # Midblock spatial snap within 25m with corroborating street name/route
    LOW = "LOW"          # Spatial snap 25m–50m with partial attribute corroboration
    NONE = "NONE"        # Ambiguous or unmatched


@dataclass
class CandidateSite:
    """A candidate roadway site evaluated for matching."""
    site_id: str
    site_type: SiteType
    distance_meters: float
    corroboration_score: float  # 0.0 to 1.0 based on name/route agreement
    source_reference_id: str
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "site_id": self.site_id,
            "site_type": self.site_type.value,
            "distance_meters": round(self.distance_meters, 2),
            "corroboration_score": round(self.corroboration_score, 2),
            "source_reference_id": self.source_reference_id,
            "notes": self.notes,
        }


@dataclass
class SiteRecord:
    """Registered entity in the Stable Identifier Registry."""
    site_id: str
    site_type: SiteType
    canonical_name: str
    municipality_code: Optional[str] = None
    municipality_name: Optional[str] = None
    road_class: RoadClass = RoadClass.UNKNOWN
    street_names: List[str] = field(default_factory=list)
    centroid_lat: Optional[float] = None
    centroid_lon: Optional[float] = None
    source_reference_ids: List[str] = field(default_factory=list)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "site_id": self.site_id,
            "site_type": self.site_type.value,
            "canonical_name": self.canonical_name,
            "municipality_code": self.municipality_code,
            "municipality_name": self.municipality_name,
            "road_class": self.road_class.value,
            "street_names": self.street_names,
            "centroid_lat": round(self.centroid_lat, 6) if self.centroid_lat is not None else None,
            "centroid_lon": round(self.centroid_lon, 6) if self.centroid_lon is not None else None,
            "source_reference_ids": self.source_reference_ids,
            "version": self.version,
        }


@dataclass
class CrosswalkRecord:
    """Deterministic, traceable mapping between a single crash and its primary road site.

    Enforces the One-Primary-Site Rule: exactly 1 primary site ID when MATCHED;
    None when AMBIGUOUS or UNMATCHED.
    """
    crash_id: int
    crash_year: Optional[int]
    primary_site_id: Optional[str]
    site_type: SiteType
    road_class: RoadClass
    match_method: MatchMethod
    match_status: MatchStatus
    match_confidence: MatchConfidence
    candidate_site_count: int
    secondary_candidates: List[CandidateSite] = field(default_factory=list)
    snap_distance_meters: Optional[float] = None
    source_reference_id: Optional[str] = None
    coordinate_validation_status: str = "VALID"
    crosswalk_version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "crash_id": self.crash_id,
            "crash_year": self.crash_year,
            "primary_site_id": self.primary_site_id,
            "site_type": self.site_type.value,
            "road_class": self.road_class.value,
            "match_method": self.match_method.value,
            "match_status": self.match_status.value,
            "match_confidence": self.match_confidence.value,
            "candidate_site_count": self.candidate_site_count,
            "secondary_candidates": [c.to_dict() for c in self.secondary_candidates],
            "snap_distance_meters": (
                round(self.snap_distance_meters, 2)
                if self.snap_distance_meters is not None
                else None
            ),
            "source_reference_id": self.source_reference_id,
            "coordinate_validation_status": self.coordinate_validation_status,
            "crosswalk_version": self.crosswalk_version,
        }
