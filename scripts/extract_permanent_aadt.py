"""Extract the Allegheny subset of PennDOT's two 2024 permanent-site tables."""

import argparse
import csv
import re
from pathlib import Path

import pymupdf

YEARS = range(2020, 2025)


def lines(path):
    with pymupdf.open(path) as document:
        for page in document:
            yield from page.get_text(sort=True).splitlines()


def extract(directory):
    station_pattern = re.compile(
        r"^\s*(\d+)\s*\**\s+Allegheny\s{2,}.*?\s{2,}(\d+)\s+(\d+)\s{2,}"
    )
    stations = {}
    for line in lines(directory / "Permanent_Site_Locations.pdf"):
        match = station_pattern.search(line)
        if match:
            station, route, segment = match.groups()
            if station in stations:
                raise ValueError(f"Duplicate permanent station {station}")
            stations[station] = route.zfill(4), segment.zfill(4)
    if not stations:
        raise ValueError("No Allegheny permanent stations located")

    aadt = {}
    for line in lines(directory / "5_Year_Summary_AADT_Permanent_sites.pdf"):
        cells = line.split()
        if not cells or cells[0] not in stations or len(cells) != 8:
            continue
        station, *values = cells[:6]
        if station in aadt or not all(re.fullmatch(r"[\d,]+", cell) for cell in values):
            raise ValueError(f"Unexpected or duplicate AADT row for permanent station {station}")
        aadt[station] = [int(cell.replace(",", "")) for cell in values]
    if stations.keys() != aadt.keys():
        raise ValueError("Permanent stations and annual tables did not reconcile")

    with (directory / "allegheny_permanent_aadt.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["permanent_site_id", "county_code", "route", "segment_2024", "year", "published_aadt",
                         "link_status"])
        for station, (route, segment) in sorted(stations.items()):
            for year, value in zip(YEARS, aadt[station]):
                writer.writerow([station, "02", route, segment, year, value, "STATION_ONLY_SITE_YEAR_UNLINKED"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    extract(parser.parse_args().directory)
