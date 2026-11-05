"""
Dataset Ingestion, Preview & Management Endpoints
Implements Phase 1 specifications according to Section 5.1 of the EDAgent specification.
"""

import hashlib
import os
import re
import uuid
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, Header, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.storage import get_storage_provider
from app.core.config import settings
from app.models.dataset import Dataset, DatasetMetadata
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.dataset import (
    FileFormatEnum,
    DatasetUploadResponse,
    DatasetURLImportRequest,
    DatasetPreview,
    DatasetResponse,
    DatasetListItem,
    DatasetListResponse,
    SheetInfo,
    SheetInspectionResponse,
    SelectSheetRequest,
    ConfirmIngestionRequest,
)
from app.schemas.common import APIResponse
from app.services.ingestion.validator import IngestionValidator, IngestionValidationError
from app.services.ingestion.parser import IngestionService, ParsedDatasetResult
from app.services.profiler.profiler_engine import ProfilerEngine

router = APIRouter()


def sanitize_filename(filename: str) -> str:
    """Strips path traversal sequences and unsafe characters."""
    base = os.path.basename(filename)
    return re.sub(r"[^\w\.\-]", "_", base)


@router.post("/upload", response_model=APIResponse[DatasetUploadResponse], summary="Upload Tabular Dataset")
async def upload_dataset(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form(None),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Accepts CSV, TSV, or XLSX datasets.
    Validates file format, detects MIME/encoding/delimiter, enforces isolated storage,
    and returns initial upload decision or sheet selection prompt.
    """
    if not file.filename:
        raise IngestionValidationError("Uploaded file has no filename.", error_code="MISSING_FILENAME")

    # 1. Extension & Format validation
    format_enum = IngestionValidator.validate_extension(file.filename)
    clean_filename = sanitize_filename(file.filename)
    dataset_id = uuid.uuid4()

    # Determine user identity / isolation path
    user_uuid: Optional[uuid.UUID] = None
    if x_user_id:
        try:
            user_uuid = uuid.UUID(x_user_id)
        except ValueError:
            pass
    user_path_key = str(user_uuid) if user_uuid else "anonymous"
    destination_subpath = f"{user_path_key}/{dataset_id}/{clean_filename}"

    # 2. Stream to isolated storage while tracking size and computing SHA256
    storage = get_storage_provider()
    sha256_hasher = hashlib.sha256()
    bytes_read = 0
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # We write chunks into storage
    try:
        abs_dest_path = await storage.get_file_path(destination_subpath)
    except FileNotFoundError:
        # get_file_path raises if not exists in LocalStorageProvider; construct full path
        abs_dest_path = os.path.abspath(os.path.join(storage.base_dir, destination_subpath))
        os.makedirs(os.path.dirname(abs_dest_path), exist_ok=True)

    try:
        with open(abs_dest_path, "wb") as f_out:
            while True:
                chunk = await file.read(65536)
                if not chunk:
                    break
                bytes_read += len(chunk)
                if bytes_read > max_bytes:
                    raise IngestionValidationError(
                        f"File size exceeds maximum upload limit of {settings.MAX_UPLOAD_SIZE_MB} MB.",
                        error_code="FILE_TOO_LARGE",
                    )
                sha256_hasher.update(chunk)
                f_out.write(chunk)
    except IngestionValidationError:
        if os.path.exists(abs_dest_path):
            os.remove(abs_dest_path)
        raise
    except Exception as e:
        if os.path.exists(abs_dest_path):
            os.remove(abs_dest_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stream and store file: {str(e)}",
        )

    checksum = sha256_hasher.hexdigest()

    # 3. Content signature validation (deep content check)
    try:
        IngestionValidator.validate_content_signature(abs_dest_path, format_enum)
    except IngestionValidationError:
        if os.path.exists(abs_dest_path):
            os.remove(abs_dest_path)
        raise

    # 4. Check Excel multi-sheet handling
    detected_sheets: Optional[List[str]] = None
    requires_sheet_selection = False
    parsing_decision = ""
    parsed_result: Optional[ParsedDatasetResult] = None

    if format_enum == FileFormatEnum.XLSX:
        sheets = IngestionService.inspect_excel_sheets(abs_dest_path)
        sheet_names = [s.name for s in sheets]
        detected_sheets = sheet_names

        if len(sheet_names) > 1 and not sheet_name:
            requires_sheet_selection = True
            parsing_decision = (
                f"Workbook contains {len(sheet_names)} sheets: {', '.join(sheet_names)}. "
                f"Awaiting sheet selection."
            )
        else:
            target_sheet = sheet_name or sheet_names[0]
            parsed_result = IngestionService.parse_dataset(
                file_path=abs_dest_path,
                format_enum=format_enum,
                sheet_name=target_sheet,
            )
            parsing_decision = parsed_result.parsing_decisions
    else:
        # CSV or TSV
        parsed_result = IngestionService.parse_dataset(
            file_path=abs_dest_path,
            format_enum=format_enum,
        )
        parsing_decision = parsed_result.parsing_decisions

    # 5. Persist Dataset in database
    dataset_repo = DatasetRepository(db)
    dataset_model = Dataset(
        id=dataset_id,
        user_id=user_uuid,
        name=clean_filename,
        original_filename=file.filename,
        file_format=format_enum.value,
        storage_uri=destination_subpath,
        file_size_bytes=bytes_read,
        row_count=parsed_result.row_count if parsed_result else None,
        column_count=parsed_result.column_count if parsed_result else None,
        checksum_sha256=checksum,
        is_deleted=False,
    )

    # Automatic profiling when ingestion is complete
    profile_data = {}
    if not requires_sheet_selection and parsed_result:
        try:
            profile_data = ProfilerEngine.profile_dataset(
                file_path=abs_dest_path,
                format_str=format_enum.value,
                sheet_name=parsed_result.selected_sheet if parsed_result else None,
                delimiter=parsed_result.delimiter if parsed_result else None,
                encoding=parsed_result.encoding if parsed_result else None,
                parsing_warnings=parsed_result.parsing_warnings if parsed_result else [],
            )
        except Exception:
            profile_data = {}

    metadata_model = DatasetMetadata(
        id=uuid.uuid4(),
        dataset_id=dataset_id,
        inferred_schema=parsed_result.inferred_types if parsed_result else {},
        summary_statistics=profile_data,
        missingness_report=profile_data.get("missingness", {}),
        duplicates_report=profile_data.get("duplicates", {}),
        quality_warnings=profile_data.get("quality_warnings", [{"message": w} for w in (parsed_result.parsing_warnings if parsed_result else [])]),
        parsed_sheets=detected_sheets,
        sample_preview={
            "column_names": parsed_result.headers if parsed_result else [],
            "inferred_types": parsed_result.inferred_types if parsed_result else {},
            "head_records": parsed_result.head_records if parsed_result else [],
            "tail_records": parsed_result.tail_records if parsed_result else [],
            "sample_records": parsed_result.sample_records if parsed_result else [],
            "parsing_warnings": parsed_result.parsing_warnings if parsed_result else [],
            "selected_sheet": parsed_result.selected_sheet if parsed_result else None,
        }
        if parsed_result
        else None,
    )

    await dataset_repo.create(dataset_model, metadata_model)

    return APIResponse(
        success=True,
        message="Dataset uploaded successfully."
        if not requires_sheet_selection
        else "Multiple sheets detected. Please select a sheet to proceed.",
        data=DatasetUploadResponse(
            dataset_id=dataset_id,
            name=clean_filename,
            original_filename=file.filename,
            file_format=format_enum,
            file_size_bytes=bytes_read,
            multiple_sheets_found=bool(detected_sheets and len(detected_sheets) > 1),
            detected_sheets=detected_sheets,
            selected_sheet=parsed_result.selected_sheet if parsed_result else None,
            requires_sheet_selection=requires_sheet_selection,
            parsing_decision=parsing_decision,
            storage_uri=destination_subpath,
            created_at=dataset_model.created_at or datetime_now(),
        ),
    )


@router.get("/{dataset_id}/sheets", response_model=APIResponse[SheetInspectionResponse], summary="Inspect Excel Sheets")
async def inspect_sheets(
    dataset_id: uuid.UUID,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Returns all available sheet names and dimensions for an Excel dataset."""
    user_uuid = parse_user_id(x_user_id)
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get_by_id(dataset_id, user_id=user_uuid)

    if not dataset:
        raise IngestionValidationError(f"Dataset '{dataset_id}' not found.", error_code="FILE_NOT_FOUND")

    if dataset.file_format != "xlsx":
        raise IngestionValidationError(
            f"Sheet inspection only applies to Excel XLSX files, not '{dataset.file_format}'.",
            error_code="INVALID_OPERATION",
        )

    storage = get_storage_provider()
    abs_path = await storage.get_file_path(dataset.storage_uri)
    sheets = IngestionService.inspect_excel_sheets(abs_path)

    return APIResponse(
        success=True,
        message=f"Found {len(sheets)} sheets in workbook.",
        data=SheetInspectionResponse(
            dataset_id=dataset_id,
            sheets=sheets,
            default_sheet=sheets[0].name if sheets else None,
        ),
    )


@router.post("/{dataset_id}/select-sheet", response_model=APIResponse[DatasetPreview], summary="Select Excel Sheet")
async def select_excel_sheet(
    dataset_id: uuid.UUID,
    payload: SelectSheetRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Parses the chosen worksheet and updates dataset dimensions and preview."""
    user_uuid = parse_user_id(x_user_id)
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get_by_id(dataset_id, user_id=user_uuid)

    if not dataset:
        raise IngestionValidationError(f"Dataset '{dataset_id}' not found.", error_code="FILE_NOT_FOUND")

    if dataset.file_format != "xlsx":
        raise IngestionValidationError(
            f"Sheet selection only applies to Excel XLSX files.", error_code="INVALID_OPERATION"
        )

    storage = get_storage_provider()
    abs_path = await storage.get_file_path(dataset.storage_uri)

    parsed = IngestionService.parse_dataset(
        file_path=abs_path,
        format_enum=FileFormatEnum.XLSX,
        sheet_name=payload.sheet_name,
    )

    # Update dataset model
    dataset.row_count = parsed.row_count
    dataset.column_count = parsed.column_count

    # Run automatic profiling on selected sheet
    try:
        profile_data = ProfilerEngine.profile_dataset(
            file_path=abs_path,
            format_str=FileFormatEnum.XLSX.value,
            sheet_name=payload.sheet_name,
            parsing_warnings=parsed.parsing_warnings,
        )
    except Exception:
        profile_data = {}

    # Update metadata
    if dataset.metadata_entry:
        dataset.metadata_entry.inferred_schema = parsed.inferred_types
        dataset.metadata_entry.summary_statistics = profile_data
        dataset.metadata_entry.missingness_report = profile_data.get("missingness", {})
        dataset.metadata_entry.duplicates_report = profile_data.get("duplicates", {})
        dataset.metadata_entry.quality_warnings = profile_data.get("quality_warnings", [{"message": w} for w in parsed.parsing_warnings])
        dataset.metadata_entry.sample_preview = {
            "column_names": parsed.headers,
            "inferred_types": parsed.inferred_types,
            "head_records": parsed.head_records,
            "tail_records": parsed.tail_records,
            "sample_records": parsed.sample_records,
            "parsing_warnings": parsed.parsing_warnings,
            "selected_sheet": parsed.selected_sheet,
        }

    await dataset_repo.update(dataset)

    return APIResponse(
        success=True,
        message=f"Successfully ingested worksheet '{payload.sheet_name}'.",
        data=DatasetPreview(
            dataset_id=dataset.id,
            selected_sheet=parsed.selected_sheet,
            total_rows=parsed.row_count,
            total_columns=parsed.column_count,
            column_names=parsed.headers,
            inferred_types=parsed.inferred_types,
            head_records=parsed.head_records,
            tail_records=parsed.tail_records,
            sample_records=parsed.sample_records,
            parsing_warnings=parsed.parsing_warnings,
        ),
    )


@router.post("/{dataset_id}/confirm", response_model=APIResponse[DatasetPreview], summary="Confirm Ingestion Options")
async def confirm_ingestion(
    dataset_id: uuid.UUID,
    payload: ConfirmIngestionRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Re-parses the original dataset with confirmed delimiter/encoding/sheet parameters."""
    user_uuid = parse_user_id(x_user_id)
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get_by_id(dataset_id, user_id=user_uuid)

    if not dataset:
        raise IngestionValidationError(f"Dataset '{dataset_id}' not found.", error_code="FILE_NOT_FOUND")

    storage = get_storage_provider()
    abs_path = await storage.get_file_path(dataset.storage_uri)

    format_enum = FileFormatEnum(dataset.file_format)
    parsed = IngestionService.parse_dataset(
        file_path=abs_path,
        format_enum=format_enum,
        sheet_name=payload.sheet_name,
        override_delimiter=payload.delimiter,
        override_encoding=payload.encoding,
    )

    dataset.row_count = parsed.row_count
    dataset.column_count = parsed.column_count

    # Run automatic profiling with confirmed parameters
    try:
        profile_data = ProfilerEngine.profile_dataset(
            file_path=abs_path,
            format_str=format_enum.value,
            sheet_name=payload.sheet_name,
            delimiter=payload.delimiter,
            encoding=payload.encoding,
            parsing_warnings=parsed.parsing_warnings,
        )
    except Exception:
        profile_data = {}

    if dataset.metadata_entry:
        dataset.metadata_entry.inferred_schema = parsed.inferred_types
        dataset.metadata_entry.summary_statistics = profile_data
        dataset.metadata_entry.missingness_report = profile_data.get("missingness", {})
        dataset.metadata_entry.duplicates_report = profile_data.get("duplicates", {})
        dataset.metadata_entry.quality_warnings = profile_data.get("quality_warnings", [{"message": w} for w in parsed.parsing_warnings])
        dataset.metadata_entry.sample_preview = {
            "column_names": parsed.headers,
            "inferred_types": parsed.inferred_types,
            "head_records": parsed.head_records,
            "tail_records": parsed.tail_records,
            "sample_records": parsed.sample_records,
            "parsing_warnings": parsed.parsing_warnings,
            "selected_sheet": parsed.selected_sheet,
        }

    await dataset_repo.update(dataset)

    return APIResponse(
        success=True,
        message="Dataset ingestion parameters confirmed and applied.",
        data=DatasetPreview(
            dataset_id=dataset.id,
            selected_sheet=parsed.selected_sheet,
            total_rows=parsed.row_count,
            total_columns=parsed.column_count,
            column_names=parsed.headers,
            inferred_types=parsed.inferred_types,
            head_records=parsed.head_records,
            tail_records=parsed.tail_records,
            sample_records=parsed.sample_records,
            parsing_warnings=parsed.parsing_warnings,
        ),
    )


@router.get("/{dataset_id}/preview", response_model=APIResponse[DatasetPreview], summary="Get Dataset Preview")
async def get_dataset_preview(
    dataset_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=50),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Returns first 10 rows, last 10 rows, random sample, inferred types, and parsing warnings."""
    user_uuid = parse_user_id(x_user_id)
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get_by_id(dataset_id, user_id=user_uuid)

    if not dataset:
        raise IngestionValidationError(f"Dataset '{dataset_id}' not found.", error_code="FILE_NOT_FOUND")

    preview_data = dataset.metadata_entry.sample_preview if dataset.metadata_entry else None
    if not preview_data:
        # Re-parse if preview was not pre-calculated
        storage = get_storage_provider()
        abs_path = await storage.get_file_path(dataset.storage_uri)
        parsed = IngestionService.parse_dataset(abs_path, FileFormatEnum(dataset.file_format))
        return APIResponse(
            success=True,
            message="Preview generated.",
            data=DatasetPreview(
                dataset_id=dataset.id,
                selected_sheet=parsed.selected_sheet,
                total_rows=parsed.row_count,
                total_columns=parsed.column_count,
                column_names=parsed.headers,
                inferred_types=parsed.inferred_types,
                head_records=parsed.head_records[:limit],
                tail_records=parsed.tail_records[:limit],
                sample_records=parsed.sample_records[:limit],
                parsing_warnings=parsed.parsing_warnings,
            ),
        )

    return APIResponse(
        success=True,
        message="Preview retrieved.",
        data=DatasetPreview(
            dataset_id=dataset.id,
            selected_sheet=preview_data.get("selected_sheet"),
            total_rows=dataset.row_count or 0,
            total_columns=dataset.column_count or 0,
            column_names=preview_data.get("column_names", []),
            inferred_types=preview_data.get("inferred_types", {}),
            head_records=preview_data.get("head_records", [])[:limit],
            tail_records=preview_data.get("tail_records", [])[:limit],
            sample_records=preview_data.get("sample_records", [])[:limit],
            parsing_warnings=preview_data.get("parsing_warnings", []),
        ),
    )


@router.get("/{dataset_id}", response_model=APIResponse[DatasetResponse], summary="Get Dataset Metadata")
async def get_dataset(
    dataset_id: uuid.UUID,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves dataset record and metadata summary."""
    user_uuid = parse_user_id(x_user_id)
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get_by_id(dataset_id, user_id=user_uuid)

    if not dataset:
        raise IngestionValidationError(f"Dataset '{dataset_id}' not found.", error_code="FILE_NOT_FOUND")

    metadata_dict = {}
    if dataset.metadata_entry:
        metadata_dict = {
            "inferred_schema": dataset.metadata_entry.inferred_schema,
            "quality_warnings": dataset.metadata_entry.quality_warnings,
            "parsed_sheets": dataset.metadata_entry.parsed_sheets,
        }

    return APIResponse(
        success=True,
        message="Dataset retrieved successfully.",
        data=DatasetResponse(
            id=dataset.id,
            user_id=dataset.user_id,
            name=dataset.name,
            original_filename=dataset.original_filename,
            file_format=dataset.file_format,
            file_size_bytes=dataset.file_size_bytes,
            row_count=dataset.row_count,
            column_count=dataset.column_count,
            checksum_sha256=dataset.checksum_sha256,
            is_deleted=dataset.is_deleted,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
            metadata_summary=metadata_dict,
        ),
    )


@router.get("", response_model=APIResponse[DatasetListResponse], summary="List Datasets")
async def list_datasets(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Lists user's datasets with pagination."""
    user_uuid = parse_user_id(x_user_id)
    dataset_repo = DatasetRepository(db)
    items, total = await dataset_repo.list_datasets(user_id=user_uuid, skip=skip, limit=limit)

    list_items = [
        DatasetListItem(
            id=d.id,
            name=d.name,
            original_filename=d.original_filename,
            file_format=d.file_format,
            file_size_bytes=d.file_size_bytes,
            row_count=d.row_count,
            column_count=d.column_count,
            created_at=d.created_at,
        )
        for d in items
    ]

    return APIResponse(
        success=True,
        message=f"Retrieved {len(list_items)} datasets.",
        data=DatasetListResponse(
            items=list_items,
            total=total,
            page=(skip // limit) + 1,
            page_size=limit,
        ),
    )


@router.delete("/{dataset_id}", response_model=APIResponse[bool], summary="Delete Dataset")
async def delete_dataset(
    dataset_id: uuid.UUID,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Deletes a dataset and cleans up its storage files."""
    user_uuid = parse_user_id(x_user_id)
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get_by_id(dataset_id, user_id=user_uuid)

    if not dataset:
        raise IngestionValidationError(f"Dataset '{dataset_id}' not found.", error_code="FILE_NOT_FOUND")

    storage_uri = dataset.storage_uri
    success = await dataset_repo.delete(dataset_id, user_id=user_uuid)

    # Clean up physical storage
    if success and storage_uri:
        storage = get_storage_provider()
        await storage.delete_file(storage_uri)

    return APIResponse(
        success=True,
        message=f"Dataset '{dataset_id}' successfully deleted.",
        data=success,
    )


def parse_user_id(user_str: Optional[str]) -> Optional[uuid.UUID]:
    if not user_str:
        return None
    try:
        return uuid.UUID(user_str)
    except ValueError:
        return None


def datetime_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
