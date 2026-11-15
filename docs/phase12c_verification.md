# Phase 12C Verification Report: Exact-Derivative Review and Gated Retrospective Model Diagnostics

> **Governance & Authority Notice:**  
> This document records the complete implementation and verification of **Phase 12C — Exact-Derivative Review and Gated Retrospective Model Diagnostics**, incorporating the prerequisite **Phase 12A Verification-Hardening Pass**.  
> Governed by [EDAgent Project Plan v4 (Phase 12)](file:///c:/Users/user/Desktop/EDAgent/docs/EDAgent_Project_Plan_v4.pdf), [Project Plan v3 (Deliverables D5/D6 Scientific Restrictions)](file:///c:/Users/user/Desktop/EDAgent/docs/EDAgent_Project_Plan_v3.pdf), and `docs/phase12a_verification.md`.  
> **Scientific Release Status:** `REVIEW_CANDIDATE` / `PENDING_INDEPENDENT_REVIEW`.  
> **Crucial Rule:** The engineering implementation team does **not** self-approve the candidate derivative. The release gate fails closed (`HTTP 503 MODELS_UNAVAILABLE`) until explicit cryptographic approval is entered into the deployment ledger (`ROAD_SAFETY_APPROVALS`).

---

## 1. Executive Summary & Core Scientific Boundaries

Phase 12C transforms the retrospective severity modeling research in `analysis/EDA_v6.ipynb` into a versioned, offline, cryptographically verified derivative bundle suitable for public review and presentation, strictly gated against live deployment or unscientific claims.

### Governing Constraints & Prohibitions
1. **Target Conditioning:** Binary severe injury ($Y_{\text{severe}} \in \{0, 1\}$) is modeled **strictly conditioned on already reported crashes with known outcomes**:  
   $$P(Y_{\text{severe}} = 1 \mid \text{Crash Reported } \land \text{ Severity Known})$$  
   It is **not** a crash occurrence forecast.
2. **Deliverable D5 Strictly Review-Only:** Deliverable D5 (Retrospective Severity Model) is classified as `REVIEW_ONLY` and `NOT_APPROVED_FOR_PRODUCTION`.
3. **Deliverable D6 Firmly Out of Scope:** Deliverable D6 (Site-year frequency / Empirical Bayes model) remains signed `OUT_OF_SCOPE_NO_GO`.
4. **Zero Accepted Site Assignments:** `PRIMARY_SITE_ASSIGNMENTS_ACCEPTED = 0`.
5. **No Live Crash Prediction, No Site Rankings, No Case Scoring:** Severity model derivatives are barred from predicting crash counts, ranking physical intersections, prioritizing treatments, or serving real-time case risk scores.
6. **No Binary Joblib Deserialization in Backend:** All public endpoints serve precomputed, verified JSON/CSV tables; binary estimator artifacts are barred from backend execution paths.

---

## 2. Phase 12A Hardening Verification Summary

Before constructing the derivative, the Phase 12A reproduction comparator was substantially strengthened to eliminate ambiguities in estimator equivalence.

### 2.1 Comparator Enhancements (`scripts/compare_v6_repro.py`)
- **Fixed 21-Artifact Inventory:** Enforces an immutable manifest of 15 CSVs, 5 estimators, and 1 run manifest. Unexpected or missing files immediately trigger a non-zero exit code.
- **Deep Estimator Inspection:**
  - **Random Forest (180 trees each):** Compares tree counts, topologies, split feature IDs, thresholds, leaf values, and feature importances (maximum importance difference: $0.000$).
  - **Logistic Regression:** Compares coefficients, intercepts, classes, and scaling parameters.
  - **Calibrated Classifier:** Compares number of temporal folds (3), inner estimator structures, and sigmoid Platt parameters.
  - **HistGradientBoosting:** Compares iteration counts (45), binning thresholds, and class definitions.
- **Deterministic Prediction-Level Equivalence on Approved Test Cohort ($N = 27,697$):**
  - Evaluated on identical test records ($N = 27,697$, 1,231 severe positives).
  - Maximum absolute prediction probability difference: $\le 1.287 \times 10^{-9}$.
  - Classification decision differences at $0.50$ threshold: **$0 / 27,697$ ($100.00\%$ functional agreement)**.
- **Byte Divergence Root Cause Proven:** The byte digest discrepancy between frozen and rerun `.joblib` estimators is conclusively demonstrated to stem from Python pickle protocol chunking (the `\x95` frame opcode) and heap memory address variations during serialization, not numerical or algorithmic divergence.

### 2.2 Hardened Regression Test Results
- `tests/test_comparator_hardening.py` (7 tests passing): Proves that the comparator rejects missing artifacts, unexpected files, altered row counts, reordered columns, out-of-tolerance values, string/null discrepancies, and tampered raw inputs.
- `tests/test_phase12a_reproduction.py` (7 tests passing): Proves raw input identity, notebook identity, cohort reconciliation, collision ablation collapse, and calibration contrast.

---

## 3. Phase 12C-A Candidate Derivative Specification

The candidate derivative is generated into `data/exports/models/candidate/` under schema version `1.0.0` and derivative version `v3-d5-1`.

### 3.1 Four Versioned Aggregate Tables
1. **`model_comparisons` (JSON & CSV):**  
   Row identity includes model ID, model family, feature timing class, inclusion of collision type, training cohort ($N = 58,660$, 2,384 severe), test holdout ($N = 27,697$, 1,231 severe, 4.4445% prevalence), Average Precision (AP), 95% temporal bootstrap confidence interval, chance AP baseline (0.0444), ROC-AUC, chance ROC baseline (0.5000), balanced accuracy at 0.50 cutoff, Brier score, constant baseline Brier score (0.0425), and calibration state.
2. **`feature_ablation` (JSON & CSV):**  
   Row identity includes feature ID, feature name, timing category (`POST_CRASH_INCIDENT` vs `PRE_CRASH_ENVIRONMENTAL`/`PRE_CRASH_TEMPORAL`/`PRE_CRASH_GEOMETRIC`), analysis population ($N = 77,476$), Cramér's V, Chi-square statistic, degrees of freedom, raw p-value, and FDR Benjamini-Hochberg q-value.
3. **`threshold_performance` (JSON & CSV):**  
   Row identity includes model ID, decision threshold ($0.50$), evaluation records ($N = 27,697$), actual positives ($1,231$), actual negatives ($26,466$), true negatives, false positives, false negatives, true positives, sensitivity/recall, specificity, precision, and balanced accuracy.
4. **`calibration_diagnostics` (JSON & CSV):**  
   Row identity includes model ID, fitting interval, evaluation interval, raw vs calibrated Brier score, constant base rate baseline ($0.0426$), `beats_constant_baseline` boolean, calibration method (`sigmoid_platt_3_temporal_folds`), and methodological notes.

### 3.2 Candidate Manifest & Checksums

- **Candidate Manifest SHA-256:** `4ac5f547d111661c19e5b10291106d5c6ed0709a526a3b03a51732561ad7321b`
- **Output Artifact Inventory & Hashes:**

| Artifact Name | Format | SHA-256 Digest |
| :--- | :--- | :--- |
| `manifest.json` | JSON | `4ac5f547d111661c19e5b10291106d5c6ed0709a526a3b03a51732561ad7321b` |
| `model_comparisons.json` | JSON | `ffaeffb9a7218ed167f1aae762c0140921609e5390a353e43455c63bd15a0955` |
| `model_comparisons.csv` | CSV | `520ad5c94b5c45de7df759de268f65fe34039e2aafe9b93a9d1a5f0f6cd9d5df` |
| `feature_ablation.json` | JSON | `50788bea7c193f66b7616e11940d02c4233699dee17682cda1e0b918b5951891` |
| `feature_ablation.csv` | CSV | `933df4ccf267f6274f334cacf112f8ab069e0f16cbf6e60daf2fc77b0ff8677a` |
| `threshold_performance.json` | JSON | `43482e10094c9f4ec2c8ad66a253be4e94a80ed9867d6123f58f15359da2f9b1` |
| `threshold_performance.csv` | CSV | `c077fb535d670bef9af3381059c084a03dc2425d93230b109efa095a4f66cd75` |
| `calibration_diagnostics.json` | JSON | `fc650bdcd34da35dd718079de53a2bbedcb13cc7ebdf698502dc35e44c827bf5` |
| `calibration_diagnostics.csv` | CSV | `6e54b2d7ef371817a6d2d595c4fa6bd28866905a9844b269c5659a314007da66` |
| `models_data_dictionary.md` | Markdown | `ea24dd72b9a254a93a2751bf1b8f1b713a2efe55278c26608e6cbfbe31197359` |
| `validation_report.json` | JSON | `f1bddc0f553e07d15f2d4992da6d9518bbd7377db0a50bd0f0eaca877b18ad80` |

---

## 4. Phase 12C-B Builder & Determinism Verification

The offline builder is implemented in `scripts/build_severity_derivative.py`.

### 4.1 Input Verification & Checksum Proof
The builder verifies all upstream raw and research files before writing any table:
- Raw crash extract SHA-256: `c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511`
- Municipal boundary zip SHA-256: `da4051717caec55c75e3748c3608c2a3dbde8d1ff401bbaf4f952e3c3fb63ef1`
- Notebook `EDA_v6.ipynb` normalized LF SHA-256: `bdb7101c9fc017a68690506fd8cfdec579623b028563f287202ed54e6e324064`
- Research run manifest normalized LF SHA-256: `8bdedd5347e0942f49eae2465c7e7f261260476a7fead09b3315dfa67747400f`

### 4.2 Determinism Proof
The builder was run across multiple independent directories. All output digests, including `manifest.json`, matched byte-for-byte across runs:
```powershell
.\.venv\Scripts\python.exe scripts/build_severity_derivative.py
```
Exit code: `0`. Manifest SHA-256: `4ac5f547d111661c19e5b10291106d5c6ed0709a526a3b03a51732561ad7321b`.

### 4.3 Builder Test Suite (`tests/test_severity_derivative_builder.py`)
All 6 tests passed:
- `test_builder_candidate_manifest_and_tables`: PASSED
- `test_builder_denominators_and_reconciliation`: PASSED
- `test_no_case_level_or_coordinate_leakage`: PASSED
- `test_builder_determinism`: PASSED
- `test_builder_rejects_missing_input`: PASSED
- `test_builder_rejects_changed_source_hash`: PASSED

---

## 5. Phase 12C-C Independent Scientific Review Package

The review package is authored and delivered in `docs/modelling/phase12c_candidate_review.md`.

### Key Review Findings
1. **The Kinematic Lift Finding:**  
   Collision type (`COLLISION_LABEL`, Cramér's V = 0.2020) accounts for 92.5% of the model's predictive lift above chance. Removing collision type causes Random Forest AP to drop from **0.1420** to **0.0517** (chance baseline is 0.0444). Pre-crash roadway and environmental attributes alone cannot reliably forecast injury severity.
2. **Calibration Necessity:**  
   Uncalibrated classifiers produce severe score distortions (Brier scores between 0.1711 and 0.2132), performing substantially worse than predicting the constant base rate (0.0425). Chronological Platt scaling restores empirical calibration, reducing Brier score to **0.0416**.
3. **Review Status:** Signed as `REVIEW_CANDIDATE` / `PENDING_INDEPENDENT_REVIEW`. Self-approval by the engineering team is strictly prohibited.

---

## 6. Phase 12C-D Backend Release Integration

The backend release endpoint is implemented in `EDAgent_Completed_Extension/EDAgent/backend/app/api/v1/endpoints/models.py` and registered in `router.py`.

### 6.1 Gated Behavior & Security Guards
- **Ledger Verification:** Evaluates `ROAD_SAFETY_APPROVALS` for entry `models`. Fails closed (`HTTP 503 MODELS_UNAVAILABLE`) when unapproved, pending, withdrawn, or corrupted.
- **Manifest Fingerprint Guard:** Verifies manifest hash matches `4ac5f547d111661c19e5b10291106d5c6ed0709a526a3b03a51732561ad7321b`.
- **Prohibited Parameter Guard:** Any request query containing `latitude`, `longitude`, `site_id`, `intersection_id`, `predict`, `score`, `risk`, or `crn` is rejected immediately with `HTTP 400 Bad Request`.
- **Headers:** Sets `Cache-Control: no-store` on all responses (both success and error).
- **Independent from D7:** The `models` release gate and `descriptive_release` (D7) release gate operate completely independently.

### 6.2 Backend Test Suite (`test_models_release.py`)
All 6 tests passed:
- `test_models_unapproved_missing_ledger_fails_closed`: PASSED
- `test_models_pending_or_withdrawn_decision_fails_closed`: PASSED
- `test_models_manifest_digest_mismatch_fails_closed`: PASSED
- `test_models_approved_serving_provenance_and_tables`: PASSED
- `test_models_prohibited_parameters_strictly_rejected`: PASSED
- `test_models_unsupported_table_fails_closed`: PASSED

---

## 7. Phase 12C-E Frontend Presentation & Verification

The editorial presentation is implemented in `EDAgent_Completed_Extension/EDAgent/frontend/src/pages/ModelDiagnosticsPage.tsx` and mounted at `/road-safety/models`.

### 7.1 Seven Mandatory Editorial Sections
1. **Research Question & Conditioning Statement:** Highlights $P(\text{Severe Injury} \mid \text{Crash Reported } \land \text{ Severity Known})$ and explicitly disclaims crash occurrence prediction.
2. **Population, Era & Missing-Outcome Exclusions:** Displays training cohort ($58,660$), test holdout ($27,697$), and excluded unknown severity ($43,266$, listwise deletion).
3. **Model Comparison Table:** Contrasts HistGradientBoosting (AP 0.1548), Random Forest (AP 0.1420), Logistic Regression (AP 0.1393), and calibrated Logistic Regression against chance baselines (AP 0.0444, ROC 0.5000).
4. **Feature Timing & Ablation:** Features Cramér's V table, timing category pills (`POST_CRASH_INCIDENT` vs `PRE_CRASH`), and visual bar breakdown of collision type lift collapse.
5. **Probability Calibration & Thresholds:** Highlights Brier scores ($0.0416$ vs $0.2132$ raw) and confusion matrix counts at 0.50 threshold.
6. **Scientific Limitations & Prohibited Uses:** Explicit two-column callout detailing prohibited uses (no live prediction, no site rankings, no treatment prioritization, no case scores).
7. **Provenance, Verification & Downloads:** Displays manifest SHA-256, candidate version, approval status, and one-click downloads for all 4 tables in CSV and data dictionary in Markdown.

### 7.2 Visual Smoke Testing Across Viewports
Executed via `EDAgent_Completed_Extension/EDAgent/frontend/tests/models-smoke.mjs` using Playwright:
- **Desktop (1440 × 900):** Full approved presentation verified (`desktop_1440_approved.png`). Zero horizontal overflow.
- **Tablet (768 × 1024):** Fully responsive, wrap-around tables and cards verified (`tablet_768_approved.png`). Zero horizontal overflow.
- **Mobile (390 × 844):** Fully responsive narrow layout verified (`mobile_390_approved.png`). Zero horizontal overflow.
- **Gated Offline View (1440 × 900):** Gated status view verified (`desktop_1440_gated_offline.png`).

All screenshots are stored in `.repro/phase12c/screenshots/` and archived in `docs/phase12c_screenshots/`.

---

## 8. Withdrawal & Rollback Protocol

If an external reviewer, auditor, or the Road Safety Review Committee determines that the models release must be withdrawn:

1. **Immediate Revocation via External Ledger:**  
   In the ledger file pointed to by `ROAD_SAFETY_APPROVALS`, set the `models` decision to `"WITHDRAWN"`:
   ```json
   {
     "models": {
       "decision": "WITHDRAWN",
       "reviewer": "ROAD SAFETY REVIEW COMMITTEE",
       "date": "2026-11-15",
       "manifest_sha256": "4ac5f547d111661c19e5b10291106d5c6ed0709a526a3b03a51732561ad7321b",
       "reason": "Administrative supersession or review revocation"
     }
   }
   ```
2. **Zero-Latency Backend Enforcement:**  
   Because the backend evaluates the ledger on every incoming read and sets `Cache-Control: no-store`, revocation takes effect immediately across all endpoints (`/provenance`, `/tables/*`, `/downloads/*`, `/assets/*`), returning `HTTP 503 MODELS_UNAVAILABLE`.
3. **Frontend Immediate Fallback:**  
   The frontend automatically renders the offline gate notice upon receiving the 503 status code.

---

## 9. Verification Sign-Off Matrix

| Check / Verification Item | Target Standard | Result | Status |
| :--- | :--- | :--- | :---: |
| Raw crash extract checksum | `c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511` | Matched | **PASS** |
| Municipal boundary zip checksum | `da4051717caec55c75e3748c3608c2a3dbde8d1ff401bbaf4f952e3c3fb63ef1` | Matched | **PASS** |
| Frozen notebook normalized LF hash | `bdb7101c9fc017a68690506fd8cfdec579623b028563f287202ed54e6e324064` | Matched | **PASS** |
| Run manifest normalized LF hash | `8bdedd5347e0942f49eae2465c7e7f261260476a7fead09b3315dfa67747400f` | Matched | **PASS** |
| Phase 12A comparator hardening | 21-artifact fixed inventory, deep estimator inspection | 14/14 tests passing | **PASS** |
| Prediction functional agreement | $N = 27,697$ test records, max diff $\le 1.29 \times 10^{-9}$ | 0 decision diffs at 0.50 | **PASS** |
| Builder determinism | Byte-identical outputs across runs | SHA-256 match | **PASS** |
| Derivative manifest checksum | `4ac5f547d111661c19e5b10291106d5c6ed0709a526a3b03a51732561ad7321b` | Generated & Verified | **PASS** |
| Case-level or site leakage | No CRN, individual coordinates, or site rankings | 0 leaked fields | **PASS** |
| Candidate review package | Complete documentation of methodology, timing, limitations | Authored in `docs/modelling/` | **PASS** |
| Backend release gating | Fails closed (503) without approval; 200 when approved | 6/6 tests passing | **PASS** |
| Query parameter protection | Prohibits coordinates, site_id, live crash scoring (400) | Verified in tests | **PASS** |
| Frontend editorial page | 7 mandatory sections, institutional typography | TypeScript built 0 errors | **PASS** |
| Responsive layout & screenshots | 1440px desktop, 768px tablet, 390px mobile, gated view | 4/4 screenshots captured | **PASS** |
| Scientific approval boundary | Release candidate pending independent sign-off | Gated `REVIEW_CANDIDATE` | **PASS** |
