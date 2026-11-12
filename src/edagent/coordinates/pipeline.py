"""Pipeline for batch decoding and quality validation of crash coordinates."""

from __future__ import annotations

import csv
from typing import Any, Dict, Iterable, List, Optional, Tuple

from edagent.coordinates.decoder import GPSDecoder
from edagent.coordinates.models import CoordinateRecord, ValidationFlag, ValidationStatus
from edagent.coordinates.validator import CoordinateValidator


class CoordinatePipeline:
    """Orchestrates end-to-end decoding, validation, and reporting for crash datasets."""

    def __init__(
        self,
        validator: Optional[CoordinateValidator] = None,
    ) -> None:
        self.validator = validator or CoordinateValidator()

    def process_records(
        self, rows: Iterable[Dict[str, Any]]
    ) -> List[CoordinateRecord]:
        """Process an iterable of dictionary rows into validated CoordinateRecord objects."""
        records: List[CoordinateRecord] = []

        for row in rows:
            # Handle varied key cases (uppercase from CSV or lowercase)
            crn_val = row.get("CRASH_CRN") or row.get("crash_crn") or 0
            try:
                crn = int(crn_val)
            except (ValueError, TypeError):
                crn = 0

            year_val = row.get("CRASH_YEAR") or row.get("crash_year")
            try:
                year = int(year_val) if year_val is not None else None
            except (ValueError, TypeError):
                year = None

            raw_lat = row.get("LATITUDE") or row.get("latitude") or row.get("raw_latitude")
            raw_lon = row.get("LONGITUDE") or row.get("longitude") or row.get("raw_longitude")
            raw_dec_lat = row.get("DEC_LAT") or row.get("dec_lat") or row.get("DEC_LATITUDE")
            raw_dec_long = row.get("DEC_LONG") or row.get("dec_long") or row.get("DEC_LONGITUDE")

            route = str(row.get("ROUTE") or row.get("route") or "").strip()
            is_state_route = bool(route and route not in {"", "None", "nan", "0"})

            rec = self.validator.process_crash_record(
                crash_crn=crn,
                crash_year=year,
                raw_latitude=raw_lat,
                raw_longitude=raw_lon,
                raw_dec_lat=raw_dec_lat,
                raw_dec_long=raw_dec_long,
                is_state_route=is_state_route,
            )
            records.append(rec)

        # Run concentration and duplicate analysis across the batch
        records = self.validator.audit_concentration_and_duplicates(records)
        return records

    def process_csv_file(
        self, csv_path: str, max_rows: Optional[int] = None
    ) -> List[CoordinateRecord]:
        """Read and process rows directly from a CSV file."""
        rows = []
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if max_rows is not None and i >= max_rows:
                    break
                rows.append(row)
        return self.process_records(rows)

    def generate_quality_summary(
        self, records: List[CoordinateRecord]
    ) -> Dict[str, Any]:
        """Compute aggregate quality metrics across validated records."""
        total = len(records)
        status_counts = {s.value: 0 for s in ValidationStatus}
        source_counts: Dict[str, int] = {}
        reason_counts: Dict[str, int] = {}
        distances: List[float] = []

        for rec in records:
            status_counts[rec.validation_status.value] += 1
            src = rec.coordinate_source.value
            source_counts[src] = source_counts.get(src, 0) + 1

            for flag in rec.validation_reasons:
                reason_counts[flag.value] = reason_counts.get(flag.value, 0) + 1

            if rec.pair_distance_meters is not None:
                distances.append(rec.pair_distance_meters)

        distances.sort()
        n_dist = len(distances)

        def percentile(p: float) -> Optional[float]:
            if not distances:
                return None
            idx = int(p * (n_dist - 1))
            return distances[idx]

        return {
            "total_records": total,
            "status_counts": status_counts,
            "status_percentages": {
                k: (v / total * 100.0 if total > 0 else 0.0)
                for k, v in status_counts.items()
            },
            "source_counts": source_counts,
            "reason_counts": reason_counts,
            "pairwise_comparisons": n_dist,
            "distance_stats": {
                "min_m": distances[0] if distances else None,
                "median_m": percentile(0.50),
                "p90_m": percentile(0.90),
                "p95_m": percentile(0.95),
                "p99_m": percentile(0.99),
                "max_m": distances[-1] if distances else None,
            },
        }
