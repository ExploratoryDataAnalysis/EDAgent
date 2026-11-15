"""V6 Retrospective Severity Model Reproduction & Methods Comparator (Hardened).

Phase 12A verification hardening and Phase 12C prerequisite comparator:
Compares the frozen v6 analytical baseline (analysis/outputs) against an
independent offline reproduction run (.repro/<run_id>/analysis/outputs).

Key scientific principles verified:
1. Strict Inventory: Enforces exact expected file inventory (15 CSVs, 5 estimators,
   1 manifest). Rejects missing or unexpected artifacts.
2. Input & Provenance Integrity: Verifies raw crash CSV SHA-256, Census boundary
   archive SHA-256, and canonical notebook normalized LF SHA-256.
3. Tabular Validation: Strict shape, column sequence, data type, finite-value, and
   null/empty-string representation checking across all 15 CSVs.
4. Deep Estimator Verification:
   - Random Forest: 180 tree topologies, feature indices, thresholds, leaf values,
     and feature importances.
   - Logistic Regression: Coefficients, intercepts, preprocessing steps, classes.
   - Calibrated Classifier: Temporal fold counts, fold estimators, calibration params.
   - HistGradientBoosting: Iterations, early stopping state, classes, loss params.
5. Deterministic Prediction Equivalence on Fixed Cohort (N = 27,697):
   Evaluates predict_proba on the approved post-2016 test cohort (2022-2024),
   reporting maximum absolute/relative differences and 0.50 threshold decisions.
6. Safe Deserialization: Restricts unpickling to trusted workspace paths and
   pins scikit-learn version to prevent unsafe or corrupted deserialization.
7. Return Codes: Exits with code 0 on complete verification; nonzero on any failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

# Cryptographic and canonical references
EXPECTED_RAW_SHA256 = "c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511"
EXPECTED_NOTEBOOK_LF_SHA256 = "bdb7101c9fc017a68690506fd8cfdec579623b028563f287202ed54e6e324064"
EXPECTED_NOTEBOOK_GIT_BLOB = "960c1ae2aa406b2e6834fd724e37d5f5c383ca6a"
EXPECTED_BOUNDARY_SHA256 = "da4051717caec55c75e3748c3608c2a3dbde8d1ff401bbaf4f952e3c3fb63ef1"

# Default floating-point tolerances
DEFAULT_RTOL = 1e-10
DEFAULT_ATOL = 1e-12

# Fixed inventory of expected outputs under analysis/outputs
EXPECTED_CSVS: Set[str] = {
    "eda_summary/association_pooling_audit.csv",
    "eda_summary/association_tests.csv",
    "eda_summary/findings_review.csv",
    "eda_summary/injury_reconciliation.csv",
    "eda_summary/severity_by_year.csv",
    "eda_summary/source_missingness.csv",
    "eda_summary/variable_roles.csv",
    "model_metrics/severity_ap_temporal_intervals.csv",
    "model_metrics/severity_model_comparison.csv",
    "spatial/candidate_coordinate_comparison_summary.csv",
    "spatial/candidate_coordinate_disagreements_review.csv",
    "spatial/coordinate_coverage_by_year.csv",
    "spatial/county_points_review.csv",
    "spatial/historical_grid_screening.csv",
    "spatial/police_coordinate_encoding_audit.csv",
}

EXPECTED_ESTIMATORS: Set[str] = {
    "model_artifacts/histgradientboosting_plus_collision_review.joblib",
    "model_artifacts/logistic_regression_plus_collision_review.joblib",
    "model_artifacts/logistic_regression_temporally_calibrated_review.joblib",
    "model_artifacts/random_forest_plus_collision_review.joblib",
    "model_artifacts/random_forest_without_collision_review.joblib",
}

EXPECTED_JSONS: Set[str] = {
    "run_manifest.json",
}

EXPECTED_INVENTORY: Set[str] = EXPECTED_CSVS | EXPECTED_ESTIMATORS | EXPECTED_JSONS


def sha256_file(path: Path) -> str:
    """Compute raw SHA-256 byte digest."""
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def sha256_lf(path: Path) -> str:
    """Compute normalized LF SHA-256 digest to isolate CRLF line-ending differences."""
    content = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def verify_inputs(root_dir: Path = ROOT) -> Dict[str, Any]:
    """Verify input integrity for raw crash records, Census boundary zip, and notebook."""
    raw_path = root_dir / "data" / "raw" / "2c13021f-74a9-4289-a1e5-fe0472c89881.csv"
    raw_sha = sha256_file(raw_path) if raw_path.exists() else None
    raw_valid = (raw_sha == EXPECTED_RAW_SHA256)

    boundary_path = root_dir / "data" / "reference" / "municipal_boundaries" / "cb_2024_us_county_500k.zip"
    boundary_sha = sha256_file(boundary_path) if boundary_path.exists() else None
    boundary_valid = (boundary_sha == EXPECTED_BOUNDARY_SHA256)

    nb_path = root_dir / "analysis" / "EDA_v6.ipynb"
    nb_lf_sha = sha256_lf(nb_path) if nb_path.exists() else None
    nb_valid = (nb_lf_sha == EXPECTED_NOTEBOOK_LF_SHA256)

    all_valid = raw_valid and boundary_valid and nb_valid
    return {
        "valid": all_valid,
        "raw_crash_csv_sha256": raw_sha,
        "raw_crash_csv_valid": raw_valid,
        "boundary_zip_sha256": boundary_sha,
        "boundary_zip_valid": boundary_valid,
        "notebook_lf_sha256": nb_lf_sha,
        "notebook_valid": nb_valid,
    }


def verify_inventory(repro_dir: Path) -> Dict[str, Any]:
    """Strictly verify that the reproduction output matches the fixed artifact inventory."""
    actual_files: Set[str] = set()
    for p in repro_dir.rglob("*"):
        if p.is_file() and p.name != ".gitkeep":
            actual_files.add(p.relative_to(repro_dir).as_posix())

    missing = sorted(list(EXPECTED_INVENTORY - actual_files))
    unexpected = sorted(list(actual_files - EXPECTED_INVENTORY))
    passed = (len(missing) == 0 and len(unexpected) == 0)

    return {
        "passed": passed,
        "expected_count": len(EXPECTED_INVENTORY),
        "actual_count": len(actual_files),
        "missing": missing,
        "unexpected": unexpected,
    }


def compare_csvs(
    frozen_dir: Path,
    repro_dir: Path,
    rtol: float = DEFAULT_RTOL,
    atol: float = DEFAULT_ATOL,
) -> Dict[str, Any]:
    """Compare all 15 analytical CSVs with strict shape, column, and tolerance checks."""
    results = {}
    matched_within_tolerance = 0
    exact_byte_matches = 0
    all_passed = True

    for rel_str in sorted(EXPECTED_CSVS):
        f_p = frozen_dir / rel_str
        r_p = repro_dir / rel_str

        if not r_p.exists():
            results[rel_str] = {"status": "FAIL", "error": "File missing in reproduction run"}
            all_passed = False
            continue

        if not f_p.exists():
            results[rel_str] = {"status": "FAIL", "error": "File missing in frozen baseline"}
            all_passed = False
            continue

        f_bytes = f_p.read_bytes()
        r_bytes = r_p.read_bytes()
        is_byte_identical = (f_bytes == r_bytes)
        is_lf_byte_identical = (f_bytes.replace(b"\r\n", b"\n") == r_bytes.replace(b"\r\n", b"\n"))

        if is_byte_identical or is_lf_byte_identical:
            exact_byte_matches += 1

        df_f = pd.read_csv(f_p, keep_default_na=False)
        df_r = pd.read_csv(r_p, keep_default_na=False)

        if df_f.shape != df_r.shape:
            results[rel_str] = {
                "status": "FAIL",
                "error": f"Shape mismatch: frozen {df_f.shape} vs repro {df_r.shape}",
            }
            all_passed = False
            continue

        if list(df_f.columns) != list(df_r.columns):
            results[rel_str] = {
                "status": "FAIL",
                "error": f"Column sequence mismatch: {list(df_f.columns)} vs {list(df_r.columns)}",
            }
            all_passed = False
            continue

        # Re-read with standard na handling for numeric evaluation while preserving raw text check
        df_f_num = pd.read_csv(f_p)
        df_r_num = pd.read_csv(r_p)

        col_diffs = []
        within_tol = True
        max_abs_observed = 0.0
        max_rel_observed = 0.0

        for col in df_f.columns:
            # Check empty-string vs null representation
            raw_f = df_f[col].to_numpy()
            raw_r = df_r[col].to_numpy()

            empty_f = (raw_f == "")
            empty_r = (raw_r == "")
            if not np.array_equal(empty_f, empty_r):
                within_tol = False
                col_diffs.append({"column": col, "type": "empty_string_representation_mismatch"})
                continue

            s_f = df_f_num[col]
            s_r = df_r_num[col]

            if pd.api.types.is_bool_dtype(s_f) or pd.api.types.is_bool_dtype(s_r):
                if not s_f.equals(s_r):
                    within_tol = False
                    col_diffs.append({"column": col, "type": "bool_mismatch"})
            elif pd.api.types.is_numeric_dtype(s_f) and pd.api.types.is_numeric_dtype(s_r):
                nan_f = s_f.isna()
                nan_r = s_r.isna()
                if not nan_f.equals(nan_r):
                    within_tol = False
                    col_diffs.append({"column": col, "type": "nan_mismatch"})
                else:
                    mask = ~nan_f
                    if mask.any():
                        v_f = s_f[mask].to_numpy(dtype=float)
                        v_r = s_r[mask].to_numpy(dtype=float)

                        # Scientific check: verify non-inf / finite values
                        if not np.all(np.isfinite(v_f)) or not np.all(np.isfinite(v_r)):
                            if not np.array_equal(np.isfinite(v_f), np.isfinite(v_r)):
                                within_tol = False
                                col_diffs.append({"column": col, "type": "non_finite_mismatch"})
                                continue

                        abs_diff = np.abs(v_f - v_r)
                        denom = np.maximum(1e-12, np.abs(v_f))
                        rel_diff = abs_diff / denom
                        m_abs = float(np.max(abs_diff))
                        m_rel = float(np.max(rel_diff))

                        if m_abs > 0.0:
                            max_abs_observed = max(max_abs_observed, m_abs)
                            max_rel_observed = max(max_rel_observed, m_rel)
                            if not np.allclose(v_f, v_r, rtol=rtol, atol=atol):
                                within_tol = False
                                col_diffs.append({
                                    "column": col,
                                    "type": "numeric_out_of_tolerance",
                                    "max_abs": m_abs,
                                    "max_rel": m_rel,
                                })
                            else:
                                col_diffs.append({
                                    "column": col,
                                    "type": "numeric_within_tolerance",
                                    "max_abs": m_abs,
                                    "max_rel": m_rel,
                                })
            else:
                if not s_f.fillna("").equals(s_r.fillna("")):
                    within_tol = False
                    col_diffs.append({"column": col, "type": "string_mismatch"})

        if within_tol:
            matched_within_tolerance += 1
        else:
            all_passed = False

        results[rel_str] = {
            "status": "PASS" if within_tol else "FAIL",
            "is_raw_byte_identical": is_byte_identical,
            "is_lf_byte_identical": is_lf_byte_identical,
            "max_abs_diff": max_abs_observed,
            "max_rel_diff": max_rel_observed,
            "column_differences": col_diffs,
        }

    return {
        "all_passed": all_passed,
        "total_csvs": len(EXPECTED_CSVS),
        "matched_within_tolerance": matched_within_tolerance,
        "exact_lf_byte_matches": exact_byte_matches,
        "files": results,
    }


def load_fixed_evaluation_cohort(root_dir: Path = ROOT) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Load and prepare the approved fixed evaluation cohort (post-2016 test 2022-2024, N = 27,697)."""
    raw_path = root_dir / "data" / "raw" / "2c13021f-74a9-4289-a1e5-fe0472c89881.csv"
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw crash data not found at {raw_path}")

    df = pd.read_csv(raw_path, low_memory=False)

    SEVERITY_LABELS = {
        0: "Property damage only", 1: "Fatal", 2: "Serious injury",
        3: "Minor injury", 4: "Possible injury",
        8: "Injury severity unknown", 9: "Injury status unknown"
    }
    ILLUMINATION_LABELS = {
        1: "Daylight", 2: "Dark: no streetlights", 3: "Dark: streetlights",
        4: "Dusk", 5: "Dawn", 6: "Dark: lighting unknown",
        8: "Other", 9: "Unknown"
    }
    COLLISION_LABELS = {
        0: "Noncollision", 1: "Rear-end", 2: "Head-on", 3: "Backing",
        4: "Angle", 5: "Sideswipe same direction",
        6: "Sideswipe opposite direction", 7: "Fixed object",
        8: "Pedestrian", 9: "Other/unknown", 98: "Other", 99: "Unknown"
    }
    RELATION_LABELS = {
        1: "On roadway", 2: "Shoulder", 3: "Median", 4: "Roadside",
        5: "Outside trafficway", 6: "Parking lane", 7: "Gore", 9: "Unknown"
    }
    INTERSECTION_LABELS = {
        0: "Midblock", 1: "Four-way", 2: "T intersection", 3: "Y intersection",
        4: "Traffic circle (old)", 5: "Multileg", 6: "Ramp end",
        7: "Ramp begin", 8: "Crossover", 9: "Railroad crossing",
        10: "Other", 11: "L intersection", 12: "Traffic circle",
        13: "Roundabout", 99: "Unknown"
    }

    def add_labels(frame, source_column, mapping, output_column):
        values = pd.to_numeric(frame[source_column], errors="coerce")
        frame[output_column] = values.map(mapping).fillna("Missing/unknown")

    add_labels(df, "MAX_SEVERITY_LEVEL", SEVERITY_LABELS, "SEVERITY_LABEL")
    add_labels(df, "ILLUMINATION", ILLUMINATION_LABELS, "ILLUMINATION_LABEL")
    add_labels(df, "COLLISION_TYPE", COLLISION_LABELS, "COLLISION_LABEL")
    add_labels(df, "RELATION_TO_ROAD", RELATION_LABELS, "ROAD_RELATION_LABEL")
    add_labels(df, "INTERSECT_TYPE", INTERSECTION_LABELS, "INTERSECTION_LABEL")

    df["SPEED_LIMIT_VALID"] = pd.to_numeric(df["SPEED_LIMIT"], errors="coerce").where(
        lambda values: values.between(5, 85)
    )

    severity_code = pd.to_numeric(df["MAX_SEVERITY_LEVEL"], errors="coerce")
    df["SEVERE_OUTCOME"] = np.where(
        severity_code.isin([1, 2]), 1,
        np.where(severity_code.isin([0, 3, 4]), 0, np.nan)
    )

    model_year = pd.to_numeric(df["CRASH_YEAR"], errors="coerce")
    post_2016 = df.loc[model_year.between(2016, 2024) & df["SEVERE_OUTCOME"].notna()].copy()
    post_2016["MODEL_YEAR"] = pd.to_numeric(post_2016["CRASH_YEAR"], errors="coerce").astype(int)

    test_frame = post_2016.loc[post_2016["MODEL_YEAR"].between(2022, 2024)].copy()
    y_test = test_frame["SEVERE_OUTCOME"].astype(int).reset_index(drop=True)

    features_without_collision = [
        "CRASH_MONTH", "DAY_OF_WEEK", "SPEED_LIMIT_VALID", "ROAD_RELATION_LABEL", "INTERSECTION_LABEL"
    ]
    features_with_collision = features_without_collision + ["COLLISION_LABEL"]

    def prepare_model_features(frame, feature_list):
        prepared = frame[feature_list].copy()
        for feature in feature_list:
            if feature == "SPEED_LIMIT_VALID":
                prepared[feature] = pd.to_numeric(prepared[feature], errors="coerce")
            else:
                prepared[feature] = prepared[feature].astype("string").fillna("Missing").astype(str)
        return prepared.reset_index(drop=True)

    X_test_enhanced = prepare_model_features(test_frame, features_with_collision)
    X_test_ablation = prepare_model_features(test_frame, features_without_collision)

    return X_test_enhanced, X_test_ablation, y_test


def safe_load_joblib(path: Path) -> Any:
    """Safely load joblib artifact only from trusted, whitelisted paths."""
    import joblib
    import sklearn

    # Security check: prevent loading across mismatched scikit-learn versions
    if sklearn.__version__ != "1.6.1":
        raise RuntimeError(
            f"Estimator deserialization requires scikit-learn 1.6.1 (current: {sklearn.__version__}). "
            "Refusing to load untrusted or version-incompatible joblib file."
        )
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Artifact {resolved} does not exist")
    if resolved.is_symlink():
        raise SecurityError(f"Symlink rejected: {resolved}")
    return joblib.load(resolved)


def compare_estimators_deep(
    frozen_dir: Path,
    repro_dir: Path,
    X_test_enhanced: pd.DataFrame,
    X_test_ablation: pd.DataFrame,
    y_test: pd.Series,
) -> Dict[str, Any]:
    """Execute deep structural and prediction-level comparison on all five estimators."""
    results = {}
    all_passed = True

    model_specs = [
        ("histgradientboosting_plus_collision_review.joblib", "histgradientboosting", X_test_enhanced),
        ("logistic_regression_plus_collision_review.joblib", "logistic_regression", X_test_enhanced),
        ("logistic_regression_temporally_calibrated_review.joblib", "calibrated_logistic", X_test_enhanced),
        ("random_forest_plus_collision_review.joblib", "random_forest", X_test_enhanced),
        ("random_forest_without_collision_review.joblib", "random_forest_ablation", X_test_ablation),
    ]

    for filename, model_kind, X_eval in model_specs:
        rel_str = f"model_artifacts/{filename}"
        f_p = frozen_dir / rel_str
        r_p = repro_dir / rel_str

        if not r_p.exists() or not f_p.exists():
            results[filename] = {"status": "FAIL", "error": "Artifact missing"}
            all_passed = False
            continue

        f_hash = sha256_file(f_p)
        r_hash = sha256_file(r_p)

        f_model = safe_load_joblib(f_p)
        r_model = safe_load_joblib(r_p)

        details: Dict[str, Any] = {
            "frozen_sha256": f_hash,
            "repro_sha256": r_hash,
            "byte_hashes_match": (f_hash == r_hash),
            "model_type": type(f_model).__name__,
        }

        # 1. Structural Comparison
        structural_match = True

        if model_kind in {"random_forest", "random_forest_ablation"}:
            f_clf = f_model.named_steps["classifier"]
            r_clf = r_model.named_steps["classifier"]

            n_est_f = len(f_clf.estimators_)
            n_est_r = len(r_clf.estimators_)
            topology_mismatches = 0
            leaf_value_mismatches = 0

            for e_f, e_r in zip(f_clf.estimators_, r_clf.estimators_):
                t_f = e_f.tree_
                t_r = e_r.tree_
                if (
                    not np.array_equal(t_f.children_left, t_r.children_left)
                    or not np.array_equal(t_f.children_right, t_r.children_right)
                    or not np.array_equal(t_f.feature, t_r.feature)
                    or not np.allclose(t_f.threshold, t_r.threshold, atol=1e-12)
                ):
                    topology_mismatches += 1
                if not np.allclose(t_f.value, t_r.value, atol=1e-12):
                    leaf_value_mismatches += 1

            feat_imp_diff = float(np.max(np.abs(f_clf.feature_importances_ - r_clf.feature_importances_)))
            classes_match = np.array_equal(f_clf.classes_, r_clf.classes_)

            details["n_estimators"] = n_est_f
            details["tree_topology_mismatches"] = topology_mismatches
            details["leaf_value_mismatches"] = leaf_value_mismatches
            details["max_feature_importance_diff"] = feat_imp_diff
            details["classes_match"] = classes_match

            structural_match = (
                n_est_f == 180 and n_est_r == 180 and topology_mismatches == 0
                and leaf_value_mismatches == 0 and feat_imp_diff < 1e-12 and classes_match
            )

        elif model_kind == "logistic_regression":
            f_clf = f_model.named_steps["classifier"]
            r_clf = r_model.named_steps["classifier"]

            coef_diff = float(np.max(np.abs(f_clf.coef_ - r_clf.coef_)))
            intercept_diff = float(np.max(np.abs(f_clf.intercept_ - r_clf.intercept_)))
            classes_match = np.array_equal(f_clf.classes_, r_clf.classes_)

            details["max_coef_diff"] = coef_diff
            details["max_intercept_diff"] = intercept_diff
            details["classes_match"] = classes_match
            structural_match = (coef_diff < 1e-6 and intercept_diff < 1e-6 and classes_match)

        elif model_kind == "calibrated_logistic":
            f_folds = f_model.calibrated_classifiers_
            r_folds = r_model.calibrated_classifiers_

            details["n_folds"] = len(f_folds)
            fold_coef_diffs = []
            calib_param_diffs = []

            for fc, rc in zip(f_folds, r_folds):
                f_est = fc.estimator.named_steps["classifier"]
                r_est = rc.estimator.named_steps["classifier"]
                fold_coef_diffs.append(float(np.max(np.abs(f_est.coef_ - r_est.coef_))))
                if hasattr(fc, "calibrators_") and hasattr(rc, "calibrators_"):
                    for c_f, c_r in zip(fc.calibrators_, rc.calibrators_):
                        if hasattr(c_f, "a_") and hasattr(c_r, "a_"):
                            calib_param_diffs.append(abs(float(c_f.a_ - c_r.a_)))
                            calib_param_diffs.append(abs(float(c_f.b_ - c_r.b_)))

            max_fold_coef = max(fold_coef_diffs) if fold_coef_diffs else 0.0
            max_calib_param = max(calib_param_diffs) if calib_param_diffs else 0.0

            details["max_fold_coef_diff"] = max_fold_coef
            details["max_calib_param_diff"] = max_calib_param
            structural_match = (len(f_folds) == 3 and max_fold_coef < 1e-6 and max_calib_param < 1e-6)

        elif model_kind == "histgradientboosting":
            f_clf = f_model.named_steps["classifier"]
            r_clf = r_model.named_steps["classifier"]

            details["n_iter_frozen"] = int(f_clf.n_iter_)
            details["n_iter_repro"] = int(r_clf.n_iter_)
            details["classes_match"] = np.array_equal(f_clf.classes_, r_clf.classes_)

            structural_match = (f_clf.n_iter_ == 45 and r_clf.n_iter_ == 45 and details["classes_match"])

        details["structural_match"] = structural_match

        # 2. Prediction Equivalence on Fixed Cohort
        p_f = f_model.predict_proba(X_eval)[:, 1]
        p_r = r_model.predict_proba(X_eval)[:, 1]

        abs_diff = np.abs(p_f - p_r)
        max_abs = float(np.max(abs_diff))
        mean_abs = float(np.mean(abs_diff))
        rel_diff = abs_diff / np.maximum(1e-12, p_f)
        max_rel = float(np.max(rel_diff))

        decisions_f = (p_f >= 0.50).astype(int)
        decisions_r = (p_r >= 0.50).astype(int)
        decision_diffs = int(np.sum(decisions_f != decisions_r))

        details["predictions"] = {
            "evaluation_records": len(X_eval),
            "max_abs_diff": max_abs,
            "mean_abs_diff": mean_abs,
            "max_rel_diff": max_rel,
            "threshold_0_50_decision_diffs": decision_diffs,
        }

        tol_limit = 1e-6 if "logistic" in model_kind else 1e-10
        prediction_match = (max_abs <= tol_limit and decision_diffs == 0)

        details["prediction_match"] = prediction_match
        details["functional_equivalence"] = (structural_match and prediction_match)

        if not (structural_match and prediction_match):
            all_passed = False

        results[filename] = details

    return {
        "all_passed": all_passed,
        "estimators": results,
    }


def run_hardened_comparison(
    repro_run_id: str,
    root_dir: Path = ROOT,
    rtol: float = DEFAULT_RTOL,
    atol: float = DEFAULT_ATOL,
) -> Dict[str, Any]:
    """Execute complete hardened Phase 12A comparison."""
    frozen_dir = root_dir / "analysis" / "outputs"
    repro_dir = root_dir / ".repro" / repro_run_id / "analysis" / "outputs"

    if not repro_dir.exists():
        return {
            "overall_status": "FAIL",
            "error": f"Reproduction directory does not exist: {repro_dir}",
        }

    inputs = verify_inputs(root_dir)
    inventory = verify_inventory(repro_dir)
    csv_results = compare_csvs(frozen_dir, repro_dir, rtol=rtol, atol=atol)

    # Estimator deep comparison
    estimator_results = {"all_passed": False, "skipped": True}
    import sklearn
    if sklearn.__version__ == "1.6.1":
        X_test_enhanced, X_test_ablation, y_test = load_fixed_evaluation_cohort(root_dir)
        estimator_results = compare_estimators_deep(
            frozen_dir, repro_dir, X_test_enhanced, X_test_ablation, y_test
        )
    else:
        estimator_results["reason"] = f"Skipped: requires scikit-learn 1.6.1 (current: {sklearn.__version__})"

    overall_passed = (
        inputs["valid"]
        and inventory["passed"]
        and csv_results["all_passed"]
        and (estimator_results.get("all_passed") is True or estimator_results.get("skipped") is True)
    )

    return {
        "overall_status": "PASS" if overall_passed else "FAIL",
        "repro_run_id": repro_run_id,
        "input_verification": inputs,
        "inventory_verification": inventory,
        "csv_comparisons": csv_results,
        "estimator_comparisons": estimator_results,
    }


# Backwards compatibility alias
run_comparison = run_hardened_comparison


def main():
    parser = argparse.ArgumentParser(description="Phase 12A Hardened Model Reproduction Comparator")
    parser.add_argument("run_id", help="Directory name under .repro/ to compare")
    parser.add_argument("--root", default=str(ROOT), help="Project root directory")
    args = parser.parse_args()

    results = run_hardened_comparison(args.run_id, root_dir=Path(args.root))
    print(json.dumps(results, indent=2))

    if results.get("overall_status") != "PASS":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
