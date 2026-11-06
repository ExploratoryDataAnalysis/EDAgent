"""
Suggested analyses, derived from the profile (no AI needed).

Each suggestion is a ready-to-run structured plan plus a plain-language title, so the
workspace can offer one-click analyses that depend on what the data actually contains.
"""

from typing import Any, Dict, List

from app.schemas.analysis import AnalysisOperationEnum as Op


def _plan(op: Op, **kw: Any) -> Dict[str, Any]:
    return {"operation": op.value, **kw}


def suggest_analyses(profile: Dict[str, Any], limit: int = 12) -> List[Dict[str, Any]]:
    cols = profile.get("columns", [])
    measures = [c["name"] for c in cols if c.get("semantic_role") == "measure"]
    cats = [c["name"] for c in cols if c.get("semantic_role") == "category" and 2 <= c.get("distinct_count", 0) <= 20]
    dates = [c["name"] for c in cols if c.get("semantic_role") == "datetime"]
    out: List[Dict[str, Any]] = []

    def add(title: str, why: str, plan: Dict[str, Any], family: str) -> None:
        out.append({"title": title, "description": why, "family": family, "plan": plan})

    if measures:
        add("Summary statistics", f"Mean, spread and shape for {len(measures)} numeric column(s).", _plan(Op.DESCRIPTIVE_STATS, target_columns=measures[:10]), "descriptive")
        m = measures[0]
        add(f"Distribution of {m}", "See the shape, skew and typical range.", _plan(Op.HISTOGRAM, column=m), "distribution")
        add(f"Outliers in {m}", "Rows far from the rest using the IQR rule (nothing is removed).", _plan(Op.OUTLIER_IQR, column=m), "outliers")
    if len(measures) >= 2:
        add("Correlations between numeric columns", "Which measures move together (Pearson).", _plan(Op.CORRELATION, target_columns=measures[:12], method="pearson"), "relationships")
        add(f"{measures[1]} vs {measures[0]}", "Scatter plot with trend line.", _plan(Op.SCATTER_PLOT, target_columns=[measures[0], measures[1]]), "relationships")
    if measures and cats:
        add(f"Average {measures[0]} by {cats[0]}", "Compare groups side by side.", _plan(Op.GROUP_BY, column=measures[0], group_by=[cats[0]], aggregation="mean"), "grouping")
        add(f"Does {measures[0]} differ across {cats[0]}?", "Hypothesis test with assumption checks.", _plan(Op.GROUP_COMPARISON, column=measures[0], group_by=[cats[0]]), "grouping")
    if cats:
        add(f"Frequency of {cats[0]}", "Counts and shares per category.", _plan(Op.FREQUENCY, column=cats[0]), "descriptive")
    if len(cats) >= 2:
        add(f"{cats[0]} by {cats[1]}", "Cross-tabulation of two categories.", _plan(Op.CROSSTAB, target_columns=[cats[0], cats[1]]), "relationships")
    if dates and measures:
        add(f"{measures[0]} over time", "Monthly trend.", _plan(Op.TIME_TREND, column=measures[0], date_column=dates[0], aggregation="sum", interval="month"), "time")
    if len(measures) >= 3:
        add("Find natural clusters", "K-Means on standardised numeric columns.", _plan(Op.KMEANS, target_columns=measures[:6]), "advanced")
        add("Principal components", "Reduce numeric columns to the directions of most variance.", _plan(Op.PCA, target_columns=measures[:8]), "advanced")
    return out[:limit]
