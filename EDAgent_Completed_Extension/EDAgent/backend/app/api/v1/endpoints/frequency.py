"""Serve approved historical screening and explicitly unavailable frequency predictions."""

import csv
import io
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.road_safety_release import ReleaseUnavailable, approved_bytes, verify_release
from app.schemas.common import APIResponse

router = APIRouter()
UNAVAILABLE = "Site-level historical screening is outside Project Plan v3 release scope."
SCREENING_OUTPUTS = {
    "historical_crash_concentration.csv",
    "historical_concentration_by_year.csv",
    "historical_concentration_by_road_class.csv",
    "historical_concentration_by_site_type.csv",
    "top_concentration_sites_geographic.geojson",
}


def require_reviewed_concentration():
    root = Path(os.environ.get("ROAD_SAFETY_RELEASE_ROOT", "data/exports/road_safety"))
    approvals = os.environ.get("ROAD_SAFETY_APPROVALS")
    path = root / "visualizations"
    try:
        if not approvals:
            raise ReleaseUnavailable("Approval ledger is absent")
        manifest = verify_release(path, approvals, "visualizations")
        if not SCREENING_OUTPUTS <= manifest["outputs"].keys():
            raise ReleaseUnavailable("The approved screening bundle is incomplete")
        return path, manifest
    except ReleaseUnavailable as exc:
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from exc


def _standard_metadata(bundle=None):
    scope = bundle[1]["scope"] if bundle else {}
    years = scope.get("observed_years", [])
    return {
        "analysis_type": "HISTORICAL_CRASH_CONCENTRATION",
        "analysis_period": f"{years[0]}-{years[-1]}" if years else None,
        "is_predictive": False,
        "coverage_status": "REVIEWED_SCOPE" if bundle else "UNVERIFIED",
        "crosswalk_version": scope.get("crosswalk_version"),
        "supported_scope": scope,
    }


def _payload(bundle, name, parse):
    try:
        return parse(approved_bytes(*bundle, name).decode("utf-8"))
    except (ReleaseUnavailable, UnicodeError, ValueError, KeyError, TypeError, csv.Error) as exc:
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from exc


def _rows(bundle, name):
    return _payload(bundle, name, lambda data: list(csv.DictReader(io.StringIO(data))))


def _summary_rows(bundle, name, year=False):
    def parse(data):
        rows = list(csv.DictReader(io.StringIO(data)))
        fields = ["eligible_site_years", "observed_site_years", "crashes"]
        if year:
            fields.append("crash_year")
        for row in rows:
            for field in fields:
                row[field] = int(row[field])
        return rows

    return _payload(bundle, name, parse)


def _site_rows(bundle):
    def parse(data):
        rows = list(csv.DictReader(io.StringIO(data)))
        for row in rows:
            for field in ("crashes", "observed_site_years"):
                row[field] = int(row[field])
            row["screening_value"] = float(row["screening_value"])
            row["segment_length_km"] = float(row["segment_length_km"]) if row["segment_length_km"] else None
        return rows

    return _payload(bundle, "historical_crash_concentration.csv", parse)


@router.get("/status")
async def get_modelling_status() -> APIResponse[dict[str, Any]]:
    try:
        bundle = require_reviewed_concentration()
    except HTTPException:
        bundle = None
    return APIResponse(success=True, message="Frequency modelling and concentration status retrieved.", data={
        "predictive_frequency_modeling": {
            "decision": "NO-GO", "status": "BLOCKED",
            "reason": "Frequency inference requires separately validated and approved exposure and models.",
        },
        "mandated_active_pathway": {
            "pathway_name": "Historical Crash-Concentration Alternative",
            "status": "AVAILABLE" if bundle else "BLOCKED_PENDING_REVIEW",
        },
        "metadata": _standard_metadata(bundle),
    })


@router.get("/predictions/{site_id}")
async def get_site_prediction(site_id: str, year: int = 2024) -> APIResponse[dict[str, Any]]:
    site_id = site_id.strip()
    try:
        bundle = require_reviewed_concentration()
        screening = next((row for row in _site_rows(bundle) if row["site_id"] == site_id), None)
    except HTTPException:
        bundle, screening = None, None
    return APIResponse(success=True, message="Predictive frequency is unavailable pending review.", data={
        "site_id": site_id,
        "prediction_year": year,
        "expected_crash_frequency": None,
        "exposure_basis": "UNAVAILABLE",
        "prediction_status": "BLOCKED_INSUFFICIENT_EXPOSURE",
        "metadata": _standard_metadata(bundle),
        "historical_concentration_alternative": screening,
    })


@router.get("/concentration/annual")
async def get_annual_concentration_trends(bundle=Depends(require_reviewed_concentration)) -> APIResponse[dict[str, Any]]:
    rows = _summary_rows(bundle, "historical_concentration_by_year.csv", year=True)
    return APIResponse(success=True, message="Annual concentration trends retrieved.",
                       data={"trends": rows, "metadata": _standard_metadata(bundle)})


@router.get("/concentration/breakdown")
async def get_concentration_breakdown(bundle=Depends(require_reviewed_concentration)) -> APIResponse[dict[str, Any]]:
    return APIResponse(success=True, message="Stratified concentration breakdowns retrieved.", data={
        "by_road_class": _summary_rows(bundle, "historical_concentration_by_road_class.csv"),
        "by_site_type": _summary_rows(bundle, "historical_concentration_by_site_type.csv"),
        "metadata": _standard_metadata(bundle),
    })


@router.get("/concentration/geojson")
async def get_concentration_geojson(bundle=Depends(require_reviewed_concentration)) -> APIResponse[dict[str, Any]]:
    document = _payload(bundle, "top_concentration_sites_geographic.geojson", json.loads)
    return APIResponse(success=True, message="Historical screening map retrieved.",
                       data={**document, "metadata": _standard_metadata(bundle)})


@router.get("/severity/retrospective")
async def get_retrospective_severity(bundle=Depends(require_reviewed_concentration)) -> APIResponse[dict[str, Any]]:
    return APIResponse(success=True, message="Retrospective severity analysis retrieved.", data={
        "analysis_type": "RETROSPECTIVE_SEVERITY_ASSOCIATION",
        "is_predictive": False,
        "is_causal": False,
        "results": _rows(bundle, "severity_retrospective_associations.csv"),
        "metadata": _standard_metadata(bundle),
    })


@router.get("/concentration/top")
async def get_top_concentration_sites(
    road_class: str | None = None,
    site_type: str = Query("SEGMENT", pattern="^(SEGMENT|INTERSECTION)$"),
    limit: int = Query(20, ge=1, le=100),
    bundle=Depends(require_reviewed_concentration),
) -> APIResponse[dict[str, Any]]:
    rows = [r for r in _site_rows(bundle) if r["site_type"] == site_type
            and (road_class is None or r["road_class"].upper() == road_class.upper())]
    rows.sort(key=lambda row: (-row["screening_value"], row["site_id"]))
    return APIResponse(success=True, message="Historical screening results retrieved.",
                       data={"sites": rows[:limit], "metadata": _standard_metadata(bundle)})


@router.get("/concentration/{site_id}")
async def get_site_concentration(site_id: str, bundle=Depends(require_reviewed_concentration)) -> APIResponse[dict[str, Any]]:
    for row in _site_rows(bundle):
        if row["site_id"] == site_id.strip():
            return APIResponse(success=True, message="Historical concentration record retrieved.",
                               data={"site": row, "metadata": _standard_metadata(bundle)})
    raise HTTPException(status_code=404, detail="Site is outside the approved historical screening records.")
