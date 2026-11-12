"""Site-year panel prototype construction module.

Governed by Phase 4 Module A requirements.
Constructs a structured site-year panel linking physical roadway sites to annual crash counts,
incorporates legitimate zero-crash site-years for continuously observable corridors,
and preserves transparent missingness indicators for unverified traffic exposure.
Never fabricates exposure or manufactures unverified zero-crash years.
"""

from __future__ import annotations

import csv
import gzip
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class SiteYearPanelBuilder:
    """Builds a verified site-year panel prototype without fabricating exposure."""

    def __init__(
        self,
        crosswalk_gz_path: str,
        start_year: int = 2016,
        end_year: int = 2024,
        crosswalk_version: str = "1.0.0",
        eligible_site_years: Optional[Set[Tuple[str, int]]] = None,
        observed_site_years: Optional[Set[Tuple[str, int]]] = None,
    ) -> None:
        self.crosswalk_gz_path = Path(crosswalk_gz_path)
        self.start_year = start_year
        self.end_year = end_year
        self.crosswalk_version = crosswalk_version
        self.eligible_site_years = eligible_site_years
        self.observed_site_years = observed_site_years

    def build_panel(
        self,
        max_sites: Optional[int] = None,
        focus_state_routes_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Construct the site-year panel prototype.

        Parameters:
            max_sites: Optional cap on the number of sites to process for prototype sizing.
            focus_state_routes_only: Restrict zero-crash expansion to verified State Route
                                     corridors where continuous historical observability is legally documented.
        """
        if not self.crosswalk_gz_path.exists():
            raise FileNotFoundError(f"Crosswalk file not found: {self.crosswalk_gz_path}")

        if self.eligible_site_years is None:
            raise ValueError("An independently reviewed eligible site-year frame is required")
        if self.observed_site_years is None:
            raise ValueError("An independently reviewed crash-observation frame is required")
        if not self.observed_site_years <= self.eligible_site_years:
            raise ValueError("Observed site-years must be eligible")

        # 1. Aggregate observed crash counts by site and year
        # site_id -> {year: count}
        site_annual_counts: Dict[str, Dict[int, int]] = {}
        site_metadata: Dict[str, Tuple[str, str]] = {}  # site_id -> (road_class, site_type)

        with gzip.open(self.crosswalk_gz_path, "rt", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pid = row.get("primary_site_id")
                if not pid:
                    continue

                yr_val = row.get("crash_year")
                if not yr_val or not yr_val.isdigit():
                    continue
                yr = int(yr_val)

                if not (self.start_year <= yr <= self.end_year):
                    continue

                rc = row.get("road_class") or "UNKNOWN"
                st = row.get("site_type") or "SEGMENT"

                # If focusing on state routes for legitimate zero-crash panel expansion:
                if focus_state_routes_only and not pid.startswith("SEG:02:SR"):
                    continue

                if (pid, yr) not in self.eligible_site_years:
                    raise ValueError(f"Matched crash outside eligible site-year frame: {pid}, {yr}")

                if pid not in site_annual_counts:
                    site_annual_counts[pid] = {y: 0 for y in range(self.start_year, self.end_year + 1)}
                    site_metadata[pid] = (rc, st)

                site_annual_counts[pid][yr] += 1

        # Add eligible sites with no observed crashes anywhere in the window.
        for pid, yr in self.eligible_site_years:
            if self.start_year <= yr <= self.end_year:
                if focus_state_routes_only and not pid.startswith("SEG:02:SR"):
                    continue
                site_annual_counts.setdefault(pid, {})
                site_metadata.setdefault(pid, ("UNKNOWN", "SEGMENT"))

        # Sort sites deterministically
        sorted_sites = sorted(site_annual_counts.keys())
        if max_sites:
            sorted_sites = sorted_sites[:max_sites]

        panel_rows: List[Dict[str, Any]] = []

        for site_id in sorted_sites:
            rc, st = site_metadata[site_id]
            annual_dict = site_annual_counts[site_id]

            for yr in range(self.start_year, self.end_year + 1):
                if (site_id, yr) not in self.eligible_site_years:
                    continue
                observed = (site_id, yr) in self.observed_site_years
                cnt = annual_dict.get(yr, 0) if observed else None
                is_zero_crash = (cnt == 0) if observed else None

                panel_rows.append({
                    "site_id": site_id,
                    "year": yr,
                    "crash_count": cnt,
                    "is_zero_crash_observation": is_zero_crash,
                    "road_class": rc,
                    "site_type": st,
                    "traffic_exposure": None,  # Strictly unpopulated; zero fabrication
                    "exposure_source": "UNAVAILABLE",
                    "exposure_year": None,
                    "exposure_quality_status": "MISSING_EXPOSURE",
                    "observability_status": "OBSERVED" if observed else "INCOMPLETE_OR_UNKNOWN",
                    "crosswalk_version": self.crosswalk_version,
                })

        return panel_rows

    def export_csv(
        self,
        panel_rows: List[Dict[str, Any]],
        output_filepath: str,
    ) -> None:
        """Export the site-year panel prototype to a standardized CSV."""
        path = Path(output_filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not panel_rows:
            return

        fieldnames = [
            "site_id",
            "year",
            "crash_count",
            "is_zero_crash_observation",
            "road_class",
            "site_type",
            "traffic_exposure",
            "exposure_source",
            "exposure_year",
            "exposure_quality_status",
            "observability_status",
            "crosswalk_version",
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in panel_rows:
                # Format None as empty string for CSV compliance
                out_dict = {
                    k: ("" if v is None else v) for k, v in row.items()
                }
                writer.writerow(out_dict)
