"""Crosswalk reconciliation and stratified quality reporting engine.

Governed by Project Plan v2 (§12–15) and Phase 3 Module D requirements.
Executes end-to-end batch crosswalk reconciliation across all 248,810 crashes,
enforces the strict One-Primary-Site Rule, generates stratified quality reports,
and establishes full cryptographic reproducibility.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from edagent.coordinates.decoder import GPSDecoder
from edagent.coordinates.models import CoordinateRecord, ValidationFlag, ValidationStatus
from edagent.coordinates.validator import CoordinateValidator
from edagent.crosswalk.ambiguous_reviewer import AmbiguousRecordReviewer
from edagent.crosswalk.centerline_loader import CenterlineLoader
from edagent.crosswalk.disagreement_analyzer import CoordinateDisagreementAnalyzer
from edagent.roadway.matching import CrashSiteMatcher
from edagent.roadway.normalization import normalize_route_number
from edagent.roadway.registry import SiteRegistry
from edagent.roadway.schema import CrosswalkRecord, MatchConfidence, MatchMethod, MatchStatus, RoadClass, SiteType


def compute_sha256(filepath: str) -> str:
    """Calculate SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


class CrosswalkReconciler:
    """Orchestrates the Phase 3 Module D crosswalk reconciliation and quality review."""

    def __init__(
        self,
        crash_csv_path: str,
        centerline_zip_path: str,
        disagreements_csv_path: str,
        output_dir: str = "data/exports/crosswalk",
        crosswalk_version: str = "1.0.0",
    ) -> None:
        self.crash_csv_path = Path(crash_csv_path)
        self.centerline_zip_path = Path(centerline_zip_path)
        self.disagreements_csv_path = Path(disagreements_csv_path)
        self.output_dir = Path(output_dir)
        self.crosswalk_version = crosswalk_version

        self.registry = SiteRegistry()
        self.validator = CoordinateValidator()
        self.matcher: Optional[CrashSiteMatcher] = None
        self.disagreement_analyzer = CoordinateDisagreementAnalyzer()
        self.baseline_disagreements: Dict[int, Dict[str, Any]] = {}

    def setup(self) -> None:
        """Initialize reference registry and load baseline conflict records."""
        # 1. Load baseline coordinate disagreements (>500m)
        if self.disagreements_csv_path.exists():
            self.baseline_disagreements = CoordinateDisagreementAnalyzer.load_baseline_disagreements(
                str(self.disagreements_csv_path)
            )

        # 2. Populate PennDOT LRS state routes from crash records
        CenterlineLoader.populate_state_route_segments_from_crashes(
            str(self.crash_csv_path), self.registry
        )

        # 3. Load Allegheny County Centerlines
        if self.centerline_zip_path.exists():
            CenterlineLoader.load_centerlines_from_zip(
                str(self.centerline_zip_path), self.registry
            )

        self.matcher = CrashSiteMatcher(self.registry)

    def run(self) -> Dict[str, Any]:
        """Execute crosswalk matching across all crash records and produce deliverables."""
        if not self.matcher:
            self.setup()

        self.output_dir.mkdir(parents=True, exist_ok=True)
        t_start = time.time()

        # Output filepaths
        gz_crosswalk_path = self.output_dir / f"crosswalk_v{self.crosswalk_version}.csv.gz"
        sample_crosswalk_path = self.output_dir / f"crosswalk_v{self.crosswalk_version}_sample.csv"
        ambiguous_path = self.output_dir / "ambiguous_records_review.csv"
        disagreement_path = self.output_dir / "coordinate_disagreements_review.csv"
        strat_year_path = self.output_dir / "stratified_summary_by_year.csv"
        strat_road_path = self.output_dir / "stratified_summary_by_road_class.csv"
        strat_site_path = self.output_dir / "stratified_summary_by_site_type.csv"
        strat_method_path = self.output_dir / "stratified_summary_by_method.csv"
        strat_coord_path = self.output_dir / "stratified_summary_by_coord_status.csv"
        manifest_path = self.output_dir / "reproducibility_manifest.json"

        # Crosswalk schema headers
        cw_headers = [
            "crash_id",
            "crash_year",
            "primary_site_id",
            "site_type",
            "road_class",
            "match_method",
            "match_status",
            "match_confidence",
            "candidate_site_count",
            "snap_distance_meters",
            "source_reference_id",
            "coordinate_validation_status",
            "crosswalk_version",
        ]

        total_crashes = 0
        status_counts = {"MATCHED": 0, "AMBIGUOUS": 0, "UNMATCHED": 0}

        # Stratified count trackers
        by_year: Dict[int, Dict[str, int]] = {y: {"MATCHED": 0, "AMBIGUOUS": 0, "UNMATCHED": 0, "TOTAL": 0} for y in range(2004, 2025)}
        by_road_class: Dict[str, Dict[str, int]] = {}
        by_site_type: Dict[str, Dict[str, int]] = {}
        by_method: Dict[str, int] = {}
        by_coord_status: Dict[str, int] = {}

        ambiguous_rows: List[Dict[str, Any]] = []
        disagreement_rows: List[Dict[str, Any]] = []

        # Open compressed CSV writer
        with gzip.open(gz_crosswalk_path, "wt", encoding="utf-8", newline="") as gz_out, \
             open(sample_crosswalk_path, "w", encoding="utf-8", newline="") as sample_out:

            gz_writer = csv.DictWriter(gz_out, fieldnames=cw_headers)
            gz_writer.writeheader()

            sample_writer = csv.DictWriter(sample_out, fieldnames=cw_headers)
            sample_writer.writeheader()

            with open(self.crash_csv_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    total_crashes += 1

                    if total_crashes % 50000 == 0 or total_crashes == 248810:
                        elapsed = time.time() - t_start
                        rate = total_crashes / elapsed if elapsed > 0 else 0
                        print(f"Processed {total_crashes:,} / 248,810 records ({rate:.0f} rec/s)...", flush=True)

                    try:
                        crn = int(row.get("CRASH_CRN") or 0)
                    except (ValueError, TypeError):
                        crn = 0

                    try:
                        year = int(row.get("CRASH_YEAR") or 0)
                    except (ValueError, TypeError):
                        year = 0

                    # 1. Coordinate Validation & Conflict Gating
                    coord_rec: Optional[CoordinateRecord] = None
                    baseline_conflict = self.baseline_disagreements.get(crn)

                    if baseline_conflict is not None:
                        # Gated as conflict
                        coord_rec = CoordinateRecord(
                            crash_crn=crn,
                            crash_year=year,
                            validation_status=ValidationStatus.CONFLICT,
                            validation_reasons=[ValidationFlag.COORDINATE_PAIR_CONFLICT],
                            decoded_latitude=baseline_conflict["candidate_police_lat"],
                            decoded_longitude=baseline_conflict["candidate_police_lon"],
                            police_latitude=baseline_conflict["candidate_police_lat"],
                            police_longitude=baseline_conflict["candidate_police_lon"],
                            state_latitude=baseline_conflict["state_decimal_lat"],
                            state_longitude=baseline_conflict["state_decimal_lon"],
                            pair_distance_meters=baseline_conflict["difference_m"],
                        )
                    else:
                        r_route = str(row.get("ROUTE") or "").strip()
                        is_sr = bool(r_route and r_route not in {"", "0", "None", "nan"})
                        coord_rec = self.validator.process_crash_record(
                            crash_crn=crn,
                            crash_year=year,
                            raw_latitude=row.get("LATITUDE"),
                            raw_longitude=row.get("LONGITUDE"),
                            raw_dec_lat=row.get("DEC_LAT"),
                            raw_dec_long=row.get("DEC_LONG"),
                            is_state_route=is_sr,
                        )

                    # 2. Execute Staged Match
                    cw: CrosswalkRecord = self.matcher.match(row, coord_rec=coord_rec)

                    # 3. Enforce Invariant: One Primary Site Rule
                    if cw.match_status == MatchStatus.MATCHED:
                        assert cw.primary_site_id is not None
                    else:
                        assert cw.primary_site_id is None

                    # 4. Serialize to Crosswalk Output
                    row_dict = {
                        "crash_id": cw.crash_id,
                        "crash_year": cw.crash_year,
                        "primary_site_id": cw.primary_site_id or "",
                        "site_type": cw.site_type.value,
                        "road_class": cw.road_class.value,
                        "match_method": cw.match_method.value,
                        "match_status": cw.match_status.value,
                        "match_confidence": cw.match_confidence.value,
                        "candidate_site_count": cw.candidate_site_count,
                        "snap_distance_meters": cw.snap_distance_meters if cw.snap_distance_meters is not None else "",
                        "source_reference_id": cw.source_reference_id or "",
                        "coordinate_validation_status": cw.coordinate_validation_status,
                        "crosswalk_version": cw.crosswalk_version,
                    }
                    gz_writer.writerow(row_dict)

                    # Sample write (first 1000 rows)
                    if total_crashes <= 1000:
                        sample_writer.writerow(row_dict)

                    # 5. Track Metrics
                    m_status = cw.match_status.value
                    status_counts[m_status] = status_counts.get(m_status, 0) + 1

                    # Stratified by year (2004-2024)
                    if 2004 <= year <= 2024:
                        by_year[year][m_status] += 1
                        by_year[year]["TOTAL"] += 1

                    # Stratified by road class
                    rc = cw.road_class.value
                    if rc not in by_road_class:
                        by_road_class[rc] = {"MATCHED": 0, "AMBIGUOUS": 0, "UNMATCHED": 0, "TOTAL": 0}
                    by_road_class[rc][m_status] += 1
                    by_road_class[rc]["TOTAL"] += 1

                    # Stratified by site type
                    st = cw.site_type.value
                    if st not in by_site_type:
                        by_site_type[st] = {"MATCHED": 0, "AMBIGUOUS": 0, "UNMATCHED": 0, "TOTAL": 0}
                    by_site_type[st][m_status] += 1
                    by_site_type[st]["TOTAL"] += 1

                    # Stratified by method
                    mm = cw.match_method.value
                    by_method[mm] = by_method.get(mm, 0) + 1

                    # Stratified by coordinate status
                    cs = cw.coordinate_validation_status
                    by_coord_status[cs] = by_coord_status.get(cs, 0) + 1

                    # 6. Ambiguous and Disagreement Logging
                    if cw.match_status == MatchStatus.AMBIGUOUS:
                        ambig_item = AmbiguousRecordReviewer.extract_review_record(row, cw)
                        if ambig_item:
                            ambiguous_rows.append(ambig_item)

                    disagree_item = self.disagreement_analyzer.analyze_record(row, cw, baseline_conflict)
                    if disagree_item:
                        disagreement_rows.append(disagree_item)

        t_elapsed = time.time() - t_start

        # Export Ambiguous Review Table
        AmbiguousRecordReviewer.export_csv(ambiguous_rows, str(ambiguous_path))

        # Export Disagreement Review Table
        if disagreement_rows:
            with open(disagreement_path, "w", newline="", encoding="utf-8") as f:
                d_writer = csv.DictWriter(f, fieldnames=list(disagreement_rows[0].keys()))
                d_writer.writeheader()
                for dr in disagreement_rows:
                    d_writer.writerow(dr)

        # Export Stratified Summaries (Counts and % with explicit denominator)
        self._export_stratified_by_year(by_year, total_crashes, str(strat_year_path))
        self._export_stratified_by_category("road_class", by_road_class, total_crashes, str(strat_road_path))
        self._export_stratified_by_category("site_type", by_site_type, total_crashes, str(strat_site_path))
        self._export_frequency_summary("match_method", by_method, total_crashes, str(strat_method_path))
        self._export_frequency_summary("coordinate_status", by_coord_status, total_crashes, str(strat_coord_path))

        # Compute Output Hashes for Reproducibility Manifest
        output_hashes = {
            "crosswalk_csv_gz": compute_sha256(str(gz_crosswalk_path)),
            "crosswalk_sample_csv": compute_sha256(str(sample_crosswalk_path)),
            "ambiguous_records_review_csv": compute_sha256(str(ambiguous_path)),
            "coordinate_disagreements_review_csv": compute_sha256(str(disagreement_path)),
            "stratified_summary_by_year_csv": compute_sha256(str(strat_year_path)),
            "stratified_summary_by_road_class_csv": compute_sha256(str(strat_road_path)),
            "stratified_summary_by_site_type_csv": compute_sha256(str(strat_site_path)),
            "stratified_summary_by_method_csv": compute_sha256(str(strat_method_path)),
            "stratified_summary_by_coord_status_csv": compute_sha256(str(strat_coord_path)),
        }

        # Build Manifest
        manifest = {
            "crosswalk_version": self.crosswalk_version,
            "pipeline_name": "EDAgent Road-Safety Crosswalk Reconciliation",
            "generation_utc": datetime.now(timezone.utc).isoformat(),
            "software": {
                "python_version": sys.version.split()[0],
                "platform": sys.platform,
                "edagent_version": "1.0.0",
            },
            "parameters": {
                "max_snap_distance_meters": 50.0,
                "default_intersection_radius_meters": 30.48,
                "tie_distance_tolerance_meters": 2.0,
                "conflict_distance_threshold_meters": 500.0,
                "one_primary_site_rule_enforced": True,
            },
            "inputs": {
                "crash_dataset": {
                    "path": str(self.crash_csv_path),
                    "sha256": compute_sha256(str(self.crash_csv_path)),
                    "total_records": total_crashes,
                },
                "street_centerlines": {
                    "path": str(self.centerline_zip_path),
                    "sha256": compute_sha256(str(self.centerline_zip_path)),
                },
                "candidate_coordinate_disagreements": {
                    "path": str(self.disagreements_csv_path),
                    "sha256": compute_sha256(str(self.disagreements_csv_path)),
                    "gated_conflicts_n": len(self.baseline_disagreements),
                },
            },
            "review_decisions": {
                "candidate_coordinate_conflicts_over_500m": "GATED_AS_AMBIGUOUS_NO_PRIMARY_SITE",
                "equidistant_multi_candidate_ties": "GATED_AS_AMBIGUOUS_SECONDARY_PRESERVED",
                "exceeds_max_distance_50m": "UNMATCHED_REJECTED",
                "missing_coordinates_no_lrs": "UNMATCHED_MISSING",
            },
            "summary_metrics": {
                "total_crashes": total_crashes,
                "status_counts": status_counts,
                "status_percents_cohort_denominator": {
                    k: round((v / total_crashes) * 100.0, 4) for k, v in status_counts.items()
                },
                "total_ambiguous_reviews": len(ambiguous_rows),
                "total_disagreement_audits": len(disagreement_rows),
                "processing_time_seconds": round(t_elapsed, 2),
                "processing_rate_rec_per_sec": round(total_crashes / t_elapsed, 1),
            },
            "outputs": output_hashes,
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest

    def _export_stratified_by_year(
        self,
        by_year: Dict[int, Dict[str, int]],
        total_cohort: int,
        filepath: str,
    ) -> None:
        """Export annual stratified counts and percentages with documented denominators."""
        fieldnames = [
            "crash_year",
            "matched_count",
            "matched_pct_annual",
            "matched_pct_cohort",
            "ambiguous_count",
            "ambiguous_pct_annual",
            "ambiguous_pct_cohort",
            "unmatched_count",
            "unmatched_pct_annual",
            "unmatched_pct_cohort",
            "annual_total",
            "annual_pct_of_cohort",
            "annual_denominator",
            "cohort_denominator",
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for year in sorted(by_year.keys()):
                d = by_year[year]
                ann_tot = d["TOTAL"]
                ann_denom = ann_tot if ann_tot > 0 else 1
                writer.writerow({
                    "crash_year": year,
                    "matched_count": d["MATCHED"],
                    "matched_pct_annual": f"{(d['MATCHED'] / ann_denom) * 100.0:.2f}%",
                    "matched_pct_cohort": f"{(d['MATCHED'] / total_cohort) * 100.0:.4f}%",
                    "ambiguous_count": d["AMBIGUOUS"],
                    "ambiguous_pct_annual": f"{(d['AMBIGUOUS'] / ann_denom) * 100.0:.2f}%",
                    "ambiguous_pct_cohort": f"{(d['AMBIGUOUS'] / total_cohort) * 100.0:.4f}%",
                    "unmatched_count": d["UNMATCHED"],
                    "unmatched_pct_annual": f"{(d['UNMATCHED'] / ann_denom) * 100.0:.2f}%",
                    "unmatched_pct_cohort": f"{(d['UNMATCHED'] / total_cohort) * 100.0:.4f}%",
                    "annual_total": ann_tot,
                    "annual_pct_of_cohort": f"{(ann_tot / total_cohort) * 100.0:.2f}%",
                    "annual_denominator": ann_tot,
                    "cohort_denominator": total_cohort,
                })

    def _export_stratified_by_category(
        self,
        cat_name: str,
        cat_dict: Dict[str, Dict[str, int]],
        total_cohort: int,
        filepath: str,
    ) -> None:
        """Export categorical stratified counts and percentages with documented denominators."""
        fieldnames = [
            cat_name,
            "matched_count",
            "matched_pct_category",
            "matched_pct_cohort",
            "ambiguous_count",
            "ambiguous_pct_category",
            "ambiguous_pct_cohort",
            "unmatched_count",
            "unmatched_pct_category",
            "unmatched_pct_cohort",
            "category_total",
            "category_pct_of_cohort",
            "category_denominator",
            "cohort_denominator",
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for cat in sorted(cat_dict.keys()):
                d = cat_dict[cat]
                cat_tot = d["TOTAL"]
                cat_denom = cat_tot if cat_tot > 0 else 1
                writer.writerow({
                    cat_name: cat,
                    "matched_count": d["MATCHED"],
                    "matched_pct_category": f"{(d['MATCHED'] / cat_denom) * 100.0:.2f}%",
                    "matched_pct_cohort": f"{(d['MATCHED'] / total_cohort) * 100.0:.4f}%",
                    "ambiguous_count": d["AMBIGUOUS"],
                    "ambiguous_pct_category": f"{(d['AMBIGUOUS'] / cat_denom) * 100.0:.2f}%",
                    "ambiguous_pct_cohort": f"{(d['AMBIGUOUS'] / total_cohort) * 100.0:.4f}%",
                    "unmatched_count": d["UNMATCHED"],
                    "unmatched_pct_category": f"{(d['UNMATCHED'] / cat_denom) * 100.0:.2f}%",
                    "unmatched_pct_cohort": f"{(d['UNMATCHED'] / total_cohort) * 100.0:.4f}%",
                    "category_total": cat_tot,
                    "category_pct_of_cohort": f"{(cat_tot / total_cohort) * 100.0:.2f}%",
                    "category_denominator": cat_tot,
                    "cohort_denominator": total_cohort,
                })

    def _export_frequency_summary(
        self,
        name: str,
        freq_dict: Dict[str, int],
        total_cohort: int,
        filepath: str,
    ) -> None:
        """Export single-dimension frequency summaries with documented cohort denominator."""
        fieldnames = [name, "count", "percentage", "cohort_denominator"]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for k in sorted(freq_dict.keys(), key=lambda x: -freq_dict[x]):
                writer.writerow({
                    name: k,
                    "count": freq_dict[k],
                    "percentage": f"{(freq_dict[k] / total_cohort) * 100.0:.4f}%",
                    "cohort_denominator": total_cohort,
                })
