# Phase 3 Quality Control & Crosswalk Reconciliation Report

> **Superseded scope:** This report records earlier work and decisions. [Project Plan v3](../EDAgent_Project_Plan_v3.pdf) and the [v3 roadmap](../implementation_plan.md#v3-transition-and-roadmap) govern release scope: site-level historical screening, frequency/EB modelling and real-site treatment estimates are out of scope; geographic matches are diagnostic, with zero accepted primary assignments. Earlier claims of approval, mandatory pathways or pending release describe historical proposals, not current authorization.

**Project:** EDAgent — Road-Safety Analytics  
**Version:** 1.0.0  
**Phase:** Phase 3 — Module D  
**Date:** November 2026  
**Status:** **PASSED & COMPLETE**  
**Pipeline Manifest:** `data/exports/crosswalk/reproducibility_manifest.json`  

---

## 1. Executive Summary

Phase 3 established the authoritative roadway crosswalk linking historical crash incidents in Allegheny County, Pennsylvania (2004–2024, $N = 248,810$) to physical roadway infrastructure.

The batch reconciliation pipeline processed all 248,810 records through the verified 5-stage matching engine in **941.03 seconds (264.4 records/sec)**, enforcing the strict **One-Primary-Site Rule** without exception:

| Resolution Category | Crash Count | Percentage of Cohort | Denominator ($N$) | Physical Meaning |
|---|---|---|---|---|
| **MATCHED** | **187,068** | **75.1851%** | 248,810 | Successfully resolved to exactly **one primary site ID** (`SEG:...` or `INT:...`). |
| **AMBIGUOUS** | **5,856** | **2.3536%** | 248,810 | Spatial conflict or multi-candidate tie; `primary_site_id = None`. Exported to review queue. |
| **UNMATCHED** | **55,886** | **22.4613%** | 248,810 | Exceeds 50m snap threshold, missing coordinates, or out-of-bounds; `primary_site_id = None`. |
| **TOTAL** | **248,810** | **100.0000%** | 248,810 | Complete analytical universe (2004–2024). |

---

## 2. Invariant & Governance Verification

### 2.1 The One-Primary-Site Rule
- **Verification Rule**: $\forall \text{ crash} \in \text{Cohort}, \text{count}(\text{primary\_site\_id}) \le 1$.
- **Result**: **100.000% compliant**. Exactly 187,068 crashes have a non-null primary site ID; exactly 61,742 crashes have `primary_site_id = None`. Zero crashes in the entire dataset have duplicate primary assignments.
- **Impact**: Crash double-counting in site-level safety models and hotspot identification is eliminated.

### 2.2 Preservation of Ambiguity (Zero Spurious Snapping)
- Rather than forcing problematic crashes onto the nearest arbitrary line feature:
  - **2,146** candidate coordinate conflict pairs (>500m discrepancy between police DMS and state decimal coordinates) were gated as `AMBIGUOUS_CONFLICT`.
  - **3,710** multi-candidate ties (equidistant divided highway corridors within 2.0m) were gated as `AMBIGUOUS_MULTI_CANDIDATE`.
  - All 5,856 ambiguous incidents were preserved in `ambiguous_records_review.csv` with their competing candidates for engineering adjudication.

---

## 3. Stratified Quality Summaries

All summary tables report counts and percentages with explicit denominators.

### 3.1 Match Status by Crash Year (2004–2024)
- **Source**: `data/exports/crosswalk/stratified_summary_by_year.csv`
- **Cohort Denominator**: $N = 248,810$

| Crash Year | Matched Count | % Annual | % Cohort | Ambiguous Count | % Annual | % Cohort | Unmatched Count | % Annual | % Cohort | Annual Total | Annual Denom |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **2004** | 8,342 | 66.55% | 3.3528% | 232 | 1.85% | 0.0932% | 3,961 | 31.60% | 1.5920% | 12,535 | 12,535 |
| **2005** | 8,313 | 68.06% | 3.3411% | 243 | 1.99% | 0.0977% | 3,659 | 29.95% | 1.4706% | 12,215 | 12,215 |
| **2006** | 8,128 | 69.19% | 3.2667% | 243 | 2.07% | 0.0977% | 3,376 | 28.74% | 1.3569% | 11,747 | 11,747 |
| **2007** | 9,504 | 77.66% | 3.8198% | 356 | 2.91% | 0.1431% | 2,378 | 19.43% | 0.9557% | 12,238 | 12,238 |
| **2008** | 9,612 | 81.06% | 3.8632% | 368 | 3.10% | 0.1479% | 1,878 | 15.84% | 0.7548% | 11,858 | 11,858 |
| **2009** | 9,543 | 81.72% | 3.8355% | 327 | 2.80% | 0.1314% | 1,807 | 15.47% | 0.7263% | 11,677 | 11,677 |
| **2010** | 9,171 | 81.02% | 3.6859% | 420 | 3.71% | 0.1688% | 1,729 | 15.27% | 0.6949% | 11,320 | 11,320 |
| **2011** | 10,167 | 83.41% | 4.0863% | 347 | 2.85% | 0.1395% | 1,675 | 13.74% | 0.6732% | 12,189 | 12,189 |
| **2012** | 10,175 | 83.20% | 4.0895% | 332 | 2.71% | 0.1334% | 1,723 | 14.09% | 0.6925% | 12,230 | 12,230 |
| **2013** | 9,889 | 82.45% | 3.9745% | 344 | 2.87% | 0.1383% | 1,761 | 14.68% | 0.7078% | 11,994 | 11,994 |
| **2014** | 10,130 | 83.16% | 4.0714% | 286 | 2.35% | 0.1149% | 1,766 | 14.50% | 0.7098% | 12,182 | 12,182 |
| **2015** | 10,798 | 84.79% | 4.3399% | 145 | 1.14% | 0.0583% | 1,792 | 14.07% | 0.7202% | 12,735 | 12,735 |
| **2016** | 10,308 | 79.86% | 4.1429% | 237 | 1.84% | 0.0953% | 2,363 | 18.31% | 0.9497% | 12,908 | 12,908 |
| **2017** | 9,757 | 77.83% | 3.9215% | 280 | 2.23% | 0.1125% | 2,500 | 19.94% | 1.0048% | 12,537 | 12,537 |
| **2018** | 5,075 | 40.87% | 2.0397% | 112 | 0.90% | 0.0450% | 7,230 | 58.23% | 2.9058% | 12,417 | 12,417 |
| **2019** | 9,320 | 76.06% | 3.7458% | 245 | 2.00% | 0.0985% | 2,688 | 21.94% | 1.0803% | 12,253 | 12,253 |
| **2020** | 7,483 | 75.87% | 3.0075% | 196 | 1.99% | 0.0788% | 2,184 | 22.14% | 0.8778% | 9,863 | 9,863 |
| **2021** | 9,066 | 77.32% | 3.6437% | 238 | 2.03% | 0.0957% | 2,422 | 20.65% | 0.9734% | 11,726 | 11,726 |
| **2022** | 8,902 | 76.82% | 3.5778% | 270 | 2.33% | 0.1085% | 2,416 | 20.85% | 0.9710% | 11,588 | 11,588 |
| **2023** | 8,059 | 77.71% | 3.2390% | 269 | 2.59% | 0.1081% | 2,042 | 19.69% | 0.8207% | 10,370 | 10,370 |
| **2024** | 5,326 | 52.07% | 2.1406% | 366 | 3.58% | 0.1471% | 4,536 | 44.35% | 1.8231% | 10,228 | 10,228 |

### 3.2 Match Status by Road Class
- **Source**: `data/exports/crosswalk/stratified_summary_by_road_class.csv`
- **Cohort Denominator**: $N = 248,810$

| Road Class | Matched Count | % Class | % Cohort | Ambiguous Count | % Class | % Cohort | Unmatched Count | % Class | % Cohort | Class Total | Class % Cohort |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **INTERSTATE** | 21,935 | **95.21%** | 8.8160% | 96 | 0.42% | 0.0386% | 1,008 | 4.38% | 0.4051% | 23,039 | 9.26% |
| **STATE_ROUTE** | 100,725 | **95.25%** | 40.4827% | 2,030 | 1.92% | 0.8159% | 2,991 | 2.83% | 1.2021% | 105,746 | 42.50% |
| **RAMP** | 5,355 | **96.73%** | 2.1522% | 72 | 1.30% | 0.0289% | 109 | 1.97% | 0.0438% | 5,536 | 2.22% |
| **COUNTY_ROAD** | 4,118 | 46.34% | 1.6551% | 104 | 1.17% | 0.0418% | 4,664 | 52.49% | 1.8745% | 8,886 | 3.57% |
| **LOCAL_STREET** | 54,935 | 52.02% | 22.0791% | 3,554 | 3.37% | 1.4284% | 47,114 | 44.61% | 18.9357% | 105,603 | 42.44% |

> [!NOTE]
> High-order facilities (**Interstates, State Routes, and Ramps**) demonstrate **$>95\%$ match success**, driven by PennDOT LRS precision. Local streets show a higher unmatched rate due to crashes in off-street private lots or unrecorded local block numbers.

### 3.3 Distribution of Matching Methods
- **Source**: `data/exports/crosswalk/stratified_summary_by_method.csv`
- **Cohort Denominator**: $N = 248,810$

| Matching Method Code | Description | Count | Percentage | Denominator |
|---|---|---|---|---|
| `EXACT_LRS` | Stage 1 match using official PennDOT Route + Segment | 122,696 | 49.3131% | 248,810 |
| `SEGMENT_SPATIAL_SNAP` | Stage 3 orthogonal snapping to centerline $\le 50.0$m | 64,372 | 25.8720% | 248,810 |
| `UNMATCHED_DISTANCE` | Stage 5 rejection: nearest road $>50.0$m | 45,932 | 18.4607% | 248,810 |
| `UNMATCHED_MISSING` | Stage 5 rejection: missing coordinates & no LRS | 9,862 | 3.9637% | 248,810 |
| `AMBIGUOUS_MULTI_CANDIDATE`| Stage 4 tie: multiple candidates within 2m tolerance | 3,710 | 1.4911% | 248,810 |
| `AMBIGUOUS_CONFLICT` | Stage 4 gating: Police DMS vs. State Decimal $>500$m | 2,146 | 0.8625% | 248,810 |
| `UNMATCHED_OUT_OF_BOUNDS` | Stage 5 rejection: coordinates outside project bounds | 92 | 0.0370% | 248,810 |

### 3.4 Coordinate Validation Status Distribution
- **Source**: `data/exports/crosswalk/stratified_summary_by_coord_status.csv`

| Coordinate Status | Count | Percentage | Denominator |
|---|---|---|---|
| `VALID` | 236,513 | 95.0577% | 248,810 |
| `MISSING` | 10,059 | 4.0428% | 248,810 |
| `CONFLICT` | 2,146 | 0.8625% | 248,810 |
| `INVALID` | 55 | 0.0221% | 248,810 |
| `WARNING` | 37 | 0.0149% | 248,810 |

---

## 4. Cryptographic Provenance & Output Manifest

All generated deliverables were hashed using SHA-256 and recorded in `reproducibility_manifest.json`:

```json
{
  "crosswalk_version": "1.0.0",
  "pipeline_name": "EDAgent Road-Safety Crosswalk Reconciliation",
  "generation_utc": "2026-11-12T07:51:31.636617+00:00",
  "software": {
    "python_version": "3.13.3",
    "platform": "win32",
    "edagent_version": "1.0.0"
  },
  "parameters": {
    "max_snap_distance_meters": 50.0,
    "default_intersection_radius_meters": 30.48,
    "tie_distance_tolerance_meters": 2.0,
    "conflict_distance_threshold_meters": 500.0,
    "one_primary_site_rule_enforced": true
  },
  "inputs": {
    "crash_dataset_sha256": "c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511",
    "street_centerlines_sha256": "f204219e0230f73514718b58c2ba02d1cdef4c4d1a33faca87e2b974b0463502",
    "candidate_coordinate_disagreements_sha256": "6454a9ae11f8c5821d26c72f07d4f5456ab1e16bb49fa9d7c1441103e95f0cd1"
  },
  "outputs": {
    "crosswalk_csv_gz": "3da463a32cb3c06f7a24a5d2cdfcc855a8baf6ee8b11567b8fb6b3832e9e7ea8",
    "crosswalk_sample_csv": "470c0f4bbb3b40f85b3e9dd35767846bc09a48da9b28747127434ff23830390c",
    "ambiguous_records_review_csv": "64fea42ed86ad3de05652519069f71e8062904895db1ff8ef11820d7124b9e19",
    "coordinate_disagreements_review_csv": "dc78e5206ca3f669730622bcc8a7ba52c243be9452ba0335faab34d7c23b0905",
    "stratified_summary_by_year_csv": "fea2663df269df9a0b67afce9e7e747298470c0d50ba5164b82385d0069c9ffd",
    "stratified_summary_by_road_class_csv": "88748ffdcf921fc5fab28ef298fe514fae4c10931f43118719a8fb135c8acfc5",
    "stratified_summary_by_site_type_csv": "ac2b06a65244b0e4fca454d7ee4bf2a3ee964332319e65b4720491a091046673",
    "stratified_summary_by_method_csv": "2315812383e83e521908d5d500ca4c9c582bf5c4d8e537c9f49ad9c35d21df75",
    "stratified_summary_by_coord_status_csv": "a4102fda3d00732e1e81cbdcdf4be99b49b1f19db807853bab30d71ff6ee012f"
  }
}
```

---

## 5. Phase 3 Completion Gate Evaluation

| # | Acceptance Criterion | Evaluation Status | Evidence / Verification |
|---|---|---|---|
| **1** | Official source documentation verified or missing sources documented | **PASS** | Completed in Module A. All 8 official sources preserved with SHA-256 hashes in `data/reference/source_registry.json`. Source gaps documented in `docs/data_sources/phase3_source_gaps.md`. |
| **2** | GPS decoding validated | **PASS** | Completed in Module B. PennDOT official DMS parser tested across 31 unit tests (including 2,146 baseline disagreement pairs). Documentation in `docs/coordinates/gps_decoding_specification.md`. |
| **3** | Stable site identifiers generated | **PASS** | Completed in Module C. Semantic, order-invariant `INT:...` and `SEG:...` identifiers generated. 14 unit tests passed in `tests/test_stable_site_identification.py`. |
| **4** | Every crash has an explicit match status | **PASS** | Verified in Module D. All 248,810 records received an explicit status: 187,068 `MATCHED`, 5,856 `AMBIGUOUS`, 55,886 `UNMATCHED`. Zero unclassified records. |
| **5** | At most one primary site exists per crash | **PASS** | Strict invariant enforced in `reconciler.py` and unit tests. Exactly 1 primary site ID when `MATCHED`, strictly `None` when `AMBIGUOUS` or `UNMATCHED`. Zero multiple assignments. |
| **6** | Matched, ambiguous, and unmatched records reported by year and road class | **PASS** | Exported to `stratified_summary_by_year.csv` (all 21 years 2004–2024) and `stratified_summary_by_road_class.csv` with counts, annual %, cohort %, and documented denominators. |
| **7** | Review decisions and output hashes preserved | **PASS** | All review ledgers exported (`ambiguous_records_review.csv`, `coordinate_disagreements_review.csv`). All input and output SHA-256 hashes preserved in `reproducibility_manifest.json`. |

### Final Phase 3 Gate Decision: **PASS (100% Complete)**
