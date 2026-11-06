"""
Raw table reader shared by the profiler and the analysis loader.

Both must see *exactly* the same rows and column names, otherwise a profile could say
"1,204 rows" while an analysis uses 1,203. This module is that single source of truth: it
reads a CSV/TSV/XLSX file into a header list plus rows of plain strings, applying the same
header sanitising, ragged-row repair and blank-row skipping as the ingestion parser.
"""

import csv
from typing import Any, List, Optional, Tuple

from app.services.ingestion.parser import IngestionService
from app.services.ingestion.validator import IngestionValidationError, IngestionValidator

# csv.field_size_limit defaults to 128 KiB which breaks on long free-text cells.
csv.field_size_limit(10 * 1024 * 1024)


def read_table_as_strings(
    file_path: str,
    format_str: str,
    sheet_name: Optional[str] = None,
    delimiter: Optional[str] = None,
    encoding: Optional[str] = None,
) -> Tuple[List[str], List[List[str]], List[str]]:
    """
    Returns (headers, rows, warnings). Every cell is a stripped string; empty cells are "".
    Raises IngestionValidationError for unreadable/empty files.
    """
    fmt = format_str.lower().lstrip(".")
    warnings: List[str] = []

    if fmt == "xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        try:
            target = sheet_name or wb.sheetnames[0]
            if target not in wb.sheetnames:
                raise IngestionValidationError(f"Sheet '{target}' not found.", error_code="SHEET_NOT_FOUND")
            raw_headers: List[str] = []
            rows: List[List[str]] = []
            iterator = wb[target].iter_rows(values_only=True)
            for r in iterator:
                if any(v is not None and str(v).strip() != "" for v in r):
                    raw_headers = [str(v).strip() if v is not None else "" for v in r]
                    break
            if not raw_headers:
                raise IngestionValidationError(f"Worksheet '{target}' contains no data.", error_code="EMPTY_SHEET")
            headers, hw = IngestionService._sanitize_headers(raw_headers)
            warnings.extend(hw)
            width = len(headers)
            for r in iterator:
                cells = [IngestionService._format_excel_value(v).strip() for v in r[:width]]
                if len(cells) < width:
                    cells.extend([""] * (width - len(cells)))
                if any(c != "" for c in cells):
                    rows.append(cells)
        finally:
            wb.close()
        return headers, rows, warnings

    # --- CSV / TSV ---------------------------------------------------------
    enc = encoding or IngestionValidator.detect_encoding(file_path)
    delim = delimiter or ("\t" if fmt == "tsv" else IngestionService._detect_delimiter(
        file_path, IngestionService_format(fmt), enc))
    headers = []
    rows = []
    ragged = 0
    with open(file_path, "r", encoding=enc, errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter=delim)
        raw_headers: List[str] = []
        for line in reader:
            if any(c.strip() for c in line):
                raw_headers = line
                break
        if not raw_headers:
            raise IngestionValidationError("File does not contain any valid header row.", error_code="MISSING_HEADERS")
        headers, hw = IngestionService._sanitize_headers(raw_headers)
        warnings.extend(hw)
        width = len(headers)
        for line in reader:
            if not any(c.strip() for c in line):
                continue
            if len(line) != width:
                ragged += 1
                line = (line + [""] * (width - len(line))) if len(line) < width else line[:width]
            rows.append([c.strip() for c in line])
    if ragged:
        warnings.append(f"{ragged} row(s) had an inconsistent number of fields and were padded/truncated to {len(headers)} columns.")
    return headers, rows, warnings


def IngestionService_format(fmt: str):
    """Maps a format string to the FileFormatEnum the parser's helpers expect."""
    from app.schemas.dataset import FileFormatEnum

    return FileFormatEnum(fmt)
