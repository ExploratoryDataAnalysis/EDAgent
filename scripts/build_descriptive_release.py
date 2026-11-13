"""Build the v3 D7 aggregate candidate from the pinned v6 evidence."""

import csv
import json
import shutil
from collections import Counter, defaultdict
from math import isclose

from road_safety_command import ROOT, digest, run

KIND = "descriptive_release"
VERSION = "v3-d7-1"
STATUS = "REVIEW_CANDIDATE"
FROZEN = ROOT / "analysis/outputs"
PHASE3 = ROOT / ".repro/v3-phase3-verified-a"
PHASE3_SHA = "c5e8b9a27a92fc65067ea6775b42331f81b70f409242782f22abbc036fd54ddf"
YEARS = range(2004, 2025)
SEVERITY = {
    "0": "Property damage only", "1": "Fatal", "2": "Serious injury",
    "3": "Minor injury", "4": "Possible injury", "8": "Injury severity unknown",
    "9": "Injury status unknown", "missing": "Missing severity", "other": "Unrecognised severity",
}
KNOWN = tuple("01234")
SOURCE_HASHES = {
    "run_manifest.json": "8bdedd5347e0942f49eae2465c7e7f261260476a7fead09b3315dfa67747400f",
    "eda_summary/severity_by_year.csv": "71203c297fcdd845a7e995a910d8f1934999ec141f7913a6da2ed0074e3a3e3f",
    "eda_summary/injury_reconciliation.csv": "eea397540b1da57baec0b7de6a4f6f341525dd8765b7efe93730224c35a005bb",
    "eda_summary/source_missingness.csv": "32a0e799028d77c24858f453619d7fd1d8a3cbc88dc3cd22510ab859bc4b067a",
    "eda_summary/findings_review.csv": "dc4bbb1bf5f0f4841570a1192ba8669aa52486082a687c528dcd90c33d9a6960",
    "eda_summary/association_tests.csv": "f4e4022025ddf787fa939887893263a84f5c14103f9b1f32f4c52bc85d34424c",
    "eda_summary/association_pooling_audit.csv": "df0484a730cb970619c81fd10f3b31a1ee2cd5514968899f61862e0109a46546",
    "model_metrics/severity_model_comparison.csv": "de54733c03599971cf6cdae07e79c41969a0ea66516b1e006e12f133799d4cbc",
}
GUIDE = ROOT / "docs/descriptive_release_data_dictionary.md"
NOTEBOOK = ROOT / "analysis/EDA_v6.ipynb"
GRID_RESOLUTION = 0.001
INVENTORY = "county_coordinate_inventory_by_year.csv"
COVERAGE_FIELDS = ("state_route_decimal", "missing_decimal_pair", "invalid_decimal_pair",
                   "decimal_placeholder", "outside_county", "inside_county")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def percent(numerator, denominator):
    return 100 * numerator / denominator if denominator else None


def period(start, end):
    return {"period_start": start, "period_end": end}


def json_file(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")
                     .encode("utf-8"))


def write_table(output, name, data):
    with (output / f"{name}.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(data)
    json_file(output / f"{name}.json", data)


def severity_group(value):
    value = value.strip()
    if value in SEVERITY and value.isdigit():
        return value
    return "other" if value else "missing"


def summarize_raw(raw, county=None):
    """Read the source once. Recheck the polygon only when Phase 3 is absent."""
    from phase3_diagnostics import decimal_point, rows
    from shapely.geometry import Point
    from shapely.prepared import prep

    prepared = prep(county) if county is not None else None
    seen = set()
    severity, fields, locations = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    for row in rows(raw):
        year, crn = int(row["CRASH_YEAR"]), row["CRASH_CRN"]
        require(crn and crn not in seen and year in YEARS, "Duplicate CRN or unexpected source period")
        seen.add(crn)
        severity[year][severity_group(row["MAX_SEVERITY_LEVEL"])] += 1
        hour = row["HOUR_OF_DAY"]
        fields[year]["valid_hour"] += bool(hour and 0 <= float(hour) <= 23)
        fields[year]["nonmissing_illumination"] += bool(row["ILLUMINATION"])
        if prepared is not None:
            status, point = decimal_point(row)
            locations[year][status] += 1
            if point is not None:
                key = "inside_county" if prepared.covers(Point(*point)) else "outside_county"
                locations[year][key] += 1
    require(set(severity) == set(YEARS), "Source years are incomplete")
    return severity, fields, locations


def severity_summary(counts, start, end):
    reported = counts.total()
    known = sum(counts[code] for code in KNOWN)
    fatal = counts["1"]
    serious_fatal = fatal + counts["2"]
    return {**period(start, end), "reported_crashes": reported, "known_severity_crashes": known,
            "unknown_severity_crashes": reported - known, "fatal_crashes": fatal,
            "serious_fatal_crashes": serious_fatal if start >= 2016 else None,
            "known_severity_percent_of_reported": percent(known, reported),
            "fatal_percent_of_known": percent(fatal, known),
            "serious_fatal_percent_of_known": percent(serious_fatal, known) if start >= 2016 else None}


def check_annual_severity(summary, counts, frozen):
    observed = (summary["reported_crashes"], summary["known_severity_crashes"], counts["1"],
                counts["1"] + counts["2"])
    expected = tuple(int(frozen[key]) for key in (
        "crash_records", "known_severity_records", "fatal_records", "serious_fatal_records"))
    require(observed == expected, f"Severity counts disagree for {frozen['CRASH_YEAR']}")
    for key, source_key in (("known_severity_percent_of_reported", "known_severity_percent"),
                            ("fatal_percent_of_known", "fatal_percent_of_known"),
                            ("serious_fatal_percent_of_known", "serious_fatal_percent_of_known")):
        value, source = summary[key], frozen[source_key]
        matches = source == "" if value is None else bool(source) and isclose(value, float(source))
        require(matches, f"Severity percentage {key} disagrees for {frozen['CRASH_YEAR']}")


def coordinate_summary(counts, reported, start, end):
    usable, outside, mapped = (counts[key] for key in
                               ("state_route_decimal", "outside_county", "inside_county"))
    missing, invalid, placeholder = (counts[key] for key in
                                     ("missing_decimal_pair", "invalid_decimal_pair", "decimal_placeholder"))
    unusable = missing + invalid + placeholder
    require(reported == usable + unusable and usable == outside + mapped,
            f"Coordinate populations disagree for {start}–{end}")
    return {**period(start, end), "reported_crashes": reported, "usable_decimal_crashes": usable,
            "missing_decimal_pair_crashes": missing, "invalid_decimal_pair_crashes": invalid,
            "placeholder_decimal_pair_crashes": placeholder, "unusable_decimal_crashes": unusable,
            "outside_county_crashes": outside, "mapped_crashes": mapped,
            "mapped_percent_of_reported": percent(mapped, reported),
            "outside_percent_of_usable": percent(outside, usable)}


def staged_sources(stage):
    from phase3_diagnostics import checked_digest

    manifest_path = stage / "manifest.json"
    inputs = {"phase3/manifest.json": checked_digest(manifest_path, PHASE3_SHA)}
    manifest = json.loads(manifest_path.read_bytes())
    require(manifest["status"] == "PROVISIONAL" and manifest["scope"]["PRIMARY_SITE_ASSIGNMENTS_ACCEPTED"] == 0,
            "Phase 3 diagnostic state changed")
    for name in (INVENTORY, "county_grid.svg"):
        inputs[f"phase3/{name}"] = checked_digest(stage / name, manifest["outputs"][name])
    return inputs


def grid_table(mapped):
    from phase3_diagnostics import SPATIAL, rows

    counts, years = Counter(), defaultdict(set)
    points_by_year = Counter()
    seen = set()
    for row in rows(SPATIAL / "county_points_review.csv"):
        crn = row["CRASH_CRN"]
        require(crn and crn not in seen and row["LOCATION_SOURCE"] == "state_route_decimal",
                "Invalid county point record")
        seen.add(crn)
        year = int(row["CRASH_YEAR"])
        cell = (round(float(row["LAT"]) * 1000) / 1000, round(float(row["LON"]) * 1000) / 1000)
        counts[cell] += 1
        years[cell].add(year)
        points_by_year[year] += 1
    require(points_by_year == mapped, "County point counts disagree with the coordinate ledger")
    frozen = list(rows(SPATIAL / "historical_grid_screening.csv"))
    expected = {(float(row["LAT_BIN"]), float(row["LON_BIN"])):
                (int(row["crash_count"]), int(row["years_observed"])) for row in frozen}
    require(len(frozen) == len(expected) == 38332
            and expected == {cell: (n, len(years[cell])) for cell, n in counts.items()},
            "County grid disagrees with the frozen export")
    table = [{"lat_bin": lat, "lon_bin": lon, "mapped_crashes": n, "years_observed": observed}
             for (lat, lon), (n, observed) in sorted(expected.items())]
    return table, counts


def field_missingness(reported):
    from phase3_diagnostics import rows

    table = []
    for row in rows(FROZEN / "eda_summary/source_missingness.csv"):
        missing = int(row["missing_count"])
        value = percent(missing, reported)
        require(0 <= missing <= reported and isclose(value, float(row["missing_percent"])),
                f"Source missingness disagrees for {row['']}")
        table.append({"source_field": row[""], "missing_crashes": missing,
                      "reported_crashes": reported, "missing_percent_of_reported": value})
    return table


def findings(known, coverage, association_population, field_coverage, manifest):
    from phase3_diagnostics import rows

    ledger = list(rows(FROZEN / "eda_summary/findings_review.csv"))
    reported, mapped = coverage["reported_crashes"], coverage["mapped_crashes"]
    require(manifest["codebook_team_attested"] is False and manifest["police_gps_format_verified"] is False
            and manifest["conditional_site_frequency_gate"] is False, "Frozen research gates changed")
    descriptions = [
        (2004, 2024, "All source reports", STATUS,
         f"The frozen source has {reported:,} unique crash reports. "
         "The extract covers police-reported crashes and contains no travel-exposure denominator."),
        (2004, 2024, "All source reports", STATUS,
         f"{known:,} of {reported:,} reports have severity codes 0–4 ({percent(known, reported):.2f}%). "
         "The 2016 injury standard separates the injury-severity reporting eras."),
        (2024, 2024, "2024 source reports", STATUS,
         f"{field_coverage['valid_hour']:,} of {field_coverage['reported']:,} reports have a valid hour "
         "and zero have a nonmissing illumination value. Withhold full-year hour and lighting comparisons."),
        (2018, 2019, "Weather and road-surface code transition", "UNVERIFIED",
         "The assumed weather and road-surface code transition remains unverified. "
         "These groupings are excluded from formal comparisons."),
        (2016, 2023, "Known-severity source reports", STATUS,
         f"Four categorical tests used {association_population:,} known-severity reports. "
         "Collision type had the largest Cramér's V. Consult the pooling and test denominators."),
        (2004, 2024, "Source reports and polygon-screened state decimals", STATUS,
         f"{mapped:,} of {reported:,} reports map within the county polygon. "
         "Grid counts describe historical concentration. "
         f"Of {manifest['candidate_dms_pairs_n']:,} diagnostic police/state pairs, "
         f"{manifest['candidate_dms_disagreements_over_500m_n']:,} differ by more than 500 m. "
         "Police coordinate encoding remains unverified."),
        (2022, 2024, "Known-severity test reports", "REVIEW_ONLY",
         "Frozen severity evaluation uses 27,697 known-severity reports from 2022–2024. "
         "The test interval was previously examined. Model scores and inference are withheld."),
        (2004, 2024, "v3 site-analysis scope", "OUT_OF_SCOPE_NO_GO",
         "Site screening, site ranks, frequency and Empirical Bayes models, expected crash counts "
         "and real-site treatment benefits are outside the v3 release scope."),
    ]
    return [{"finding_id": i, "finding": row["finding"], **period(start, end), "population": population,
             "review_state": state, "narrative": narrative}
            for i, (row, (start, end, population, state, narrative))
            in enumerate(zip(ledger, descriptions, strict=True), 1)]


def association_table(known, period_reported, all_reported):
    from phase3_diagnostics import rows

    pooling = {row["feature"]: row["pooled_original_levels"] or None
               for row in rows(FROZEN / "eda_summary/association_pooling_audit.csv") if row["reason"] == "valid"}
    table = []
    for row in rows(FROZEN / "eda_summary/association_tests.csv"):
        feature = row["feature"]
        tested = int(row["tested_known_severity_n"])
        require(row["analysis_years"] == "2016–2023" and tested == known
                and int(row["known_severity_population_n"]) == known
                and round(percent(tested, all_reported), 2) == float(row["overall_source_fraction_percent"])
                and percent(tested, known) == float(row["within_population_coverage_percent"]),
                f"Association population disagrees for {feature}")
        table.append({"feature": feature, **period(2016, 2023), "tested_crashes": tested,
                      "known_severity_crashes_in_period": known,
                      "reported_crashes_in_period": period_reported,
                      "tested_percent_of_known_in_period": percent(tested, known),
                      "tested_percent_of_reported_in_period": percent(tested, period_reported),
                      "reported_crashes_in_full_extract": all_reported,
                      "tested_percent_of_full_extract": percent(tested, all_reported),
                      "tested_levels": int(row["tested_levels"]), "pooled_source_levels": pooling[feature],
                      "min_expected_cell": float(row["min_expected_cell"]), "cramers_v": float(row["cramers_v"]),
                      "fdr_bh_q": float(row["fdr_bh_q"]) or None,
                      "fdr_bh_q_underflow": float(row["fdr_bh_q"]) == 0})
    require(len(table) == 4 and set(pooling) == {row["feature"] for row in table},
            "Association tests disagree with the pooling audit")
    return table


def stage(output, source_directory, _approvals):
    from phase3_diagnostics import (BOUNDARY_SHA256, COUNTY_BOUNDARY, FROZEN as SPATIAL_HASHES,
                                    SPATIAL, checked_digest, draw_maps, rows)
    from review_roadway_sources import _county_polygon
    from shapely.geometry import mapping

    sources = {(FROZEN / name).relative_to(ROOT).as_posix(): checked_digest(FROZEN / name, sha)
               for name, sha in SOURCE_HASHES.items()}
    for name in ("coordinate_coverage_by_year.csv", "county_points_review.csv", "historical_grid_screening.csv"):
        path = SPATIAL / name
        sources[path.relative_to(ROOT).as_posix()] = checked_digest(path, SPATIAL_HASHES[name])
    sources[COUNTY_BOUNDARY.relative_to(ROOT).as_posix()] = checked_digest(COUNTY_BOUNDARY, BOUNDARY_SHA256)
    sources[NOTEBOOK.relative_to(ROOT).as_posix()] = checked_digest(
        NOTEBOOK, "bdb7101c9fc017a68690506fd8cfdec579623b028563f287202ed54e6e324064")
    manifest = json.loads((FROZEN / "run_manifest.json").read_bytes())
    source = manifest["data"]
    raw = ROOT / "data/raw" / source["filename"]
    sources[raw.relative_to(ROOT).as_posix()] = checked_digest(raw, source["sha256"])
    guide = GUIDE.read_text(encoding="utf-8")
    county = _county_polygon()
    upstream = source_directory or PHASE3
    use_stage = source_directory is not None or upstream.exists()
    if use_stage:
        sources.update(staged_sources(upstream))
    severity, fields, locations = summarize_raw(raw, None if use_stage else county)
    if use_stage:
        for row in rows(upstream / INVENTORY):
            year = int(row["year"])
            require(sum(severity[year].values()) == int(row["raw_crns"]),
                    f"Phase 3 reported population disagrees for {year}")
            locations[year].update({key: int(row[key]) for key in COVERAGE_FIELDS})

    annual = list(rows(FROZEN / "eda_summary/severity_by_year.csv"))
    require([int(row["CRASH_YEAR"]) for row in annual] == list(YEARS), "Frozen severity period disagrees")
    frozen_coverage = {(int(row["CRASH_YEAR"]), row["LOCATION_SOURCE"]): int(row["crashes"])
                       for row in rows(SPATIAL / "coordinate_coverage_by_year.csv")}
    for year, frozen in zip(YEARS, annual, strict=True):
        check_annual_severity(severity_summary(severity[year], year, year), severity[year], frozen)
        require(locations[year]["state_route_decimal"] == frozen_coverage[year, "state_route_decimal"]
                and sum(severity[year].values()) - locations[year]["state_route_decimal"]
                == frozen_coverage[year, "unavailable_or_ambiguous"],
                f"Frozen coordinate eligibility disagrees for {year}")

    period_groups = [(2004, 2024, "county"), (2004, 2015, "era"), (2016, 2024, "era")]
    period_groups += [(year, year, "year") for year in YEARS]
    summaries, composition, coverage, field_coverage = [], [], [], []
    for start, end, grain in period_groups:
        years = range(start, end + 1)
        counts = sum((severity[year] for year in years), Counter())
        summary = severity_summary(counts, start, end)
        reported, known = summary["reported_crashes"], summary["known_severity_crashes"]
        summaries.append({"period_grain": grain, **summary})
        coverage.append({"period_grain": grain, **coordinate_summary(
            sum((locations[year] for year in years), Counter()), reported, start, end)})
        for code, label in SEVERITY.items():
            # Injury-class percentages are defined within a coding era.
            denominator = known if code in KNOWN else reported
            if grain == "county" and code in ("2", "3", "4"):
                denominator = None
            population = "known severity" if code in KNOWN else "all reports"
            composition.append({"period_grain": grain, **period(start, end), "severity_group": label,
                                "severity_code": int(code) if code.isdigit() else None,
                                "crashes": counts[code], "denominator_crashes": denominator,
                                "denominator_population": population if denominator is not None else None,
                                "percent_of_denominator": percent(counts[code], denominator)})
        if grain == "year":
            for field, n in fields[start].items():
                field_coverage.append({**period(start, end), "metric_id": field, "covered_crashes": n,
                                       "excluded_crashes": reported - n, "reported_crashes": reported,
                                       "covered_percent_of_reported": percent(n, reported)})

    reported = summaries[0]["reported_crashes"]
    require((source["first_year"], source["last_year"], source["rows"], reported) == (2004, 2024, 248810, 248810)
            and coverage[0]["mapped_crashes"] == 238281 and coverage[0]["outside_county_crashes"] == 275
            and coverage[0]["unusable_decimal_crashes"] == 10254
            and summaries[0]["known_severity_crashes"] == 205544
            and (fields[2024]["valid_hour"], fields[2024]["nonmissing_illumination"]) == (387, 0),
            "County totals or 2024 coverage disagree with the frozen findings")
    grid, grid_counts = grid_table(Counter({year: locations[year]["inside_county"] for year in YEARS}))
    missingness = field_missingness(reported)
    require(len(missingness) == source["columns"], "Source missingness field inventory disagrees")
    association_counts = sum((severity[year] for year in range(2016, 2024)), Counter())
    association_known = sum(association_counts[code] for code in KNOWN)
    # The frozen association CSV's overall fraction uses the full 2004–2024 extract.
    associations = association_table(association_known, association_counts.total(), reported)
    model_counts = sum((severity[year] for year in range(2022, 2025)), Counter())
    model_known = sum(model_counts[code] for code in KNOWN)
    model_rows = rows(FROZEN / "model_metrics/severity_model_comparison.csv")
    require(model_known == 27697 and all(
        int(row["test_records"]) == model_known
        and isclose(float(row["test_prevalence_percent"]), percent(model_counts["1"] + model_counts["2"], model_known))
        for row in model_rows), "Frozen model test population disagrees")
    notes = findings(summaries[0]["known_severity_crashes"], coverage[0], association_known,
                     {**fields[2024], "reported": summaries[-1]["reported_crashes"]}, manifest)

    output.mkdir(parents=True)
    tables = {"county_periods": summaries, "severity_composition": composition,
              "coordinate_coverage": coverage, "field_coverage_by_year": field_coverage,
              "source_missingness": missingness, "historical_grid": grid,
              "severity_associations": associations, "findings": notes}
    for name, data in tables.items():
        write_table(output, name, data)
    (output / GUIDE.name).write_bytes(guide.encode("utf-8"))
    json_file(output / "county_boundary.geojson", {
        "type": "Feature", "properties": {"geoid": "42003", "vintage": 2024}, "geometry": mapping(county)})
    if use_stage:
        shutil.copyfile(upstream / "county_grid.svg", output / "county_grid.svg")
    else:
        draw_maps(output, county, grid_counts)

    json_file(output / "manifest.json", {
        "kind": KIND, "version": VERSION, "schema_version": 1, "status": STATUS, "approval": None,
        "scope": {"county": "Allegheny County, Pennsylvania", "geoid": "42003", **period(2004, 2024),
                  "claim_class": "HISTORICAL_DESCRIPTIVE_AGGREGATES", "PRIMARY_SITE_ASSIGNMENTS_ACCEPTED": 0},
        "run_id": f"v6/{manifest['notebook_version']}/{manifest['generated_utc']}",
        "frozen_run_review_status": manifest["review_status"],
        "reproduce": "python scripts/build_descriptive_release.py --stage .repro/v3-phase4-verified-a/descriptive_release",
        "phase3_geography": "verified staging artifacts" if use_stage else "frozen points and rebuilt coverage",
        "tables": {name: {"rows": len(data), "review_state": STATUS} for name, data in tables.items()},
        "grid": {"crs": "EPSG:4326", "side_degrees": GRID_RESOLUTION, "county_bbox_wsen": county.bounds,
                 "mapped_crashes": coverage[0]["mapped_crashes"], "occupied_cells": len(grid),
                 "lat_bin_range": [min(row["lat_bin"] for row in grid), max(row["lat_bin"] for row in grid)],
                 "lon_bin_range": [min(row["lon_bin"] for row in grid), max(row["lon_bin"] for row in grid)]},
        "data_dictionary": GUIDE.name,
        "inputs": sources,
        "outputs": {path.name: digest(path) for path in sorted(output.iterdir())},
    })


if __name__ == "__main__":
    run(KIND, stage)
