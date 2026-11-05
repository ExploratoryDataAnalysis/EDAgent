"""
Background Job Schemas
Supports long-running task status, progress polling, cancellation, and quotas.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from app.schemas.common import BaseSchema


class JobTypeEnum(str, Enum):
    PROFILING = "profiling"
    ANALYSIS = "analysis"
    REPORT_GENERATION = "report_generation"
    CONVERSION = "conversion"


class JobStatusEnum(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    REVOKED = "REVOKED"


class JobStatusResponse(BaseSchema):
    job_id: str
    dataset_id: Optional[uuid.UUID] = None
    session_id: Optional[uuid.UUID] = None
    job_type: JobTypeEnum
    status: JobStatusEnum
    progress_percentage: float
    status_message: str
    error_details: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class JobCancelResponse(BaseSchema):
    job_id: str
    cancelled: bool
    message: str
