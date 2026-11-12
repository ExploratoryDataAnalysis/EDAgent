"""API endpoints for site-year frequency modelling, historical crash concentration, and retrospective severity.

Governed by Project Plan v2 (§8, §14, §18) and Phase 4 Module C requirements.
Ensures the backend application handles unavailable predictive frequency models
gracefully, prevents unsupported predictions from being exposed, and serves the
mandated Historical Crash-Concentration Alternative with explicit metadata.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.common import APIResponse

router = APIRouter()


async def require_reviewed_concentration() -> None:
    """Do not serve legacy artifacts while the crosswalk release is unreviewed."""
    raise HTTPException(status_code=503, detail="Historical concentration is unavailable pending crosswalk and artifact review.")

CONCENTRATION_CSV_PATH = Path("data/exports/frequency/historical_crash_concentration.csv")
YEAR_CSV_PATH = Path("data/exports/frequency/historical_concentration_by_year.csv")
CLASS_CSV_PATH = Path("data/exports/frequency/historical_concentration_by_road_class.csv")
TYPE_CSV_PATH = Path("data/exports/frequency/historical_concentration_by_site_type.csv")
GEOJSON_PATH = Path("data/exports/frequency/top_concentration_sites_geographic.geojson")
SEVERITY_CSV_PATH = Path("data/exports/frequency/severity_retrospective_associations.csv")


def _standard_metadata() -> Dict[str, Any]:
    """Standardized metadata block adhering to Phase 4 Module C requirements."""
    return {
        "analysis_type": "HISTORICAL_CRASH_CONCENTRATION",
        "analysis_period": "2004-2024",
        "is_predictive": False,
        "coverage_status": "UNVERIFIED",
        "crosswalk_version": None,
        "limitations": [
            "No reviewed crosswalk or exposure coverage assessment is available.",
            "Historical concentration artifacts are withheld pending review.",
        ],
    }


def _load_concentration_record(site_id: str) -> Optional[Dict[str, Any]]:
    """Lookup a historical concentration record by site_id."""
    if not CONCENTRATION_CSV_PATH.exists():
        return None

    with open(CONCENTRATION_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("site_id", "").strip() == site_id.strip():
                return {
                    "site_id": row["site_id"],
                    "road_class": row["road_class"],
                    "site_type": row["site_type"],
                    "segment_length_km": float(row["segment_length_km"]),
                    "total_crashes_2004_2024": int(row["total_crashes_2004_2024"]),
                    "fatal_crashes": int(row["fatal_crashes"]),
                    "major_injury_crashes": int(row["major_injury_crashes"]),
                    "ksi_crashes": int(row["ksi_crashes"]),
                    "pedestrian_crashes": int(row["pedestrian_crashes"]),
                    "bicycle_crashes": int(row["bicycle_crashes"]),
                    "vru_crashes": int(row["vru_crashes"]),
                    "crash_density_per_km": float(row["crash_density_per_km"]),
                    "ksi_density_per_km": float(row["ksi_density_per_km"]),
                    "vru_density_per_km": float(row["vru_density_per_km"]),
                    "epoch1_crashes_2004_2010": int(row["epoch1_crashes_2004_2010"]),
                    "epoch2_crashes_2011_2017": int(row["epoch2_crashes_2011_2017"]),
                    "epoch3_crashes_2018_2024": int(row["epoch3_crashes_2018_2024"]),
                    "persistence_category": row["persistence_category"],
                    "road_class_percentile": float(row["road_class_percentile"]),
                }
    return None


@router.get("/status", summary="Frequency Modelling & Concentration Pathway Status")
async def get_modelling_status() -> APIResponse[Dict[str, Any]]:
    """Returns the feasibility decision, active reporting pathway, and exposure gates."""
    status_data = {
        "module": "Phase 4 — Module C (Historical Concentration & Retrospective Severity)",
        "predictive_frequency_modeling": {
            "decision": "NO-GO",
            "status": "BLOCKED",
            "reason": (
                "A reviewed site-year frame and linked traffic exposure are unavailable."
            ),
            "failed_criteria": [],
        },
        "mandated_active_pathway": {
            "pathway_name": "Historical Crash-Concentration Alternative",
            "status": "BLOCKED_PENDING_REVIEW",
            "description": (
                "Historical screening requires a reviewed crosswalk and corrected denominators."
            ),
        },
        "metadata": _standard_metadata(),
    }
    return APIResponse(
        success=True,
        message="Frequency modelling and concentration status retrieved.",
        data=status_data,
    )


@router.get("/predictions/{site_id}", summary="Get Site-Year Prediction (Graceful Block Handling)")
async def get_site_prediction(
    site_id: str,
    year: int = Query(2024, description="Evaluation year"),
) -> APIResponse[Dict[str, Any]]:
    """Handles frequency prediction requests gracefully when predictive modelling is blocked.

    In accordance with Phase 4 Module B/C invariants:
    - Never presents an expected frequency prediction when exposure data is unverified.
    - Explicitly returns `expected_crash_frequency: null` and status `BLOCKED_INSUFFICIENT_EXPOSURE`.
    - Supplies the empirical historical concentration metrics as the sanctioned alternative.
    """
    clean_site_id = site_id.strip()
    conc_record = None  # Legacy concentration is not approved for display.

    prediction_contract = {
        "site_id": clean_site_id,
        "prediction_year": year,
        "expected_crash_frequency": None,  # Strictly None under NO-GO invariant
        "model_name": "Poisson_GLM / Negative_Binomial_NB2",
        "model_version": "1.0.0",
        "exposure_basis": "UNAVAILABLE",
        "training_period": "2016-2020",
        "validation_period": "2021-2024",
        "prediction_status": "BLOCKED_INSUFFICIENT_EXPOSURE",
        "metadata": _standard_metadata(),
        "historical_concentration_alternative": conc_record,
    }

    return APIResponse(
        success=True,
        message="Predictive frequency and historical concentration are unavailable pending review.",
        data=prediction_contract,
    )


@router.get("/concentration/annual", summary="Get Annual Concentration & Coverage Trends", dependencies=[Depends(require_reviewed_concentration)])
async def get_annual_concentration_trends() -> APIResponse[Dict[str, Any]]:
    """Retrieve annual crash counts, match coverage, and missing coordinates (2004–2024)."""
    if not YEAR_CSV_PATH.exists():
        raise HTTPException(status_code=404, detail="Annual concentration dataset not found.")

    rows = []
    with open(YEAR_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "crash_year": int(r["crash_year"]),
                "total_crashes": int(r["total_crashes"]),
                "matched_crashes": int(r["matched_crashes"]),
                "ambiguous_crashes": int(r["ambiguous_crashes"]),
                "unmatched_crashes": int(r["unmatched_crashes"]),
                "match_coverage_percent": r["match_coverage_percent"],
                "missing_coord_crashes": int(r["missing_coord_crashes"]),
                "missing_coord_percent": r["missing_coord_percent"],
                "fatal_crashes": int(r["fatal_crashes"]),
                "major_injury_crashes": int(r["major_injury_crashes"]),
                "ksi_crashes": int(r["ksi_crashes"]),
                "vru_crashes": int(r["vru_crashes"]),
            })

    return APIResponse(
        success=True,
        message="Annual concentration trends retrieved.",
        data={"trends": rows, "metadata": _standard_metadata()},
    )


@router.get("/concentration/breakdown", summary="Get Stratified Concentration by Class & Site Type", dependencies=[Depends(require_reviewed_concentration)])
async def get_concentration_breakdown() -> APIResponse[Dict[str, Any]]:
    """Retrieve stratified breakdowns across functional road classes and site types."""
    road_classes = []
    if CLASS_CSV_PATH.exists():
        with open(CLASS_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                road_classes.append({
                    "road_class": r["road_class"],
                    "total_crashes": int(r["total_crashes"]),
                    "matched_crashes": int(r["matched_crashes"]),
                    "ambiguous_crashes": int(r["ambiguous_crashes"]),
                    "unmatched_crashes": int(r["unmatched_crashes"]),
                    "unique_matched_sites": int(r["unique_matched_sites"]),
                    "match_coverage_percent": r["match_coverage_percent"],
                    "missing_coord_percent": r["missing_coord_percent"],
                })

    site_types = []
    if TYPE_CSV_PATH.exists():
        with open(TYPE_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                site_types.append({
                    "site_type": r["site_type"],
                    "total_crashes": int(r["total_crashes"]),
                    "matched_crashes": int(r["matched_crashes"]),
                    "ambiguous_crashes": int(r["ambiguous_crashes"]),
                    "unmatched_crashes": int(r["unmatched_crashes"]),
                    "unique_matched_sites": int(r["unique_matched_sites"]),
                    "match_coverage_percent": r["match_coverage_percent"],
                    "missing_coord_percent": r["missing_coord_percent"],
                })

    return APIResponse(
        success=True,
        message="Stratified concentration breakdowns retrieved.",
        data={
            "by_road_class": road_classes,
            "by_site_type": site_types,
            "metadata": _standard_metadata(),
        },
    )


@router.get("/concentration/geojson", summary="Get GeoJSON of Top High-Concentration Sites", dependencies=[Depends(require_reviewed_concentration)])
async def get_concentration_geojson() -> APIResponse[Dict[str, Any]]:
    """Retrieve standard GeoJSON FeatureCollection with validated site coordinates."""
    if not GEOJSON_PATH.exists():
        raise HTTPException(status_code=404, detail="GeoJSON visualization dataset not found.")

    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        geojson_doc = json.load(f)

    return APIResponse(
        success=True,
        message="Top concentration GeoJSON retrieved.",
        data=geojson_doc,
    )


@router.get("/severity/retrospective", summary="Get Retrospective Severity Analysis & Limitations", dependencies=[Depends(require_reviewed_concentration)])
async def get_retrospective_severity() -> APIResponse[Dict[str, Any]]:
    """Retrieve retrospective severity association metrics, AP intervals, and caveats."""
    items = []
    if SEVERITY_CSV_PATH.exists():
        with open(SEVERITY_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                items.append(dict(r))

    severity_data = {
        "analysis_type": "RETROSPECTIVE_SEVERITY_ASSOCIATION",
        "analysis_period": "2016-2023",
        "is_predictive": False,
        "is_causal": False,
        "outcome_definition": "FATAL_OR_MAJ_INJ (KABCO Scale K or A)",
        "prevalence_percent": 4.44,
        "temporal_code_break_year": 2016,
        "records_tested": 77476,
        "results": items,
        "limitations": [
            "Retrospective Association Only: Evaluates severity ranking among already reported crashes; does not predict crash occurrence.",
            "Post-Crash Collision Type: Collision type (Cramér's V = 0.202) is observed post-crash. Models without collision type achieve AP=0.0517 (near baseline).",
            "Class Imbalance: Severe outcomes represent only 4.44% of reported crashes.",
            "Code Break: Pennsylvania adopted the MMUCC 4th Edition injury standard in 2016; pre-2016 severe injury definitions are non-comparable.",
            "Zero Causal Inference: Categorical associations do not prove causation.",
        ],
    }
    return APIResponse(
        success=True,
        message="Retrospective severity analysis retrieved.",
        data=severity_data,
    )


@router.get("/concentration/top", summary="Get Top High-Hazard Roadway Sites", dependencies=[Depends(require_reviewed_concentration)])
async def get_top_concentration_sites(
    road_class: Optional[str] = Query(None, description="Filter by road class (e.g., STATE_ROUTE, LOCAL_STREET)"),
    limit: int = Query(20, ge=1, le=100, description="Number of sites to return"),
    persistence_category: Optional[str] = Query(None, description="Filter by persistence category"),
) -> APIResponse[Dict[str, Any]]:
    """Retrieve top crash-concentration sites ranked by historical density and persistence."""
    if not CONCENTRATION_CSV_PATH.exists():
        return APIResponse(
            success=True,
            message="Concentration dataset is not yet generated.",
            data={"sites": [], "metadata": _standard_metadata()},
        )

    results: List[Dict[str, Any]] = []
    with open(CONCENTRATION_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if road_class and row.get("road_class", "").upper() != road_class.upper():
                continue
            if persistence_category and row.get("persistence_category", "") != persistence_category:
                continue

            results.append(
                {
                    "site_id": row["site_id"],
                    "road_class": row["road_class"],
                    "site_type": row["site_type"],
                    "segment_length_km": float(row["segment_length_km"]),
                    "total_crashes_2004_2024": int(row["total_crashes_2004_2024"]),
                    "fatal_crashes": int(row["fatal_crashes"]),
                    "major_injury_crashes": int(row["major_injury_crashes"]),
                    "ksi_crashes": int(row["ksi_crashes"]),
                    "pedestrian_crashes": int(row["pedestrian_crashes"]),
                    "bicycle_crashes": int(row["bicycle_crashes"]),
                    "vru_crashes": int(row["vru_crashes"]),
                    "crash_density_per_km": float(row["crash_density_per_km"]),
                    "ksi_density_per_km": float(row["ksi_density_per_km"]),
                    "vru_density_per_km": float(row["vru_density_per_km"]),
                    "persistence_category": row["persistence_category"],
                    "road_class_percentile": float(row["road_class_percentile"]),
                }
            )
            if len(results) >= limit:
                break

    return APIResponse(
        success=True,
        message=f"Retrieved {len(results)} high-hazard sites.",
        data={"sites": results, "metadata": _standard_metadata()},
    )


@router.get("/concentration/{site_id}", summary="Get Site Historical Crash Concentration", dependencies=[Depends(require_reviewed_concentration)])
async def get_site_concentration(site_id: str) -> APIResponse[Dict[str, Any]]:
    """Retrieve empirical crash concentration, density, and persistence category for a site."""
    record = _load_concentration_record(site_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Site identifier '{site_id}' not found in canonical concentration records.",
        )
    return APIResponse(
        success=True,
        message="Historical concentration record retrieved.",
        data={"site": record, "metadata": _standard_metadata()},
    )
