"""
Tabular Dataset Ingestion & Parsing Engine
Supports CSV, TSV, and Excel (XLSX) with robust delimiter sniffing,
encoding detection, header sanitization, malformed row recovery,
type inference, and preview generation.
"""

import csv
import io
import os
import random
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import openpyxl

from app.schemas.dataset import (
    FileFormatEnum,
    SheetInfo,
)
from app.services.ingestion.validator import (
    IngestionValidator,
    IngestionValidationError,
)


class ParsedDatasetResult:
    """Encapsulates the complete result of parsing a dataset."""

    def __init__(
        self,
        headers: List[str],
        row_count: int,
        column_count: int,
        head_records: List[Dict[str, Any]],
        tail_records: List[Dict[str, Any]],
        sample_records: List[Dict[str, Any]],
        inferred_types: Dict[str, str],
        parsing_warnings: List[str],
        parsing_decisions: str,
        detected_sheets: Optional[List[str]] = None,
        selected_sheet: Optional[str] = None,
        encoding: Optional[str] = None,
        delimiter: Optional[str] = None,
    ):
        self.headers = headers
        self.row_count = row_count
        self.column_count = column_count
        self.head_records = head_records
        self.tail_records = tail_records
        self.sample_records = sample_records
        self.inferred_types = inferred_types
        self.parsing_warnings = parsing_warnings
        self.parsing_decisions = parsing_decisions
        self.detected_sheets = detected_sheets
        self.selected_sheet = selected_sheet
        self.encoding = encoding
        self.delimiter = delimiter


class IngestionService:
    """Core service for parsing, previewing, and inspecting tabular datasets."""

    DATE_PATTERNS = [
        re.compile(r"^\d{4}-\d{2}-\d{2}$"),
        re.compile(r"^\d{4}/\d{2}/\d{2}$"),
        re.compile(r"^\d{2}/\d{2}/\d{4}$"),
        re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}"),
    ]

    MAX_CELL_PREVIEW_LENGTH = 300
    PREVIEW_ROW_LIMIT = 10
    SAMPLE_RESERVOIR_SIZE = 10

    @classmethod
    def validate_file_format(cls, filename: str) -> str:
        """Validates file format and returns extension string (e.g. 'csv')."""
        try:
            return IngestionValidator.validate_extension(filename).value
        except IngestionValidationError as e:
            raise ValueError(e.message) from e

    @staticmethod
    def compute_sha256(file_path: str) -> str:
        """Computes SHA-256 hash of a file."""
        import hashlib
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def detect_delimiter(cls, file_path: str, default: str = ",") -> str:
        """Detects delimiter for CSV/TSV file."""
        enc = IngestionValidator.detect_encoding(file_path)
        fmt = FileFormatEnum.TSV if file_path.lower().endswith(".tsv") else FileFormatEnum.CSV
        return cls._detect_delimiter(file_path, fmt, enc)

    @classmethod
    def extract_preview(
        cls, file_path: str, delimiter: str = ",", limit: int = 10
    ) -> Dict[str, Any]:
        """Backward-compatible extraction preview."""
        fmt = FileFormatEnum.TSV if file_path.lower().endswith(".tsv") else FileFormatEnum.CSV
        parsed = cls._parse_delimited_text(file_path, fmt, override_delimiter=delimiter)
        return {
            "headers": parsed.headers,
            "rows": parsed.head_records[:limit],
            "parsing_decision": parsed.parsing_decisions,
            "total_preview_count": len(parsed.head_records[:limit]),
        }

    @classmethod
    def inspect_excel_sheets(cls, file_path: str) -> List[SheetInfo]:
        """Inspects all worksheets in an Excel workbook."""
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        sheet_infos: List[SheetInfo] = []
        try:
            for name in wb.sheetnames:
                ws = wb[name]
                # Fast estimate: max_row and max_column if available
                max_r = getattr(ws, "max_row", None)
                max_c = getattr(ws, "max_column", None)
                sheet_infos.append(
                    SheetInfo(
                        name=name,
                        row_count_estimate=max_r if max_r and max_r > 0 else None,
                        column_count_estimate=max_c if max_c and max_c > 0 else None,
                    )
                )
        finally:
            wb.close()
        return sheet_infos

    @classmethod
    def parse_dataset(
        cls,
        file_path: str,
        format_enum: FileFormatEnum,
        sheet_name: Optional[str] = None,
        override_delimiter: Optional[str] = None,
        override_encoding: Optional[str] = None,
    ) -> ParsedDatasetResult:
        """Main dispatcher for parsing tabular files."""
        if format_enum == FileFormatEnum.XLSX:
            return cls._parse_excel(file_path, sheet_name=sheet_name)
        elif format_enum in (FileFormatEnum.CSV, FileFormatEnum.TSV):
            return cls._parse_delimited_text(
                file_path=file_path,
                format_enum=format_enum,
                override_delimiter=override_delimiter,
                override_encoding=override_encoding,
            )
        else:
            raise IngestionValidationError(
                f"Unsupported format: {format_enum}", error_code="UNSUPPORTED_FORMAT"
            )

    @classmethod
    def _parse_delimited_text(
        cls,
        file_path: str,
        format_enum: FileFormatEnum,
        override_delimiter: Optional[str] = None,
        override_encoding: Optional[str] = None,
    ) -> ParsedDatasetResult:
        """Parses CSV and TSV files with delimiter sniffing and encoding detection."""
        encoding = override_encoding or IngestionValidator.detect_encoding(file_path)
        delimiter = override_delimiter or cls._detect_delimiter(file_path, format_enum, encoding)

        warnings: List[str] = []
        raw_headers: List[str] = []
        rows: List[List[str]] = []

        try:
            with open(file_path, "r", encoding=encoding, errors="replace") as f:
                reader = csv.reader(f, delimiter=delimiter)

                # 1. Read Header
                try:
                    for line in reader:
                        # Skip initial blank lines
                        if any(cell.strip() for cell in line):
                            raw_headers = line
                            break
                except csv.Error as e:
                    raise IngestionValidationError(
                        f"Malformed CSV header structure: {str(e)}", error_code="MALFORMED_CSV"
                    )

                if not raw_headers:
                    raise IngestionValidationError(
                        "File does not contain any valid header row.", error_code="MISSING_HEADERS"
                    )

                # Clean and deduplicate headers
                headers, header_warnings = cls._sanitize_headers(raw_headers)
                warnings.extend(header_warnings)
                col_count = len(headers)

                # 2. Stream Data Rows
                row_idx = 0
                head_records_raw: List[List[str]] = []
                tail_buffer: List[List[str]] = []
                sample_reservoir: List[List[str]] = []
                ragged_row_warnings = 0

                random.seed(42)  # Deterministic reservoir sampling

                for line in reader:
                    # Skip completely empty trailing lines
                    if not any(cell.strip() for cell in line):
                        continue

                    # Handle inconsistent column counts (ragged rows)
                    if len(line) < col_count:
                        if ragged_row_warnings < 5:
                            warnings.append(
                                f"Row {row_idx + 1} has {len(line)} values instead of {col_count}; padded with empty cells."
                            )
                            ragged_row_warnings += 1
                        line = line + [""] * (col_count - len(line))
                    elif len(line) > col_count:
                        if ragged_row_warnings < 5:
                            warnings.append(
                                f"Row {row_idx + 1} has {len(line)} values instead of {col_count}; excess cells truncated."
                            )
                            ragged_row_warnings += 1
                        line = line[:col_count]

                    # Head collection
                    if row_idx < cls.PREVIEW_ROW_LIMIT:
                        head_records_raw.append(line)

                    # Tail rolling window
                    tail_buffer.append(line)
                    if len(tail_buffer) > cls.PREVIEW_ROW_LIMIT:
                        tail_buffer.pop(0)

                    # Reservoir sampling for random sample
                    if len(sample_reservoir) < cls.SAMPLE_RESERVOIR_SIZE:
                        sample_reservoir.append(line)
                    else:
                        rand_pos = random.randint(0, row_idx)
                        if rand_pos < cls.SAMPLE_RESERVOIR_SIZE:
                            sample_reservoir[rand_pos] = line

                    row_idx += 1

                total_rows = row_idx

                if total_rows == 0:
                    warnings.append("Dataset contains a header row but 0 data rows.")

        except UnicodeDecodeError as e:
            raise IngestionValidationError(
                f"Encoding error reading file with '{encoding}': {str(e)}. Try specifying a different encoding.",
                error_code="ENCODING_ERROR",
            )
        except csv.Error as e:
            raise IngestionValidationError(
                f"CSV parsing error: {str(e)}", error_code="MALFORMED_CSV"
            )

        # Convert raw row arrays to dictionaries with truncated previews
        head_records = [cls._row_to_dict(headers, r) for r in head_records_raw]
        tail_records = [cls._row_to_dict(headers, r) for r in tail_buffer]
        sample_records = [cls._row_to_dict(headers, r) for r in sample_reservoir]

        # Infer storage types based on sample reservoir + head records
        sample_pool = head_records_raw + sample_reservoir
        inferred_types = cls._infer_column_types(headers, sample_pool)

        decision_text = (
            f"Parsed {format_enum.value.upper()} with encoding '{encoding}' and "
            f"delimiter '{cls._format_delimiter_name(delimiter)}'. "
            f"Detected {col_count} columns and {total_rows} rows."
        )

        return ParsedDatasetResult(
            headers=headers,
            row_count=total_rows,
            column_count=col_count,
            head_records=head_records,
            tail_records=tail_records,
            sample_records=sample_records,
            inferred_types=inferred_types,
            parsing_warnings=warnings,
            parsing_decisions=decision_text,
            encoding=encoding,
            delimiter=delimiter,
        )

    @classmethod
    def _parse_excel(
        cls,
        file_path: str,
        sheet_name: Optional[str] = None,
    ) -> ParsedDatasetResult:
        """Parses an Excel OpenXML (.xlsx) workbook."""
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        detected_sheets = wb.sheetnames

        if not detected_sheets:
            wb.close()
            raise IngestionValidationError(
                "Excel workbook contains no sheets.", error_code="EMPTY_EXCEL"
            )

        # Multiple sheets handling
        if sheet_name is None:
            if len(detected_sheets) > 1:
                wb.close()
                raise IngestionValidationError(
                    f"Workbook contains {len(detected_sheets)} sheets ({', '.join(detected_sheets)}). "
                    f"Please select which sheet to analyze.",
                    error_code="MULTIPLE_SHEETS_REQUIRE_SELECTION",
                )
            selected_sheet = detected_sheets[0]
        else:
            if sheet_name not in detected_sheets:
                wb.close()
                raise IngestionValidationError(
                    f"Sheet '{sheet_name}' not found. Available sheets: {', '.join(detected_sheets)}",
                    error_code="SHEET_NOT_FOUND",
                )
            selected_sheet = sheet_name

        ws = wb[selected_sheet]
        warnings: List[str] = []
        raw_headers: List[str] = []
        head_records_raw: List[List[str]] = []
        tail_buffer: List[List[str]] = []
        sample_reservoir: List[List[str]] = []

        random.seed(42)

        try:
            row_iterator = ws.iter_rows(values_only=True)

            # Find first non-empty row as header
            for row in row_iterator:
                if any(v is not None and str(v).strip() != "" for v in row):
                    raw_headers = [str(v).strip() if v is not None else "" for v in row]
                    break

            if not raw_headers:
                wb.close()
                raise IngestionValidationError(
                    f"Worksheet '{selected_sheet}' contains no data or headers.",
                    error_code="EMPTY_SHEET",
                )

            headers, header_warnings = cls._sanitize_headers(raw_headers)
            warnings.extend(header_warnings)
            col_count = len(headers)

            row_idx = 0
            for row in row_iterator:
                str_row = [
                    cls._format_excel_value(v) for v in row[:col_count]
                ]
                # Pad if row has fewer cells
                if len(str_row) < col_count:
                    str_row.extend([""] * (col_count - len(str_row)))

                # Skip completely blank lines
                if not any(c != "" for c in str_row):
                    continue

                if row_idx < cls.PREVIEW_ROW_LIMIT:
                    head_records_raw.append(str_row)

                tail_buffer.append(str_row)
                if len(tail_buffer) > cls.PREVIEW_ROW_LIMIT:
                    tail_buffer.pop(0)

                if len(sample_reservoir) < cls.SAMPLE_RESERVOIR_SIZE:
                    sample_reservoir.append(str_row)
                else:
                    rand_pos = random.randint(0, row_idx)
                    if rand_pos < cls.SAMPLE_RESERVOIR_SIZE:
                        sample_reservoir[rand_pos] = str_row

                row_idx += 1

            total_rows = row_idx
            if total_rows == 0:
                warnings.append(f"Worksheet '{selected_sheet}' has headers but 0 data rows.")

        finally:
            wb.close()

        head_records = [cls._row_to_dict(headers, r) for r in head_records_raw]
        tail_records = [cls._row_to_dict(headers, r) for r in tail_buffer]
        sample_records = [cls._row_to_dict(headers, r) for r in sample_reservoir]

        sample_pool = head_records_raw + sample_reservoir
        inferred_types = cls._infer_column_types(headers, sample_pool)

        decision_text = (
            f"Parsed Excel workbook sheet '{selected_sheet}' with {col_count} columns and {total_rows} rows. "
            f"Total sheets detected: {len(detected_sheets)}."
        )

        return ParsedDatasetResult(
            headers=headers,
            row_count=total_rows,
            column_count=col_count,
            head_records=head_records,
            tail_records=tail_records,
            sample_records=sample_records,
            inferred_types=inferred_types,
            parsing_warnings=warnings,
            parsing_decisions=decision_text,
            detected_sheets=detected_sheets,
            selected_sheet=selected_sheet,
        )

    @classmethod
    def _detect_delimiter(cls, file_path: str, format_enum: FileFormatEnum, encoding: str) -> str:
        """Sniffs delimiter using csv.Sniffer with safe format-aware heuristics."""
        default = "\t" if format_enum == FileFormatEnum.TSV else ","

        try:
            with open(file_path, "r", encoding=encoding, errors="replace") as f:
                sample = f.read(8192)

            if not sample.strip():
                return default

            # If format is TSV and tab occurs frequently, honor it
            if format_enum == FileFormatEnum.TSV and "\t" in sample:
                return "\t"

            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters=[",", "\t", ";", "|"])
            if dialect.delimiter in (",", "\t", ";", "|"):
                return dialect.delimiter
        except Exception:
            pass

        return default

    @classmethod
    def _sanitize_headers(cls, raw_headers: List[str]) -> Tuple[List[str], List[str]]:
        """
        Cleans headers, names empty headers (e.g. 'unnamed_1'),
        and deduplicates duplicate headers (e.g. 'age' -> 'age_1').
        """
        clean_headers: List[str] = []
        warnings: List[str] = []
        seen_counts: Dict[str, int] = {}

        for i, raw in enumerate(raw_headers):
            col_name = str(raw).strip()
            if not col_name:
                col_name = f"unnamed_{i + 1}"
                warnings.append(f"Empty header found at column position {i + 1}; assigned name '{col_name}'.")

            # Check duplication
            base_name = col_name
            if base_name in seen_counts:
                seen_counts[base_name] += 1
                col_name = f"{base_name}_{seen_counts[base_name]}"
                warnings.append(
                    f"Duplicate column name '{base_name}' detected at index {i + 1}; renamed to '{col_name}'."
                )
            else:
                seen_counts[base_name] = 0

            clean_headers.append(col_name)

        return clean_headers, warnings

    @classmethod
    def _infer_column_types(
        cls, headers: List[str], sample_rows: List[List[str]]
    ) -> Dict[str, str]:
        """Infers storage type for each column from sample rows."""
        inferred: Dict[str, str] = {}
        if not sample_rows:
            return {h: "string" for h in headers}

        for col_idx, col_name in enumerate(headers):
            col_values = [
                row[col_idx].strip()
                for row in sample_rows
                if col_idx < len(row) and row[col_idx].strip() != ""
            ]
            if not col_values:
                inferred[col_name] = "string"
                continue

            # Check boolean
            lowered = {v.lower() for v in col_values}
            if lowered.issubset({"true", "false", "0", "1", "yes", "no"}):
                inferred[col_name] = "boolean"
                continue

            # Check integer
            is_int = True
            for v in col_values:
                if not re.match(r"^-?\d+$", v):
                    is_int = False
                    break
            if is_int:
                inferred[col_name] = "integer"
                continue

            # Check float
            is_float = True
            for v in col_values:
                try:
                    float(v)
                except ValueError:
                    is_float = False
                    break
            if is_float:
                inferred[col_name] = "float"
                continue

            # Check datetime
            date_matches = 0
            for v in col_values[:20]:
                if any(pat.match(v) for pat in cls.DATE_PATTERNS):
                    date_matches += 1
            if date_matches / max(len(col_values[:20]), 1) >= 0.7:
                inferred[col_name] = "datetime"
                continue

            # Default
            inferred[col_name] = "string"

        return inferred

    @classmethod
    def _row_to_dict(cls, headers: List[str], row: List[str]) -> Dict[str, Any]:
        """Converts row list to dict, capping preview value lengths."""
        result: Dict[str, Any] = {}
        for i, h in enumerate(headers):
            val = row[i] if i < len(row) else ""
            if isinstance(val, str) and len(val) > cls.MAX_CELL_PREVIEW_LENGTH:
                val = val[: cls.MAX_CELL_PREVIEW_LENGTH] + "..."
            result[h] = val
        return result

    @classmethod
    def _format_excel_value(cls, val: Any) -> str:
        """Formats cell values from OpenPyXL cleanly."""
        if val is None:
            return ""
        if isinstance(val, datetime):
            return val.isoformat()
        return str(val)

    @classmethod
    def _format_delimiter_name(cls, delim: str) -> str:
        if delim == ",":
            return "comma (,)"
        elif delim == "\t":
            return "tab (\\t)"
        elif delim == ";":
            return "semicolon (;)"
        elif delim == "|":
            return "pipe (|)"
        return delim
