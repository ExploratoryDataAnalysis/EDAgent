"""
Background Job Monitoring & Cancellation Endpoints
"""

from fastapi import APIRouter
from app.schemas.job import JobStatusResponse, JobCancelResponse
from app.schemas.common import APIResponse

router = APIRouter()


@router.get("/{job_id}", response_model=APIResponse[JobStatusResponse], summary="Get Job Status")
async def get_job_status(job_id: str):
    """Polls progress percentage, status message, and execution state of background tasks."""
    return APIResponse(
        success=True,
        message="Job status retrieved.",
        data=None
    )


@router.post("/{job_id}/cancel", response_model=APIResponse[JobCancelResponse], summary="Cancel Job")
async def cancel_job(job_id: str):
    """Terminates or revokes an active background task."""
    return APIResponse(
        success=True,
        message="Job cancellation requested.",
        data=None
    )
