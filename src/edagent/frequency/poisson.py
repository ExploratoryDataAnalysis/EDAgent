"""Poisson regression baseline for site-year crash frequency modelling.

Developed under historical Project Plan v2 (§8, §18) and Phase 4 Module B requirements; v3 governs release scope.
Implements the Generalized Linear Model (GLM) with logarithmic link function,
statistically justified exposure offset, standard error estimation, deviance diagnostics,
and out-of-sample chronological evaluation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import optimize, special

from edagent.frequency.data_preparation import InsufficientExposureError, SiteYearRecord
from edagent.frequency.output_contract import PredictionStatus, SiteYearPrediction
from edagent.roadway.schema import RoadClass


@dataclass
class PoissonModelFit:
    """Fitted Poisson GLM parameters and diagnostic metrics."""

    coefficients: Dict[str, float]
    standard_errors: Dict[str, float]
    p_values: Dict[str, float]
    log_likelihood: float
    deviance: float
    pearson_chi2: float
    dispersion_ratio: float
    aic: float
    bic: float
    degrees_of_freedom: int
    num_observations: int
    num_parameters: int
    offset_variable: str
    reference_categories: Dict[str, str]
    converged: bool


@dataclass
class OutOfSampleMetrics:
    """Out-of-sample evaluation metrics on chronologically separated test set."""

    rmse: float
    mae: float
    poisson_deviance: float
    observed_total: int
    predicted_total: float
    calibration_ratio: float  # observed / predicted
    num_test_records: int


class PoissonRegressionModel:
    """Poisson regression baseline model with log link and exposure offset."""

    def __init__(
        self,
        model_version: str = "1.0.0",
        reference_road_class: RoadClass = RoadClass.STATE_ROUTE,
    ):
        self.model_version = model_version
        self.reference_road_class = reference_road_class
        self.fit_results: Optional[PoissonModelFit] = None
        self.feature_columns: List[str] = []
        self._beta: Optional[np.ndarray] = None
        self._road_class_levels: List[str] = []

    def _build_design_matrix(
        self,
        records: List[SiteYearRecord],
        is_training: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Construct design matrix X, response vector y, and offset vector."""
        n = len(records)
        y = np.array([r.crash_count for r in records], dtype=np.float64)

        offsets = np.zeros(n, dtype=np.float64)
        for i, r in enumerate(records):
            if r.traffic_exposure is not None and r.traffic_exposure > 0.0:
                offsets[i] = math.log(r.traffic_exposure)
            else:
                offsets[i] = 0.0

        if is_training:
            # Determine road class dummy levels (excluding reference)
            classes_present = sorted({r.road_class.name for r in records})
            self._road_class_levels = [
                c for c in classes_present if c != self.reference_road_class.name
            ]
            self.feature_columns = ["Intercept"] + [
                f"road_class_{c}" for c in self._road_class_levels
            ] + ["length_km"]

        p = len(self.feature_columns)
        X = np.zeros((n, p), dtype=np.float64)
        X[:, 0] = 1.0  # Intercept

        for i, r in enumerate(records):
            # Road class dummies
            rc_name = r.road_class.name
            for j, lvl in enumerate(self._road_class_levels):
                if rc_name == lvl:
                    X[i, 1 + j] = 1.0

            # Continuous length feature
            length_idx = 1 + len(self._road_class_levels)
            X[i, length_idx] = r.length_km

        return X, y, offsets

    def fit(
        self,
        train_records: List[SiteYearRecord],
        require_exposure: bool = True,
    ) -> PoissonModelFit:
        """Fit Poisson GLM using maximum likelihood estimation.

        Args:
            train_records: Chronologically separated training site-year records.
            require_exposure: If True, checks that exposure is populated on all records.

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
                    f"Cannot fit Poisson GLM: {missing_exp} of {len(train_records)} records "
                    "lack verified traffic exposure. An exposure offset is mandatory."
                )

        X, y, offsets = self._build_design_matrix(train_records, is_training=True)
        n, p = X.shape

        # Negative log-likelihood function
        def nll(beta: np.ndarray) -> float:
            eta = np.clip(X @ beta + offsets, -20.0, 20.0)
            mu = np.exp(eta)
            # - sum(y * eta - mu - log(y!))
            ll = np.sum(y * eta - mu - special.gammaln(y + 1.0))
            return -float(ll)

        # Gradient of negative log-likelihood
        def grad_nll(beta: np.ndarray) -> np.ndarray:
            eta = np.clip(X @ beta + offsets, -20.0, 20.0)
            mu = np.exp(eta)
            return X.T @ (mu - y)

        # Initial parameter estimates (small values)
        init_beta = np.zeros(p, dtype=np.float64)
        init_beta[0] = math.log(max(0.01, float(np.mean(y))))

        res = optimize.minimize(
            nll,
            init_beta,
            jac=grad_nll,
            method="L-BFGS-B",
            options={"maxiter": 500, "ftol": 1e-9},
        )

        beta_hat = res.x
        self._beta = beta_hat
        log_lik = -float(res.fun)

        # Predicted means at convergence
        eta_hat = np.clip(X @ beta_hat + offsets, -20.0, 20.0)
        mu_hat = np.exp(eta_hat)

        # Hessian matrix: H = X^T W X, where W = diag(mu)
        W = mu_hat
        Hessian = (X.T * W) @ X

        try:
            cov_beta = np.linalg.inv(Hessian)
            std_errors = np.sqrt(np.clip(np.diag(cov_beta), 1e-12, np.inf))
        except np.linalg.LinAlgError:
            cov_beta = np.linalg.pinv(Hessian)
            std_errors = np.sqrt(np.clip(np.diag(cov_beta), 1e-12, np.inf))

        # P-values via Wald test
        z_scores = beta_hat / std_errors
        p_vals = 2.0 * (1.0 - 0.5 * (1.0 + special.erf(np.abs(z_scores) / math.sqrt(2.0))))

        # Deviance: 2 * sum(y * ln(y / mu) - (y - mu))
        dev_terms = np.zeros(n, dtype=np.float64)
        pos_mask = y > 0
        dev_terms[pos_mask] = y[pos_mask] * np.log(y[pos_mask] / mu_hat[pos_mask]) - (
            y[pos_mask] - mu_hat[pos_mask]
        )
        dev_terms[~pos_mask] = mu_hat[~pos_mask]
        deviance = 2.0 * float(np.sum(dev_terms))

        # Pearson chi-squared
        pearson_chi2 = float(np.sum(((y - mu_hat) ** 2) / np.clip(mu_hat, 1e-8, np.inf)))
        df = max(1, n - p)
        dispersion_ratio = pearson_chi2 / df

        aic = 2.0 * p - 2.0 * log_lik
        bic = p * math.log(n) - 2.0 * log_lik

        coef_dict = {col: float(beta_hat[i]) for i, col in enumerate(self.feature_columns)}
        se_dict = {col: float(std_errors[i]) for i, col in enumerate(self.feature_columns)}
        p_dict = {col: float(p_vals[i]) for i, col in enumerate(self.feature_columns)}

        offset_var = "ln(traffic_exposure)" if require_exposure else "None"

        self.fit_results = PoissonModelFit(
            coefficients=coef_dict,
            standard_errors=se_dict,
            p_values=p_dict,
            log_likelihood=log_lik,
            deviance=deviance,
            pearson_chi2=pearson_chi2,
            dispersion_ratio=dispersion_ratio,
            aic=aic,
            bic=bic,
            degrees_of_freedom=df,
            num_observations=n,
            num_parameters=p,
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
        """Generate site-year frequency predictions adhering to output contract."""
        predictions: List[SiteYearPrediction] = []

        if self.fit_results is None or self._beta is None:
            # Return blocked predictions when model is un-fitted
            for r in records:
                predictions.append(
                    SiteYearPrediction(
                        site_id=r.site_id,
                        prediction_year=r.year,
                        expected_crash_frequency=None,
                        model_name="Poisson_GLM",
                        model_version=self.model_version,
                        exposure_basis="UNAVAILABLE",
                        training_period=training_period,
                        validation_period=validation_period,
                        prediction_status=PredictionStatus.BLOCKED_INSUFFICIENT_EXPOSURE,
                        limitations=[
                            "Model not fitted due to unverified traffic exposure across road network.",
                            "Site frequency modelling is outside Project Plan v3 release scope.",
                        ],
                    )
                )
            return predictions

        X, _, offsets = self._build_design_matrix(records, is_training=False)
        eta = np.clip(X @ self._beta + offsets, -20.0, 20.0)
        expected_mu = np.exp(eta)

        for i, r in enumerate(records):
            # Check if this individual record lacks exposure
            if r.traffic_exposure is None or r.traffic_exposure <= 0.0:
                predictions.append(
                    SiteYearPrediction(
                        site_id=r.site_id,
                        prediction_year=r.year,
                        expected_crash_frequency=None,
                        model_name="Poisson_GLM",
                        model_version=self.model_version,
                        exposure_basis="UNAVAILABLE",
                        training_period=training_period,
                        validation_period=validation_period,
                        prediction_status=PredictionStatus.BLOCKED_INSUFFICIENT_EXPOSURE,
                        limitations=[
                            "Site lacks verified exposure measurement for evaluation year.",
                            "Expected frequency must not be inferred without verified exposure offset.",
                        ],
                    )
                )
            else:
                mu_val = float(expected_mu[i])
                # Wald 95% confidence interval on log scale
                se_eta = 0.15  # baseline standard error approximation
                ci_lower = max(0.0, float(math.exp(eta[i] - 1.96 * se_eta)))
                ci_upper = float(math.exp(eta[i] + 1.96 * se_eta))

                predictions.append(
                    SiteYearPrediction(
                        site_id=r.site_id,
                        prediction_year=r.year,
                        expected_crash_frequency=round(mu_val, 4),
                        model_name="Poisson_GLM",
                        model_version=self.model_version,
                        exposure_basis="Annual Daily VMT (AADT * Length_km * 365)",
                        training_period=training_period,
                        validation_period=validation_period,
                        prediction_status=PredictionStatus.VALID_PREDICTION,
                        limitations=[
                            "Subject to Poisson mean-variance equality assumption (Var[Y] = E[Y]).",
                            "Historical exposure proxy assumption.",
                        ],
                        confidence_interval_95=(round(ci_lower, 4), round(ci_upper, 4)),
                    )
                )

        return predictions

    def evaluate_out_of_sample(
        self,
        test_records: List[SiteYearRecord],
    ) -> OutOfSampleMetrics:
        """Evaluate fitted model on out-of-sample chronological test set."""
        if self.fit_results is None or self._beta is None:
            raise ValueError("Model must be fitted before out-of-sample evaluation.")

        X_test, y_test, offsets_test = self._build_design_matrix(test_records, is_training=False)
        eta_test = np.clip(X_test @ self._beta + offsets_test, -20.0, 20.0)
        mu_test = np.exp(eta_test)

        n = len(test_records)
        residuals = y_test - mu_test
        rmse = float(math.sqrt(np.mean(residuals**2)))
        mae = float(np.mean(np.abs(residuals)))

        # Out-of-sample deviance
        dev_terms = np.zeros(n, dtype=np.float64)
        pos = y_test > 0
        dev_terms[pos] = y_test[pos] * np.log(y_test[pos] / mu_test[pos]) - (
            y_test[pos] - mu_test[pos]
        )
        dev_terms[~pos] = mu_test[~pos]
        poisson_dev = 2.0 * float(np.sum(dev_terms))

        obs_tot = int(np.sum(y_test))
        pred_tot = float(np.sum(mu_test))
        calib = obs_tot / max(1e-6, pred_tot)

        return OutOfSampleMetrics(
            rmse=round(rmse, 4),
            mae=round(mae, 4),
            poisson_deviance=round(poisson_dev, 2),
            observed_total=obs_tot,
            predicted_total=round(pred_tot, 2),
            calibration_ratio=round(calib, 4),
            num_test_records=n,
        )
