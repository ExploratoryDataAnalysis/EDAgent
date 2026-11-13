# Phase 5 treatment evidence and illustrative calculator

## D8 evidence register

The [treatment evidence register](../EDAgent_Completed_Extension/EDAgent/backend/app/treatment_evidence/register.json) is version `v3-d8-1`. The canonical backend bundles it and serves it at `GET /api/v1/interventions/evidence` in the standard success envelope. Each record links to its citations through `source_ids` and records candidate facility and crash contexts, limitations, and an evidence decision. The contexts describe proposals from the available references. Applicability to EDAgent road sites has not been established.

The inventory uses [Project Plan v3, Chapter 8 and reference R8](EDAgent_Project_Plan_v3.tex), the [legacy concentration report, Section 5](frequency/historical_concentration_report.md), and the [Phase 3 source gap on CMF applicability](data_sources/phase3_source_gaps.md). The Clearinghouse citation provides methodology and applicability guidance. The legacy report supplies treatment names and proposed contexts. Its historical densities and thresholds supply no study effects. [Frozen notebook](../analysis/EDA_v6.ipynb) section 20 records that `data/reference/cmf/curated_cmf.csv` was absent. The v6 intervention-evidence output contains no curated entries.

All six entries are `REFERENCE_ONLY`, with null study factors, confidence intervals, and quality ratings. The register's overall numeric state is `NO_APPROVED_NUMERIC_CMF`.

| ID | Treatment family | Candidate facility and crash context |
| --- | --- | --- |
| `pedestrian-crossings-refuges` | Pedestrian crossings and refuge islands | Crossings and intersections on corridors with pedestrian activity. Pedestrian crashes. |
| `lighting` | Roadway lighting | General candidate in the plan. Facility and crash outcome are unspecified. |
| `speed-management` | Speed management and traffic calming | Municipal corridors and local streets. Study outcome is unspecified. |
| `dynamic-queue-warning` | Dynamic queue warning and speed advisories | Interstate tunnel approaches. Rear-end crashes. |
| `intersection-control-geometry` | Intersection control and geometric treatments | Intersections and arterial approaches. Study outcome is unspecified. |
| `access-management` | Arterial access management | Commercial state arterials. Rear-end and angle crashes. |

This is a manually curated register from the closed inputs. Its version and reviewed file are tracked in Git. Frozen provenance for the absence of curated factors is run `v6/6.1-targeted-corrections/2026-11-11T03:13:38.038283+00:00`, [run manifest](../analysis/outputs/run_manifest.json) SHA-256 `8bdedd5347e0942f49eae2465c7e7f261260476a7fead09b3315dfa67747400f`, and source crash CSV SHA-256 `c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511`. The register and calculator require no crash data at runtime.

## D9 scenario contract

`POST /api/v1/interventions/scenarios` accepts JSON using scenario schema version `"1"`. The canonical FastAPI app exposes the [Pydantic schema](../EDAgent_Completed_Extension/EDAgent/backend/app/schemas/intervention.py) through `/api/v1/openapi.json`. The scenario kind is `HYPOTHETICAL`, and the calculator uses a user-entered hypothetical baseline and factor. For example:

```json
{
  "schema_version": "1",
  "scenario_kind": "HYPOTHETICAL",
  "hypothetical_baseline_n": "10",
  "crash_type": "PEDESTRIAN",
  "analysis_period": {"length": 1, "unit": "YEARS"},
  "units": "CRASHES_PER_ANALYSIS_PERIOD",
  "cmf": {
    "origin": "USER_ENTERED_HYPOTHETICAL",
    "crash_type": "PEDESTRIAN",
    "value": "0.8",
    "bounds": {"lower": "0.6", "upper": "1.3"}
  }
}
```

The crash type must match across the baseline and the factor. The supported illustrative labels are `ALL`, `PEDESTRIAN`, `BICYCLIST`, `REAR_END`, `ANGLE`, and `NIGHTTIME`. The period is a positive whole number of years. Counts are totals over the same hypothetical period. A two-year scenario uses a two-year baseline total. The CMF and its optional bounds are dimensionless.

Send decimal strings with up to 12 whole digits and 6 fractional digits in ordinary decimal notation. The baseline must be finite and nonnegative. The factor and both optional bounds must be finite and strictly positive. Bounds must satisfy `lower ≤ value ≤ upper`. An omitted or null `bounds` means no sensitivity range. Extra fields and numeric JSON values for decimal inputs fail validation.

The response contains `data.status = ILLUSTRATIVE_ONLY`, the submitted scenario assumptions in `data.scenario`, and two representations of the counts. `data.exact` preserves the decimal calculation. `data.display` rounds each count and each endpoint independently to two places, with ties away from zero and signed zero displayed as `0.00`. Use the returned display strings to keep exact rounding across clients. Subtracting the rounded after-count from the rounded baseline may differ by 0.01 from the independently rounded change. Decimal outputs are strings.

- After-count is `N_before × CMF`.
- Change is `N_before × (1 − CMF)`. A positive change means fewer hypothetical crashes. A negative change means more. A factor of 1 gives zero change.
- After-count increases from `N_before × lower` to `N_before × upper`. Change increases from `N_before × (1 − upper)` to `N_before × (1 − lower)`. With the sample inputs, `data.display` is:

```json
{
  "hypothetical_baseline_n": "10.00",
  "after_n": "8.00",
  "delta_n": "2.00",
  "sensitivity": {
    "label": "Hypothetical factor sensitivity range",
    "after_n": {"lower": "6.00", "upper": "13.00"},
    "delta_n": {"lower": "-3.00", "upper": "4.00"}
  }
}
```

The sensitivity range holds the illustrative baseline fixed and varies the hypothetical factor. The range has no statistical confidence level.

### Unavailable and invalid requests

The app's error envelope carries `success: false`, `message`, `errors`, and `detail`.

| Request condition | HTTP | Machine-readable response |
| --- | --- | --- |
| Real-site mode or location context | 503 | `detail.code = REAL_SITE_BENEFIT_UNAVAILABLE` |
| Known evidence-only treatment reference requested as factor | 422 | `detail.code = NO_APPROVED_NUMERIC_CMF`, with `evidence_id` and `evidence_status` |
| Unknown treatment reference | 404 | `detail.code = EVIDENCE_NOT_FOUND` |
| Scenario query fields outside the contract | 422 | `detail.code = INVALID_QUERY` for an otherwise valid body |
| Invalid scenario fields | 422 | `detail[].type` reports validation codes such as `decimal_text`, `greater_than`, `literal_error`, `crash_type_mismatch`, or `invalid_factor_bounds` |

For a reference lookup, replace the sample's `cmf` object with `{"origin":"EVIDENCE_REGISTER","evidence_id":"lighting"}`. The response returns its reference status without a count or an inferred factor. For an unavailable real-site example, set `"scenario_kind":"REAL_SITE"` or add `"site_id":"Station 375"` to the sample. Site fields in nested objects and query parameters are also refused. The unavailable response carries no estimate, input echo, or numeric result. The scenario schema allows only the documented fields and enumerated labels. It accepts no location context or free-text prompt. The calculator has no dependency on selections, traffic observations, reported crashes, model artifacts, or D7 tables. Station 375's observed 2023 crash count is `UNKNOWN`.

### Deterministic test vectors

The [calculator and API tests](../EDAgent_Completed_Extension/EDAgent/backend/tests/test_interventions.py) run these cases with the sample's crash type and period unless stated otherwise.

| Baseline | Factor | Exact after | Exact change | Display after | Display change |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.8 | 8 | 2 | 8.00 | 2.00 |
| 10 | 1 | 10 | 0 | 10.00 | 0.00 |
| 10 | 1.25 | 12.5 | −2.5 | 12.50 | −2.50 |
| 0 | 1.25 | 0 | 0 | 0.00 | 0.00 |
| 12.345 | 0.8765 | 10.8203925 | 1.5246075 | 10.82 | 1.52 |
| 1 | 0.994999 | 0.994999 | 0.005001 | 0.99 | 0.01 |
| 1 | 0.995 | 0.995 | 0.005 | 1.00 | 0.01 |
| 1 | 1.004999 | 1.004999 | −0.004999 | 1.00 | 0.00 |
| 1 | 1.005 | 1.005 | −0.005 | 1.01 | −0.01 |

The two-year sensitivity vectors use the sample bounds. Baseline 10 yields exact after `[6,13]` and change `[-3,4]`. Baseline 0 yields zero at every endpoint. Baseline 0.025 yields exact after `[0.015,0.0325]` and change `[-0.0075,0.010]`, displayed as `[0.02,0.03]` and `[-0.01,0.01]`. Tests also cover large exact inputs, nonfinite and negative values, invalid period and units, crash type mismatch, invalid bounds, missing factor evidence, mixed real-site requests, and isolation from release and model loading.

From the canonical backend directory, run `python -m pytest -o addopts= -q tests/test_interventions.py` for the focused vectors and `python -m pytest -o addopts= -q tests` for the backend suite with its installed dependencies. Run the [repository road-safety suite](phase3_phase4_review_status.md#reproduction-and-review) from the root with the verified Phase 3 and D7 staging paths.

## Phase 6 display and release handoff

1. Build the Road Safety Overview first against the [D7 contract](descriptive_release_data_dictionary.md#phase-6-road-safety-overview-api-contract). Publication of D7 remains pending a designated reviewer's separate approval of the exact `v3-d7-2` manifest, SHA-256 `ec9def348fc67561f7ee2a5c7b3307a7db42b6e8832d7df7cc04252b87e70a82`. See the [D7 approval record](phase3_phase4_review_status.md).
2. Place **Illustrative scenario** in a separate workspace with no data flow from location views or map selections. Use **Hypothetical baseline crash count**, **Hypothetical CMF**, and **Hypothetical change in crash count**. Show the shared crash type and period beside both counts and the change. Show **User-entered hypothetical factor** as the factor origin.
3. Present treatment references, their sources, contexts, limitations, and `REFERENCE_ONLY` status separately from numeric inputs. For missing evidence, use **This treatment reference has no approved numeric factor. You can enter a hypothetical factor in illustrative mode.** Keep the numeric field empty after a reference lookup.
4. Label user bounds **Hypothetical factor sensitivity range** and show the scenario notice beside the results. Clear previous results when a scenario changes or fails. At a real location, use **Real-site treatment benefits are unavailable. An accepted site baseline and applicable factor are unavailable under v3.** Show no numeric placeholders. Keep Station 375's observed count unknown in the internal diagnostic context.

Phase 5 delivers the backend contract, arithmetic and references. Phase 6 owns the UI and its release acceptance checks.
