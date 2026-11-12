"""Execution script for Phase 4 Module B: Frequency Modelling & Historical Concentration.

Governed by Project Plan v2 (§8, §18) and Phase 4 Module B requirements.
Prepares chronologically separated modelling data, fits Poisson baseline and Negative
Binomial models on controlled benchmarks, executes expanding-window validation,
evaluates overdispersion, generates model persistence manifests, and exports the
canonical historical crash-concentration dataset.
"""

from __future__ import annotations

import csv
import json
import math
import sys
import time
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path("src").resolve()))

from edagent.frequency.concentration import HistoricalConcentrationAnalyzer
from edagent.frequency.data_preparation import (
    ModellingDataset,
    SiteYearDataPreparer,
    SiteYearRecord,
)
from edagent.frequency.negative_binomial import (
    ModelComparisonReport,
    NegativeBinomialFit,
    NegativeBinomialModel,
)
from edagent.frequency.output_contract import PredictionStatus
from edagent.frequency.persistence import ModelManifest, ModelPersistenceManager
from edagent.frequency.poisson import PoissonModelFit, PoissonRegressionModel
from edagent.frequency.validation import (
    ChronologicalValidator,
    ExpandingWindowFold,
    ResidualDiagnostics,
    StratifiedCalibration,
)
from edagent.roadway.schema import RoadClass


def main() -> None:
    raise RuntimeError(
        "Frequency and concentration release blocked: the crosswalk is not reviewed, "
        "the panel is crash-selected, and nominal exposure and lengths cannot support claims."
    )
    print("=" * 80)
    print("PHASE 4 — MODULE B: SITE-YEAR FREQUENCY MODELLING & HISTORICAL CONCENTRATION")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 1. Historical Crash-Concentration Reporting Pathway (Mandated Alternative)
    # -------------------------------------------------------------------------
    print("\n[Step 1] Executing Historical Crash-Concentration Pathway...")
    t0 = time.time()
    analyzer = HistoricalConcentrationAnalyzer(
        crosswalk_path="data/exports/crosswalk/crosswalk_v1.0.0.csv.gz",
        raw_crash_path="data/raw/2c13021f-74a9-4289-a1e5-fe0472c89881.csv",
    )
    conc_csv = analyzer.export_csv(
        output_path="data/exports/frequency/historical_crash_concentration.csv"
    )
    print(f"  -> Generated {conc_csv} in {time.time() - t0:.2f}s")

    # -------------------------------------------------------------------------
    # 2. Prepare Chronological Modelling Panel
    # -------------------------------------------------------------------------
    print("\n[Step 2] Loading and Validating Site-Year Panel Prototype...")
    prototype_path = Path("data/exports/traffic_exposure/site_year_panel_prototype.csv")
    if not prototype_path.exists():
        print(f"ERROR: {prototype_path} not found.")
        sys.exit(1)

    records_raw = []
    with open(prototype_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            records_raw.append(r)

    print(f"  -> Loaded {len(records_raw):,} site-year records (2016–2024).")

    preparer = SiteYearDataPreparer(
        default_train_years=(2016, 2017, 2018, 2019, 2020),
        default_test_years=(2021, 2022, 2023, 2024),
    )

    # Prepare dataset without requiring exposure (since exposure is strictly absent)
    dataset = preparer.prepare_dataset(records_raw, require_exposure=False)
    print(f"  -> Training records (2016–2020): {len(dataset.train_records):,}")
    print(f"  -> Out-of-sample test records (2021–2024): {len(dataset.test_records):,}")
    print(f"  -> Has valid exposure across network: {dataset.has_valid_exposure}")

    # Audit leakage
    ChronologicalValidator.audit_leakage(dataset.train_records, dataset.test_records)
    print("  -> Temporal leakage audit: PASSED (0% future information in training set).")

    # -------------------------------------------------------------------------
    # 3. Controlled Benchmark Model Fitting & Overdispersion Evaluation
    # -------------------------------------------------------------------------
    print("\n[Step 3] Statistical Model Evaluation (Poisson GLM vs Negative Binomial NB2)...")
    # For rigorous methodological demonstration, provide controlled baseline exposure:
    # Segment length proxy (0.8km for SR, 0.3km for local) * nominal daily traffic
    controlled_train = []
    for r in dataset.train_records:
        nominal_aadt = 12000.0 if r.road_class == RoadClass.INTERSTATE else 4500.0
        exp_val = (nominal_aadt * r.length_km * 365.0) / 1e6  # Million VMT
        controlled_train.append(
            SiteYearRecord(
                site_id=r.site_id,
                year=r.year,
                crash_count=r.crash_count,
                is_zero_crash=r.is_zero_crash,
                road_class=r.road_class,
                length_km=r.length_km,
                traffic_exposure=exp_val,
            )
        )

    controlled_test = []
    for r in dataset.test_records:
        nominal_aadt = 12000.0 if r.road_class == RoadClass.INTERSTATE else 4500.0
        exp_val = (nominal_aadt * r.length_km * 365.0) / 1e6
        controlled_test.append(
            SiteYearRecord(
                site_id=r.site_id,
                year=r.year,
                crash_count=r.crash_count,
                is_zero_crash=r.is_zero_crash,
                road_class=r.road_class,
                length_km=r.length_km,
                traffic_exposure=exp_val,
            )
        )

    # 3a. Fit Poisson baseline
    print("  -> Fitting Poisson GLM baseline...")
    poisson_model = PoissonRegressionModel(reference_road_class=RoadClass.STATE_ROUTE)
    p_fit = poisson_model.fit(controlled_train, require_exposure=True)
    print(f"     * Poisson Log-Likelihood: {p_fit.log_likelihood:.2f}")
    print(f"     * Poisson Deviance: {p_fit.deviance:.2f} (df={p_fit.degrees_of_freedom})")
    print(f"     * Dispersion ratio (phi): {p_fit.dispersion_ratio:.4f}")
    print(f"     * AIC: {p_fit.aic:.2f}, BIC: {p_fit.bic:.2f}")

    # 3b. Fit Negative Binomial (NB2)
    print("  -> Fitting Negative Binomial (NB2) model...")
    nb_model = NegativeBinomialModel(reference_road_class=RoadClass.STATE_ROUTE)
    nb_fit = nb_model.fit(
        controlled_train,
        require_exposure=True,
        poisson_baseline=poisson_model,
    )
    print(f"     * NB2 Log-Likelihood: {nb_fit.log_likelihood:.2f}")
    print(f"     * Overdispersion alpha: {nb_fit.alpha:.4f} (SE={nb_fit.alpha_standard_error:.4f})")
    print(f"     * Cameron-Trivedi test: t={nb_fit.cameron_trivedi_t_stat:.2f}, p={nb_fit.cameron_trivedi_p_value:.6f}")
    print(f"     * Likelihood ratio test vs Poisson: LR={nb_fit.lr_test_vs_poisson:.2f}, p={nb_fit.lr_p_value:.6f}")
    print(f"     * AIC: {nb_fit.aic:.2f}, BIC: {nb_fit.bic:.2f}")

    # 3c. Out-of-sample comparison
    print("  -> Chronological Out-of-Sample Evaluation (2021–2024)...")
    comp_report = nb_model.compare_with_poisson(poisson_model, controlled_test)
    print(f"     * Poisson Test RMSE: {comp_report.poisson_test_rmse:.4f}, MAE: {comp_report.poisson_test_mae:.4f}")
    print(f"     * NB2 Test RMSE: {comp_report.nb_test_rmse:.4f}, MAE: {comp_report.nb_test_mae:.4f}")
    print(f"     * Poisson Calibration Ratio: {comp_report.poisson_calibration:.4f}")
    print(f"     * NB2 Calibration Ratio: {comp_report.nb_calibration:.4f}")
    print(f"     * Selected Recommendation: {comp_report.recommended_model}")

    # -------------------------------------------------------------------------
    # 4. Expanding Window Evaluation & Residual Diagnostics
    # -------------------------------------------------------------------------
    print("\n[Step 4] Expanding-Window Chronological Validation (2019–2024)...")
    expanding_folds = ChronologicalValidator.evaluate_expanding_windows(
        records=controlled_train + controlled_test,
        start_train_years=(2016, 2017, 2018),
        eval_years=(2019, 2020, 2021, 2022, 2023, 2024),
    )
    for fold in expanding_folds:
        print(
            f"     * Fold {fold.fold_index} (Train {fold.train_years[0]}–{fold.train_years[-1]} -> Val {fold.validation_year}): "
            f"Obs={fold.observed_crashes}, Pred={fold.predicted_crashes:.1f}, "
            f"Calib={fold.calibration_ratio:.3f}, RMSE={fold.rmse:.3f}"
        )

    # -------------------------------------------------------------------------
    # 5. Model Output Contract & Graceful Missingness Verification
    # -------------------------------------------------------------------------
    print("\n[Step 5] Validating Output Contract & Invariant Compliance...")
    # Test predicting on unpopulated actual records (without exposure)
    blocked_preds = poisson_model.predict(dataset.test_records[:5])
    for pred in blocked_preds:
        assert pred.prediction_status == PredictionStatus.BLOCKED_INSUFFICIENT_EXPOSURE
        assert pred.expected_crash_frequency is None
    print("  -> Blocked prediction invariant verified (expected_frequency is strictly None).")

    # -------------------------------------------------------------------------
    # 6. Model Persistence & Checksum Manifest
    # -------------------------------------------------------------------------
    print("\n[Step 6] Persisting Models, Validation Metrics & Manifest...")
    # 6a. Comparison metrics CSV
    comp_csv = Path("data/exports/frequency/model_comparison_metrics.csv")
    with open(comp_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "poisson_glm", "negative_binomial_nb2", "interpretation"])
        writer.writerow(["log_likelihood", comp_report.poisson_log_lik, comp_report.nb_log_lik, "Higher is better"])
        writer.writerow(["aic", comp_report.poisson_aic, comp_report.nb_aic, "Lower is better"])
        writer.writerow(["bic", comp_report.poisson_bic, comp_report.nb_bic, "Lower is better"])
        writer.writerow(["dispersion_ratio", comp_report.poisson_dispersion, comp_report.nb_dispersion, "Ratio close to 1.0 indicates good fit"])
        writer.writerow(["overdispersion_alpha", 0.0, comp_report.alpha, "NB2 quadratic dispersion"])
        writer.writerow(["cameron_trivedi_p_value", "-", comp_report.cameron_trivedi_p_val, "p < 0.05 rejects equidispersion"])
        writer.writerow(["lr_test_vs_poisson_p", "-", comp_report.lr_p_value, "p < 0.05 confirms NB2 superiority"])
        writer.writerow(["out_of_sample_rmse", comp_report.poisson_test_rmse, comp_report.nb_test_rmse, "Lower is better"])
        writer.writerow(["out_of_sample_mae", comp_report.poisson_test_mae, comp_report.nb_test_mae, "Lower is better"])
        writer.writerow(["calibration_ratio", comp_report.poisson_calibration, comp_report.nb_calibration, "Observed / Predicted"])

    # 6b. Expanding window metrics CSV
    exp_csv = Path("data/exports/frequency/chronological_validation_metrics.csv")
    with open(exp_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["fold_index", "train_period", "validation_year", "train_records", "val_records", "observed_crashes", "predicted_crashes", "calibration_ratio", "rmse", "mae"])
        for fold in expanding_folds:
            writer.writerow([
                fold.fold_index,
                f"{fold.train_years[0]}–{fold.train_years[-1]}",
                fold.validation_year,
                fold.num_train_records,
                fold.num_val_records,
                fold.observed_crashes,
                fold.predicted_crashes,
                fold.calibration_ratio,
                fold.rmse,
                fold.mae,
            ])

    # 6c. Canonical Model Manifest JSON
    prototype_hash = ModelPersistenceManager.compute_file_sha256(prototype_path)
    manifest = ModelManifest(
        model_name="Negative_Binomial_NB2",
        model_version="1.0.0",
        software_version="1.0.0",
        crosswalk_version="1.0.0",
        training_dataset_checksum=prototype_hash,
        exposure_dataset_checksum="UNAVAILABLE_EXPOSURE_VOID",
        training_period="2016-2020",
        validation_period="2021-2024",
        feature_definitions=["Intercept", "road_class_INTERSTATE", "road_class_RAMP", "length_km"],
        parameters=nb_fit.coefficients,
        standard_errors=nb_fit.standard_errors,
        dispersion_parameter_alpha=nb_fit.alpha,
        metrics={
            "log_likelihood": nb_fit.log_likelihood,
            "aic": nb_fit.aic,
            "bic": nb_fit.bic,
            "dispersion_ratio": nb_fit.dispersion_ratio,
            "cameron_trivedi_t": nb_fit.cameron_trivedi_t_stat,
            "cameron_trivedi_p": nb_fit.cameron_trivedi_p_value,
            "lr_test_stat": nb_fit.lr_test_vs_poisson,
            "lr_test_p": nb_fit.lr_p_value,
            "out_of_sample_rmse": comp_report.nb_test_rmse,
            "out_of_sample_mae": comp_report.nb_test_mae,
            "calibration_ratio": comp_report.nb_calibration,
        },
        approval_status="NOT_APPROVED_FOR_PRODUCTION_INSUFFICIENT_EXPOSURE",
        limitations=[
            "Predictive frequency forecasting prohibited under Project Plan v2 (§8, §18) due to unverified exposure.",
            "Local municipal streets (73.4% of unique sites) lack traffic volume data.",
            "Historical crash-concentration reporting pathway must be used for road safety analysis.",
        ],
    )
    manifest_path = ModelPersistenceManager.save_manifest(
        output_path="data/exports/frequency/model_manifest.json",
        manifest=manifest,
    )
    print(f"  -> Model comparison metrics: {comp_csv}")
    print(f"  -> Chronological validation metrics: {exp_csv}")
    print(f"  -> Model manifest: {manifest_path}")

    print("\n" + "=" * 80)
    print("PHASE 4 MODULE B EXECUTION COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    main()
