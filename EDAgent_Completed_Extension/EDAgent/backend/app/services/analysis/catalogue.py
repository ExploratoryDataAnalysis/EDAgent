"""
Approved Analysis Tool Catalogue and plan validation.

This registry is the *only* list of things EDAgent can compute. It is used three ways:
  1. the engine looks up the function to run for a plan's operation;
  2. `validate_plan` checks column names, column types, counts and parameters against it
     before anything executes (so the AI cannot request an unsupported or malformed analysis);
  3. it is rendered into the prompt shown to the language model, so the model can only choose
     from these tools.
There is no code-execution tool: the model supplies data (a plan), never code.
"""

import difflib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.schemas.analysis import AnalysisOperationEnum as Op, FilterGroup, ScopeEnum, StructuredAnalysisPlan
from app.services.analysis import descriptive, hypothesis, modelling, relationships, timeseries
from app.services.analysis.common import Ctx, OpOutput, PlanValidationError
from app.services.analysis.filters import validate_filters
from app.services.data.loader import ColumnInfo, LoadedDataset

AGG_NUMERIC_ONLY = {"sum", "mean", "median", "std"}
AGG_ALL = {"sum", "mean", "median", "count", "min", "max", "std", "nunique"}


@dataclass
class Param:
    name: str
    type: str                      # int | float | bool | str | list | int_or_auto
    description: str = ""
    choices: Optional[List[Any]] = None
    min: Optional[float] = None
    max: Optional[float] = None


@dataclass
class ToolSpec:
    op: Op
    family: str
    description: str
    fn: Callable[[Ctx], OpOutput]
    # column slots: kind is numeric | categorical | datetime | any
    column: Optional[str] = None
    column_required: bool = False
    targets: Optional[Tuple[int, int, str]] = None   # (min, max, kind) for target_columns
    group_by: Optional[Tuple[int, int, str]] = None  # (min, max, kind)
    date_column: bool = False
    needs_filters: bool = False
    params: List[Param] = field(default_factory=list)
    uses_aggregation: bool = False
    uses_interval: bool = False
    uses_bins: bool = False
    uses_top_n: bool = False
    uses_method: Optional[List[str]] = None
    column_role: str = "the primary column"
    cost: str = "light"            # light | modelling (sampled / time-limited)


def _p(*a: Any, **k: Any) -> Param:
    return Param(*a, **k)


ALPHA = _p("alpha", "float", "significance level (default 0.05)", min=0.001, max=0.2)

TOOLS: Dict[Op, ToolSpec] = {t.op: t for t in [
    ToolSpec(Op.DESCRIPTIVE_STATS, "descriptive", "Mean, median, mode, variance, std, min/max, quantiles, skewness, kurtosis for one or more columns (optionally per group).",
             descriptive.descriptive_stats, column="any", targets=(0, 30, "any"), group_by=(0, 2, "categorical")),
    ToolSpec(Op.FREQUENCY, "descriptive", "Frequency table and bar chart of the values of a categorical column.",
             descriptive.frequency, column="any", column_required=True, uses_top_n=True),
    ToolSpec(Op.HISTOGRAM, "distribution", "Histogram of a numeric column with skewness/kurtosis.",
             descriptive.histogram, column="numeric", column_required=True, uses_bins=True),
    ToolSpec(Op.BOXPLOT, "distribution", "Box plot (quartiles, fences, outlier points) of a numeric column, optionally by a category.",
             descriptive.boxplot, column="numeric", column_required=True, group_by=(0, 1, "categorical")),
    ToolSpec(Op.VIOLIN_PLOT, "distribution", "Violin plot of a numeric column, optionally by a category.",
             descriptive.violin_plot, column="numeric", column_required=True, group_by=(0, 1, "categorical")),
    ToolSpec(Op.OUTLIER_IQR, "outliers", "Find outliers with Tukey's IQR fences.",
             descriptive.outlier_iqr, column="numeric", column_required=True, params=[_p("iqr_multiplier", "float", "fence multiplier (default 1.5)", min=0.5, max=5)]),
    ToolSpec(Op.OUTLIER_ZSCORE, "outliers", "Find outliers with Z-scores (or robust modified Z-scores).",
             descriptive.outlier_zscore, column="numeric", column_required=True,
             params=[_p("z_threshold", "float", "|z| threshold (default 3)", min=1, max=6), _p("robust", "bool", "use median/MAD instead of mean/std")]),
    ToolSpec(Op.CORRELATION, "relationships", "Pearson and/or Spearman correlation matrix and ranked pairs between numeric columns (auto-selects suitable columns when none given).",
             relationships.correlation, targets=(0, 30, "numeric"), uses_method=["pearson", "spearman", "both"]),
    ToolSpec(Op.SCATTER_PLOT, "relationships", "Scatter plot of two numeric columns with correlation and trend line.",
             relationships.scatter_plot, targets=(2, 2, "numeric"), params=[_p("color_by", "str", "optional categorical column used to colour points")]),
    ToolSpec(Op.CROSSTAB, "relationships", "Contingency table (counts or percentages) of two categorical columns.",
             relationships.crosstab, targets=(2, 2, "categorical"), params=[_p("normalize", "str", "none|row|column|all", choices=["none", "row", "column", "all"])]),
    ToolSpec(Op.GROUP_BY, "grouping", "Aggregate (sum/mean/median/count/min/max/std/nunique) a column across one to three categorical columns; supports sorting and top-N.",
             relationships.group_by, column="any", group_by=(1, 3, "categorical"), uses_aggregation=True, uses_top_n=True,
             params=[_p("aggregations", "list", "several aggregations at once, e.g. ['mean','count']")]),
    ToolSpec(Op.GROUP_COMPARISON, "grouping", "Compare a numeric measure across the groups of a category (means with 95% CIs plus a suitable test).",
             relationships.group_comparison, column="numeric", column_required=True, group_by=(1, 1, "categorical")),
    ToolSpec(Op.FILTER_ROWS, "grouping", "List the rows matching structured filters (with optional sorting and top-N).",
             relationships.filter_rows, targets=(0, 40, "any"), needs_filters=True, uses_top_n=True),
    ToolSpec(Op.TIME_TREND, "time", "Aggregate a measure (or row counts) over time by day/week/month/quarter/year; supports previous-period / previous-year comparison and seasonality components.",
             timeseries.time_trend, column="numeric", date_column=True, uses_aggregation=True, uses_interval=True,
             params=[_p("compare_with", "str", "none|previous_period|previous_year", choices=["none", "previous_period", "previous_year"]),
                     _p("component", "str", "seasonality: month_of_year|day_of_week|hour_of_day|quarter_of_year", choices=["month_of_year", "day_of_week", "hour_of_day", "quarter_of_year"])]),
    ToolSpec(Op.DATE_DISTRIBUTION, "time", "Distribution of records over time (range, buckets, weekday/hour patterns) for a date column.",
             timeseries.date_distribution, date_column=True, uses_interval=True),
    ToolSpec(Op.CUSTOM_CHART, "charts", "Draw a chart of a given type (bar, line, scatter, histogram, box, heatmap, stacked) from suitable columns.",
             None, params=[_p("chart_type", "str", "bar|line|scatter|histogram|box|heatmap|stacked", choices=["bar", "line", "scatter", "histogram", "box", "heatmap", "stacked"])]),
    ToolSpec(Op.T_TEST_INDEPENDENT, "tests", "Independent-samples (Welch) t-test comparing a numeric column between exactly two groups; reports assumptions and a non-parametric alternative.",
             hypothesis.t_test_independent, column="numeric", column_required=True, group_by=(1, 1, "categorical"),
             params=[ALPHA, _p("groups", "list", "the two group values to compare when the category has more than two"), _p("equal_var", "bool", "assume equal variances (default false = Welch)")]),
    ToolSpec(Op.T_TEST_PAIRED, "tests", "Paired t-test between two numeric columns measured on the same rows.",
             hypothesis.t_test_paired, targets=(2, 2, "numeric"), params=[ALPHA]),
    ToolSpec(Op.ANOVA_ONE_WAY, "tests", "One-way ANOVA of a numeric column across three or more groups, with Tukey post-hoc and assumption checks.",
             hypothesis.anova_one_way, column="numeric", column_required=True, group_by=(1, 1, "categorical"), params=[ALPHA]),
    ToolSpec(Op.CHI_SQUARE, "tests", "Chi-square test of independence between two categorical columns with Cramér's V.",
             hypothesis.chi_square, targets=(2, 2, "categorical"), params=[ALPHA]),
    ToolSpec(Op.MANN_WHITNEY, "tests", "Mann-Whitney U test (non-parametric) comparing a numeric column between two groups.",
             hypothesis.mann_whitney, column="numeric", column_required=True, group_by=(1, 1, "categorical"), params=[ALPHA, _p("groups", "list", "the two group values to compare")]),
    ToolSpec(Op.KRUSKAL_WALLIS, "tests", "Kruskal-Wallis test (non-parametric) of a numeric column across three or more groups.",
             hypothesis.kruskal_wallis, column="numeric", column_required=True, group_by=(1, 1, "categorical"), params=[ALPHA]),
    ToolSpec(Op.WILCOXON, "tests", "Wilcoxon signed-rank test (non-parametric paired test) between two numeric columns.",
             hypothesis.wilcoxon_signed_rank, targets=(2, 2, "numeric"), params=[ALPHA]),
    ToolSpec(Op.KMEANS, "advanced", "K-Means clustering of numeric features (standardised) with cluster summaries and quality metrics.",
             modelling.kmeans, targets=(2, 30, "numeric"), cost="modelling",
             params=[_p("n_clusters", "int_or_auto", "number of clusters 2-12, or 'auto' to choose by silhouette", min=2, max=12)]),
    ToolSpec(Op.PCA, "advanced", "Principal component analysis (explained variance, loadings, 2-D scores) of numeric features.",
             modelling.pca, targets=(0, 50, "numeric"), cost="modelling",
             params=[_p("n_components", "int", "components to keep", min=2, max=50), _p("standardize", "bool", "scale features first (default true)"), _p("color_by", "str", "categorical column to colour the score plot")]),
    ToolSpec(Op.LINEAR_REGRESSION, "advanced", "Linear / multiple linear regression of a numeric target on numeric or categorical predictors with coefficients, R² and residual diagnostics.",
             modelling.linear_regression, column="numeric", column_required=True, column_role="the numeric target", targets=(1, 30, "any"), cost="modelling"),
    ToolSpec(Op.CLASSIFICATION, "advanced", "Classification of a categorical target with a baseline model, train/test split, confusion matrix, precision/recall/F1 and ROC-AUC.",
             modelling.classification, column="any", column_required=True, column_role="the categorical target", targets=(0, 30, "any"), cost="modelling",
             params=[_p("model", "str", "logistic_regression|random_forest|decision_tree", choices=["logistic_regression", "random_forest", "decision_tree"]),
                     _p("test_size", "float", "test fraction 0.1-0.5", min=0.1, max=0.5), _p("class_weight", "str", "'balanced' to counter imbalance", choices=["balanced", "none"]),
                     _p("impute", "str", "none (drop incomplete rows) | median_mode (impute inside the training pipeline)", choices=["none", "median_mode"])]),
]}


# ---------------------------------------------------------------------------- validation helpers

def _kind_ok(info: ColumnInfo, wanted: str) -> bool:
    if wanted == "any":
        return True
    if wanted == "numeric":
        return info.is_numeric
    if wanted == "datetime":
        return info.kind == "datetime"
    if wanted == "categorical":
        # strings/booleans, or numeric columns that behave like codes/ratings (role category or few distinct values)
        return info.kind in ("string", "boolean") or (info.is_numeric and (info.role == "category" or info.distinct_count <= 20))
    return True


def _kind_phrase(wanted: str) -> str:
    return {"numeric": "numeric", "categorical": "categorical", "datetime": "date/time", "any": "any"}[wanted]


def _suggest(name: str, columns: Dict[str, ColumnInfo]) -> str:
    close = difflib.get_close_matches(name, list(columns), n=3, cutoff=0.5)
    lower = [c for c in columns if c.lower() == name.lower()]
    close = lower + [c for c in close if c not in lower]
    return f" Did you mean: {', '.join(repr(c) for c in close[:3])}?" if close else ""


def _check_param(spec_p: Param, value: Any) -> Optional[str]:
    n = spec_p.name
    t = spec_p.type
    try:
        if t == "bool":
            if not isinstance(value, bool):
                return f"Parameter '{n}' must be true or false."
        elif t in ("int", "float"):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return f"Parameter '{n}' must be a number."
            if t == "int" and int(value) != value:
                return f"Parameter '{n}' must be a whole number."
            if spec_p.min is not None and value < spec_p.min or spec_p.max is not None and value > spec_p.max:
                return f"Parameter '{n}' must be between {spec_p.min} and {spec_p.max}."
        elif t == "int_or_auto":
            if value != "auto":
                if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
                    return f"Parameter '{n}' must be a whole number or 'auto'."
                if value < (spec_p.min or 0) or value > (spec_p.max or 1e9):
                    return f"Parameter '{n}' must be between {spec_p.min:g} and {spec_p.max:g}."
        elif t == "str":
            if not isinstance(value, str):
                return f"Parameter '{n}' must be text."
            if spec_p.choices and value not in spec_p.choices:
                return f"Parameter '{n}' must be one of: {', '.join(map(str, spec_p.choices))}."
        elif t == "list":
            if not isinstance(value, list) or len(value) > 50:
                return f"Parameter '{n}' must be a list of at most 50 items."
    except TypeError:
        return f"Parameter '{n}' has an invalid value."
    return None


def validate_plan(plan: StructuredAnalysisPlan, loaded: LoadedDataset) -> List[str]:
    """Returns a list of human-readable problems (empty = valid). Never mutates the plan."""
    spec = TOOLS.get(plan.operation)
    if spec is None:
        return [f"Operation '{plan.operation}' is not in the approved tool catalogue."]
    cols = loaded.columns
    errors: List[str] = []

    def need(name: Optional[str], role: str, wanted: str) -> None:
        if name is None:
            return
        info = cols.get(name)
        if info is None:
            errors.append(f"Column '{name}' (used as {role}) does not exist in this dataset.{_suggest(name, cols)}")
        elif not _kind_ok(info, wanted):
            errors.append(f"Column '{name}' (used as {role}) is {info.kind} ({info.role}), but this analysis needs a {_kind_phrase(wanted)} column.")

    # primary column
    if spec.column is None and plan.column:
        errors.append(f"'{spec.op.value}' does not take a single 'column'; use target_columns/group_by as described in the catalogue.")
    elif spec.column is not None:
        if spec.column_required and not plan.column:
            errors.append(f"'{spec.op.value}' needs {spec.column_role} (field 'column').")
        need(plan.column, spec.column_role, spec.column)

    # target columns
    if spec.targets is None:
        if plan.target_columns:
            errors.append(f"'{spec.op.value}' does not use target_columns.")
    else:
        lo, hi, kind = spec.targets
        n = len(plan.target_columns)
        if len(set(plan.target_columns)) != n:
            errors.append("target_columns contains duplicates.")
        if n and (n < lo or n > hi) or (n == 0 and lo > 0 and not (spec.op in (Op.CORRELATION, Op.PCA))):
            errors.append(f"'{spec.op.value}' needs {lo if lo == hi else f'{lo}-{hi}'} column(s) in target_columns (got {n}).")
        for c in plan.target_columns:
            need(c, "a target column", kind)
        if spec.op in (Op.CORRELATION, Op.PCA) and 0 < n < 2:
            errors.append(f"'{spec.op.value}' needs at least 2 columns (or none, to auto-select).")

    # group_by
    if spec.group_by is None:
        if plan.group_by:
            errors.append(f"'{spec.op.value}' does not use group_by.")
    else:
        lo, hi, kind = spec.group_by
        n = len(plan.group_by)
        if n < lo or n > hi:
            errors.append(f"'{spec.op.value}' needs {lo if lo == hi else f'{lo}-{hi}'} grouping column(s) in group_by (got {n}).")
        if len(set(plan.group_by)) != n:
            errors.append("group_by contains duplicates.")
        for c in plan.group_by:
            need(c, "a grouping column", kind)
            if plan.column and c == plan.column:
                errors.append(f"'{c}' cannot be both the measured column and a grouping column.")

    # date column
    if spec.date_column:
        if not plan.date_column:
            errors.append(f"'{spec.op.value}' needs a date column (field 'date_column').")
        need(plan.date_column, "the date column", "datetime")
    elif plan.date_column:
        errors.append(f"'{spec.op.value}' does not use date_column.")

    # filters
    if spec.needs_filters and (plan.filters is None or not plan.filters.conditions):
        errors.append("'filter_rows' needs at least one filter condition.")
    if plan.filters is not None:
        errors += validate_filters(plan.filters, cols)

    # aggregation
    if spec.uses_aggregation:
        if plan.aggregation not in AGG_ALL:
            errors.append(f"Aggregation '{plan.aggregation}' is not supported. Use one of: {', '.join(sorted(AGG_ALL))}.")
        aggs = plan.parameters.get("aggregations") or [plan.aggregation]
        for a in aggs:
            if a not in AGG_ALL:
                errors.append(f"Aggregation '{a}' is not supported.")
            elif a in AGG_NUMERIC_ONLY and plan.column and plan.column in cols and not cols[plan.column].is_numeric:
                errors.append(f"Aggregation '{a}' needs a numeric column, but '{plan.column}' is {cols[plan.column].kind}.")
        if spec.op == Op.GROUP_BY and not plan.column and any(a != "count" for a in aggs):
            errors.append("group_by without a value column can only count rows (aggregation 'count').")
    if spec.uses_method is not None and plan.method and plan.method not in spec.uses_method:
        errors.append(f"method must be one of: {', '.join(spec.uses_method)}.")

    # sort
    if plan.sort_by and plan.sort_by not in cols and spec.op == Op.FILTER_ROWS:
        errors.append(f"sort_by column '{plan.sort_by}' does not exist.{_suggest(plan.sort_by, cols)}")

    # parameters: whitelist + types
    allowed = {p.name: p for p in spec.params}
    for k, v in plan.parameters.items():
        if k == "aggregations" and spec.uses_aggregation:
            continue
        if k not in allowed:
            errors.append(f"Unknown parameter '{k}' for '{spec.op.value}'. Allowed: {', '.join(allowed) or 'none'}.")
            continue
        msg = _check_param(allowed[k], v)
        if msg:
            errors.append(msg)
    for pk in ("color_by",):
        v = plan.parameters.get(pk)
        if isinstance(v, str) and v not in cols:
            errors.append(f"Column '{v}' (parameter {pk}) does not exist.{_suggest(v, cols)}")

    if plan.scope == ScopeEnum.SAMPLE and not plan.sample_size:
        errors.append("scope 'sample' needs a sample_size.")
    return errors


def plan_warnings(plan: StructuredAnalysisPlan, loaded: LoadedDataset) -> List[str]:
    """Non-blocking advisories (e.g. identifier columns used in numeric analysis)."""
    out: List[str] = []
    spec = TOOLS.get(plan.operation)
    used = ([plan.column] if plan.column else []) + list(plan.target_columns)
    for c in used:
        info = loaded.columns.get(c)
        if info and info.is_numeric and info.role == "identifier" and spec and spec.op not in (Op.FREQUENCY, Op.FILTER_ROWS):
            out.append(f"'{c}' looks like an identifier; numeric statistics on identifiers are usually meaningless.")
        elif info and info.is_numeric and info.role == "category" and spec and spec.op in (Op.DESCRIPTIVE_STATS, Op.HISTOGRAM, Op.CORRELATION, Op.PCA, Op.KMEANS, Op.LINEAR_REGRESSION):
            out.append(f"'{c}' looks like an encoded category (codes), so treating it as a continuous measurement may be misleading.")
    return out


# ---------------------------------------------------------------------------- custom_chart dispatch

_CHART_MAP = {"bar": Op.GROUP_BY, "line": Op.TIME_TREND, "scatter": Op.SCATTER_PLOT, "histogram": Op.HISTOGRAM, "box": Op.BOXPLOT, "stacked": Op.CROSSTAB}


def resolve_custom_chart(plan: StructuredAnalysisPlan, loaded: LoadedDataset) -> StructuredAnalysisPlan:
    """Translates the generic `custom_chart` request into the concrete operation that draws it."""
    ct = plan.parameters.get("chart_type") or plan.chart_type
    if ct not in ("bar", "line", "scatter", "histogram", "box", "heatmap", "stacked"):
        raise PlanValidationError(["custom_chart needs parameters.chart_type: bar, line, scatter, histogram, box, heatmap or stacked."])
    params = {k: v for k, v in plan.parameters.items() if k != "chart_type"}
    if ct == "heatmap":
        # correlation heatmap for numeric columns, otherwise a counts heatmap of two categories
        if plan.target_columns and all(loaded.columns.get(c) and loaded.columns[c].is_numeric for c in plan.target_columns) or not plan.target_columns:
            return plan.model_copy(update={"operation": Op.CORRELATION, "parameters": {}})
        return plan.model_copy(update={"operation": Op.CROSSTAB, "parameters": params})
    if ct == "bar" and not plan.group_by and plan.column:
        return plan.model_copy(update={"operation": Op.FREQUENCY, "parameters": {}})
    return plan.model_copy(update={"operation": _CHART_MAP[ct], "parameters": params})


def catalogue_for_prompt() -> str:
    """Compact, model-readable description of every approved tool and its fields."""
    lines: List[str] = []
    for op, s in TOOLS.items():
        slots: List[str] = []
        if s.column:
            slots.append(f"column ({s.column}{', required' if s.column_required else ', optional'}; {s.column_role})")
        if s.targets:
            slots.append(f"target_columns ({s.targets[2]}, {s.targets[0]}-{s.targets[1]})")
        if s.group_by:
            slots.append(f"group_by ({s.group_by[2]}, {s.group_by[0]}-{s.group_by[1]})")
        if s.date_column:
            slots.append("date_column (date, required)")
        if s.uses_aggregation:
            slots.append("aggregation (sum|mean|median|count|min|max|std|nunique)")
        if s.uses_interval:
            slots.append("interval (day|week|month|quarter|year)")
        if s.uses_bins:
            slots.append("bins (int)")
        if s.uses_top_n:
            slots.append("top_n (int), sort_by, sort_order")
        if s.uses_method:
            slots.append("method (" + "|".join(s.uses_method) + ")")
        if s.needs_filters:
            slots.append("filters (required)")
        for p in s.params:
            slots.append(f"parameters.{p.name} ({p.type}{': ' + p.description if p.description else ''})")
        lines.append(f"- {op.value}: {s.description} Fields: {'; '.join(slots) or 'none'}.")
    return "\n".join(lines)


def catalogue_for_api() -> List[Dict[str, Any]]:
    """JSON-friendly description of every tool, used by the workspace's analysis builder."""
    out: List[Dict[str, Any]] = []
    for op, s in TOOLS.items():
        out.append({
            "operation": op.value,
            "family": s.family,
            "description": s.description,
            "column": {"kind": s.column, "required": s.column_required, "label": s.column_role} if s.column else None,
            "target_columns": {"min": s.targets[0], "max": s.targets[1], "kind": s.targets[2]} if s.targets else None,
            "group_by": {"min": s.group_by[0], "max": s.group_by[1], "kind": s.group_by[2]} if s.group_by else None,
            "date_column": s.date_column,
            "needs_filters": s.needs_filters,
            "uses_aggregation": s.uses_aggregation,
            "uses_interval": s.uses_interval,
            "uses_bins": s.uses_bins,
            "uses_top_n": s.uses_top_n,
            "methods": s.uses_method,
            "cost": s.cost,
            "parameters": [{"name": p.name, "type": p.type, "description": p.description, "choices": p.choices, "min": p.min, "max": p.max} for p in s.params],
        })
    return out
