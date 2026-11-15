"""Guest lease checks and repeatable cleanup for the existing private workspace."""

import asyncio
import logging
import shutil
import time
import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import delete, select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.dataset import Dataset
from app.models.job import BackgroundJob
from app.models.report import GeneratedReport
from app.models.user import GuestLease, User
from app.services.dataset_service import absolute_path
from app.services.export_storage import export_path

logger = logging.getLogger("edagent.guest")
EXPIRED = "Your private guest session ended. Start a new session to continue."


def timestamp() -> int:
    return int(time.time())


def active_statement(user_id):
    return select(GuestLease).where(GuestLease.user_id == user_id, GuestLease.expires_at > timestamp())


async def active(db, user_id):
    return (await db.execute(active_statement(user_id))).scalar_one_or_none()


def lock_statement(user_id, *, charge=False):
    # UPDATE also serializes on SQLite, where SELECT FOR UPDATE has no effect.
    guard = update(GuestLease).where(GuestLease.user_id == user_id, GuestLease.expires_at > timestamp())
    if charge:
        guard = guard.where(GuestLease.actions < settings.GUEST_MAX_ACTIONS)
    return guard.values(actions=GuestLease.actions + int(charge)).returning(GuestLease.expires_at)


async def lock_active(db, user_id, *, charge=False):
    deadline = (await db.execute(lock_statement(user_id, charge=charge))).scalar_one_or_none()
    if deadline is not None and deadline > timestamp():
        return
    if charge and await active(db, user_id):
        raise HTTPException(429, detail="This guest session has reached its processing limit.")
    raise HTTPException(401, detail=EXPIRED, headers={"WWW-Authenticate": "Bearer"})


def lock_worker(db, user_id):
    """Serialize final worker writes with clear, then recheck wall time after the lock."""
    deadline = db.execute(lock_statement(user_id)).scalar_one_or_none()
    return deadline is not None and deadline > timestamp()


async def clear(user_id):
    async with AsyncSessionLocal() as db:
        # Commit revocation before touching the filesystem so a crash leaves an
        # expired lease that startup can find and retry.
        await db.execute(update(GuestLease).where(GuestLease.user_id == user_id).values(expires_at=0))
        await db.commit()
    await reclaim(user_id)


def _remove_owner_files(user_id):
    for folder in (Path(absolute_path(str(user_id))), Path(export_path(f"reports/{user_id}"))):
        try:
            shutil.rmtree(folder)
        except FileNotFoundError:
            pass


async def reclaim(user_id):
    async with AsyncSessionLocal() as db:
        expired = (await db.execute(
            update(GuestLease).where(GuestLease.user_id == user_id, GuestLease.expires_at <= timestamp())
            .values(expires_at=0).returning(GuestLease.user_id)
        )).scalar_one_or_none()
        if expired is None:
            return
        try:
            await asyncio.to_thread(_remove_owner_files, user_id)
        except OSError:
            # Retain the revoked lease and retry. File paths and contents stay out of the log.
            logger.warning("Guest artifact cleanup deferred")
            return
        # Database cascades cover datasets, previews, sessions, results, reports and jobs.
        await db.execute(delete(User).where(User.id == user_id))
        await db.commit()


async def sweep():
    async with AsyncSessionLocal() as db:
        ids = (await db.scalars(select(GuestLease.user_id).where(GuestLease.expires_at <= timestamp()))).all()
    for user_id in ids:
        await reclaim(user_id)


def _remove_unregistered(user_id, dataset_ids, report_files):
    uploads = Path(absolute_path(str(user_id)))
    if uploads.is_dir():
        for path in uploads.iterdir():
            try:
                dataset_id = str(uuid.UUID(path.name))
            except ValueError:
                continue
            if path.is_dir() and not path.is_symlink() and path.name == dataset_id and dataset_id not in dataset_ids:
                shutil.rmtree(path)
    reports = Path(export_path(f"reports/{user_id}"))
    if reports.is_dir():
        for path in reports.iterdir():
            if path.is_file() and path.name not in report_files:
                path.unlink()


async def recover_after_restart():
    """The single app process owns its worker pool. Failed jobs are safe to rerun."""
    await sweep()
    async with AsyncSessionLocal() as db:
        ids = (await db.scalars(select(GuestLease.user_id))).all()
    for user_id in ids:
        async with AsyncSessionLocal() as db:
            deadline = (await db.execute(lock_statement(user_id))).scalar_one_or_none()
            if deadline is None:
                continue
            datasets = await db.scalars(select(Dataset.id).where(Dataset.user_id == user_id))
            files = await db.scalars(select(GeneratedReport.storage_uri).where(GeneratedReport.user_id == user_id))
            try:
                await asyncio.to_thread(
                    _remove_unregistered, user_id, {str(d) for d in datasets}, {Path(f).name for f in files if f},
                )
            except (OSError, ValueError):
                logger.warning("Guest partial file cleanup deferred")
            await db.execute(update(BackgroundJob).where(
                BackgroundJob.user_id == user_id, BackgroundJob.status.in_(("PENDING", "PROCESSING")),
            ).values(status="FAILURE", status_message="Server restarted. Run the job again."))
            await db.execute(update(GeneratedReport).where(
                GeneratedReport.user_id == user_id, GeneratedReport.status.in_(("PENDING", "PROCESSING")),
            ).values(status="FAILURE", error_message="Server restarted. Generate the report again."))
            await db.commit()


async def sweep_periodically():
    while True:
        await asyncio.sleep(30)
        try:
            await sweep()
        except Exception:
            logger.error("Guest expiry sweep failed")
