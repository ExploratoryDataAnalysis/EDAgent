"""
File builders for result exports: tables (CSV/XLSX), chart HTML/PNG/SVG, analysis metadata,
reproducible code and a Jupyter notebook. Everything is generated from the stored structured
result, so an export always matches what the backend computed.

Spreadsheet formula-injection defence: every text cell starting with = + - @ (or tab/CR) is
prefixed with an apostrophe by `sanitize_csv_cell`; numbers stay numeric.
"""

import csv
import io
import json
import re
import zipfile
from typing import Any, Dict, List, Optional

import openpyxl
from openpyxl.utils import get_column_letter

from app.core.security import safe_filename, sanitize_csv_cell
from app.schemas.analysis import AnalysisResultResponse, ResultChart, ResultTable
from app.services.export.charts_static import render_bytes


def _cell(v: Any) -> Any:
    """Prepares a value for a spreadsheet/CSV cell."""
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False)
    return sanitize_csv_cell(v)


def table_to_csv(table: ResultTable) -> bytes:
    buf = io.StringIO(newline="")
    w = csv.writer(buf)
    w.writerow([_cell(c) for c in table.columns])
    for row in table.rows:
        w.writerow(["" if row.get(c) is None else _cell(row.get(c)) for c in table.columns])
    # UTF-8 with BOM so Excel opens non-ASCII text correctly.
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def _sheet_title(name: str, used: set) -> str:
    title = re.sub(r"[\\/*?:\[\]]", "_", name)[:28] or "table"
    base, i = title, 2
    while title.lower() in used:
        title = f"{base[:25]}_{i}"
        i += 1
    used.add(title.lower())
    return title


def tables_to_xlsx(tables: List[ResultTable], extra_sheets: Optional[Dict[str, List[List[Any]]]] = None) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    used: set = set()
    for t in tables:
        ws = wb.create_sheet(_sheet_title(t.name, used))
        ws.append([_cell(c) for c in t.columns])
        for row in t.rows:
            ws.append([_cell(row.get(c)) for c in t.columns])
        for i, c in enumerate(t.columns, start=1):
            ws.column_dimensions[get_column_letter(i)].width = min(max(len(str(c)) + 2, 12), 40)
        ws.freeze_panes = "A2"
    for name, rows in (extra_sheets or {}).items():
        ws = wb.create_sheet(_sheet_title(name, used))
        for r in rows:
            ws.append([_cell(v) for v in r])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def find_chart(result: AnalysisResultResponse, chart_id: str) -> Optional[ResultChart]:
    return next((c for c in result.charts if c.id == chart_id), None)


def chart_to_html(chart: ResultChart) -> bytes:
    """Self-contained interactive chart (Plotly.js embedded so it opens offline)."""
    import plotly.graph_objects as go
    import plotly.io as pio

    fig = go.Figure(chart.spec)
    return pio.to_html(fig, include_plotlyjs=True, full_html=True, config={"displaylogo": False}).encode("utf-8")


def chart_to_image(chart: ResultChart, fmt: str) -> bytes:
    return render_bytes(chart.spec, fmt)


def result_metadata(result: AnalysisResultResponse) -> Dict[str, Any]:
    """Parameters, filters, methodology and execution details of one analysis."""
    return {
        "operation": result.operation,
        "dataset_id": str(result.dataset_id),
        "dataset_fingerprint": result.dataset_fingerprint,
        "plan": result.plan.model_dump(mode="json"),
        "filters_applied": result.filters_applied.model_dump(mode="json") if result.filters_applied else None,
        "columns_used": result.columns_used,
        "records_examined": result.records_examined,
        "records_used": result.records_used,
        "records_excluded": result.records_excluded,
        "exclusions": [e.model_dump() for e in result.exclusions],
        "missing_value_handling": result.missing_value_handling,
        "exact_or_sampled": "sampled (approximate)" if result.is_approximate else "exact (full dataset)",
        "sample_size": result.sample_size,
        "sampling_method": result.sampling_method,
        "metrics": result.metrics,
        "warnings": result.warnings,
        "methodology": result.methodology,
        "summary": result.summary_text,
        "interpretation": result.interpretation,
        "execution": {
            "time_ms": result.execution.time_ms,
            "engine": result.execution.engine,
            "seed": result.execution.seed,
            "library_versions": result.execution.library_versions,
            "executed_at": result.execution.executed_at,
        },
        "note": "All numbers in this file were computed by the EDAgent backend. AI-written text, if any, is not included here.",
    }


def result_notebook(result: AnalysisResultResponse) -> bytes:
    """Minimal .ipynb that reproduces the analysis from the original file."""
    code = result.execution.code or "# no code available"
    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": [f"# {result.operation}\n", f"\n{result.methodology}\n"]},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": code.splitlines(keepends=True)},
        ],
    }
    return json.dumps(nb, indent=1).encode("utf-8")


def result_bundle(result: AnalysisResultResponse, label: str = "analysis") -> bytes:
    """ZIP with every export of a result: charts (PNG/SVG/HTML), tables (CSV/XLSX), metadata and code."""
    buf = io.BytesIO()
    prefix = safe_filename(label, "analysis")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{prefix}/metadata.json", json.dumps(result_metadata(result), indent=2, default=str))
        z.writestr(f"{prefix}/reproduce.py", result.execution.code or "")
        z.writestr(f"{prefix}/reproduce.ipynb", result_notebook(result))
        for c in result.charts:
            stem = safe_filename(c.id, "chart")
            z.writestr(f"{prefix}/charts/{stem}.png", chart_to_image(c, "png"))
            z.writestr(f"{prefix}/charts/{stem}.svg", chart_to_image(c, "svg"))
            z.writestr(f"{prefix}/charts/{stem}.html", chart_to_html(c))
        for i, t in enumerate(result.tables):
            stem = safe_filename(t.name, f"table{i}")
            z.writestr(f"{prefix}/tables/{i + 1:02d}_{stem}.csv", table_to_csv(t))
        if result.tables:
            z.writestr(f"{prefix}/tables/all_tables.xlsx", tables_to_xlsx(result.tables))
    return buf.getvalue()
