"""Metadata for the eight frozen D7 tables. The JSON rows remain verbatim."""

SEVERITY_BREAK = "SEVERITY_CODING_BREAK_2016"
LOW_HOUR = "LOW_2024_HOUR_COVERAGE"
NO_LIGHT = "NO_2024_ILLUMINATION_COVERAGE"
CAVEATS = {
    SEVERITY_BREAK: "Use separate injury-composition eras, 2004–2015 and 2016–2024. The combined serious/fatal measure starts in 2016.",
    LOW_HOUR: "Sparse 2024 recording requires withholding hour-of-day distributions and comparisons for 2024.",
    NO_LIGHT: "No 2024 reports have populated illumination. Withhold lighting distributions and comparisons for 2024.",
    "HOUR_HEAPING": "Earlier hours show a recorded 02:00 spike and whole- and half-hour heaping.",
    "GRID_CONCENTRATION": "Historical concentration of reported crashes in 0.001° cells clipped to the 2024 county boundary. Missing cells carry no inferred counts. Travel exposure is unmeasured.",
}
PERIOD_KEY = ("period_grain", "period_start", "period_end")
TABLES = {
    "county_periods": (PERIOD_KEY, "All reports in the period"),
    "severity_composition": ((*PERIOD_KEY, "severity_group"), "Reports by recorded severity group"),
    "coordinate_coverage": (PERIOD_KEY, "All reports in the period, with county polygon screening"),
    "field_coverage_by_year": (("period_start", "metric_id"), "All reports in the year"),
    "source_missingness": (("source_field",), "All reports in the county extract"),
    "historical_grid": (("lat_bin", "lon_bin"), "Polygon-screened mapped reports in occupied cells"),
    "severity_associations": (("feature",), "Known-severity reports tested in 2016–2023"),
    "findings": (("finding_id",), "Population identified by each finding"),
}
# Each denominator names the population behind the ratio. These differ within tables.
RATIOS = {
    "known_severity_percent_of_reported": ("known_severity_crashes", "reported_crashes", "All reports in the period"),
    "fatal_percent_of_known": ("fatal_crashes", "known_severity_crashes", "Reports with severity codes 0–4"),
    "serious_fatal_percent_of_known": ("serious_fatal_crashes", "known_severity_crashes", "Reports with severity codes 0–4"),
    "percent_of_denominator": ("crashes", "denominator_crashes", None),
    "mapped_percent_of_reported": ("mapped_crashes", "reported_crashes", "All reports in the period"),
    "outside_percent_of_usable": ("outside_county_crashes", "usable_decimal_crashes", "Reports with usable decimal pairs"),
    "covered_percent_of_reported": ("covered_crashes", "reported_crashes", "All reports in the year"),
    "missing_percent_of_reported": ("missing_crashes", "reported_crashes", "All reports in the county extract"),
    "tested_percent_of_known_in_period": ("tested_crashes", "known_severity_crashes_in_period", "In-period known-severity reports"),
    "tested_percent_of_reported_in_period": ("tested_crashes", "reported_crashes_in_period", "All in-period reports"),
    "tested_percent_of_full_extract": ("tested_crashes", "reported_crashes_in_full_extract", "All reports in the full extract"),
}


def caveats(table, row):
    if table in ("county_periods", "severity_composition"):
        return [SEVERITY_BREAK]
    if table == "historical_grid":
        return ["GRID_CONCENTRATION"]
    if table == "source_missingness":
        return {"HOUR_OF_DAY": [LOW_HOUR, "HOUR_HEAPING"], "ILLUMINATION": [NO_LIGHT]}.get(row["source_field"], [])
    if table == "field_coverage_by_year":
        if row["metric_id"] == "valid_hour":
            return [LOW_HOUR] if row["period_start"] == 2024 else ["HOUR_HEAPING"]
        if row["period_start"] == 2024 and row["metric_id"] == "nonmissing_illumination":
            return [NO_LIGHT]
    return []


def state(column, row):
    if row[column] is not None:
        return {"value_state": "AVAILABLE"}
    if column == "severity_code":
        return {"value_state": "UNKNOWN", "reason_code": "NO_RECORDED_CODE"}
    if column == "pooled_source_levels":
        reason = "NO_POOLING"
    elif column == "fdr_bh_q" and row["fdr_bh_q_underflow"]:
        reason = "FLOATING_POINT_UNDERFLOW"
    elif column.startswith("serious_fatal_") or (
        row.get("period_grain") == "county" and row.get("severity_code") in (2, 3, 4)
    ):
        reason = SEVERITY_BREAK
    else:
        reason = "UNDEFINED_DENOMINATOR"
    return {"value_state": "UNAVAILABLE", "reason_code": reason}


def units(column, value):
    if column in RATIOS:
        return "percent"
    if column.endswith("crashes") or "_crashes_" in column or column == "min_expected_cell":
        return "crashes"
    if column in ("lat_bin", "lon_bin"):
        return "decimal degrees"
    if column in ("period_start", "period_end", "years_observed"):
        return "years"
    if column in ("cramers_v", "fdr_bh_q", "tested_levels"):
        return "unitless"
    if column.endswith("_id") or column == "severity_code":
        return "identifier"
    return "boolean" if isinstance(value, bool) else "text"


def counts(column, row):
    if column not in RATIOS:
        return None, None
    numerator, denominator, population = RATIOS[column]
    if row[denominator] is None or row[numerator] is None:
        return None, None
    return (
        {"count": row[numerator], "population": numerator.replace("_", " ").capitalize()},
        {"count": row[denominator], "population": population or row["denominator_population"]},
    )
