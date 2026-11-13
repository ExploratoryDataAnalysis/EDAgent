"""Intersection identification and stable identifier generation module.

Developed under historical Project Plan v2 (§12–15) and Phase 3 Module C requirements; v3 governs release scope.
Generates reproducible, order-invariant, municipality-scoped intersection IDs.
"""

from __future__ import annotations

import hashlib
from typing import Dict, List, Optional, Set, Tuple

from edagent.coordinates.decoder import haversine_distance_meters
from edagent.roadway.normalization import normalize_street_name, parse_intersection_streets
from edagent.roadway.schema import RoadClass, SiteRecord, SiteType

DEFAULT_INTERSECTION_RADIUS_METERS = 30.48  # 100 feet standard intersection catchment


class IntersectionIdentifier:
    """Utilities for generating reproducible, order-invariant intersection identifiers."""

    @staticmethod
    def canonical_streets(street_names: List[str]) -> List[str]:
        """Normalize, deduplicate, and alphabetically sort street names.

        Guarantees order invariance:
        ['FORBES AVE', 'CRAFT AVE'] -> ['CRAFT AVE', 'FORBES AVE']
        """
        normalized_set: Set[str] = set()
        for raw in street_names:
            if not raw:
                continue
            norm = normalize_street_name(raw)
            if norm:
                normalized_set.add(norm)

        return sorted(normalized_set)

    @classmethod
    def generate_id(cls, muni_code: str, street_names: List[str]) -> str:
        """Generate a deterministic semantic intersection identifier.

        Format: INT:{muni_code}:{STREET1}:{STREET2}...
        Example: INT:02101:CRAFT AVE:FORBES AVE

        Raises:
            ValueError: If muni_code is empty or fewer than 2 distinct streets are provided.
        """
        clean_muni = str(muni_code).strip()
        if not clean_muni:
            raise ValueError("muni_code must not be empty")

        streets = cls.canonical_streets(street_names)
        if len(streets) < 2:
            raise ValueError(
                f"Intersection requires at least 2 distinct street names, got {len(streets)}: {streets}"
            )

        streets_joined = ":".join(streets)
        return f"INT:{clean_muni}:{streets_joined}"

    @classmethod
    def generate_hash_id(cls, muni_code: str, street_names: List[str], length: int = 12) -> str:
        """Generate a deterministic short hash intersection identifier.

        Format: INT-{muni_code}-{sha256[:12]}
        Example: INT-02101-7a8b9c0d1e2f
        """
        canonical_str = cls.generate_id(muni_code, street_names)
        digest = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()[:length]
        clean_muni = str(muni_code).strip()
        return f"INT-{clean_muni}-{digest}"

    @classmethod
    def generate_canonical_name(
        cls, street_names: List[str], muni_name: Optional[str] = None
    ) -> str:
        """Create a human-readable canonical intersection name.

        Example: 'CRAFT AVE & FORBES AVE' or 'CRAFT AVE & FORBES AVE (PITTSBURGH)'
        """
        streets = cls.canonical_streets(street_names)
        base = " & ".join(streets)
        if muni_name and str(muni_name).strip():
            return f"{base} ({str(muni_name).strip()})"
        return base


class IntersectionSite:
    """Represents a validated physical intersection entity with geometry and approach attributes."""

    def __init__(
        self,
        site_id: str,
        canonical_name: str,
        municipality_code: str,
        street_names: List[str],
        centroid_lat: Optional[float] = None,
        centroid_lon: Optional[float] = None,
        radius_meters: float = DEFAULT_INTERSECTION_RADIUS_METERS,
        municipality_name: Optional[str] = None,
        road_class: RoadClass = RoadClass.LOCAL_STREET,
        source_reference_ids: Optional[List[str]] = None,
        aliases: Optional[Dict[str, str]] = None,
    ):
        self.site_id = site_id
        self.canonical_name = canonical_name
        self.municipality_code = str(municipality_code).strip()
        self.street_names = IntersectionIdentifier.canonical_streets(street_names)
        self.centroid_lat = centroid_lat
        self.centroid_lon = centroid_lon
        self.radius_meters = radius_meters
        self.municipality_name = municipality_name
        self.road_class = road_class
        self.source_reference_ids = source_reference_ids or []
        self.aliases = aliases or {}

    @classmethod
    def from_streets(
        cls,
        muni_code: str,
        street_names: List[str],
        centroid_lat: Optional[float] = None,
        centroid_lon: Optional[float] = None,
        radius_meters: float = DEFAULT_INTERSECTION_RADIUS_METERS,
        municipality_name: Optional[str] = None,
        road_class: RoadClass = RoadClass.LOCAL_STREET,
        source_reference_ids: Optional[List[str]] = None,
        aliases: Optional[Dict[str, str]] = None,
    ) -> IntersectionSite:
        """Construct an IntersectionSite with automatically generated canonical ID and name."""
        site_id = IntersectionIdentifier.generate_id(muni_code, street_names)
        canonical_name = IntersectionIdentifier.generate_canonical_name(street_names, municipality_name)
        return cls(
            site_id=site_id,
            canonical_name=canonical_name,
            municipality_code=muni_code,
            street_names=street_names,
            centroid_lat=centroid_lat,
            centroid_lon=centroid_lon,
            radius_meters=radius_meters,
            municipality_name=municipality_name,
            road_class=road_class,
            source_reference_ids=source_reference_ids,
            aliases=aliases,
        )

    def matches_point(self, lat: float, lon: float) -> Tuple[bool, float]:
        """Check if coordinates fall within the intersection catchment radius.

        Returns:
            Tuple of (is_within_radius, distance_meters).
        """
        if self.centroid_lat is None or self.centroid_lon is None:
            return False, float("inf")

        distance = haversine_distance_meters(lat, lon, self.centroid_lat, self.centroid_lon)
        return distance <= self.radius_meters, distance

    def corroborates_streets(self, query_streets: List[str]) -> float:
        """Calculate street name corroboration score between 0.0 and 1.0.

        1.0: Full match of multiple approach streets.
        0.5: Partial match (at least 1 approach street matches).
        0.0: No matching street names.
        """
        if not query_streets:
            return 0.0

        query_normalized = {normalize_street_name(s) for s in query_streets if s}
        # Resolve aliases
        query_resolved = set()
        for q in query_normalized:
            query_resolved.add(q)
            if q in self.aliases:
                query_resolved.add(self.aliases[q])

        intersection_streets = set(self.street_names)
        for s in self.street_names:
            if s in self.aliases:
                intersection_streets.add(self.aliases[s])

        matched_count = len(query_resolved.intersection(intersection_streets))
        if matched_count >= 2:
            return 1.0
        elif matched_count == 1:
            return 0.5
        return 0.0

    def to_site_record(self) -> SiteRecord:
        """Convert to a standardized SiteRecord for registry storage."""
        return SiteRecord(
            site_id=self.site_id,
            site_type=SiteType.INTERSECTION,
            canonical_name=self.canonical_name,
            municipality_code=self.municipality_code,
            municipality_name=self.municipality_name,
            road_class=self.road_class,
            street_names=self.street_names,
            centroid_lat=self.centroid_lat,
            centroid_lon=self.centroid_lon,
            source_reference_ids=self.source_reference_ids,
        )
