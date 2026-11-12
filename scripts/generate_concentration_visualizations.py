"""Generates historical concentration reports, stratified tables, and geographic visualizations.

Governed by Project Plan v2 (§8, §14, §18) and Phase 4 Module C requirements.
Calculates historical crash concentration by:
- Intersection vs Road Segment (site type)
- Road class
- Year (2004–2024)
- Multi-epoch periods
Generates GeoJSON and CSV visualizations using validated site coordinates.
Exports retrospective severity association audits.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path("src").resolve()))

from edagent.severity.retrospective import RetrospectiveSeverityAnalyzer


def main() -> None:
    raise RuntimeError(
        "Visualization release blocked until crosswalk and concentration inputs "
        "have been rebuilt and reviewed."
    )
    print("=" * 80)
    print("PHASE 4 — MODULE C: HISTORICAL CONCENTRATION & RETROSPECTIVE SEVERITY")
    print("=" * 80)

    crosswalk_path = Path("data/exports/crosswalk/crosswalk_v1.0.0.csv.gz")
    raw_crash_path = Path("data/raw/2c13021f-74a9-4289-a1e5-fe0472c89881.csv")

    if not crosswalk_path.exists() or not raw_crash_path.exists():
        print("ERROR: Required input files not found.")
        sys.exit(1)

    t0 = time.time()

    # -------------------------------------------------------------------------
    # 1. Load raw crash attributes (injuries, VRU, coordinates, intersection flag)
    # -------------------------------------------------------------------------
    print("\n[Step 1] Loading raw crash attributes...")
    crash_meta = {}
    with open(raw_crash_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            crn = str(r.get("CRASH_CRN", "")).strip()
            if not crn:
                continue

            def _to_int(val: str | None) -> int:
                try:
                    return int(float(val)) if val else 0
                except (ValueError, TypeError):
                    return 0

            fatal = _to_int(r.get("FATAL_COUNT"))
            maj_inj = _to_int(r.get("MAJ_INJ_COUNT"))
            ped = _to_int(r.get("PED_COUNT"))
            bike = _to_int(r.get("BICYCLE_COUNT"))

            if fatal == 0 and str(r.get("FATAL", "")).strip() == "1":
                fatal = 1
            if maj_inj == 0 and str(r.get("FATAL_OR_MAJ_INJ", "")).strip() == "1":
                maj_inj = 1
            if ped == 0 and str(r.get("PEDESTRIAN", "")).strip() == "1":
                ped = 1
            if bike == 0 and str(r.get("BICYCLE", "")).strip() == "1":
                bike = 1

            is_intersect = str(r.get("INTERSECTION", "")).strip() == "1"

            lat_val = None
            lon_val = None
            lat_str = r.get("DEC_LAT")
            lon_str = r.get("DEC_LONG")
            if lat_str and lon_str:
                try:
                    lat_f = float(lat_str)
                    lon_f = float(lon_str)
                    if 40.1 <= lat_f <= 40.8 and -80.4 <= lon_f <= -79.6:
                        lat_val = lat_f
                        lon_val = lon_f
                except ValueError:
                    pass

            crash_meta[crn] = {
                "fatal": 1 if fatal > 0 else 0,
                "maj_inj": 1 if maj_inj > 0 else 0,
                "ped": 1 if ped > 0 else 0,
                "bike": 1 if bike > 0 else 0,
                "is_intersection": is_intersect,
                "lat": lat_val,
                "lon": lon_val,
            }

    print(f"  -> Loaded metadata for {len(crash_meta):,} raw crashes in {time.time() - t0:.2f}s")

    # -------------------------------------------------------------------------
    # 2. Process crosswalk and compute multidimensional aggregations
    # -------------------------------------------------------------------------
    print("\n[Step 2] Processing crosswalk records and computing stratifications...")

    # By Year
    by_year = defaultdict(lambda: {
        "total": 0, "matched": 0, "ambiguous": 0, "unmatched": 0,
        "missing_coord": 0, "fatal": 0, "maj_inj": 0, "ped": 0, "bike": 0,
    })

    # By Road Class
    by_class = defaultdict(lambda: {
        "total": 0, "matched": 0, "ambiguous": 0, "unmatched": 0,
        "missing_coord": 0, "sites": set(),
    })

    # By Site Type (Intersection vs Road Segment)
    by_site_type = defaultdict(lambda: {
        "total": 0, "matched": 0, "ambiguous": 0, "unmatched": 0,
        "missing_coord": 0, "sites": set(),
    })

    # Site coordinate accumulator for centroids
    site_coords = defaultdict(lambda: {"lats": [], "lons": []})

    with gzip.open(crosswalk_path, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            yr = int(r.get("crash_year", 0))
            crn = str(r.get("crash_id", "")).strip()
            status = r.get("match_status", "UNMATCHED")
            road_class = r.get("road_class") or "UNCLASSIFIED"
            coord_status = r.get("coordinate_validation_status", "")
            is_missing_coord = (coord_status == "MISSING")
            primary_site = r.get("primary_site_id")

            c_info = crash_meta.get(crn, {})
            is_inter = c_info.get("is_intersection", False)
            site_type_label = "INTERSECTION" if is_inter else "ROAD_SEGMENT"

            # Year accumulation
            by_year[yr]["total"] += 1
            if status == "MATCHED":
                by_year[yr]["matched"] += 1
            elif status == "AMBIGUOUS":
                by_year[yr]["ambiguous"] += 1
            else:
                by_year[yr]["unmatched"] += 1

            if is_missing_coord:
                by_year[yr]["missing_coord"] += 1

            by_year[yr]["fatal"] += c_info.get("fatal", 0)
            by_year[yr]["maj_inj"] += c_info.get("maj_inj", 0)
            by_year[yr]["ped"] += c_info.get("ped", 0)
            by_year[yr]["bike"] += c_info.get("bike", 0)

            # Road Class accumulation
            by_class[road_class]["total"] += 1
            if status == "MATCHED":
                by_class[road_class]["matched"] += 1
                if primary_site:
                    by_class[road_class]["sites"].add(primary_site)
            elif status == "AMBIGUOUS":
                by_class[road_class]["ambiguous"] += 1
            else:
                by_class[road_class]["unmatched"] += 1

            if is_missing_coord:
                by_class[road_class]["missing_coord"] += 1

            # Site Type accumulation
            by_site_type[site_type_label]["total"] += 1
            if status == "MATCHED":
                by_site_type[site_type_label]["matched"] += 1
                if primary_site:
                    by_site_type[site_type_label]["sites"].add(primary_site)
            elif status == "AMBIGUOUS":
                by_site_type[site_type_label]["ambiguous"] += 1
            else:
                by_site_type[site_type_label]["unmatched"] += 1

            if is_missing_coord:
                by_site_type[site_type_label]["missing_coord"] += 1

            # Centroid coordinate collection
            if status == "MATCHED" and primary_site:
                lat = c_info.get("lat")
                lon = c_info.get("lon")
                if lat is not None and lon is not None:
                    site_coords[primary_site]["lats"].append(lat)
                    site_coords[primary_site]["lons"].append(lon)

    # -------------------------------------------------------------------------
    # 3. Export Concentration Stratification CSVs
    # -------------------------------------------------------------------------
    print("\n[Step 3] Exporting stratified historical concentration tables...")

    # 3a. By Year
    year_csv = Path("data/exports/frequency/historical_concentration_by_year.csv")
    with open(year_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "crash_year", "total_crashes", "matched_crashes", "ambiguous_crashes",
            "unmatched_crashes", "match_coverage_percent", "missing_coord_crashes",
            "missing_coord_percent", "fatal_crashes", "major_injury_crashes",
            "ksi_crashes", "vru_crashes", "analysis_period", "is_predictive",
        ])
        for yr in sorted(by_year.keys()):
            d = by_year[yr]
            tot = d["total"]
            match_pct = round((d["matched"] / tot) * 100.0, 2) if tot > 0 else 0.0
            miss_pct = round((d["missing_coord"] / tot) * 100.0, 2) if tot > 0 else 0.0
            ksi = d["fatal"] + d["maj_inj"]
            vru = d["ped"] + d["bike"]
            writer.writerow([
                yr, tot, d["matched"], d["ambiguous"], d["unmatched"],
                f"{match_pct}%", d["missing_coord"], f"{miss_pct}%",
                d["fatal"], d["maj_inj"], ksi, vru, "2004-2024", False,
            ])
    print(f"  -> Generated {year_csv}")

    # 3b. By Road Class
    class_csv = Path("data/exports/frequency/historical_concentration_by_road_class.csv")
    with open(class_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "road_class", "total_crashes", "matched_crashes", "ambiguous_crashes",
            "unmatched_crashes", "unique_matched_sites", "match_coverage_percent",
            "missing_coord_percent", "analysis_period", "is_predictive",
        ])
        for rc in sorted(by_class.keys()):
            d = by_class[rc]
            tot = d["total"]
            match_pct = round((d["matched"] / tot) * 100.0, 2) if tot > 0 else 0.0
            miss_pct = round((d["missing_coord"] / tot) * 100.0, 2) if tot > 0 else 0.0
            writer.writerow([
                rc, tot, d["matched"], d["ambiguous"], d["unmatched"],
                len(d["sites"]), f"{match_pct}%", f"{miss_pct}%", "2004-2024", False,
            ])
    print(f"  -> Generated {class_csv}")

    # 3c. By Site Type
    type_csv = Path("data/exports/frequency/historical_concentration_by_site_type.csv")
    with open(type_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "site_type", "total_crashes", "matched_crashes", "ambiguous_crashes",
            "unmatched_crashes", "unique_matched_sites", "match_coverage_percent",
            "missing_coord_percent", "analysis_period", "is_predictive",
        ])
        for st in sorted(by_site_type.keys()):
            d = by_site_type[st]
            tot = d["total"]
            match_pct = round((d["matched"] / tot) * 100.0, 2) if tot > 0 else 0.0
            miss_pct = round((d["missing_coord"] / tot) * 100.0, 2) if tot > 0 else 0.0
            writer.writerow([
                st, tot, d["matched"], d["ambiguous"], d["unmatched"],
                len(d["sites"]), f"{match_pct}%", f"{miss_pct}%", "2004-2024", False,
            ])
    print(f"  -> Generated {type_csv}")

    # -------------------------------------------------------------------------
    # 4. Generate Top Concentration Sites with Coordinates (CSV & GeoJSON)
    # -------------------------------------------------------------------------
    print("\n[Step 4] Generating Geographic Top Concentration Datasets (CSV & GeoJSON)...")
    conc_csv_in = Path("data/exports/frequency/historical_crash_concentration.csv")
    if not conc_csv_in.exists():
        print("ERROR: historical_crash_concentration.csv not found.")
        sys.exit(1)

    top_sites = []
    with open(conc_csv_in, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for rank_idx, row in enumerate(reader):
            if rank_idx >= 100:  # Top 100 high-concentration sites
                break
            s_id = row["site_id"]
            lats = site_coords.get(s_id, {}).get("lats", [])
            lons = site_coords.get(s_id, {}).get("lons", [])

            # Compute centroid coordinate
            if lats and lons:
                centroid_lat = round(sum(lats) / len(lats), 6)
                centroid_lon = round(sum(lons) / len(lons), 6)
            else:
                # Default Allegheny County center fallback
                centroid_lat = 40.4406
                centroid_lon = -79.9959

            row["rank"] = rank_idx + 1
            row["latitude"] = centroid_lat
            row["longitude"] = centroid_lon
            row["analysis_period"] = "2004-2024"
            row["is_predictive"] = False
            top_sites.append(row)

    # 4a. Top sites CSV
    geo_csv = Path("data/exports/frequency/top_concentration_sites_geographic.csv")
    with open(geo_csv, "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "rank", "site_id", "latitude", "longitude", "road_class", "site_type",
            "segment_length_km", "total_crashes_2004_2024", "fatal_crashes",
            "major_injury_crashes", "ksi_crashes", "pedestrian_crashes",
            "bicycle_crashes", "vru_crashes", "crash_density_per_km",
            "ksi_density_per_km", "vru_density_per_km", "persistence_category",
            "road_class_percentile", "analysis_period", "is_predictive",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for s in top_sites:
            writer.writerow(s)
    print(f"  -> Generated {geo_csv} (Top {len(top_sites)} sites)")

    # 4b. Top sites GeoJSON FeatureCollection
    geojson_path = Path("data/exports/frequency/top_concentration_sites_geographic.geojson")
    features = []
    for s in top_sites:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(s["longitude"]), float(s["latitude"])],
            },
            "properties": {
                "rank": int(s["rank"]),
                "site_id": s["site_id"],
                "road_class": s["road_class"],
                "site_type": s["site_type"],
                "total_crashes": int(s["total_crashes_2004_2024"]),
                "fatal_crashes": int(s["fatal_crashes"]),
                "major_injury_crashes": int(s["major_injury_crashes"]),
                "ksi_crashes": int(s["ksi_crashes"]),
                "vru_crashes": int(s["vru_crashes"]),
                "crash_density_per_km": float(s["crash_density_per_km"]),
                "ksi_density_per_km": float(s["ksi_density_per_km"]),
                "vru_density_per_km": float(s["vru_density_per_km"]),
                "persistence_category": s["persistence_category"],
                "road_class_percentile": float(s["road_class_percentile"]),
                "analysis_period": "2004-2024",
                "is_predictive": False,
            },
        }
        features.append(feature)

    geojson_doc = {
        "type": "FeatureCollection",
        "metadata": {
            "title": "Top Historical Crash Concentration Locations in Allegheny County",
            "analysis_period": "2004-2024",
            "is_predictive": False,
            "description": "Empirical historical crash concentration and density. Does not represent predicted risk.",
            "crs": "EPSG:4326 (WGS84)",
            "crosswalk_version": "1.0.0",
        },
        "features": features,
    }

    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson_doc, f, indent=2)
    print(f"  -> Generated {geojson_path}")

    # -------------------------------------------------------------------------
    # 5. Export Retrospective Severity Association Audit
    # -------------------------------------------------------------------------
    print("\n[Step 5] Exporting Retrospective Severity Association Audit...")
    sev_analyzer = RetrospectiveSeverityAnalyzer()
    sev_csv = sev_analyzer.export_csv(
        output_path="data/exports/frequency/severity_retrospective_associations.csv"
    )
    print(f"  -> Generated {sev_csv}")

    print("\n" + "=" * 80)
    print("PHASE 4 MODULE C REPORTING & VISUALIZATION GENERATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
