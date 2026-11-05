"""
Automatic Dataset Profiler Endpoints
Implements Phase 2 automatic profiling retrieval and on-demand trigger.
Zero LLM dependencies.
"""

import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.storage import get_storage_provider
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.profiler import ProfilerResultResponse
from app.schemas.common import APIResponse
from app.services.profiler.profiler_engine import ProfilerEngine
from app.services.ingestion.validator import IngestionValidationError

router = APIRouter()


def parse_user_id(x_user_id: Optional[str]) -> Optional[uuid.UUID]:
    """Parses X-User-ID header into UUID if valid."""
    if not x_user_id:
        return None
    try:
        return uuid.UUID(x_user_id)
    except ValueError:
        return None


@router.post("/{dataset_id}", response_model=APIResponse[ProfilerResultResponse], summary="Trigger Automatic Profiling")
async def trigger_profiling(
    dataset_id: uuid.UUID,
    sheet_name: Optional[str] = None,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Computes baseline summary statistics, missingness, duplicate checks,
    column semantic role inference, distributions, relationships, and quality checks
    deterministically without needing AI/LLM calls.
    """
    user_uuid = parse_user_id(x_user_id)
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get_by_id(dataset_id, user_id=user_uuid)

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    storage = get_storage_provider()
    try:
        abs_path = await storage.get_file_path(dataset.storage_uri)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to locate storage file: {str(e)}",
        )

    # Determine selected sheet if Excel
    target_sheet = sheet_name
    if not target_sheet and dataset.metadata_entry and dataset.metadata_entry.sample_preview:
        target_sheet = dataset.metadata_entry.sample_preview.get("selected_sheet")

    # Run profiler engine
    profile_data = ProfilerEngine.profile_dataset(
        file_path=abs_path,
        format_str=dataset.file_format,
        sheet_name=target_sheet,
    )

    # Persist in dataset metadata
    if dataset.metadata_entry:
        dataset.metadata_entry.summary_statistics = profile_data
        dataset.metadata_entry.missingness_report = profile_data.get("missingness", {})
        dataset.metadata_entry.duplicates_report = profile_data.get("duplicates", {})
        dataset.metadata_entry.quality_warnings = profile_data.get("quality_warnings", [])
        await dataset_repo.update(dataset)

    response_data = ProfilerResultResponse(dataset_id=dataset.id, **profile_data)

    return APIResponse(
        success=True,
        message="Profiling generated successfully.",
        data=response_data,
    )


@router.get("/{dataset_id}", response_model=APIResponse[ProfilerResultResponse], summary="Get Dataset Profile")
async def get_profiler_result(
    dataset_id: uuid.UUID,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves cached baseline profiling results for the dataset.
    If not yet computed, automatically runs the profiler deterministically.
    """
    user_uuid = parse_user_id(x_user_id)
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get_by_id(dataset_id, user_id=user_uuid)

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    # Check for cached complete profile
    cached_profile = None
    if (
        dataset.metadata_entry
        and dataset.metadata_entry.summary_statistics
        and isinstance(dataset.metadata_entry.summary_statistics, dict)
        and "overview" in dataset.metadata_entry.summary_statistics
    ):
        cached_profile = dataset.metadata_entry.summary_statistics

    if cached_profile:
        response_data = ProfilerResultResponse(dataset_id=dataset.id, **cached_profile)
        return APIResponse(
            success=True,
            message="Profile retrieved.",
            data=response_data,
        )

    # If not yet cached, compute it now
    storage = get_storage_provider()
    try:
        abs_path = await storage.get_file_path(dataset.storage_uri)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to locate storage file: {str(e)}",
        )

    target_sheet = None
    if dataset.metadata_entry and dataset.metadata_entry.sample_preview:
        target_sheet = dataset.metadata_entry.sample_preview.get("selected_sheet")

    profile_data = ProfilerEngine.profile_dataset(
        file_path=abs_path,
        format_str=dataset.file_format,
        sheet_name=target_sheet,
    )

    if dataset.metadata_entry:
        dataset.metadata_entry.summary_statistics = profile_data
        dataset.metadata_entry.missingness_report = profile_data.get("missingness", {})
        dataset.metadata_entry.duplicates_report = profile_data.get("duplicates", {})
        dataset.metadata_entry.quality_warnings = profile_data.get("quality_warnings", [])
        await dataset_repo.update(dataset)

    response_data = ProfilerResultResponse(dataset_id=dataset.id, **profile_data)

    return APIResponse(
        success=True,
        message="Profile retrieved.",
        data=response_data,
    )
