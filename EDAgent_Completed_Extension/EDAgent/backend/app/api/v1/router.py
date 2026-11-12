"""API v1 Router Aggregator
"""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    health,
    auth,
    datasets,
    profiling,
    analysis,
    chat,
    sessions,
    reports,
    exports,
    jobs,
    frequency,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["Datasets"])
api_router.include_router(profiling.router, prefix="/profiling", tags=["Profiling"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])
api_router.include_router(chat.router, prefix="/chat", tags=["Conversational Analysis"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(exports.router, prefix="/exports", tags=["Exports"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Background Jobs"])
api_router.include_router(frequency.router, prefix="/frequency", tags=["Crash Frequency & Concentration"])
