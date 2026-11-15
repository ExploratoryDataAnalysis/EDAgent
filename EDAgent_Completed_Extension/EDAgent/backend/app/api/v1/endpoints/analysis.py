"""
Analysis endpoints: tool catalogue, suggested analyses, direct execution of an explicit plan
(used by the workspace builder) and retrieval of stored results.

Plans are validated against the dataset schema before anything runs; nothing here evaluates
user-supplied code.
"""

import asyncio
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import charge_guest, get_current_user
from app.models.user import User
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.analysis import AnalysisExecuteRequest, AnalysisResultResponse
from app.schemas.common import APIResponse
from app.services import analysis_service, dataset_service, guest_sessions
from app.services import report_service
from app.services.analysis import catalogue, engine
from app.services.jobs import runner
from app.services.analysis.common import AnalysisError, PlanValidationError
from app.services.suggestions import suggest_analyses

router = APIRouter()


@router.get("/catalogue", summary="List Approved Analysis Tools")
async def get_catalogue(user: User = Depends(get_current_user)):
    return APIResponse(success=True, message="Approved analysis tools.", data=catalogue.catalogue_for_api())


@router.get("/suggestions/{dataset_id}", summary="Suggested Analyses For A Dataset")
async def get_suggestions(dataset_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    dataset = await DatasetRepository(db).get_by_id(dataset_id, user.id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    profile = await dataset_service.get_or_compute_profile(db, dataset)
    return APIResponse(success=True, message="Suggested analyses.", data=suggest_analyses(profile))


@router.post("/execute", response_model=APIResponse[AnalysisResultResponse], summary="Execute An Analysis Plan")
async def execute_analysis_plan(payload: AnalysisExecuteRequest, user: User = Depends(charge_guest), db: AsyncSession = Depends(get_db)):
    """Runs an explicit plan inside one of the user's sessions and stores it in the session history."""
    session = await SessionRepository(db).get(payload.session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    dataset = await DatasetRepository(db).get_by_id(session.dataset_id, user.id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    try:
        result = await analysis_service.run_plan(db, dataset, payload.plan, guest=user.is_guest)
    except PlanValidationError as e:
        raise HTTPException(status_code=422, detail={"message": "The analysis plan is not valid for this dataset.", "problems": e.errors})
    except AnalysisError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if user.is_guest:
        await guest_sessions.lock_active(db, user.id)
    await analysis_service.add_multiple_test_warning(db, session.id, result)
    label = payload.label or f"Run {payload.plan.operation.value.replace('_', ' ')}"
    req = await analysis_service.persist_turn(
        db, session, question=label, kind="analysis", assistant_message=result.summary_text, plan=payload.plan,
        result=result, explanation_source="template",
    )
    result.request_id = req.id
    return APIResponse(success=True, message="Analysis executed successfully.", data=result)


@router.post("/execute-async", status_code=202, summary="Execute An Analysis As A Background Job")
async def execute_analysis_async(payload: AnalysisExecuteRequest, user: User = Depends(charge_guest), db: AsyncSession = Depends(get_db)):
    """For heavy operations (modelling on large data): returns a job id to poll at /jobs/{id}."""
    session = await SessionRepository(db).get(payload.session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    dataset = await DatasetRepository(db).get_by_id(session.dataset_id, user.id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    # Validate now so obvious mistakes fail fast instead of inside a job.
    loaded = await dataset_service.load_for_analysis(db, dataset, guest=user.is_guest)
    errors = catalogue.validate_plan(engine.effective_plan(payload.plan, loaded), loaded)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "The analysis plan is not valid for this dataset.", "problems": errors})
    await db.commit()  # release any write lock (e.g. a freshly stored profile) before the job thread touches the database
    try:
        job_id = await asyncio.to_thread(
            runner.create_job, user_id=user.id, job_type="analysis", dataset_id=dataset.id, session_id=session.id,
            message="Analysis queued", guest=user.is_guest,
        )
    except runner.JobLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    label = payload.label or f"Run {payload.plan.operation.value.replace('_', ' ')}"
    runner.submit(job_id, report_service.analysis_job(session.id, payload.plan, label, guest=user.is_guest), guest=user.is_guest)
    return APIResponse(success=True, message="Analysis started.", data={"job_id": str(job_id)})


@router.get("/results/{result_id}", response_model=APIResponse[AnalysisResultResponse], summary="Get Analysis Result")
async def get_analysis_result(result_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await SessionRepository(db).get_result(result_id, user.id)
    result = analysis_service.result_from_row(row) if row else None
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found.")
    return APIResponse(success=True, message="Result retrieved.", data=result)
