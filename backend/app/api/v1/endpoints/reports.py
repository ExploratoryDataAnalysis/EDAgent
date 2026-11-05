"""
Report Generation & Export Endpoints
"""

import uuid
from fastapi import APIRouter
from app.schemas.report import ReportGenerateRequest, ReportResponse
from app.schemas.common import APIResponse

router = APIRouter()


@router.post("/generate", response_model=APIResponse[ReportResponse], summary="Generate EDA Report")
async def generate_eda_report(payload: ReportGenerateRequest):
    """
    Builds a structured PDF/HTML report combining baseline profiler outputs
    and user-requested analyses with reproducibility metadata.
    """
    return APIResponse(
        success=True,
        message="Report generation task created.",
        data=None
    )
