"""Reconcile and map the frozen v6 geography separately from roadway candidates."""

import csv
import io
import json
import math
import zipfile
from collections import Counter, defaultdict

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.colors import LogNorm
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path
from shapely.geometry import Point
from shapely.geometry.polygon import orient
from shapely.prepared import prep

from build_provisional_crosswalk import FEET_TO_METRES, RAW, ROOT, digest
from edagent.coordinates.decoder import DECIMAL_PATTERN
from review_roadway_sources import COUNTY_BOUNDARY, _county_polygon, shapefile

SPATIAL = ROOT / "analysis/outputs/spatial"
FROZEN = {
    "candidate_coordinate_comparison_summary.csv": "1aac1de7fe33e28bb3b74c722b7547cd1211e6415091b21d8638b548c4016e97",
    "candidate_coordinate_disagreements_review.csv": "6454a9ae11f8c5821d26c72f07d4f5456ab1e16bb49fa9d7c1441103e95f0cd1",
    "coordinate_coverage_by_year.csv": "40683f291098c9d2f5218c51fbcb746b68b0d2a834653da64fb47c574dbddff4",
    "county_points_review.csv": "d100fdbba6e09c30927fc016c8cbe076cf58e9593a7cf598e5e0fcc8e79c9f42",
    "historical_grid_screening.csv": "5ce12d5e3dfe616a48a77aaac0214a47af4f9d063f9aadcd4038eadf5ff490d5",
    "police_coordinate_encoding_audit.csv": "d74959b3f28434b8be7c731247a1f325646552d32528e50ede8b334b4893f06f",
}
BOUNDARY_SHA256 = "da4051717caec55c75e3748c3608c2a3dbde8d1ff401bbaf4f952e3c3fb63ef1"
SOURCE_REGISTRY = ROOT / "data/reference/phase3_phase4_review_sources.json"
SECTION_ID = "02002200600000014014491"


def rows(path):
    with path.open(encoding="utf-8", newline="") as source:
        yield from csv.DictReader(source)


def checked_digest(path, expected):
    actual = digest(path)
    if actual != expected:
        raise ValueError(f"Checksum mismatch: {path}")
    return actual


def frozen_inputs():
    return {**{f"v6/{name}": checked_digest(SPATIAL / name, sha) for name, sha in FROZEN.items()},
            "county_boundary_2024": checked_digest(COUNTY_BOUNDARY, BOUNDARY_SHA256)}


def station_375(output):
    """Record archived section AADT without imputing a pilot count or site exposure."""
    source = json.loads(SOURCE_REGISTRY.read_bytes())["traffic_202411"]
    traffic_archive = ROOT / source["path"]
    checksum = checked_digest(traffic_archive, source["sha256"])
    with zipfile.ZipFile(traffic_archive) as archive:
        with shapefile.Reader(dbf=io.BytesIO(archive.read("PaTraffic2024_11.dbf"))) as table:
            fields = ["RMSTRAFFIC", "CTY_CODE", "ST_RT_NO", "SEG_BGN", "OFFSET_BGN", "SEG_END",
                      "OFFSET_END", "DIR_IND", "BASE_ADT", "BASE_ADT_Y", "VOL_CNT_KE", "VOL_CNT_DA"]
            section, = (row.as_dict() for row in table.iterRecords(fields=fields)
                        if row["RMSTRAFFIC"] == SECTION_ID)
    if (section["CTY_CODE"], section["ST_RT_NO"], section["DIR_IND"], section["BASE_ADT_Y"],
            section["BASE_ADT"]) != ("02", "0022", "E", 2023, 11072) or not (
            section["SEG_BGN"] < "0080" < section["SEG_END"]):
        raise ValueError("Archived traffic section does not reconcile with the Station 375 pilot")
    pilot = {
        "status": "INTERNAL_DIAGNOSTIC", "station": "375", "year": 2023,
        "observed_crash_count_status": "UNKNOWN", "observed_crash_count": None,
        "site_year_exposure": None,
        "limitations": "The archived eastbound traffic section contains segment 0080. "
                       "Station linkage, complete crash observation and site-year exposure are unverified.",
        "traffic_section": {"status": "ARCHIVED_TRAFFIC_SECTION_ONLY", "contains_segment": "0080",
                            "units": "vehicles/day", "source": "PennDOT PASDA PaTraffic, November 2024",
                            "source_sha256": checksum, "source_path": source["path"], **section},
    }
    (output / "station_375_pilot.json").write_text(json.dumps(pilot, indent=2) + "\n", encoding="utf-8")
    return checksum


def decimal_point(row):
    values = [row[field].strip() for field in ("DEC_LONG", "DEC_LAT")]
    if not all(values):
        return "missing_decimal_pair", None
    if not all(DECIMAL_PATTERN.fullmatch(value) for value in values):
        return "invalid_decimal_pair", None
    lon, lat = map(float, values)
    if not (-82 <= lon <= -78 and 38 <= lat <= 43):
        return "invalid_decimal_pair", None
    # Match the frozen notebook's np.isclose defaults for the (40, -80) placeholder.
    if abs(lon + 80) <= 0.00080001 and abs(lat - 40) <= 0.00040001:
        return "decimal_placeholder", None
    return "state_route_decimal", (lon, lat)


def audit_geography(output, county, frozen):
    points = {}
    point_counts = Counter()
    for row in rows(SPATIAL / "county_points_review.csv"):
        crn = row["CRASH_CRN"]
        if crn in points or row["LOCATION_SOURCE"] != "state_route_decimal":
            raise ValueError(f"Duplicate CRN or unexpected frozen county coordinate source: {crn}")
        points[crn] = (row["CRASH_YEAR"], float(row["LON"]), float(row["LAT"]))
        point_counts[points[crn][1:]] += 1

    prepared = prep(county)
    counts = Counter()
    grid_counts = Counter()
    grid_years = defaultdict(set)
    candidate_counts = Counter()
    seen = set()
    # Candidate rows follow the raw CSV order and must leave every primary site blank.
    for raw, candidate in zip(rows(RAW), rows(output / "crosswalk.csv"), strict=True):
        crn, year = raw["CRASH_CRN"], raw["CRASH_YEAR"]
        if (not crn or crn in seen or candidate["crash_id"] != crn or candidate["crash_year"] != year
                or candidate["primary_site_id"] or candidate["match_status"] not in {"AMBIGUOUS", "UNMATCHED"}):
            raise ValueError(f"Invalid diagnostic disposition for {crn}")
        seen.add(crn)
        counts[year, "raw_crns"] += 1
        counts[year, "police_raw_pair_present"] += bool(raw["LATITUDE"].strip() and raw["LONGITUDE"].strip())
        counts[year, "road_reference_key_present"] += all(
            raw[field].strip() for field in ("ROADWAY_COUNTY", "ROUTE", "SEGMENT"))
        counts[year, "road_offset_present"] += bool(raw["OFFSET"].strip())
        candidate_count = int(candidate["candidate_count"])
        if candidate_count == 0:
            band = "zero"
        elif candidate_count == 1:
            band = "one"
        else:
            band = "multiple"
        candidate_counts[band] += 1
        candidate_counts["associations"] += candidate_count
        candidate_counts["source_" + (candidate["coordinate_source"] or "none")] += 1
        status, point = decimal_point(raw)
        counts[year, status] += 1
        if point is None or not prepared.covers(Point(*point)):
            if point is not None:
                counts[year, "outside_county"] += 1
            if crn in points:
                raise ValueError(f"Unexpected frozen county point: {crn}")
            continue
        exported = points.pop(crn, None)
        if (exported is None or exported[0] != year
                or any(abs(a - b) > 1e-12 for a, b in zip(point, exported[1:]))):
            raise ValueError(f"County point does not match the frozen export: {crn}")
        counts[year, "inside_county"] += 1
        counts[year, "crns_at_repeated_point"] += point_counts[exported[1:]] > 1
        lon, lat = exported[1:]
        # Match the frozen LAT_BIN/LON_BIN grid (0.001°); see the Phase 3 review status.
        cell = round(lat * 1000) / 1000, round(lon * 1000) / 1000
        grid_counts[cell] += 1
        grid_years[cell].add(year)

    if points or len(seen) != frozen["data"]["rows"]:
        raise ValueError("Frozen CRN and county populations did not reconcile")
    coverage = {(r["CRASH_YEAR"], r["LOCATION_SOURCE"]): int(r["crashes"])
                for r in rows(SPATIAL / "coordinate_coverage_by_year.csv")}
    years = sorted({year for year, _ in counts})
    for year in years:
        if (counts[year, "state_route_decimal"] != coverage[year, "state_route_decimal"]
                or counts[year, "raw_crns"] - counts[year, "state_route_decimal"]
                != coverage[year, "unavailable_or_ambiguous"]):
            raise ValueError(f"Frozen coordinate coverage mismatch for {year}")
    grid = list(rows(SPATIAL / "historical_grid_screening.csv"))
    expected_grid = {(float(r["LAT_BIN"]), float(r["LON_BIN"])):
                     (int(r["crash_count"]), int(r["years_observed"])) for r in grid}
    if len(expected_grid) != len(grid) or expected_grid != {
        key: (n, len(grid_years[key])) for key, n in grid_counts.items()
    }:
        raise ValueError("County points do not reconcile with the frozen grid cells")
    with (output / "county_coordinate_inventory_by_year.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        metrics = sorted({key for _, key in counts})
        writer.writerow(["year", *metrics])
        for year in years:
            writer.writerow([year, *(counts[year, key] for key in metrics)])
    totals = Counter()
    # Keep the first occurrence of each metric in year/metric order for stable JSON bytes.
    for year, metric in sorted(counts):
        totals[metric] += counts[year, metric]
    return grid_counts, {
        "PRIMARY_SITE_ASSIGNMENTS_ACCEPTED": 0,
        "unique_crns": len(seen), "coverage": dict(totals), "grid_cells": len(grid_counts),
        "unique_coordinate_pairs_inside_county": len(point_counts),
        "candidate_associations_nonadditive": dict(candidate_counts),
    }


def county_path(county):
    polygons = county.geoms if county.geom_type == "MultiPolygon" else [county]
    oriented = [orient(polygon) for polygon in polygons]
    return Path.make_compound_path(*(Path(ring.coords, closed=True) for polygon in oriented
                                    for ring in (polygon.exterior, *polygon.interiors)))


def draw_maps(output, county, grid_counts, conflicts=None):
    boundary = county_path(county)
    plt.switch_backend("Agg")
    matplotlib.rcParams.update({"svg.hashsalt": "edagent-phase3-v3", "svg.fonttype": "none"})
    names = ("county_grid",) if conflicts is None else ("county_grid", "coordinate_conflicts")
    for name in names:
        fig, ax = plt.subplots(figsize=(10, 7), layout="constrained")
        ax.add_patch(PathPatch(boundary, facecolor="none", edgecolor="#344054", linewidth=0.8, zorder=3))
        ax.set(xlabel="Longitude (WGS 84)", ylabel="Latitude (WGS 84)",
               aspect=1 / math.cos(math.radians(40.45)))
        if name == "county_grid":
            cells = PatchCollection([Rectangle((lon - 0.0005, lat - 0.0005), 0.001, 0.001)
                                     for lat, lon in grid_counts], cmap="viridis", norm=LogNorm())
            cells.set_array(list(grid_counts.values()))
            cells.set_clip_path(boundary, ax.transData)
            ax.add_collection(cells)
            fig.colorbar(cells, ax=ax, label="Reported crashes per cell (log scale)")
            ax.set_title("Reported-crash concentration | Allegheny County, 2004–2024\n"
                         "Frozen v6 state decimals · 0.001° cells clipped to 2024 Census 500k boundary\n"
                         f"{sum(grid_counts.values()):,} mapped CRNs · excludes unavailable and outside points\n"
                         "Descriptive concentration · exposure unmeasured · site assignments accepted: 0",
                         fontsize=10)
        else:
            pairs = [[(float(row[lon]), float(row[lat])) for lon, lat in (
                      ("state_decimal_lon", "state_decimal_lat"), ("candidate_police_lon", "candidate_police_lat"))]
                     for row in conflicts]
            ax.add_collection(LineCollection(pairs, colors="#98A2B3", alpha=0.35, linewidths=0.45))
            for points, label, color in zip(zip(*pairs), ("State decimal", "Police DMS hypothesis"),
                                            ("#175CD3", "#B42318")):
                ax.scatter(*zip(*points), s=5, color=color, alpha=0.65, label=label)
            ax.legend(loc="upper right", markerscale=2)
            ax.set_title("Coordinate conflicts | Allegheny County crash records, 2004–2024\n"
                         f"Frozen v6 · {len(conflicts):,} paired disagreements over 500 m · one connector per CRN\n"
                         "Internal coordinate diagnostics · police encoding unverified · site assignments accepted: 0",
                         fontsize=10)
        ax.autoscale_view()
        fig.savefig(output / f"{name}.svg", bbox_inches="tight", pad_inches=0.18, metadata={"Date": None})
        plt.close(fig)


def stage_diagnostics(output, frozen):
    config = ROOT / "data/reference/coordinates/police_gps_format.json"
    summary, = rows(SPATIAL / "candidate_coordinate_comparison_summary.csv")
    if (json.loads(config.read_bytes())["verified"] is not False
            or frozen["police_gps_format_verified"] is not False or summary["official_format_verified"] != "False"):
        raise ValueError("The frozen police coordinate parser must remain unverified")
    county = _county_polygon()
    grid, qa = audit_geography(output, county, frozen)
    conflicts = list(rows(output / "conflict_review.csv"))
    expected = {r["CRASH_CRN"] for r in rows(SPATIAL / "candidate_coordinate_disagreements_review.csv")}
    if (len(conflicts) != frozen["candidate_dms_disagreements_over_500m_n"]
            or {r["CRASH_CRN"] for r in conflicts} != expected
            or any(not r["disposition"].startswith("WITHHELD") or r["primary_site_id"]
                   or float(r["difference_m"]) <= 500 for r in conflicts)):
        raise ValueError("Conflict dispositions do not reconcile with the frozen comparison")
    traffic_hash = station_375(output)
    draw_maps(output, county, grid, conflicts)
    qa.update({"police_gps_parser_status": "UNVERIFIED", "coordinate_comparison": summary,
               "conflicts_with_withheld_disposition": len(conflicts), "out_of_scope_crns": 0,
               "geography": {"boundary": "2024 Census 500k, GEOID 42003", "map_crs": "EPSG:4326",
                             "grid_degrees": 0.001, "roadway_distance_crs": "EPSG:2272",
                             "metres_per_us_survey_foot": FEET_TO_METRES}})
    (output / "diagnostic_qa.json").write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    return {"police_gps_format": digest(config), "penndot_traffic_202411": traffic_hash}
