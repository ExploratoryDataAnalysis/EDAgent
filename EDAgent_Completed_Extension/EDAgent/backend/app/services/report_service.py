"""
Report generation and async-analysis job bodies (run in worker threads with a sync DB session).

Both read everything they need from the database, never from the HTTP request that started
them, so they keep working after the request has returned.
"""

import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.sync_db import sync_session
from app.models.analysis import AnalysisRequest
from app.models.dataset import Dataset
from app.models.report import GeneratedReport
from app.models.session import AnalysisSession
from app.schemas.analysis import AnalysisResultResponse, StructuredAnalysisPlan
from app.services import analysis_service
from app.services.analysis import engine
from app.services.data import loader
from app.services.dataset_service import absolute_path
from app.services.export import report as report_builder
from app.services.export_storage import export_path
from app.services.jobs.runner import JobContext

logger = logging.getLogger("edagent.reports")


def report_rel_path(user_id: uuid.UUID, report_id: uuid.UUID, fmt: str) -> str:
    return f"reports/{user_id}/{report_id}.{fmt}"


def generate_report_job(report_id: uuid.UUID):
    """Returns the job function that builds report `report_id` and stores the file."""

    def run(ctx: JobContext) -> Dict[str, Any]:
        ctx.progress(5, "Collecting results")
        with sync_session() as s:
            report = s.get(GeneratedReport, report_id)
            if report is None:
                raise RuntimeError("Report record not found")
            report.status = "PROCESSING"
            session = s.get(AnalysisSession, report.session_id)
            dataset = s.execute(select(Dataset).options(selectinload(Dataset.metadata_entry)).where(Dataset.id == session.dataset_id)).scalar_one()
            meta = dataset.metadata_entry
            cfg = report.config or {}
            wanted_ids = {str(x) for x in (cfg.get("included_result_ids") or [])}
            turns = s.execute(
                select(AnalysisRequest).options(selectinload(AnalysisRequest.result)).where(AnalysisRequest.session_id == session.id).order_by(AnalysisRequest.created_at)
            ).scalars().all()
            analyses: List[report_builder.ReportAnalysis] = []
            for t in turns:
                if t.result is None or not t.result.result_payload:
                    continue
                if wanted_ids and str(t.result.id) not in wanted_ids:
                    continue
                res = AnalysisResultResponse.model_validate(t.result.result_payload)
                analyses.append(
                    report_builder.ReportAnalysis(
                        label=t.user_query, result=res,
                        ai_text=t.assistant_message if t.explanation_source == "llm" else None,
                        fallback_text=t.assistant_message if t.explanation_source != "llm" else None,
                    )
                )
            inp = report_builder.ReportInput(
                title=report.title,
                concise=bool(cfg.get("concise_mode")),
                sections=list(report.included_sections),
                dataset_id=str(dataset.id),
                dataset_name=dataset.name,
                original_filename=dataset.original_filename,
                file_format=dataset.file_format,
                file_size_bytes=dataset.file_size_bytes,
                checksum_sha256=dataset.checksum_sha256,
                fingerprint=report.dataset_fingerprint,
                parse_options=meta.parse_options or {},
                profile=meta.summary_statistics or {},
                analyses=analyses,
            )
            fmt, user_id = report.format, report.user_id
        ctx.progress(30, "Building sections and charts")
        sections = report_builder.build_document(inp)
        ctx.progress(70, f"Rendering {fmt.upper()}")
        data = report_builder.render_pdf(inp, sections) if fmt == "pdf" else report_builder.render_html(inp, sections)
        rel = report_rel_path(user_id, report_id, fmt)
        path = export_path(rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        with sync_session() as s:
            report = s.get(GeneratedReport, report_id)
            report.storage_uri, report.status = rel, "SUCCESS"
        return {"report_id": str(report_id), "size_bytes": len(data)}

    def on_error(message: str) -> None:
        with sync_session() as s:
            report = s.get(GeneratedReport, report_id)
            if report:
                report.status, report.error_message = "FAILURE", message[:500]

    run.on_error = on_error  # type: ignore[attr-defined]
    return run


def analysis_job(session_id: uuid.UUID, plan: StructuredAnalysisPlan, label: str):
    """Job body for long-running analyses started via /analysis/execute-async."""

    def run(ctx: JobContext) -> Dict[str, Any]:
        ctx.progress(10, "Loading data")
        with sync_session() as s:
            session = s.get(AnalysisSession, session_id)
            dataset = s.execute(select(Dataset).options(selectinload(Dataset.metadata_entry)).where(Dataset.id == session.dataset_id)).scalar_one()
            meta = dataset.metadata_entry
            profile_cols = (meta.summary_statistics or {}).get("columns", [])
            path, fmt, checksum, opts, dataset_id = absolute_path(dataset.storage_uri), dataset.file_format, dataset.checksum_sha256, meta.parse_options, dataset.id
        loaded = loader.load_dataset(str(dataset_id), path, fmt, checksum, opts, profile_cols)
        ctx.progress(40, "Computing")
        result = engine.run_analysis(loaded, plan, dataset_id)
        with sync_session() as s:
            req, row = analysis_service.build_turn_rows(session_id, question=label, kind="analysis", assistant_message=result.summary_text, plan=plan, result=result, explanation_source="template")
            s.add(req)
            s.flush()
            if row is not None:
                s.add(row)
        return {"result_id": str(result.id), "request_id": str(result.request_id)}

    return run
