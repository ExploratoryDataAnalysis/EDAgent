"""
Report endpoints. Generation runs as a background job (the response returns immediately with a
job id); the client polls /jobs/{id} or /reports/{id} and downloads when SUCCESS.
"""

import asyncio
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import charge_guest, get_current_user
from app.core.security import safe_filename
from app.models.dataset import Dataset
from app.models.report import GeneratedReport
from app.models.user import User
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.common import APIResponse
from app.schemas.report import ReportGenerateRequest, ReportResponse
from app.services import guest_sessions, report_service
from app.services.data.loader import dataset_fingerprint
from app.services.export_storage import export_path, remove_export_file
from app.services.jobs import runner

router = APIRouter()


def _to_response(r: GeneratedReport, job_id: Optional[str] = None) -> ReportResponse:
    return ReportResponse(
        report_id=r.id, session_id=r.session_id, title=r.title, format=r.format, status=r.status,
        download_url=f"/api/v1/reports/{r.id}/download" if r.status == "SUCCESS" else None,
        dataset_fingerprint=r.dataset_fingerprint, created_at=r.created_at, job_id=job_id, error_message=r.error_message,
        config=ReportGenerateRequest.model_validate(r.config) if r.config else None,
    )


async def _owned(db: AsyncSession, report_id: uuid.UUID, user: User) -> GeneratedReport:
    r = (await db.execute(select(GeneratedReport).where(GeneratedReport.id == report_id, GeneratedReport.user_id == user.id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found.")
    return r


@router.post("/generate", response_model=APIResponse[ReportResponse], status_code=202, summary="Generate EDA Report")
async def generate_report(payload: ReportGenerateRequest, user: User = Depends(charge_guest), db: AsyncSession = Depends(get_db)):
    session = await SessionRepository(db).get(payload.session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    dataset: Optional[Dataset] = await DatasetRepository(db).get_by_id(session.dataset_id, user.id)
    if not dataset or not dataset.metadata_entry or not dataset.metadata_entry.parse_options:
        raise HTTPException(status_code=409, detail="The dataset is not ready (choose a worksheet first).")
    if not payload.included_sections:
        raise HTTPException(status_code=422, detail="Select at least one report section.")
    # Create the job first, in a worker thread: it uses its own (blocking) DB connection and must not
    # run while this request holds an open write transaction, or SQLite would deadlock on the lock.
    try:
        job_id = await asyncio.to_thread(
            runner.create_job, user_id=user.id, job_type="report_generation", dataset_id=dataset.id, session_id=session.id,
            message="Report queued", guest=user.is_guest,
        )
    except runner.JobLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    report = GeneratedReport(
        id=uuid.uuid4(), session_id=session.id, user_id=user.id, title=payload.title.strip() or "EDA Report", format=payload.format.value,
        status="PENDING", included_sections=[s.value for s in payload.included_sections], config=payload.model_dump(mode="json"),
        dataset_fingerprint=dataset_fingerprint(dataset.checksum_sha256, dataset.metadata_entry.parse_options),
    )
    db.add(report)
    try:
        if user.is_guest:
            await guest_sessions.lock_active(db, user.id)
        await db.commit()  # the worker thread must be able to see the row
    except Exception:
        await asyncio.to_thread(runner.cancel, job_id, user.id)
        raise
    runner.submit(job_id, report_service.generate_report_job(report.id, guest=user.is_guest), guest=user.is_guest)
    return APIResponse(success=True, message="Report generation started.", data=_to_response(report, str(job_id)))


@router.get("", response_model=APIResponse[List[ReportResponse]], summary="List Reports")
async def list_reports(session_id: Optional[uuid.UUID] = Query(None), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    q = select(GeneratedReport).where(GeneratedReport.user_id == user.id).order_by(GeneratedReport.created_at.desc())
    if session_id:
        q = q.where(GeneratedReport.session_id == session_id)
    rows = (await db.execute(q)).scalars().all()
    return APIResponse(success=True, message=f"{len(rows)} report(s).", data=[_to_response(r) for r in rows])


@router.get("/{report_id}", response_model=APIResponse[ReportResponse], summary="Report Status")
async def get_report(report_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return APIResponse(success=True, message="Report status.", data=_to_response(await _owned(db, report_id, user)))


@router.get("/{report_id}/download", summary="Download Report File")
async def download_report(report_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    r = await _owned(db, report_id, user)
    if r.status != "SUCCESS" or not r.storage_uri:
        raise HTTPException(status_code=409, detail=f"The report is not ready (status: {r.status}).")
    try:
        path = export_path(r.storage_uri)
    except ValueError:
        raise HTTPException(status_code=404, detail="Report file not found.")
    import os

    if not os.path.isfile(path):
        raise HTTPException(status_code=410, detail="The report file has expired. Generate it again.")
    media = "application/pdf" if r.format == "pdf" else "text/html; charset=utf-8"
    filename = f"{safe_filename(r.title, 'report')}.{r.format}"
    if user.is_guest:
        # Read before the delivery guard, so an unlink during clear cannot race
        # a FileResponse opening the file after it has sent success headers.
        try:
            data = await asyncio.to_thread(Path(path).read_bytes)
        except FileNotFoundError:
            raise HTTPException(410, detail="The report file has expired.")
        return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    return FileResponse(path, media_type=media, filename=filename)


@router.delete("/{report_id}", response_model=APIResponse[bool], summary="Delete Report")
async def delete_report(report_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.is_guest:
        await guest_sessions.lock_active(db, user.id)
    r = await _owned(db, report_id, user)
    uri = r.storage_uri
    await db.delete(r)
    await db.commit()
    remove_export_file(uri)
    return APIResponse(success=True, message="Report deleted.", data=True)
