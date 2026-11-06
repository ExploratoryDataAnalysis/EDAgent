"""
Keeps AI prose honest.

* `result_facts` renders a computed result as compact text for the explainer prompt.
* `ungrounded_numbers` finds numbers in model prose that do not appear in the result
  (so an invented figure is caught and the deterministic explanation is used instead).
* `template_explanation` is the no-AI fallback built purely from computed values.
"""

import json
import math
import re
from typing import Any, Iterable, List, Set

from app.schemas.analysis import AnalysisResultResponse

_NUM = re.compile(r"(?<![\w.])[-+]?\d[\d,]*\.?\d*(?:e[-+]?\d+)?%?", re.I)
MAX_TABLE_ROWS_IN_PROMPT = 12


def _walk_numbers(obj: Any, out: Set[float]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        if math.isfinite(obj):
            out.add(float(obj))
    elif isinstance(obj, str):
        for m in _NUM.findall(obj):
            try:
                out.add(float(m.replace(",", "").rstrip("%")))
            except ValueError:
                pass
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_numbers(v, out)


def _facts_payload(result: AnalysisResultResponse) -> dict:
    tables = []
    for t in result.tables:
        tables.append({"name": t.name, "columns": t.columns, "rows": t.rows[:MAX_TABLE_ROWS_IN_PROMPT], "total_rows": t.total_rows})
    return {
        "operation": result.operation,
        "columns_used": result.columns_used,
        "rows_in_dataset": result.records_examined,
        "rows_used": result.records_used,
        "rows_excluded": result.records_excluded,
        "exclusions": [e.model_dump() for e in result.exclusions],
        "exact_or_sampled": "sampled (approximate)" if result.is_approximate else "exact (full dataset)",
        "metrics": result.metrics,
        "tables": tables,
        "summary": result.summary_text,
        "interpretation": result.interpretation,
        "warnings": result.warnings,
        "methodology": result.methodology,
    }


def result_facts(result: AnalysisResultResponse, max_chars: int = 9000) -> str:
    text = json.dumps(_facts_payload(result), default=str, ensure_ascii=False)
    return text if len(text) <= max_chars else text[:max_chars] + " ...[truncated]"


def known_numbers(result: AnalysisResultResponse) -> Set[float]:
    """Every number legitimately available to the explainer (including the full tables)."""
    nums: Set[float] = set()
    _walk_numbers(_facts_payload(result), nums)
    for t in result.tables:
        _walk_numbers(t.rows, nums)
    return nums


def _decimals(token: str) -> int:
    t = token.rstrip("%").replace(",", "")
    return len(t.split(".")[1]) if "." in t and "e" not in t.lower() else 0


def ungrounded_numbers(text: str, result: AnalysisResultResponse) -> List[str]:
    """Numbers written in `text` that cannot be matched to the result (allowing rounding and x100 for rates)."""
    known = known_numbers(result)
    bad: List[str] = []
    for tok in _NUM.findall(text):
        try:
            val = float(tok.replace(",", "").rstrip("%"))
        except ValueError:
            continue
        # List numbering / tiny counts ("two groups", "3 columns") are not claims about the data.
        if abs(val) <= 10 and float(val).is_integer():
            continue
        # Calendar years are descriptive labels rather than computed values.
        if float(val).is_integer() and 1900 <= val <= 2100:
            continue
        d = _decimals(tok)
        ok = False
        for k in known:
            for cand in (k, k * 100, -k, abs(k)):
                if round(cand, d) == round(val, d) or math.isclose(cand, val, rel_tol=2e-3, abs_tol=10 ** -(d + 1)):
                    ok = True
                    break
            if ok:
                break
        if not ok:
            bad.append(tok)
    return bad


def template_explanation(result: AnalysisResultResponse) -> str:
    """Deterministic plain-language summary assembled only from computed fields."""
    parts: List[str] = [result.summary_text.strip()]
    if result.interpretation:
        parts.append(result.interpretation.strip())
    scope = "approximate (computed on a sample)" if result.is_approximate else "exact (computed on all included rows)"
    parts.append(f"The result is {scope}, using {result.records_used:,} of {result.records_examined:,} rows.")
    if result.warnings:
        parts.append("Please note: " + " ".join(w.strip() for w in result.warnings[:4]))
    return " ".join(p for p in parts if p)


def suggested_followups(result: AnalysisResultResponse) -> List[str]:
    """Short, deterministic next questions based on what was just computed."""
    op = result.operation
    cols = result.columns_used
    first = cols[0] if cols else None
    out: List[str] = []
    if op in ("descriptive_stats", "histogram") and first:
        out += [f"Are there outliers in {first}?", f"Show the boxplot of {first}"]
    elif op in ("group_by", "group_comparison") and len(cols) >= 2:
        out += [f"Is the difference in {cols[0]} between {cols[-1]} groups statistically significant?", "Show only the top 5 groups"]
    elif op == "correlation":
        out += ["Show a scatter plot for the strongest pair", "Use Spearman instead of Pearson"]
    elif op in ("outlier_iqr", "outlier_zscore") and first:
        out += [f"Show the distribution of {first}", "Compare with the Z-score method" if op == "outlier_iqr" else "Compare with the IQR method"]
    elif op == "time_trend":
        out += ["Now compare it with the previous year", "Show the same trend by quarter"]
    else:
        out += ["Which columns have the most missing values?", "Which variables are most strongly correlated?"]
    return out[:3]


def iter_text(*parts: Iterable[str]) -> str:
    return " ".join(p for ps in parts for p in ps)
