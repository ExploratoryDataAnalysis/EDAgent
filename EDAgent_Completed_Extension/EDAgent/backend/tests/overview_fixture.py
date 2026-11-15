"""Invented D7 data for API and browser tests. Never mount it in staging."""

import csv
import hashlib
import json
from pathlib import Path

from app.api.v1.endpoints import overview
from app.road_safety_release import digest

FIXTURE_VERSION = "fixture-d7-1"


def write_fixture(root: Path, *, large_grid=False, partial=False):
    path = root / overview.KIND
    path.mkdir(parents=True)

    def period(grain, start, end):
        return dict(period_grain=grain, period_start=start, period_end=end)

    periods = [period("county", 2004, 2024), period("era", 2004, 2015), period("era", 2016, 2024),
               period("year", 2015, 2015), period("year", 2024, 2024)]
    county = [dict(p, reported_crashes=24 if p["period_grain"] == "county" else 12,
                   known_severity_crashes=9, unknown_severity_crashes=3, fatal_crashes=1,
                   fatal_percent_of_known=100 / 9,
                   serious_fatal_crashes=2 if p["period_start"] >= 2016 else None,
                   serious_fatal_percent_of_known=200 / 9 if p["period_start"] >= 2016 else None,
                   known_severity_percent_of_reported=75) for p in periods]
    county[0].update(known_severity_crashes=18, unknown_severity_crashes=6, fatal_crashes=2)
    coordinates = [dict(p, reported_crashes=24, usable_decimal_crashes=22,
                        missing_decimal_pair_crashes=2, invalid_decimal_pair_crashes=0,
                        placeholder_decimal_pair_crashes=0, unusable_decimal_crashes=2,
                        outside_county_crashes=2, mapped_crashes=20,
                        mapped_percent_of_reported=100 * 20 / 24, outside_percent_of_usable=200 / 22)
                   for p in periods]
    for row in coordinates[1:]:
        row.update(reported_crashes=12, usable_decimal_crashes=11, missing_decimal_pair_crashes=1,
                   unusable_decimal_crashes=1, outside_county_crashes=1, mapped_crashes=10)
    severity = [dict(p, severity_group=group, severity_code=code, crashes=n,
                     denominator_population=pop, denominator_crashes=denom,
                     percent_of_denominator=100 * n / denom if denom else None)
                for p in periods for group, code, n, pop, denom in (
                    ("Fatal", 1, 2, "known severity", 18) if p["period_grain"] == "county" else
                    ("Fatal", 1, 1, "known severity", 9),
                    ("Serious injury", 2, 1, "known severity", 9) if p["period_grain"] != "county" else
                    ("Serious injury", 2, 2, None, None),
                    ("Injury severity unknown", 8, 6, "all reports", 24) if p["period_grain"] == "county" else
                    ("Injury severity unknown", 8, 3, "all reports", 12),
                    ("Missing severity", None, 0, "all reports", 24 if p["period_grain"] == "county" else 12),
                    ("Property damage only", 0, 14, "known severity", 18) if p["period_grain"] == "county" else
                    ("Property damage only", 0, 7, "known severity", 9),
                )]
    fields = [dict(period_start=year, period_end=year, metric_id=field, covered_crashes=n,
                   excluded_crashes=12 - n, reported_crashes=12, covered_percent_of_reported=100 * n / 12)
              for year, hour, light in ((2015, 10, 11), (2024, 1, 0))
              for field, n in (("valid_hour", hour), ("nonmissing_illumination", light))]
    if partial:
        fields = [row for row in fields if row["period_start"] != 2024 or row["metric_id"] != "nonmissing_illumination"]
    tables = {
        "county_periods": county, "coordinate_coverage": coordinates, "severity_composition": severity,
        "field_coverage_by_year": fields,
        "source_missingness": [dict(source_field=field, missing_crashes=n, reported_crashes=24,
                                    missing_percent_of_reported=100 * n / 24)
                               for field, n in (("HOUR_OF_DAY", 12), ("ILLUMINATION", 13))],
        "historical_grid": [dict(lat_bin=40.45, lon_bin=-80, mapped_crashes=20, years_observed=2)],
        "severity_associations": [
            dict(feature=feature, period_start=2016, period_end=2023, tested_crashes=7,
                 known_severity_crashes_in_period=7, reported_crashes_in_period=10, tested_levels=2,
                 fdr_bh_q=q, fdr_bh_q_underflow=q is None, pooled_source_levels=pooled,
                 min_expected_cell=1.5, cramers_v=v)
            for feature, v, q, pooled in (("TIME_PERIOD", 0.1, 0.125, None), ("COLLISION_LABEL", 0.45, None, "Unknown, Backing"))
        ],
        "findings": [dict(finding_id=1, finding="Fixture review note", period_start=2022, period_end=2024,
                          population="Invented reports", review_state="REVIEW_ONLY", narrative="Synthetic test fixture.")],
    }
    if large_grid:
        # Match the candidate's row count with invented interior cells for browser timing.
        cells = [dict(lat_bin=(40201 + lat) / 1000, lon_bin=(-80199 + lon) / 1000,
                      mapped_crashes=1 + (lat + lon) % 12, years_observed=1)
                 for lat in range(199) for lon in range(199)][:38332]
        tables["historical_grid"] = cells
        mapped = sum(cell["mapped_crashes"] for cell in cells)
        coordinates[0].update(reported_crashes=mapped + 4, usable_decimal_crashes=mapped + 2,
                              mapped_crashes=mapped, mapped_percent_of_reported=100 * mapped / (mapped + 4))
    for table, rows in tables.items():
        (path / f"{table}.json").write_text(json.dumps(rows), encoding="utf-8")
        with (path / f"{table}.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, rows[0])
            writer.writeheader()
            writer.writerows(rows)
    # The eastern boundary intersects the occupied cell so clipping can be exercised.
    boundary = {"type": "Feature", "properties": {"geoid": "42003", "vintage": 2024},
                "geometry": {"type": "Polygon", "coordinates": [[[-80.2, 40.2], [-79.8, 40.2], [-79.8, 40.44],
                    [-79.9998, 40.44], [-79.9998, 40.46], [-79.8, 40.46], [-79.8, 40.6], [-80.2, 40.6], [-80.2, 40.2]]]}}
    (path / "county_boundary.geojson").write_text(json.dumps(boundary), encoding="utf-8")
    (path / "county_grid.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 200">'
        '<rect x="12" y="12" width="456" height="176" fill="#dbeafe" stroke="#1e40af"/>'
        '<rect x="215" y="110" width="2" height="2" fill="#1e40af"/>'
        '<text x="24" y="45" fill="#1e3a8a">Synthetic grid fixture</text></svg>', encoding="utf-8",
    )
    (path / "descriptive_release_data_dictionary.md").write_text("# Synthetic D7 test fixture\n", encoding="utf-8")
    manifest = dict(kind=overview.KIND, version=FIXTURE_VERSION, schema_version=1,
                    status="REVIEW_CANDIDATE", approval=None, run_id="synthetic-fixture",
                    scope=dict(county="Allegheny County, Pennsylvania (synthetic fixture)", geoid="42003",
                               period_start=2004, period_end=2024, claim_class="HISTORICAL_DESCRIPTIVE_AGGREGATES",
                               PRIMARY_SITE_ASSIGNMENTS_ACCEPTED=0),
                    grid=dict(crs="EPSG:4326", side_degrees=0.001, county_bbox_wsen=[-80.2, 40.2, -79.8, 40.6],
                              mapped_crashes=coordinates[0]["mapped_crashes"], occupied_cells=len(tables["historical_grid"])),
                    inputs={"invented-test-rows": hashlib.sha256(b"synthetic").hexdigest()},
                    tables={name: {"rows": len(rows)} for name, rows in tables.items()},
                    outputs={file.name: digest(file) for file in path.iterdir()})
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return path


def write_decision(ledger, manifest_sha256, decision="APPROVED"):
    ledger.write_text(json.dumps({overview.KIND: dict(decision=decision, reviewer="SYNTHETIC TEST FIXTURE",
                                                     date="2026-11-13", manifest_sha256=manifest_sha256)}),
                      encoding="utf-8")
