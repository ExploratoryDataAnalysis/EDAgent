"""
Dataset endpoints: upload, URL import, sample datasets, sheet selection, preview, listing, deletion.

All routes require a signed-in user and are scoped to that user's datasets. A dataset that
belongs to someone else is reported as "not found" so its existence is never revealed.
"""

import asyncio
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import account_only, charge_guest, get_current_user
from app.models.dataset import Dataset
from app.models.user import User
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.common import APIResponse
from app.schemas.dataset import (
    ConfirmIngestionRequest,
    DatasetListItem,
    DatasetListResponse,
    DatasetPreview,
    DatasetRecoveryCandidate,
    DatasetResponse,
    DatasetUploadResponse,
    DatasetURLImportRequest,
    FileFormatEnum,
    SelectSheetRequest,
    SheetInspectionResponse,
)
from app.services import dataset_service as svc
from app.services import guest_sessions
from app.services.export_storage import remove_export_file
from app.services.ingestion.parser import IngestionService
from app.services.ingestion.validator import IngestionValidationError, IngestionValidator

router = APIRouter()


async def _owned(db: AsyncSession, dataset_id: uuid.UUID, user: User) -> Dataset:
    dataset = await DatasetRepository(db).get_by_id(dataset_id, user.id)
    if not dataset:
        raise IngestionValidationError(f"Dataset '{dataset_id}' not found.", error_code="FILE_NOT_FOUND")
    return dataset


async def _ingest_saved(
    db: AsyncSession,
    user: User,
    *,
    dataset_id: uuid.UUID,
    rel_path: str,
    original_filename: str,
    display_name: str,
    fmt: FileFormatEnum,
    size: int,
    checksum: str,
    sheet_name: Optional[str],
    message: str,
    remove_on_failure: bool = True,
) -> APIResponse[DatasetUploadResponse]:
    """Shared tail of upload / URL import / sample: ingest, and clean the folder up on failure."""
    try:
        dataset, parsed, sheets, needs_sheet, decision = await svc.create_dataset_from_file(
            db, user_id=user.id, dataset_id=dataset_id, rel_path=rel_path, original_filename=original_filename,
            display_name=display_name, fmt=fmt, size=size, checksum=checksum, sheet_name=sheet_name, guest=user.is_guest,
        )
        if user.is_guest:
            # Upload held the lease while writing to disk. Recheck expiry before
            # publishing it and clean the new folder if storage or commit failed.
            await guest_sessions.lock_active(db, user.id)
            await db.commit()
    except Exception:
        if remove_on_failure:
            svc.remove_dataset_files(rel_path)
        raise
    return APIResponse(
        success=True,
        message="Multiple sheets detected. Please select a sheet to proceed." if needs_sheet else message,
        data=DatasetUploadResponse(
            dataset_id=dataset.id,
            name=display_name,
            original_filename=original_filename,
            file_format=fmt,
            file_size_bytes=size,
            multiple_sheets_found=bool(sheets and len(sheets) > 1),
            detected_sheets=sheets,
            selected_sheet=parsed.selected_sheet if parsed else None,
            requires_sheet_selection=needs_sheet,
            parsing_decision=decision,
            storage_uri=rel_path,
            created_at=dataset.created_at,
        ),
    )


async def _check_quota(db: AsyncSession, user: User) -> None:
    limit = settings.GUEST_MAX_DATASETS if user.is_guest else settings.MAX_DATASETS_PER_USER
    if await DatasetRepository(db).count_for_user(user.id) >= limit:
        raise IngestionValidationError(
            f"You have reached the limit of {limit} datasets. Delete one to upload another.",
            error_code="QUOTA_EXCEEDED",
        )


def _find_recovery_file(
    user_id: uuid.UUID, dataset_id: uuid.UUID
) -> tuple[str, str, FileFormatEnum, int, datetime] | None:
    """Finds one supported, unregistered upload in this user's storage folder."""
    try:
        storage_root = Path(svc.absolute_path("")).resolve()
        owner_root = Path(svc.absolute_path(str(user_id)))
    except IngestionValidationError:
        return None
    if owner_root.is_symlink() or not owner_root.is_dir():
        return None
    try:
        owner_root.resolve().relative_to(storage_root)
    except ValueError:
        return None

    dataset_dir = owner_root / str(dataset_id)
    if dataset_dir.is_symlink() or not dataset_dir.is_dir():
        return None

    candidates = []
    for path in dataset_dir.iterdir():
        if path.is_symlink() or not path.is_file():
            continue
        try:
            fmt = IngestionValidator.validate_extension(path.name)
            absolute = Path(svc.absolute_path(svc.storage_subpath(user_id, dataset_id, path.name)))
        except IngestionValidationError:
            continue
        if absolute.resolve() != path.resolve():
            continue
        candidates.append((path, fmt))

    if len(candidates) != 1:
        return None
    path, fmt = candidates[0]
    stat = path.stat()
    rel_path = svc.storage_subpath(user_id, dataset_id, path.name)
    return rel_path, path.name, fmt, stat.st_size, datetime.fromtimestamp(stat.st_mtime, UTC)


@router.post("/upload", response_model=APIResponse[DatasetUploadResponse], summary="Upload Tabular Dataset")
async def upload_dataset(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form(None),
    user: User = Depends(charge_guest),
    db: AsyncSession = Depends(get_db),
):
    """Accepts CSV, TSV or XLSX. Validates, stores in per-user storage, parses and profiles it."""
    if not file.filename:
        raise IngestionValidationError("Uploaded file has no filename.", error_code="MISSING_FILENAME")
    fmt = IngestionValidator.validate_extension(file.filename)
    if user.is_guest:
        if fmt not in (FileFormatEnum.CSV, FileFormatEnum.TSV):
            raise IngestionValidationError("Private guests can upload CSV and TSV files.", error_code="INVALID_FORMAT")
        # Holding the lease here serializes the storage quota and keeps clear
        # from deleting an owner folder before this upload is done writing.
        await guest_sessions.lock_active(db, user.id)
    await _check_quota(db, user)
    name = svc.clean_name(file.filename)
    dataset_id = uuid.uuid4()
    rel = svc.storage_subpath(user.id, dataset_id, name)
    try:
        size, checksum = await svc.save_upload(
            file, svc.absolute_path(rel), max_bytes=settings.GUEST_MAX_UPLOAD_BYTES if user.is_guest else None,
        )
    except Exception:
        svc.remove_dataset_files(rel)
        raise
    return await _ingest_saved(
        db, user, dataset_id=dataset_id, rel_path=rel, original_filename=file.filename, display_name=name,
        fmt=fmt, size=size, checksum=checksum, sheet_name=sheet_name, message="Dataset uploaded successfully.",
    )


@router.post("/import-url", response_model=APIResponse[DatasetUploadResponse], summary="Import Dataset From URL")
async def import_from_url(payload: DatasetURLImportRequest, user: User = Depends(account_only), db: AsyncSession = Depends(get_db)):
    """Downloads a public CSV/TSV/XLSX. Internal addresses are refused (SSRF protection)."""
    await _check_quota(db, user)
    dataset_id = uuid.uuid4()
    # The extension is only known after redirects, so download to a temporary name first.
    tmp_rel = svc.storage_subpath(user.id, dataset_id, "download.tmp")
    try:
        size, checksum, remote_name = await svc.download_url(payload.url, svc.absolute_path(tmp_rel))
        fmt = IngestionValidator.validate_extension(remote_name if "." in remote_name else remote_name + ".csv")
        name = svc.clean_name(payload.dataset_name or remote_name)
        if not name.lower().endswith("." + fmt.value):
            name = f"{name}.{fmt.value}"
        rel = svc.storage_subpath(user.id, dataset_id, name)
        os.replace(svc.absolute_path(tmp_rel), svc.absolute_path(rel))
    except Exception:
        svc.remove_dataset_files(tmp_rel)
        raise
    return await _ingest_saved(
        db, user, dataset_id=dataset_id, rel_path=rel, original_filename=remote_name, display_name=name,
        fmt=fmt, size=size, checksum=checksum, sheet_name=None, message="Dataset imported from URL.",
    )


@router.get("/samples", summary="List Sample Datasets")
async def list_sample_datasets(user: User = Depends(account_only)):
    return APIResponse(success=True, message="Sample datasets.", data=svc.list_samples())


@router.post("/samples/{sample_id}", response_model=APIResponse[DatasetUploadResponse], summary="Load Sample Dataset")
async def load_sample_dataset(sample_id: str, user: User = Depends(account_only), db: AsyncSession = Depends(get_db)):
    """Copies a bundled sample into the user's own storage so it behaves like any other dataset."""
    await _check_quota(db, user)
    src = svc.sample_path(sample_id)
    fmt = IngestionValidator.validate_extension(sample_id)
    dataset_id = uuid.uuid4()
    rel = svc.storage_subpath(user.id, dataset_id, svc.clean_name(sample_id))
    dest = svc.absolute_path(rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    import hashlib
    import shutil

    shutil.copyfile(src, dest)
    with open(dest, "rb") as fh:
        checksum = hashlib.sha256(fh.read()).hexdigest()
    return await _ingest_saved(
        db, user, dataset_id=dataset_id, rel_path=rel, original_filename=sample_id, display_name=svc.clean_name(sample_id),
        fmt=fmt, size=os.path.getsize(dest), checksum=checksum, sheet_name=None, message="Sample dataset loaded.",
    )


@router.get("/recoverable", response_model=APIResponse[list[DatasetRecoveryCandidate]], summary="List Stored Uploads Not Registered")
async def list_recoverable_uploads(user: User = Depends(account_only), db: AsyncSession = Depends(get_db)):
    """Lists supported files in the signed-in user's storage that are missing from the database."""
    owner_root = Path(svc.absolute_path(str(user.id)))
    if owner_root.is_symlink() or not owner_root.is_dir():
        candidates = []
    else:
        candidates = []
        for folder in owner_root.iterdir():
            if folder.is_symlink() or not folder.is_dir():
                continue
            try:
                dataset_id = uuid.UUID(folder.name)
            except ValueError:
                continue
            if folder.name != str(dataset_id) or await db.get(Dataset, dataset_id):
                continue
            stored = _find_recovery_file(user.id, dataset_id)
            if stored is None:
                continue
            _, filename, fmt, size, modified_at = stored
            candidates.append(
                DatasetRecoveryCandidate(
                    dataset_id=dataset_id,
                    name=filename,
                    file_format=fmt,
                    file_size_bytes=size,
                    modified_at=modified_at,
                )
            )
    return APIResponse(success=True, message="Recoverable stored uploads.", data=candidates)


@router.post("/{dataset_id}/recover", response_model=APIResponse[DatasetUploadResponse], summary="Restore Stored Upload")
async def recover_stored_upload(dataset_id: uuid.UUID, user: User = Depends(account_only), db: AsyncSession = Depends(get_db)):
    """Registers and profiles an orphaned file from this user's storage without moving or deleting it."""
    if await db.get(Dataset, dataset_id):
        raise IngestionValidationError("Stored upload not found.", error_code="FILE_NOT_FOUND")
    stored = _find_recovery_file(user.id, dataset_id)
    if stored is None:
        raise IngestionValidationError("Stored upload not found.", error_code="FILE_NOT_FOUND")
    await _check_quota(db, user)
    rel_path, filename, fmt, size, _ = stored
    IngestionValidator.validate_file_size(size)
    checksum = await asyncio.to_thread(IngestionService.compute_sha256, svc.absolute_path(rel_path))
    return await _ingest_saved(
        db,
        user,
        dataset_id=dataset_id,
        rel_path=rel_path,
        original_filename=filename,
        display_name=svc.clean_name(filename),
        fmt=fmt,
        size=size,
        checksum=checksum,
        sheet_name=None,
        message="Stored dataset restored successfully.",
        remove_on_failure=False,
    )


@router.get("/{dataset_id}/sheets", response_model=APIResponse[SheetInspectionResponse], summary="Inspect Excel Sheets")
async def inspect_sheets(dataset_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    dataset = await _owned(db, dataset_id, user)
    if dataset.file_format != "xlsx":
        raise IngestionValidationError(
            f"Sheet inspection only applies to Excel XLSX files, not '{dataset.file_format}'.", error_code="INVALID_OPERATION"
        )
    sheets = IngestionService.inspect_excel_sheets(svc.absolute_path(dataset.storage_uri))
    return APIResponse(
        success=True,
        message=f"Found {len(sheets)} sheets in workbook.",
        data=SheetInspectionResponse(dataset_id=dataset_id, sheets=sheets, default_sheet=sheets[0].name if sheets else None),
    )


def _preview_from_parsed(dataset_id: uuid.UUID, parsed) -> DatasetPreview:
    return DatasetPreview(
        dataset_id=dataset_id,
        selected_sheet=parsed.selected_sheet,
        total_rows=parsed.row_count,
        total_columns=parsed.column_count,
        column_names=parsed.headers,
        inferred_types=parsed.inferred_types,
        head_records=parsed.head_records,
        tail_records=parsed.tail_records,
        sample_records=parsed.sample_records,
        parsing_warnings=parsed.parsing_warnings,
    )


@router.post("/{dataset_id}/select-sheet", response_model=APIResponse[DatasetPreview], summary="Select Excel Sheet")
async def select_excel_sheet(dataset_id: uuid.UUID, payload: SelectSheetRequest, user: User = Depends(account_only), db: AsyncSession = Depends(get_db)):
    dataset = await _owned(db, dataset_id, user)
    if dataset.file_format != "xlsx":
        raise IngestionValidationError("Sheet selection only applies to Excel XLSX files.", error_code="INVALID_OPERATION")
    parsed = await svc.reparse_dataset(db, dataset, sheet_name=payload.sheet_name)
    return APIResponse(success=True, message=f"Successfully ingested worksheet '{payload.sheet_name}'.", data=_preview_from_parsed(dataset.id, parsed))


@router.post("/{dataset_id}/confirm", response_model=APIResponse[DatasetPreview], summary="Confirm Ingestion Options")
async def confirm_ingestion(dataset_id: uuid.UUID, payload: ConfirmIngestionRequest, user: User = Depends(charge_guest), db: AsyncSession = Depends(get_db)):
    """Re-parses the original file with a user-confirmed delimiter / encoding / sheet."""
    dataset = await _owned(db, dataset_id, user)
    parsed = await svc.reparse_dataset(db, dataset, sheet_name=payload.sheet_name, delimiter=payload.delimiter, encoding=payload.encoding, guest=user.is_guest)
    return APIResponse(success=True, message="Dataset ingestion parameters confirmed and applied.", data=_preview_from_parsed(dataset.id, parsed))


@router.get("/{dataset_id}/preview", response_model=APIResponse[DatasetPreview], summary="Get Dataset Preview")
async def get_dataset_preview(
    dataset_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dataset = await _owned(db, dataset_id, user)
    preview = dataset.metadata_entry.sample_preview if dataset.metadata_entry else None
    if not preview:
        raise IngestionValidationError(
            "This workbook has several sheets; choose one first (POST /datasets/{id}/select-sheet).", error_code="SHEET_REQUIRED"
        )
    return APIResponse(
        success=True,
        message="Preview retrieved.",
        data=DatasetPreview(
            dataset_id=dataset.id,
            selected_sheet=preview.get("selected_sheet"),
            total_rows=dataset.row_count or 0,
            total_columns=dataset.column_count or 0,
            column_names=preview.get("column_names", []),
            inferred_types=preview.get("inferred_types", {}),
            head_records=preview.get("head_records", [])[:limit],
            tail_records=preview.get("tail_records", [])[:limit],
            sample_records=preview.get("sample_records", [])[:limit],
            parsing_warnings=preview.get("parsing_warnings", []),
        ),
    )


@router.get("/{dataset_id}", response_model=APIResponse[DatasetResponse], summary="Get Dataset Metadata")
async def get_dataset(dataset_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    dataset = await _owned(db, dataset_id, user)
    meta = dataset.metadata_entry
    summary = (
        {
            "inferred_schema": meta.inferred_schema,
            "quality_warnings": meta.quality_warnings,
            "parsed_sheets": meta.parsed_sheets,
            "parse_options": meta.parse_options,
            "selected_sheet": (meta.sample_preview or {}).get("selected_sheet"),
            "requires_sheet_selection": meta.sample_preview is None,
        }
        if meta
        else {}
    )
    return APIResponse(
        success=True,
        message="Dataset retrieved successfully.",
        data=DatasetResponse(
            id=dataset.id, user_id=dataset.user_id, name=dataset.name, original_filename=dataset.original_filename,
            file_format=dataset.file_format, file_size_bytes=dataset.file_size_bytes, row_count=dataset.row_count,
            column_count=dataset.column_count, checksum_sha256=dataset.checksum_sha256, is_deleted=dataset.is_deleted,
            created_at=dataset.created_at, updated_at=dataset.updated_at, metadata_summary=summary,
        ),
    )


@router.get("", response_model=APIResponse[DatasetListResponse], summary="List Datasets")
async def list_datasets(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await DatasetRepository(db).list_datasets(user_id=user.id, skip=skip, limit=limit)
    rows = [
        DatasetListItem(
            id=d.id, name=d.name, original_filename=d.original_filename, file_format=d.file_format,
            file_size_bytes=d.file_size_bytes, row_count=d.row_count, column_count=d.column_count, created_at=d.created_at,
        )
        for d in items
    ]
    return APIResponse(
        success=True, message=f"Retrieved {len(rows)} datasets.",
        data=DatasetListResponse(items=rows, total=total, page=(skip // limit) + 1, page_size=limit),
    )


@router.delete("/{dataset_id}", response_model=APIResponse[bool], summary="Delete Dataset")
async def delete_dataset(dataset_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Permanently deletes the dataset, its sessions/results/reports, the stored file and cached data."""
    if user.is_guest:
        await guest_sessions.lock_active(db, user.id)
    dataset = await _owned(db, dataset_id, user)
    rel = dataset.storage_uri
    report_files = await DatasetRepository(db).purge(dataset)
    await db.commit()  # the rows are gone; only now touch the disk
    for uri in report_files:
        remove_export_file(uri)
    svc.remove_dataset_files(rel)
    svc.invalidate_caches(dataset_id)
    return APIResponse(success=True, message="Dataset deleted along with its sessions, results, reports and files.", data=True)
