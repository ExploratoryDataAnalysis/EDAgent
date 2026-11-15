"""Public, read-only exercises using the same engine as the private workspace."""

import hashlib
import json
import os
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Response

from app.api.v1.endpoints import overview
from app.schemas.analysis import StructuredAnalysisPlan
from app.schemas.common import APIResponse
from app.services.analysis import engine
from app.services.data.loader import LoadedDataset, build_typed_frame
from app.services.export.files import result_metadata

router = APIRouter()
Sample = Literal["teaching", "county"]
Operation = Literal["descriptive_stats", "histogram"]
COUNTY_COLUMNS = ["period_start", "reported_crashes"]
TEACHING = {
    "title": "Invented teaching dataset",
    "source": "EDAgent teaching fixture. Twelve invented library return times in minutes.",
    "fixture_date": "2026-11-15",
    "interpretation": "Describe the invented returns. The values do not represent a real library.",
}


def county_sample(response: Response):
    if os.environ.get("ALLOW_COUNTY_ANALYSER_SAMPLE", "true").lower() != "true":
        raise overview.unavailable()
    release = overview.reviewed_release(response)
    try:
        rows = [
            [row[column] for column in COUNTY_COLUMNS]
            for row in release.rows("county_periods")
            if row["period_grain"] == "year"
        ]
    except (KeyError, TypeError) as exc:
        raise overview.unavailable() from exc
    if not rows or any(type(value) is not int or value < 0 for row in rows for value in row):
        raise overview.unavailable()
    return rows, {
        "title": "Approved county aggregates",
        "source": release.manifest["inputs"],
        "scope": release.manifest["scope"],
        "approval_date": release.approval_date,
        "run_id": release.manifest["run_id"],
        "bundle": release.bundle("county_periods.json"),
        "interpretation": "Describe annual counts of police-reported crashes in the fixed extract. "
        "These counts do not measure exposure, risk, forecasts, site rankings or treatment effects.",
    }


@router.get("")
def list_exercises(response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        _, county = county_sample(response)
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        county = None
    return APIResponse(data={"county": county})


def analyse(
    sample: Sample, operation: Operation, response: Response, manifest_sha256: str | None,
    instance_id: uuid.UUID | None = None,
):
    response.headers["Cache-Control"] = "no-store"
    if sample == "teaching":
        headers = ["return_minutes"]
        rows = [[n] for n in (4, 5, 5, 7, 8, 8, 9, 10, 12, 14, 18, 30)]
        provenance = TEACHING
    else:
        headers = COUNTY_COLUMNS
        rows, provenance = county_sample(response)
        if manifest_sha256 != provenance["bundle"]["manifest_sha256"]:
            raise overview.unavailable()
    columns = [{"name": name, "semantic_role": "measure", "inferred_type": "integer"} for name in headers]
    df, infos = build_typed_frame(headers, [[str(value) for value in row] for row in rows], columns)
    fingerprint = hashlib.sha256(json.dumps([headers, rows, provenance], sort_keys=True).encode()).hexdigest()
    plan = StructuredAnalysisPlan(operation=operation, column=headers[-1])
    # Keep public exercises out of workspace history and caches. Each run has its own result,
    # and a download must pass the same release check again before recomputing its numbers.
    result = engine.run_analysis(LoadedDataset(df, infos, fingerprint), plan, instance_id or uuid.uuid4(), use_cache=False)
    return result, provenance


@router.post("/{sample}/analysis")
def run_exercise(sample: Sample, operation: Operation, response: Response, manifest_sha256: str | None = None):
    result, provenance = analyse(sample, operation, response, manifest_sha256)
    return APIResponse(data={"result": result, "provenance": provenance})


@router.get("/{sample}/download")
def download_exercise(
    sample: Sample, operation: Operation, response: Response, manifest_sha256: str | None = None,
    instance_id: uuid.UUID | None = None,
):
    result, provenance = analyse(sample, operation, response, manifest_sha256, instance_id)
    return Response(
        json.dumps({
            "provenance": provenance,
            "analysis": result_metadata(result),
            "tables": [table.model_dump(mode="json") for table in result.tables],
        }, indent=2),
        media_type="application/json",
        headers={"Cache-Control": "no-store", "Content-Disposition": f'attachment; filename="{sample}-analysis.json"'},
    )
