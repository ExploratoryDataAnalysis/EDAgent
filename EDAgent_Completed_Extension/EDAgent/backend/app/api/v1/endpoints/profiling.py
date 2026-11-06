"""
Automatic profiling endpoints. Zero LLM involvement: every number is computed by the backend
from the original file, using the same parse options the dataset was ingested with.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.common import APIResponse
from app.schemas.profiler import ProfilerResultResponse
from app.services import dataset_service as svc
from app.services.ingestion.validator import IngestionValidationError

router = APIRouter()


async def _owned(db: AsyncSession, dataset_id: uuid.UUID, user: User):
    dataset = await DatasetRepository(db).get_by_id(dataset_id, user.id)
    if not dataset:
        raise IngestionValidationError(f"Dataset '{dataset_id}' not found.", error_code="FILE_NOT_FOUND")
    return dataset


@router.post("/{dataset_id}", response_model=APIResponse[ProfilerResultResponse], summary="Re-run Automatic Profiling")
async def trigger_profiling(dataset_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Forces a fresh profile (e.g. after the user changed parsing options)."""
    dataset = await _owned(db, dataset_id, user)
    profile = await svc.get_or_compute_profile(db, dataset, force=True)
    return APIResponse(success=True, message="Profiling generated successfully.", data=ProfilerResultResponse(dataset_id=dataset.id, **profile))


@router.get("/{dataset_id}", response_model=APIResponse[ProfilerResultResponse], summary="Get Dataset Profile")
async def get_profiler_result(dataset_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Returns the stored profile, computing it first if it does not exist yet."""
    dataset = await _owned(db, dataset_id, user)
    profile = await svc.get_or_compute_profile(db, dataset)
    return APIResponse(success=True, message="Profile retrieved.", data=ProfilerResultResponse(dataset_id=dataset.id, **profile))
