"""
Analysis service: runs a validated plan against a user's dataset and persists the outcome.

Responsibilities that do not belong in the pure engine:
* bounded concurrency + wall-clock timeout around the (CPU-bound) engine call,
* turning engine exceptions into stable, user-readable errors,
* persisting one conversation turn (request + result) per execution,
* the "you have run several hypothesis tests" multiple-comparison reminder.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.analysis import AnalysisRequest, AnalysisResult
from app.models.dataset import Dataset
from app.models.session import AnalysisSession
from app.schemas.analysis import AnalysisOperationEnum as Op, AnalysisResultResponse, StructuredAnalysisPlan
from app.services import dataset_service
from app.services.analysis import engine
from app.services.analysis.common import AnalysisError

HYPOTHESIS_OPS = {
    Op.T_TEST_INDEPENDENT.value, Op.T_TEST_PAIRED.value, Op.ANOVA_ONE_WAY.value, Op.CHI_SQUARE.value,
    Op.MANN_WHITNEY.value, Op.KRUSKAL_WALLIS.value, Op.WILCOXON.value,
}
# From this many tests in one session the multiple-comparisons reminder is attached.
MULTIPLE_TEST_THRESHOLD = 3

# One semaphore per running event loop (tests create several loops).
_semaphores: dict = {}


def _semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    sem = _semaphores.get(loop)
    if sem is None:
        sem = _semaphores[loop] = asyncio.Semaphore(max(1, settings.MAX_CONCURRENT_ANALYSES))
    return sem


async def run_plan(db: AsyncSession, dataset: Dataset, plan: StructuredAnalysisPlan, *, guest: bool = False) -> AnalysisResultResponse:
    """
    Executes a plan with concurrency and time limits. Raises PlanValidationError / AnalysisError
    (both carry readable messages). A timed-out computation keeps running in its worker thread
    until it finishes, but the request is released and the user is told to narrow the question.
    """
    loaded = await dataset_service.load_for_analysis(db, dataset, guest=guest)
    async with _semaphore():
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(engine.run_analysis, loaded, plan, dataset.id, row_cap=settings.MAX_RESULT_ROWS, use_cache=not guest),
                timeout=settings.ANALYSIS_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            raise AnalysisError(
                f"The analysis took longer than {settings.ANALYSIS_TIMEOUT_SECONDS} seconds and was stopped. "
                "Try filtering the data, selecting fewer columns, or asking for a sampled result."
            )


async def hypothesis_tests_in_session(db: AsyncSession, session_id: uuid.UUID) -> int:
    q = (
        select(func.count(AnalysisResult.id))
        .join(AnalysisRequest, AnalysisRequest.id == AnalysisResult.request_id)
        .where(AnalysisRequest.session_id == session_id, AnalysisResult.operation_type.in_(HYPOTHESIS_OPS))
    )
    return (await db.execute(q)).scalar_one() or 0


async def add_multiple_test_warning(db: AsyncSession, session_id: uuid.UUID, result: AnalysisResultResponse) -> None:
    if result.operation not in HYPOTHESIS_OPS:
        return
    previous = await hypothesis_tests_in_session(db, session_id)
    total = previous + 1
    if total >= MULTIPLE_TEST_THRESHOLD:
        result.warnings.append(
            f"This is hypothesis test number {total} in this session. Running many tests raises the chance of at least one "
            f"false positive; at alpha = 0.05 expect roughly one in twenty to be 'significant' by chance. Consider a "
            f"correction such as Bonferroni (alpha / {total} = {0.05 / total:.4f}) before drawing conclusions."
        )


def build_turn_rows(
    session_id: uuid.UUID,
    *,
    question: str,
    kind: str,
    assistant_message: str,
    plan: Optional[StructuredAnalysisPlan] = None,
    result: Optional[AnalysisResultResponse] = None,
    explanation_source: Optional[str] = None,
    error_message: Optional[str] = None,
) -> Tuple[AnalysisRequest, Optional[AnalysisResult]]:
    """Builds the ORM rows for one conversation turn; shared by the async API and job threads."""
    req = AnalysisRequest(
        id=uuid.uuid4(),
        session_id=session_id,
        user_query=question,
        structured_plan=plan.model_dump(mode="json") if plan else None,
        status="FAILED" if kind == "error" else "COMPLETED",
        kind=kind,
        assistant_message=assistant_message,
        explanation_source=explanation_source,
        error_message=error_message,
    )
    row = None
    if result is not None:
        result.request_id = req.id
        row = AnalysisResult(
            id=result.id,
            request_id=req.id,
            operation_type=result.operation,
            summary_text=result.summary_text,
            execution_code=result.execution.code or "",
            records_examined=result.records_examined,
            records_used=result.records_used,
            is_sampled=result.is_sampled,
            sample_size=result.sample_size,
            plot_spec=result.charts[0].model_dump(mode="json") if result.charts else None,
            data_table=result.tables[0].model_dump(mode="json") if result.tables else None,
            warnings=result.warnings,
            execution_time_ms=result.execution.time_ms,
            result_payload=result.model_dump(mode="json"),
        )
    return req, row


async def persist_turn(db: AsyncSession, session: AnalysisSession, **kwargs) -> AnalysisRequest:
    """Stores one conversation turn (and its result, when a computation ran)."""
    req, row = build_turn_rows(session.id, **kwargs)
    db.add(req)
    await db.flush()  # the request row must exist before the result that points at it
    if row is not None:
        db.add(row)
    session.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(req)
    return req


def result_from_row(row: AnalysisResult) -> Optional[AnalysisResultResponse]:
    """Rebuilds the full structured result stored with a turn."""
    if not row or not row.result_payload:
        return None
    res = AnalysisResultResponse.model_validate(row.result_payload)
    res.id = row.id
    res.request_id = row.request_id
    return res


def explain_exact_or_sampled(result: AnalysisResultResponse) -> str:
    return "sampled (approximate)" if result.is_approximate else "exact (full dataset)"
