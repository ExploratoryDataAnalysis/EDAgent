"""Coordinate disagreement analysis module.

Governed by Phase 3 Module D requirements.
Compares crash coordinates with official roadway geometry, identifies spatial
discrepancies, and categorizes them with full provenance and review statuses.
Never hides disagreements through automatic snapping.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from edagent.coordinates.decoder import haversine_distance_meters
from edagent.roadway.schema import CrosswalkRecord, MatchMethod, MatchStatus, RoadClass


class CoordinateDisagreementAnalyzer:
    """Audits spatial disagreements between crash coordinates and reference geometries."""

    def __init__(self, conflict_threshold_meters: float = 500.0) -> None:
        self.conflict_threshold_meters = conflict_threshold_meters

    @staticmethod
    def load_baseline_disagreements(filepath: str) -> Dict[int, Dict[str, Any]]:
        """Load the 2,146 frozen candidate coordinate disagreements from EDA v6.

        Returns:
            Dict mapping CRASH_CRN to record attributes.
        """
        path = Path(filepath)
        if not path.exists():
            return {}

        disagreements: Dict[int, Dict[str, Any]] = {}
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    crn = int(row["CRASH_CRN"])
                    disagreements[crn] = {
                        "crash_crn": crn,
                        "crash_year": int(row.get("CRASH_YEAR") or 0),
                        "candidate_police_lat": float(row["candidate_police_lat"]),
                        "candidate_police_lon": float(row["candidate_police_lon"]),
                        "state_decimal_lat": float(row["state_decimal_lat"]),
                        "state_decimal_lon": float(row["state_decimal_lon"]),
                        "difference_m": float(row["difference_m"]),
                    }
                except (ValueError, KeyError):
                    continue

        return disagreements

    def analyze_record(
        self,
        crash_data: Dict[str, Any],
        crosswalk: CrosswalkRecord,
        baseline_conflict: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Evaluate a single record for coordinate-reference discrepancy.

        Returns disagreement audit dict if a discrepancy is detected, else None.
        """
        crash_id = crosswalk.crash_id
        crash_year = crosswalk.crash_year

        # Case 1: Known baseline coordinate conflict (>500m between Police DMS & State Decimal)
        if baseline_conflict is not None:
            return {
                "crash_id": crash_id,
                "crash_year": crash_year,
                "discrepancy_type": "POLICE_STATE_COORDINATE_CONFLICT",
                "distance_meters": round(baseline_conflict["difference_m"], 2),
                "coordinate_source": "police_dms_vs_state_decimal",
                "reference_dataset_version": "2c13021f-74a9-4289-a1e5-fe0472c89881",
                "candidate_site_count": crosswalk.candidate_site_count,
                "match_method": crosswalk.match_method.value,
                "road_class": crosswalk.road_class.value,
                "primary_site_id": crosswalk.primary_site_id or "NONE",
                "review_status": "FLAGGED_CONFLICT",
                "notes": (
                    f"Police DMS coordinates disagree with State Route Decimal coordinates "
                    f"by {baseline_conflict['difference_m']:.1f}m (>500m threshold). Gated from automatic matching."
                ),
            }

        # Case 2: Crash coordinates fall outside standard matching catchment (>50m from candidate reference)
        if (
            crosswalk.match_method == MatchMethod.UNMATCHED_DISTANCE
            and crosswalk.snap_distance_meters is not None
            and crosswalk.snap_distance_meters > 50.0
        ):
            return {
                "crash_id": crash_id,
                "crash_year": crash_year,
                "discrepancy_type": "EXCEEDS_MAX_ROAD_SNAP_DISTANCE",
                "distance_meters": round(crosswalk.snap_distance_meters, 2),
                "coordinate_source": "decoded_crash_gps",
                "reference_dataset_version": "alleghenycounty_streetcenterlines202610",
                "candidate_site_count": crosswalk.candidate_site_count,
                "match_method": crosswalk.match_method.value,
                "road_class": crosswalk.road_class.value,
                "primary_site_id": "NONE",
                "review_status": "NEEDS_MANUAL_LOCATION_REVIEW",
                "notes": (
                    f"Distance to nearest roadway centerline ({crosswalk.snap_distance_meters:.1f}m) "
                    f"exceeds the 50m tolerance threshold. Preserved as UNMATCHED without automatic snapping."
                ),
            }

        return None
