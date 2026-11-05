"""
Background Job Orchestration with Celery
Supports asynchronous profiling, long-running statistical analysis, and report generation.
"""

from app.core.config import settings

try:
    from celery import Celery

    celery_app = Celery(
        "edagent_tasks",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
        task_time_limit=settings.JOB_TIMEOUT_SECONDS,
    )

except Exception:
    # Lightweight mock for local development when celery/redis is not yet configured
    class MockCelery:
        conf = {}

        def task(self, *args, **kwargs):
            def decorator(f):
                return f
            return decorator

    celery_app = MockCelery()  # type: ignore
