"""
Background jobs: a bounded in-process thread pool with job state stored in the database.

Why not Celery? A single-node deployment does not need a broker, and an unused Celery setup
would only be a promise the code does not keep. This runner gives the same API surface
(submit -> poll status -> result reference) so a distributed queue can replace it later without
touching the endpoints.

Limits and behaviour
* at most MAX_CONCURRENT_JOBS_PER_USER pending/running jobs per user (HTTP 429 beyond that),
* a global worker pool of JOB_WORKERS threads,
* a soft timeout: after JOB_TIMEOUT_SECONDS the job is marked FAILURE and its late result is
  discarded (Python cannot kill a running thread),
* a job still PENDING can be cancelled (REVOKED); running jobs cannot be interrupted.
"""

import logging
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.sync_db import sync_session
from app.models.job import BackgroundJob

logger = logging.getLogger("edagent.jobs")

JOB_WORKERS = 2
_pool = ThreadPoolExecutor(max_workers=JOB_WORKERS, thread_name_prefix="edagent-job")
ACTIVE = ("PENDING", "PROCESSING")


class JobLimitError(Exception):
    pass


class JobContext:
    """Handed to the job function so it can report progress."""

    def __init__(self, job_id: uuid.UUID):
        self.job_id = job_id

    def progress(self, pct: float, message: str) -> None:
        with sync_session() as s:
            job = s.get(BackgroundJob, self.job_id)
            if job and job.status == "PROCESSING":
                job.progress_percentage = float(min(max(pct, 0), 99))
                job.status_message = message[:250]


def _finish(job_id: uuid.UUID, *, ok: bool, message: str, result_ref: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> None:
    with sync_session() as s:
        job = s.get(BackgroundJob, job_id)
        if job is None or job.status in ("FAILURE", "REVOKED"):
            return  # timed out or cancelled meanwhile: keep that outcome
        job.status = "SUCCESS" if ok else "FAILURE"
        job.progress_percentage = 100.0 if ok else job.progress_percentage
        job.status_message = message[:250]
        job.result_ref = result_ref
        job.error_details = error
        job.completed_at = datetime.now(timezone.utc)


def _timeout(job_id: uuid.UUID) -> None:
    with sync_session() as s:
        job = s.get(BackgroundJob, job_id)
        if job and job.status in ACTIVE:
            job.status = "FAILURE"
            job.status_message = "Timed out"
            job.error_details = f"The job exceeded the {settings.JOB_TIMEOUT_SECONDS}s limit."
            job.completed_at = datetime.now(timezone.utc)


def active_jobs(s: Session, user_id: uuid.UUID) -> int:
    return s.execute(select(func.count(BackgroundJob.id)).where(BackgroundJob.user_id == user_id, BackgroundJob.status.in_(ACTIVE))).scalar_one()


def create_job(
    *, user_id: uuid.UUID, job_type: str, dataset_id: Optional[uuid.UUID] = None, session_id: Optional[uuid.UUID] = None, message: str = "Queued"
) -> uuid.UUID:
    """Creates the PENDING row, enforcing the per-user concurrency cap."""
    with sync_session() as s:
        if active_jobs(s, user_id) >= settings.MAX_CONCURRENT_JOBS_PER_USER:
            raise JobLimitError(f"You already have {settings.MAX_CONCURRENT_JOBS_PER_USER} jobs running. Wait for one to finish.")
        job = BackgroundJob(user_id=user_id, dataset_id=dataset_id, session_id=session_id, job_type=job_type, status="PENDING", status_message=message)
        s.add(job)
        s.flush()
        return job.id


def submit(job_id: uuid.UUID, fn: Callable[[JobContext], Dict[str, Any]]) -> None:
    """Runs `fn(ctx)` on the pool. `fn` returns the result reference (e.g. {"report_id": ...})."""

    def work() -> None:
        with sync_session() as s:
            job = s.get(BackgroundJob, job_id)
            if job is None or job.status != "PENDING":
                return  # cancelled before it started
            job.status = "PROCESSING"
            job.status_message = "Running"
        timer = threading.Timer(settings.JOB_TIMEOUT_SECONDS, _timeout, args=(job_id,))
        timer.daemon = True
        timer.start()
        try:
            ref = fn(JobContext(job_id))
            _finish(job_id, ok=True, message="Completed", result_ref=ref)
        except Exception as e:  # noqa: BLE001 - any failure becomes a FAILURE row
            logger.error("job %s failed: %s", job_id, traceback.format_exc())
            _finish(job_id, ok=False, message="Failed", error=f"{type(e).__name__}: {e}"[:1000])
            hook = getattr(fn, "on_error", None)
            if hook:
                try:
                    hook(f"{type(e).__name__}: {e}")
                except Exception:  # noqa: BLE001
                    logger.exception("on_error hook failed")
        finally:
            timer.cancel()

    _pool.submit(work)


def cancel(job_id: uuid.UUID, user_id: uuid.UUID) -> Optional[bool]:
    """True = cancelled, False = already running/finished, None = no such job."""
    with sync_session() as s:
        job = s.get(BackgroundJob, job_id)
        if job is None or job.user_id != user_id:
            return None
        if job.status == "PENDING":
            job.status = "REVOKED"
            job.status_message = "Cancelled"
            job.completed_at = datetime.now(timezone.utc)
            return True
        return False
