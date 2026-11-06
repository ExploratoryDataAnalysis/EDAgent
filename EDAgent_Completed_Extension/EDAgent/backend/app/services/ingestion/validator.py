"""
File Ingestion Validator
Performs strict multi-layer validation: extension, magic signatures,
file sizes, encoding, and format integrity.
Never trusts file extensions alone.
"""

import os
import zipfile
from typing import Tuple, Optional
import charset_normalizer
import openpyxl

from app.core.config import settings
from app.schemas.dataset import FileFormatEnum


# Limits for the zip-bomb check on .xlsx uploads.
MAX_XLSX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024  # 1 GiB once decompressed
MAX_XLSX_COMPRESSION_RATIO = 200


class IngestionValidationError(Exception):
    """Custom exception for understandable ingestion validation errors."""
    def __init__(self, message: str, error_code: str = "VALIDATION_ERROR"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class IngestionValidator:
    """Validates files before and during ingestion."""

    ALLOWED_EXTENSIONS = {
        ".csv": FileFormatEnum.CSV,
        ".tsv": FileFormatEnum.TSV,
        ".xlsx": FileFormatEnum.XLSX,
    }

    ZIP_MAGIC = b"PK\x03\x04"

    @classmethod
    def validate_extension(cls, filename: str) -> FileFormatEnum:
        """Validates extension and returns canonical FileFormatEnum."""
        if not filename or "." not in filename:
            raise IngestionValidationError(
                "Uploaded file must have a valid file extension (.csv, .tsv, .xlsx).",
                error_code="MISSING_EXTENSION"
            )

        ext = os.path.splitext(filename)[1].lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            allowed = ", ".join(cls.ALLOWED_EXTENSIONS.keys())
            raise IngestionValidationError(
                f"Unsupported file format '{ext}'. Only {allowed} files are supported in this phase.",
                error_code="UNSUPPORTED_FORMAT"
            )
        return cls.ALLOWED_EXTENSIONS[ext]

    @classmethod
    def validate_file_size(cls, file_size_bytes: int) -> None:
        """Enforces upload size limit."""
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if file_size_bytes == 0:
            raise IngestionValidationError(
                "The uploaded file is empty (0 bytes). Please upload a valid dataset.",
                error_code="EMPTY_FILE"
            )
        if file_size_bytes > max_bytes:
            mb_size = round(file_size_bytes / (1024 * 1024), 2)
            raise IngestionValidationError(
                f"File size ({mb_size} MB) exceeds the maximum allowed upload limit of {settings.MAX_UPLOAD_SIZE_MB} MB.",
                error_code="FILE_TOO_LARGE"
            )

    @classmethod
    def validate_content_signature(cls, file_path: str, format_enum: FileFormatEnum) -> None:
        """
        Deep inspection of file signatures and binary integrity.
        Never trusts the file extension alone.
        """
        if not os.path.exists(file_path):
            raise IngestionValidationError("File not found on storage.", error_code="FILE_NOT_FOUND")

        size = os.path.getsize(file_path)
        cls.validate_file_size(size)

        if format_enum == FileFormatEnum.XLSX:
            cls._validate_xlsx_content(file_path)
        elif format_enum in (FileFormatEnum.CSV, FileFormatEnum.TSV):
            cls._validate_text_content(file_path)

    @classmethod
    def _validate_xlsx_content(cls, file_path: str) -> None:
        """Validates that an Excel file is a genuine uncorrupted OpenXML workbook."""
        with open(file_path, "rb") as f:
            header = f.read(4)
            if header != cls.ZIP_MAGIC:
                raise IngestionValidationError(
                    "The file has an .xlsx extension but is not a valid OpenXML Excel spreadsheet (missing zip signature).",
                    error_code="CORRUPT_EXCEL"
                )

        if not zipfile.is_zipfile(file_path):
            raise IngestionValidationError(
                "Corrupted or invalid Excel file. The archive structure is damaged.",
                error_code="CORRUPT_EXCEL"
            )

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                namelist = zf.namelist()
                # Zip-bomb guard: an .xlsx is a zip, so a tiny upload could expand to gigabytes
                # when read. Check the declared uncompressed size and the compression ratio
                # before openpyxl ever touches it.
                infos = zf.infolist()
                total_uncompressed = sum(i.file_size for i in infos)
                total_compressed = max(sum(i.compress_size for i in infos), 1)
                if len(infos) > 5000 or total_uncompressed > MAX_XLSX_UNCOMPRESSED_BYTES or (
                    total_uncompressed / total_compressed > MAX_XLSX_COMPRESSION_RATIO and total_uncompressed > 50 * 1024 * 1024
                ):
                    raise IngestionValidationError(
                        "The Excel file expands to an unreasonable size when decompressed and was rejected for safety.",
                        error_code="EXCEL_TOO_LARGE_UNCOMPRESSED",
                    )
                if "[Content_Types].xml" not in namelist:
                    raise IngestionValidationError(
                        "Invalid Excel workbook structure (missing [Content_Types].xml).",
                        error_code="INVALID_EXCEL_STRUCTURE"
                    )
        except zipfile.BadZipFile:
            raise IngestionValidationError(
                "Corrupted Excel archive. Unable to read workbook contents.",
                error_code="CORRUPT_EXCEL"
            )

        # Attempt to load workbook headers safely
        try:
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            if not wb.sheetnames:
                wb.close()
                raise IngestionValidationError(
                    "Excel workbook contains no sheets.",
                    error_code="EMPTY_EXCEL"
                )
            wb.close()
        except openpyxl.utils.exceptions.InvalidFileException as e:
            raise IngestionValidationError(
                f"Invalid or corrupted Excel file: {str(e)}",
                error_code="INVALID_EXCEL"
            )
        except Exception as e:
            msg = str(e).lower()
            if "encrypted" in msg or "password" in msg:
                raise IngestionValidationError(
                    "Password-protected or encrypted Excel files are not supported. Please remove encryption before uploading.",
                    error_code="EXCEL_PASSWORD_PROTECTED"
                )
            raise IngestionValidationError(
                f"Failed to inspect Excel workbook: {str(e)}",
                error_code="INVALID_EXCEL"
            )

    @classmethod
    def _validate_text_content(cls, file_path: str) -> None:
        """Validates CSV/TSV for text encoding and absence of binary/null bytes."""
        with open(file_path, "rb") as f:
            sample = f.read(8192)

        # Check for binary null bytes
        if b"\x00" in sample:
            raise IngestionValidationError(
                "Binary data or null bytes detected in tabular text file. Only plain-text CSV or TSV files are supported.",
                error_code="BINARY_FILE_DETECTED"
            )

        # Verify it contains non-whitespace text
        if not sample.strip():
            raise IngestionValidationError(
                "The file contains only empty or whitespace characters.",
                error_code="EMPTY_FILE"
            )

    @classmethod
    def detect_encoding(cls, file_path: str) -> str:
        """Detects text file encoding using charset_normalizer with safe fallback."""
        try:
            results = charset_normalizer.from_path(file_path)
            best = results.best()
            if best and best.encoding:
                # Normalise encoding name
                enc = best.encoding.lower()
                # Test reading a small block
                with open(file_path, "r", encoding=enc, errors="strict") as test_f:
                    test_f.read(4096)
                return enc
        except Exception:
            pass

        # Fallback sequence: UTF-8 -> UTF-8-SIG (BOM) -> Latin-1 -> CP1252
        for candidate in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                with open(file_path, "r", encoding=candidate, errors="strict") as f:
                    f.read(8192)
                return candidate
            except (UnicodeDecodeError, Exception):
                continue

        # Ultimate safe fallback
        return "utf-8"
