"""Build Phase 4 only against an exact approved upstream bundle."""

import csv
import json
import math
import shutil
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from app.road_safety_release import ReleaseUnavailable, digest, verify_release
from road_safety_command import ROOT, write_manifest


def _csv(path):
    with path.open(encoding="utf-8", newline="") as source:
        yield from csv.DictReader(source)


def _write(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _upstream(inputs, approvals, output, kind, required):
    sources = {}
    manifests = {}
    scope = {"county": "Allegheny", "supported_site_years": 0}
    try:
        for upstream in required:
            path = inputs / upstream if inputs else None
            if path and not path.exists() and upstream == "crosswalk" and (inputs / "manifest.json").exists():
                path = inputs
            if path and (path / "manifest.json").exists():
                sources[upstream + "_manifest"] = digest(path / "manifest.json")
            if not path or not approvals:
                raise ReleaseUnavailable(f"Approved {upstream} bundle and ledger required")
            manifest = verify_release(path, approvals, upstream)
            manifests[upstream] = (path, manifest)
            if upstream == "crosswalk":
                scope = manifest["scope"].copy()
                scope["crosswalk_version"] = manifest["version"]
    except ReleaseUnavailable as error:
        output.mkdir(parents=True)
        local_sources = ROOT / ".repro/source_review"
        for path in (
            ROOT / ".repro/penndot_roadwaysegments/segments.geojson",
            ROOT / ".repro/tire_station_sample/sample.json",
            local_sources / "Permanent_Site_Locations.pdf",
            local_sources / "5_Year_Summary_AADT_Permanent_sites.pdf",
            local_sources / "allegheny_permanent_aadt.csv",
        ):
            if path.is_file():
                sources[path.name] = digest(path)
        decision = {"decision": "NO_GO", "reason": str(error), "eligible_site_years": None,
                    "observed_exposure_fraction": None, "estimated_exposure_fraction": None,
                    "missing_exposure_fraction": None, "expected_baseline_scope": []}
        if kind == "exposure" and "allegheny_permanent_aadt.csv" in sources:
            annual = list(_csv(local_sources / "allegheny_permanent_aadt.csv"))
            sample_path = ROOT / ".repro/tire_station_sample/sample.json"
            stations = defaultdict(list)
            if sample_path.is_file():
                for feature in json.loads(sample_path.read_bytes())["features"]:
                    row = feature["attributes"]
                    stations[str(row["PERMANENT_SITE_ID"])].append(row)
            rows = []
            for row in annual:
                candidates = [s for s in stations[row["permanent_site_id"]]
                              if (s["CTY_CODE"], s["ST_RT_NO"], s["SEG_NO"])
                              == (row["county_code"], row["route"], row["segment_2024"])]
                station = candidates[0] if len(candidates) == 1 else {}
                rows.append({**row, "tire_station_id": station.get("STATION_ID", ""),
                             "tire_segment_offset": station.get("SEG_OFFSET", ""),
                             "tire_sample_candidates": len(candidates)})
            _write(output / "station_link_evidence.csv", list(rows[0]), rows)
            decision["unlinked_published_station_years"] = len(rows)
            decision["station_years_with_unique_station_sample_key"] = sum(
                row["tire_sample_candidates"] == 1 for row in rows
            )
        (output / "decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
        write_manifest(output, kind, kind + "-blocked-v1", scope, sources, "PROVISIONAL")
        return None
    return manifests, scope, sources


def _unique(rows, get_key):
    result = {}
    for row in rows:
        key = get_key(row)
        if key in result:
            raise ValueError(f"Duplicate record: {key}")
        result[key] = row
    return result


def _site_year(row):
    return row["site_id"], int(row["year"])


def _artifact(path, manifest, name):
    candidate = path / name
    if manifest["outputs"].get(name) != digest(candidate):
        raise ValueError(f"Artifact does not match the approved manifest: {name}")
    return candidate


def _covers_year(row, year):
    return (date.fromisoformat(row["valid_from"]) <= date(year, 1, 1)
            and date.fromisoformat(row["valid_through"]) >= date(year, 12, 31))


def stage_exposure(output, inputs, approvals):
    checked = _upstream(inputs, approvals, output, "exposure", ("crosswalk",))
    if checked is None:
        return
    manifests, scope, sources = checked
    crosswalk, manifest = manifests["crosswalk"]
    inventory = _unique(_csv(_artifact(crosswalk, manifest, "site_inventory.csv")), lambda row: row["site_id"])
    frames = {}
    for name in ("eligibility.csv", "observation.csv", "linked_annual_aadt.csv"):
        path = inputs / name
        sources[name] = digest(path)
        frames[name] = _unique(_csv(path), _site_year)
    eligible = frames["eligibility.csv"]
    observed = frames["observation.csv"]
    annual = frames["linked_annual_aadt.csv"]
    if not eligible or not observed.keys() <= eligible.keys():
        raise ValueError("The eligibility frame must be nonempty and contain every observed site-year")
    for frame in (eligible, observed, annual):
        for row in frame.values():
            if row["crosswalk_version"] != manifest["version"] or not row["evidence_id"].strip():
                raise ValueError("Each site-year needs the approved crosswalk version and independent evidence")

    counts = Counter()
    seen = set()
    for row in _csv(_artifact(crosswalk, manifest, "crosswalk.csv")):
        crn = row["crash_id"]
        if not crn or crn in seen:
            raise ValueError(f"Invalid or duplicate crash ID: {crn}")
        seen.add(crn)
        site_id = row["primary_site_id"]
        if bool(site_id) != (row["match_status"] == "MATCHED"):
            raise ValueError(f"Assignment and match status disagree: {crn}")
        if site_id:
            key = site_id, int(row["crash_year"])
            if row["reference_version"] != manifest["version"] or key not in eligible:
                raise ValueError(f"Primary crash assignment is outside the eligible version or frame: {crn}")
            counts[key] += 1

    output.mkdir(parents=True)
    panel = []
    coverage = defaultdict(Counter)
    rejected = [{"site_id": s, "year": y, "reason": "OUTSIDE_ELIGIBILITY_FRAME"} for s, y in sorted(annual.keys() - eligible.keys())]
    for site_id, year in sorted(eligible):
        key = site_id, year
        site = inventory[site_id]
        first, last = scope["crash_years"]
        if (site["site_type"] not in {"SEGMENT", "INTERSECTION"}
                or not first <= year <= last or not _covers_year(site, year)
                or not _covers_year(eligible[key], year)):
            raise ValueError(f"Eligibility requires supported site type and full-year effective dates: {key}")
        if key in observed and not _covers_year(observed[key], year):
            raise ValueError(f"Crash observation requires full-year evidence: {key}")
        traffic = annual.get(key)
        aadt = None
        status = "MISSING"
        if traffic:
            try:
                value = float(traffic["aadt"])
            except (TypeError, ValueError):
                value = math.nan
            compatible = (traffic["site_type"] == site["site_type"] and
                          all(traffic[k] == site[k] for k in ("route", "segment", "direction")) and
                          bool(traffic["station_id"].strip()) and
                          traffic["measure"] == ("AADT" if site["site_type"] == "SEGMENT" else "ENTERING_AADT"))
            if not compatible or not math.isfinite(value) or value <= 0 or traffic["quality"] not in {"OBSERVED", "ESTIMATED"}:
                rejected.append({"site_id": site_id, "year": year, "reason": "INCOMPATIBLE_OR_INVALID_EXPOSURE"})
            else:
                status, aadt = traffic["quality"], value
        road_class, site_type = site["road_class"], site["site_type"]
        coverage[(year, road_class, site_type)][status] += 1
        panel.append({"site_id": site_id, "year": year, "road_class": road_class, "site_type": site_type,
                      "attributed_crashes": counts[key], "crash_count": counts[key] if key in observed else None,
                      "observation_status": "OBSERVED" if key in observed else "UNKNOWN",
                      "aadt": aadt, "exposure_status": status,
                      "exposure_evidence": traffic["evidence_id"] if aadt is not None else "",
                      "station_id": traffic["station_id"] if aadt is not None else "",
                      "traffic_measure": traffic["measure"] if aadt is not None else "",
                      "eligibility_evidence": eligible[key]["evidence_id"],
                      "observation_evidence": observed[key]["evidence_id"] if key in observed else "",
                      "crosswalk_version": manifest["version"]})
    _write(output / "site_year_panel.csv", list(panel[0]), panel)
    exposure_rows = []
    for (year, road_class, site_type), tally in sorted(coverage.items()):
        total = sum(tally.values())
        row = {"year": year, "road_class": road_class, "site_type": site_type, "eligible": total}
        for status in ("OBSERVED", "ESTIMATED", "MISSING"):
            row[status.lower()] = tally[status]
            row[status.lower() + "_fraction"] = tally[status] / total
        exposure_rows.append(row)
    _write(output / "coverage.csv", list(exposure_rows[0]), exposure_rows)
    _write(output / "unlinked_exposure.csv", ["site_id", "year", "reason"], rejected)
    _write_decision(output, {"decision": "NO_GO", "reason": "Frequency use requires separate validation and approval",
                             "eligible_site_years": len(panel), "observed_site_years": len(observed),
                             "attributed_crashes": sum(counts.values()),
                             "attributed_crashes_in_unknown_years": sum(n for k, n in counts.items() if k not in observed),
                             "expected_baseline_scope": []})
    write_manifest(output, "exposure", manifest["version"] + "-exposure-v1", scope, sources)


def _write_decision(output, data):
    (output / "decision.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def stage_screening(output, inputs, approvals):
    checked = _upstream(inputs, approvals, output, "concentration", ("crosswalk", "exposure"))
    if checked is None:
        return
    manifests, scope, sources = checked
    crosswalk, manifest = manifests["crosswalk"]
    exposure, panel_manifest = manifests["exposure"]
    if panel_manifest["inputs"].get("crosswalk_manifest") != sources["crosswalk_manifest"]:
        raise ValueError("The approved exposure panel refers to a different crosswalk")
    inventory = _unique(_csv(_artifact(crosswalk, manifest, "site_inventory.csv")), lambda row: row["site_id"])
    panel = list(_csv(_artifact(exposure, panel_manifest, "site_year_panel.csv")))
    observed = _unique((r for r in panel if r["observation_status"] == "OBSERVED"), _site_year)
    if not observed:
        raise ValueError("Historical screening requires independently observed site-years")
    annual = defaultdict(Counter)
    by_site = defaultdict(list)
    by_class = defaultdict(Counter)
    by_type = defaultdict(Counter)
    for row in panel:
        site_id, year = _site_year(row)
        for tally in (annual[year], by_class[row["road_class"]], by_type[row["site_type"]]):
            tally["eligible_site_years"] += 1
            if (site_id, year) in observed:
                tally["observed_site_years"] += 1
                tally["crashes"] += int(row["crash_count"])
        if (site_id, year) in observed:
            by_site[site_id].append(row)
    rows = []
    for site_id, site_years in sorted(by_site.items()):
        site = inventory[site_id]
        crashes = sum(int(r["crash_count"]) for r in site_years)
        length_km = None
        years = len(site_years)
        if site["site_type"] == "SEGMENT":
            length_km = float(site["length_m"]) / 1000
            if not math.isfinite(length_km) or length_km <= 0:
                raise ValueError(f"Invalid geometry-derived segment length: {site_id}")
        rows.append({"site_id": site_id, "road_class": site["road_class"], "site_type": site["site_type"],
                     "observed_years": "|".join(str(r["year"]) for r in site_years), "crashes": crashes,
                     "observed_site_years": years, "segment_length_km": length_km,
                     "screening_measure": "CRASHES_PER_KM_YEAR" if length_km else "CRASHES_PER_INTERSECTION_YEAR",
                     "screening_value": crashes / (length_km * years if length_km else years)})
    output.mkdir(parents=True)
    _write(output / "historical_crash_concentration.csv", list(rows[0]), rows)
    for name, key, tallies in (("year", "crash_year", annual), ("road_class", "road_class", by_class),
                               ("site_type", "site_type", by_type)):
        fields = [key, "eligible_site_years", "observed_site_years", "crashes"]
        _write(output / f"historical_concentration_by_{name}.csv", fields,
               ({key: value, **{f: tally[f] for f in fields[1:]}} for value, tally in sorted(tallies.items())))
    _write_decision(output, {"decision": "HISTORICAL_SCREENING_ONLY", "eligible_site_years": len(panel),
                             "observed_site_years": len(observed), "expected_baseline_scope": []})
    scope["observed_years"] = sorted({year for _, year in observed})
    write_manifest(output, "concentration", manifest["version"] + "-screening-v1", scope, sources)


def stage_visualizations(output, inputs, approvals):
    checked = _upstream(inputs, approvals, output, "visualizations", ("crosswalk", "concentration"))
    if checked is None:
        return
    manifests, scope, sources = checked
    crosswalk, manifest = manifests["crosswalk"]
    concentration, screening = manifests["concentration"]
    if screening["inputs"].get("crosswalk_manifest") != sources["crosswalk_manifest"]:
        raise ValueError("The approved screening bundle refers to a different crosswalk")
    name = "historical_crash_concentration.csv"
    sites = _unique(_csv(_artifact(concentration, screening, name)), lambda row: row["site_id"])
    network = json.loads(_artifact(crosswalk, manifest, "network.geojson").read_bytes())
    features = []
    for feature in network["features"]:
        site_id = feature["properties"]["site_id"]
        if site_id in sites:
            features.append({**feature, "properties": sites.pop(site_id)})
    if sites:
        raise ValueError("Approved screening includes sites missing from the approved map")
    output.mkdir(parents=True)
    for name in screening["outputs"]:
        if name.startswith("historical_"):
            shutil.copyfile(_artifact(concentration, screening, name), output / name)
    (output / "top_concentration_sites_geographic.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": features}), encoding="utf-8")
    write_manifest(output, "visualizations", manifest["version"] + "-visualizations-v1", screening["scope"], sources)
