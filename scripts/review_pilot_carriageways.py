"""Map directional station and crash diagnostics without assigning primary sites."""

import argparse
import csv
import io
import json
import math
from pathlib import Path
import zipfile

from review_roadway_sources import (
    CONFLICTS, CRS, FEET_TO_METRES, Point, RAW, ROOT, Transformer, _lrs_key, _orient_rms_line,
    digest, linemerge, mapping, shape, shapefile, transform,
)

DISTRICT_MAP = "https://gis.penndot.gov/BPR_PDF_FILES/MAPS/Traffic/PermTrafSiteLocMaps/DistrictMaps/District_11.pdf"
ARCHIVE = "https://www.pasda.psu.edu/download/padot/state/historic/PaStateRoads/"
# District 11 map created 2026-01-26. The transcription is snapshot evidence.
STATIONS = (
    ("208", "0376", "0794", "E", 1442, -79.8404631169325, 40.4437481518813),
    ("208", "0376", "0795", "W", 1297, -79.8406900158766, 40.4439831286857),
    ("203", "0065", "0270", "N", 0, -80.2166880663543, 40.5712818148009),
    ("203", "0065", "0271", "S", 0, -80.2167764578937, 40.5712199317507),
    ("375", "0022", "0080", "E", 0, -80.2252508198692, 40.4395907609556),
    ("375", "0022", "0081", "W", 0, -80.2267078751124, 40.439665177263),
    ("840", "0279", "0122", "N", 1267, -80.0928016562861, 40.5749945935734),
    ("840", "0279", "0123", "S", 1158, -80.0929760136743, 40.5745826139728),
)
RADIUS_M = 50


def nearby_lines(path, station_keys, points, to_plane):
    lines = []
    with zipfile.ZipFile(path) as archive:
        files = {Path(entry).suffix.lower(): entry for entry in archive.namelist()}
        crs = CRS.from_wkt(archive.read(files[".prj"]).decode())
        project = Transformer.from_crs(crs, 2272, always_xy=True).transform
        reader = shapefile.Reader(
            **{ext: io.BytesIO(archive.read(files["." + ext])) for ext in ("shp", "shx", "dbf")},
            encodingErrors="replace",
        )
        for item in reader.iterRecords(fields=["CTY_CODE"]):
            if item["CTY_CODE"] != "02":
                continue
            record = reader.record(item.oid).as_dict()
            key = record["ST_RT_NO"], record["SEG_NO"]
            geometry = reader.shape(item.oid)
            if not geometry.points:
                continue
            line = transform(project, shape(geometry.__geo_interface__))
            if line.geom_type == "MultiLineString":
                line = linemerge(line)
            # Include ramps, other routes and the opposite carriageway for geometric comparison.
            if key in station_keys or any(line.distance(point) * FEET_TO_METRES <= RADIUS_M for point in points):
                lines.append((key, line, record, _orient_rms_line(line, record, to_plane)))
    return lines


def offset_point(line, length, offset):
    if line is not None and length and 0 <= offset <= length:
        return line.interpolate(offset / length, normalized=True)
    return None


def pilot_crashes(keys, project):
    with CONFLICTS.open(encoding="utf-8", newline="") as source:
        conflicts = {row["CRASH_CRN"] for row in csv.DictReader(source)}
    with RAW.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            key = _lrs_key(row)
            if row["CRASH_YEAR"] != "2023" or not key or key[0] != "02" or key[1:] not in keys:
                continue
            lon, lat = (float(row[field] or "nan") for field in ("DEC_LONG", "DEC_LAT"))
            point = Point(*project(lon, lat)) if -180 <= lon <= 180 and -90 <= lat <= 90 else None
            yield key[1:], row, row["CRASH_CRN"] in conflicts, point


def review(directory, output):
    frozen = json.loads((ROOT / "analysis/outputs/run_manifest.json").read_bytes())
    raw_sha256 = digest(RAW)
    if raw_sha256 != frozen["data"]["sha256"]:
        raise ValueError("Frozen crash input checksum mismatch")
    to_plane = Transformer.from_crs(4326, 2272, always_xy=True).transform
    to_wgs = Transformer.from_crs(2272, 4326, always_xy=True).transform
    anchors = {(route, segment): Point(*to_plane(lon, lat))
               for _, route, segment, _, _, lon, lat in STATIONS}
    crashes = list(pilot_crashes(anchors, to_plane))
    nearby_points = [*anchors.values(), *(point for _, _, _, point in crashes if point is not None)]
    output.mkdir(parents=True)
    report = {"status": "PROVISIONAL", "station_map": {"url": DISTRICT_MAP, "version": "2026-01-26",
              "sha256": digest(directory / "District_11.pdf") if (directory / "District_11.pdf").is_file() else None,
              "coverage": "District 11 station locations and reported activation dates"},
              "raw_sha256": raw_sha256, "conflicts_sha256": digest(CONFLICTS), "archives": {}}
    features = []
    for name in ("PaStateRoads2023_10.zip", "PaStateRoads2024_11.zip"):
        path = directory / name
        result = {"url": ARCHIVE + name, "snapshot": path.stem.removeprefix("PaStateRoads").replace("_", "-"),
                  "coverage": "County 02 state-road lines within 50 m of station or keyed crash points, plus station keys"}
        report["archives"][name] = result
        if not path.is_file():
            result.update(status="MISSING", sha256=None)
            continue
        lines = nearby_lines(path, set(anchors), nearby_points, to_plane)
        result.update(status="SNAPSHOT_ONLY", sha256=digest(path), carriageways=[], crashes=[])
        for key, line, record, _ in lines:
            features.append({"type": "Feature", "geometry": mapping(transform(to_wgs, line)),
                             "properties": {"archive": name, "route": key[0], "segment": key[1],
                                            "direction": record["DIR_IND"], "role": "SNAPSHOT_ROAD"}})
        target_lines = {}
        for station, route, segment, direction, offset, lon, lat in STATIONS:
            key = route, segment
            point = anchors[key]
            matches = [(line, record, oriented) for candidate, line, record, oriented in lines
                       if candidate == key]
            evidence = {"station": station, "route": route, "segment": segment, "direction": direction,
                        "reported_offset_ft": offset, "snapshot_key_count": len(matches),
                        "nearby_snapshot_keys": sorted({candidate for candidate, line, _, _ in lines
                                                        if line.distance(point) * FEET_TO_METRES <= RADIUS_M})}
            if len(matches) == 1:
                line, record, oriented = matches[0]
                length = record["SEG_LNGTH_"]
                projected = offset_point(oriented, length, offset)
                evidence.update(snapshot_direction=record["DIR_IND"], rms_length_ft=length,
                                geometry_length_m=round(line.length * FEET_TO_METRES, 3),
                                point_to_line_m=round(point.distance(line) * FEET_TO_METRES, 3),
                                point_to_offset_m=round(point.distance(projected) * FEET_TO_METRES, 3)
                                if projected is not None else None)
                if direction == record["DIR_IND"]:
                    target_lines[key] = oriented, length, direction
            result["carriageways"].append(evidence)
            features.append({"type": "Feature", "geometry": mapping(Point(lon, lat)),
                             "properties": {"archive": name, "station": station, "route": route,
                                            "segment": segment, "direction": direction, "role": "STATION_MAP_POINT"}})
        for key, row, conflict, point in crashes:
            evidence = {"crash_id": row["CRASH_CRN"], "route": key[0], "segment": key[1],
                        "direction": row["RDWY_ORIENT"], "offset_ft": row["OFFSET"],
                        "frozen_coordinate_conflict": conflict, "disposition": "WITHHELD",
                        "reason": "CRASH_ERA_AND_COORDINATE_LINEAGE_UNVERIFIED"}
            result["crashes"].append(evidence)
            if point is None:
                continue
            distances = sorted((round(line.distance(point) * FEET_TO_METRES, 3), *candidate, record["DIR_IND"])
                               for candidate, line, record, _ in lines)
            evidence["snapshot_lines_within_50m"] = [entry for entry in distances if entry[0] <= RADIUS_M]
            target = target_lines.get(key)
            offset = float(row["OFFSET"] or "nan")
            if target and target[2] == row["RDWY_ORIENT"] and math.isfinite(offset):
                projected = offset_point(*target[:2], offset)
                if projected is not None:
                    evidence["decimal_to_offset_m"] = round(point.distance(projected) * FEET_TO_METRES, 3)
            features.append({"type": "Feature", "geometry": mapping(transform(to_wgs, point)),
                             "properties": {"archive": name, "role": "WITHHELD_CRASH_POINT",
                                            "crash_id": evidence["crash_id"]}})
    (output / "carriageway_review.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "pilot_candidates.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": features}) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_directory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    review(args.source_directory, args.output)
