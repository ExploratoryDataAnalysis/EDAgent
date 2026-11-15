# Phase 12C Candidate Review: Retrospective Crash Severity Model Diagnostics

> **Governance Notice & Independent Scientific Boundary:**  
> This candidate review package evaluates the exact offline aggregate derivative produced from the frozen v6 research artifacts (`EDA_v6.ipynb`, `run_manifest.json`, `analysis/outputs/`).  
> **Status:** `REVIEW_CANDIDATE` / `PENDING_REVIEW`.  
> **Authority:** The implementation team has assembled and verified this candidate derivative. **The implementation team does not self-approve the candidate.** Public serving through EDAgent is gated strictly by an external, independent scientific approval record in the ledger (`ROAD_SAFETY_APPROVALS`). Without explicit external sign-off, this candidate derivative remains offline and inaccessible (`HTTP 503 MODELS_UNAVAILABLE`).  
> Governed by Project Plan v4 (Phase 12), Plan v3 (D5/D6 Scientific Restrictions), and `docs/phase12a_verification.md`.

---

## 1. Candidate Derivative Manifest & Checksums

The offline candidate derivative was deterministically built by `scripts/build_severity_derivative.py` into `data/exports/models/candidate/`.

- **Derivative Kind:** `models`
- **Derivative Version:** `v3-d5-1`
- **Schema Version:** `1.0.0`
- **Builder Version:** `1.0.0`
- **Candidate Manifest SHA-256:** `443344dc7fc8cc5d002a7754a13a08b0c666c4ac4d45c2fa13739f4390a0cd46`
- **Candidate Directory:** `data/exports/models/candidate/`

### Candidate Artifact Checksums

| Artifact Filename | Format | SHA-256 Checksum | Description |
| :--- | :--- | :--- | :--- |
| `manifest.json` | JSON | `443344dc7fc8cc5d002a7754a13a08b0c666c4ac4d45c2fa13739f4390a0cd46` | Candidate release manifest, scope, and verification metadata |
| `model_comparisons.json` | JSON | `de1d771fdfa67ba82420c9b31f28c59bf9b2faf0e8b30fd2a91592f51416e0a8` | Retrospective model comparison metrics on 2022–2024 holdout (N = 27,697) |
| `model_comparisons.csv` | CSV | `e8dc3b3a6b0a17d8853d3c91949c81f06ce76aa965c866e5dd29ff140652e1f5` | Tabular export of model comparison metrics |
| `feature_ablation.json` | JSON | `22fff2e167fe8afcc7aa2ba4d79b41bbff4e3ca7356e12ec3cf6c6ad25709fcb` | Categorical associations (Cramér's V) and pre- vs post-crash timing labels |
| `feature_ablation.csv` | CSV | `c6437f7d2c82d0e814b47afeb6622313cf1b99cddda180871968895c2d729186` | Tabular export of feature timing and ablation |
| `threshold_performance.json` | JSON | `7da1921bc3a970ca392bebefeeac976f1c9b4b5dd35f092ce42b5d1b9ea5ff85` | Confusion matrix counts and sensitivity/specificity at 0.50 threshold |
| `threshold_performance.csv` | CSV | `5c26d01e9a2da95e71c9999ae5d0baf0d4b8eefa93dea1b83366c26984d52905` | Tabular export of threshold confusion matrix |
| `calibration_diagnostics.json` | JSON | `99cd4ff47301aa135ad24f52d86f1b8c2b5c8b71a292f5ace7c6229b19844188` | Brier score calibration contrast and temporal fold details |
| `calibration_diagnostics.csv` | CSV | `bf852b99f24b47347812c7f168d794e7a37c92ed426cc8d5b88dd854625ac5fe` | Tabular export of calibration diagnostics |
| `models_data_dictionary.md` | Markdown | `c471fcb9ecc934a58c729738c85302eff05a1323d6c0e2520ec2003ae4119a41` | Field-by-field definitions and semantic types |
| `validation_report.json` | JSON | `f75e48d7e16ca5a35e69c77e71a2222831f6573c80968259AC855907D941E863` | Builder validation log and reconciliation results |

---

## 2. Upstream Source Lineage & Verification

The candidate derivative is derived entirely from approved, frozen research inputs without external modification:

1. **Raw Crash Extract:**  
   `data/raw/allegheny_county_crash_data_extract_2004_2024.csv`  
   SHA-256: `c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511`  
   CRN Universe: 248,810 records (248,810 unique CRNs, 2004–2024).
2. **Municipal Boundary Shapefile Archive:**  
   `data/raw/Allegheny_County_Municipal_Boundaries.zip`  
   SHA-256: `da4051717caec55c75e3748c3608c2a3dbde8d1ff401bbaf4f952e3c3fb63ef1`
3. **Frozen Research Notebook:**  
   `analysis/EDA_v6.ipynb`  
   Normalized LF SHA-256: `bdb7101c9fc017a68690506fd8cfdec579623b028563f287202ed54e6e324064`
4. **Frozen Run Manifest:**  
   `analysis/outputs/run_manifest.json`  
   Normalized LF SHA-256: `8bdedd5347e0942f49eae2465c7e7f261260476a7fead09b3315dfa67747400f`
5. **Frozen Metrics & Tables:**  
   - `analysis/outputs/model_metrics/severity_model_comparison.csv` (LF: `e74f33190dfad0eb50ce224a18018e6ec9cb166299066497f1f31fba825704bb`)
   - `analysis/outputs/model_metrics/severity_ap_temporal_intervals.csv` (LF: `9fb8cf92ba666e8574d6c468a3fb70e7e1fecde174f85e509eb2bf66fba89326`)
   - `analysis/outputs/eda_summary/association_tests.csv` (LF: `b4445b273ca35d64b18df457497aa1388151f12258ea09b3503f2a7db7660205`)
   - `analysis/outputs/eda_summary/injury_reconciliation.csv` (LF: `ec011d88ba2a0f8bfdfc6183eec1cf1dd88b8fa2c65969542a42dd6aa36ef797`)
   - `analysis/outputs/eda_summary/severity_by_year.csv` (LF: `fec25b29b4e7fe7447db073db16e00caebc366ff5940e53a3ae8b0e8ceec6b31`)

### Reproduction Environment & Exact Commands

- **Environment:** Dedicated virtual environment `.venv` with Python 3.13.3, scikit-learn 1.6.1, pandas 2.2.3, numpy 2.4.6, joblib 1.6.0.
- **Builder Command:**
  ```powershell
  .\.venv\Scripts\python.exe scripts/build_severity_derivative.py
  ```
- **Builder Verification Test Suite:**
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_severity_derivative_builder.py -v
  ```

---

## 3. Cohort Eligibility, Splits, and Conditioning

### 3.1 Target Definition and Conditioning
The modeling target is binary severe injury ($Y_{\text{severe}} \in \{0, 1\}$):
$$Y_{\text{severe}} = \begin{cases} 1 & \text{if } \text{FATAL\_COUNT} > 0 \lor \text{MAJ\_INJ\_COUNT} > 0 \lor \text{FATAL\_OR\_MAJ\_INJ} = 1 \\ 0 & \text{if crash resulted in minor injury, moderate injury, or property damage only} \end{cases}$$

**Fundamental Conditioning:**  
All models evaluate $P(Y_{\text{severe}} = 1 \mid \text{Crash Reported } \land \text{ Severity Known})$.  
This is strictly a retrospective outcome severity model conditional on an already reported incident. **It does not model crash occurrence frequency, crash risk per unit distance, or the probability that a crash will occur at a specific location.**

### 3.2 Listwise Exclusion of Unknown Severity
- Historical extract universe (2004–2024): 248,810 reported crashes.
- Unknown / unrecorded injury severity: 43,266 records (17.39%).
- Known severity records: 205,544 records (82.61%).
- **Scientific Decision:** Unknown severity crashes are removed via listwise deletion. They are **never imputed as non-severe** ($Y=0$), avoiding severe outcome deflation.

### 3.3 Historical 2016 Break and Chronological Split
Due to the PennDOT adoption of MMUCC 4th Edition clinical definitions in 2016, pre-2016 police injury classifications are not clinically comparable. The analysis is partitioned chronologically:
- **Training Cohort (2016–2021):** 58,660 known-severity crashes, containing 2,384 severe outcomes (4.0641% prevalence).
- **Test Holdout (2022–2024):** 27,697 known-severity crashes, containing 1,231 severe outcomes (4.4445% prevalence).
- **Full Modern Era (2016–2024):** 86,357 known-severity crashes, 3,615 severe outcomes (4.1861% prevalence).
- **Association Population (2016–2023):** 77,476 known-severity crashes (used for formal Cramér's V tests due to 2024 reporting lag in auxiliary environmental fields).

---

## 4. Model Architecture & Performance Matrix

Performance is evaluated on the independent chronological holdout (2022–2024, $N = 27,697$, $N_{\text{severe}} = 1,231$, prevalence $4.4445\%$).

| Model Architecture | Feature Timing Class | Collision Type Included? | Average Precision (AP) | 95% Temporal Bootstrap CI | ROC-AUC | Balanced Acc (0.50) | Brier Score | Calibration State |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Chance / Baseline** | — | — | **0.0444** | — | **0.5000** | 0.5000 | **0.0425** | — |
| **HistGradientBoosting** | POST_CRASH_KINEMATICS | Yes | **0.1548** | [0.1320, 0.1810] | 0.6921 | 0.6333 | 0.2028 | Uncalibrated raw margins |
| **Random Forest** | POST_CRASH_KINEMATICS | Yes | **0.1420** | [0.1256, 0.1621] | 0.6900 | 0.6301 | 0.1711 | Uncalibrated tree votes |
| **Logistic Regression** | POST_CRASH_KINEMATICS | Yes | **0.1393** | [0.1216, 0.1606] | 0.6990 | 0.6381 | 0.2132 | Uncalibrated logit outputs |
| **Logistic Regression (Calibrated)** | POST_CRASH_KINEMATICS | Yes | **0.1373** | [0.1216, 0.1606] | 0.6969 | 0.5000 | **0.0416** | Platt sigmoid (3 folds) |
| **Random Forest (No Collision)** | PRE_CRASH_ENVIRONMENTAL | **No** | **0.0517** | [0.0471, 0.0587] | 0.5461 | 0.5279 | 0.1995 | Uncalibrated tree votes |

---

## 5. Scientific Findings & Feature Timing Ablation

### 5.1 Post-Crash Kinematics vs. Pre-Crash Forecasting
The feature ablation study reveals that retrospective severity classification power is almost entirely driven by post-crash impact kinematics (`COLLISION_LABEL`):
- `COLLISION_LABEL` demonstrates Cramér's V = 0.2020 ($\chi^2 = 3,159.84$, $df = 10$, FDR-adjusted $q = 0.0$).
- When `COLLISION_LABEL` is removed from Random Forest, Average Precision collapses from **0.1420** to **0.0517**, barely exceeding the chance prevalence baseline of **0.0444**.
- Pre-crash environmental, temporal, and geometric features alone (`TIME_PERIOD` $V=0.0483$, `ILLUMINATION` $V=0.0371$, `INTERSECTION` $V=0.0222$) provide virtually zero discriminatory power for injury severity.
- **Scientific Implication:** Collision type (e.g., head-on, angle, pedestrian impact) is observed **after** or **during** the crash event. Models incorporating collision type cannot function as pre-crash warning systems; they describe physical energy transfer in already occurred collisions.

### 5.2 Probability Calibration Contrast
- Raw, uncalibrated classifier outputs exhibit severely distorted probability scales (Brier scores between 0.1711 and 0.2132), performing substantially **worse** than a naive constant prediction of the base rate ($\text{Brier} = 0.0425$).
- Chronological Platt calibration (3 temporal folds: 2016–2017, 2018–2019, 2020–2021) aligns predicted probabilities with true empirical risk, reducing the Brier score to **0.0416** (surpassing the constant-rate baseline).
- **Scientific Requirement:** Uncalibrated model scores must never be presented as event probabilities.

### 5.3 Threshold Performance at 0.50 Decision Cutoff
At the conventional 0.50 probability threshold, uncalibrated classifiers achieve apparent balanced accuracy (~0.63) only because raw score distributions happen to cross 0.50. However, calibrated probabilities on a 4.4% prevalence dataset rarely exceed 0.50, producing balanced accuracy of 0.5000 (all predicted negative). Decision thresholds must be tuned explicitly to operational utility rather than default cutoffs.

---

## 6. Permitted vs. Concrete Prohibited Claims

### 6.1 Permitted Public Claims (Upon Scientific Approval)
1. "Among reported crashes with known injury outcomes in Allegheny County (2016–2024), gradient-boosted trees and logistic regression rank severe injury outcomes with an Average Precision of 0.14–0.15 compared to a chance baseline of 0.044 (prevalence)."
2. "Collision type (an in-incident kinematic attribute) is the primary driver of retrospective severity ranking; removing collision type reduces Average Precision to 0.052, demonstrating that pre-crash environmental and geometric features alone have minimal severity predictive power."
3. "Uncalibrated classifier outputs yield poor probability fidelity (Brier scores > 0.17 vs 0.042 constant baseline); chronological Platt scaling restores empirical calibration (Brier score 0.0416)."
4. "The 2022–2024 holdout evaluation represents a retrospective temporal evaluation; the test years were previously examined during exploratory research (v5/v6) and do not represent a prospective clinical trial."

### 6.2 Concrete Prohibited Claims (Strictly Barred)
1. **NO Live Crash Prediction:** Claiming or implying that the models forecast where, when, or how many crashes will happen.
2. **NO Site-Level Risk Scoring:** Claiming or implying that a specific road segment, corridor, or intersection has a high "severity score" derived from these models.
3. **NO Intersection Safety Rankings:** Using model outputs to rank physical road locations.
4. **NO Countermeasure Prioritization:** Recommending engineering treatments or infrastructure investments based on model feature weights.
5. **NO Individual Crash Scoring:** Serving real-time severity scores for individual crashes or dispatch optimization.
6. **NO Binary Joblib Deserialization:** Loading pickled model weights in backend web services or public execution paths.

---

## 7. Release Gating, Withdrawal, and Supersession Protocol

### 7.1 Release Gate Mechanism
The candidate derivative is protected by an independent gate in EDAgent's release infrastructure:
- **Ledger:** `ROAD_SAFETY_APPROVALS`
- **Required Kind:** `models`
- **Required Version:** `v3-d5-1`
- **Required SHA-256 Digest:** `443344dc7fc8cc5d002a7754a13a08b0c666c4ac4d45c2fa13739f4390a0cd46`
- **Gate Evaluation:** `verify_release_decision("models")` evaluates the ledger at runtime. If the record is missing, has status other than `APPROVED`, or has a mismatched SHA-256 digest, the backend fails closed:
  - Responds with `HTTP 503 Service Unavailable`.
  - Error code: `MODELS_UNAVAILABLE`.
  - Sets header: `Cache-Control: no-store`.

### 7.2 Withdrawal & Rollback Protocol
If any scientific discrepancy, methodological flaw, or unapproved representation is identified post-approval:
1. Append a revocation record to `ROAD_SAFETY_APPROVALS` setting `"status": "WITHDRAWN"` with a cryptographic timestamp and reason.
2. The backend immediately revokes public access within zero seconds (no caching).
3. The frontend renders the standard model unavailable fallback view with reason: "Scientific review withdrawn by governing committee."

---

## 8. Review Sign-Off Block

```
================================================================================
                    INDEPENDENT SCIENTIFIC REVIEW RECORD
================================================================================
Derivative Name:    Allegheny County Retrospective Severity Diagnostics
Derivative Kind:    models
Derivative Version: v3-d5-1
Schema Version:     1.0.0
Manifest SHA-256:   443344dc7fc8cc5d002a7754a13a08b0c666c4ac4d45c2fa13739f4390a0cd46
Builder Version:    1.0.0

Review Status:      REVIEW_CANDIDATE (PENDING INDEPENDENT APPROVAL)
Implementation By:  EDAgent Autonomous Engineering Team
Execution Date:     2026-11-15

Scientific Checklist:
[X] 1. Output aggregates reproduce deterministically from frozen v6 inputs.
[X] 2. Estimators verified functionally equivalent on test cohort (max diff <= 1.29e-9).
[X] 3. Target conditioned strictly on reported crashes with known outcomes.
[X] 4. Unknown severity excluded via listwise deletion (not imputed as non-severe).
[X] 5. Post-crash collision type feature timing clearly separated and documented.
[X] 6. Calibration contrast (Brier score 0.0416 vs 0.2132) explicitly reported.
[X] 7. Zero individual crash records, coordinates, or site risk rankings in outputs.
[X] 8. Binary joblib files excluded from backend API serving.
[X] 9. Backend release gate fails closed (503) without external ledger entry.

Formal Sign-Off:
Status:             PENDING_INDEPENDENT_REVIEW
Approved For Live:  NO (Gated pending Road Safety Review Committee approval)
================================================================================
```
