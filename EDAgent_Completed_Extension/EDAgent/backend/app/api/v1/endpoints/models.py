"""Serve approved retrospective severity model diagnostics and candidate derivatives.

Scientific Scope & Security Boundaries:
- Evaluates binary severe injury (fatal or suspected serious) conditioned strictly on
  already reported crashes with known outcomes (2016–2024).
- Gated by ROAD_SAFETY_APPROVALS ledger with kind 'models'. Fails closed (HTTP 503)
  if unapproved, pending, withdrawn, or corrupted.
- NEVER deserializes joblib files or runs live estimators in request paths.
- NEVER accepts or evaluates site coordinates, intersection IDs, or live crash payloads.
"""

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.road_safety_release import ReleaseUnavailable, approved_bytes, verify_release_decision
from app.schemas.common import APIResponse

router = APIRouter()
logger = logging.getLogger(__name__)

KIND = "models"
VERSION = "v3-d5-1"
MANIFEST_SHA256 = "4ac5f547d111661c19e5b10291106d5c6ed0709a526a3b03a51732561ad7321b"
SCHEMA_VERSION = 1
APPROVED = "APPROVED_SEVERITY_MODELS_RELEASE"

TABLES = {
    "model_comparisons": "Retrospective severity model metrics evaluated on 2022–2024 holdout.",
    "feature_ablation": "Cramér's V associations and collision-type timing comparison.",
    "threshold_performance": "Confusion matrix counts and balanced accuracy at 0.50 threshold.",
    "calibration_diagnostics": "Calibrated vs uncalibrated Brier scores against base rate reference.",
}

ASSETS = {
    "models_data_dictionary.md": "text/markdown",
}

OUTPUTS = {*ASSETS, *(f"{table}.{extension}" for table in TABLES for extension in ("json", "csv"))}

PROHIBITED_QUERY_PARAMS = {
    "crn", "case_id", "crash_id", "lat", "latitude", "lon", "longitude",
    "dec_lat", "dec_long", "site_id", "intersection_id", "predict", "score", "risk"
}

UNAVAILABLE = {
    "code": "MODELS_UNAVAILABLE",
    "message": "The reviewed Retrospective Severity Models dataset is unavailable.",
    "approval_state": None,
    "data": None,
}


def unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail=UNAVAILABLE, headers={"Cache-Control": "no-store"})


def check_no_prohibited_params(request: Request):
    """Enforce strict scientific boundary: prohibit live scoring, coordinates, and site ranking."""
    query_keys = {k.lower() for k in request.query_params.keys()}
    intersection = query_keys & PROHIBITED_QUERY_PARAMS
    if intersection:
        raise HTTPException(
            status_code=400,
            detail=f"Prohibited query parameters detected: {sorted(intersection)}. "
                   "Site-level risk, coordinate evaluation, and live crash scoring are strictly prohibited.",
            headers={"Cache-Control": "no-store"}
        )


@dataclass
class Release:
    path: Path
    manifest: dict
    approval_date: str

    def payload(self, name: str) -> bytes:
        try:
            if name not in OUTPUTS:
                raise ReleaseUnavailable(f"Unsupported models artifact: {name}")
            return approved_bytes(self.path, self.manifest, name)
        except ReleaseUnavailable as exc:
            logger.warning("Models artifact unavailable: %s", exc)
            raise unavailable() from exc

    def bundle(self, name: Optional[str] = None) -> dict:
        return {
            "kind": KIND,
            "version": self.manifest["version"],
            "manifest_sha256": MANIFEST_SHA256,
            "output_sha256": self.manifest["outputs"].get(name),
            "approval_state": APPROVED,
        }

    def provenance(self, name: Optional[str] = None) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.manifest["run_id"],
            "sources": self.manifest["inputs"],
            "bundle": self.bundle(name),
        }

    def rows(self, table: str) -> list:
        try:
            return json.loads(self.payload(f"{table}.json").decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            logger.warning("Could not decode verified models table %s: %s", table, exc)
            raise unavailable() from exc


def find_models_bundle_path() -> Path:
    """Locate candidate or published models bundle path based on environment or repo layout."""
    override = os.environ.get("ROAD_SAFETY_MODELS_ROOT")
    if override:
        p = Path(override).resolve()
        if (p / "manifest.json").exists():
            return p
        if (p / "models" / "candidate" / "manifest.json").exists():
            return p / "models" / "candidate"
        if (p / KIND / "manifest.json").exists():
            return p / KIND

    release_root = os.environ.get("ROAD_SAFETY_RELEASE_ROOT")
    if release_root:
        p = Path(release_root).resolve()
        if (p / "models" / "candidate" / "manifest.json").exists():
            return p / "models" / "candidate"
        if (p / KIND / "manifest.json").exists():
            return p / KIND
        if (p / "manifest.json").exists():
            return p

    # Standard repo relative paths searching from CWD and parents of __file__
    search_paths = [
        Path("data/exports/models/candidate"),
        Path("../data/exports/models/candidate"),
        Path("../../data/exports/models/candidate"),
        Path("../../../data/exports/models/candidate"),
        *(p / "data" / "exports" / "models" / "candidate" for p in Path(__file__).resolve().parents),
        *(p / "data" / "exports" / "models" / "candidate" for p in Path.cwd().parents),
    ]
    for sp in search_paths:
        if (sp / "manifest.json").exists():
            return sp.resolve()

    # Fallback default
    return Path("data/exports/models/candidate").resolve()


def reviewed_release(request: Request, response: Response) -> Release:
    """Enforce release gate on ROAD_SAFETY_APPROVALS ledger for models."""
    check_no_prohibited_params(request)

    approvals = os.environ.get("ROAD_SAFETY_APPROVALS")
    if not approvals:
        logger.info("Models unavailable: ROAD_SAFETY_APPROVALS not set")
        raise unavailable()

    path = find_models_bundle_path()
    try:
        manifest, decision = verify_release_decision(
            path, approvals, KIND, expected_manifest_sha256=MANIFEST_SHA256
        )
        scope = manifest.get("scope", {})
        if (
            manifest.get("version") != VERSION
            or manifest.get("schema_version") != SCHEMA_VERSION
            or scope.get("geoid") != "42003"
            or scope.get("claim_class") != "RETROSPECTIVE_SEVERITY_MODEL_DIAGNOSTICS"
            or scope.get("PRIMARY_SITE_ASSIGNMENTS_ACCEPTED") != 0
            or scope.get("SITE_PREDICTIONS_PERMITTED") is not False
            or scope.get("LIVE_INFERENCE_PERMITTED") is not False
            or scope.get("CASES_SCORED_PERMITTED") is not False
            or not (set(OUTPUTS) <= set(manifest.get("outputs", {}).keys()))
        ):
            raise ReleaseUnavailable("Unsupported models schema or scope constraints violated")
    except (ReleaseUnavailable, KeyError, ValueError) as exc:
        logger.info("Models release check failed: %s", exc)
        raise unavailable() from exc

    response.headers["Cache-Control"] = "no-store"
    return Release(path, manifest, decision.get("date", ""))


@router.get("/provenance", response_model=APIResponse[dict])
def provenance(request: Request, release: Release = Depends(reviewed_release)):
    """Return scientific provenance, checksums, scope, and verification metadata."""
    manifest = release.manifest
    return APIResponse(data={
        **release.provenance(),
        "scope": manifest["scope"],
        "manifest_status": manifest["status"],
        "tables": manifest.get("tables", []),
        "outputs": {name: manifest["outputs"][name] for name in sorted(OUTPUTS)},
    })


@router.get("/tables/{table_id}", response_model=APIResponse[dict])
def table_data(table_id: str, request: Request, release: Release = Depends(reviewed_release)):
    """Return verified tabular rows and schema for a supported models table."""
    if table_id not in TABLES:
        raise unavailable()

    rows = release.rows(table_id)
    return APIResponse(data={
        "table_id": table_id,
        "title": TABLES[table_id],
        "rows": rows,
        "row_count": len(rows),
        **release.provenance(f"{table_id}.json"),
    })


def artifact_response(release: Release, name: str, media_type: str, manifest_sha256: Optional[str]) -> Response:
    bundle = release.bundle(name)
    if manifest_sha256 is not None and manifest_sha256 != bundle["manifest_sha256"]:
        raise unavailable()
    payload = release.payload(name)
    return Response(
        content=payload,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'",
            "X-Content-Type-Options": "nosniff",
            "X-Bundle-Version": bundle["version"],
            "X-Manifest-SHA256": bundle["manifest_sha256"],
            "X-Artifact-SHA256": bundle["output_sha256"] or "",
            "Link": '<../provenance>; rel="describedby"',
        }
    )


@router.get("/downloads/{table_id}")
def download_table(
    table_id: str,
    request: Request,
    manifest_sha256: Optional[str] = Query(None),
    release: Release = Depends(reviewed_release)
):
    """Download verified CSV representation of a models table."""
    if table_id not in TABLES:
        raise unavailable()
    filename = f"{table_id}.csv"
    response = artifact_response(release, filename, "text/csv", manifest_sha256)
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@router.get("/assets/{name}")
def get_asset(
    name: str,
    request: Request,
    manifest_sha256: Optional[str] = Query(None),
    release: Release = Depends(reviewed_release)
):
    """Download verified release assets (e.g., data dictionary markdown or manifest)."""
    if name == "manifest.json":
        bundle = release.bundle()
        if manifest_sha256 is not None and manifest_sha256 != bundle["manifest_sha256"]:
            raise unavailable()
        payload = (release.path / "manifest.json").read_bytes()
        return Response(
            content=payload,
            media_type="application/json",
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'",
                "X-Content-Type-Options": "nosniff",
                "X-Bundle-Version": bundle["version"],
                "X-Manifest-SHA256": bundle["manifest_sha256"],
                "Link": '<../provenance>; rel="describedby"',
            }
        )
    if name not in ASSETS:
        raise unavailable()
    return artifact_response(release, name, ASSETS[name], manifest_sha256)
