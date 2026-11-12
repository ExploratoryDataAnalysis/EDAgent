"""Ambiguous record review module.

Governed by Phase 3 Module D requirements.
Extracts and structures all ambiguous crash records (coordinate conflicts and multi-candidate ties)
into a reviewable ledger with original coordinates, competing candidates, and audit recommendations.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from edagent.roadway.schema import CrosswalkRecord, MatchMethod, MatchStatus


class AmbiguousRecordReviewer:
    """Compiles and exports ambiguous match records for manual quality control."""

    @staticmethod
    def extract_review_record(
        crash_data: Dict[str, Any],
        crosswalk: CrosswalkRecord,
    ) -> Optional[Dict[str, Any]]:
        """Structure an ambiguous crosswalk match into a manual review row.

        Returns None if record is not AMBIGUOUS.
        """
        if crosswalk.match_status != MatchStatus.AMBIGUOUS:
            return None

        crash_id = crosswalk.crash_id
        orig_lat = crash_data.get("LATITUDE") or ""
        orig_lon = crash_data.get("LONGITUDE") or ""
        orig_dec_lat = crash_data.get("DEC_LAT") or ""
        orig_dec_long = crash_data.get("DEC_LONG") or ""
        st_name = crash_data.get("STREET_NAME") or ""

        # Extract secondary candidates details
        cand_site_ids = [c.site_id for c in crosswalk.secondary_candidates]
        cand_distances = [f"{c.distance_meters:.1f}m" for c in crosswalk.secondary_candidates]
        cand_notes = [c.notes or "" for c in crosswalk.secondary_candidates if c.notes]

        reason_str = ""
        rec_status = "PENDING_INVESTIGATION"

        if crosswalk.match_method == MatchMethod.AMBIGUOUS_CONFLICT:
            reason_str = "COORDINATE_CONFLICT_OVER_500M"
            rec_status = "FLAGGED_DISCREPANCY"
            evidence = (
                f"Police DMS coords ('{orig_lat}', '{orig_lon}') conflict with State Route "
                f"Decimal coords ('{orig_dec_lat}', '{orig_dec_long}') by >500m."
            )
        elif crosswalk.match_method == MatchMethod.AMBIGUOUS_MULTI_CANDIDATE:
            reason_str = "EQUIDISTANT_MULTI_CANDIDATE_TIE"
            rec_status = "NEEDS_MANUAL_ADJUDICATION"
            evidence = (
                f"{len(cand_site_ids)} equidistant roadway candidates within 2m distance tolerance. "
                f"Street name: '{st_name}'. Candidates: {'; '.join(cand_site_ids)}"
            )
        else:
            reason_str = crosswalk.match_method.value
            evidence = f"Ambiguity during {crosswalk.match_method.value} stage."

        return {
            "crash_id": crash_id,
            "crash_year": crosswalk.crash_year,
            "original_latitude": orig_lat,
            "original_longitude": orig_lon,
            "original_dec_lat": orig_dec_lat,
            "original_dec_long": orig_dec_long,
            "street_name": st_name,
            "road_class": crosswalk.road_class.value,
            "candidate_site_count": crosswalk.candidate_site_count,
            "candidate_sites": "; ".join(cand_site_ids) if cand_site_ids else "NONE",
            "candidate_distances": "; ".join(cand_distances) if cand_distances else "N/A",
            "matching_evidence": evidence,
            "reason_for_ambiguity": reason_str,
            "recommended_review_status": rec_status,
        }

    @staticmethod
    def export_csv(records: List[Dict[str, Any]], filepath: str) -> None:
        """Export review rows to a CSV file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not records:
            return

        fieldnames = list(records[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in records:
                writer.writerow(r)
