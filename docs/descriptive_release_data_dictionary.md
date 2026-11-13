# D7 data dictionary and Overview contract

The `v3-d7-2` bundle describes the frozen WPRDC Allegheny County, Pennsylvania extract. Period endpoints are inclusive crash years. `manifest.json` gives the frozen run ID, source and output SHA-256 hashes, schema version and review state. D7 identifies the run by notebook version and generation timestamp. Source paths below refer to the project repository, and `phase3/` in the manifest refers to the verified Phase 3 staging directory.

Each table has the same rows, columns and ordering in CSV and JSON. The JSON types are authoritative. Numeric values are in crashes, percent (0–100), decimal degrees or the explicitly named units below. A blank CSV field corresponds to JSON null. Zero is a measured count, including zero observations passing a coverage rule. A null percentage means a zero denominator or a withheld comparison, as described below. Rates are ratios of summed counts for the selected period. Percentages may be rounded for display.

## Chart and table inputs

All eight tables are `REVIEW_CANDIDATE` at bundle level. Read the row state in `findings` as well. Treat the county and grid results as historical counts of police-reported crashes. The source contains no travel-exposure denominator. No table contains accepted road-site assignments.

### county_periods

County extract grain. `period_grain` selects one full-county total (2004–2024), two eras (2004–2015 and 2016–2024), or 21 calendar years. These slices overlap across grains. `reported_crashes` counts unique CRNs in the WPRDC extract, including reports without usable or inside-county coordinates. `known_severity_crashes` uses codes 0–4. `unknown_severity_crashes` is its complement. `fatal_crashes` uses code 1 and counts crashes. `serious_fatal_crashes` uses codes 1 and 2 in 2016 onward. The three percentage field names identify their denominators, either all reports or known-severity reports for the row's period. Display fatal-only long-run trends with the coverage series. Serious/fatal count and share are null for pre-2016 or cross-era slices.

Source is `analysis/outputs/eda_summary/severity_by_year.csv`, reconciled against `MAX_SEVERITY_LEVEL` in the frozen WPRDC CSV. The v6 export retains pre-2016 serious/fatal code counts for audit and leaves their percentages blank. D7 withholds the combined count there as a trend metric as well. Individual code counts remain available for within-era interpretation.

### severity_composition

County extract by the same period grains and recorded severity group. Code 0 is property damage only, 1 fatal, 2 serious injury, 3 minor injury, 4 possible injury, 8 injury severity unknown, and 9 injury status unknown. Missing and unrecognised severity have null codes and distinct labels. `crashes` counts source reports in each group. Known groups use `denominator_crashes` from known severity. Excluded groups use all reports. These two sets of percentages have different populations and must not share a 100% stack. Zero missing and unrecognised values are observed in the frozen extract. Cross-era counts for codes 2–4 audit the recorded codes, with null denominators and percentages. Display injury composition within each era.

Source is the frozen WPRDC CSV, grouped by year and original severity code as in the notebook's known-severity crosstab. The sums for codes 0–4, code 1, and codes 1 and 2 reconcile to the annual frozen severity export.

### coordinate_coverage

County extract by full period, era and year. `usable_decimal_crashes` counts accepted state-route decimal pairs before polygon screening. `unusable_decimal_crashes` sums the missing, invalid and placeholder pair counts. `mapped_crashes` counts accepted pairs covered by the county polygon, including boundary points. `outside_county_crashes` is the remainder of usable pairs. The mapping percentage uses all source reports. The outside percentage uses only usable pairs. There is one location per mapped CRN. Multiple CRNs may occupy the same coordinate.

Sources are Phase 3 `county_coordinate_inventory_by_year.csv`, frozen `analysis/outputs/spatial/coordinate_coverage_by_year.csv` for the pre-polygon split, and `county_points_review.csv` for the mapped population. Missing pairs have at least one blank component. Invalid pairs fail the decimal syntax or plausibility bounds. Placeholders match the notebook tolerance around 40°N, 80°W. Police DMS candidates play no part in mapping. The unusable-pair category uses a joint record rule. The field-level null counts for `DEC_LAT` and `DEC_LONG` in `source_missingness` use individual columns.

### field_coverage_by_year

County extract by calendar year and metric. `valid_hour` counts numeric `HOUR_OF_DAY` in [0, 23]. `nonmissing_illumination` counts populated `ILLUMINATION` values, including any recorded unknown code. `covered_crashes` and `excluded_crashes` partition `reported_crashes` for that year. The coverage percentage uses all reports in the row's year. These are recording coverage counts. In 2024, 387 of 10,228 reports have a valid hour (3.78%) and 0 of 10,228 have a populated illumination field. Withhold 2024 hour-of-day, lighting distributions and comparisons that assume normal recording in 2024. Earlier hour comparisons also require a heaping caveat. The recorded 02:00 spike and whole/half-hour heaping warrant measurement caution. Exact crash dates are absent. Annual crash totals, severity-code counts and coordinate coverage keep their own denominators.

Source is the frozen WPRDC CSV with the v6 notebook's hour and illumination coverage rules. The 2024 results reconcile to `analysis/outputs/eda_summary/findings_review.csv`.

### source_missingness

One row per original source field, county extract, 2004–2024. `missing_crashes` is the number of null values after the v6 CSV load. The denominator is all 248,810 reports for every field. Blanks, encoded unknowns and invalid values can have different analytical eligibility. For example, the source severity field has zero nulls and 43,266 recorded unknown outcomes. Hour availability uses a range check in addition to nulls.

Source is `analysis/outputs/eda_summary/source_missingness.csv`, with percentages recomputed over the same population.

### historical_grid

One row per occupied 0.001° × 0.001° grid cell, 2004–2024. The geographic grain is the portion of the cell within the Allegheny County polygon. `lat_bin` and `lon_bin` are the WGS 84 (EPSG:4326) cell centres rounded to three decimals. Build each cell with half-width and half-height of 0.0005° and clip its display to `county_boundary.geojson`. Near 40.45°N the dimensions are approximately 111 m north–south by 85 m east–west before clipping. The polygon is the 2024 Census 500k boundary, GEOID 42003. `manifest.json` supplies its bounding box in west, south, east, north order and the occupied centre ranges.

`mapped_crashes` counts unique polygon-screened CRNs in the cell. `years_observed` counts years with at least one mapped crash in the cell and does not measure observation completeness. The 38,332 rows sum to 238,281 mapped crashes, after excluding 10,254 unusable pairs and 275 usable pairs outside the county. The table is sparse. Display reported concentration, with no implied exposure-adjusted rate, site prioritisation or inference for a missing cell. The verified `county_grid.svg` provides the same population, geography and resolution in a reference map.

Sources are `analysis/outputs/spatial/historical_grid_screening.csv` and `county_points_review.csv`, the pinned archive `data/reference/municipal_boundaries/cb_2024_us_county_500k.zip`, and the Phase 3 aggregate map. County points are reconciliation input and remain internal.

### severity_associations

One row per frozen categorical association test in the 2016–2023 county extract. Each uses the 77,476 known-severity crashes in that period and compares feature levels against the recorded binary serious/fatal outcome. Tested coverage is given against the in-period known-severity population, the in-period reported population and the full 2004–2024 extract, each in its named columns. Cramér's V is unitless. `min_expected_cell` is in expected crashes under independence. `fdr_bh_q` is a Benjamini–Hochberg adjusted probability, with null and an explicit underflow flag for the collision result recorded as 0 at floating-point precision. `pooled_source_levels` lists the original labels pooled before testing. Null means no pooling. Unknown or derived missing categories remain as treated by the frozen tests. These are within-population associations. Small effect sizes, pooled categories and field recording constrain interpretation. Grouped weather and road-surface comparisons remain unverified.

Sources are `analysis/outputs/eda_summary/association_tests.csv` and `association_pooling_audit.csv`. The 2024 records are outside the tested period.

### findings

Eight county-level evidence and decision notes. Each row identifies its period, population and review state. Source is `analysis/outputs/eda_summary/findings_review.csv`, with v3 scope applied and figures traced to the tables above. The codebook note also uses the frozen run manifest. The model note refers to the 2022–2024 retrospective evaluation among 27,697 known-severity reports and is `REVIEW_ONLY`. Detailed scores and model artifacts stay in the research record. The site-analysis note is `OUT_OF_SCOPE_NO_GO`.

## Phase 6 Road Safety Overview API contract

The Overview consumes bundle kind `descriptive_release`, artifact schema version `1`, and the exact approved bundle version and manifest hash. Endpoints and UI are Phase 6 work. The table IDs below resolve to `<table_id>.json` for typed rows and `<table_id>.csv` for downloads. Use `<table_id>.<column>` as the metric ID, with the applicable row key selecting the result. Return supported periods directly from the bundle and keep its table keys and types.

| Table ID | Row key | Grain and rendering metadata |
| --- | --- | --- |
| `county_periods` | Period grain and bounds | County extract. Return reported, known, unknown and metric counts. Use all reports for known-severity coverage and known outcomes for fatal or serious/fatal shares. |
| `severity_composition` | Period grain, bounds and severity group | County extract by original code group. Return the recorded code, label, count and its own denominator and population. Use the label to distinguish groups whose code is null. |
| `coordinate_coverage` | Period grain and bounds | County extract with a polygon screen. Return the usable, missing, invalid, placeholder, outside and mapped counts. Mapping coverage is over all reports. The outside share is over usable pairs. |
| `field_coverage_by_year` | Year and metric ID | County extract by field coverage rule. Return covered and excluded counts and the yearly reported denominator. |
| `source_missingness` | Source field | County extract, 2004–2024. Return field null counts and the 248,810-report denominator. |
| `historical_grid` | Cell centre latitude and longitude | Occupied clipped grid cell, 2004–2024. Return mapped counts and years represented, WGS 84, cell size, county extent and mapping coverage. Cell counts have no travel-exposure denominator. |
| `severity_associations` | Feature | County extract, 2016–2023, known severity. Return tested count, eligible and reported denominators, pooling, effect size and underflow flag. |
| `findings` | Finding ID | County scope with row-specific period, population and review state. Return the reviewed narrative and its state. Research and no-go entries are scope notes. |

Allowlisted assets are `county_boundary.geojson` (`application/geo+json`), `county_grid.svg` (`image/svg+xml`) and `descriptive_release_data_dictionary.md` (`text/markdown`). The boundary is vintage 2024. The map describes reported-crash concentration over 2004–2024 using 0.001° cells clipped to that boundary. Asset responses identify bundle version, manifest and asset SHA-256, and link to the approved provenance metadata. Row, download and asset responses all use the aggregate release gate. The manifest supplies metadata through the Overview contract. Internal records and model scores are outside this allowlist. Existing site routes keep their own bundle kinds and verification rules.

### Response metadata and availability

Successful JSON responses use the existing `APIResponse` envelope. For each result, include its table ID and schema version, inclusive period and period grain, geographic grain and GEOID, population, and the original values with their units. For percentages, include the numeric numerator and denominator and what each counts. For counts and unitless statistics without a ratio, the denominator is null. Supply coverage and excluded counts where applicable, and caveat codes with human-readable captions. Cite the frozen run ID, supporting source paths and SHA-256 values from manifest inputs, and the bundle version, manifest SHA-256 and output SHA-256. Findings also carry their source row state, independently of bundle approval.

Use an explicit metric state for a nullable observation. `UNKNOWN` means an observation is unknown. `UNAVAILABLE` means the measure is withheld or undefined and carries a reason code. Render either as a gap or a labeled unavailable value. JSON null and blank CSV values must never coerce to zero. Count values such as zero populated 2024 illumination records are measured and may display as zero. A null code for a named group, null pooling label or underflowing q retains the field-specific meaning above.

Supply `SEVERITY_CODING_BREAK_2016` with affected severity series. Preserve separate injury-composition eras and leave pre-2016 and cross-era serious/fatal counts and shares null. Fatal-only shares retain their known-severity coverage. Supply `LOW_2024_HOUR_COVERAGE` and `NO_2024_ILLUMINATION_COVERAGE` wherever the 2024 time or lighting caveats apply. Show coverage of 387/10,228 for valid hours and 0/10,228 for illumination, and withhold the affected distributions and comparisons. Earlier hourly interpretation carries the heaping caveat. Geographic captions include the exact period, resolution and 238,281/248,810 mapping coverage for the full-period grid. Missing cells carry no inferred counts or risks.

Use `verify_release` for `descriptive_release` against the external approval ledger. A named, dated `APPROVED` decision must bind the exact manifest SHA-256. Check the supported schema, scope and requested allowlisted artifact, and use `approved_bytes` to verify the bytes being consumed. Return `APPROVED_AGGREGATE_RELEASE` as the effective approval state only after those checks. The hash-bound manifest retains its original candidate state. An absent bundle or ledger, pending decision, hash mismatch, altered payload or incompatible bundle yields HTTP 503 with a stable unavailable code, no data, and a safe message. Leave verifier details in server logs. A valid approved table may still have unavailable individual metrics. Those remain typed nulls in a successful response.

### Representative success payload

Illustrative HTTP 200 after exact-hash approval. SHA-256 strings below stand for the verified values.

```json
{
  "success": true,
  "message": "Operation successful",
  "errors": null,
  "data": {
    "table_id": "county_periods",
    "schema_version": 1,
    "metric_id": "county_periods.known_severity_percent_of_reported",
    "period_start": 2024,
    "period_end": 2024,
    "period_grain": "year",
    "geographic_grain": "county_extract",
    "geoid": "42003",
    "population": "All 2024 crash reports in the WPRDC county extract",
    "value": 86.83026984747751,
    "value_state": "AVAILABLE",
    "units": "percent",
    "numerator": {"count": 8881, "population": "Reported crashes with severity codes 0–4"},
    "denominator": {"count": 10228, "population": "All reports in the period"},
    "coverage": {"known_severity_crashes": 8881, "unknown_severity_crashes": 1347},
    "caveats": [{"code": "SEVERITY_CODING_BREAK_2016", "caption": "Use separate injury-composition eras."}],
    "run_id": "v6/6.1-targeted-corrections/2026-11-11T03:13:38.038283+00:00",
    "sources": {
      "analysis/outputs/eda_summary/severity_by_year.csv": "71203c297fcdd845a7e995a910d8f1934999ec141f7913a6da2ed0074e3a3e3f",
      "data/raw/2c13021f-74a9-4289-a1e5-fe0472c89881.csv": "c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511"
    },
    "bundle": {
      "kind": "descriptive_release",
      "version": "v3-d7-2",
      "manifest_sha256": "<verified manifest SHA-256>",
      "output_sha256": "5b64fb5eff5f38fd6e5fb9d8672923fb9a9cf072d42acf4969f33ead8b77d56e",
      "approval_state": "APPROVED_AGGREGATE_RELEASE"
    }
  }
}
```

### Representative unavailable payload

HTTP 503 uses the existing FastAPI `detail` convention. Use the same public response for missing, unapproved and failed-verification cases.

```json
{
  "detail": {
    "code": "OVERVIEW_UNAVAILABLE",
    "message": "The reviewed Road Safety Overview dataset is unavailable.",
    "approval_state": null,
    "data": null
  }
}
```

For a 200 response with a withheld metric, the metric fields would include `"value": null`, `"value_state": "UNAVAILABLE"` and `"reason_code": "SEVERITY_CODING_BREAK_2016"` for a cross-era serious/fatal share. Preserve the verified bundle metadata and the period. Return null numerator and denominator for that withheld comparison.
