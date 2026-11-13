"""Negative Binomial (NB2) regression model and overdispersion evaluation.

Developed under historical Project Plan v2 (§8, §18) and Phase 4 Module B requirements; v3 governs release scope.
Evaluates empirical overdispersion against the Poisson baseline using the Cameron-Trivedi
score test, estimates the quadratic dispersion parameter alpha, and compares models
across AIC, log-likelihood, dispersion ratio, and chronological out-of-sample performance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import optimize, special

from edagent.frequency.data_preparation import InsufficientExposureError, SiteYearRecord
from edagent.frequency.output_contract import PredictionStatus, SiteYearPrediction
from edagent.frequency.poisson import PoissonModelFit, PoissonRegressionModel
from edagent.roadway.schema import RoadClass


@dataclass
class NegativeBinomialFit:
    """Fitted Negative Binomial parameters and comparative diagnostics."""

    coefficients: Dict[str, float]
    standard_errors: Dict[str, float]
    p_values: Dict[str, float]
    alpha: float  # Overdispersion parameter: Var(Y) = mu + alpha * mu^2
    alpha_standard_error: float
    log_likelihood: float
    deviance: float
    pearson_chi2: float
    dispersion_ratio: float
    aic: float
    bic: float
    degrees_of_freedom: int
    num_observations: int
    num_parameters: int
    cameron_trivedi_t_stat: float
    cameron_trivedi_p_value: float
    lr_test_vs_poisson: float  # Likelihood ratio test statistic
    lr_p_value: float
    offset_variable: str
    reference_categories: Dict[str, str]
    converged: bool


@dataclass
class ModelComparisonReport:
    """Rigorous comparison between Poisson baseline and Negative Binomial model."""

    poisson_log_lik: float
    nb_log_lik: float
    poisson_aic: float
    nb_aic: float
    poisson_bic: float
    nb_bic: float
    poisson_dispersion: float
    nb_dispersion: float
    alpha: float
    cameron_trivedi_p_val: float
    lr_statistic: float
    lr_p_value: float
    poisson_test_rmse: float
    nb_test_rmse: float
    poisson_test_mae: float
    nb_test_mae: float
    poisson_calibration: float
    nb_calibration: float
    recommended_model: str
    selection_justification: str


class NegativeBinomialModel:
    """Negative Binomial (NB2) model with quadratic variance Var(Y) = mu + alpha * mu^2."""

    def __init__(
        self,
        model_version: str = "1.0.0",
        reference_road_class: RoadClass = RoadClass.STATE_ROUTE,
    ):
        self.model_version = model_version
        self.reference_road_class = reference_road_class
        self.fit_results: Optional[NegativeBinomialFit] = None
        self.feature_columns: List[str] = []
        self._beta: Optional[np.ndarray] = None
        self._alpha: Optional[float] = None
        self._road_class_levels: List[str] = []

    def _build_design_matrix(
        self,
        records: List[SiteYearRecord],
        is_training: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Construct design matrix X, response vector y, and log-offset vector."""
        n = len(records)
        y = np.array([r.crash_count for r in records], dtype=np.float64)

        offsets = np.zeros(n, dtype=np.float64)
        for i, r in enumerate(records):
            if r.traffic_exposure is not None and r.traffic_exposure > 0.0:
                offsets[i] = math.log(r.traffic_exposure)
            else:
                offsets[i] = 0.0

        if is_training:
            classes_present = sorted({r.road_class.name for r in records})
            self._road_class_levels = [
                c for c in classes_present if c != self.reference_road_class.name
            ]
            self.feature_columns = ["Intercept"] + [
                f"road_class_{c}" for c in self._road_class_levels
            ] + ["length_km"]

        p = len(self.feature_columns)
        X = np.zeros((n, p), dtype=np.float64)
        X[:, 0] = 1.0

        for i, r in enumerate(records):
            rc_name = r.road_class.name
            for j, lvl in enumerate(self._road_class_levels):
                if rc_name == lvl:
                    X[i, 1 + j] = 1.0

            length_idx = 1 + len(self._road_class_levels)
            X[i, length_idx] = r.length_km

        return X, y, offsets

    def fit(
        self,
        train_records: List[SiteYearRecord],
        require_exposure: bool = True,
        poisson_baseline: Optional[PoissonRegressionModel] = None,
    ) -> NegativeBinomialFit:
        """Fit Negative Binomial (NB2) model via Maximum Likelihood Estimation.

        Args:
            train_records: Chronologically separated training site-year records.
            require_exposure: If True, checks that exposure is populated on all records.
            poisson_baseline: Optional pre-fitted Poisson model for comparative tests.

        Raises:
            InsufficientExposureError: If require_exposure is True and exposure is missing.
        """
        if not train_records:
            raise ValueError("train_records cannot be empty.")

        if require_exposure:
            missing_exp = sum(
                1 for r in train_records if r.traffic_exposure is None or r.traffic_exposure <= 0.0
            )
            if missing_exp > 0:
                raise InsufficientExposureError(
                    f"Cannot fit Negative Binomial: {missing_exp} of {len(train_records)} records "
                    "lack verified traffic exposure."
                )

        # Fit Poisson baseline if not provided
        if poisson_baseline is None or poisson_baseline.fit_results is None:
            poisson_model = PoissonRegressionModel(
                reference_road_class=self.reference_road_class
            )
            poisson_fit = poisson_model.fit(train_records, require_exposure=require_exposure)
        else:
            poisson_model = poisson_baseline
            poisson_fit = poisson_baseline.fit_results

        X, y, offsets = self._build_design_matrix(train_records, is_training=True)
        n, p = X.shape

        # Initial beta from Poisson
        init_beta = np.array([poisson_fit.coefficients[col] for col in self.feature_columns])
        eta_init = np.clip(X @ init_beta + offsets, -20.0, 20.0)
        mu_init = np.exp(eta_init)

        # Cameron-Trivedi (1990) Auxiliary Regression for Overdispersion Test
        # Test: ((y - mu)^2 - y) / mu = alpha * mu + e
        lhs = ((y - mu_init) ** 2 - y) / np.clip(mu_init, 1e-8, np.inf)
        rhs = mu_init
        denom = float(np.sum(rhs**2))
        alpha_init = max(0.01, float(np.sum(lhs * rhs) / max(1e-12, denom)))

        # T-statistic for Cameron-Trivedi test
        residuals_ct = lhs - alpha_init * rhs
        var_alpha = float(np.sum(residuals_ct**2) / (max(1, n - 1) * denom))
        se_alpha_ct = math.sqrt(max(1e-12, var_alpha))
        t_stat_ct = alpha_init / se_alpha_ct
        p_val_ct = 1.0 - 0.5 * (1.0 + special.erf(t_stat_ct / math.sqrt(2.0)))

        # Optimize joint log-likelihood over theta = [beta_0, ..., beta_{p-1}, ln(alpha)]
        # Parameterizing ln(alpha) ensures alpha is strictly positive.
        init_theta = np.zeros(p + 1, dtype=np.float64)
        init_theta[:p] = init_beta
        init_theta[p] = math.log(max(1e-4, alpha_init))

        def nb_nll(theta: np.ndarray) -> float:
            beta = theta[:p]
            log_a = theta[p]
            a = math.exp(np.clip(log_a, -10.0, 5.0))
            inv_a = 1.0 / a

            eta = np.clip(X @ beta + offsets, -20.0, 20.0)
            mu = np.exp(eta)

            # NB2 Log-Likelihood:
            # sum( ln_gamma(y + 1/a) - ln_gamma(1/a) - ln_gamma(y + 1)
            #      - (1/a)*ln(1 + a*mu) + y*ln(a*mu / (1 + a*mu)) )
            log_term = np.log1p(a * mu)
            ll_terms = (
                special.gammaln(y + inv_a)
                - special.gammaln(inv_a)
                - special.gammaln(y + 1.0)
                - inv_a * log_term
                + y * (np.log(np.clip(a * mu, 1e-12, np.inf)) - log_term)
            )
            return -float(np.sum(ll_terms))

        res = optimize.minimize(
            nb_nll,
            init_theta,
            method="L-BFGS-B",
            options={"maxiter": 600, "ftol": 1e-9},
        )

        theta_hat = res.x
        beta_hat = theta_hat[:p]
        alpha_hat = float(math.exp(np.clip(theta_hat[p], -10.0, 5.0)))
        log_lik_nb = -float(res.fun)

        self._beta = beta_hat
        self._alpha = alpha_hat

        # Predicted means at convergence
        eta_hat = np.clip(X @ beta_hat + offsets, -20.0, 20.0)
        mu_hat = np.exp(eta_hat)
        var_y = mu_hat + alpha_hat * (mu_hat**2)

        # Standard errors via numerical Hessian approximation or information matrix
        W_nb = (mu_hat**2) / np.clip(var_y, 1e-12, np.inf)
        Info_beta = (X.T * W_nb) @ X
        try:
            cov_beta = np.linalg.inv(Info_beta)
            std_errors = np.sqrt(np.clip(np.diag(cov_beta), 1e-12, np.inf))
        except np.linalg.LinAlgError:
            cov_beta = np.linalg.pinv(Info_beta)
            std_errors = np.sqrt(np.clip(np.diag(cov_beta), 1e-12, np.inf))

        z_scores = beta_hat / std_errors
        p_vals = 2.0 * (1.0 - 0.5 * (1.0 + special.erf(np.abs(z_scores) / math.sqrt(2.0))))

        # Likelihood ratio test vs Poisson: LR = 2 * (LL_NB - LL_Poisson)
        lr_stat = max(0.0, 2.0 * (log_lik_nb - poisson_fit.log_likelihood))
        # Boundary condition mixture: p-value is 0.5 * P(Chi2(1) > LR)
        lr_p_val = 0.5 * math.erfc(math.sqrt(max(0.0, lr_stat) / 2.0))

        # Pearson Chi-Square & Deviance
        pearson_chi2 = float(np.sum(((y - mu_hat) ** 2) / np.clip(var_y, 1e-8, np.inf)))
        df = max(1, n - (p + 1))
        dispersion_ratio = pearson_chi2 / df

        # Deviance for NB2
        inv_a = 1.0 / alpha_hat
        dev_terms = np.zeros(n, dtype=np.float64)
        pos = y > 0
        dev_terms[pos] = y[pos] * np.log(y[pos] / mu_hat[pos]) - (
            y[pos] + inv_a
        ) * np.log((1.0 + alpha_hat * y[pos]) / (1.0 + alpha_hat * mu_hat[pos]))
        dev_terms[~pos] = -inv_a * np.log(1.0 + alpha_hat * mu_hat[~pos])
        deviance = 2.0 * float(np.sum(dev_terms))

        num_params = p + 1
        aic = 2.0 * num_params - 2.0 * log_lik_nb
        bic = num_params * math.log(n) - 2.0 * log_lik_nb

        coef_dict = {col: float(beta_hat[i]) for i, col in enumerate(self.feature_columns)}
        se_dict = {col: float(std_errors[i]) for i, col in enumerate(self.feature_columns)}
        p_dict = {col: float(p_vals[i]) for i, col in enumerate(self.feature_columns)}

        offset_var = "ln(traffic_exposure)" if require_exposure else "None"

        self.fit_results = NegativeBinomialFit(
            coefficients=coef_dict,
            standard_errors=se_dict,
            p_values=p_dict,
            alpha=round(alpha_hat, 4),
            alpha_standard_error=round(se_alpha_ct, 4),
            log_likelihood=round(log_lik_nb, 2),
            deviance=round(deviance, 2),
            pearson_chi2=round(pearson_chi2, 2),
            dispersion_ratio=round(dispersion_ratio, 4),
            aic=round(aic, 2),
            bic=round(bic, 2),
            degrees_of_freedom=df,
            num_observations=n,
            num_parameters=num_params,
            cameron_trivedi_t_stat=round(t_stat_ct, 4),
            cameron_trivedi_p_value=round(p_val_ct, 6),
            lr_test_vs_poisson=round(lr_stat, 2),
            lr_p_value=round(lr_p_val, 6),
            offset_variable=offset_var,
            reference_categories={"road_class": self.reference_road_class.name},
            converged=bool(res.success),
        )
        return self.fit_results

    def predict(
        self,
        records: List[SiteYearRecord],
        training_period: str = "2016-2020",
        validation_period: str = "2021-2024",
    ) -> List[SiteYearPrediction]:
        """Generate site-year predictions adhering to output contract."""
        predictions: List[SiteYearPrediction] = []

        if self.fit_results is None or self._beta is None or self._alpha is None:
            for r in records:
                predictions.append(
                    SiteYearPrediction(
                        site_id=r.site_id,
                        prediction_year=r.year,
                        expected_crash_frequency=None,
                        model_name="Negative_Binomial_NB2",
                        model_version=self.model_version,
                        exposure_basis="UNAVAILABLE",
                        training_period=training_period,
                        validation_period=validation_period,
                        prediction_status=PredictionStatus.BLOCKED_INSUFFICIENT_EXPOSURE,
                        limitations=[
                            "Negative Binomial model not fitted due to unverified traffic exposure.",
                            "Site frequency modelling is outside Project Plan v3 release scope.",
                        ],
                    )
                )
            return predictions

        X, _, offsets = self._build_design_matrix(records, is_training=False)
        eta = np.clip(X @ self._beta + offsets, -20.0, 20.0)
        expected_mu = np.exp(eta)

        for i, r in enumerate(records):
            if r.traffic_exposure is None or r.traffic_exposure <= 0.0:
                predictions.append(
                    SiteYearPrediction(
                        site_id=r.site_id,
                        prediction_year=r.year,
                        expected_crash_frequency=None,
                        model_name="Negative_Binomial_NB2",
                        model_version=self.model_version,
                        exposure_basis="UNAVAILABLE",
                        training_period=training_period,
                        validation_period=validation_period,
                        prediction_status=PredictionStatus.BLOCKED_INSUFFICIENT_EXPOSURE,
                        limitations=[
                            "Site lacks verified exposure measurement for evaluation year.",
                        ],
                    )
                )
            else:
                mu_val = float(expected_mu[i])
                # Negative Binomial prediction interval incorporates overdispersion alpha
                var_pred = mu_val + self._alpha * (mu_val**2)
                se_pred = math.sqrt(var_pred)
                ci_lower = max(0.0, mu_val - 1.96 * se_pred)
                ci_upper = mu_val + 1.96 * se_pred

                predictions.append(
                    SiteYearPrediction(
                        site_id=r.site_id,
                        prediction_year=r.year,
                        expected_crash_frequency=round(mu_val, 4),
                        model_name="Negative_Binomial_NB2",
                        model_version=self.model_version,
                        exposure_basis="Annual Daily VMT (AADT * Length_km * 365)",
                        training_period=training_period,
                        validation_period=validation_period,
                        prediction_status=PredictionStatus.VALID_PREDICTION,
                        limitations=[
                            f"Assumes quadratic variance Var[Y] = mu + {self._alpha}*mu^2.",
                            "Evaluation proxy exposure.",
                        ],
                        confidence_interval_95=(round(ci_lower, 4), round(ci_upper, 4)),
                    )
                )

        return predictions

    def compare_with_poisson(
        self,
        poisson_model: PoissonRegressionModel,
        test_records: List[SiteYearRecord],
    ) -> ModelComparisonReport:
        """Perform comprehensive comparative evaluation between Poisson and Negative Binomial.

        Does NOT select a model merely because one metric is numerically smaller;
        evaluates theoretical dispersion, statistical tests, and chronological out-of-sample error.
        """
        if self.fit_results is None or poisson_model.fit_results is None:
            raise ValueError("Both models must be fitted before comparison.")

        # Out-of-sample metrics
        poisson_metrics = poisson_model.evaluate_out_of_sample(test_records)

        X_test, y_test, offsets_test = self._build_design_matrix(test_records, is_training=False)
        eta_test = np.clip(X_test @ self._beta + offsets_test, -20.0, 20.0)
        mu_test = np.exp(eta_test)

        residuals_nb = y_test - mu_test
        nb_rmse = float(math.sqrt(np.mean(residuals_nb**2)))
        nb_mae = float(np.mean(np.abs(residuals_nb)))
        nb_calib = float(np.sum(y_test)) / max(1e-6, float(np.sum(mu_test)))

        p_fit = poisson_model.fit_results
        nb_fit = self.fit_results

        # Scientific model recommendation
        is_overdispersed = (
            nb_fit.alpha > 0.05
            and nb_fit.cameron_trivedi_p_value < 0.05
            and nb_fit.lr_p_value < 0.05
        )

        if is_overdispersed:
            rec_model = "Negative_Binomial_NB2"
            justification = (
                f"Significant overdispersion confirmed (alpha={nb_fit.alpha}, "
                f"Cameron-Trivedi p={nb_fit.cameron_trivedi_p_value:.4f}, LR test p={nb_fit.lr_p_value:.4f}). "
                f"AIC improved from {p_fit.aic} to {nb_fit.aic}. Negative Binomial relaxes "
                f"the invalid equidispersions assumption (Poisson dispersion={p_fit.dispersion_ratio:.2f})."
            )
        else:
            rec_model = "Poisson_GLM"
            justification = (
                f"No significant overdispersion detected (alpha={nb_fit.alpha}, p={nb_fit.cameron_trivedi_p_value:.4f}). "
                "Parsimonious Poisson baseline preferred."
            )

        return ModelComparisonReport(
            poisson_log_lik=round(p_fit.log_likelihood, 2),
            nb_log_lik=round(nb_fit.log_likelihood, 2),
            poisson_aic=round(p_fit.aic, 2),
            nb_aic=round(nb_fit.aic, 2),
            poisson_bic=round(p_fit.bic, 2),
            nb_bic=round(nb_fit.bic, 2),
            poisson_dispersion=round(p_fit.dispersion_ratio, 4),
            nb_dispersion=round(nb_fit.dispersion_ratio, 4),
            alpha=round(nb_fit.alpha, 4),
            cameron_trivedi_p_val=round(nb_fit.cameron_trivedi_p_value, 6),
            lr_statistic=round(nb_fit.lr_test_vs_poisson, 2),
            lr_p_value=round(nb_fit.lr_p_value, 6),
            poisson_test_rmse=round(poisson_metrics.rmse, 4),
            nb_test_rmse=round(nb_rmse, 4),
            poisson_test_mae=round(poisson_metrics.mae, 4),
            nb_test_mae=round(nb_mae, 4),
            poisson_calibration=round(poisson_metrics.calibration_ratio, 4),
            nb_calibration=round(nb_calib, 4),
            recommended_model=rec_model,
            selection_justification=justification,
        )
