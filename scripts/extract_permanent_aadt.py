"""Reconcile the Allegheny subset of PennDOT's 2023 and 2024 permanent-site tables."""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

YEARS = range(2020, 2025)


def lines(path):
    with pymupdf.open(path) as document:
        for page in document:
            yield from page.get_text(sort=True).splitlines()


def locations(path):
    station_pattern = re.compile(
        r"^\s*(\d+)\s*\**\s+Allegheny\s{2,}.*?\s{2,}(\d+)\s+(\d+)\s{2,}"
    )
    stations = {}
    for line in lines(path):
        match = station_pattern.search(line)
        if match:
            station, route, segment = match.groups()
            if station in stations:
                raise ValueError(f"Duplicate permanent station {station}")
            stations[station] = route.zfill(4), segment.zfill(4)
    if not stations:
        raise ValueError("No Allegheny permanent stations located")
    return stations


def annual_values(path, stations):
    aadt = {}
    for line in lines(path):
        cells = line.split()
        if not cells or cells[0] not in stations or len(cells) != 8:
            continue
        station, *values = cells[:6]
        if station in aadt or not all(re.fullmatch(r"[\d,]+", cell) for cell in values):
            raise ValueError(f"Unexpected or duplicate AADT row for permanent station {station}")
        aadt[station] = [int(cell.replace(",", "")) for cell in values]
    if stations.keys() != aadt.keys():
        raise ValueError("Permanent stations and annual tables did not reconcile")
    return aadt


def extract(directory):
    stations = locations(directory / "Permanent_Site_Locations.pdf")
    aadt = annual_values(directory / "5_Year_Summary_AADT_Permanent_sites.pdf", stations)
    historical_stations = locations(directory / "Permanent_Site_Locations_2023.pdf")
    historical_aadt = annual_values(directory / "Permanent_Site_AADT_2023.pdf", historical_stations)
    if stations != historical_stations or any(
        aadt[station][:-1] != historical_aadt[station][1:] for station in stations
    ):
        raise ValueError("The 2023 and 2024 reports disagree on keys or overlapping AADT")
    with (directory / "allegheny_permanent_aadt.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["permanent_site_id", "county_code", "route", "segment_2024", "year", "published_aadt",
                         "link_status"])
        for station, (route, segment) in sorted(stations.items()):
            values = [historical_aadt[station][0], *aadt[station]]
            for year, value in zip(range(YEARS.start - 1, YEARS.stop), values, strict=True):
                writer.writerow([station, "02", route, segment, year, value, "STATION_ONLY_SITE_YEAR_UNLINKED"])


def pilot_review(directory, phase3, phase4, output):
    """Compare station and geometry pathways without promoting diagnostic matches."""
    def digest(path):
        with path.open("rb") as source:
            return hashlib.file_digest(source, "sha256").hexdigest()

    def rows(path):
        manifest = json.loads((path.parent / "manifest.json").read_bytes())
        if digest(path) != manifest["outputs"][path.name]:
            raise ValueError(f"Pilot input checksum mismatch: {path}")
        with path.open(encoding="utf-8", newline="") as file:
            yield from csv.DictReader(file)

    historical = directory / "Permanent_Site_Locations_2023.pdf"
    historical_aadt = directory / "Permanent_Site_AADT_2023.pdf"
    stations = locations(historical)
    historical_values = annual_values(historical_aadt, stations)
    annual = list(rows(phase4 / "exposure/station_link_evidence.csv"))
    keys = {(r["route"], r["segment_2024"]): r["permanent_site_id"] for r in annual}
    diagnostics = defaultdict(list)
    for row in rows(phase3 / "recent_rms_candidates.csv"):
        site = keys.get((row["route"], row["segment"]))
        if site and row["county"] == "02":
            diagnostics[site].append(row)
    routes = {route: site for (route, _), site in keys.items()}
    geometry = defaultdict(Counter)
    for row in rows(phase3 / "crosswalk.csv"):
        site = routes.get(row["route"].zfill(4))
        if row["crash_year"] != "2024" or not site:
            continue
        counts = geometry[site]
        if row["match_status"] == "AMBIGUOUS":
            counts["conflict"] += 1
        elif int(row["candidate_count"]) == 0:
            counts["no_line_candidate"] += 1
        elif int(row["candidate_count"]) == 1:
            counts["one_snapshot_line_within_50m"] += 1
        else:
            counts["multiple_snapshot_lines_within_50m"] += 1

    candidates = {}
    for key, site in sorted(keys.items(), key=lambda pair: pair[1]):
        records = diagnostics[site]
        measured = sorted((float(r["decimal_to_offset_m"]), r["crash_id"]) for r in records
                          if r["decimal_to_offset_m"])
        candidates[site] = {
            "route_segment_2024": key,
            "route_segment_2023": stations.get(site),
            "rms_2023_crash_evidence": dict(Counter(r["evidence"] for r in records)),
            "closest_crash_decimal_to_rms_offset_m_and_crn": measured[:3],
            "geometry_2024_route_diagnostics": dict(geometry[site]),
            "rms_blocker": "CRASH_ERA_SEGMENT_EFFECTIVE_DATES_AND_OFFSET_GEOMETRY_UNVERIFIED",
            "geometry_blocker": "COORDINATE_PROVENANCE_AND_DIRECTIONAL_SITE_CONTINUITY_UNVERIFIED",
        }
    for row in annual:
        site = candidates[row["permanent_site_id"]]
        row["pilot_link_reason"] = (
            "STATION_DIRECTION_AND_SEGMENT_EFFECTIVE_DATES_UNVERIFIED"
            if row["year"] in {"2023", "2024"}
            else "DATED_STATION_TO_SEGMENT_AND_DIRECTION_HISTORY_REQUIRED"
        )
        if not row["tire_station_id"]:
            row["pilot_link_reason"] += ";NO_TIRE_SAMPLE_ID"
        row["location_table_key_agrees"] = site["route_segment_2023"] == site["route_segment_2024"]
        year_index = int(row["year"]) - 2019
        row["aadt_agrees_with_2023_report"] = (
            historical_values[row["permanent_site_id"]][year_index] == int(row["published_aadt"])
            if year_index < 5 else None
        )
    checksums = {
        historical.name: digest(historical),
        historical_aadt.name: digest(historical_aadt),
        "crosswalk/manifest.json": digest(phase3 / "manifest.json"),
        "exposure/manifest.json": digest(phase4 / "exposure/manifest.json"),
    }
    output.write_text(json.dumps({
        "status": "PROVISIONAL_NO_SUPPORTED_PILOT", "inputs": checksums,
        "candidates": candidates, "station_year_links": annual,
        "additional_2019_unlinked_aadt_by_station": {site: values[0] for site, values in historical_values.items()},
        "eligible_site_years": None, "expected_baseline_scope": [],
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--pilot-review", nargs=3, type=Path, metavar=("PHASE3", "PHASE4", "OUTPUT"))
    args = parser.parse_args()
    if args.pilot_review:
        pilot_review(args.directory, *args.pilot_review)
    else:
        extract(args.directory)
