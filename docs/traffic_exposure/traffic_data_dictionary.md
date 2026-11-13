# Phase 4 — Module A: Traffic Exposure Data Dictionary

> **Superseded scope:** This report records earlier work and decisions. [Project Plan v3](../EDAgent_Project_Plan_v3.pdf) and the [v3 roadmap](../implementation_plan.md#v3-transition-and-roadmap) govern release scope: site-level historical screening, frequency/EB modelling and real-site treatment estimates are out of scope; geographic matches are diagnostic, with zero accepted primary assignments. Earlier claims of approval, mandatory pathways or pending release describe historical proposals, not current authorization.

**Project:** EDAgent — Road-Safety Analytics  
**Version:** 1.0.0  
**Phase:** Phase 4 — Module A (Traffic Exposure Research & Feasibility Assessment)  
**Date:** November 2026  
**Status:** Canonical & Complete  

---

## 1. Overview

This document provides the canonical schema, field definitions, data types, nullability rules, and domain constraints for all datasets and tabular exports generated during **Phase 4 Module A (Traffic Exposure Research and Feasibility Assessment)**.

All exports reside in the canonical output directory:  
`data/exports/traffic_exposure/`

### File Inventory:
1. `site_year_panel_prototype.csv` — Balanced site-year prototype evaluating panel construction feasibility.
2. `traffic_coverage_by_road_class.csv` — Empirical exposure availability stratified by functional road classification.
3. `traffic_coverage_by_year.csv` — Temporal coverage audit across the 21-year analysis period (2004–2024).
4. `feasibility_decision_matrix.csv` — Systematic evaluation of the five pre-defined feasibility criteria.

---

## 2. Table: `site_year_panel_prototype.csv`

The site-year panel prototype tests the construction of a balanced longitudinal panel for safety performance evaluation.

- **Primary Key:** `(site_id, year)`
- **Observation Unit:** Site-Year (One physical roadway site observed across one calendar year)
- **Temporal Window:** 2016–2024 (9 evaluation years)
- **Cohort Scope:** 3,882 verified state highway corridors (State Routes, Interstates, and Ramps)
- **Total Records:** 34,938 rows ($3,882 \times 9$)
- **Legitimate Zero-Crash Observations:** 17,623 rows (50.44% of panel)

| Field Name | Data Type | Nullable | Domain / Enum / Format | Description & Scientific Rationale |
|---|---|---|---|---|
| `site_id` | String | No | Regex: `^SEG:(02:SR[0-9]{4}:[0-9]{4}\|AC:[0-9]+)$` | Unique physical roadway site identifier assigned by Phase 3 Crosswalk. For state routes: `SEG:02:SR{route_4}:{segment_4}`. |
| `year` | Integer | No | `2016` – `2024` | Calendar year of observation. |
| `crash_count` | Integer | No | $\ge 0$ | Total number of verified crashes matched to this site during the specified calendar year. |
| `is_zero_crash_observation` | Boolean | No | `True`, `False` | Indicator flag denoting whether `crash_count == 0`. Legitimate zero-crash records are only included for verified, continuously observable state corridors. |
| `road_class` | String | No | `STATE_ROUTE`, `INTERSTATE`, `LOCAL_STREET`, `COUNTY_ROAD`, `RAMP` | Functional roadway classification derived from PennDOT RMSSEG and County GIS. |
| `site_type` | String | No | `SEGMENT`, `INTERSECTION` | Typology of the roadway site. |
| `traffic_exposure` | Float | **Yes (Strictly Empty)** | Empty (`""`) / Null | Annualized traffic exposure volume (AADT or Daily VMT). **Strictly unpopulated**: under zero-fabrication guidelines, no synthetic or static values are inserted when true annual data is absent. |
| `exposure_source` | String | No | `UNAVAILABLE`, `EXP-SRC-001`, `EXP-SRC-002`, `EXP-SRC-003`, `EXP-SRC-004`, `EXP-SRC-005` | Provenance identifier of traffic exposure measurement. For unpopulated records, this is explicitly set to `UNAVAILABLE`. |
| `exposure_year` | Integer | **Yes (Empty)** | Empty (`""`) or integer year | Year during which traffic exposure was empirically measured. Empty when exposure is unavailable. |
| `exposure_quality_status` | String | No | `MISSING_EXPOSURE`, `OFFICIAL_ANNUAL_COUNT`, `INTERPOLATED_UNVERIFIED`, `STATIC_CROSS_SECTIONAL_PROXY` | Quality classification of the exposure value. In this prototype, all records are explicitly flagged as `MISSING_EXPOSURE`. |
| `observability_status` | String | No | `VERIFIED_STATE_HIGHWAY_CORRIDOR`, `UNVERIFIED_LOCAL_ROAD`, `MUNICIPAL_BOUNDARY_DISPUTE` | Verification status of the roadway site's continuous existence and observability. State corridors are confirmed operational across the study window. |
| `crosswalk_version` | String | No | SemVer (e.g., `1.0.0`) | Version of the canonical Phase 3 crosswalk used to link crash records to physical sites. |

---

## 3. Table: `traffic_coverage_by_road_class.csv`

Provides the empirical breakdown of crashes, unique matched sites, and traffic volume coverage across functional roadway classes.

- **Primary Key:** `road_class`
- **Total Records:** 5 rows

| Field Name | Data Type | Nullable | Domain / Enum / Format | Description & Scientific Rationale |
|---|---|---|---|---|
| `road_class` | String | No | `LOCAL_STREET`, `STATE_ROUTE`, `COUNTY_ROAD`, `RAMP`, `INTERSTATE` | Functional road classification category. |
| `total_crashes` | Integer | No | $\ge 0$ | Total raw crashes occurring on roads of this class (2004–2024). |
| `matched_crashes` | Integer | No | $\ge 0$ | Crashes unambiguously matched to a physical site by the Phase 3 Crosswalk. |
| `unique_sites` | Integer | No | $\ge 0$ | Number of unique physical sites of this road class in the crosswalk. |
| `pct_of_unique_sites` | String | No | Percentage (e.g., `73.41%`) | Proportion of all unique matched sites represented by this road class ($N / 24,209$). |
| `verified_annual_exposure_coverage` | String | No | Percentage (`0.00%`) | Percentage of unique sites having a verified annual historical exposure panel. Universally 0.00%. |
| `modern_snapshot_proxy_coverage` | String | No | Percentage (e.g., `14.98%`) | Percentage of unique sites covered by the PennDOT RMSSEG modern cross-sectional snapshot proxy. |
| `exposure_availability_status` | String | No | `COMPLETELY_UNAVAILABLE`, `PARTIAL_MODERN_SNAPSHOT_ONLY`, `ADEQUATE` | High-level status indicating whether traffic exposure is sufficient for statistical modeling. |

---

## 4. Table: `traffic_coverage_by_year.csv`

Provides the temporal evaluation of crash counts, matched records, and exposure availability for each year of the 21-year analysis period.

- **Primary Key:** `crash_year`
- **Total Records:** 21 rows (2004–2024)

| Field Name | Data Type | Nullable | Domain / Enum / Format | Description & Scientific Rationale |
|---|---|---|---|---|
| `crash_year` | Integer | No | `2004` – `2024` | Calendar year of crash occurrences. |
| `total_crashes` | Integer | No | $\ge 0$ | Total raw crash incidents recorded in the WPRDC dataset for that year. |
| `matched_crashes` | Integer | No | $\ge 0$ | Crashes matched to a physical roadway site in that year. |
| `annual_exposure_site_years_covered` | Integer | No | `= 0` | Count of unique site-years possessing verified annual exposure measurements. |
| `annual_exposure_coverage_percent` | String | No | Percentage (`0.00%`) | Proportion of site-years with verified annual exposure ($0 / 24,209$). |
| `cross_sectional_proxy_eligible_crashes` | Integer | No | $\ge 0$ | Count of matched crashes that occurred on state-maintained roads eligible for modern static proxy attribution. |
| `notes` | String | No | Text | Audit note detailing historical data availability. |

---

## 5. Table: `feasibility_decision_matrix.csv`

Presents the formal evaluation of the five scientific criteria required to establish whether site-year crash frequency modeling is feasible.

- **Primary Key:** `criterion_id`
- **Total Records:** 5 rows (`CRIT-01` through `CRIT-05`)

| Field Name | Data Type | Nullable | Domain / Enum / Format | Description & Scientific Rationale |
|---|---|---|---|---|
| `criterion_id` | String | No | `CRIT-01`, `CRIT-02`, `CRIT-03`, `CRIT-04`, `CRIT-05` | Formal identifier of the scientific feasibility criterion. |
| `name` | String | No | Text | Descriptive name of the criterion. |
| `required_threshold` | String | No | Text / Threshold formula | Minimum acceptable statistical standard defined a priori. |
| `empirical_value` | String | No | Observed metric | Observed empirical value from repository data. |
| `status` | String | No | `PASS`, `FAIL` | Formal evaluation outcome against the pre-set threshold. |
| `critical_implication` | String | No | Text | Methodological, mathematical, or operational consequence of the empirical result. |
| `violates_guidelines_if_proceeded` | Boolean | No | `True`, `False` | Flag indicating whether proceeding with predictive modeling despite this failure violates project guidelines. |

---

## 6. Null and Missing Value Policies

In strict adherence to the project guidelines:
1. **No Synthetic Imputation:** When official exposure figures do not exist, fields are left empty (`""`). They are never populated with statewide averages, synthetic defaults, or imputed values.
2. **Explicit Status Flags:** Every record missing exposure is explicitly paired with `exposure_source = "UNAVAILABLE"` and `exposure_quality_status = "MISSING_EXPOSURE"` to prevent unflagged missingness in downstream processing.
3. **Zero-Crash Verification:** The `is_zero_crash_observation` flag is restricted to known, active state corridors during defined observation windows. It is never manufactured for unmonitored local streets whose historical existence cannot be verified.
