"""
Jobs Service Package
"""

from app.services.jobs.celery_app import celery_app

__all__ = ["celery_app"]
