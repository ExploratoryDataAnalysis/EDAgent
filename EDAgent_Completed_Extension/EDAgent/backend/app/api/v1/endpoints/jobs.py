"""Background job status, listing and cancellation (user-scoped)."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.job import BackgroundJob
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.job import JobCancelResponse, JobStatusResponse
from app.services.jobs import runner

router = APIRouter()


def _to_schema(j: BackgroundJob) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=str(j.id), dataset_id=j.dataset_id, session_id=j.session_id, job_type=j.job_type, status=j.status,
        progress_percentage=j.progress_percentage, status_message=j.status_message, error_details=j.error_details,
        result_ref=j.result_ref, created_at=j.created_at, completed_at=j.completed_at,
    )


@router.get("", response_model=APIResponse[List[JobStatusResponse]], summary="List My Jobs")
async def list_jobs(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(BackgroundJob).where(BackgroundJob.user_id == user.id).order_by(BackgroundJob.created_at.desc()).limit(50))).scalars().all()
    return APIResponse(success=True, message=f"{len(rows)} job(s).", data=[_to_schema(j) for j in rows])


@router.get("/{job_id}", response_model=APIResponse[JobStatusResponse], summary="Job Status")
async def get_job(job_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    j = (await db.execute(select(BackgroundJob).where(BackgroundJob.id == job_id, BackgroundJob.user_id == user.id))).scalar_one_or_none()
    if not j:
        raise HTTPException(status_code=404, detail="Job not found.")
    return APIResponse(success=True, message="Job status.", data=_to_schema(j))


@router.post("/{job_id}/cancel", response_model=APIResponse[JobCancelResponse], summary="Cancel Job")
async def cancel_job(job_id: uuid.UUID, user: User = Depends(get_current_user)):
    outcome = runner.cancel(job_id, user.id)
    if outcome is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    msg = "Job cancelled." if outcome else "The job is already running or finished and cannot be cancelled."
    return APIResponse(success=True, message=msg, data=JobCancelResponse(job_id=str(job_id), cancelled=outcome, message=msg))
