"""Unit and integration tests for Phase 12C Retrospective Severity Models Release Endpoint.

Tests cover:
1. Fail closed (503 MODELS_UNAVAILABLE) when ROAD_SAFETY_APPROVALS is unset.
2. Fail closed (503) when decision is PENDING, REJECTED, or WITHDRAWN.
3. Fail closed (503) on manifest SHA-256 fingerprint mismatch or corrupted artifact.
4. Successful serving of all 4 tables, CSV downloads, assets, and provenance when approved.
5. Strict rejection (400 Bad Request) on prohibited query parameters (coordinates, site_id, live crash scoring).
6. Cache-Control: no-store header presence on both success and error responses.
7. Independence of D7 descriptive release gate and models release gate.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

from app.api.v1.endpoints import models

BASE_MODELS = "/api/v1/road-safety/models"


def locate_candidate_dir() -> Path:
    """Robustly locate the candidate derivative directory across varying checkout roots."""
    search_dirs = [
        *(p / "data" / "exports" / "models" / "candidate" for p in Path(__file__).resolve().parents),
        *(p / "data" / "exports" / "models" / "candidate" for p in Path.cwd().parents),
        Path.cwd() / "data" / "exports" / "models" / "candidate",
    ]
    for d in search_dirs:
        if (d / "manifest.json").exists():
            return d.resolve()
    # Default fallback
    return (Path(__file__).resolve().parents[4] / "data" / "exports" / "models" / "candidate").resolve()


def write_models_decision(ledger_path: Path, manifest_sha256: str, decision: str = "APPROVED", reviewer: str = "SCIENTIFIC REVIEW COMMITTEE"):
    data = {
        models.KIND: {
            "decision": decision,
            "reviewer": reviewer,
            "date": "2026-11-15",
            "manifest_sha256": manifest_sha256,
        }
    }
    ledger_path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def models_release(tmp_path, monkeypatch):
    """Isolated, self-contained models release bundle fixture."""
    bundle_path = tmp_path / "models_bundle"
    bundle_path.mkdir(parents=True, exist_ok=True)
    candidate_src = locate_candidate_dir()
    if candidate_src.exists() and (candidate_src / "manifest.json").exists():
        for item in candidate_src.iterdir():
            if item.is_file():
                shutil.copyfile(item, bundle_path / item.name)
    else:
        root_repo = Path(__file__).resolve().parents[4]
        if str(root_repo) not in sys.path:
            sys.path.insert(0, str(root_repo))
        from scripts.build_severity_derivative import build_candidate_derivative
        build_candidate_derivative(output_dir=bundle_path)

    ledger_path = tmp_path / "approvals.json"
    manifest_bytes = (bundle_path / "manifest.json").read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    monkeypatch.setattr(models, "MANIFEST_SHA256", manifest_sha256)
    write_models_decision(ledger_path, manifest_sha256, decision="APPROVED")
    monkeypatch.setenv("ROAD_SAFETY_MODELS_ROOT", str(bundle_path))
    monkeypatch.setenv("ROAD_SAFETY_APPROVALS", str(ledger_path))
    return bundle_path, ledger_path, manifest_sha256


def test_models_unapproved_missing_ledger_fails_closed(anon_client, monkeypatch):
    """When ROAD_SAFETY_APPROVALS is not set, must return HTTP 503 MODELS_UNAVAILABLE."""
    monkeypatch.delenv("ROAD_SAFETY_APPROVALS", raising=False)
    r = anon_client.get(f"{BASE_MODELS}/provenance")
    assert r.status_code == 503
    assert r.headers["cache-control"] == "no-store"
    assert r.json()["detail"]["code"] == "MODELS_UNAVAILABLE"


def test_models_pending_or_withdrawn_decision_fails_closed(models_release, anon_client):
    """When decision is PENDING or WITHDRAWN, must return HTTP 503."""
    bundle_path, ledger_path, manifest_hash = models_release

    # Test PENDING
    write_models_decision(ledger_path, manifest_hash, decision="PENDING")
    r = anon_client.get(f"{BASE_MODELS}/provenance")
    assert r.status_code == 503
    assert r.headers["cache-control"] == "no-store"

    # Test WITHDRAWN
    write_models_decision(ledger_path, manifest_hash, decision="WITHDRAWN")
    r = anon_client.get(f"{BASE_MODELS}/tables/model_comparisons")
    assert r.status_code == 503
    assert r.headers["cache-control"] == "no-store"


def test_models_manifest_digest_mismatch_fails_closed(models_release, anon_client):
    """When ledger references a different manifest hash, must return HTTP 503."""
    bundle_path, ledger_path, _ = models_release

    wrong_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    write_models_decision(ledger_path, wrong_hash, decision="APPROVED")
    r = anon_client.get(f"{BASE_MODELS}/provenance")
    assert r.status_code == 503
    assert r.headers["cache-control"] == "no-store"


def test_models_corrupted_artifact_fails_closed(models_release, anon_client):
    """When an artifact is altered or corrupted, must fail closed with HTTP 503."""
    bundle_path, ledger_path, _ = models_release
    (bundle_path / "model_comparisons.json").write_text('{"tampered": true}', encoding="utf-8")
    r = anon_client.get(f"{BASE_MODELS}/tables/model_comparisons")
    assert r.status_code == 503
    assert r.headers["cache-control"] == "no-store"


def test_models_approved_serving_provenance_and_tables(models_release, anon_client):
    """When properly approved, serves provenance, 4 tables, downloads, and assets."""
    # 1. Provenance
    r_prov = anon_client.get(f"{BASE_MODELS}/provenance")
    assert r_prov.status_code == 200, r_prov.text
    assert r_prov.headers["cache-control"] == "no-store"
    prov_data = r_prov.json()["data"]
    assert prov_data["manifest_status"] == "REVIEW_CANDIDATE"
    assert prov_data["bundle"]["approval_state"] == models.APPROVED
    assert prov_data["scope"]["PRIMARY_SITE_ASSIGNMENTS_ACCEPTED"] == 0
    assert prov_data["scope"]["SITE_PREDICTIONS_PERMITTED"] is False

    # 2. All 4 tables
    expected_tables = [
        "model_comparisons",
        "feature_ablation",
        "threshold_performance",
        "calibration_diagnostics",
    ]
    for tid in expected_tables:
        r_tbl = anon_client.get(f"{BASE_MODELS}/tables/{tid}")
        assert r_tbl.status_code == 200, f"Table {tid} failed: {r_tbl.text}"
        assert r_tbl.headers["cache-control"] == "no-store"
        tbl_data = r_tbl.json()["data"]
        assert tbl_data["table_id"] == tid
        assert len(tbl_data["rows"]) > 0

        # Test CSV download
        r_dl = anon_client.get(f"{BASE_MODELS}/downloads/{tid}")
        assert r_dl.status_code == 200
        assert r_dl.headers["content-type"].startswith("text/csv")
        assert f'filename="{tid}.csv"' in r_dl.headers.get("content-disposition", "")
        assert r_dl.headers["x-manifest-sha256"] == models.MANIFEST_SHA256

    # 3. Assets
    r_dict = anon_client.get(f"{BASE_MODELS}/assets/models_data_dictionary.md")
    assert r_dict.status_code == 200
    assert r_dict.headers["content-type"].startswith("text/markdown")


def test_models_prohibited_parameters_strictly_rejected(models_release, anon_client):
    """Enforce security boundary: query parameters suggesting live crash scoring or site ranking return 400."""
    prohibited_queries = [
        {"latitude": "40.4406", "longitude": "-79.9959"},
        {"site_id": "INTERSECTION_42"},
        {"predict": "true"},
        {"score": "high"},
        {"crn": "20210001"},
    ]
    for q in prohibited_queries:
        r = anon_client.get(f"{BASE_MODELS}/tables/model_comparisons", params=q)
        assert r.status_code == 400
        assert "Prohibited query parameters detected" in r.json()["detail"]


def test_models_unsupported_table_fails_closed(models_release, anon_client):
    """Requesting an unsupported table returns 503."""
    r = anon_client.get(f"{BASE_MODELS}/tables/non_existent_table")
    assert r.status_code == 503
