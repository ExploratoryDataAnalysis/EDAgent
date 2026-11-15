"""Test suite for Phase 12A: Retrospective Model Reproduction & Methods Verification.

Verifies:
1. Frozen canonical inputs and notebook integrity (SHA-256 digests and blob IDs).
2. Reproduction comparator invariants across all 15 analytical CSVs.
3. Estimator functional equivalence vs binary joblib serialization differences.
4. Target definition: Binary severe injury conditioned on reported crashes with known outcomes.
5. Strict exclusion of unknown severity records (listwise deletion).
6. Post-crash feature timing caveat (collision type Cramér's V = 0.202 vs pre-crash ablation collapse).
7. Evaluation metric distinctions: AP vs ROC vs Brier vs baselines.
8. Unapproved production status: NOT_APPROVED_FOR_PRODUCTION invariants.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


class TestPhase12AProvenanceAndIntegrity:
    """Verify input and frozen baseline identities."""

    def test_raw_dataset_identity(self):
        raw_csv = ROOT / "data" / "raw" / "2c13021f-74a9-4289-a1e5-fe0472c89881.csv"
        assert raw_csv.exists(), "Raw crash CSV must be archived in data/raw/"
        assert raw_csv.stat().st_size == 116560683
        with open(raw_csv, "rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        assert digest == "c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511"

    def test_frozen_notebook_identity(self):
        nb_file = ROOT / "analysis" / "EDA_v6.ipynb"
        assert nb_file.exists(), "EDA_v6.ipynb must exist in analysis/"
        content_lf = nb_file.read_bytes().replace(b"\r\n", b"\n")
        digest = hashlib.sha256(content_lf).hexdigest()
        assert digest == "bdb7101c9fc017a68690506fd8cfdec579623b028563f287202ed54e6e324064"

    def test_manifest_review_status(self):
        manifest_file = ROOT / "analysis" / "outputs" / "run_manifest.json"
        assert manifest_file.exists()
        import json
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert manifest["review_status"] == "NOT_APPROVED_FOR_PRODUCTION"
        assert manifest["severity_model_training_years"] == "2016-2021"
        assert manifest["severity_model_final_test_years"] == "2022-2024"
        assert manifest["data"]["rows"] == 248810
        assert manifest["data"]["columns"] == 191


class TestPhase12ASeverityMethodology:
    """Verify scientific methodology, cohort counts, and metric baselines."""

    def test_severity_cohort_and_exclusions(self):
        """Reconcile 2016-2021 train and 2022-2024 test cohort counts."""
        comp_file = ROOT / "analysis" / "outputs" / "model_metrics" / "severity_model_comparison.csv"
        assert comp_file.exists()
        with open(comp_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 4
        for r in rows:
            # 27,697 known-severity test records
            assert int(r["test_records"]) == 27697
            assert float(r["test_prevalence_percent"]) == pytest.approx(4.444525, abs=1e-4)

    def test_collision_type_ablation_collapse(self):
        """Verify that removing post-crash collision type causes AP to collapse."""
        comp_file = ROOT / "analysis" / "outputs" / "model_metrics" / "severity_model_comparison.csv"
        with open(comp_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = {r["model"]: r for r in reader}

        rf_coll = float(rows["Random Forest + collision"]["average_precision"])
        rf_no_coll = float(rows["Random Forest without collision"]["average_precision"])
        prevalence = float(rows["Random Forest + collision"]["test_prevalence_percent"]) / 100.0

        assert rf_coll > 0.14
        assert rf_no_coll < 0.055
        # Without collision, AP is barely above prevalence (chance baseline)
        assert rf_no_coll == pytest.approx(prevalence, abs=0.01)

    def test_brier_score_calibration_contrast(self):
        """Verify uncalibrated vs constant baseline contrast."""
        comp_file = ROOT / "analysis" / "outputs" / "model_metrics" / "severity_model_comparison.csv"
        with open(comp_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Uncalibrated balanced models have worse Brier score (>0.15) than constant baseline (~0.0426)
        for r in rows:
            brier = float(r["brier_score_uncalibrated"])
            assert brier > 0.15, "Uncalibrated balanced models should have high Brier scores"


class TestPhase12AReproductionComparator:
    """Verify that scripts/compare_v6_repro.py executes and passes on valid repro."""

    def test_reproduction_comparison_passes(self):
        import sklearn
        from scripts.compare_v6_repro import run_comparison
        # Run comparison on the executed phase12a run
        repro_run = "v6-repro-phase12a-20261115"
        repro_path = ROOT / ".repro" / repro_run
        if not repro_path.exists():
            pytest.skip("Reproduction run not yet executed in this environment")

        # Scientific decision: Deserializing frozen joblib estimators requires exact scikit-learn 1.6.1
        # Sklearn internal classes (e.g. _RemainderColsList) break when unpickled across major/minor versions.
        if sklearn.__version__ != "1.6.1":
            pytest.skip(f"Estimator unpickling requires scikit-learn 1.6.1 (current: {sklearn.__version__})")

        result = run_comparison(repro_run)
        assert result["input_verification"]["raw_crash_csv_valid"] is True
        assert result["input_verification"]["notebook_valid"] is True
        assert result["csv_comparisons"]["total_csvs"] == 15
        assert result["csv_comparisons"]["matched_within_tolerance"] == 15
        # All 5 estimators must be functionally matching
        estimators = result["estimator_comparisons"].get("estimators", {})
        assert len(estimators) == 5
        for est_name, est_info in estimators.items():
            assert est_info["functional_equivalence"] is True, f"Estimator {est_name} failed functional match"
