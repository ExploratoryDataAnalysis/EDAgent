"""
Dataset service: everything between "bytes arrived" and "dataset is ready to analyse".

The endpoints stay thin and call into this module for:

* streaming an upload (or a remote download) to isolated per-user storage,
* validating, parsing and profiling the file (CPU work runs in a worker thread),
* persisting the dataset + profile + the parse options that were used,
* re-parsing when the user picks a sheet / delimiter / encoding,
* loading the typed DataFrame that analyses run on.

The original file is only ever read. All type conversion happens in memory (see data/loader.py).
"""

import asyncio
import hashlib
import logging
import os
import shutil
import uuid
from typing import Any, Dict, List, Optional, Tuple

from fastapi import UploadFile

from app.core.config import settings
from app.core.security import safe_filename, validate_url_safe
from app.core.storage import LocalStorageProvider, get_storage_provider
from app.models.dataset import Dataset, DatasetMetadata
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.dataset import FileFormatEnum
from app.services.analysis import engine as analysis_engine
from app.services.data import loader
from app.services.ingestion.parser import IngestionService, ParsedDatasetResult
from app.services.ingestion.validator import IngestionValidationError, IngestionValidator
from app.services.profiler.profiler_engine import ProfilerEngine

logger = logging.getLogger("edagent.datasets")

_CHUNK = 64 * 1024


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def storage_subpath(user_id: uuid.UUID, dataset_id: uuid.UUID, filename: str) -> str:
    """Per-user / per-dataset folder so one account's files never share a directory with another's."""
    return f"{user_id}/{dataset_id}/{filename}"


def _local_storage() -> LocalStorageProvider:
    storage = get_storage_provider()
    if not isinstance(storage, LocalStorageProvider):
        raise IngestionValidationError(
            "Only local storage is implemented for uploads in this build (S3 is a documented extension point).",
            error_code="STORAGE_UNSUPPORTED",
        )
    return storage


def absolute_path(rel_path: str) -> str:
    """Resolves a stored relative path, refusing anything that escapes the storage root."""
    storage = _local_storage()
    full = os.path.abspath(os.path.join(storage.base_dir, rel_path))
    if os.path.commonpath([full, storage.base_dir]) != storage.base_dir:
        raise IngestionValidationError("Invalid storage path.", error_code="INVALID_PATH")
    return full


def remove_dataset_files(rel_path: str) -> None:
    """Deletes the dataset's whole folder (original file included)."""
    try:
        folder = os.path.dirname(absolute_path(rel_path))
    except IngestionValidationError:
        return
    shutil.rmtree(folder, ignore_errors=True)


async def save_upload(file: UploadFile, abs_dest: str, *, max_bytes: int | None = None) -> Tuple[int, str]:
    """Streams an upload to disk, enforcing the size limit while reading. Returns (size, sha256)."""
    os.makedirs(os.path.dirname(abs_dest), exist_ok=True)
    server_limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    max_bytes = min(max_bytes, server_limit) if max_bytes is not None else server_limit
    hasher = hashlib.sha256()
    size = 0
    with open(abs_dest, "wb") as out:
        while True:
            chunk = await file.read(_CHUNK)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise IngestionValidationError(
                    f"File size exceeds the upload limit of {max_bytes:,} bytes.", error_code="FILE_TOO_LARGE"
                )
            hasher.update(chunk)
            out.write(chunk)
    return size, hasher.hexdigest()


# ---------------------------------------------------------------------------
# Secure URL download (SSRF-aware)
# ---------------------------------------------------------------------------

async def download_url(url: str, abs_dest: str) -> Tuple[int, str, str]:
    """
    Downloads a remote CSV/TSV/XLSX with SSRF protections:
    * the URL (scheme, credentials, resolved IPs) is validated before every request,
    * redirects are followed manually, up to a small cap, and each hop is re-validated,
    * after connecting, the peer address is checked again to close DNS-rebinding gaps,
    * size and time limits are enforced while streaming.
    Returns (size_bytes, sha256, filename).
    """
    import httpx
    from urllib.parse import urljoin, urlparse

    from app.core.security import is_ip_blocked

    max_bytes = settings.URL_IMPORT_MAX_MB * 1024 * 1024
    current = url
    timeout = httpx.Timeout(settings.URL_IMPORT_TIMEOUT_SECONDS, connect=10.0)
    os.makedirs(os.path.dirname(abs_dest), exist_ok=True)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, headers={"User-Agent": "EDAgent-importer/1.0"}) as client:
        for _hop in range(settings.URL_IMPORT_MAX_REDIRECTS + 1):
            if settings.PREVENT_SSRF:
                # DNS resolution is blocking; keep it off the event loop.
                ok, reason = await asyncio.to_thread(validate_url_safe, current)
                if not ok:
                    raise IngestionValidationError(f"URL rejected: {reason}", error_code="URL_NOT_ALLOWED")
            try:
                async with client.stream("GET", current) as resp:
                    if settings.PREVENT_SSRF:
                        stream = resp.extensions.get("network_stream")
                        peer = stream.get_extra_info("server_addr") if stream is not None else None
                        if peer and is_ip_blocked(str(peer[0])):
                            raise IngestionValidationError("URL rejected: connected to a restricted address.", error_code="URL_NOT_ALLOWED")
                    if resp.status_code in (301, 302, 303, 307, 308):
                        location = resp.headers.get("location")
                        if not location:
                            raise IngestionValidationError("Redirect without a target.", error_code="URL_FETCH_FAILED")
                        current = urljoin(current, location)
                        continue
                    if resp.status_code != 200:
                        raise IngestionValidationError(f"The server answered HTTP {resp.status_code}.", error_code="URL_FETCH_FAILED")
                    declared = resp.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > max_bytes:
                        raise IngestionValidationError(
                            f"Remote file is larger than the {settings.URL_IMPORT_MAX_MB} MB import limit.", error_code="FILE_TOO_LARGE"
                        )
                    hasher = hashlib.sha256()
                    size = 0
                    with open(abs_dest, "wb") as out:
                        async for chunk in resp.aiter_bytes(_CHUNK):
                            size += len(chunk)
                            if size > max_bytes:
                                raise IngestionValidationError(
                                    f"Remote file is larger than the {settings.URL_IMPORT_MAX_MB} MB import limit.", error_code="FILE_TOO_LARGE"
                                )
                            hasher.update(chunk)
                            out.write(chunk)
                    name = os.path.basename(urlparse(current).path) or "imported.csv"
                    return size, hasher.hexdigest(), name
            except httpx.TimeoutException:
                raise IngestionValidationError("The remote server took too long to respond.", error_code="URL_FETCH_FAILED")
            except httpx.HTTPError as e:
                raise IngestionValidationError(f"Could not download the file ({type(e).__name__}).", error_code="URL_FETCH_FAILED")
        raise IngestionValidationError("Too many redirects.", error_code="URL_FETCH_FAILED")


# ---------------------------------------------------------------------------
# Parse + profile
# ---------------------------------------------------------------------------

def _parse_and_profile(
    abs_path: str,
    fmt: FileFormatEnum,
    sheet_name: Optional[str],
    delimiter: Optional[str],
    encoding: Optional[str],
    guest: bool = False,
) -> Tuple[ParsedDatasetResult, Dict[str, Any], Dict[str, Any]]:
    """Blocking: parse for the preview, then profile with the *resolved* options."""
    parsed = IngestionService.parse_dataset(abs_path, fmt, sheet_name=sheet_name, override_delimiter=delimiter, override_encoding=encoding)
    if guest and (parsed.row_count > 10_000 or len(parsed.headers) > 16):
        raise IngestionValidationError("Guest datasets can contain up to 10,000 rows and 16 columns.", error_code="QUOTA_EXCEEDED")
    options: Dict[str, Any] = {
        "delimiter": parsed.delimiter,
        "encoding": parsed.encoding,
        "sheet": parsed.selected_sheet if fmt == FileFormatEnum.XLSX else None,
    }
    try:
        profile = ProfilerEngine.profile_dataset(
            file_path=abs_path,
            format_str=fmt.value,
            sheet_name=options["sheet"],
            delimiter=options["delimiter"],
            encoding=options["encoding"],
            parsing_warnings=parsed.parsing_warnings,
        )
    except Exception:  # profile failure must not lose the upload; it is recomputed on demand
        if guest:
            logger.warning("Guest profiling failed during ingestion")
            raise IngestionValidationError("The guest dataset could not be profiled.", error_code="INVALID_FORMAT") from None
        else:
            logger.exception("Profiling failed during ingestion")
        profile = {}
    return parsed, profile, options


def _preview_dict(parsed: ParsedDatasetResult) -> Dict[str, Any]:
    return {
        "column_names": parsed.headers,
        "inferred_types": parsed.inferred_types,
        "head_records": parsed.head_records,
        "tail_records": parsed.tail_records,
        "sample_records": parsed.sample_records,
        "parsing_warnings": parsed.parsing_warnings,
        "selected_sheet": parsed.selected_sheet,
    }


def _apply_parse_result(dataset: Dataset, meta: DatasetMetadata, parsed: ParsedDatasetResult, profile: Dict[str, Any], options: Dict[str, Any]) -> None:
    dataset.row_count = parsed.row_count
    dataset.column_count = parsed.column_count
    meta.inferred_schema = parsed.inferred_types
    meta.summary_statistics = profile
    meta.missingness_report = profile.get("missingness", {})
    meta.duplicates_report = profile.get("duplicates", {})
    meta.quality_warnings = profile.get("quality_warnings", [{"message": w} for w in parsed.parsing_warnings])
    meta.sample_preview = _preview_dict(parsed)
    meta.parse_options = options


def invalidate_caches(dataset_id: uuid.UUID) -> None:
    """Drops cached frames and cached results after a re-parse or delete."""
    loader.invalidate_dataset(str(dataset_id))
    analysis_engine.clear_cache_for(dataset_id)


async def create_dataset_from_file(
    db,
    *,
    user_id: uuid.UUID,
    dataset_id: uuid.UUID,
    rel_path: str,
    original_filename: str,
    display_name: str,
    fmt: FileFormatEnum,
    size: int,
    checksum: str,
    sheet_name: Optional[str],
    guest: bool = False,
) -> Tuple[Dataset, Optional[ParsedDatasetResult], Optional[List[str]], bool, str]:
    """
    Validates, parses, profiles and stores a file that is already on disk.
    Returns (dataset, parsed_or_None, sheet_names, requires_sheet_selection, decision_text).
    Raises IngestionValidationError for unusable files (caller removes the folder).
    """
    abs_path = absolute_path(rel_path)
    IngestionValidator.validate_file_size(size)
    await asyncio.to_thread(IngestionValidator.validate_content_signature, abs_path, fmt)

    sheets: Optional[List[str]] = None
    parsed: Optional[ParsedDatasetResult] = None
    profile: Dict[str, Any] = {}
    options: Dict[str, Any] = {}
    requires_selection = False
    decision = ""

    if fmt == FileFormatEnum.XLSX:
        infos = await asyncio.to_thread(IngestionService.inspect_excel_sheets, abs_path)
        sheets = [s.name for s in infos]
        if len(sheets) > 1 and not sheet_name:
            requires_selection = True
            decision = f"Workbook contains {len(sheets)} sheets: {', '.join(sheets)}. Awaiting sheet selection."
        else:
            target = sheet_name or sheets[0]
            parsed, profile, options = await asyncio.to_thread(_parse_and_profile, abs_path, fmt, target, None, None)
    else:
        parsed, profile, options = await asyncio.to_thread(_parse_and_profile, abs_path, fmt, None, None, None, guest)
    if parsed:
        decision = parsed.parsing_decisions

    dataset = Dataset(
        id=dataset_id,
        user_id=user_id,
        name=display_name,
        original_filename=original_filename,
        file_format=fmt.value,
        storage_uri=rel_path,
        file_size_bytes=size,
        row_count=parsed.row_count if parsed else None,
        column_count=parsed.column_count if parsed else None,
        checksum_sha256=checksum,
        is_deleted=False,
    )
    meta = DatasetMetadata(
        id=uuid.uuid4(),
        dataset_id=dataset_id,
        inferred_schema=parsed.inferred_types if parsed else {},
        summary_statistics=profile,
        missingness_report=profile.get("missingness", {}),
        duplicates_report=profile.get("duplicates", {}),
        quality_warnings=profile.get("quality_warnings", [{"message": w} for w in (parsed.parsing_warnings if parsed else [])]),
        parsed_sheets=sheets,
        sample_preview=_preview_dict(parsed) if parsed else None,
        parse_options=options or None,
    )
    await DatasetRepository(db).create(dataset, meta)
    return dataset, parsed, sheets, requires_selection, decision


async def reparse_dataset(
    db,
    dataset: Dataset,
    *,
    sheet_name: Optional[str] = None,
    delimiter: Optional[str] = None,
    encoding: Optional[str] = None,
    guest: bool = False,
) -> ParsedDatasetResult:
    """Re-parses with new options (select-sheet / confirm) and stores the new preview, profile and options."""
    fmt = FileFormatEnum(dataset.file_format)
    abs_path = absolute_path(dataset.storage_uri)
    meta = dataset.metadata_entry
    previous = (meta.parse_options if meta and meta.parse_options else {})
    # Keep earlier choices the user did not override, so changing only the delimiter keeps the sheet.
    parsed, profile, options = await asyncio.to_thread(
        _parse_and_profile,
        abs_path,
        fmt,
        sheet_name or previous.get("sheet"),
        delimiter,
        encoding,
        guest,
    )
    _apply_parse_result(dataset, meta, parsed, profile, options)
    await DatasetRepository(db).update(dataset)
    invalidate_caches(dataset.id)
    return parsed


async def get_or_compute_profile(db, dataset: Dataset, force: bool = False) -> Dict[str, Any]:
    """Returns the stored profile; computes (and stores) it with the dataset's parse options when missing."""
    meta = dataset.metadata_entry
    cached = meta.summary_statistics if meta else None
    if not force and isinstance(cached, dict) and "overview" in cached:
        return cached
    if meta is None or not meta.parse_options:
        raise IngestionValidationError(
            "This workbook has several sheets; choose one first (POST /datasets/{id}/select-sheet).", error_code="SHEET_REQUIRED"
        )
    opts = meta.parse_options
    abs_path = absolute_path(dataset.storage_uri)
    profile = await asyncio.to_thread(
        ProfilerEngine.profile_dataset,
        abs_path,
        dataset.file_format,
        opts.get("sheet"),
        opts.get("delimiter"),
        opts.get("encoding"),
        (meta.sample_preview or {}).get("parsing_warnings", []),
    )
    meta.summary_statistics = profile
    meta.missingness_report = profile.get("missingness", {})
    meta.duplicates_report = profile.get("duplicates", {})
    meta.quality_warnings = profile.get("quality_warnings", [])
    await DatasetRepository(db).update(dataset)
    return profile


async def load_for_analysis(db, dataset: Dataset, *, guest: bool = False) -> "loader.LoadedDataset":
    """Typed DataFrame for a dataset (cached). Computes the profile first if it is missing."""
    profile = await get_or_compute_profile(db, dataset)
    meta = dataset.metadata_entry
    abs_path = absolute_path(dataset.storage_uri)
    return await asyncio.to_thread(
        loader.load_dataset,
        str(dataset.id),
        abs_path,
        dataset.file_format,
        dataset.checksum_sha256,
        meta.parse_options,
        profile.get("columns", []),
        use_cache=not guest,
    )


# ---------------------------------------------------------------------------
# Sample datasets (real files shipped with the app, copied per user on request)
# ---------------------------------------------------------------------------

def list_samples() -> List[Dict[str, Any]]:
    root = os.path.abspath(settings.SAMPLES_PATH)
    if not os.path.isdir(root):
        return []
    out = []
    for name in sorted(os.listdir(root)):
        if name.lower().endswith((".csv", ".tsv", ".xlsx")):
            path = os.path.join(root, name)
            out.append({"id": name, "name": name, "size_bytes": os.path.getsize(path), "description": _SAMPLE_DESCRIPTIONS.get(name, "Sample dataset")})
    return out


_SAMPLE_DESCRIPTIONS = {
    "employees_demo.csv": "600 synthetic employees: salary, department, tenure, performance and hire dates.",
    "sales_demo.csv": "1,200 synthetic orders: region, product category, revenue, discount and order dates.",
    "customer_churn_demo.csv": "800 synthetic customers with a churn flag, for classification and hypothesis tests.",
}


def sample_path(sample_id: str) -> str:
    """Only plain file names inside the samples folder are accepted (no traversal)."""
    root = os.path.abspath(settings.SAMPLES_PATH)
    if sample_id != os.path.basename(sample_id):
        raise IngestionValidationError("Unknown sample dataset.", error_code="FILE_NOT_FOUND")
    path = os.path.join(root, sample_id)
    if not os.path.isfile(path):
        raise IngestionValidationError("Unknown sample dataset.", error_code="FILE_NOT_FOUND")
    return path


def clean_name(filename: str) -> str:
    return safe_filename(filename, default="dataset")
