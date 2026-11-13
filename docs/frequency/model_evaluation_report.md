# Phase 4 — Module B: Frequency Model Evaluation & Diagnostic Report

> **Superseded scope:** This report records earlier work and decisions. [Project Plan v3](../EDAgent_Project_Plan_v3.pdf) and the [v3 roadmap](../implementation_plan.md#v3-transition-and-roadmap) govern release scope: site-level historical screening, frequency/EB modelling and real-site treatment estimates are out of scope; geographic matches are diagnostic, with zero accepted primary assignments. Earlier claims of approval, mandatory pathways or pending release describe historical proposals, not current authorization.

**Project:** EDAgent — Road-Safety Analytics  
**Version:** 1.0.0  
**Phase:** Phase 4 — Module B (Site-Year Frequency Modelling & Historical Concentration)  
**Date:** November 2026  
**Status:** Complete Empirical Diagnostic Evaluation  

---

## 1. Executive Summary

This report presents the empirical diagnostic evaluation of the **Poisson Generalized Linear Model (GLM) baseline** and the **Negative Binomial (NB2) model** on the 34,938 site-year longitudinal panel (2016–2024).

In accordance with Project Plan v2 (§8, §18) and the Phase 4 Module A **NO-GO** decision:
1. **Overdispersion is Confirmed:** The Negative Binomial model decisively outperforms the Poisson baseline across every statistical criterion. The overdispersion parameter is estimated at $\hat{\alpha} = 1.2395$ ($t = 22.55, p < 10^{-6}$), and the Bayesian Information Criterion improves by **11,137 points**.
2. **Poisson Equidispersion Assumption Fails:** The Poisson dispersion ratio ($\phi = 2.9379$) heavily violates the theoretical mean-variance equality assumption ($\text{Var}[Y] = \mathbb{E}[Y]$), deflating parameter standard errors and producing falsely narrow confidence bounds.
3. **Production Status is BLOCKED:** Although the Negative Binomial model is methodologically superior to Poisson, **neither model is approved for operational production forecasting** (`NOT_APPROVED_FOR_PRODUCTION_INSUFFICIENT_EXPOSURE`). This is because verified traffic exposure is 100% missing on municipal local roads (73.4% of unique crash sites) and 0.00% annual historical exposure exists across the county.
4. **Mandated Action:** Deploy the **Historical Crash-Concentration Alternative** for all road safety screening, ranking, and API queries.

---

## 2. Statistical Model Comparison (Poisson GLM vs. Negative Binomial NB2)

Both models were fitted on the 19,410 training site-years (2016–2020) and evaluated on the 15,528 out-of-sample chronological test site-years (2021–2024) across 3,882 verified state highway corridors:

| Diagnostic Metric | Poisson GLM Baseline | Negative Binomial (NB2) | Absolute Difference | Better Model | Statistical Interpretation |
|---|---|---|---|:---:|---|
| **Log-Likelihood** ($\ell$) | -35,664.05 | **-30,090.48** | +5,573.57 | **NB2** | Substantially higher likelihood (higher is better). |
| **Akaike Information Criterion (AIC)** | 71,336.10 | **60,190.97** | -11,145.13 | **NB2** | AIC drops by 11,145 points (lower is better; $\Delta \text{AIC} > 10$ is decisive). |
| **Bayesian Information Criterion (BIC)** | 71,367.59 | **60,230.34** | -11,137.25 | **NB2** | Penalizes parameter count ($P \ln N$). Massive evidence favoring NB2. |
| **Dispersion Ratio** ($\phi = \chi^2 / df$) | 2.9379 | **1.1155** | -1.8224 | **NB2** | Poisson exhibits severe overdispersion ($\phi \gg 1.0$). NB2 brings dispersion near 1.0. |
| **Overdispersion Parameter** ($\alpha$) | $0.0000$ *(fixed)* | **1.2395** | +1.2395 | **NB2** | Quadratic variance term: $\text{Var}(Y) = \mu + 1.2395 \mu^2$. |
| **Cameron-Trivedi Score Test** | — | **$t = 22.55, p < 10^{-6}$** | — | **NB2** | Decisively rejects Poisson equidispersion ($H_0: \alpha = 0$). |
| **Likelihood Ratio Test vs. Poisson** | — | **$LR = 11,147.13, p < 10^{-6}$** | — | **NB2** | $\chi_1^2$ mixture test confirms NB2 superiority over Poisson. |
| **Out-of-Sample RMSE (2021–2024)** | 2.0465 | 2.0465 | 0.0000 | Tied | Both models estimate the conditional mean $\mathbb{E}[Y]$. |
| **Out-of-Sample MAE (2021–2024)** | 1.3223 | 1.3223 | 0.0000 | Tied | Mean absolute prediction error across 15,528 test site-years. |
| **Out-of-Sample Calibration Ratio** | 0.8232 | 0.8232 | 0.0000 | Tied | Observed total (17,044 crashes) / Predicted total (20,705 crashes). |

*Table data exported directly from `data/exports/frequency/model_comparison_metrics.csv`.*

```mermaid
flowchart LR
    subgraph Model Comparison
        Poisson[Poisson GLM<br/>AIC: 71,336.1<br/>Dispersion: 2.9379]
        NB2[Negative Binomial NB2<br/>AIC: 60,190.97<br/>Dispersion: 1.1155]
    end
    
    Poisson -. Overdispersion t=22.55 .-> NB2
    NB2 --> Verdict[Statistical Verdict:<br/>NB2 Superior (delta AIC = -11,145)<br/>Overdispersion alpha = 1.2395]
    
    Verdict --> OperationalDecision[Operational Decision:<br/>BLOCKED FOR PRODUCTION<br/>Verified Network Exposure Absent (0%)]
```

---

## 3. Negative Binomial Parameter Estimates and Inference

The parameter estimates for the fitted Negative Binomial (NB2) model are summarized below:

| Feature / Predictor | Estimated Coefficient ($\hat{\beta}$) | Standard Error ($\text{SE}$) | Wald $z$-Statistic | $p$-Value | 95% Confidence Interval |
|---|---|---|---|---|---|
| **Intercept** ($\beta_0$) | **+0.3887** | 0.0092 | +42.23 | $< 0.0001$ | $[+0.3707, +0.4068]$ |
| **Road Class: Interstate** | -0.0390 | 0.0331 | -1.18 | 0.2388 | $[-0.1039, +0.0259]$ |
| **Road Class: Ramp** | **-0.6253** | 0.0360 | -17.38 | $< 0.0001$ | $[-0.6958, -0.5548]$ |
| **Segment Length (km)** | **+0.0505** | 0.0046 | +10.97 | $< 0.0001$ | $[+0.0415, +0.0595]$ |
| **Overdispersion** ($\alpha$) | **1.2395** | 0.0628 | +19.74 | $< 0.0001$ | $[+1.1164, +1.3626]$ |

*Reference category: State Route (`STATE_ROUTE`).*

### Statistical Interpretation:
1. **Ramp Crash Deficit:** Roadway ramps exhibit a statistically significant negative coefficient ($\hat{\beta}_{\text{ramp}} = -0.6253, p < 0.0001$). Exponentiating this coefficient yields a rate multiplier of $\exp(-0.6253) = 0.535$, indicating that highway ramps experience $46.5\%$ fewer crashes per unit length than mainline state routes.
2. **Length Effect:** Physical segment length has a positive, highly significant coefficient ($\hat{\beta}_{\text{length}} = +0.0505, p < 0.0001$), confirming that longer segments accumulate proportionally more crash events.
3. **Severe Overdispersion:** $\hat{\alpha} = 1.2395$ indicates that the variance grows quadratically: at an expected crash count of $\mu = 10$, the variance is $\text{Var}(Y) = 10 + 1.2395(100) = 133.95$, more than thirteen times the Poisson variance assumption.

---

## 4. Chronological Expanding-Window Validation (2019–2024)

To prevent future temporal leakage, expanding-window evaluation was executed across six consecutive annual horizons:

| Fold Index | Training Window | Validation Year | Train Records | Val Records | Observed Crashes | Predicted Crashes | Calibration Ratio ($O/E$) | Out-of-Sample RMSE | Out-of-Sample MAE |
|---|---|---|---|---|---|---|---|---|---|
| **Fold 1** | 2016–2018 | **2019** | 11,646 | 3,882 | 5,342 | 5,418.0 | **0.9860** | 2.1154 | 1.3743 |
| **Fold 2** | 2016–2019 | **2020** | 15,528 | 3,882 | 4,286 | 5,399.0 | **0.7939** | 1.9247 | 1.2938 |
| **Fold 3** | 2016–2020 | **2021** | 19,410 | 3,882 | 5,152 | 5,176.4 | **0.9953** | 2.2951 | 1.3715 |
| **Fold 4** | 2016–2021 | **2022** | 23,292 | 3,882 | 5,318 | 5,172.3 | **1.0282** | 2.1557 | 1.3683 |
| **Fold 5** | 2016–2022 | **2023** | 27,174 | 3,882 | 5,186 | 5,193.1 | **0.9986** | 2.1790 | 1.3327 |
| **Fold 6** | 2016–2023 | **2024** | 31,056 | 3,882 | 1,388 | 5,192.2 | **0.2673** | 1.4609 | 1.2222 |

*Table data exported directly from `data/exports/frequency/chronological_validation_metrics.csv`.*

### Key Insights from Chronological Evaluation:
1. **Exceptional Pre-Pandemic Calibration (2019):** In Fold 1 (pre-COVID), the calibration ratio was **0.9860** (observed 5,342 crashes vs. predicted 5,418.0), demonstrating high stability under baseline travel conditions.
2. **Detection of the COVID-19 Shock (2020):** In Fold 2, the calibration ratio dropped sharply to **0.7939** (observed crashes fell by $20.6\%$ relative to model expectation). This reflects the massive collapse in vehicular travel volume during pandemic lockdowns, which static historical models cannot adjust for in the absence of continuous VMT data.
3. **Rapid Post-Pandemic Rebound (2021–2023):** Folds 3, 4, and 5 demonstrated near-perfect recovery:
   - 2021: Calibration = **0.9953**
   - 2022: Calibration = **1.0282**
   - 2023: Calibration = **0.9986**
4. **The 2024 Truncation Warning:** In Fold 6, observed crashes dropped to 1,388 (calibration 0.2673). As established in `analysis/outputs/eda_summary/findings_review.csv`, the 2024 WPRDC extract contains partial-year crash data and must not be interpreted as an annual observation.

---

## 5. Formal Production Approval Status

Pursuant to the Phase 4 Module A feasibility criteria and Project Plan v2 (§8, §18):

```json
{
  "model_name": "Negative_Binomial_NB2",
  "approval_status": "NOT_APPROVED_FOR_PRODUCTION_INSUFFICIENT_EXPOSURE",
  "manifest_checksum": "f36c59d2ff6442fddfecee3d65495696d4d360a254597fae25fe1c89d22271e1"
}
```

### Rationales for Rejection from Production:
1. **Network Exposure Void:** True annual traffic volume ($AADT_{s,t}$) is 100% missing on municipal roads (73.4% of unique sites).
2. **Jurisdictional Inequity:** Releasing a state-route-only model would systematically erase municipal Vision Zero and pedestrian safety corridors from the analytical dashboard.
3. **Invariant Preservation:** Exposing expected crash frequency ($\mathbb{E}[Y]$) to frontend users without verified exposure violates core project commitments.

**Conclusion:** The backend API and frontend dashboard will exclusively serve the **Historical Crash-Concentration Reporting Pathway** (`data/exports/frequency/historical_crash_concentration.csv`).
