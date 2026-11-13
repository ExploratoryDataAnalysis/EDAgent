# D7 data dictionary and Overview contract

The `v3-d7-1` bundle describes the frozen WPRDC Allegheny County, Pennsylvania extract. Period endpoints are inclusive crash years. `manifest.json` gives the frozen run ID, source and output SHA-256 hashes, schema version and review state. The notebook does not assign a run ID. D7 identifies it by notebook version and generation timestamp. Source paths below refer to the project repository, and `phase3/` in the manifest refers to the verified Phase 3 staging directory.

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

## Consumption and approval

Use the table name and named value column as the metric identifier. The inclusive period columns, or the period in this dictionary and manifest for fixed-period tables, travel with the chart. The row carries counts and percentage denominators. Use this dictionary for units, population, geographic grain, eligibility, exclusions and source paths. Resolve the source SHA-256 values and frozen run ID from the manifest. This is the Phase 6 data contract. The bundle is staged and the Overview is not deployed.

Read the manifest status together with the existing external approval ledger. Approval requires a named and dated reviewer decision for `descriptive_release` with the exact candidate manifest SHA-256. The hash binds its version, scope, table files and other outputs. Use the existing release verifier and verify the file bytes at consumption. `APPROVED_AGGREGATE_RELEASE` describes only the allowed aggregate claims after that approval. The original candidate bytes remain hash-bound. The explicit research, diagnostic and no-go states stay in force.
