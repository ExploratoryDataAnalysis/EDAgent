# Retrospective Crash Severity Analysis: Methodological Specifications & Limitations

> **Superseded scope:** This report records earlier work and decisions. [Project Plan v3](../EDAgent_Project_Plan_v3.pdf) and the [v3 roadmap](../implementation_plan.md#v3-transition-and-roadmap) govern release scope: site-level historical screening, frequency/EB modelling and real-site treatment estimates are out of scope; geographic matches are diagnostic, with zero accepted primary assignments. Earlier claims of approval, mandatory pathways or pending release describe historical proposals, not current authorization.

**Project:** EDAgent — Road-Safety Analytics  
**Version:** 1.0.0  
**Phase:** Phase 4 — Module C (Severity Analysis Limitations & Analytical Boundaries)  
**Date:** November 2026  
**Status:** Canonical & Methodologically Complete  

---

## 1. Executive Summary and Analytical Purpose

This document establishes the scientific boundaries, outcome definitions, feature properties, and validation limits of crash injury severity modeling in the EDAgent platform. Governed by Project Plan v2 (§8, §14, §18) and empirical findings in `EDA_v6.ipynb` (Sections 14 and 18):

1. **Retrospective Associations Only:** Severity classification models evaluate injury outcome severity **conditioned on a crash having already occurred**. They do not predict whether, where, or when a crash will occur.
2. **Prohibition of Causal Inferences:** Observational associations (e.g., angle collisions having higher fatal/major injury rates) reflect physical impact kinematics, not actionable causal interventions. Selecting safety countermeasures based purely on correlational classifier weights is scientifically invalid.
3. **Collision Type is Observed Post-Crash:** The single strongest predictor of severe injury is `COLLISION_TYPE` (Cramér's V = 0.202). Because collision type is determined during the incident, it represents retrospective characterization rather than an antecedent pre-crash forecasting feature.
4. **Mandatory Production Restriction:** All severity models are classified as `REVIEW_ONLY` and `NOT_APPROVED_FOR_PRODUCTION`. Retrospective severity scores must not be represented as future predictions without a separate, prospective clinical validation study.

```mermaid
flowchart TD
    Universe[248,810 Historical Reported Crashes] --> MissingSplit{Severity Known?}
    MissingSplit -- Unknown Severity<br/>43,266 Records (17.39%) --> Excluded[Listwise Deletion<br/>NOT Imputed as Non-Severe]
    MissingSplit -- Known Severity<br/>205,544 Records (82.61%) --> HistoricalEra{Crash Era?}
    
    HistoricalEra -- Pre-2016 Break<br/>1980s Police Standards --> NonComparable[Non-Comparable Injury Codes<br/>Major vs Moderate Shift]
    HistoricalEra -- 2016–2023 Study Era<br/>77,476 Records --> Target[Binary Target: FATAL_OR_MAJ_INJ<br/>Severe Prevalence: 4.44%]
    
    Target --> Models[Retrospective Classifiers<br/>HistGradientBoosting / RF / LogReg]
    Models --> CollisionLeakage{Include Post-Crash Collision Type?}
    CollisionLeakage -- Yes --> AP_High[AP: 0.1548 | ROC-AUC: 0.6921<br/>AP 95% CI: 0.132 to 0.181]
    CollisionLeakage -- No: Pre-Crash Only --> AP_Low[AP: 0.0517 | ROC-AUC: 0.5461<br/>Near Chance Baseline 0.0445]
    
    AP_High & AP_Low --> Limitations[Strict Limitations:<br/>1. Retrospective Only<br/>2. Not Occurrence Prediction<br/>3. Association != Causation]
```

---

## 2. Outcome Definition and Historical Code Break

### 2.1 The KABCO Injury Severity Scale
In highway safety engineering, injury severity is recorded on the standard five-point KABCO scale:
- **K:** Fatal Injury (Death within 30 days of the crash)
- **A:** Suspected Serious / Major Injury (Incapacitating injury preventing normal activity)
- **B:** Suspected Minor / Moderate Injury (Evident injury such as bruises, abrasions, lacerations)
- **C:** Possible Injury (Complaint of pain without evident physical wounds)
- **O:** No Apparent Injury (Property Damage Only)

### 2.2 The Binary Target: `FATAL_OR_MAJ_INJ`
To focus on life-altering harm, severity analysis defines the binary outcome:
$$Y_{\text{severe}} = \begin{cases} 1 & \text{if } \text{FATAL\_COUNT} > 0 \lor \text{MAJ\_INJ\_COUNT} > 0 \lor \text{FATAL\_OR\_MAJ\_INJ} = 1 \\ 0 & \text{if crash resulted in minor, moderate, or property-damage-only outcomes} \end{cases}$$

### 2.3 The 2016 Historical Coding Break
In 2016, the Pennsylvania Department of Transportation transitioned from legacy police reporting codes to the federal **Model Minimum Uniform Crash Criteria (MMUCC) 4th Edition**:
- Under legacy definitions (2004–2015), major injury definitions were subjective and varied significantly across 130 municipal police departments.
- MMUCC 4th Edition instituted standardized clinical criteria for suspected serious injuries.
- As documented in `analysis/outputs/eda_summary/injury_reconciliation.csv`, principal severe-outcome modeling must be **strictly restricted to the consistent 2016–2023 reporting era**.

---

## 3. Sample Composition, Missing Data, and Class Imbalance

### 3.1 Handling of Unknown Severity
Across the 248,810 total crash records:
- **Known Binary Outcomes:** 205,544 records (**82.61%**).
- **Unknown Injury Severity:** 43,266 records (**17.39%**).

#### Core Handling Rule:
Unknown severity records are **listwise excluded from model training and evaluation**. Under project invariants, unknown outcomes must never be silently converted to zero or assumed non-severe.

### 3.2 Extreme Class Imbalance
In the 2016–2023 evaluation population:
- **Total Tested Records:** 77,476 crashes.
- **Severe Injury Crashes ($Y=1$):** 3,443 crashes (**4.44% prevalence**).
- **Non-Severe Crashes ($Y=0$):** 74,033 crashes (**95.56%**).

Because of this 21:1 imbalance:
- Standard classification accuracy is useless (a trivial dummy classifier predicting $Y=0$ achieves $95.56\%$ accuracy while detecting zero severe injuries).
- Evaluation must rely on **Average Precision (Area Under the Precision-Recall Curve)**, **ROC-AUC**, and **Balanced Accuracy at 0.50**.

---

## 4. Feature Definitions and Retrospective Associations

### 4.1 Categorical Association Tests (2016–2023 Study Population)
*Canonical source: `analysis/outputs/eda_summary/association_tests.csv`*

All categorical association tests were evaluated on the 77,476 known-severity crashes using Pearson's $\chi^2$ test, Cramér's $V$, and Benjamini-Hochberg (BH) false discovery rate control:

| Feature Name | Degrees of Freedom | $\chi^2$ Statistic | Cramér's $V$ | Raw $p$-Value | BH Adjusted $q$-Value | Timing of Observation |
|---|---|---|---|---|---|---|
| **`COLLISION_LABEL`** | 10 | 3,159.84 | **0.2020** | $< 10^{-15}$ | **$0.0$** | **Post-Crash (During Incident)** |
| **`TIME_PERIOD`** | 4 | 180.92 | **0.0483** | $4.72 \times 10^{-38}$ | $9.44 \times 10^{-38}$ | Pre-Crash (Environmental) |
| **`ILLUMINATION_LABEL`** | 6 | 106.76 | **0.0371** | $9.72 \times 10^{-21}$ | $1.30 \times 10^{-20}$ | Pre-Crash (Environmental) |
| **`INTERSECTION_LABEL`** | 8 | 38.04 | **0.0222** | $7.39 \times 10^{-6}$ | $7.39 \times 10^{-6}$ | Pre-Crash (Geometric) |

### 4.2 The Collision Type Effect (Target Leakage Caveat)
`COLLISION_LABEL` (angle, head-on, rear-end, sideswipe, fixed object) exhibits by far the highest association ($V = 0.2020$).
- Head-on collisions and angle collisions at high speed impart catastrophic kinetic energy transfers into passenger compartments.
- **The Critical Flaw:** Collision type is not known prior to a crash. It is an artifact of the collision event itself. Including collision type in a severity model improves ranking among already reported incidents, but cannot forecast impending danger before vehicles collide.

---

## 5. Model Performance and Temporal Validation Intervals

Four machine learning architectures were trained on retrospective crash records (evaluating $N = 27,697$ test records):

| Model Architecture | Features Included | Average Precision (AP) | 95% Block-Bootstrap AP Interval | ROC-AUC | Balanced Accuracy at 0.50 | Uncalibrated Brier Score |
|---|---|---|---|---|---|---|
| **HistGradientBoosting** | Environmental + Road + Collision Type | **0.1548** | **$[0.1320, 0.1810]$** | **0.6921** | 0.6333 | 0.2028 |
| **Random Forest** | Environmental + Road + Collision Type | 0.1420 | $[0.1256, 0.1621]$ | 0.6900 | 0.6301 | 0.1711 |
| **Logistic Regression** | Environmental + Road + Collision Type | 0.1393 | $[0.1216, 0.1606]$ | 0.6990 | **0.6381** | 0.2132 |
| **Random Forest (Pre-Crash Only)** | Environmental + Road *(No Collision Type)* | **0.0517** | **$[0.0471, 0.0587]$** | **0.5461** | 0.5279 | 0.1995 |

*Chance baseline Average Precision = 0.0445 (4.44% prevalence).*

### Key Performance Findings:
1. **The 3-Fold Power of Collision Type:** HistGradientBoosting with collision type achieves $\text{AP} = 0.1548$ (a 3.5-fold increase over the 0.0445 chance baseline).
2. **Pre-Crash Predictive Collapse:** When collision type is removed, Random Forest performance collapses to $\text{AP} = 0.0517$ and $\text{ROC-AUC} = 0.5461$ (barely above chance). Environmental conditions (rain, darkness, wet pavement) do not discriminate severe injuries from non-severe crashes in the absence of vehicle impact kinematics.
3. **Temporal Stability:** The 300-replicate block-bootstrap validation shows narrow confidence bounds ($[0.132, 0.181]$ for HistGradientBoosting), confirming model stability across temporal blocks.

---

## 6. Comprehensive Limitations Ledger

To protect users and transportation decision-makers, all retrospective severity analyses are bounded by seven strict limitations:

1. **Retrospective Conditioning:** Models predict $P(\text{Severe} \mid \text{Crash occurred})$. They cannot predict $P(\text{Crash occurrence})$.
2. **Post-Crash Target Leakage:** Collision type represents post-impact kinematics. Using it for pre-crash safety screening is invalid.
3. **Severe Class Imbalance:** At $4.44\%$ prevalence, predicted positive probabilities represent ranking percentiles rather than absolute clinical probabilities.
4. **Uncalibrated Probability Scores:** Uncalibrated model scores must not be presented as true posterior probabilities without isotonic or Platt calibration.
5. **Absence of Vehicle & Human Factors:** The public crash dataset lacks vehicle telemetry (delta-V, impact angle in degrees, vehicle mass ratio, restraint pretensioner firing) and medical records (pre-existing conditions, trauma bay triage scores), capping achievable ROC-AUC below $\sim 0.72$.
6. **Zero Causal Inference:** Observational correlation between roadway lighting and injury does not imply that installing overhead luminaires will reduce severe crashes by the odds ratio coefficient.
7. **Prohibition of Production Deployment:** All models remain `NOT_APPROVED_FOR_PRODUCTION`. Retrospective severity scores must not be displayed as live predictions on the frontend interface.
