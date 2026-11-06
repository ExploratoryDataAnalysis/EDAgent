"""
Shared building blocks for every analysis operation.

An operation is a plain function `fn(ctx) -> OpOutput`. The engine (engine.py) is the only
place that validates a plan, applies filters/sampling, times the call and assembles the
final structured result, so individual operations stay small and focused on the statistics.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.core.config import settings
from app.schemas.analysis import ExclusionNote, ResultChart, ResultTable, StructuredAnalysisPlan
from app.services.data.loader import ColumnInfo, LoadedDataset


class AnalysisError(Exception):
    """A user-facing problem: the request is valid but cannot be computed on this data
    (e.g. fewer than 2 groups). The message is shown to the user verbatim."""

    def __init__(self, message: str, code: str = "ANALYSIS_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class PlanValidationError(Exception):
    """The plan itself is invalid (unknown column, unsuitable type, bad parameter)."""

    def __init__(self, errors: List[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def jsonable(obj: Any) -> Any:
    """Recursively converts numpy/pandas values to plain JSON types. NaN/inf become None so
    results never contain non-standard JSON tokens."""
    if obj is None:
        return None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return None if pd.isna(obj) else obj.isoformat()
    if isinstance(obj, (np.datetime64,)):
        return None if np.isnat(obj) else str(pd.Timestamp(obj).isoformat())
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [jsonable(v) for v in obj.tolist()]
    if obj is pd.NaT:
        return None
    if isinstance(obj, (str, int)):
        return obj
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


@dataclass
class Ctx:
    """Everything an operation needs. `df` is the already-filtered, possibly sampled frame
    (a view the operation must not mutate); `full_rows` counts rows before filtering."""
    plan: StructuredAnalysisPlan
    df: pd.DataFrame
    loaded: LoadedDataset
    full_rows: int
    row_cap: int = settings.MAX_RESULT_ROWS
    filter_code: str = ""
    # filled in by the engine when it samples before running the op
    sampled: bool = False

    @property
    def columns(self) -> Dict[str, ColumnInfo]:
        return self.loaded.columns

    def info(self, name: str) -> ColumnInfo:
        return self.loaded.columns[name]

    def param(self, key: str, default: Any = None) -> Any:
        return self.plan.parameters.get(key, default)


@dataclass
class OpOutput:
    """What an operation returns; the engine turns this into the public result schema."""
    columns_used: List[str] = field(default_factory=list)
    records_used: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)
    tables: List[ResultTable] = field(default_factory=list)
    charts: List[ResultChart] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    exclusions: List[ExclusionNote] = field(default_factory=list)
    methodology: str = ""
    summary: str = ""
    interpretation: Optional[str] = None
    code: str = ""
    missing_value_handling: str = ""
    approximate: bool = False
    sampling_note: Optional[str] = None


def make_table(name: str, df: pd.DataFrame, row_cap: int, round_to: int = 6) -> ResultTable:
    """Turns a DataFrame into a size-limited JSON table (never returns unbounded rows)."""
    total = int(len(df))
    shown = df.head(row_cap)
    rows = [jsonable({c: _round(v, round_to) for c, v in rec.items()}) for rec in shown.to_dict(orient="records")]
    return ResultTable(name=name, columns=[str(c) for c in df.columns], rows=rows, total_rows=total, truncated=total > row_cap)


def table_from_rows(name: str, columns: List[str], rows: List[Dict[str, Any]], row_cap: int) -> ResultTable:
    total = len(rows)
    return ResultTable(
        name=name, columns=columns,
        rows=[jsonable({c: _round(r.get(c)) for c in columns}) for r in rows[:row_cap]],
        total_rows=total, truncated=total > row_cap,
    )


def _round(v: Any, digits: int = 6) -> Any:
    if isinstance(v, (float, np.floating)) and not (math.isnan(float(v)) or math.isinf(float(v))):
        return round(float(v), digits)
    return v


def fmt(x: Any, digits: int = 4) -> str:
    """Compact number formatting for the deterministic summary sentences."""
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "n/a"
    if isinstance(x, (int, np.integer)):
        return f"{int(x):,}"
    x = float(x)
    if x != 0 and (abs(x) >= 1e7 or abs(x) < 1e-3):
        return f"{x:.{digits}g}"
    return f"{x:,.{digits}f}".rstrip("0").rstrip(".") if "." in f"{x:.{digits}f}" else f"{x:,.0f}"


def fmt_p(p: Optional[float]) -> str:
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "n/a"
    return "< 0.0001" if p < 1e-4 else f"{p:.4f}"


def numeric_series(ctx: Ctx, col: str) -> pd.Series:
    """Column as float with missing dropped. Validation guarantees the column is numeric."""
    return ctx.df[col].astype(float).dropna()


def missing_note(ctx: Ctx, cols: List[str], used_rows: int) -> List[ExclusionNote]:
    """Per-column count of rows lost to missing values within the (already filtered) frame."""
    notes: List[ExclusionNote] = []
    for c in cols:
        n = int(ctx.df[c].isna().sum())
        if n:
            notes.append(ExclusionNote(reason="missing value", count=n, column=c))
    return notes


def coerce_warnings(ctx: Ctx, cols: List[str]) -> List[str]:
    """Warns when a used column had cells that could not be converted at load time."""
    out: List[str] = []
    for c in cols:
        info = ctx.columns.get(c)
        if not info:
            continue
        if info.unparseable_count:
            kind = {"numeric": "numbers", "datetime": "dates", "boolean": "booleans"}.get(info.kind, "values")
            out.append(f"Column '{c}': {info.unparseable_count} cell(s) could not be read as {kind} and were treated as missing.")
        if info.infinite_count:
            out.append(f"Column '{c}': {info.infinite_count} infinite value(s) were treated as missing.")
    return out


def small_group_warning(counts: pd.Series, threshold: int = 5) -> Optional[str]:
    small = counts[counts < threshold]
    if len(small):
        return f"{len(small)} group(s) have fewer than {threshold} observations, so their statistics are unreliable."
    return None


def strength_label(r: float) -> str:
    a = abs(r)
    if a >= 0.8:
        return "very strong"
    if a >= 0.6:
        return "strong"
    if a >= 0.4:
        return "moderate"
    if a >= 0.2:
        return "weak"
    return "very weak / none"


def limit_categories(series: pd.Series, top: int) -> pd.Series:
    """Keeps the `top` most frequent categories and folds the rest into 'Other'."""
    vc = series.value_counts()
    if len(vc) <= top:
        return series
    keep = set(vc.index[:top])
    return series.where(series.isin(keep), "Other")
