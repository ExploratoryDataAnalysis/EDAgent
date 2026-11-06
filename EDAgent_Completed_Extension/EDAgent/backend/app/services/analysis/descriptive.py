"""
Descriptive, distribution and outlier operations.

Statistical conventions (documented in each result's methodology):
  * variance / standard deviation use the sample formula (ddof = 1);
  * quantiles use linear interpolation (the NumPy/pandas default);
  * skewness / excess kurtosis are the bias-corrected sample estimators;
  * histogram bin edges follow the Freedman-Diaconis rule unless the user fixes the bin count.
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from scipy import stats

from app.schemas.analysis import ExclusionNote
from app.services.analysis import charts
from app.services.analysis.common import (
    AnalysisError, Ctx, OpOutput, coerce_warnings, fmt, limit_categories, make_table, missing_note,
    numeric_series, small_group_warning, table_from_rows,
)

QUANTILES = [0.05, 0.25, 0.5, 0.75, 0.95]


def _numeric_stats(s: pd.Series) -> Dict[str, Any]:
    """All descriptive statistics for one numeric series (missing already dropped)."""
    n = int(len(s))
    if n == 0:
        return {"count": 0}
    modes = s.mode().tolist()
    q = s.quantile(QUANTILES)
    out: Dict[str, Any] = {
        "count": n,
        "mean": float(s.mean()),
        "median": float(s.median()),
        "mode": modes[0] if modes else None,
        "mode_count": int((s == modes[0]).sum()) if modes else None,
        "multimodal": len(modes) > 1,
        "variance": float(s.var(ddof=1)) if n > 1 else None,
        "std": float(s.std(ddof=1)) if n > 1 else None,
        "min": float(s.min()),
        "p05": float(q[0.05]), "q1": float(q[0.25]), "q3": float(q[0.75]), "p95": float(q[0.95]),
        "max": float(s.max()),
        "range": float(s.max() - s.min()),
        "iqr": float(q[0.75] - q[0.25]),
        "sum": float(s.sum()),
    }
    out["skewness"] = float(s.skew()) if n >= 3 and s.std() > 0 else None
    out["kurtosis"] = float(s.kurt()) if n >= 4 and s.std() > 0 else None
    out["cv"] = float(out["std"] / abs(out["mean"])) if out["std"] is not None and out["mean"] not in (0, 0.0) else None
    return out


def descriptive_stats(ctx: Ctx) -> OpOutput:
    p = ctx.plan
    cols = list(p.target_columns) or ([p.column] if p.column else [])
    explicit = bool(cols)
    if not cols:
        cols = ctx.loaded.numeric_columns()
        if not cols:
            raise AnalysisError("This dataset has no numeric measure columns to summarise. Pick a column explicitly.")
    out = OpOutput(columns_used=cols + list(p.group_by))
    out.warnings += coerce_warnings(ctx, cols)
    if not explicit:
        out.warnings.append("No column was specified, so all numeric measure columns were summarised (identifier columns and numeric codes are excluded).")

    # Grouped statistics for a single numeric column.
    if p.group_by:
        if len(cols) != 1 or not ctx.info(cols[0]).is_numeric:
            raise AnalysisError("Grouped descriptive statistics need exactly one numeric column.")
        col, g = cols[0], p.group_by
        d = ctx.df[[col] + g].dropna(subset=[col])
        rows = []
        for key, sub in d.groupby(g, dropna=True, sort=True):
            key = key if isinstance(key, tuple) else (key,)
            st = _numeric_stats(sub[col])
            rows.append({**{gc: kv for gc, kv in zip(g, key)}, **{k: st.get(k) for k in ("count", "mean", "median", "std", "min", "q1", "q3", "max")}})
        out.tables.append(table_from_rows("grouped_statistics", g + ["count", "mean", "median", "std", "min", "q1", "q3", "max"], rows, ctx.row_cap))
        counts = pd.Series([r["count"] for r in rows])
        w = small_group_warning(counts)
        if w:
            out.warnings.append(w)
        out.records_used = int(len(d))
        out.metrics = {"groups": len(rows), "overall": _numeric_stats(d[col])}
        out.summary = f"Computed descriptive statistics of '{col}' for {len(rows)} group(s) of {', '.join(g)} using {fmt(len(d))} rows."
        out.exclusions = missing_note(ctx, [col] + g, len(d))
        out.methodology = "Statistics are computed per group on non-missing values; sample variance/std (ddof=1), linear-interpolated quantiles."
        out.missing_value_handling = "Rows with a missing value in the analysed column are excluded from the groups' statistics."
        out.code = f"summary = df.groupby({g!r})[{col!r}].describe()"
        return out

    table_rows: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {}
    for c in cols:
        info = ctx.info(c)
        if info.is_numeric:
            s = numeric_series(ctx, c)
            st = _numeric_stats(s)
            st["missing"] = int(ctx.df[c].isna().sum())
            metrics[c] = st
            table_rows.append({"column": c, "type": "numeric", **{k: st.get(k) for k in (
                "count", "missing", "mean", "median", "mode", "std", "variance", "min", "q1", "q3", "max", "iqr", "skewness", "kurtosis")}})
            if st["count"] and st["count"] < 30:
                out.warnings.append(f"'{c}' has only {st['count']} non-missing values; its statistics are imprecise.")
        else:
            s = ctx.df[c].dropna()
            vc = s.astype(str).value_counts()
            top = vc.index[0] if len(vc) else None
            metrics[c] = {"count": int(len(s)), "missing": int(ctx.df[c].isna().sum()), "unique": int(vc.size), "top": top,
                          "top_count": int(vc.iloc[0]) if len(vc) else None}
            table_rows.append({"column": c, "type": info.kind if info.kind != "string" else "categorical", "count": len(s),
                               "missing": metrics[c]["missing"], "mode": top})
    all_cols = ["column", "type", "count", "missing", "mean", "median", "mode", "std", "variance", "min", "q1", "q3", "max", "iqr", "skewness", "kurtosis"]
    out.tables.append(table_from_rows("descriptive_statistics", all_cols, table_rows, ctx.row_cap))
    out.metrics = metrics
    out.records_used = int(ctx.df[cols].dropna(how="all").shape[0])
    out.exclusions = missing_note(ctx, cols, out.records_used)
    first = metrics[cols[0]]
    if len(cols) == 1 and "mean" in first:
        out.summary = (f"'{cols[0]}' (n = {fmt(first['count'])}): mean {fmt(first['mean'])}, median {fmt(first['median'])}, "
                       f"std {fmt(first['std'])}, range {fmt(first['min'])} to {fmt(first['max'])}.")
    else:
        out.summary = f"Computed descriptive statistics for {len(cols)} column(s)."
    out.methodology = ("Numeric columns: count, mean, median, mode, sample variance and standard deviation (ddof=1), min/max, quartiles, IQR, "
                       "bias-corrected skewness and excess kurtosis. Statistics use all non-missing values of each column independently.")
    out.missing_value_handling = "Each column is summarised on its own non-missing values; missing counts are reported per column."
    out.code = f"stats = df[{cols!r}].describe(percentiles=[.05, .25, .5, .75, .95])\nextra = df[{cols!r}].agg(['var', 'skew', 'kurt'])"
    return out


def frequency(ctx: Ctx) -> OpOutput:
    p = ctx.plan
    col = p.column
    top_n = p.top_n or 20
    s = ctx.df[col]
    total_missing = int(s.isna().sum())
    vals = s.dropna()
    if vals.empty:
        raise AnalysisError(f"Column '{col}' has no non-missing values.")
    vc = vals.astype(str).value_counts()
    n = int(vc.sum())
    top = vc.head(top_n)
    other = int(vc.iloc[top_n:].sum()) if len(vc) > top_n else 0
    rows = [{col: k, "count": int(v), "percent": float(v / n * 100)} for k, v in top.items()]
    if other:
        rows.append({col: f"Other ({len(vc) - top_n} values)", "count": other, "percent": float(other / n * 100)})
    out = OpOutput(columns_used=[col], records_used=n)
    out.tables.append(table_from_rows("frequency", [col, "count", "percent"], rows, ctx.row_cap))
    labels = [r[col] for r in rows]
    out.charts.append(charts.bar("frequency", f"Frequency of {col}", labels, [r["count"] for r in rows], col, "Count",
                                 horizontal=len(rows) > 6, text=[f"{r['percent']:.1f}%" for r in rows]))
    out.metrics = {"unique_values": int(vc.size), "most_common": str(vc.index[0]), "most_common_count": int(vc.iloc[0]),
                   "most_common_percent": float(vc.iloc[0] / n * 100), "missing": total_missing}
    out.summary = (f"'{col}' has {fmt(vc.size)} distinct value(s) across {fmt(n)} rows; the most common is "
                   f"{vc.index[0]!r} ({vc.iloc[0] / n * 100:.1f}%).")
    if vc.size > top_n:
        out.warnings.append(f"Showing the top {top_n} of {vc.size} values; the remainder are grouped as 'Other'.")
    if total_missing:
        out.exclusions.append(ExclusionNote(reason="missing value", count=total_missing, column=col))
    out.methodology = "Counts of each distinct non-missing value, sorted by frequency; percentages are of non-missing rows."
    out.missing_value_handling = "Missing values are excluded from counts and percentages and reported separately."
    out.code = f"freq = df[{col!r}].value_counts(dropna=True)\npercent = freq / freq.sum() * 100"
    return out


def _bin_edges(s: pd.Series, bins: int | None) -> np.ndarray:
    if bins:
        return np.histogram_bin_edges(s, bins=bins)
    # Freedman-Diaconis adapts to spread and sample size; clamp to a readable range of bins.
    edges = np.histogram_bin_edges(s, bins="fd")
    if len(edges) - 1 > 100:
        edges = np.histogram_bin_edges(s, bins=100)
    if len(edges) - 1 < 5 and s.nunique() > 5:
        edges = np.histogram_bin_edges(s, bins=10)
    return edges


def histogram(ctx: Ctx) -> OpOutput:
    col = ctx.plan.column
    s = numeric_series(ctx, col)
    if len(s) < 2:
        raise AnalysisError(f"'{col}' needs at least 2 non-missing numeric values for a histogram.")
    edges = _bin_edges(s, ctx.plan.bins)
    counts, edges = np.histogram(s, bins=edges)
    n = int(counts.sum())
    st = _numeric_stats(s)
    rows = [{"bin_start": float(edges[i]), "bin_end": float(edges[i + 1]), "count": int(counts[i]), "percent": float(counts[i] / n * 100)}
            for i in range(len(counts))]
    out = OpOutput(columns_used=[col], records_used=n)
    out.tables.append(table_from_rows("histogram_bins", ["bin_start", "bin_end", "count", "percent"], rows, ctx.row_cap))
    out.charts.append(charts.histogram_bars("histogram", f"Distribution of {col}", edges.tolist(), counts.tolist(), col, st["mean"], st["median"]))
    out.metrics = {"bins": len(counts), "bin_rule": "user-specified" if ctx.plan.bins else "Freedman-Diaconis",
                   **{k: st.get(k) for k in ("count", "mean", "median", "std", "min", "max", "skewness", "kurtosis")}}
    sk = st.get("skewness")
    shape = ""
    if sk is not None:
        shape = " roughly symmetric" if abs(sk) < 0.5 else (" right-skewed (long upper tail)" if sk > 0 else " left-skewed (long lower tail)")
    out.summary = (f"Distribution of '{col}' across {len(counts)} bins (n = {fmt(n)}): mean {fmt(st['mean'])}, median {fmt(st['median'])}, "
                   f"skewness {fmt(sk)}{(' -> ' + shape.strip()) if shape else ''}.")
    out.exclusions = missing_note(ctx, [col], n)
    out.warnings += coerce_warnings(ctx, [col])
    out.methodology = ("Exact full-data histogram. Bin edges use the Freedman-Diaconis rule (clamped to 5-100 bins) unless a bin count was "
                       "specified. Skewness and excess kurtosis are bias-corrected sample estimators.")
    out.missing_value_handling = "Missing values are excluded; their count is reported."
    out.code = (f"s = df[{col!r}].dropna().astype(float)\n"
                f"counts, edges = np.histogram(s, bins={ctx.plan.bins if ctx.plan.bins else repr('fd')})")
    return out


def _box_stats(s: pd.Series, name: str) -> Dict[str, Any]:
    q1, med, q3 = (float(s.quantile(q)) for q in (0.25, 0.5, 0.75))
    iqr = q3 - q1
    lo_f, hi_f = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inside = s[(s >= lo_f) & (s <= hi_f)]
    outl = s[(s < lo_f) | (s > hi_f)]
    return {"name": name, "n": int(len(s)), "min": float(s.min()), "q1": q1, "median": med, "q3": q3, "max": float(s.max()),
            "iqr": iqr, "lower_fence": lo_f, "upper_fence": hi_f,
            "lower": float(inside.min()) if len(inside) else q1, "upper": float(inside.max()) if len(inside) else q3,
            "mean": float(s.mean()), "outlier_count": int(len(outl)), "outliers": outl.head(200).tolist()}


def _grouped_numeric(ctx: Ctx, col: str) -> Dict[str, pd.Series]:
    if not ctx.plan.group_by:
        return {col: numeric_series(ctx, col)}
    g = ctx.plan.group_by[0]
    d = ctx.df[[col, g]].dropna()
    counts = d[g].astype(str).value_counts()
    keep = counts.index[:20]  # a readable maximum; the rest are reported in a warning
    return {k: d.loc[d[g].astype(str) == k, col].astype(float) for k in keep}


def boxplot(ctx: Ctx) -> OpOutput:
    col = ctx.plan.column
    groups = _grouped_numeric(ctx, col)
    groups = {k: v for k, v in groups.items() if len(v) >= 1}
    if not groups:
        raise AnalysisError(f"No non-missing values of '{col}' to plot.")
    stats_rows = [_box_stats(v, k) for k, v in groups.items()]
    out = OpOutput(columns_used=[col] + ctx.plan.group_by[:1], records_used=int(sum(len(v) for v in groups.values())))
    out.tables.append(table_from_rows("boxplot_statistics", ["name", "n", "min", "q1", "median", "q3", "max", "iqr", "lower_fence", "upper_fence", "mean", "outlier_count"], stats_rows, ctx.row_cap))
    gl = ctx.plan.group_by[0] if ctx.plan.group_by else ""
    out.charts.append(charts.boxes("boxplot", f"{col}" + (f" by {gl}" if gl else ""), stats_rows, gl, col))
    total_out = sum(r["outlier_count"] for r in stats_rows)
    out.metrics = {"groups": len(stats_rows), "total_outliers": total_out}
    if len(stats_rows) == 1:
        r = stats_rows[0]
        out.summary = (f"'{col}' median {fmt(r['median'])}, IQR {fmt(r['iqr'])} (Q1 {fmt(r['q1'])} to Q3 {fmt(r['q3'])}); "
                       f"{r['outlier_count']} point(s) lie beyond the 1.5×IQR fences.")
    else:
        out.summary = f"Box plot of '{col}' across {len(stats_rows)} '{gl}' groups; {total_out} point(s) lie beyond the 1.5×IQR fences."
    if ctx.plan.group_by:
        total_groups = ctx.df[ctx.plan.group_by[0]].nunique()
        if total_groups > 20:
            out.warnings.append(f"Only the 20 largest of {total_groups} groups are plotted.")
        w = small_group_warning(pd.Series([r["n"] for r in stats_rows]))
        if w:
            out.warnings.append(w)
    out.warnings += coerce_warnings(ctx, [col])
    out.exclusions = missing_note(ctx, [col], out.records_used)
    out.methodology = "Quartiles by linear interpolation; whiskers extend to the most extreme points within 1.5×IQR of the quartiles; points beyond are flagged (at most 200 drawn per group). Flags indicate unusual values, not errors."
    out.missing_value_handling = "Rows missing the analysed (or grouping) value are excluded."
    out.code = (f"q1, q3 = df[{col!r}].quantile([.25, .75]); iqr = q3 - q1\n"
                f"fences = (q1 - 1.5 * iqr, q3 + 1.5 * iqr)")
    return out


def violin_plot(ctx: Ctx) -> OpOutput:
    out = boxplot(ctx)
    col = ctx.plan.column
    groups = _grouped_numeric(ctx, col)
    rng = np.random.default_rng(ctx.plan.seed)
    vg, approx = [], False
    for k, v in groups.items():
        vals = v.to_numpy()
        if len(vals) > 2000:  # drawing sample only; the statistics tables above remain exact
            vals = rng.choice(vals, 2000, replace=False)
            approx = True
        vg.append({"name": k, "values": vals.tolist()})
    gl = ctx.plan.group_by[0] if ctx.plan.group_by else ""
    out.charts = [charts.violins("violin", f"{col}" + (f" by {gl}" if gl else ""), vg, gl, col)] + out.charts
    if approx:
        out.warnings.append("Violin shapes are drawn from a random sample of up to 2,000 values per group (seeded); the statistics tables use all values.")
    out.methodology = "Kernel-density violin of each group (drawn from ≤2,000 sampled values per group) with exact quartile statistics in the table. " + out.methodology
    return out


def outlier_iqr(ctx: Ctx) -> OpOutput:
    col = ctx.plan.column
    k = float(ctx.param("iqr_multiplier", 1.5))
    s = numeric_series(ctx, col)
    if len(s) < 4:
        raise AnalysisError(f"'{col}' needs at least 4 non-missing values for IQR outlier detection.")
    q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
    iqr = q3 - q1
    lo, hi = q1 - k * iqr, q3 + k * iqr
    col_vals = ctx.df[col].astype(float)
    mask = (col_vals < lo) | (col_vals > hi)
    flagged = ctx.df.loc[mask.fillna(False)]
    ctx_cols = [c for c in ctx.loaded.df.columns if c != col][:4]
    table = flagged[[col] + ctx_cols].copy()
    table.insert(0, "row_number", flagged.index.to_numpy() + 1)
    table.insert(2, "direction", np.where(flagged[col].astype(float) > hi, "above upper fence", "below lower fence"))
    table = table.reindex(table[col].astype(float).sub(s.median()).abs().sort_values(ascending=False).index)
    n_out = int(len(flagged))
    out = OpOutput(columns_used=[col], records_used=int(len(s)))
    out.metrics = {"q1": q1, "q3": q3, "iqr": iqr, "multiplier": k, "lower_fence": lo, "upper_fence": hi,
                   "outlier_count": n_out, "outlier_percent": n_out / len(s) * 100, "lower_outliers": int((col_vals < lo).sum()), "upper_outliers": int((col_vals > hi).sum())}
    out.tables.append(make_table("flagged_records", table, ctx.row_cap))
    box = _box_stats(s, col)
    box["lower"], box["upper"] = (float(s[s >= lo].min()) if (s >= lo).any() else q1), (float(s[s <= hi].max()) if (s <= hi).any() else q3)
    box["outliers"] = s[(s < lo) | (s > hi)].head(200).tolist()
    out.charts.append(charts.boxes("outlier_box", f"Outliers in {col} (IQR rule)", [box], "", col))
    out.summary = (f"{n_out} of {fmt(len(s))} values in '{col}' ({n_out / len(s) * 100:.2f}%) fall outside the IQR fences "
                   f"[{fmt(lo)}, {fmt(hi)}] (Q1 {fmt(q1)}, Q3 {fmt(q3)}, IQR {fmt(iqr)}, multiplier {k:g}).")
    out.warnings.append("Outlier flags mark unusual values; they do not prove errors. No records were removed or changed.")
    out.warnings += coerce_warnings(ctx, [col])
    out.exclusions = missing_note(ctx, [col], int(len(s)))
    out.methodology = f"Tukey fences: Q1 − {k:g}×IQR and Q3 + {k:g}×IQR with linear-interpolated quartiles on non-missing values. Records are listed, never removed."
    out.missing_value_handling = "Missing values cannot be outliers and are excluded from the quartile calculation."
    out.code = (f"s = df[{col!r}].astype(float)\nq1, q3 = s.quantile([.25, .75]); iqr = q3 - q1\n"
                f"lo, hi = q1 - {k} * iqr, q3 + {k} * iqr\noutliers = df[(s < lo) | (s > hi)]")
    return out


def outlier_zscore(ctx: Ctx) -> OpOutput:
    col = ctx.plan.column
    thr = float(ctx.param("z_threshold", 3.0))
    robust = bool(ctx.param("robust", False))
    s = numeric_series(ctx, col)
    if len(s) < 4:
        raise AnalysisError(f"'{col}' needs at least 4 non-missing values for Z-score outlier detection.")
    vals = ctx.df[col].astype(float)
    if robust:
        med = float(s.median())
        mad = float((s - med).abs().median())
        if mad == 0:
            raise AnalysisError(f"'{col}' has a median absolute deviation of 0, so robust Z-scores are undefined. Use the IQR method instead.")
        z = 0.6745 * (vals - med) / mad
        centre, spread = med, mad
    else:
        mean, std = float(s.mean()), float(s.std(ddof=1))
        if std == 0:
            raise AnalysisError(f"'{col}' is constant (standard deviation 0), so Z-scores are undefined.")
        z = (vals - mean) / std
        centre, spread = mean, std
    mask = z.abs() > thr
    flagged = ctx.df.loc[mask.fillna(False)]
    ctx_cols = [c for c in ctx.loaded.df.columns if c != col][:4]
    table = flagged[[col] + ctx_cols].copy()
    table.insert(0, "row_number", flagged.index.to_numpy() + 1)
    table.insert(2, "z_score", z[flagged.index].round(4))
    table = table.reindex(table["z_score"].abs().sort_values(ascending=False).index)
    n_out = int(len(flagged))
    out = OpOutput(columns_used=[col], records_used=int(len(s)))
    lower, upper = (centre - thr * spread / (0.6745 if robust else 1), centre + thr * spread / (0.6745 if robust else 1))
    out.metrics = {"method": "modified z-score (median/MAD)" if robust else "z-score (mean/std, ddof=1)", "threshold": thr,
                   "center": centre, "spread": spread, "lower_threshold": lower, "upper_threshold": upper,
                   "outlier_count": n_out, "outlier_percent": n_out / len(s) * 100}
    out.tables.append(make_table("flagged_records", table, ctx.row_cap))
    idx = np.arange(len(vals))
    good = ~mask.fillna(False).to_numpy()
    ok = vals.notna().to_numpy()
    out.charts.append(charts.scatter("zscore_scatter", f"{col}: observations vs row number (|z| > {thr:g} flagged)", [
        {"name": "within threshold", "x": (idx[good & ok] + 1)[:5000].tolist(), "y": vals.to_numpy()[good & ok][:5000].tolist()},
        {"name": "flagged", "x": (idx[~good & ok] + 1).tolist(), "y": vals.to_numpy()[~good & ok].tolist(), "color": "#EF4444", "size": 9},
    ], "row number", col))
    out.summary = (f"{n_out} of {fmt(len(s))} values in '{col}' ({n_out / len(s) * 100:.2f}%) have |z| > {thr:g} "
                   f"(thresholds {fmt(lower)} to {fmt(upper)}).")
    out.warnings.append("Outlier flags mark unusual values; they do not prove errors. No records were removed or changed.")
    if not robust and abs(float(s.skew())) > 1:
        out.warnings.append("The data are noticeably skewed, so mean/std-based Z-scores can be misleading; consider the IQR method or robust=true.")
    out.warnings += coerce_warnings(ctx, [col])
    out.exclusions = missing_note(ctx, [col], int(len(s)))
    out.methodology = (("Modified Z-score 0.6745·(x − median)/MAD" if robust else "Z-score (x − mean)/std with sample standard deviation (ddof=1)") +
                       f"; values with |z| > {thr:g} are flagged. Scatter drawing shows at most 5,000 unflagged points.")
    out.missing_value_handling = "Missing values are excluded from the mean/std (or median/MAD) and are never flagged."
    out.code = (f"s = df[{col!r}].astype(float)\nz = (s - s.mean()) / s.std(ddof=1)\noutliers = df[z.abs() > {thr}]")
    if len(vals.dropna()) > 5000:
        out.warnings.append("The scatter chart shows at most 5,000 non-flagged points for readability; all flagged points and all calculations use every row.")
    return out
