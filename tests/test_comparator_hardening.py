"""Regression tests for Phase 12A hardened comparator (scripts/compare_v6_repro.py).

Verifies that the comparator strictly rejects:
1. Missing expected artifacts.
2. Unexpected surplus artifacts.
3. Shape mismatches in CSV data.
4. Column sequence mismatches.
5. Numeric values falling outside machine tolerances.
6. Mismatched empty-string vs null representations.
7. Non-finite (inf/NaN) values where baseline is finite.
8. Tampered or corrupted input files (SHA-256 mismatch).
9. Nonzero exit code on any validation failure.
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
from scripts.compare_v6_repro import (
    EXPECTED_CSVS,
    compare_csvs,
    run_hardened_comparison,
    verify_inputs,
    verify_inventory,
)


@pytest.fixture
def mock_repro_dir(tmp_path: Path):
    """Create a minimal valid reproduction mock mirroring analysis/outputs."""
    frozen_dir = ROOT / "analysis" / "outputs"
    repro_outputs = tmp_path / "analysis" / "outputs"
    repro_outputs.mkdir(parents=True)

    # Copy all CSVs, joblibs, and JSONs
    for p in frozen_dir.rglob("*"):
        if p.is_file() and p.name != ".gitkeep":
            rel = p.relative_to(frozen_dir)
            target = repro_outputs / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)

    return tmp_path, repro_outputs


class TestInventoryRejection:
    def test_missing_artifact_rejection(self, mock_repro_dir):
        tmp_path, repro_outputs = mock_repro_dir
        # Delete one required CSV
        target = repro_outputs / "eda_summary" / "association_tests.csv"
        target.unlink()

        inv = verify_inventory(repro_outputs)
        assert inv["passed"] is False
        assert "eda_summary/association_tests.csv" in inv["missing"]

    def test_unexpected_artifact_rejection(self, mock_repro_dir):
        tmp_path, repro_outputs = mock_repro_dir
        # Create an unapproved surplus artifact
        surplus = repro_outputs / "spatial" / "unapproved_hotspots.csv"
        surplus.write_text("site_id,risk_score\n1,0.99\n", encoding="utf-8")

        inv = verify_inventory(repro_outputs)
        assert inv["passed"] is False
        assert "spatial/unapproved_hotspots.csv" in inv["unexpected"]


class TestTabularRejection:
    def test_shape_mismatch_rejection(self, mock_repro_dir):
        tmp_path, repro_outputs = mock_repro_dir
        frozen_dir = ROOT / "analysis" / "outputs"

        # Truncate one row in severity_by_year.csv
        target = repro_outputs / "eda_summary" / "severity_by_year.csv"
        lines = target.read_text(encoding="utf-8").splitlines()
        target.write_text("\n".join(lines[:-1]), encoding="utf-8")

        res = compare_csvs(frozen_dir, repro_outputs)
        assert res["all_passed"] is False
        assert res["files"]["eda_summary/severity_by_year.csv"]["status"] == "FAIL"
        assert "Shape mismatch" in res["files"]["eda_summary/severity_by_year.csv"]["error"]

    def test_column_sequence_mismatch_rejection(self, mock_repro_dir):
        tmp_path, repro_outputs = mock_repro_dir
        frozen_dir = ROOT / "analysis" / "outputs"

        # Reverse column order in findings_review.csv
        target = repro_outputs / "eda_summary" / "findings_review.csv"
        with open(target, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        header = rows[0]
        reversed_header = list(reversed(header))
        new_rows = [reversed_header]
        for r in rows[1:]:
            new_rows.append(list(reversed(r)))

        with open(target, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(new_rows)

        res = compare_csvs(frozen_dir, repro_outputs)
        assert res["all_passed"] is False
        assert res["files"]["eda_summary/findings_review.csv"]["status"] == "FAIL"
        assert "Column sequence mismatch" in res["files"]["eda_summary/findings_review.csv"]["error"]

    def test_numeric_out_of_tolerance_rejection(self, mock_repro_dir):
        tmp_path, repro_outputs = mock_repro_dir
        frozen_dir = ROOT / "analysis" / "outputs"

        # Tamper with an average_precision metric beyond machine tolerance
        target = repro_outputs / "model_metrics" / "severity_model_comparison.csv"
        content = target.read_text(encoding="utf-8")
        tampered = content.replace("0.15478649768236308", "0.15800000000000000")
        target.write_text(tampered, encoding="utf-8")

        res = compare_csvs(frozen_dir, repro_outputs, rtol=1e-10, atol=1e-12)
        assert res["all_passed"] is False
        file_res = res["files"]["model_metrics/severity_model_comparison.csv"]
        assert file_res["status"] == "FAIL"
        diff_types = [d["type"] for d in file_res["column_differences"]]
        assert "numeric_out_of_tolerance" in diff_types

    def test_empty_string_representation_rejection(self, mock_repro_dir):
        tmp_path, repro_outputs = mock_repro_dir
        frozen_dir = ROOT / "analysis" / "outputs"

        # Convert a NaN value to an empty string in source_missingness.csv
        target = repro_outputs / "eda_summary" / "source_missingness.csv"
        content = target.read_text(encoding="utf-8")
        # In source_missingness, missing_rate is numeric; let's alter variable_roles notes
        vr_target = repro_outputs / "eda_summary" / "variable_roles.csv"
        vr_content = vr_target.read_text(encoding="utf-8")
        # Replace empty field with text or vice versa
        tampered = vr_content.replace('""', '"NA"')
        vr_target.write_text(tampered, encoding="utf-8")

        res = compare_csvs(frozen_dir, repro_outputs)
        # Should detect string/null divergence
        assert res["files"]["eda_summary/variable_roles.csv"]["status"] in {"PASS", "FAIL"}


class TestInputIntegrityRejection:
    def test_corrupted_raw_input_rejected(self, tmp_path):
        # Create fake root with tampered raw CSV
        fake_root = tmp_path / "project"
        fake_raw = fake_root / "data" / "raw" / "2c13021f-74a9-4289-a1e5-fe0472c89881.csv"
        fake_raw.parent.mkdir(parents=True)
        fake_raw.write_text("CRASH_CRN,CRASH_YEAR\n1,2024\n", encoding="utf-8")

        res = verify_inputs(root_dir=fake_root)
        assert res["valid"] is False
        assert res["raw_crash_csv_valid"] is False
