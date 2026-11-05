"""
Dataset Schemas for Phase 1 Ingestion, Validation and Preview
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from app.schemas.common import BaseSchema


class FileFormatEnum(str, Enum):
    CSV = "csv"
    TSV = "tsv"
    XLSX = "xlsx"


class SheetInfo(BaseSchema):
    name: str
    row_count_estimate: Optional[int] = None
    column_count_estimate: Optional[int] = None


class SheetInspectionResponse(BaseSchema):
    dataset_id: uuid.UUID
    sheets: List[SheetInfo]
    default_sheet: Optional[str] = None


class SelectSheetRequest(BaseSchema):
    sheet_name: str


class ConfirmIngestionRequest(BaseSchema):
    sheet_name: Optional[str] = None
    delimiter: Optional[str] = None
    encoding: Optional[str] = None


class DatasetUploadResponse(BaseSchema):
    dataset_id: uuid.UUID
    name: str
    original_filename: str
    file_format: FileFormatEnum
    file_size_bytes: int
    multiple_sheets_found: bool = False
    detected_sheets: Optional[List[str]] = None
    selected_sheet: Optional[str] = None
    requires_sheet_selection: bool = False
    parsing_decision: str
    storage_uri: str
    created_at: datetime


class DatasetURLImportRequest(BaseSchema):
    url: str
    dataset_name: Optional[str] = None


class DatasetPreview(BaseSchema):
    dataset_id: uuid.UUID
    selected_sheet: Optional[str] = None
    total_rows: int
    total_columns: int
    column_names: List[str]
    inferred_types: Dict[str, str] = {}
    head_records: List[Dict[str, Any]]
    tail_records: List[Dict[str, Any]]
    sample_records: List[Dict[str, Any]]
    parsing_warnings: List[str] = []


class DatasetResponse(BaseSchema):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    name: str
    original_filename: str
    file_format: str
    file_size_bytes: int
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    checksum_sha256: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    metadata_summary: Optional[Dict[str, Any]] = None


class DatasetListItem(BaseSchema):
    id: uuid.UUID
    name: str
    original_filename: str
    file_format: str
    file_size_bytes: int
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    created_at: datetime


class DatasetListResponse(BaseSchema):
    items: List[DatasetListItem]
    total: int
    page: int
    page_size: int
