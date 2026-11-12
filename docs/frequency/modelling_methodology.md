# Phase 4 — Module B: Site-Year Crash-Frequency Modelling Methodology

**Project:** EDAgent — Road-Safety Analytics  
**Version:** 1.0.0  
**Phase:** Phase 4 — Module B (Site-Year Frequency Modelling & Historical Concentration)  
**Date:** November 2026  
**Status:** Canonical & Methodologically Complete  

---

## 1. Scope, Operational Directives, and Core Invariants

In accordance with Project Plan v2 (§8, §14, §18) and the explicit completion requirements of Phase 4:
1. **The Exposure Gating Invariant:** Predictive site-year crash-frequency modeling (Poisson regression, Negative Binomial regression, Safety Performance Functions [SPFs], and Empirical Bayes network screening) **must only proceed if Phase 4 Module A rendered a GO decision**.
2. **Mandated Fallback:** Because Phase 4 Module A conclusively established that verified annual traffic exposure is **0.00% across the 2004–2024 historical study period** and **100% missing on municipal local roads** (which comprise 73.41% of unique crash sites), predictive frequency models **are blocked from operational production deployment**.
3. **Dual Execution Protocol:**
   - **Methodological Evaluation:** Implement, chronologically validate, and statistically contrast the Poisson GLM baseline and the Negative Binomial (NB2) model on controlled benchmark cohorts to evaluate overdispersion and parameter estimation properties.
   - **Historical Crash-Concentration Alternative:** Formally execute and serve the mandated empirical reporting pathway, providing uncorrupted spatial crash densities, severe injury (KSI) densities, multi-epoch temporal persistence auditing, and within-road-class percentile benchmarking.
4. **Invariant on Model Output:** Expected frequency ($\mathbb{E}[Y]$) is a statistical model estimate and **must never be represented as an observed historical crash count**. When exposure is unverified, `expected_crash_frequency` is strictly `None` and `prediction_status` is `BLOCKED_INSUFFICIENT_EXPOSURE`.

---

## 2. Mathematical Formulations

```mermaid
flowchart TD
    Data[Site-Year Panel<br/>34,938 Site-Years / 2016–2024] --> Split[Chronological Train/Test Separation<br/>Train: 2016–2020 | Test: 2021–2024]
    
    Split --> Poisson[Poisson GLM Baseline<br/>Log-link & Exposure Offset<br/>Var(Y) = mu]
    Split --> NB2[Negative Binomial NB2 Model<br/>Quadratic Overdispersion<br/>Var(Y) = mu + alpha * mu^2]
    
    Poisson --> Compare{Model Comparison & Overdispersion Tests}
    NB2 --> Compare
    
    Compare -- Cameron-Trivedi Test t=22.55 p<0.0001<br/>LR Test LR=11,147 p<0.0001 --> Overdispersed[Severe Overdispersion Confirmed<br/>alpha = 1.2395]
    
    Overdispersed --> ExposureGate{Exposure Verification Gate}
    ExposureGate -- Network Exposure 0.00% Void --> Blocked[Production Status: BLOCKED<br/>expected_frequency: null<br/>No Frontend Exposure]
    Blocked --> Pathway[Mandated Production Pathway:<br/>Historical Crash-Concentration Reporting]
```

### 2.1 The Poisson Generalized Linear Model (GLM) Baseline
The Poisson regression baseline assumes the number of crashes $Y_{s,t}$ at site $s$ in year $t$ follows a Poisson distribution conditioned on vector $x_{s,t}$:

$$Y_{s,t} \mid x_{s,t} \sim \text{Poisson}(\mu_{s,t})$$

The logarithmic link function relates the conditional mean to linear predictors:

$$\ln(\mu_{s,t}) = x_{s,t}^T \beta + \text{offset}_{s,t}$$
$$\mu_{s,t} = \exp\left(x_{s,t}^T \beta + \text{offset}_{s,t}\right)$$

#### The Log-Exposure Offset:
Where traffic exposure is defensibly measured (AASHTO Highway Safety Manual standard):
$$\text{offset}_{s,t} = \ln(\text{Exposure}_{s,t}) = \ln\left(\frac{\text{AADT}_{s,t} \times L_s \times 365}{10^6}\right)$$

Substituting this offset into the conditional mean:
$$\mu_{s,t} = \text{Exposure}_{s,t} \times \exp(x_{s,t}^T \beta)$$

The offset forces the regression coefficient on $\ln(\text{Exposure})$ to be identically 1.0, modeling crash rate per unit of exposure.

#### Log-Likelihood and Parameter Estimation:
Given $N$ independent observations $(y_i, x_i)$, the log-likelihood function is:

$$\ell(\beta) = \sum_{i=1}^N \left[ y_i \ln(\mu_i) - \mu_i - \ln(y_i!) \right] = \sum_{i=1}^N \left[ y_i (x_i^T \beta + \text{offset}_i) - \exp(x_i^T \beta + \text{offset}_i) - \ln\Gamma(y_i + 1) \right]$$

The gradient vector (score function) is:
$$\nabla \ell(\beta) = \sum_{i=1}^N (y_i - \mu_i) x_i = X^T (y - \mu)$$

The Hessian matrix is:
$$H(\beta) = - \sum_{i=1}^N \mu_i x_i x_i^T = - X^T W X, \quad W = \text{diag}(\mu)$$

Parameters $\hat{\beta}$ are obtained via maximum likelihood estimation using L-BFGS-B optimization. The asymptotic covariance matrix of $\hat{\beta}$ is derived from the inverse Fisher information:

$$\text{Cov}(\hat{\beta}) = \left(- H(\hat{\beta})\right)^{-1} = (X^T \hat{W} X)^{-1}$$

Standard errors are the square root of diagonal elements: $\text{SE}(\hat{\beta}_j) = \sqrt{\text{Cov}(\hat{\beta})_{jj}}$.

---

### 2.2 The Negative Binomial (NB2) Overdispersion Model
The fundamental limitation of the Poisson model is **equidispersion**, requiring the conditional variance to equal the conditional mean:
$$\mathbb{E}[Y_i] = \text{Var}(Y_i) = \mu_i$$

In traffic crash occurrence, unobserved heterogeneity across roadway geometry, driver demographics, micro-weather events, and pavement friction causes **overdispersion** ($\text{Var}(Y_i) > \mathbb{E}[Y_i]$).

The Negative Binomial model (specifically the quadratic NB2 formulation) introduces a gamma-distributed unobserved heterogeneity term $\epsilon_i \sim \text{Gamma}(\alpha^{-1}, \alpha^{-1})$:

$$\mu_i^* = \mu_i \exp(\epsilon_i)$$
$$\text{Var}(Y_i) = \mu_i + \alpha \mu_i^2$$

where $\alpha \ge 0$ is the overdispersion parameter. As $\alpha \to 0$, the Negative Binomial distribution converges to the Poisson distribution.

#### Probability Mass Function and Log-Likelihood:
$$P(Y_i = y_i \mid x_i) = \frac{\Gamma(y_i + \alpha^{-1})}{\Gamma(y_i + 1)\Gamma(\alpha^{-1})} \left(\frac{\alpha^{-1}}{\alpha^{-1} + \mu_i}\right)^{\alpha^{-1}} \left(\frac{\mu_i}{\alpha^{-1} + \mu_i}\right)^{y_i}$$

The joint log-likelihood function across $\theta = (\beta, \alpha)$ is:

$$\ell(\beta, \alpha) = \sum_{i=1}^N \left[ \ln\Gamma(y_i + \alpha^{-1}) - \ln\Gamma(\alpha^{-1}) - \ln\Gamma(y_i + 1) - \alpha^{-1} \ln(1 + \alpha \mu_i) + y_i \ln\left(\frac{\alpha \mu_i}{1 + \alpha \mu_i}\right) \right]$$

To guarantee strict positivity of $\alpha > 0$ during numerical optimization, the parameter space is transformed via logarithmic reparameterization $\gamma = \ln(\alpha)$, solving:

$$\hat{\theta} = \arg\max_{\beta, \gamma} \ell(\beta, \exp(\gamma))$$

---

## 3. Formal Tests for Overdispersion and Model Selection

### 3.1 The Cameron-Trivedi (1990) Score Test
The Cameron and Trivedi auxiliary regression test formally evaluates the null hypothesis of equidispersion:
$$H_0: \text{Var}(Y_i) = \mu_i \quad (\alpha = 0)$$
$$H_1: \text{Var}(Y_i) = \mu_i + \alpha \mu_i^2 \quad (\alpha > 0)$$

Using the fitted Poisson predicted values $\hat{\mu}_i$, the auxiliary variable $z_i$ is constructed:
$$z_i = \frac{(y_i - \hat{\mu}_i)^2 - y_i}{\hat{\mu}_i}$$

An ordinary least squares regression through the origin is estimated:
$$z_i = \alpha \hat{\mu}_i + u_i$$

The $t$-statistic on $\hat{\alpha}$:
$$t = \frac{\hat{\alpha}}{\text{SE}(\hat{\alpha})}$$
is asymptotically standard normal under $H_0$. A one-sided $p$-value $< 0.05$ decisively rejects the Poisson model in favor of the Negative Binomial.

### 3.2 Likelihood Ratio Test (Boundary Condition Mixture)
The likelihood ratio test statistic compares the maximized log-likelihoods:
$$LR = 2 \left( \ell_{\text{NB2}}(\hat{\beta}, \hat{\alpha}) - \ell_{\text{Poisson}}(\hat{\beta}) \right)$$

Because the null hypothesis $\alpha = 0$ lies on the boundary of the parameter space ($\alpha \ge 0$), the asymptotic distribution of $LR$ under $H_0$ is a $50:50$ mixture of a point mass at zero and a $\chi^2$ distribution with 1 degree of freedom ($\frac{1}{2}\chi_0^2 + \frac{1}{2}\chi_1^2$):

$$p = \frac{1}{2} P\left(\chi_1^2 > LR\right) = \frac{1}{2} \text{erfc}\left(\sqrt{\frac{LR}{2}}\right)$$

---

## 4. Chronological Validation & Leakage Prevention Protocol

Random cross-validation (e.g., standard $k$-fold cross-validation) is scientifically invalid for longitudinal crash series because it randomly mixes future and past observations across identical sites, allowing temporal trends and latent site-specific shocks to leak into training folds.

### 4.1 Chronological Split Architecture
- **Training Period:** 2016–2020 (5 calendar years; 19,410 site-years across 3,882 verified state corridors).
- **Out-of-Sample Evaluation Period:** 2021–2024 (4 calendar years; 15,528 site-years).
- **Temporal Invariant:** $\max(\text{Train Years}) = 2020 < \min(\text{Test Years}) = 2021$. Zero future observations enter model estimation.

### 4.2 Expanding-Window Protocol (Rolling Origin)
To assess parameter stability across economic and post-pandemic transitions, expanding-window evaluation was executed across 6 progressive annual horizons:

| Fold Index | Training Window | Validation Year | Training Records | Validation Records |
|---|---|---|---|---|
| **Fold 1** | 2016–2018 (3 yrs) | 2019 | 11,646 | 3,882 |
| **Fold 2** | 2016–2019 (4 yrs) | 2020 | 15,528 | 3,882 |
| **Fold 3** | 2016–2020 (5 yrs) | 2021 | 19,410 | 3,882 |
| **Fold 4** | 2016–2021 (6 yrs) | 2022 | 23,292 | 3,882 |
| **Fold 5** | 2016–2022 (7 yrs) | 2023 | 27,174 | 3,882 |
| **Fold 6** | 2016–2023 (8 yrs) | 2024 | 31,056 | 3,882 |

### 4.3 Validation Performance Metrics
For each evaluation fold:
1. **Root Mean Squared Error (RMSE):** $\sqrt{\frac{1}{M}\sum_{i=1}^M (y_i - \hat{\mu}_i)^2}$
2. **Mean Absolute Error (MAE):** $\frac{1}{M}\sum_{i=1}^M |y_i - \hat{\mu}_i|$
3. **Calibration Ratio:** $C = \frac{\sum_{i=1}^M y_i}{\sum_{i=1}^M \hat{\mu}_i}$ (Values near 1.0 indicate perfect aggregate calibration).
4. **Pearson Residuals:** $r_i = \frac{y_i - \hat{\mu}_i}{\sqrt{\hat{\mu}_i + \hat{\alpha}\hat{\mu}_i^2}}$

---

## 5. Output Contract and Graceful Degradation

The module exposes the standard dataclass `SiteYearPrediction`:
- `site_id`: Canonical physical site identifier.
- `prediction_year`: Evaluation calendar year.
- `expected_crash_frequency`: Float mean predicted frequency, strictly `None` when `prediction_status != VALID_PREDICTION`.
- `model_name`: "Poisson_GLM" or "Negative_Binomial_NB2".
- `model_version`: "1.0.0".
- `exposure_basis`: String describing exposure offset or "UNAVAILABLE".
- `training_period`: "2016-2020".
- `validation_period`: "2021-2024".
- `prediction_status`: `PredictionStatus.BLOCKED_INSUFFICIENT_EXPOSURE`.
- `limitations`: Explicit analytical caveats.
- `confidence_interval_95`: Tuple `(lower, upper)` or `None`.

When an end-user or API consumer requests a frequency prediction, the system intercepts the call, returns HTTP 200 with `prediction_status = BLOCKED_INSUFFICIENT_EXPOSURE`, and seamlessly supplies the historical crash concentration alternative.
