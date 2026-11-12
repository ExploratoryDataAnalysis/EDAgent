"""Staged crash-to-site matching engine.

Governed by Project Plan v2 (§12–15) and Phase 3 Module C requirements.
Enforces the strict One-Primary-Site Rule:
- Exactly one primary site ID when resolved (MATCHED).
- Zero primary site matches when unresolved (AMBIGUOUS or UNMATCHED).
Never counts a crash multiple times in primary site-level analyses.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from edagent.coordinates.models import CoordinateRecord, ValidationFlag, ValidationStatus
from edagent.roadway.intersections import DEFAULT_INTERSECTION_RADIUS_METERS, IntersectionIdentifier
from edagent.roadway.normalization import (
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

MAX_SNAP_DISTANCE_METERS = 50.0
TIE_DISTANCE_TOLERANCE_METERS = 2.0  # Distance difference below which candidates are considered tied


class CrashSiteMatcher:
    """Staged matcher assigning crashes to physical intersection and segment sites."""

    def __init__(self, registry: SiteRegistry) -> None:
        self.registry = registry

    def match(
        self,
        crash_data: Dict[str, Any],
        coord_rec: Optional[CoordinateRecord] = None,
    ) -> CrosswalkRecord:
        """Execute the 5-stage matching pipeline for a single crash record.

        Stages:
        1. Exact reference-identifier match (EXACT_LRS)
        2. Validated intersection match (INTERSECTION_JUNCTION)
        3. Validated road-segment spatial match (SEGMENT_SPATIAL_SNAP)
        4. Ambiguous classification (AMBIGUOUS_CONFLICT or AMBIGUOUS_MULTI_CANDIDATE)
        5. Unmatched classification (UNMATCHED_DISTANCE, UNMATCHED_MISSING, UNMATCHED_OUT_OF_BOUNDS)
        """
        crn_raw = (
            crash_data.get("CRASH_CRN")
            or crash_data.get("CRN")
            or crash_data.get("crash_id")
            or crash_data.get("crash_crn")
            or (coord_rec.crash_crn if coord_rec else 0)
        )
        try:
            crash_id = int(crn_raw)
        except (ValueError, TypeError):
            crash_id = 0
        year_raw = crash_data.get("CRASH_YEAR")
        crash_year = int(year_raw) if year_raw is not None and str(year_raw).isdigit() else None

        coord_status_str = "VALID"
        lat: Optional[float] = None
        lon: Optional[float] = None

        if coord_rec:
            coord_status_str = coord_rec.validation_status.value
            lat = coord_rec.decoded_latitude
            lon = coord_rec.decoded_longitude
        else:
            # Check if lat/lon provided in dictionary
            raw_lat = crash_data.get("LATITUDE") or crash_data.get("DEC_LAT")
            raw_lon = crash_data.get("LONGITUDE") or crash_data.get("DEC_LONG")
            if raw_lat is not None and raw_lon is not None:
                try:
                    lat_f = float(raw_lat)
                    lon_f = float(raw_lon)
                    if not (math.isnan(lat_f) or math.isnan(lon_f) or math.isinf(lat_f) or math.isinf(lon_f)):
                        lat = lat_f
                        lon = lon_f
                    else:
                        lat = None
                        lon = None
                except (ValueError, TypeError):
                    lat = None
                    lon = None

        # Road class inference from crash attributes
        crash_road_class = map_road_class(
            road_owner=crash_data.get("ROAD_OWNER"),
            route=str(crash_data.get("ROUTE") or ""),
        )

        # -------------------------------------------------------------------------
        # PRE-CHECK: Coordinate Quality Gating
        # -------------------------------------------------------------------------
        if coord_rec and coord_rec.validation_status == ValidationStatus.CONFLICT:
            # Frozen baseline requirement: coordinate conflict >500m must be gated as AMBIGUOUS
            return CrosswalkRecord(
                crash_id=crash_id,
                crash_year=crash_year,
                primary_site_id=None,
                site_type=SiteType.UNMATCHED,
                road_class=crash_road_class,
                match_method=MatchMethod.AMBIGUOUS_CONFLICT,
                match_status=MatchStatus.AMBIGUOUS,
                match_confidence=MatchConfidence.NONE,
                candidate_site_count=0,
                coordinate_validation_status=coord_status_str,
            )

        if coord_rec and (
            coord_rec.validation_status == ValidationStatus.INVALID
            or ValidationFlag.OUTSIDE_COUNTY_BOUNDARY in coord_rec.validation_reasons
            or ValidationFlag.LATITUDE_OUT_OF_REGIONAL_BOUNDS in coord_rec.validation_reasons
            or ValidationFlag.LONGITUDE_OUT_OF_REGIONAL_BOUNDS in coord_rec.validation_reasons
        ):
            return CrosswalkRecord(
                crash_id=crash_id,
                crash_year=crash_year,
                primary_site_id=None,
                site_type=SiteType.UNMATCHED,
                road_class=crash_road_class,
                match_method=MatchMethod.UNMATCHED_OUT_OF_BOUNDS,
                match_status=MatchStatus.UNMATCHED,
                match_confidence=MatchConfidence.NONE,
                candidate_site_count=0,
                coordinate_validation_status=coord_status_str,
            )

        # -------------------------------------------------------------------------
        # STAGE 1: Exact Reference-Identifier Match (EXACT_LRS)
        # -------------------------------------------------------------------------
        raw_route = crash_data.get("ROUTE")
        raw_seg = crash_data.get("SEGMENT")
        if raw_route and raw_seg:
            norm_route = normalize_route_number(str(raw_route))
            if norm_route:
                lrs_site = self.registry.find_segment_by_lrs("02", norm_route, str(raw_seg))
                if lrs_site:
                    # Verified exact match
                    return CrosswalkRecord(
                        crash_id=crash_id,
                        crash_year=crash_year,
                        primary_site_id=lrs_site.site_id,
                        site_type=SiteType.SEGMENT,
                        road_class=lrs_site.road_class,
                        match_method=MatchMethod.EXACT_LRS,
                        match_status=MatchStatus.MATCHED,
                        match_confidence=MatchConfidence.HIGH,
                        candidate_site_count=1,
                        source_reference_id=(
                            lrs_site.source_reference_ids[0]
                            if lrs_site.source_reference_ids
                            else None
                        ),
                        coordinate_validation_status=coord_status_str,
                    )

        # If coordinates are missing and Stage 1 could not resolve LRS:
        if lat is None or lon is None:
            return CrosswalkRecord(
                crash_id=crash_id,
                crash_year=crash_year,
                primary_site_id=None,
                site_type=SiteType.UNMATCHED,
                road_class=crash_road_class,
                match_method=MatchMethod.UNMATCHED_MISSING,
                match_status=MatchStatus.UNMATCHED,
                match_confidence=MatchConfidence.NONE,
                candidate_site_count=0,
                coordinate_validation_status=coord_status_str,
            )

        # -------------------------------------------------------------------------
        # STAGE 2: Validated Intersection Match (INTERSECTION_JUNCTION)
        # -------------------------------------------------------------------------
        is_intersection_flag = (
            str(crash_data.get("INTERSECTION") or "").strip() == "1"
            or str(crash_data.get("INTERSECT_TYPE") or "").strip() not in {"", "0", "99", "None"}
        )
        street_raw = crash_data.get("STREET_NAME") or ""
        parsed_streets = parse_intersection_streets(street_raw)
        muni_code = str(crash_data.get("MUNICIPALITY") or "").strip()

        if is_intersection_flag or len(parsed_streets) >= 2:
            # 2a. Attempt intersection lookup by municipality and parsed street names
            if muni_code and len(parsed_streets) >= 2:
                matched_int = self.registry.find_intersection(muni_code, parsed_streets)
                if matched_int and matched_int.centroid_lat is not None and matched_int.centroid_lon is not None:
                    nearby = self.registry.find_nearby_sites(
                        lat, lon, max_distance_meters=MAX_SNAP_DISTANCE_METERS, site_type=SiteType.INTERSECTION
                    )
                    # Check if matched_int is within distance
                    for s, dist in nearby:
                        if s.site_id == matched_int.site_id:
                            confidence = (
                                MatchConfidence.HIGH
                                if dist <= DEFAULT_INTERSECTION_RADIUS_METERS
                                else MatchConfidence.MEDIUM
                            )
                            return CrosswalkRecord(
                                crash_id=crash_id,
                                crash_year=crash_year,
                                primary_site_id=matched_int.site_id,
                                site_type=SiteType.INTERSECTION,
                                road_class=matched_int.road_class,
                                match_method=MatchMethod.INTERSECTION_JUNCTION,
                                match_status=MatchStatus.MATCHED,
                                match_confidence=confidence,
                                candidate_site_count=1,
                                snap_distance_meters=dist,
                                source_reference_id=(
                                    matched_int.source_reference_ids[0]
                                    if matched_int.source_reference_ids
                                    else None
                                ),
                                coordinate_validation_status=coord_status_str,
                            )

            # 2b. Spatial search for nearby registered intersections within catchment (30.48m)
            nearby_intersections = self.registry.find_nearby_sites(
                lat, lon, max_distance_meters=DEFAULT_INTERSECTION_RADIUS_METERS, site_type=SiteType.INTERSECTION
            )
            if nearby_intersections:
                corroborated_ints: List[Tuple[SiteRecord, float, float]] = []
                for s, dist in nearby_intersections:
                    score = self._evaluate_intersection_corroboration(s, parsed_streets, street_raw)
                    if score > 0.0:
                        corroborated_ints.append((s, dist, score))

                if corroborated_ints:
                    # Sort by score descending, then distance ascending
                    corroborated_ints.sort(key=lambda x: (-x[2], x[1]))
                    best_site, best_dist, best_score = corroborated_ints[0]

                    # Check for ambiguity among top candidates
                    if len(corroborated_ints) > 1:
                        second_site, second_dist, second_score = corroborated_ints[1]
                        if (
                            second_score == best_score
                            and abs(second_dist - best_dist) <= TIE_DISTANCE_TOLERANCE_METERS
                        ):
                            # Ambiguous intersection tie
                            cand_sites = [
                                CandidateSite(
                                    site_id=item[0].site_id,
                                    site_type=SiteType.INTERSECTION,
                                    distance_meters=item[1],
                                    corroboration_score=item[2],
                                    source_reference_id=(
                                        item[0].source_reference_ids[0]
                                        if item[0].source_reference_ids
                                        else ""
                                    ),
                                )
                                for item in corroborated_ints
                            ]
                            return CrosswalkRecord(
                                crash_id=crash_id,
                                crash_year=crash_year,
                                primary_site_id=None,
                                site_type=SiteType.UNMATCHED,
                                road_class=crash_road_class,
                                match_method=MatchMethod.AMBIGUOUS_MULTI_CANDIDATE,
                                match_status=MatchStatus.AMBIGUOUS,
                                match_confidence=MatchConfidence.NONE,
                                candidate_site_count=len(cand_sites),
                                secondary_candidates=cand_sites,
                                coordinate_validation_status=coord_status_str,
                            )

                    confidence = MatchConfidence.HIGH if best_score >= 1.0 else MatchConfidence.MEDIUM
                    return CrosswalkRecord(
                        crash_id=crash_id,
                        crash_year=crash_year,
                        primary_site_id=best_site.site_id,
                        site_type=SiteType.INTERSECTION,
                        road_class=best_site.road_class,
                        match_method=MatchMethod.INTERSECTION_JUNCTION,
                        match_status=MatchStatus.MATCHED,
                        match_confidence=confidence,
                        candidate_site_count=len(corroborated_ints),
                        snap_distance_meters=best_dist,
                        source_reference_id=(
                            best_site.source_reference_ids[0]
                            if best_site.source_reference_ids
                            else None
                        ),
                        coordinate_validation_status=coord_status_str,
                    )

        # -------------------------------------------------------------------------
        # STAGE 3: Validated Road-Segment Spatial Match (SEGMENT_SPATIAL_SNAP)
        # -------------------------------------------------------------------------
        nearby_segments = self.registry.find_nearby_sites(
            lat, lon, max_distance_meters=MAX_SNAP_DISTANCE_METERS, site_type=SiteType.SEGMENT
        )

        norm_crash_street = normalize_street_name(street_raw)
        norm_crash_route = normalize_route_number(str(raw_route or ""))

        corroborated_segs: List[Tuple[SiteRecord, float, float]] = []
        for seg_site, dist in nearby_segments:
            score = self._evaluate_segment_corroboration(
                seg_site, norm_crash_street, norm_crash_route
            )
            if score > 0.0:
                corroborated_segs.append((seg_site, dist, score))

        if corroborated_segs:
            # Sort by score descending, then distance ascending
            corroborated_segs.sort(key=lambda x: (-x[2], x[1]))
            best_seg, best_dist, best_score = corroborated_segs[0]

            # Check for ambiguity among top segment candidates
            if len(corroborated_segs) > 1:
                second_seg, second_dist, second_score = corroborated_segs[1]
                if (
                    second_score == best_score
                    and abs(second_dist - best_dist) <= TIE_DISTANCE_TOLERANCE_METERS
                ):
                    # Multi-candidate tie on parallel or dual-carriageway segments
                    cand_sites = [
                        CandidateSite(
                            site_id=item[0].site_id,
                            site_type=SiteType.SEGMENT,
                            distance_meters=item[1],
                            corroboration_score=item[2],
                            source_reference_id=(
                                item[0].source_reference_ids[0]
                                if item[0].source_reference_ids
                                else ""
                            ),
                        )
                        for item in corroborated_segs
                    ]
                    return CrosswalkRecord(
                        crash_id=crash_id,
                        crash_year=crash_year,
                        primary_site_id=None,
                        site_type=SiteType.UNMATCHED,
                        road_class=crash_road_class,
                        match_method=MatchMethod.AMBIGUOUS_MULTI_CANDIDATE,
                        match_status=MatchStatus.AMBIGUOUS,
                        match_confidence=MatchConfidence.NONE,
                        candidate_site_count=len(cand_sites),
                        secondary_candidates=cand_sites,
                        coordinate_validation_status=coord_status_str,
                    )

            confidence = (
                MatchConfidence.MEDIUM if best_dist <= 25.0 else MatchConfidence.LOW
            )
            return CrosswalkRecord(
                crash_id=crash_id,
                crash_year=crash_year,
                primary_site_id=best_seg.site_id,
                site_type=SiteType.SEGMENT,
                road_class=best_seg.road_class,
                match_method=MatchMethod.SEGMENT_SPATIAL_SNAP,
                match_status=MatchStatus.MATCHED,
                match_confidence=confidence,
                candidate_site_count=len(corroborated_segs),
                snap_distance_meters=best_dist,
                source_reference_id=(
                    best_seg.source_reference_ids[0]
                    if best_seg.source_reference_ids
                    else None
                ),
                coordinate_validation_status=coord_status_str,
            )

        # -------------------------------------------------------------------------
        # STAGE 5: Unmatched Classification (UNMATCHED_DISTANCE)
        # -------------------------------------------------------------------------
        # If segments were nearby but lacked attribute corroboration, do not arbitrarily snap!
        return CrosswalkRecord(
            crash_id=crash_id,
            crash_year=crash_year,
            primary_site_id=None,
            site_type=SiteType.UNMATCHED,
            road_class=crash_road_class,
            match_method=MatchMethod.UNMATCHED_DISTANCE,
            match_status=MatchStatus.UNMATCHED,
            match_confidence=MatchConfidence.NONE,
            candidate_site_count=len(nearby_segments),
            coordinate_validation_status=coord_status_str,
        )

    def _evaluate_intersection_corroboration(
        self, site: SiteRecord, parsed_streets: List[str], raw_street: str
    ) -> float:
        """Score corroboration between crash street info and intersection site."""
        site_streets = {normalize_street_name(s) for s in site.street_names if s}
        if not site_streets:
            return 0.0

        crash_streets = set(parsed_streets)
        if not crash_streets and raw_street:
            crash_streets = {normalize_street_name(raw_street)}

        matched = crash_streets.intersection(site_streets)
        if len(matched) >= 2:
            return 1.0
        elif len(matched) == 1:
            return 0.5

        # Check partial token match
        raw_tokens = set(normalize_street_name(raw_street).split())
        for s in site_streets:
            s_tokens = set(s.split())
            if raw_tokens.intersection(s_tokens):
                return 0.25

        return 0.0

    def _evaluate_segment_corroboration(
        self, site: SiteRecord, norm_crash_street: str, norm_crash_route: Optional[str]
    ) -> float:
        """Score corroboration between crash street/route and segment site."""
        # 1. Check route match
        if norm_crash_route and f"SR{norm_crash_route}" in site.site_id:
            return 1.0

        # 2. Check street names
        site_streets = {normalize_street_name(s) for s in site.street_names if s}
        if norm_crash_street in site_streets:
            return 1.0

        # 3. Check token overlap
        crash_tokens = set(norm_crash_street.split())
        for s in site_streets:
            s_tokens = set(s.split())
            overlap = crash_tokens.intersection(s_tokens)
            if overlap and len(overlap) >= len(crash_tokens) * 0.5:
                return 0.5

        return 0.0
