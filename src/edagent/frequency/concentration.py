"""Historical crash-concentration reporting pathway.

Governed by Project Plan v2 (§8, §14, §18) and Phase 4 Module B requirements.
Mandated alternative when traffic exposure coverage is inadequate for predictive modelling.
Computes empirical spatial crash density, severe injury (KSI) density, vulnerable road user
(VRU) concentration, multi-epoch temporal persistence auditing, and within-road-class
percentile benchmarking without fabricating synthetic exposure data.
"""

from __future__ import annotations

import csv
import gzip
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class PersistenceCategory(str, Enum):
    """Temporal persistence classification across three 7-year observation epochs."""

    PERSISTENT_HIGH_HAZARD = "PERSISTENT_HIGH_HAZARD"
    EMERGING_HIGH_HAZARD = "EMERGING_HIGH_HAZARD"
    HISTORIC_RESOLVED = "HISTORIC_RESOLVED"
    TRANSIENT_STOCHASTIC = "TRANSIENT_STOCHASTIC"


@dataclass
class SiteConcentrationRecord:
    """Historical crash concentration metrics for a physical roadway site."""

    site_id: str
    road_class: str
    site_type: str
    segment_length_km: float
    total_crashes_2004_2024: int
    fatal_crashes: int
    major_injury_crashes: int
    ksi_crashes: int  # Killed or Seriously Injured
    pedestrian_crashes: int
    bicycle_crashes: int
    vru_crashes: int  # Vulnerable Road Users
    crash_density_per_km: float
    ksi_density_per_km: float
    vru_density_per_km: float
    epoch1_crashes_2004_2010: int
    epoch2_crashes_2011_2017: int
    epoch3_crashes_2018_2024: int
    persistence_category: PersistenceCategory
    road_class_percentile: float  # 0.0 to 100.0 within road class

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["persistence_category"] = self.persistence_category.value
        return res


class HistoricalConcentrationAnalyzer:
    """Computes empirical historical crash concentration and multi-epoch persistence."""

    def __init__(
        self,
        crosswalk_path: str | Path = "data/exports/crosswalk/crosswalk_v1.0.0.csv.gz",
        raw_crash_path: str | Path = "data/raw/2c13021f-74a9-4289-a1e5-fe0472c89881.csv",
    ):
        self.crosswalk_path = Path(crosswalk_path)
        self.raw_crash_path = Path(raw_crash_path)

    def _load_raw_crash_severities(self) -> Dict[str, Dict[str, int]]:
        """Load crash injury and VRU attributes from raw dataset indexed by CRASH_CRN."""
        severities: Dict[str, Dict[str, int]] = {}
        if not self.raw_crash_path.exists():
            return severities

        with open(self.raw_crash_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                crn = str(row.get("CRASH_CRN", "")).strip()
                if not crn:
                    continue

                def _to_int(val: Any) -> int:
                    try:
                        return int(float(val))
                    except (ValueError, TypeError):
                        return 0

                fatal = _to_int(row.get("FATAL_COUNT", 0))
                maj_inj = _to_int(row.get("MAJ_INJ_COUNT", 0))
                ped = _to_int(row.get("PED_COUNT", 0))
                bike = _to_int(row.get("BICYCLE_COUNT", 0))

                # Binary flags if counts are zero
                if fatal == 0 and str(row.get("FATAL", "")).strip() == "1":
                    fatal = 1
                if maj_inj == 0 and str(row.get("FATAL_OR_MAJ_INJ", "")).strip() == "1":
                    maj_inj = 1
                if ped == 0 and str(row.get("PEDESTRIAN", "")).strip() == "1":
                    ped = 1
                if bike == 0 and str(row.get("BICYCLE", "")).strip() == "1":
                    bike = 1

                severities[crn] = {
                    "fatal": 1 if fatal > 0 else 0,
                    "maj_inj": 1 if maj_inj > 0 else 0,
                    "ped": 1 if ped > 0 else 0,
                    "bike": 1 if bike > 0 else 0,
                }
        return severities

    def compute_concentration(self) -> List[SiteConcentrationRecord]:
        """Aggregate crashes by site and compute historical concentration metrics."""
        severities = self._load_raw_crash_severities()

        site_data: Dict[str, Dict[str, Any]] = {}

        # Read matched crosswalk records
        with gzip.open(self.crosswalk_path, "rt", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                status = row.get("match_status", "")
                if status != "MATCHED":
                    continue

                site_id = row.get("primary_site_id", "")
                if not site_id:
                    continue

                year_val = row.get("crash_year", "0")
                try:
                    year = int(year_val)
                except ValueError:
                    year = 0

                crn = str(row.get("crash_id", "")).strip()
                road_class = row.get("road_class", "LOCAL_STREET")
                site_type = row.get("site_type", "SEGMENT")

                if site_id not in site_data:
                    site_data[site_id] = {
                        "road_class": road_class,
                        "site_type": site_type,
                        "total_crashes": 0,
                        "fatal": 0,
                        "maj_inj": 0,
                        "ped": 0,
                        "bike": 0,
                        "epoch1": 0,  # 2004-2010
                        "epoch2": 0,  # 2011-2017
                        "epoch3": 0,  # 2018-2024
                    }

                site_data[site_id]["total_crashes"] += 1

                # Severity attribution
                sev = severities.get(crn, {"fatal": 0, "maj_inj": 0, "ped": 0, "bike": 0})
                site_data[site_id]["fatal"] += sev["fatal"]
                site_data[site_id]["maj_inj"] += sev["maj_inj"]
                site_data[site_id]["ped"] += sev["ped"]
                site_data[site_id]["bike"] += sev["bike"]

                # Epoch attribution
                if 2004 <= year <= 2010:
                    site_data[site_id]["epoch1"] += 1
                elif 2011 <= year <= 2017:
                    site_data[site_id]["epoch2"] += 1
                elif 2018 <= year <= 2024:
                    site_data[site_id]["epoch3"] += 1

        # Classify persistence and compute densities
        raw_records: List[Dict[str, Any]] = []
        for s_id, d in site_data.items():
            tot = d["total_crashes"]
            fat = d["fatal"]
            maj = d["maj_inj"]
            ksi = fat + maj
            ped = d["ped"]
            bike = d["bike"]
            vru = ped + bike

            e1 = d["epoch1"]
            e2 = d["epoch2"]
            e3 = d["epoch3"]

            # Segment length in km (standardized 0.5km baseline if physical geometry unparsed)
            # State routes: approximately 0.8 km (0.5 mile PennDOT nominal segment)
            # Local streets: approximately 0.25 km (nominal block length)
            length_km = 0.8 if d["road_class"] in ("STATE_ROUTE", "INTERSTATE") else 0.3

            crash_density = tot / length_km
            ksi_density = ksi / length_km
            vru_density = vru / length_km

            # Multi-epoch persistence classification
            if e1 >= 1 and e2 >= 1 and e3 >= 1 and tot >= 5:
                cat = PersistenceCategory.PERSISTENT_HIGH_HAZARD
            elif e3 >= 3 and e3 > (e1 + e2):
                cat = PersistenceCategory.EMERGING_HIGH_HAZARD
            elif e1 >= 3 and e3 == 0:
                cat = PersistenceCategory.HISTORIC_RESOLVED
            else:
                cat = PersistenceCategory.TRANSIENT_STOCHASTIC

            raw_records.append(
                {
                    "site_id": s_id,
                    "road_class": d["road_class"],
                    "site_type": d["site_type"],
                    "length_km": length_km,
                    "total_crashes": tot,
                    "fatal": fat,
                    "maj_inj": maj,
                    "ksi": ksi,
                    "ped": ped,
                    "bike": bike,
                    "vru": vru,
                    "crash_density": crash_density,
                    "ksi_density": ksi_density,
                    "vru_density": vru_density,
                    "e1": e1,
                    "e2": e2,
                    "e3": e3,
                    "category": cat,
                }
            )

        # Compute within-road-class percentile ranks
        by_class: Dict[str, List[Dict[str, Any]]] = {}
        for r in raw_records:
            rc = r["road_class"]
            by_class.setdefault(rc, []).append(r)

        output_records: List[SiteConcentrationRecord] = []
        for rc, items in by_class.items():
            # Sort ascending by crash_density
            items.sort(key=lambda x: x["crash_density"])
            n_class = len(items)
            for rank_idx, item in enumerate(items):
                percentile = round(((rank_idx + 1) / n_class) * 100.0, 2)
                output_records.append(
                    SiteConcentrationRecord(
                        site_id=item["site_id"],
                        road_class=item["road_class"],
                        site_type=item["site_type"],
                        segment_length_km=item["length_km"],
                        total_crashes_2004_2024=item["total_crashes"],
                        fatal_crashes=item["fatal"],
                        major_injury_crashes=item["maj_inj"],
                        ksi_crashes=item["ksi"],
                        pedestrian_crashes=item["ped"],
                        bicycle_crashes=item["bike"],
                        vru_crashes=item["vru"],
                        crash_density_per_km=round(item["crash_density"], 2),
                        ksi_density_per_km=round(item["ksi_density"], 2),
                        vru_density_per_km=round(item["vru_density"], 2),
                        epoch1_crashes_2004_2010=item["e1"],
                        epoch2_crashes_2011_2017=item["e2"],
                        epoch3_crashes_2018_2024=item["e3"],
                        persistence_category=item["category"],
                        road_class_percentile=percentile,
                    )
                )

        # Sort final output descending by total crashes
        output_records.sort(key=lambda x: x.total_crashes_2004_2024, reverse=True)
        return output_records

    def export_csv(
        self,
        output_path: str | Path = "data/exports/frequency/historical_crash_concentration.csv",
    ) -> Path:
        """Compute concentration records and export to CSV."""
        records = self.compute_concentration()
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "site_id",
            "road_class",
            "site_type",
            "segment_length_km",
            "total_crashes_2004_2024",
            "fatal_crashes",
            "major_injury_crashes",
            "ksi_crashes",
            "pedestrian_crashes",
            "bicycle_crashes",
            "vru_crashes",
            "crash_density_per_km",
            "ksi_density_per_km",
            "vru_density_per_km",
            "epoch1_crashes_2004_2010",
            "epoch2_crashes_2011_2017",
            "epoch3_crashes_2018_2024",
            "persistence_category",
            "road_class_percentile",
        ]

        with open(out, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in records:
                writer.writerow(r.to_dict())

        return out
