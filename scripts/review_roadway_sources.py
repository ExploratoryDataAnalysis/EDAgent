"""Stage source profiles, candidate lineage, junctions and conflict evidence."""

import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import Point, mapping, shape
from shapely.ops import linemerge, transform
from shapely.strtree import STRtree

from build_provisional_crosswalk import (
    CONFLICTS, FEET_TO_METRES, NETWORK, RAW, ROOT, candidate_for_point, digest, load_network,
)
from edagent.roadway.network_review import cluster_junctions, line_edges, segment_lineage

PASDA = "https://www.pasda.psu.edu/download/alleghenycounty/historic/AlleghenyCounty_StreetCenterlines/"
ARCHIVE_NAMES = {
    "2006": "AlleghenyCounty_Streetcl2006.zip",
    **{f"{year}{month}": f"AlleghenyCounty_StreetCenterlines{year}{month}.zip"
       for year, month in [(2013, 12), (2014, 12), (2015, 11), (2016, "08")]
       + [(y, 12) for y in range(2017, 2025)]},
}
PENNDOT_ARCHIVE = "https://www.pasda.psu.edu/download/padot/state/historic/"
COUNTY_BOUNDARY = ROOT / "data/reference/municipal_boundaries/cb_2024_us_county_500k.zip"


def _county_polygon():
    with zipfile.ZipFile(COUNTY_BOUNDARY) as archive:
        files = {name.rsplit(".", 1)[-1].lower(): name for name in archive.namelist()}
        crs = CRS.from_wkt(archive.read(files["prj"]).decode())
        reader = shapefile.Reader(**{ext: io.BytesIO(archive.read(files[ext]))
                                     for ext in ("shp", "shx", "dbf")}, encodingErrors="replace")
        county = [item for item in reader.iterRecords(fields=["GEOID"]) if item["GEOID"] == "42003"]
        if len(county) != 1:
            raise ValueError("Expected one Allegheny County boundary")
        return transform(Transformer.from_crs(crs, 4326, always_xy=True).transform,
                         shape(reader.shape(county[0].oid).__geo_interface__))


def archive_profile(path):
    with zipfile.ZipFile(path) as archive:
        files = {name.rsplit(".", 1)[-1].lower(): name for name in archive.namelist()}
        crs = CRS.from_wkt(archive.read(files["prj"]).decode()) if "prj" in files else None
        reader = shapefile.Reader(**{ext: io.BytesIO(archive.read(files[ext]))
                                     for ext in ("shp", "shx", "dbf")}, encodingErrors="replace")
        fields = [field[0] for field in reader.fields[1:]]
        field_map = {field.upper(): field for field in fields}
        key = next((field_map[f] for f in ("FEATURE_KE", "FEATURE_KEY", "UNIQUE_ID", "DYNAMAPID")
                    if f in field_map), None)
        metadata = {"sha256": digest(path), "epsg": crs.to_epsg() if crs else None,
                    "features": reader.numRecords, "fields": fields, "bbox": list(reader.bbox)}
        if metadata["epsg"] != 2272:
            metadata["lineage_status"] = "UNSUPPORTED_CRS"
            return metadata, {}, {}
        key_counts = Counter(str(row[key]).strip() for row in reader.iterRecords()) if key else Counter()
        records = {}
        classes = Counter()
        endpoints = defaultdict(set)
        fallback = 0
        for item in reader.iterShapeRecords():
            row = {k.upper(): v for k, v in item.record.as_dict().items()}
            feature_key = str(row[key.upper()]).strip() if key else ""
            if feature_key in {"", "None", "0"} or key_counts[feature_key] != 1:
                feature_key = f"{path.stem}:ROW:{item.record.oid}"
                fallback += 1
            elif key.upper() not in {"FEATURE_KE", "FEATURE_KEY"}:
                feature_key = f"{key}:{feature_key}"
            classes[str(row.get("FCC") or row.get("CFCC") or "")] += 1
            if item.shape.shapeType == shapefile.NULL:
                continue
            street = str(row.get("FULL_NAME") or row.get("STREETNAME") or "").strip().upper()
            line = shape(item.shape.__geo_interface__)
            records[feature_key] = ((street, str(row.get("ONEWAY") or "").strip().upper()),
                                    line_edges(line))
            if street:
                parts = line.geoms if line.geom_type == "MultiLineString" else [line]
                for part in parts:
                    for end in (part.coords[0], part.coords[-1]):
                        endpoints[tuple(round(value, 1) for value in end[:2])].add((feature_key, street))
        metadata["fcc_counts"] = dict(classes)
        metadata["key_field"] = key
        metadata["fallback_row_keys"] = fallback
        metadata["usable_geometry"] = len(records)
        return metadata, records, endpoints


def review_lineage(output, source_directory):
    paths = {version: source_directory / name for version, name in ARCHIVE_NAMES.items()}
    paths["202412"] = NETWORK
    paths["202610"] = NETWORK.with_name("alleghenycounty_streetcenterlines202610.zip")
    profiles = {}
    previous, previous_version = {}, None
    stable_ids = {}
    previous_nodes = {}
    totals = Counter()
    with ((output / "segment_lineage.csv").open("w", encoding="utf-8", newline="") as file,
          (output / "junction_lineage.csv").open("w", encoding="utf-8", newline="") as junction_file):
        writer = csv.writer(file)
        writer.writerow(["older_version", "newer_version", "older_key", "newer_key",
                         "evidence", "candidate_continuity_id"])
        junction_writer = csv.writer(junction_file)
        junction_writer.writerow(["older_version", "newer_version", "x_ft", "y_ft",
                                  "evidence", "candidate_continuity_id", "incident_segment_ids"])
        for version, path in sorted(paths.items()):
            if not path.exists():
                profiles[version] = {"status": "MISSING_LOCAL_ARCHIVE", "url": PASDA + path.name}
                continue
            profile, current, endpoints = archive_profile(path)
            url = (PASDA + path.name if version != "202610" else
                   "https://www.pasda.psu.edu/uci/DataSummary.aspx?dataset=1224")
            profiles[version] = {"url": url, **profile}
            if not current:
                continue
            current_ids = {}
            for old_key, new_key, status in segment_lineage(previous, current):
                identity = ""
                if new_key:
                    default = f"PASDA{version}:SEG:{new_key}"
                    identity = stable_ids[old_key] if status in {"IDENTICAL", "RENUMBERING_CANDIDATE"} else default
                    current_ids[new_key] = identity
                totals[(previous_version, version, status)] += 1
                writer.writerow([previous_version, version, old_key, new_key, status, identity])
            current_nodes = {}
            for coordinate, incidents in sorted(endpoints.items()):
                if len({street for _, street in incidents}) < 2:
                    continue
                members = "|".join(sorted({current_ids[key] for key, _ in incidents}))
                old = previous_nodes.get(coordinate)
                if old and old[1] == members:
                    identity, status = old[0], "SAME_ENDPOINT_AND_INCIDENT_LINEAGE"
                else:
                    token = hashlib.sha256(f"{coordinate}|{members}".encode()).hexdigest()[:20]
                    identity = f"PASDA{version}:JUNC:{token}"
                    status = "UNRESOLVED_CHANGED_ENDPOINT_TOPOLOGY" if old else "UNRESOLVED_NO_PREDECESSOR"
                current_nodes[coordinate] = identity, members
                junction_writer.writerow([previous_version, version, *coordinate, status, identity, members])
            for coordinate in sorted(previous_nodes.keys() - current_nodes.keys()):
                identity, members = previous_nodes[coordinate]
                junction_writer.writerow([previous_version, version, *coordinate,
                                         "UNRESOLVED_NO_SUCCESSOR", identity, members])
            previous_nodes = current_nodes
            previous, previous_version, stable_ids = current, version, current_ids
    return {"archives": profiles, "pair_counts": [
        {"older": older, "newer": newer, "evidence": status, "links": count}
        for (older, newer, status), count in totals.items()
    ]}


def review_official_archive(source_directory, output, name, folder):
    path = source_directory / name
    profile = {"url": PENNDOT_ARCHIVE + folder + "/" + name, "snapshot": "2024-11"}
    if not zipfile.is_zipfile(path):
        return {**profile, "status": "MISSING_OR_INCOMPLETE_ARCHIVE"}
    with zipfile.ZipFile(path) as archive:
        if bad_file := archive.testzip():
            raise ValueError(f"CRC failure in {name}: {bad_file}")
        files = {entry.rsplit(".", 1)[-1].lower(): entry for entry in archive.namelist()}
        crs = CRS.from_wkt(archive.read(files["prj"]).decode())
        reader = shapefile.Reader(**{ext: io.BytesIO(archive.read(files[ext]))
                                     for ext in ("shp", "shx", "dbf")}, encodingErrors="replace")
        profile.update({"sha256": digest(path), "epsg": crs.to_epsg(), "statewide_features": reader.numRecords,
                        "fields": [field[0] for field in reader.fields[1:]]})
        keys = Counter()
        grade = folder == "PA_AtGrade_Intersections"
        features = []
        rms = {}
        missing_geometry = 0
        to_wgs = Transformer.from_crs(crs, 4326, always_xy=True).transform
        to_plane = Transformer.from_crs(crs, 2272, always_xy=True).transform
        from_wgs = Transformer.from_crs(4326, 2272, always_xy=True).transform
        for item in reader.iterRecords(fields=["CTY_CODE"]):
            if item["CTY_CODE"] != "02":
                continue
            record = reader.record(item.oid).as_dict()
            key = record["ST_RT_NO"], record["SEG_NO"]
            keys[key] += 1
            geometry = reader.shape(item.oid)
            if not geometry.points:
                missing_geometry += 1
                continue
            if grade:
                fields = ("ST_RT_NO", "SEG_NO", "SEG_OFFSET", "CTY_IXN", "ST_RT_IXN", "SEG_IXN",
                          "OFFSET_IXN", "INTERSECT_", "NODE_ID", "GPID")
                props = {field: record[field] for field in fields}
                props["evidence"] = "PENNDOT_AT_GRADE_SNAPSHOT_2024_11"
                features.append({"type": "Feature", "properties": props,
                                 "geometry": mapping(Point(*to_wgs(*geometry.points[0])))})
            else:
                line = transform(to_plane, shape(geometry.__geo_interface__))
                line = linemerge(line) if line.geom_type == "MultiLineString" else line
                anchor = _orient_rms_line(line, record, from_wgs)
                if anchor is not None:
                    rms[key] = anchor, record["SEG_LNGTH_"], record["DIR_IND"]
        profile.update({"allegheny_features": sum(keys.values()), "route_segment_keys": len(keys),
                        "nonunique_route_segment_keys": sum(n > 1 for n in keys.values()),
                        "missing_geometry": missing_geometry})
        if grade:
            profile["nonempty_node_ids"] = len({f["properties"]["NODE_ID"] for f in features} - {"", None})
            for feature in features:
                props = feature["properties"]
                node_key = props["NODE_ID"] or f"ROW:{props['GPID']}"
                props["site_id"] = f"PENNDOT202411:JUNC:{node_key}"
            (output / "penndot_at_grade_202411.geojson").write_text(json.dumps(
                {"type": "FeatureCollection", "features": features}, separators=(",", ":")), encoding="utf-8")
        else:
            rms = {key: value for key, value in rms.items() if keys[key] == 1}
            profile["uniquely_keyed_endpoint_checked_lines"] = len(rms)
            profile["recent_lrs_diagnostic"] = _review_recent_lrs(output, keys, rms, from_wgs)
    return profile


def _orient_rms_line(line, record, project):
    if line.geom_type != "LineString" or line.is_empty or not (record["SEG_LNGTH_"] or 0) > 0:
        return None
    try:
        begin = Point(*project(float(record["X_VALUE_BG"]), float(record["Y_VALUE_BG"])))
        end = Point(*project(float(record["X_VALUE_EN"]), float(record["Y_VALUE_EN"])))
    except (ValueError, TypeError):
        return None
    a, b = Point(line.coords[0]), Point(line.coords[-1])
    forward = max(begin.distance(a), end.distance(b)) * FEET_TO_METRES
    backward = max(begin.distance(b), end.distance(a)) * FEET_TO_METRES
    if (forward <= 20) == (backward <= 20):
        return None
    return line if forward <= 20 else line.reverse()


def _lrs_key(row):
    fields = [row[k].strip() for k in ("ROADWAY_COUNTY", "ROUTE", "SEGMENT")]
    if all(re.fullmatch(r"\d+(?:\.0+)?", field) for field in fields):
        county, route, segment = (field.split(".")[0] for field in fields)
        return county.zfill(2), route.zfill(4), segment.zfill(4)
    return None


def _review_recent_lrs(output, keys, lines, project):
    totals = Counter()
    with (RAW.open(encoding="utf-8", newline="") as source,
          (output / "recent_rms_candidates.csv").open("w", encoding="utf-8", newline="") as file):
        writer = csv.writer(file)
        writer.writerow(["crash_id", "crash_year", "county", "route", "segment", "offset_ft", "direction",
                         "offset_candidate_x_ft", "offset_candidate_y_ft", "decimal_to_offset_m", "evidence",
                         "disposition"])
        for row in csv.DictReader(source):
            year = row["CRASH_YEAR"]
            if year not in {"2023", "2024"}:
                continue
            key = _lrs_key(row)
            county, route, segment = key or ("", row["ROUTE"], row["SEGMENT"])
            rms_key = (route, segment)
            offset, direction = row["OFFSET"], row["RDWY_ORIENT"].strip().upper()
            status = "INCOMPLETE_OR_OUTSIDE_COUNTY_LRS_KEY"
            x = y = distance = ""
            if key and county == "02":
                status = "NO_UNIQUE_ENDPOINT_CHECKED_RMS_GEOMETRY"
                if keys[rms_key] == 1 and rms_key in lines:
                    line, length, rms_direction = lines[rms_key]
                    status = "INCOMPATIBLE_OR_UNKNOWN_DIRECTION"
                    if direction in {"N", "S", "E", "W"} and rms_direction in {direction, "B"}:
                        status = "MISSING_OR_OUT_OF_RANGE_OFFSET"
                        if re.fullmatch(r"\d+(?:\.\d+)?", offset) and 0 <= float(offset) <= length:
                            point = line.interpolate(float(offset) / length, normalized=True)
                            x, y = round(point.x, 3), round(point.y, 3)
                            status = "OFFSET_CANDIDATE_ONLY"
                            if row["DEC_LONG"] and row["DEC_LAT"]:
                                observed = Point(*project(float(row["DEC_LONG"]), float(row["DEC_LAT"])))
                                difference = observed.distance(point) * FEET_TO_METRES
                                if math.isfinite(difference):
                                    distance = round(difference, 3)
            totals[(year, status)] += 1
            writer.writerow([row["CRASH_CRN"], year, county, route, segment, offset, direction, x, y, distance,
                             status, "WITHHELD_CRASH_ERA_VALIDITY_UNVERIFIED"])
    return [{"year": year, "status": status, "crashes": count}
            for (year, status), count in sorted(totals.items())]


def review_junction_candidates(output):
    official = output / "penndot_at_grade_202411.geojson"
    if not official.exists():
        return {"status": "MISSING_OFFICIAL_SNAPSHOT"}
    project = Transformer.from_crs(4326, 2272, always_xy=True).transform
    features = json.loads(official.read_bytes())["features"]
    tree = STRtree([Point(*project(*feature["geometry"]["coordinates"])) for feature in features])
    counts = Counter()
    with (RAW.open(encoding="utf-8", newline="") as source,
          (output / "junction_crash_candidates.csv").open("w", encoding="utf-8", newline="") as file):
        writer = csv.writer(file)
        writer.writerow(["crash_id", "year", "nearest_at_grade_snapshot_id", "distance_m",
                         "candidate_node_count", "disposition"])
        for row in csv.DictReader(source):
            if row["CRASH_YEAR"] != "2024" or row["INTERSECTION"] != "1":
                continue
            candidates = {}
            if row["DEC_LAT"] and row["DEC_LONG"]:
                point = Point(*project(float(row["DEC_LONG"]), float(row["DEC_LAT"])))
                if math.isfinite(point.x) and math.isfinite(point.y):
                    for index in tree.query(point, predicate="dwithin", distance=50 / FEET_TO_METRES):
                        site_id = features[index]["properties"]["site_id"]
                        distance = point.distance(tree.geometries[index]) * FEET_TO_METRES
                        candidates[site_id] = min(distance, candidates.get(site_id, distance))
            if candidates:
                nearest = min(candidates, key=lambda site_id: (candidates[site_id], site_id))
                writer.writerow([row["CRASH_CRN"], 2024, nearest, round(candidates[nearest], 3),
                                 len(candidates), "WITHHELD_HISTORICAL_SCOPE_AND_INCIDENT_ROADS_UNVERIFIED"])
                counts["WITH_NEARBY_SNAPSHOT_NODE"] += 1
            else:
                writer.writerow([row["CRASH_CRN"], 2024, "", "", 0, "NO_SNAPSHOT_CANDIDATE"])
                counts["WITHOUT_SNAPSHOT_CANDIDATE"] += 1
    return dict(counts)


def review_locations(output):
    sites, lines, _ = load_network(NETWORK)
    sites_by_id = {site["site_id"]: {**site, "ramp": site["fcc"].upper() == "A63"} for site in sites}
    with (output / "candidate_junctions.csv").open(encoding="utf-8", newline="") as source:
        nodes = []
        for row in csv.DictReader(source):
            segments = set(row["segment_ids"].split("|"))
            roads = {sites_by_id[s]["street"].strip().upper() for s in segments} - {""}
            nodes.append({"id": row["junction_id"], "x": float(row["x_ft"]),
                          "y": float(row["y_ft"]), "segments": segments, "roads": roads})
    groups = cluster_junctions(nodes, sites_by_id, 25 / FEET_TO_METRES)
    to_wgs = Transformer.from_crs(2272, 4326, always_xy=True).transform
    features = []
    with (output / "junction_clusters.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["cluster_id", "member_ids", "incident_segment_ids", "grade_status"])
        for group in groups:
            members = [nodes[i] for i in group]
            ids = "|".join(sorted(node["id"] for node in members))
            identity = "PASDA202412:CLUSTER:" + hashlib.sha256(ids.encode()).hexdigest()[:20]
            incident = sorted(set().union(*(node["segments"] for node in members)))
            writer.writerow([identity, ids, "|".join(incident), "AT_GRADE_UNVERIFIED"])
            x = sum(node["x"] for node in members) / len(members)
            y = sum(node["y"] for node in members) / len(members)
            features.append({"type": "Feature", "geometry": mapping(Point(*to_wgs(x, y))),
                             "properties": {"site_id": identity, "grade_status": "AT_GRADE_UNVERIFIED"}})
    (output / "junction_review.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": features}, separators=(",", ":")), encoding="utf-8")
    tree = STRtree(lines)
    to_plane = Transformer.from_crs(4326, 2272, always_xy=True)
    county = _county_polygon()
    conflict_counts = Counter()
    crosswalk_conflicts = {}
    distances = Counter()
    samples = {}
    with (output / "crosswalk.csv").open(encoding="utf-8", newline="") as source:
        seen = set()
        for row in csv.DictReader(source):
            crn = row["crash_id"]
            if not crn or crn in seen or row["primary_site_id"]:
                raise ValueError("Provisional crosswalk must contain one withheld outcome per CRN")
            seen.add(crn)
            references = [item.rsplit("@", 1)[0] for item in row["candidates"].split(";") if item]
            if (len(references) != int(row["candidate_count"])
                    or (references[0] if references else "") != row["candidate_site_id"]
                    or any(site_id not in sites_by_id for site_id in references)):
                raise ValueError(f"Invalid inventory references: {crn}")
            if row["decision_reason"] == "V6_COORDINATE_CONFLICT_WITHHELD":
                crosswalk_conflicts[crn] = row
            distance = float(row["candidate_distance_m"]) if row["candidate_distance_m"] else None
            band = "NO_CANDIDATE" if distance is None else next(n for n in (10, 25, 50) if distance <= n)
            site_type = "SEGMENT_CANDIDATE" if distance is not None else "UNATTRIBUTED"
            key = (row["crash_year"], row["road_class"], site_type, row["decision_reason"], band)
            distances[key] += 1
            if int(row["candidate_count"]) > 1:
                samples.setdefault("MULTIPLE_NEARBY_LINES", row)
            samples.setdefault(row["decision_reason"], row)
    with (output / "qa_candidate_distances.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["year", "road_class", "site_type", "method_reason", "distance_band_max_m", "crashes"])
        writer.writerows((*key, count) for key, count in sorted(distances.items()))
    with CONFLICTS.open(encoding="utf-8", newline="") as source, (output / "conflict_review.csv").open(
            "w", encoding="utf-8", newline="") as file:
        rows = csv.DictReader(source)
        writer = csv.writer(file)
        writer.writerow([*rows.fieldnames, "route", "segment", "offset",
                         "police_candidate", "police_distance_m", "decimal_candidate", "decimal_distance_m",
                         "police_inside_county", "decimal_inside_county", "boundary_evidence",
                         "disposition", "primary_site_id"])
        for row in rows:
            evidence = crosswalk_conflicts.pop(row["CRASH_CRN"])
            candidates = []
            inside = []
            for lat, lon in (("candidate_police_lat", "candidate_police_lon"), ("state_decimal_lat", "state_decimal_lon")):
                longitude, latitude = float(row[lon]), float(row[lat])
                inside.append(county.covers(Point(longitude, latitude)))
                point = Point(*to_plane.transform(longitude, latitude))
                near = candidate_for_point(point, tree, sites)
                candidates.extend([near[0][1], round(near[0][0], 3)] if near else ["", ""])
            boundary_evidence = {
                (True, True): "BOTH_INSIDE", (False, True): "POLICE_OUTSIDE",
                (True, False): "DECIMAL_OUTSIDE", (False, False): "BOTH_OUTSIDE",
            }[tuple(inside)]
            conflict_counts[boundary_evidence] += 1
            writer.writerow([*row.values(), evidence["route"], evidence["segment"], evidence["offset"],
                             *candidates, *inside, boundary_evidence,
                             "WITHHELD_PENDING_INDEPENDENT_LOCATION_EVIDENCE", ""])
    if crosswalk_conflicts:
        raise ValueError("Conflict register did not reconcile with the crosswalk")
    # Preserve geometry-only crossings as unresolved examples for grade review.
    for i, line in enumerate(lines):
        crossing = sorted(j for j in tree.query(line, predicate="crosses") if j > i)
        if crossing:
            samples["PLANAR_CROSSING_GRADE_UNVERIFIED"] = [sites[i]["site_id"], sites[crossing[0]]["site_id"]]
            break
    samples["MULTI_NODE_GRADE_UNVERIFIED"] = next(
        ([nodes[i]["id"] for i in group] for group in groups if len(group) > 1), [])
    return {"junction_nodes": len(nodes), "junction_clusters": len(groups),
            "multi_node_clusters": sum(len(group) > 1 for group in groups),
            "confirmed_county_crosswalk_intersections": 0, "reconciled_crns": len(seen),
            "conflicts_by_county_boundary_evidence": dict(conflict_counts), "samples": samples}


def review_penndot():
    path = ROOT / ".repro/penndot_roadwaysegments/segments.geojson"
    if not path.exists():
        return {"status": "MISSING_LOCAL_SNAPSHOT"}
    rows = [feature["properties"] for feature in json.loads(path.read_bytes())["features"]]
    keys = defaultdict(list)
    for row in rows:
        keys[(row["CTY_CODE"], row["ST_RT_NO"], row["SEG_NO"])].append(row)
    result = {"sha256": digest(path), "features": len(rows), "key_count": len(keys),
              "nonunique_keys": sum(len(entries) > 1 for entries in keys.values()),
              "direction_values": dict(Counter(row["DIR_IND"] for row in rows)),
              "positive_current_aadt": sum((row["CUR_AADT"] or 0) > 0 for row in rows)}
    dates = sorted(datetime.fromtimestamp(row["GIS_UPDATE_DATE"] / 1000, tz=timezone.utc).date().isoformat()
                   for row in rows if row["GIS_UPDATE_DATE"])
    result["gis_edit_date_range"] = dates[:1] + dates[-1:]
    counts = Counter()
    samples = {}
    with RAW.open(encoding="utf-8", newline="") as file:
        for crash in csv.DictReader(file):
            key = _lrs_key(crash)
            status = "INCOMPLETE_LRS_KEY"
            if key:
                entries = keys.get(key, ())
                status = "NO_CURRENT_KEY" if not entries else "NONUNIQUE_CURRENT_KEY"
                if len(entries) == 1:
                    offset = crash["OFFSET"].strip()
                    if not re.fullmatch(r"\d+(?:\.\d+)?", offset):
                        status = "CURRENT_KEY_WITHOUT_USABLE_OFFSET"
                    elif float(offset) <= (entries[0]["SEG_LNGTH_FEET"] or 0):
                        status = "CURRENT_KEY_OFFSET_IN_RANGE"
                    else:
                        status = "CURRENT_KEY_OFFSET_EXCEEDS_LENGTH"
            counts[(crash["CRASH_YEAR"], status)] += 1
            samples.setdefault(status, crash["CRASH_CRN"])
    result["diagnostic_only_by_year"] = [
        {"year": year, "status": status, "crashes": n} for (year, status), n in sorted(counts.items())
    ]
    result["diagnostic_samples"] = samples
    return result
