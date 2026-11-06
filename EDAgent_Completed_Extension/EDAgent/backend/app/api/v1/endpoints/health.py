"""
Health & Diagnostic Endpoints
"""

from datetime import datetime, timezone
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/health", summary="System Health Check")
async def health_check():
    """Returns application status, version, and active configuration."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "storage_backend": settings.STORAGE_BACKEND,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
