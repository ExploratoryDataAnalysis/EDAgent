# Phase 4 — Module B: Frequency Modelling & Concentration Data Dictionary

**Project:** EDAgent — Road-Safety Analytics  
**Version:** 1.0.0  
**Phase:** Phase 4 — Module B (Site-Year Frequency Modelling & Historical Concentration)  
**Date:** November 2026  
**Status:** Canonical & Complete  

---

## 1. Overview

This data dictionary provides the formal specification, column definitions, data types, constraints, nullability rules, and domain enums for all datasets, manifests, and API response contracts generated in **Phase 4 Module B**.

### Artifact File Inventory:
All data exports reside in the canonical frequency exports directory:  
`data/exports/frequency/`

1. `historical_crash_concentration.csv` — Full 21-year empirical crash concentration, density, and persistence dataset across all 24,209 unique physical matched roadway sites.
2. `model_comparison_metrics.csv` — Comparative statistical goodness-of-fit metrics contrasting Poisson GLM and Negative Binomial (NB2).
3. `chronological_validation_metrics.csv` — Out-of-sample expanding-window chronological validation metrics across 2019–2024.
4. `model_manifest.json` — Cryptographic model provenance manifest, parameter ledger, and production approval status.

---

## 2. Table: `historical_crash_concentration.csv`

- **Primary Key:** `site_id`
- **Total Records:** 24,209 rows (one per unique physical matched site in Allegheny County)
- **Temporal Span:** 2004–2024 (21 calendar years)
- **Unit of Analysis:** Physical roadway site (road segment or intersection)

| Field Name | Data Type | Nullable | Domain / Format | Description & Scientific Rationale |
|---|---|---|---|---|
| `site_id` | String | No | Regex: `^SEG:(02:SR[0-9]{4}:[0-9]{4}\|AC:[0-9]+)$` | Canonical roadway site identifier from the Phase 3 crosswalk. |
| `road_class` | String | No | `STATE_ROUTE`, `INTERSTATE`, `LOCAL_STREET`, `COUNTY_ROAD`, `RAMP` | Functional roadway classification. |
| `site_type` | String | No | `SEGMENT`, `INTERSECTION` | Typology of the roadway site. |
| `segment_length_km` | Float | No | $> 0.0$ | Physical length of the road segment in kilometers (0.8 km nominal for State Routes / Interstates, 0.3 km nominal for Local Streets). |
| `total_crashes_2004_2024` | Integer | No | $\ge 0$ | Total number of matched crashes occurring at this site across the full 21-year analysis period. |
| `fatal_crashes` | Integer | No | $\ge 0$ | Count of matched crashes resulting in at least one fatality (`FATAL_COUNT > 0` or `FATAL == '1'`). |
| `major_injury_crashes` | Integer | No | $\ge 0$ | Count of matched crashes resulting in at least one severe/major injury (`MAJ_INJ_COUNT > 0`). |
| `ksi_crashes` | Integer | No | $\ge 0$ | Total Killed or Seriously Injured crashes ($N_{\text{fatal}} + N_{\text{major\_injury}}$). |
| `pedestrian_crashes` | Integer | No | $\ge 0$ | Count of crashes involving at least one pedestrian (`PED_COUNT > 0` or `PEDESTRIAN == '1'`). |
| `bicycle_crashes` | Integer | No | $\ge 0$ | Count of crashes involving at least one pedalcycle (`BICYCLE_COUNT > 0` or `BICYCLE == '1'`). |
| `vru_crashes` | Integer | No | $\ge 0$ | Total Vulnerable Road User crashes ($N_{\text{pedestrian}} + N_{\text{bicycle}}$). |
| `crash_density_per_km` | Float | No | $\ge 0.0$ | Empirical spatial crash density: $\frac{\text{total\_crashes}}{\text{segment\_length\_km}}$. |
| `ksi_density_per_km` | Float | No | $\ge 0.0$ | Severe injury spatial density: $\frac{\text{ksi\_crashes}}{\text{segment\_length\_km}}$. |
| `vru_density_per_km` | Float | No | $\ge 0.0$ | Vulnerable road user spatial density: $\frac{\text{vru\_crashes}}{\text{segment\_length\_km}}$. |
| `epoch1_crashes_2004_2010` | Integer | No | $\ge 0$ | Count of crashes occurring during Epoch 1 (2004–2010). |
| `epoch2_crashes_2011_2017` | Integer | No | $\ge 0$ | Count of crashes occurring during Epoch 2 (2011–2017). |
| `epoch3_crashes_2018_2024` | Integer | No | $\ge 0$ | Count of crashes occurring during Epoch 3 (2018–2024). |
| `persistence_category` | String | No | Enum: `PERSISTENT_HIGH_HAZARD`, `EMERGING_HIGH_HAZARD`, `HISTORIC_RESOLVED`, `TRANSIENT_STOCHASTIC` | Multi-epoch temporal persistence classification. |
| `road_class_percentile` | Float | No | $0.00$ to $100.00$ | Percentile rank of `crash_density_per_km` strictly within its functional road class. Prevents local residential streets from being obscured by high-volume interstates. |

---

## 3. Table: `model_comparison_metrics.csv`

Provides the side-by-side empirical statistical comparison between the Poisson GLM baseline and the Negative Binomial (NB2) model on the controlled benchmark cohort.

- **Primary Key:** `metric`
- **Total Records:** 10 rows

| Field Name | Data Type | Nullable | Description |
|---|---|---|---|
| `metric` | String | No | Name of the diagnostic metric (e.g., `log_likelihood`, `aic`, `dispersion_ratio`). |
| `poisson_glm` | String / Float | No | Value computed under the Poisson GLM specification. |
| `negative_binomial_nb2` | String / Float | No | Value computed under the Negative Binomial (NB2) specification. |
| `interpretation` | String | No | Methodological guidance on how to interpret the comparison. |

---

## 4. Table: `chronological_validation_metrics.csv`

Provides the out-of-sample expanding-window chronological validation results across consecutive horizons.

- **Primary Key:** `fold_index`
- **Total Records:** 6 rows (Folds 1 through 6, evaluating 2019 through 2024)

| Field Name | Data Type | Nullable | Description |
|---|---|---|---|
| `fold_index` | Integer | No | Sequential fold identifier (1 to 6). |
| `train_period` | String | No | Calendar year range of the training split (e.g., `2016–2018`). |
| `validation_year` | Integer | No | Out-of-sample evaluation year (e.g., `2019`). |
| `train_records` | Integer | No | Number of training site-year observations. |
| `val_records` | Integer | No | Number of validation site-year observations. |
| `observed_crashes` | Integer | No | Total observed crashes in the validation year. |
| `predicted_crashes` | Float | No | Model-predicted aggregate crash frequency ($\sum \hat{\mu}_i$). |
| `calibration_ratio` | Float | No | Aggregate calibration ratio: $\frac{\text{observed}}{\text{predicted}}$. Values near 1.0 indicate perfect calibration. |
| `rmse` | Float | No | Root Mean Squared Error on validation site-years. |
| `mae` | Float | No | Mean Absolute Error on validation site-years. |

---

## 5. Artifact: `model_manifest.json`

The JSON model manifest provides cryptographic and operational traceability for trained model parameters.

| Field Name | Data Type | Nullable | Description |
|---|---|---|---|
| `model_name` | String | No | Name of the model architecture (`Negative_Binomial_NB2`). |
| `model_version` | String | No | Semantic version (`1.0.0`). |
| `software_version` | String | No | Project release version (`1.0.0`). |
| `crosswalk_version` | String | No | Crosswalk release version (`1.0.0`). |
| `training_dataset_checksum` | String | No | SHA-256 hash of the input training dataset. |
| `exposure_dataset_checksum` | String | No | Checksum or `UNAVAILABLE_EXPOSURE_VOID` tracking exposure provenance. |
| `training_period` | String | No | `2016-2020` |
| `validation_period` | String | No | `2021-2024` |
| `feature_definitions` | List[String] | No | Enclosed model features (`Intercept`, road class dummies, `length_km`). |
| `parameters` | Dict[String, Float] | No | Fitted coefficients ($\hat{\beta}$). |
| `standard_errors` | Dict[String, Float] | No | Asymptotic standard errors derived from inverse Hessian. |
| `dispersion_parameter_alpha` | Float | No | Quadratic overdispersion parameter $\hat{\alpha} = 1.2395$. |
| `metrics` | Dict[String, Any] | No | Summary goodness-of-fit metrics (AIC, BIC, dispersion, p-values). |
| `approval_status` | String | No | Explicit deployment gate: `NOT_APPROVED_FOR_PRODUCTION_INSUFFICIENT_EXPOSURE`. |
| `limitations` | List[String] | No | Mandatory regulatory and analytical caveats. |

---

## 6. Output Contract Schema: `SiteYearPrediction`

Defines the contract for frequency predictions returned by Python services and API endpoints:

```python
@dataclass(frozen=True)
class SiteYearPrediction:
    site_id: str
    prediction_year: int
    expected_crash_frequency: Optional[float]
    model_name: str
    model_version: str
    exposure_basis: str
    training_period: str
    validation_period: str
    prediction_status: PredictionStatus
    limitations: List[str]
    confidence_interval_95: Optional[Tuple[float, float]]
```

### Core Invariants:
1. **Strict Nullability When Blocked:** If `prediction_status != PredictionStatus.VALID_PREDICTION`, `expected_crash_frequency` must be `None`. Exposing synthetic or unverified predicted counts to users is prohibited.
2. **Non-Negativity:** When populated, `expected_crash_frequency` must be $\ge 0.0$.
3. **No Confusion with Observed Counts:** Expected crash frequency represents $\mathbb{E}[Y_{s,t}]$, a model expectation, and must never be labeled or displayed as an observed historical crash count.
