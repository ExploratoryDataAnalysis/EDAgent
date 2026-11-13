"""Expose treatment references and hypothetical-only arithmetic."""

import json
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BeforeValidator

from app.schemas.common import APIResponse
from app.schemas.intervention import EvidenceFactorRequest, IllustrativeResult, InterventionScenario
from app.services.intervention_service import calculate_scenario

router = APIRouter()
REGISTER = Path(__file__).resolve().parents[3] / "treatment_evidence" / "register.json"

REAL_SITE_FIELDS = {
    "address", "coordinates", "county", "crashid", "crashrecord", "crn", "facilityid",
    "geometry", "intersection",
    "intersectionid", "latitude", "lat", "location", "locationid", "locationname",
    "longitude", "lon", "lng", "mapcontext", "mapselection", "markerid", "place", "placeid",
    "reallocation", "realsite", "realsitebenefit", "realsiteestimate", "realsiteid",
    "road", "roadid", "roadname", "roadsegment", "roadsegmentid", "route", "routeid",
    "segment", "segmentid", "site",
    "siteid", "sitename", "siteyear", "station", "stationid", "stationnumber",
    "trafficsection", "trafficsectionid",
}
MODE_FIELDS = {"kind", "mode", "requesttype", "scenariokind", "scenariomode"}
REAL_SITE_MODES = {"real", "reallocation", "realsite", "realsitebenefit", "realsiteestimate", "sitespecific"}


def _has_real_site(value: object) -> bool:
    # Clients can supply location context in a nested object or use camelCase field names.
    if isinstance(value, dict):
        for key, item in value.items():
            field = re.sub(r"[^a-z0-9]", "", key.lower())
            if field in REAL_SITE_FIELDS:
                return True
            if field in MODE_FIELDS and isinstance(item, str):
                mode = re.sub(r"[^a-z0-9]", "", item.lower())
                if mode in REAL_SITE_MODES:
                    return True
            if _has_real_site(item):
                return True
    elif isinstance(value, list):
        return any(_has_real_site(item) for item in value)
    return False


def _reject_real_site(value: object):
    if _has_real_site(value):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "REAL_SITE_BENEFIT_UNAVAILABLE",
                "message": "Real-site treatment benefits are unavailable. An accepted site baseline and applicable factor are unavailable under v3.",
            },
        )
    return value


def _check_location_query(request: Request) -> None:
    for key, value in request.query_params.multi_items():
        _reject_real_site({key: value})


def _read_register() -> dict:
    return json.loads(REGISTER.read_text(encoding="utf-8"))


@router.get("/evidence", response_model=APIResponse[dict], dependencies=[Depends(_check_location_query)])
def evidence_register():
    return APIResponse(data=_read_register())


@router.post(
    "/scenarios",
    response_model=APIResponse[IllustrativeResult],
    dependencies=[Depends(_check_location_query)],
)
def illustrative_scenario(
    request: Request,
    # Refuse location context before validating any of the numeric scenario inputs.
    scenario: Annotated[InterventionScenario, BeforeValidator(_reject_real_site), Body()],
):
    if request.query_params:
        raise HTTPException(
            422, detail={"code": "INVALID_QUERY", "message": "Use the scenario request body."}
        )
    if isinstance(scenario.cmf, EvidenceFactorRequest):
        entry = next(
            (
                record for record in _read_register()["records"]
                if record["EVIDENCE_ID"] == scenario.cmf.evidence_id
            ),
            None,
        )
        if entry is None:
            raise HTTPException(404, detail={"code": "EVIDENCE_NOT_FOUND", "message": "Treatment reference not found."})
        # The closed v3 register has no reviewed numeric entries.
        raise HTTPException(
            status_code=422,
            detail={
                "code": "NO_APPROVED_NUMERIC_CMF",
                "message": "This treatment reference has no approved numeric factor. You can enter a hypothetical factor in illustrative mode.",
                "evidence_id": entry["EVIDENCE_ID"],
                "evidence_status": entry["EVIDENCE_STATUS"],
            },
        )
    return APIResponse(data=calculate_scenario(scenario))
