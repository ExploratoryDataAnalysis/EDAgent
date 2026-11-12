"""Road segment identification, LRS parsing, and spatial snapping module.

Governed by Project Plan v2 (§12–15) and Phase 3 Module C requirements.
Supports PennDOT State Route Linear Referencing System (LRS), County Centerlines,
and local municipal road segments with deterministic identifiers.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple

from edagent.coordinates.decoder import haversine_distance_meters
from edagent.roadway.normalization import normalize_route_number, normalize_street_name
from edagent.roadway.schema import RoadClass, SiteRecord, SiteType

DEFAULT_MAX_SNAP_DISTANCE_METERS = 50.0  # Maximum snapping distance threshold (50m)


class SegmentIdentifier:
    """Utilities for generating reproducible, standardized road segment identifiers."""

    @staticmethod
    def generate_state_segment_id(
        county_code: str,
        route: str,
        segment: str,
    ) -> str:
        """Generate a deterministic PennDOT State Route segment identifier.

        Format: SEG:{county_code}:SR{route_4}:{segment_4}
        Example: SEG:02:SR0022:0040

        Raises:
            ValueError: If route or segment numbers cannot be normalized to 4 digits.
        """
        clean_county = str(county_code).strip().zfill(2)
        norm_route = normalize_route_number(route)
        if not norm_route:
            raise ValueError(f"Invalid state route number: {route}")

        seg_digits = re.findall(r"\d+", str(segment).strip())
        if not seg_digits:
            raise ValueError(f"Invalid segment number: {segment}")
        norm_seg = f"{int(seg_digits[0]):04d}"

        return f"SEG:{clean_county}:SR{norm_route}:{norm_seg}"

    @staticmethod
    def generate_centerline_segment_id(feature_key: str) -> str:
        """Generate a deterministic County Centerline segment identifier.

        Format: SEG:AC:{feature_key}
        Example: SEG:AC:RCL100234
        """
        clean_key = str(feature_key).strip().upper()
        if not clean_key:
            raise ValueError("Feature key must not be empty")
        return f"SEG:AC:{clean_key}"

    @staticmethod
    def generate_local_segment_id(
        muni_code: str,
        street_name: str,
        segment_id: str,
    ) -> str:
        """Generate a deterministic local street segment identifier.

        Format: SEG:{muni_code}:{normalized_street}:{segment_id}
        Example: SEG:02101:MAIN ST:0100
        """
        clean_muni = str(muni_code).strip()
        norm_street = normalize_street_name(street_name)
        clean_seg = str(segment_id).strip().upper()
        if not clean_muni or not norm_street:
            raise ValueError("muni_code and street_name must not be empty")
        return f"SEG:{clean_muni}:{norm_street}:{clean_seg}"

    @staticmethod
    def determine_penndot_direction(segment: str, is_divided: bool = True) -> str:
        """Determine direction of travel from PennDOT segment numbering.

        PennDOT convention:
        - Divided highways:
          - Even segment numbers (0010, 0020, 0030...) = Northbound or Eastbound.
          - Odd segment numbers (0011, 0021, 0031...) = Southbound or Westbound.
        - Undivided highways:
          - Even segment numbers for both directions.
        """
        seg_digits = re.findall(r"\d+", str(segment).strip())
        if not seg_digits:
            return "UNKNOWN"

        seg_num = int(seg_digits[0])
        if not is_divided:
            return "BIDIRECTIONAL"

        if seg_num % 2 == 0:
            return "NORTH_EAST"
        else:
            return "SOUTH_WEST"


def point_to_line_segment_distance(
    pt_lat: float,
    pt_lon: float,
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> Tuple[float, float, float]:
    """Calculate the shortest distance from a point to a 2D line segment in meters.

    Uses a local equirectangular flat-Earth projection centered at the segment midpoint.
    Returns:
        Tuple of (distance_meters, closest_lat, closest_lon).
    """
    mid_lat = (start_lat + end_lat) / 2.0
    cos_lat = math.cos(math.radians(mid_lat))
    m_per_deg_lat = 111132.954 - 559.822 * math.cos(2 * math.radians(mid_lat))
    m_per_deg_lon = 111412.84 * cos_lat

    # Convert coordinates to local Cartesian coordinates (meters)
    # Origin at start point
    p_x = (pt_lon - start_lon) * m_per_deg_lon
    p_y = (pt_lat - start_lat) * m_per_deg_lat

    b_x = (end_lon - start_lon) * m_per_deg_lon
    b_y = (end_lat - start_lat) * m_per_deg_lat

    # Vector dot products
    v_len_sq = b_x * b_x + b_y * b_y
    if v_len_sq == 0:
        # Segment is a single point
        dist = math.hypot(p_x, p_y)
        return dist, start_lat, start_lon

    # Parameter t of the closest point on segment AB
    t = (p_x * b_x + p_y * b_y) / v_len_sq
    t_clamped = max(0.0, min(1.0, t))

    closest_x = t_clamped * b_x
    closest_y = t_clamped * b_y

    dist = math.hypot(p_x - closest_x, p_y - closest_y)

    closest_lat = start_lat + (closest_y / m_per_deg_lat)
    closest_lon = start_lon + (closest_x / m_per_deg_lon)

    return dist, closest_lat, closest_lon


class RoadSegmentSite:
    """Represents a validated physical road segment entity with geometry and reference attributes."""

    def __init__(
        self,
        site_id: str,
        canonical_name: str,
        road_class: RoadClass,
        municipality_code: Optional[str] = None,
        municipality_name: Optional[str] = None,
        street_name: Optional[str] = None,
        route_number: Optional[str] = None,
        segment_number: Optional[str] = None,
        direction: Optional[str] = None,
        start_coord: Optional[Tuple[float, float]] = None,
        end_coord: Optional[Tuple[float, float]] = None,
        midpoint_coord: Optional[Tuple[float, float]] = None,
        max_snap_distance: float = DEFAULT_MAX_SNAP_DISTANCE_METERS,
        source_reference_ids: Optional[List[str]] = None,
    ):
        self.site_id = site_id
        self.canonical_name = canonical_name
        self.road_class = road_class
        self.municipality_code = str(municipality_code).strip() if municipality_code else None
        self.municipality_name = municipality_name
        self.street_name = normalize_street_name(street_name) if street_name else None
        self.route_number = normalize_route_number(route_number) if route_number else None
        self.segment_number = segment_number
        self.direction = direction
        self.start_coord = start_coord
        self.end_coord = end_coord
        self.max_snap_distance = max_snap_distance
        self.source_reference_ids = source_reference_ids or []

        # Derive midpoint if not explicitly given
        if midpoint_coord:
            self.midpoint_coord = midpoint_coord
        elif start_coord and end_coord:
            self.midpoint_coord = (
                (start_coord[0] + end_coord[0]) / 2.0,
                (start_coord[1] + end_coord[1]) / 2.0,
            )
        elif start_coord:
            self.midpoint_coord = start_coord
        else:
            self.midpoint_coord = None

    @classmethod
    def from_penndot_lrs(
        cls,
        county_code: str,
        route: str,
        segment: str,
        street_name: Optional[str] = None,
        municipality_code: Optional[str] = None,
        municipality_name: Optional[str] = None,
        road_class: Optional[RoadClass] = None,
        start_coord: Optional[Tuple[float, float]] = None,
        end_coord: Optional[Tuple[float, float]] = None,
        source_reference_id: Optional[str] = None,
    ) -> RoadSegmentSite:
        """Construct a RoadSegmentSite from PennDOT LRS attributes."""
        site_id = SegmentIdentifier.generate_state_segment_id(county_code, route, segment)
        norm_route = normalize_route_number(route) or route
        clean_seg = str(segment).strip().zfill(4)
        canonical_name = f"SR {norm_route} SEG {clean_seg}"
        if street_name:
            canonical_name = f"{canonical_name} ({normalize_street_name(street_name)})"

        if road_class is None:
            road_class = RoadClass.INTERSTATE if norm_route in {"0076", "0079", "0279", "0376", "0576", "0579"} else RoadClass.STATE_ROUTE

        direction = SegmentIdentifier.determine_penndot_direction(segment)

        return cls(
            site_id=site_id,
            canonical_name=canonical_name,
            road_class=road_class,
            municipality_code=municipality_code,
            municipality_name=municipality_name,
            street_name=street_name,
            route_number=norm_route,
            segment_number=clean_seg,
            direction=direction,
            start_coord=start_coord,
            end_coord=end_coord,
            source_reference_ids=[source_reference_id] if source_reference_id else [],
        )

    @classmethod
    def from_centerline(
        cls,
        feature_key: str,
        street_name: str,
        road_class: RoadClass,
        municipality_code: Optional[str] = None,
        municipality_name: Optional[str] = None,
        start_coord: Optional[Tuple[float, float]] = None,
        end_coord: Optional[Tuple[float, float]] = None,
        source_reference_id: Optional[str] = None,
    ) -> RoadSegmentSite:
        """Construct a RoadSegmentSite from County Centerline attributes."""
        site_id = SegmentIdentifier.generate_centerline_segment_id(feature_key)
        norm_name = normalize_street_name(street_name)
        canonical_name = f"{norm_name} [{feature_key}]"

        return cls(
            site_id=site_id,
            canonical_name=canonical_name,
            road_class=road_class,
            municipality_code=municipality_code,
            municipality_name=municipality_name,
            street_name=norm_name,
            start_coord=start_coord,
            end_coord=end_coord,
            source_reference_ids=[source_reference_id] if source_reference_id else [],
        )

    def distance_to_point(self, lat: float, lon: float) -> Tuple[float, Optional[Tuple[float, float]]]:
        """Compute the shortest distance in meters from coordinates to the segment.

        Uses line-segment projection if endpoints are available; otherwise midpoint haversine.
        Returns:
            Tuple of (distance_meters, (closest_lat, closest_lon)).
        """
        if self.start_coord and self.end_coord:
            dist, c_lat, c_lon = point_to_line_segment_distance(
                lat, lon,
                self.start_coord[0], self.start_coord[1],
                self.end_coord[0], self.end_coord[1],
            )
            return dist, (c_lat, c_lon)

        if self.midpoint_coord:
            dist = haversine_distance_meters(
                lat, lon, self.midpoint_coord[0], self.midpoint_coord[1]
            )
            return dist, self.midpoint_coord

        return float("inf"), None

    def corroborates(
        self,
        query_street: Optional[str] = None,
        query_route: Optional[str] = None,
    ) -> float:
        """Evaluate name and route corroboration between crash and segment.

        Returns:
            1.0: Full match of route number or exact street name.
            0.5: Partial token match of street name.
            0.0: No match.
        """
        score = 0.0

        # Check route match
        if query_route and self.route_number:
            norm_q_route = normalize_route_number(query_route)
            if norm_q_route and norm_q_route == self.route_number:
                return 1.0

        # Check street name match
        if query_street and self.street_name:
            norm_q_street = normalize_street_name(query_street)
            if norm_q_street:
                if norm_q_street == self.street_name:
                    return 1.0
                # Check token containment (e.g., "LIBERTY" vs "LIBERTY AVE")
                q_tokens = set(norm_q_street.split())
                seg_tokens = set(self.street_name.split())
                if q_tokens and seg_tokens:
                    overlap = q_tokens.intersection(seg_tokens)
                    if overlap and len(overlap) >= len(q_tokens) * 0.5:
                        score = max(score, 0.5)

        return score

    def to_site_record(self) -> SiteRecord:
        """Convert to a standardized SiteRecord for registry storage."""
        lat = self.midpoint_coord[0] if self.midpoint_coord else None
        lon = self.midpoint_coord[1] if self.midpoint_coord else None
        streets = [self.street_name] if self.street_name else []

        return SiteRecord(
            site_id=self.site_id,
            site_type=SiteType.SEGMENT,
            canonical_name=self.canonical_name,
            municipality_code=self.municipality_code,
            municipality_name=self.municipality_name,
            road_class=self.road_class,
            street_names=streets,
            centroid_lat=lat,
            centroid_lon=lon,
            source_reference_ids=self.source_reference_ids,
        )
