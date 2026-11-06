"""
Relationship, grouping and row-selection operations: correlation, scatter, crosstab,
group_by, group_comparison and filter_rows.
"""

from itertools import combinations
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from scipy import stats

from app.schemas.analysis import ExclusionNote
from app.services.analysis import charts
from app.services.analysis.common import (
    AnalysisError, Ctx, OpOutput, coerce_warnings, fmt, fmt_p, limit_categories, make_table, missing_note,
    small_group_warning, strength_label, table_from_rows,
)

AGGS = {"sum": "sum", "mean": "mean", "median": "median", "count": "count", "min": "min", "max": "max", "std": "std", "nunique": "nunique"}


# --------------------------------------------------------------------------- correlation

def correlation(ctx: Ctx) -> OpOutput:
    p = ctx.plan
    explicit = bool(p.target_columns)
    cols = list(p.target_columns) if explicit else ctx.loaded.numeric_columns()
    out = OpOutput(columns_used=cols)
    if len(cols) < 2:
        raise AnalysisError("Correlation needs at least two suitable numeric columns. Identifier columns and numeric codes are excluded unless you choose them explicitly.")
    if len(cols) > 30:
        raise AnalysisError(f"Correlation is limited to 30 columns at a time (got {len(cols)}). Please select a subset.")
    if not explicit:
        excluded = [c for c, i in ctx.columns.items() if i.is_numeric and c not in cols]
        out.warnings.append("Columns were chosen automatically from numeric measures." + (
            f" Excluded as identifiers/encoded categories: {', '.join(excluded)}." if excluded else ""))
    else:
        for c in cols:
            if ctx.info(c).role in ("identifier", "category"):
                out.warnings.append(f"'{c}' looks like an {ctx.info(c).role} rather than a measurement; its correlation may not be meaningful.")

    method = (p.method or "pearson").lower()
    methods = ["pearson", "spearman"] if method == "both" else [method]
    d = ctx.df[cols].astype(float)
    const = [c for c in cols if d[c].nunique(dropna=True) < 2]
    if const:
        out.warnings.append(f"Constant/empty column(s) have no defined correlation: {', '.join(const)}.")
    out.warnings += coerce_warnings(ctx, cols)

    pair_rows: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {}
    for m in methods:
        mat = d.corr(method=m)
        metrics[m] = {"matrix": mat.where(mat.notna(), None).round(6).to_dict()}
        out.tables.append(make_table(f"{m}_matrix", mat.round(4).reset_index().rename(columns={"index": "column"}), ctx.row_cap))
        out.charts.append(charts.heatmap(f"{m}_heatmap", f"{m.title()} correlation", mat.where(mat.notna(), None).values.tolist(), cols, cols, -1, 1))
        for a, b in combinations(cols, 2):
            pair = d[[a, b]].dropna()
            n = len(pair)
            r, pv = (np.nan, np.nan)
            if n >= 3 and pair[a].nunique() > 1 and pair[b].nunique() > 1:
                r, pv = (stats.pearsonr(pair[a], pair[b]) if m == "pearson" else stats.spearmanr(pair[a], pair[b]))
            pair_rows.append({"method": m, "column_x": a, "column_y": b, "r": float(r), "p_value": float(pv), "n": n,
                              "strength": strength_label(r) if not np.isnan(r) else "undefined"})
    pair_rows.sort(key=lambda r: -abs(r["r"]) if not np.isnan(r["r"]) else 0)
    out.tables.insert(0, table_from_rows("pairs", ["method", "column_x", "column_y", "r", "p_value", "n", "strength"], pair_rows, ctx.row_cap))
    metrics["pairs"] = len(pair_rows)
    out.metrics = metrics
    out.records_used = int(d.dropna(how="all").shape[0])
    out.exclusions = missing_note(ctx, cols, out.records_used)
    best = next((r for r in pair_rows if not np.isnan(r["r"])), None)
    if best:
        out.summary = (f"Strongest {best['method']} association: '{best['column_x']}' and '{best['column_y']}' "
                       f"(r = {best['r']:.3f}, {best['strength']}, n = {best['n']}, p {('= ' + fmt_p(best['p_value'])) if best['p_value'] >= 1e-4 else fmt_p(best['p_value'])}).")
    else:
        out.summary = "No computable correlations for the selected columns."
    if len(pair_rows) > 20:
        out.warnings.append(f"{len(pair_rows)} pairs were tested; with many comparisons some p-values will be small by chance. Treat these as exploratory.")
    out.warnings.append("Correlation measures association, not causation. Pearson captures linear relationships only; Spearman captures monotonic ones.")
    out.methodology = (f"{', '.join(m.title() for m in methods)} correlation using pairwise-complete observations (each pair uses rows where both values exist; n is shown per pair). "
                       "p-values test H0: no correlation (two-sided), without multiple-comparison correction.")
    out.missing_value_handling = "Pairwise deletion: a row is dropped only from the pairs in which one of its two values is missing."
    out.code = "\n".join(f"corr_{m} = df[{cols!r}].astype(float).corr(method={m!r})" for m in methods)
    return out


def scatter_plot(ctx: Ctx) -> OpOutput:
    p = ctx.plan
    x, y = p.target_columns[0], p.target_columns[1]
    color_by = ctx.param("color_by")
    cols = [x, y] + ([color_by] if color_by else [])
    d = ctx.df[cols].dropna()
    n = len(d)
    if n < 3:
        raise AnalysisError(f"Only {n} complete observation(s) of '{x}' and '{y}'; at least 3 are needed.")
    xv, yv = d[x].astype(float), d[y].astype(float)
    out = OpOutput(columns_used=cols, records_used=n)
    r = rho = np.nan
    slope = intercept = r2 = np.nan
    if xv.nunique() > 1 and yv.nunique() > 1:
        r, pr = stats.pearsonr(xv, yv)
        rho, ps = stats.spearmanr(xv, yv)
        lr = stats.linregress(xv, yv)
        slope, intercept, r2 = float(lr.slope), float(lr.intercept), float(lr.rvalue ** 2)
    else:
        pr = ps = np.nan
        out.warnings.append("One of the variables is constant, so correlation and trend line are undefined.")
    out.metrics = {"n": n, "pearson_r": float(r), "pearson_p": float(pr), "spearman_rho": float(rho), "spearman_p": float(ps),
                   "slope": slope, "intercept": intercept, "r_squared": r2}
    # Drawing is limited to 5,000 points (seeded sample) so very large datasets stay responsive.
    draw = d if n <= 5000 else d.sample(5000, random_state=p.seed)
    groups: List[Dict[str, Any]] = []
    if color_by:
        top = d[color_by].astype(str).value_counts().index[:10]
        for g in top:
            sub = draw[draw[color_by].astype(str) == g]
            groups.append({"name": str(g), "x": sub[x].astype(float).tolist(), "y": sub[y].astype(float).tolist()})
        if d[color_by].nunique() > 10:
            out.warnings.append(f"'{color_by}' has {d[color_by].nunique()} values; only the 10 most frequent are coloured.")
    else:
        groups.append({"name": "observations", "x": draw[x].astype(float).tolist(), "y": draw[y].astype(float).tolist()})
    line = None
    if not np.isnan(slope):
        xs = [float(xv.min()), float(xv.max())]
        line = {"name": f"linear fit (R² = {r2:.3f})", "x": xs, "y": [intercept + slope * v for v in xs]}
    out.charts.append(charts.scatter("scatter", f"{y} vs {x}", groups, x, y, line))
    if n > 5000:
        # Only the drawing is sampled; every statistic uses all points, so the result stays exact.
        out.warnings.append(f"The chart shows a seeded random sample of 5,000 of {n:,} points; all statistics use every point.")
    out.exclusions = missing_note(ctx, cols, n)
    out.warnings += coerce_warnings(ctx, [x, y])
    if not np.isnan(r):
        out.summary = (f"'{x}' and '{y}': Pearson r = {r:.3f} ({strength_label(r)}), Spearman ρ = {rho:.3f}, n = {fmt(n)}; "
                       f"least-squares slope {fmt(slope)} per unit of '{x}' (R² = {r2:.3f}).")
    else:
        out.summary = f"Scatter plot of '{y}' vs '{x}' (n = {fmt(n)})."
    out.warnings.append("A visible association does not imply causation; check for outliers and non-linear patterns in the plot.")
    out.methodology = "Pearson and Spearman correlations and a simple least-squares line on rows where both values exist (listwise deletion)."
    out.missing_value_handling = "Rows missing either axis value are excluded."
    out.code = (f"d = df[[{x!r}, {y!r}]].dropna().astype(float)\nr, p = stats.pearsonr(d[{x!r}], d[{y!r}])\n"
                f"rho, p_s = stats.spearmanr(d[{x!r}], d[{y!r}])\nfit = stats.linregress(d[{x!r}], d[{y!r}])")
    return out


# --------------------------------------------------------------------------- crosstab

def crosstab(ctx: Ctx) -> OpOutput:
    p = ctx.plan
    a, b = p.target_columns[0], p.target_columns[1]
    normalize = ctx.param("normalize", "none")
    d = ctx.df[[a, b]].dropna()
    if d.empty:
        raise AnalysisError(f"No rows have values for both '{a}' and '{b}'.")
    out = OpOutput(columns_used=[a, b], records_used=len(d))
    da, db = limit_categories(d[a].astype(str), 20), limit_categories(d[b].astype(str), 20)
    if d[a].nunique() > 20 or d[b].nunique() > 20:
        out.warnings.append("High-cardinality column(s): only the 20 most frequent categories per axis are shown; others are grouped as 'Other'.")
    counts = pd.crosstab(da, db)
    norm_map = {"none": False, "row": "index", "column": "columns", "all": "all"}
    if normalize not in norm_map:
        raise AnalysisError("normalize must be one of none, row, column, all.")
    shown = pd.crosstab(da, db, normalize=norm_map[normalize]) * (100 if normalize != "none" else 1)
    tbl = shown.reset_index().rename(columns={a: a})
    tbl.columns = [str(c) for c in tbl.columns]
    out.tables.append(make_table("crosstab" + ("" if normalize == "none" else f"_{normalize}_percent"), tbl, ctx.row_cap))
    if normalize != "none":
        out.tables.append(make_table("crosstab_counts", counts.reset_index(), ctx.row_cap))
    series = {str(c): shown[c].tolist() for c in shown.columns}
    out.charts.append(charts.grouped_bar("crosstab_bar", f"{a} × {b}" + ("" if normalize == "none" else f" ({normalize} %)"),
                                         [str(i) for i in shown.index], series, a, "Count" if normalize == "none" else "Percent", stacked=True))
    out.charts.append(charts.heatmap("crosstab_heat", f"{a} × {b} counts", counts.values.tolist(), [str(c) for c in counts.columns],
                                     [str(i) for i in counts.index], diverging=False, xlabel=b, ylabel=a))
    # Association strength is a descriptive companion; the formal test lives in chi_square.
    chi2, pv, dof, exp = stats.chi2_contingency(counts.values, correction=False) if min(counts.shape) > 1 else (np.nan, np.nan, 0, None)
    n = counts.values.sum()
    v = float(np.sqrt(chi2 / (n * (min(counts.shape) - 1)))) if min(counts.shape) > 1 and n else float("nan")
    out.metrics = {"n": int(n), "rows": int(counts.shape[0]), "columns": int(counts.shape[1]), "cramers_v": v, "chi2": float(chi2), "chi2_p": float(pv)}
    out.summary = (f"Cross-tabulation of '{a}' ({counts.shape[0]} categories) by '{b}' ({counts.shape[1]} categories) over {fmt(n)} rows"
                   + (f"; Cramér's V = {v:.3f}." if not np.isnan(v) else "."))
    out.exclusions = missing_note(ctx, [a, b], len(d))
    out.methodology = "Contingency table of complete pairs. Cramér's V is the uncorrected chi-square based association strength (0 = none, 1 = perfect); use the chi-square test for formal inference."
    out.missing_value_handling = "Rows missing either variable are excluded."
    out.code = f"ct = pd.crosstab(df[{a!r}], df[{b!r}]" + (f", normalize={norm_map[normalize]!r}" if normalize != "none" else "") + ")"
    return out


# --------------------------------------------------------------------------- group_by

def _agg_series(sub: Any, col: str | None, agg: str) -> Any:
    if agg == "count" and col is None:
        return sub.size()
    return getattr(sub[col], AGGS[agg])()


def group_by(ctx: Ctx) -> OpOutput:
    p = ctx.plan
    gcols, col = p.group_by, p.column
    aggs = [a for a in ctx.param("aggregations", [p.aggregation]) if a in AGGS] or [p.aggregation]
    if col is None and aggs != ["count"]:
        raise AnalysisError("A value column is needed for aggregations other than 'count'. Use aggregation 'count' to count rows.")
    d = ctx.df[gcols + ([col] if col else [])]
    d = d.dropna(subset=gcols)  # rows without a group key cannot be assigned to a group
    grp = d.groupby(gcols, dropna=True, sort=True)
    res = pd.DataFrame({"n": grp.size()})
    for agg in aggs:
        label = agg if len(aggs) > 1 or col is None else f"{agg}_{col}"
        res[label] = _agg_series(grp, col, agg) if col else grp.size()
    res = res.reset_index()
    sort_col = p.sort_by if p.sort_by in res.columns else (res.columns[len(gcols) + 1] if len(res.columns) > len(gcols) + 1 else "n")
    asc = p.sort_order == "asc"
    res = res.sort_values(sort_col, ascending=asc, kind="mergesort")
    total_groups = len(res)
    top = p.top_n or (50 if total_groups > 50 else None)
    shown = res.head(top) if top else res
    out = OpOutput(columns_used=gcols + ([col] if col else []), records_used=len(d))
    out.tables.append(make_table("grouped_result", shown, ctx.row_cap))
    value_col = res.columns[len(gcols) + 1] if len(res.columns) > len(gcols) + 1 else "n"
    labels = shown[gcols].astype(str).agg(" / ".join, axis=1) if len(gcols) > 1 else shown[gcols[0]].astype(str)
    chart_rows = shown.head(30)
    out.charts.append(charts.bar("group_bar", f"{value_col} by {', '.join(gcols)}", labels.head(30).tolist(), chart_rows[value_col].tolist(),
                                 ", ".join(gcols), value_col, horizontal=len(chart_rows) > 8))
    if len(shown) > 30:
        out.warnings.append("The chart shows the first 30 groups; the table lists all returned groups.")
    if top and total_groups > top:
        out.warnings.append(f"{total_groups} groups found; showing the top {top} by '{sort_col}'.")
    w = small_group_warning(res["n"])
    if w:
        out.warnings.append(w)
    best = res.sort_values(value_col, ascending=False).iloc[0] if len(res) else None
    out.metrics = {"groups": int(total_groups), "aggregations": aggs, "sorted_by": sort_col}
    if col and len(aggs) >= 1 and best is not None:
        overall = _agg_series(d, col, aggs[0]) if aggs[0] != "count" else len(d)
        out.metrics["overall"] = overall
        top_label = " / ".join(str(best[g]) for g in gcols)
        low = res.sort_values(value_col, ascending=True).iloc[0]
        out.summary = (f"{aggs[0]} of '{col}' across {total_groups} group(s) of {', '.join(gcols)}: highest is {top_label!r} ({fmt(best[value_col])}), "
                       f"lowest is {' / '.join(str(low[g]) for g in gcols)!r} ({fmt(low[value_col])}).")
    else:
        out.summary = f"Counted rows across {total_groups} group(s) of {', '.join(gcols)}."
    out.exclusions = missing_note(ctx, gcols + ([col] if col else []), len(d))
    out.warnings += coerce_warnings(ctx, [col] if col else [])
    out.methodology = f"Rows are grouped by {', '.join(gcols)}; {', '.join(aggs)} computed over non-missing values per group. Groups with a missing key are excluded."
    out.missing_value_handling = "Rows with a missing group key are dropped; missing measure values are ignored by each aggregation (count excludes them too)."
    agg_code = {a: f"{a!r}" for a in aggs}
    out.code = (f"res = df.groupby({gcols!r})[{col!r}].agg({list(aggs)!r}).reset_index()\n"
                f"res = res.sort_values({sort_col!r}, ascending={asc})" if col else
                f"res = df.groupby({gcols!r}).size().reset_index(name='count')")
    return out


# --------------------------------------------------------------------------- group_comparison

def group_comparison(ctx: Ctx) -> OpOutput:
    from app.services.analysis import hypothesis

    p = ctx.plan
    col, g = p.column, p.group_by[0]
    d = ctx.df[[col, g]].dropna()
    d[g] = d[g].astype(str)
    counts = d[g].value_counts()
    if len(counts) < 2:
        raise AnalysisError(f"'{g}' has fewer than 2 groups with data, so there is nothing to compare.")
    if len(counts) > 20:
        keep = counts.index[:20]
        d = d[d[g].isin(keep)]
    rows = []
    for key, sub in d.groupby(g, sort=False):
        v = sub[col].astype(float)
        n = len(v)
        sd = float(v.std(ddof=1)) if n > 1 else np.nan
        se = sd / np.sqrt(n) if n > 1 else np.nan
        half = stats.t.ppf(0.975, n - 1) * se if n > 1 else np.nan
        rows.append({g: key, "n": n, "mean": float(v.mean()), "std": sd, "median": float(v.median()),
                     "ci95_low": float(v.mean() - half), "ci95_high": float(v.mean() + half)})
    rows.sort(key=lambda r: -r["mean"])
    out = OpOutput(columns_used=[col, g], records_used=len(d))
    out.tables.append(table_from_rows("group_comparison", [g, "n", "mean", "std", "median", "ci95_low", "ci95_high"], rows, ctx.row_cap))
    out.charts.append(charts.bar("comparison_bar", f"Mean of {col} by {g} (95% CI)", [r[g] for r in rows], [r["mean"] for r in rows], g, f"mean {col}",
                                 error=[(r["ci95_high"] - r["mean"]) if not np.isnan(r["ci95_high"]) else 0 for r in rows]))
    w = small_group_warning(pd.Series([r["n"] for r in rows]))
    if w:
        out.warnings.append(w)
    # A formal test is attached only when the data support one (>=2 groups with n >= 2).
    usable = [k for k, c in d[g].value_counts().items() if c >= 2]
    test = None
    if len(usable) == 2:
        test = hypothesis.t_test_independent_core(d, col, g, usable, alpha=0.05)
    elif len(usable) >= 3:
        test = hypothesis.anova_core(d, col, g, usable, alpha=0.05)
    if test:
        out.metrics["test"] = test["metrics"]
        out.warnings += test["warnings"]
        out.interpretation = test["interpretation"]
    out.metrics["groups"] = len(rows)
    out.summary = (f"Mean of '{col}' by '{g}': highest {rows[0][g]!r} ({fmt(rows[0]['mean'])}), lowest {rows[-1][g]!r} ({fmt(rows[-1]['mean'])})."
                   + (f" {test['headline']}" if test else ""))
    out.exclusions = missing_note(ctx, [col, g], len(d))
    out.methodology = ("Per-group mean with a 95% t-based confidence interval, std and median. When ≥2 groups have n ≥ 2 an exploratory test "
                       "(Welch t-test for two groups, one-way ANOVA for three or more) is attached with its assumption checks.")
    out.missing_value_handling = "Rows missing the measure or the group are excluded."
    out.code = f"summary = df.groupby({g!r})[{col!r}].agg(['count', 'mean', 'std', 'median'])"
    return out


# --------------------------------------------------------------------------- filter_rows

def filter_rows(ctx: Ctx) -> OpOutput:
    p = ctx.plan
    cols = list(p.target_columns) or list(ctx.loaded.df.columns)
    d = ctx.df
    if p.sort_by:
        d = d.sort_values(p.sort_by, ascending=(p.sort_order == "asc"), kind="mergesort", na_position="last")
    total = len(d)
    limit = min(p.top_n or ctx.row_cap, ctx.row_cap)
    shown = d.head(limit)[cols].copy()
    shown.insert(0, "row_number", d.head(limit).index.to_numpy() + 1)
    out = OpOutput(columns_used=cols, records_used=total)
    out.tables.append(make_table("matching_rows", shown, max(limit, 1)))
    pct = total / ctx.full_rows * 100 if ctx.full_rows else 0
    out.metrics = {"matching_rows": total, "total_rows": ctx.full_rows, "matching_percent": pct}
    out.summary = f"{fmt(total)} of {fmt(ctx.full_rows)} rows ({pct:.1f}%) match the filters" + (f"; showing the first {min(limit, total)}." if total > limit else ".")
    if total > limit:
        out.warnings.append(f"Showing {limit} of {total} matching rows. Use the export to download the complete table.")
    out.methodology = "Rows are selected by the structured filters; no values are modified. Row numbers refer to the position in the original data (1-based)."
    out.missing_value_handling = "Comparisons against missing values never match (use is_null to select missing rows)."
    out.code = ctx.filter_code or "# no filters applied"
    return out
