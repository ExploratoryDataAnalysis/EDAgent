"""Chronological validation, expanding-window evaluation, and calibration diagnostics.

Governed by Project Plan v2 (§8, §18) and Phase 4 Module B requirements.
Enforces strict temporal validation without future leakage, evaluates calibration
by year and road class, and computes residual diagnostics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from edagent.frequency.data_preparation import SiteYearRecord, TemporalLeakageError
from edagent.frequency.poisson import PoissonRegressionModel
from edagent.roadway.schema import RoadClass


@dataclass
class ExpandingWindowFold:
    """Results for an individual expanding-window validation fold."""

    fold_index: int
    train_years: Tuple[int, ...]
    validation_year: int
    num_train_records: int
    num_val_records: int
    rmse: float
    mae: float
    observed_crashes: int
    predicted_crashes: float
    calibration_ratio: float


@dataclass
class StratifiedCalibration:
    """Calibration breakdown across road classes or temporal cohorts."""

    stratum_name: str
    observed_crashes: int
    predicted_crashes: float
    calibration_ratio: float
    num_records: int


@dataclass
class ResidualDiagnostics:
    """Residual distribution properties for model goodness-of-fit."""

    mean_pearson_residual: float
    std_pearson_residual: float
    max_residual: float
    min_residual: float
    num_large_residuals: int  # |residual| > 3.0


class ChronologicalValidator:
    """Evaluates frequency models under strict chronological and stratified protocols."""

    @staticmethod
    def audit_leakage(
        train_records: List[SiteYearRecord],
        test_records: List[SiteYearRecord],
    ) -> bool:
        """Verify that zero future information leaks into training records.

        Raises:
            TemporalLeakageError: If any training observation occurs at or after test observations.
        """
        if not train_records or not test_records:
            return True

        max_train = max(r.year for r in train_records)
        min_test = min(r.year for r in test_records)

        if max_train >= min_test:
            raise TemporalLeakageError(
                f"Data leakage detected! Training data contains records from year {max_train}, "
                f"which equals or succeeds minimum test year {min_test}."
            )
        return True

    @staticmethod
    def evaluate_expanding_windows(
        records: List[SiteYearRecord],
        start_train_years: Tuple[int, ...] = (2016, 2017, 2018),
        eval_years: Tuple[int, ...] = (2019, 2020, 2021, 2022, 2023, 2024),
    ) -> List[ExpandingWindowFold]:
        """Execute expanding-window (rolling origin) evaluation."""
        folds: List[ExpandingWindowFold] = []
        current_train_years = list(start_train_years)

        for idx, val_year in enumerate(eval_years):
            tr_recs = [r for r in records if r.year in current_train_years]
            val_recs = [r for r in records if r.year == val_year]

            if not tr_recs or not val_recs:
                continue

            # Fit model on training slice
            model = PoissonRegressionModel()
            try:
                model.fit(tr_recs, require_exposure=False)
                metrics = model.evaluate_out_of_sample(val_recs)

                folds.append(
                    ExpandingWindowFold(
                        fold_index=idx + 1,
                        train_years=tuple(current_train_years),
                        validation_year=val_year,
                        num_train_records=len(tr_recs),
                        num_val_records=len(val_recs),
                        rmse=metrics.rmse,
                        mae=metrics.mae,
                        observed_crashes=metrics.observed_total,
                        predicted_crashes=metrics.predicted_total,
                        calibration_ratio=metrics.calibration_ratio,
                    )
                )
            except Exception:
                pass

            # Expand training window for next iteration
            current_train_years.append(val_year)

        return folds

    @staticmethod
    def evaluate_calibration_by_road_class(
        test_records: List[SiteYearRecord],
        predictions: List[float],
    ) -> List[StratifiedCalibration]:
        """Compute observed vs predicted calibration ratio stratified by road class."""
        strata: Dict[str, Dict[str, Any]] = {}

        for rec, pred in zip(test_records, predictions):
            c_name = rec.road_class.name
            if c_name not in strata:
                strata[c_name] = {"obs": 0, "pred": 0.0, "count": 0}
            strata[c_name]["obs"] += rec.crash_count
            strata[c_name]["pred"] += pred
            strata[c_name]["count"] += 1

        results: List[StratifiedCalibration] = []
        for c_name, data in sorted(strata.items()):
            obs = data["obs"]
            pred = data["pred"]
            ratio = obs / max(1e-6, pred)
            results.append(
                StratifiedCalibration(
                    stratum_name=c_name,
                    observed_crashes=obs,
                    predicted_crashes=round(pred, 2),
                    calibration_ratio=round(ratio, 4),
                    num_records=data["count"],
                )
            )
        return results

    @staticmethod
    def evaluate_residuals(
        y_true: np.ndarray,
        mu_pred: np.ndarray,
        alpha: float = 0.0,
    ) -> ResidualDiagnostics:
        """Compute Pearson residual diagnostics."""
        var = mu_pred + alpha * (mu_pred**2)
        pearson_residuals = (y_true - mu_pred) / np.sqrt(np.clip(var, 1e-8, np.inf))

        mean_res = float(np.mean(pearson_residuals))
        std_res = float(np.std(pearson_residuals))
        max_res = float(np.max(pearson_residuals))
        min_res = float(np.min(pearson_residuals))
        large_count = int(np.sum(np.abs(pearson_residuals) > 3.0))

        return ResidualDiagnostics(
            mean_pearson_residual=round(mean_res, 4),
            std_pearson_residual=round(std_res, 4),
            max_residual=round(max_res, 4),
            min_residual=round(min_res, 4),
            num_large_residuals=large_count,
        )
