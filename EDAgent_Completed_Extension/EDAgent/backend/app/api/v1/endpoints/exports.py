"""
Export centre endpoints: charts (PNG/SVG/HTML), tables (CSV/XLSX), analysis metadata, reproducible
code/notebook, per-result and per-session bundles, and the dataset profile.

Everything is built from the stored structured result, so an export always matches what the
backend computed. Ownership is checked through the result's session.
"""

import asyncio
import io
import json
import uuid
import zipfile
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import charge_guest, get_current_user
from app.core.security import safe_filename
from app.models.user import User
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.analysis import AnalysisResultResponse
from app.services import analysis_service, dataset_service
from app.services.analysis.common import AnalysisError
from app.services.export import files

router = APIRouter()

_CHART_TYPES = {"png": "image/png", "svg": "image/svg+xml", "html": "text/html; charset=utf-8", "json": "application/json"}
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _download(data: bytes, filename: str, media: str) -> Response:
    # filename is sanitised: it can contain user-controlled text (analysis labels, column names).
    return Response(content=data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{safe_filename(filename)}"'})


async def _result(db: AsyncSession, result_id: uuid.UUID, user: User) -> AnalysisResultResponse:
    row = await SessionRepository(db).get_result(result_id, user.id)
    res = analysis_service.result_from_row(row) if row else None
    if res is None:
        raise HTTPException(status_code=404, detail="Result not found.")
    return res


@router.get("/results/{result_id}/charts/{chart_id}", summary="Export A Chart")
async def export_chart(result_id: uuid.UUID, chart_id: str, format: str = Query("png", pattern="^(png|svg|html|json)$"), user: User = Depends(charge_guest), db: AsyncSession = Depends(get_db)):
    res = await _result(db, result_id, user)
    chart = files.find_chart(res, chart_id)
    if chart is None:
        raise HTTPException(status_code=404, detail="Chart not found in this result.")
    if format == "html":
        data = await asyncio.to_thread(files.chart_to_html, chart)
    elif format == "json":
        data = json.dumps(chart.spec).encode()
    else:
        data = await asyncio.to_thread(files.chart_to_image, chart, format)
    return _download(data, f"{chart.id}.{format}", _CHART_TYPES[format])


@router.get("/results/{result_id}/tables/{index}", summary="Export A Result Table")
async def export_table(
    result_id: uuid.UUID,
    index: int,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    full: bool = Query(True, description="Re-run truncated tables so the file holds every row (up to the export cap)."),
    user: User = Depends(charge_guest),
    db: AsyncSession = Depends(get_db),
):
    res = await _result(db, result_id, user)
    if index < 0 or index >= len(res.tables):
        raise HTTPException(status_code=404, detail="Table not found in this result.")
    table = res.tables[index]
    if full and table.truncated:
        # The stored result keeps only the first MAX_RESULT_ROWS rows; recompute with a higher cap
        # (deterministic, same plan) so the export is complete.
        from app.services.analysis import engine

        dataset = await DatasetRepository(db).get_by_id(res.dataset_id, user.id)
        if dataset is None:
            raise HTTPException(status_code=404, detail="Dataset not found.")
        loaded = await dataset_service.load_for_analysis(db, dataset, guest=user.is_guest)
        try:
            fresh = await asyncio.to_thread(engine.run_analysis, loaded, res.plan, dataset.id, row_cap=settings.MAX_EXPORT_ROWS, use_cache=False)
        except AnalysisError as e:
            raise HTTPException(status_code=422, detail=str(e))
        if index < len(fresh.tables):
            table = fresh.tables[index]
    if format == "csv":
        return _download(files.table_to_csv(table), f"{table.name}.csv", "text/csv; charset=utf-8")
    return _download(await asyncio.to_thread(files.tables_to_xlsx, [table]), f"{table.name}.xlsx", _XLSX)


@router.get("/results/{result_id}/metadata", summary="Export Analysis Metadata (JSON)")
async def export_metadata(result_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await _result(db, result_id, user)
    return _download(json.dumps(files.result_metadata(res), indent=2, default=str).encode(), f"{res.operation}_metadata.json", "application/json")


@router.get("/results/{result_id}/code", summary="Export Reproducible Code")
async def export_code(result_id: uuid.UUID, format: str = Query("py", pattern="^(py|ipynb)$"), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await _result(db, result_id, user)
    if format == "ipynb":
        return _download(files.result_notebook(res), f"{res.operation}.ipynb", "application/x-ipynb+json")
    return _download((res.execution.code or "").encode(), f"{res.operation}.py", "text/x-python; charset=utf-8")


@router.get("/results/{result_id}/bundle", summary="Download Everything For One Result (ZIP)")
async def export_result_bundle(result_id: uuid.UUID, user: User = Depends(charge_guest), db: AsyncSession = Depends(get_db)):
    res = await _result(db, result_id, user)
    data = await asyncio.to_thread(files.result_bundle, res, res.operation)
    return _download(data, f"{res.operation}_bundle.zip", "application/zip")


@router.get("/sessions/{session_id}/bundle", summary="Download All Results Of A Session (ZIP)")
async def export_session_bundle(session_id: uuid.UUID, user: User = Depends(charge_guest), db: AsyncSession = Depends(get_db)):
    repo = SessionRepository(db)
    session = await repo.get(session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    results = [analysis_service.result_from_row(t.result) for t in await repo.turns(session.id) if t.result is not None]
    results = [r for r in results if r]
    if not results:
        raise HTTPException(status_code=404, detail="This session has no analysis results yet.")

    def build() -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for i, r in enumerate(results, start=1):
                inner = files.result_bundle(r, f"{i:02d}_{r.operation}")
                with zipfile.ZipFile(io.BytesIO(inner)) as zi:
                    for name in zi.namelist():
                        z.writestr(name, zi.read(name))
        return buf.getvalue()

    return _download(await asyncio.to_thread(build), f"{safe_filename(session.title, 'session')}_results.zip", "application/zip")


@router.get("/datasets/{dataset_id}/profile", summary="Export Dataset Profile")
async def export_profile(dataset_id: uuid.UUID, format: str = Query("xlsx", pattern="^(xlsx|json)$"), user: User = Depends(charge_guest), db: AsyncSession = Depends(get_db)):
    dataset = await DatasetRepository(db).get_by_id(dataset_id, user.id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    profile = await dataset_service.get_or_compute_profile(db, dataset)
    stem = safe_filename(dataset.name, "dataset")
    if format == "json":
        return _download(json.dumps(profile, indent=2, default=str).encode(), f"{stem}_profile.json", "application/json")
    from app.schemas.analysis import ResultTable

    cols = profile.get("columns", [])
    inv = ResultTable(
        name="Column inventory", total_rows=len(cols),
        columns=["column", "stored_as", "inferred_type", "role", "non_null", "missing_pct", "distinct"],
        rows=[{"column": c["name"], "stored_as": c["storage_dtype"], "inferred_type": c["inferred_type"], "role": c["semantic_role"], "non_null": c["non_null_count"], "missing_pct": c["missing_percentage"], "distinct": c["distinct_count"]} for c in cols],
    )
    num = [c for c in cols if c.get("numeric_summary")]
    stats = ResultTable(
        name="Numeric statistics", total_rows=len(num),
        columns=["column", "count", "mean", "std", "min", "q25", "median", "q75", "max", "skewness", "kurtosis"],
        rows=[{"column": c["name"], **{k: c["numeric_summary"].get(k) for k in ["count", "mean", "std", "min", "q25", "median", "q75", "max", "skewness", "kurtosis"]}} for c in num],
    )
    warns = profile.get("quality_warnings", [])
    quality = ResultTable(
        name="Quality findings", total_rows=len(warns), columns=["severity", "column", "check", "message"],
        rows=[{"severity": w.get("severity"), "column": w.get("column"), "check": w.get("check_type"), "message": w.get("message")} for w in warns],
    )
    data = await asyncio.to_thread(files.tables_to_xlsx, [inv, stats, quality])
    return _download(data, f"{stem}_profile.xlsx", files_xlsx())


def files_xlsx() -> str:
    return _XLSX
