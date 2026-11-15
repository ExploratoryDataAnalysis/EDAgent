"""Render explanations and follow-ups solely from the computed result."""

import json
from typing import List

from app.schemas.analysis import AnalysisResultResponse


def result_facts(result: AnalysisResultResponse) -> str:
    # The provider only chooses emphasis, so it doesn't need result tables, cell values
    # or dataset labels. The ID ties that choice to this specific computation.
    return json.dumps({
        "result_id": str(result.id),
        "operation": result.operation,
        "approximate": result.is_approximate,
        "rows_used": result.records_used,
        "rows_examined": result.records_examined,
    })


def template_explanation(result: AnalysisResultResponse, *, scope_first: bool = False) -> str:
    """Deterministic plain-language summary assembled only from computed fields."""
    parts: List[str] = [result.summary_text.strip()]
    if result.interpretation:
        parts.append(result.interpretation.strip())
    scope = "approximate (computed on a sample)" if result.is_approximate else "exact (computed on all included rows)"
    scope_text = f"The result is {scope}, using {result.records_used:,} of {result.records_examined:,} rows."
    if scope_first:
        parts.insert(0, scope_text)
    else:
        parts.append(scope_text)
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
