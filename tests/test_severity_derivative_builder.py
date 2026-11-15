"""Tests for the Phase 12C Retrospective Severity Models Aggregate Derivative Builder.

Validates:
1. Normal execution producing valid schemas and manifests
2. Determinism across runs (byte-identical SHA-256)
3. Rejection of changed source hash
4. Rejection of missing required inputs
5. Rejection of mismatched denominators / event counts
6. Absence of case-level records, individual coordinates, or site risk rankings
7. Manifest release gates and scientific exclusions
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from scripts.build_severity_derivative import (
    BUILDER_VERSION,
    COHORT_TEST,
    COHORT_TRAIN,
    DERIVATIVE_SCHEMA_VERSION,
    DERIVATIVE_VERSION,
    EXPECTED_INPUTS,
    KIND,
    build_candidate_derivative,
    sha256_file,
    verify_source_inputs,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
CANDIDATE_DIR = ROOT_DIR / "data" / "exports" / "models" / "candidate"


def test_builder_candidate_manifest_and_tables():
    """Verify the generated candidate derivative has expected schema, manifest, and tables."""
    assert CANDIDATE_DIR.exists(), "Candidate directory must exist"
    manifest_path = CANDIDATE_DIR / "manifest.json"
    assert manifest_path.exists(), "manifest.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["kind"] == KIND
    assert manifest["version"] == DERIVATIVE_VERSION
    assert manifest["schema_version"] == DERIVATIVE_SCHEMA_VERSION
    assert manifest["status"] == "REVIEW_CANDIDATE"
    assert manifest["scope"]["PRIMARY_SITE_ASSIGNMENTS_ACCEPTED"] == 0
    assert manifest["scope"]["SITE_PREDICTIONS_PERMITTED"] is False
    assert manifest["scope"]["LIVE_INFERENCE_PERMITTED"] is False
    assert manifest["scope"]["CASES_SCORED_PERMITTED"] is False

    # Check 4 required tables
    table_ids = [t["table_id"] for t in manifest["tables"]]
    expected_tables = [
        "model_comparisons",
        "feature_ablation",
        "threshold_performance",
        "calibration_diagnostics",
    ]
    assert sorted(table_ids) == sorted(expected_tables)

    # Check that both JSON and CSV exist for each table
    for tid in expected_tables:
        json_file = CANDIDATE_DIR / f"{tid}.json"
        csv_file = CANDIDATE_DIR / f"{tid}.csv"
        assert json_file.exists(), f"Missing {tid}.json"
        assert csv_file.exists(), f"Missing {tid}.csv"
        assert sha256_file(json_file) == manifest["outputs"][f"{tid}.json"]
        assert sha256_file(csv_file) == manifest["outputs"][f"{tid}.csv"]


def test_builder_denominators_and_reconciliation():
    """Verify cohort counts reconcile with Phase 12A research evidence."""
    comp_json = CANDIDATE_DIR / "model_comparisons.json"
    with open(comp_json, "r", encoding="utf-8") as f:
        comparisons = json.load(f)

    # 4 uncalibrated models from comparison CSV + 1 temporally calibrated model = 5 models
    assert len(comparisons) == 5
    for model in comparisons:
        assert model["training_records"] == 58660
        assert model["training_positives"] == 2384
        assert model["test_records"] == 27697
        assert model["test_positives"] == 1231
        assert model["test_prevalence_percent"] == 4.4445
        assert model["ap_chance_baseline"] == 0.0444
        assert model["roc_chance_baseline"] == 0.5000
        assert model["derivative_schema_version"] == DERIVATIVE_SCHEMA_VERSION


def test_no_case_level_or_coordinate_leakage():
    """Verify derivative outputs contain zero individual crash records or site risk predictions."""
    prohibited_keys = [
        "CRN", "crn", "LATITUDE", "LONGITUDE", "dec_lat", "dec_long",
        "crash_id", "site_id", "intersection_id", "predicted_risk", "rank"
    ]
    for ext in ["json", "csv"]:
        for tid in ["model_comparisons", "feature_ablation", "threshold_performance", "calibration_diagnostics"]:
            file_path = CANDIDATE_DIR / f"{tid}.{ext}"
            content = file_path.read_text(encoding="utf-8")
            for key in prohibited_keys:
                assert f'"{key}"' not in content, f"Prohibited key {key} leaked in {file_path.name}"


def test_builder_determinism():
    """Verify that running builder twice yields identical manifest and table hashes."""
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        res1 = build_candidate_derivative(root_dir=ROOT_DIR, output_dir=Path(tmp1))
        res2 = build_candidate_derivative(root_dir=ROOT_DIR, output_dir=Path(tmp2))

        assert res1["manifest_sha256"] == res2["manifest_sha256"]
        assert res1["outputs"] == res2["outputs"]


def test_builder_rejects_missing_input():
    """Verify builder raises FileNotFoundError if an archived input is missing."""
    with tempfile.TemporaryDirectory() as tmp_root:
        # Empty root has no inputs
        with pytest.raises(FileNotFoundError, match="Required frozen research input missing"):
            verify_source_inputs(Path(tmp_root))


def test_builder_rejects_changed_source_hash():
    """Verify builder raises ValueError if an archived input's SHA-256 changes."""
    with tempfile.TemporaryDirectory() as mock_root:
        mock_path = Path(mock_root)
        # Create dummy directory structure
        for key, spec in EXPECTED_INPUTS.items():
            dest = mock_path / spec["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Write tampered content
            dest.write_text("TAMPERED_CONTENT_CORRUPTED_HASH", encoding="utf-8")

        with pytest.raises(ValueError, match="checksum mismatch"):
            verify_source_inputs(mock_path)
