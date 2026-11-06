"""
Deterministic analysis engine.

`run_analysis` is the single entry point used by the API, the AI chat and the report builder:

    plan (data) -> validate -> filter -> (optional sample) -> run approved operation
                -> assemble one consistent, structured result object

It never evaluates strings as code, never mutates the loaded dataset and never silently
changes a parameter. Identical (dataset fingerprint, plan) pairs are served from a small LRU
cache; the cache key includes the fingerprint so re-parsing a file invalidates old results.
"""

import json
import platform
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import scipy
import sklearn

from app.core.config import settings
from app.schemas.analysis import (
    AnalysisOperationEnum as Op, AnalysisResultResponse, ExclusionNote, ExecutionInfo, MissingPolicyEnum, ScopeEnum, StructuredAnalysisPlan,
)
from app.services.analysis import catalogue
from app.services.analysis.common import AnalysisError, Ctx, OpOutput, PlanValidationError, jsonable
from app.services.analysis.filters import build_mask, describe_filters, filter_code
from app.services.data.loader import LoadedDataset

_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_cache_lock = threading.Lock()


def _versions() -> Dict[str, str]:
    return {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__, "scipy": scipy.__version__, "scikit-learn": sklearn.__version__}


def _plan_key(fingerprint: str, plan: StructuredAnalysisPlan, row_cap: int) -> str:
    return f"{fingerprint}|{row_cap}|" + json.dumps(plan.model_dump(mode="json"), sort_keys=True, default=str)


def clear_cache_for(fingerprint_prefix: str = "") -> None:
    with _cache_lock:
        for k in [k for k in _cache if k.startswith(fingerprint_prefix)]:
            _cache.pop(k, None)


def _code_header(loaded: LoadedDataset, cols: List[str]) -> str:
    lines = ["import numpy as np", "import pandas as pd", "from scipy import stats", "",
             "# Reload your ORIGINAL file (EDAgent never modifies it) and convert types as EDAgent did:",
             'df = pd.read_csv("your_file.csv", dtype=str)  # use pd.read_excel(..., dtype=str) for .xlsx']
    for c in dict.fromkeys(cols):
        info = loaded.columns.get(c)
        if info is None:
            continue
        if info.kind == "numeric":
            lines.append(f"df[{c!r}] = pd.to_numeric(df[{c!r}].str.replace(',', ''), errors='coerce')")
        elif info.kind == "datetime":
            lines.append(f"df[{c!r}] = pd.to_datetime(df[{c!r}], errors='coerce')")
    return "\n".join(lines)


def effective_plan(plan: StructuredAnalysisPlan, loaded: LoadedDataset) -> StructuredAnalysisPlan:
    """Resolves `custom_chart` to the concrete operation; every other plan is returned unchanged."""
    if plan.operation == Op.CUSTOM_CHART:
        return catalogue.resolve_custom_chart(plan, loaded)
    return plan


def run_analysis(
    loaded: LoadedDataset,
    plan: StructuredAnalysisPlan,
    dataset_id: uuid.UUID,
    *,
    row_cap: Optional[int] = None,
    use_cache: bool = True,
) -> AnalysisResultResponse:
    cap = row_cap or settings.MAX_RESULT_ROWS
    started = time.perf_counter()
    key = _plan_key(loaded.fingerprint, plan, cap)
    if use_cache:
        with _cache_lock:
            hit = _cache.get(key)
            if hit is not None:
                _cache.move_to_end(key)
        if hit is not None:
            res = AnalysisResultResponse.model_validate(hit)
            res.id = uuid.uuid4()
            res.request_id = None
            res.execution.cache_hit = True
            res.execution.time_ms = round((time.perf_counter() - started) * 1000, 2)
            res.created_at = datetime.now(timezone.utc)
            return res

    # 1) resolve + validate (custom_chart is rewritten to a concrete op first, never silently otherwise)
    run_plan = effective_plan(plan, loaded)
    errors = catalogue.validate_plan(run_plan, loaded)
    if errors:
        raise PlanValidationError(errors)
    spec = catalogue.TOOLS[run_plan.operation]
    advisories = catalogue.plan_warnings(run_plan, loaded)

    # 2) filters, then optional user-requested sampling
    df = loaded.df
    full_rows = int(len(df))
    exclusions: List[ExclusionNote] = []
    fcode = ""
    if run_plan.filters is not None and run_plan.filters.conditions:
        mask = build_mask(df, run_plan.filters, loaded.columns)
        df = df[mask.to_numpy()]
        removed = full_rows - len(df)
        exclusions.append(ExclusionNote(reason=f"excluded by filters ({describe_filters(run_plan.filters)})", count=int(removed)))
        fcode = filter_code(run_plan.filters)
    after_filter = int(len(df))
    sampled = False
    sample_note: Optional[str] = None
    if run_plan.scope == ScopeEnum.SAMPLE and run_plan.sample_size and run_plan.sample_size < len(df):
        df = df.sample(n=run_plan.sample_size, random_state=run_plan.seed)  # keeps original row labels
        sampled = True
        sample_note = f"Computed on a seeded random sample of {run_plan.sample_size:,} of {after_filter:,} rows (seed {run_plan.seed}); results are approximate."
        exclusions.append(ExclusionNote(reason="not sampled", count=int(after_filter - len(df))))
    if len(df) == 0 and run_plan.operation != Op.FILTER_ROWS:  # an empty filter result is a valid answer for filter_rows
        raise AnalysisError("No rows remain after applying the filters, so there is nothing to analyse. Relax or remove a filter.")

    used_cols = [c for c in ([run_plan.column] if run_plan.column else []) + run_plan.target_columns + run_plan.group_by + ([run_plan.date_column] if run_plan.date_column else []) if c]
    if run_plan.missing_policy == MissingPolicyEnum.FAIL_ON_MISSING:
        bad = [c for c in used_cols if df[c].isna().any()]
        if bad:
            raise AnalysisError(f"Missing values were found in {', '.join(bad)} and the missing-value policy is 'fail_on_missing'.")

    # 3) run the approved operation
    ctx = Ctx(plan=run_plan, df=df, loaded=loaded, full_rows=full_rows, row_cap=cap, filter_code=fcode, sampled=sampled)
    try:
        out: OpOutput = spec.fn(ctx)
    except (AnalysisError, PlanValidationError):
        raise
    except (ValueError, KeyError, np.linalg.LinAlgError, TypeError) as e:
        # Numerical/shape problems (e.g. singular matrix) surface as a clear, non-technical error.
        raise AnalysisError(f"This analysis could not be computed on the selected data ({type(e).__name__}: {e}).") from e

    # 4) assemble the structured result
    approx = sampled or out.approximate
    notes = [n for n in (sample_note, out.sampling_note) if n]
    warnings = list(dict.fromkeys(advisories + out.warnings))
    for n in notes:
        if n not in warnings:
            warnings.insert(0, n)
    scope_text = (f"Computed on {after_filter:,} of {full_rows:,} rows after filters" if fcode else f"Computed on all {full_rows:,} rows") + (" (sampled, approximate)." if approx else " (exact, full dataset).")
    methodology = f"{scope_text} {out.methodology}".strip()
    if run_plan.filters is not None and run_plan.filters.conditions:
        methodology += f" Filters applied: {describe_filters(run_plan.filters)}."
    code = _code_header(loaded, used_cols) + ("\n\n# filters\n" + fcode if fcode else "") + "\n\n# analysis\n" + (out.code or "# (see methodology)")
    exclusions.extend(out.exclusions)
    used = out.records_used or len(df)
    res = AnalysisResultResponse(
        dataset_id=dataset_id, dataset_fingerprint=loaded.fingerprint, operation=plan.operation.value,
        columns_used=list(dict.fromkeys(out.columns_used or used_cols)), plan=plan, filters_applied=run_plan.filters,
        records_examined=full_rows, records_used=int(used), records_excluded=max(full_rows - int(used), 0),
        exclusions=[e for e in exclusions if e.count], missing_value_handling=out.missing_value_handling or "Missing values are excluded from calculations and reported.",
        is_sampled=approx, sample_size=int(len(df)) if approx else None,
        sampling_method="seeded simple random sample (without replacement)" if approx else None, is_approximate=approx,
        metrics=jsonable(out.metrics), tables=out.tables, charts=out.charts, warnings=warnings, methodology=methodology,
        summary_text=out.summary or f"{plan.operation.value} completed on {used:,} rows.", interpretation=out.interpretation,
        execution=ExecutionInfo(time_ms=round((time.perf_counter() - started) * 1000, 2), seed=run_plan.seed, cache_hit=False, code=code,
                                library_versions=_versions(), executed_at=datetime.now(timezone.utc).isoformat()),
        created_at=datetime.now(timezone.utc),
    )
    if use_cache:
        with _cache_lock:
            _cache[key] = res.model_dump(mode="json")
            while len(_cache) > max(1, settings.ANALYSIS_CACHE_ENTRIES):
                _cache.popitem(last=False)
    return res
