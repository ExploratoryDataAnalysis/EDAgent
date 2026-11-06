"""
Statistical hypothesis tests.

Every test returns: hypotheses, sample sizes, the test statistic, p-value, the significance
level used, an effect size, assumption checks, a computed plain-language interpretation and
warnings (small samples, violated assumptions, multiple comparisons). Where parametric
assumptions look violated the non-parametric alternative is computed alongside and flagged,
rather than silently swapped in. All results are exploratory unless a study was designed for
confirmatory testing.
"""

from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from app.services.analysis import charts
from app.services.analysis.common import (
    AnalysisError, Ctx, OpOutput, coerce_warnings, fmt, fmt_p, limit_categories, make_table, missing_note, table_from_rows,
)
from app.services.analysis.descriptive import _box_stats

SMALL_N = 30  # below this, normality assumptions matter and are flagged


def _alpha(ctx: Ctx) -> float:
    a = float(ctx.param("alpha", 0.05))
    if not 0.001 <= a <= 0.2:
        raise AnalysisError("alpha must be between 0.001 and 0.2.")
    return a


def _normality(values: pd.Series, label: str, alpha: float) -> Dict[str, Any]:
    """Shapiro-Wilk normality check (only meaningful for 3 <= n <= 5000 and non-constant data)."""
    n = len(values)
    if n < 3:
        return {"check": "normality (Shapiro-Wilk)", "group": label, "checked": False, "note": "n < 3"}
    if values.nunique() < 2:
        return {"check": "normality (Shapiro-Wilk)", "group": label, "checked": False, "note": "constant values"}
    if n > 5000:
        return {"check": "normality (Shapiro-Wilk)", "group": label, "checked": False,
                "note": "n > 5000: Shapiro-Wilk is over-sensitive at this size; rely on the central limit theorem and inspect the plot"}
    w, p = stats.shapiro(values)
    return {"check": "normality (Shapiro-Wilk)", "group": label, "checked": True, "statistic": float(w), "p_value": float(p),
            "passed": bool(p >= alpha)}


def _levene(groups: List[pd.Series], alpha: float) -> Dict[str, Any]:
    if any(len(g) < 2 for g in groups):
        return {"check": "equal variances (Levene)", "group": "all", "checked": False, "note": "a group has n < 2"}
    s, p = stats.levene(*groups, center="median")
    return {"check": "equal variances (Levene)", "group": "all", "checked": True, "statistic": float(s), "p_value": float(p), "passed": bool(p >= alpha)}


def _sig_text(p: float, alpha: float) -> str:
    return (f"p {('= ' + fmt_p(p)) if p >= 1e-4 else fmt_p(p)} is {'below' if p < alpha else 'not below'} α = {alpha:g}: "
            + ("the data provide evidence against the null hypothesis." if p < alpha else "there is not enough evidence to reject the null hypothesis (this does not prove it is true)."))


def _cohen_label(d: float) -> str:
    a = abs(d)
    return "negligible" if a < 0.2 else "small" if a < 0.5 else "medium" if a < 0.8 else "large"


# --------------------------------------------------------------------------- independent t-test

def t_test_independent_core(d: pd.DataFrame, col: str, g: str, groups: List[str], alpha: float, equal_var: Optional[bool] = None) -> Dict[str, Any]:
    a = d.loc[d[g].astype(str) == str(groups[0]), col].astype(float).dropna()
    b = d.loc[d[g].astype(str) == str(groups[1]), col].astype(float).dropna()
    warnings: List[str] = []
    if len(a) < 2 or len(b) < 2:
        raise AnalysisError("Each group needs at least 2 non-missing observations for a t-test.")
    checks = [_normality(a, str(groups[0]), alpha), _normality(b, str(groups[1]), alpha), _levene([a, b], alpha)]
    use_equal = bool(equal_var) if equal_var is not None else False  # Welch by default: valid with or without equal variances
    res = stats.ttest_ind(a, b, equal_var=use_equal)
    ci = res.confidence_interval(1 - alpha)
    n1, n2 = len(a), len(b)
    sp = np.sqrt(((n1 - 1) * a.var(ddof=1) + (n2 - 1) * b.var(ddof=1)) / (n1 + n2 - 2))
    dcoh = float((a.mean() - b.mean()) / sp) if sp > 0 else float("nan")
    hedges = dcoh * (1 - 3 / (4 * (n1 + n2) - 9)) if not np.isnan(dcoh) else dcoh
    nonnormal = [c for c in checks if c["check"].startswith("normality") and c.get("checked") and not c["passed"]]
    alt = None
    if nonnormal or min(n1, n2) < SMALL_N:
        u, pu = stats.mannwhitneyu(a, b, alternative="two-sided")
        alt = {"test": "Mann-Whitney U", "statistic": float(u), "p_value": float(pu), "rank_biserial_r": float(2 * u / (n1 * n2) - 1),
               "recommended": bool(nonnormal and min(n1, n2) < SMALL_N)}
    if min(n1, n2) < SMALL_N:
        warnings.append(f"Small sample (n = {n1} and {n2}): t-test results are sensitive to non-normality; interpret cautiously.")
    if nonnormal:
        warnings.append("Normality is doubtful in at least one group (Shapiro-Wilk p < α); the Mann-Whitney U alternative is reported" +
                        (" and is the safer choice here." if alt and alt["recommended"] else "."))
    metrics = {
        "test": "Welch's t-test" if not use_equal else "Student's t-test (equal variances)",
        "null_hypothesis": f"mean({col} | {g}={groups[0]}) = mean({col} | {g}={groups[1]})",
        "alternative_hypothesis": "the two means differ (two-sided)", "alpha": alpha,
        "groups": [str(groups[0]), str(groups[1])], "n": [n1, n2], "means": [float(a.mean()), float(b.mean())], "stds": [float(a.std(ddof=1)), float(b.std(ddof=1))],
        "mean_difference": float(a.mean() - b.mean()), "ci_level": 1 - alpha, "ci_low": float(ci.low), "ci_high": float(ci.high),
        "statistic": float(res.statistic), "df": float(res.df), "p_value": float(res.pvalue), "significant": bool(res.pvalue < alpha),
        "effect_size": {"cohens_d": dcoh, "hedges_g": float(hedges), "magnitude": _cohen_label(dcoh) if not np.isnan(dcoh) else "undefined"},
        "assumptions": checks, "nonparametric_alternative": alt,
    }
    interp = (f"Mean of '{col}' is {fmt(a.mean())} for {groups[0]!r} (n={n1}) vs {fmt(b.mean())} for {groups[1]!r} (n={n2}); difference {fmt(a.mean() - b.mean())} "
              f"({int((1 - alpha) * 100)}% CI {fmt(ci.low)} to {fmt(ci.high)}). t({fmt(res.df, 2)}) = {fmt(res.statistic, 3)}; {_sig_text(res.pvalue, alpha)} "
              f"Effect size Cohen's d = {fmt(dcoh, 3)} ({metrics['effect_size']['magnitude']}). Statistical significance is not the same as practical importance.")
    headline = f"Welch t-test: t = {fmt(res.statistic, 3)}, p {('= ' + fmt_p(res.pvalue)) if res.pvalue >= 1e-4 else fmt_p(res.pvalue)} ({'significant' if res.pvalue < alpha else 'not significant'} at α = {alpha:g})."
    return {"metrics": metrics, "warnings": warnings, "interpretation": interp, "headline": headline, "series": (a, b)}


def _two_groups(ctx: Ctx) -> Tuple[pd.DataFrame, str, str, List[str]]:
    col, g = ctx.plan.column, ctx.plan.group_by[0]
    d = ctx.df[[col, g]].dropna()
    levels = sorted(d[g].astype(str).unique())
    chosen = ctx.param("groups")
    if chosen:
        chosen = [str(x) for x in chosen]
        if len(chosen) != 2 or not set(chosen) <= set(levels):
            raise AnalysisError(f"'groups' must name exactly two existing values of '{g}'. Available: {', '.join(levels[:20])}.")
        levels = chosen
    if len(levels) != 2:
        raise AnalysisError(f"'{g}' has {len(levels)} groups ({', '.join(levels[:10])}{'...' if len(levels) > 10 else ''}). "
                            f"Choose exactly two with the 'groups' parameter, or use one-way ANOVA / Kruskal-Wallis for 3+ groups.")
    return d, col, g, levels


def _group_outputs(out: OpOutput, ctx: Ctx, d: pd.DataFrame, col: str, g: str, levels: List[str]) -> None:
    out.columns_used = [col, g]
    out.records_used = int(d[d[g].astype(str).isin(levels)].shape[0])
    rows, boxes = [], []
    for lv in levels:
        v = d.loc[d[g].astype(str) == lv, col].astype(float)
        rows.append({g: lv, "n": len(v), "mean": float(v.mean()), "std": float(v.std(ddof=1)) if len(v) > 1 else None, "median": float(v.median()), "min": float(v.min()), "max": float(v.max())})
        boxes.append(_box_stats(v, lv))
    out.tables.insert(0, table_from_rows("group_statistics", [g, "n", "mean", "std", "median", "min", "max"], rows, ctx.row_cap))
    out.charts.append(charts.boxes("group_box", f"{col} by {g}", boxes, g, col))
    out.exclusions = missing_note(ctx, [col, g], out.records_used)
    out.warnings += coerce_warnings(ctx, [col])


def _assumption_table(ctx: Ctx, out: OpOutput, checks: List[Dict[str, Any]]) -> None:
    rows = [{"check": c["check"], "group": c.get("group"), "statistic": c.get("statistic"), "p_value": c.get("p_value"),
             "result": ("passed" if c.get("passed") else "violated") if c.get("checked") else f"not checked ({c.get('note', '')})"} for c in checks]
    out.tables.append(table_from_rows("assumption_checks", ["check", "group", "statistic", "p_value", "result"], rows, ctx.row_cap))


def t_test_independent(ctx: Ctx) -> OpOutput:
    alpha = _alpha(ctx)
    d, col, g, levels = _two_groups(ctx)
    eq = ctx.param("equal_var")
    r = t_test_independent_core(d, col, g, levels, alpha, equal_var=eq if isinstance(eq, bool) else None)
    out = OpOutput(metrics=r["metrics"], warnings=r["warnings"], interpretation=r["interpretation"], summary=r["headline"])
    _group_outputs(out, ctx, d, col, g, levels)
    _assumption_table(ctx, out, r["metrics"]["assumptions"])
    out.warnings.append("This is an exploratory test; running many tests inflates the chance of false positives.")
    out.methodology = (f"{r['metrics']['test']} comparing '{col}' between '{levels[0]}' and '{levels[1]}' (two-sided, α = {alpha:g}); complete cases only. "
                       "Welch's version does not assume equal variances. Effect size: Cohen's d with Hedges' small-sample correction; CI is for the mean difference. "
                       "Normality is checked per group (Shapiro-Wilk, n ≤ 5000) and equal variances with Levene's test (median-centred).")
    out.missing_value_handling = "Rows missing the measure or group are excluded (listwise)."
    out.code = (f"a = df.loc[df[{g!r}] == {levels[0]!r}, {col!r}].dropna()\nb = df.loc[df[{g!r}] == {levels[1]!r}, {col!r}].dropna()\n"
                f"res = stats.ttest_ind(a, b, equal_var={bool(eq) if isinstance(eq, bool) else False})")
    return out


# --------------------------------------------------------------------------- paired t-test

def _paired(ctx: Ctx) -> Tuple[pd.Series, pd.Series, str, str]:
    a_col, b_col = ctx.plan.target_columns[0], ctx.plan.target_columns[1]
    d = ctx.df[[a_col, b_col]].dropna().astype(float)
    if len(d) < 3:
        raise AnalysisError(f"Only {len(d)} complete pair(s) of '{a_col}' and '{b_col}'; at least 3 are needed.")
    return d[a_col], d[b_col], a_col, b_col


def t_test_paired(ctx: Ctx) -> OpOutput:
    alpha = _alpha(ctx)
    a, b, ac, bc = _paired(ctx)
    diff = a - b
    n = len(diff)
    res = stats.ttest_rel(a, b)
    ci = res.confidence_interval(1 - alpha)
    sd = float(diff.std(ddof=1))
    dz = float(diff.mean() / sd) if sd > 0 else float("nan")
    norm = _normality(diff, "differences", alpha)
    alt = None
    if (norm.get("checked") and not norm["passed"]) or n < SMALL_N:
        try:
            w, pw = stats.wilcoxon(diff[diff != 0]) if (diff != 0).any() else (float("nan"), float("nan"))
            alt = {"test": "Wilcoxon signed-rank", "statistic": float(w), "p_value": float(pw), "recommended": bool(norm.get("checked") and not norm["passed"] and n < SMALL_N)}
        except ValueError:
            alt = None
    out = OpOutput(columns_used=[ac, bc], records_used=n)
    warnings = []
    if n < SMALL_N:
        warnings.append(f"Small sample (n = {n} pairs): interpret cautiously.")
    if norm.get("checked") and not norm["passed"]:
        warnings.append("The paired differences do not look normal (Shapiro-Wilk p < α); the Wilcoxon signed-rank alternative is reported.")
    out.warnings = warnings + ["Pairs are formed row-by-row; make sure each row really is a matched pair (same subject measured twice).",
                               "This is an exploratory test; running many tests inflates the chance of false positives."]
    out.metrics = {
        "test": "Paired t-test", "null_hypothesis": f"mean({ac} − {bc}) = 0", "alternative_hypothesis": "the mean difference is not 0 (two-sided)", "alpha": alpha,
        "n_pairs": n, "mean_a": float(a.mean()), "mean_b": float(b.mean()), "mean_difference": float(diff.mean()), "std_difference": sd,
        "ci_level": 1 - alpha, "ci_low": float(ci.low), "ci_high": float(ci.high), "statistic": float(res.statistic), "df": float(res.df), "p_value": float(res.pvalue),
        "significant": bool(res.pvalue < alpha), "effect_size": {"cohens_dz": dz, "magnitude": _cohen_label(dz) if not np.isnan(dz) else "undefined"},
        "assumptions": [norm], "nonparametric_alternative": alt,
    }
    out.interpretation = (f"Mean {ac} = {fmt(a.mean())}, mean {bc} = {fmt(b.mean())}; mean paired difference {fmt(diff.mean())} ({int((1 - alpha) * 100)}% CI {fmt(ci.low)} to {fmt(ci.high)}). "
                          f"t({n - 1}) = {fmt(res.statistic, 3)}; {_sig_text(res.pvalue, alpha)} Effect size d_z = {fmt(dz, 3)}.")
    out.summary = f"Paired t-test of '{ac}' vs '{bc}': t = {fmt(res.statistic, 3)}, p {('= ' + fmt_p(res.pvalue)) if res.pvalue >= 1e-4 else fmt_p(res.pvalue)} (n = {n} pairs)."
    out.tables.append(table_from_rows("paired_summary", ["measure", "value"], [
        {"measure": f"mean {ac}", "value": float(a.mean())}, {"measure": f"mean {bc}", "value": float(b.mean())},
        {"measure": "mean difference", "value": float(diff.mean())}, {"measure": "std of differences", "value": sd}], ctx.row_cap))
    _assumption_table(ctx, out, [norm])
    out.charts.append(charts.histogram_bars("diff_hist", f"Paired differences ({ac} − {bc})", *_hist(diff), f"{ac} − {bc}", float(diff.mean()), float(diff.median())))
    out.exclusions = missing_note(ctx, [ac, bc], n)
    out.warnings += coerce_warnings(ctx, [ac, bc])
    out.methodology = (f"Paired t-test on within-row differences of '{ac}' and '{bc}' (two-sided, α = {alpha:g}); complete pairs only. "
                       "Effect size is Cohen's d_z (mean difference / SD of differences). Normality of the differences is checked with Shapiro-Wilk.")
    out.missing_value_handling = "A row is used only if both values are present (listwise deletion)."
    out.code = f"d = df[[{ac!r}, {bc!r}]].dropna()\nres = stats.ttest_rel(d[{ac!r}], d[{bc!r}])"
    return out


def _hist(s: pd.Series) -> Tuple[List[float], List[int]]:
    counts, edges = np.histogram(s, bins="auto" if s.nunique() > 1 else 1)
    return edges.tolist(), counts.tolist()


# --------------------------------------------------------------------------- ANOVA

def anova_core(d: pd.DataFrame, col: str, g: str, groups: List[str], alpha: float) -> Dict[str, Any]:
    series = [d.loc[d[g].astype(str) == str(k), col].astype(float).dropna() for k in groups]
    series = [s for s in series if len(s) >= 2]
    if len(series) < 3:
        raise AnalysisError("One-way ANOVA needs at least 3 groups with 2+ observations each (use a t-test for two groups).")
    names = [str(k) for k, s in zip(groups, [d.loc[d[g].astype(str) == str(k), col].astype(float).dropna() for k in groups]) if len(s) >= 2]
    f, p = stats.f_oneway(*series)
    allv = pd.concat(series)
    grand = allv.mean()
    ssb = float(sum(len(s) * (s.mean() - grand) ** 2 for s in series))
    sst = float(((allv - grand) ** 2).sum())
    k, n = len(series), len(allv)
    eta2 = ssb / sst if sst > 0 else float("nan")
    msw = (sst - ssb) / (n - k) if n > k else float("nan")
    omega2 = (ssb - (k - 1) * msw) / (sst + msw) if sst > 0 and not np.isnan(msw) else float("nan")
    resid = pd.concat([s - s.mean() for s in series])
    checks = [_normality(resid, "residuals (pooled)", alpha), _levene(series, alpha)]
    warnings: List[str] = []
    small = [nm for nm, s in zip(names, series) if len(s) < 5]
    if small:
        warnings.append(f"Group(s) with fewer than 5 observations: {', '.join(small)}.")
    violated = [c for c in checks if c.get("checked") and not c["passed"]]
    alt = None
    if violated or min(len(s) for s in series) < SMALL_N:
        h, pk = stats.kruskal(*series)
        alt = {"test": "Kruskal-Wallis H", "statistic": float(h), "p_value": float(pk), "epsilon_squared": float((h - k + 1) / (n - k)) if n > k else None,
               "recommended": bool(violated)}
    if violated:
        warnings.append("An ANOVA assumption looks violated (" + ", ".join(c["check"] for c in violated) + "); the Kruskal-Wallis alternative is reported.")
    posthoc: List[Dict[str, Any]] = []
    if p < alpha and k <= 15:
        tk = stats.tukey_hsd(*series)
        ci = tk.confidence_interval(1 - alpha)
        for i, j in combinations(range(k), 2):
            posthoc.append({"group_a": names[i], "group_b": names[j], "mean_diff": float(series[i].mean() - series[j].mean()),
                            "p_adjusted": float(tk.pvalue[i, j]), "ci_low": float(ci.low[i, j]), "ci_high": float(ci.high[i, j]), "significant": bool(tk.pvalue[i, j] < alpha)})
        warnings.append(f"Post-hoc comparisons use Tukey's HSD, which controls the family-wise error rate across all {len(posthoc)} pairs.")
    elif p < alpha:
        warnings.append("Too many groups for pairwise post-hoc tests (limit 15).")
    metrics = {
        "test": "One-way ANOVA", "null_hypothesis": f"all group means of {col} are equal", "alternative_hypothesis": "at least one group mean differs", "alpha": alpha,
        "groups": names, "n": [len(s) for s in series], "means": [float(s.mean()) for s in series], "statistic_F": float(f), "df_between": k - 1, "df_within": n - k,
        "p_value": float(p), "significant": bool(p < alpha), "effect_size": {"eta_squared": eta2, "omega_squared": omega2,
                                                                              "magnitude": "small" if eta2 < 0.06 else "medium" if eta2 < 0.14 else "large"},
        "assumptions": checks, "nonparametric_alternative": alt, "post_hoc": posthoc,
    }
    interp = (f"F({k - 1}, {n - k}) = {fmt(f, 3)}; {_sig_text(p, alpha)} η² = {fmt(eta2, 3)} (≈ {eta2 * 100:.1f}% of the variance in '{col}' is associated with '{g}'). "
              + ("Significant pairs: " + (", ".join(f"{r['group_a']} vs {r['group_b']}" for r in posthoc if r["significant"]) or "none after adjustment") + "." if posthoc else ""))
    headline = f"One-way ANOVA: F = {fmt(f, 3)}, p {('= ' + fmt_p(p)) if p >= 1e-4 else fmt_p(p)} ({'significant' if p < alpha else 'not significant'} at α = {alpha:g}), η² = {fmt(eta2, 3)}."
    return {"metrics": metrics, "warnings": warnings, "interpretation": interp, "headline": headline, "series": series, "names": names}


def anova_one_way(ctx: Ctx) -> OpOutput:
    alpha = _alpha(ctx)
    col, g = ctx.plan.column, ctx.plan.group_by[0]
    d = ctx.df[[col, g]].dropna()
    counts = d[g].astype(str).value_counts()
    levels = [k for k in counts.index[:30]]
    if counts.size > 30:
        d = d[d[g].astype(str).isin(levels)]
    r = anova_core(d, col, g, levels, alpha)
    out = OpOutput(metrics=r["metrics"], warnings=r["warnings"], interpretation=r["interpretation"], summary=r["headline"])
    if counts.size > 30:
        out.warnings.append(f"Only the 30 largest of {counts.size} groups were included.")
    _group_outputs(out, ctx, d, col, g, r["names"])
    _assumption_table(ctx, out, r["metrics"]["assumptions"])
    if r["metrics"]["post_hoc"]:
        out.tables.append(table_from_rows("post_hoc_tukey", ["group_a", "group_b", "mean_diff", "p_adjusted", "ci_low", "ci_high", "significant"], r["metrics"]["post_hoc"], ctx.row_cap))
    out.warnings.append("This is an exploratory test; running many tests inflates the chance of false positives.")
    out.methodology = (f"One-way ANOVA of '{col}' across '{g}' (α = {alpha:g}); effect sizes η² and ω². Assumptions: Shapiro-Wilk on pooled residuals, Levene's test for equal variances. "
                       "Tukey HSD post-hoc pairs are shown only when the overall test is significant.")
    out.missing_value_handling = "Rows missing the measure or group are excluded; groups with fewer than 2 observations are dropped from the test."
    out.code = (f"groups = [s[{col!r}].dropna() for _, s in df.groupby({g!r})]\nF, p = stats.f_oneway(*groups)\n"
                f"posthoc = stats.tukey_hsd(*groups)")
    return out


# --------------------------------------------------------------------------- chi-square

def chi_square(ctx: Ctx) -> OpOutput:
    alpha = _alpha(ctx)
    a, b = ctx.plan.target_columns[0], ctx.plan.target_columns[1]
    d = ctx.df[[a, b]].dropna()
    if len(d) < 5:
        raise AnalysisError("Too few complete rows for a chi-square test.")
    da, db = limit_categories(d[a].astype(str), 30), limit_categories(d[b].astype(str), 30)
    obs = pd.crosstab(da, db)
    if obs.shape[0] < 2 or obs.shape[1] < 2:
        raise AnalysisError("Chi-square needs at least 2 categories in each variable.")
    chi2, p, dof, exp = stats.chi2_contingency(obs.values, correction=(obs.shape == (2, 2)))
    n = float(obs.values.sum())
    r_, c_ = obs.shape
    v = float(np.sqrt(chi2 / (n * min(r_ - 1, c_ - 1))))
    # Bergsma bias-corrected Cramér's V is less inflated for small samples / big tables.
    phi2 = max(0.0, chi2 / n - (r_ - 1) * (c_ - 1) / (n - 1))
    rc, cc = r_ - (r_ - 1) ** 2 / (n - 1), c_ - (c_ - 1) ** 2 / (n - 1)
    v_corr = float(np.sqrt(phi2 / min(rc - 1, cc - 1))) if min(rc, cc) > 1 else float("nan")
    low_exp = float((exp < 5).mean())
    warnings: List[str] = []
    fisher = None
    if low_exp > 0.2:
        warnings.append(f"{low_exp * 100:.0f}% of cells have an expected count below 5 (rule of thumb: ≤ 20%), so the chi-square approximation may be unreliable.")
        if obs.shape == (2, 2):
            odds, pf = stats.fisher_exact(obs.values)
            fisher = {"test": "Fisher's exact", "p_value": float(pf), "odds_ratio": float(odds)}
            warnings.append("Fisher's exact test is reported for this 2×2 table; prefer it here.")
    if d[a].nunique() > 30 or d[b].nunique() > 30:
        warnings.append("High-cardinality column(s): only the 30 most frequent categories were kept (others grouped as 'Other').")
    resid = (obs.values - exp) / np.sqrt(exp)
    out = OpOutput(columns_used=[a, b], records_used=int(n), warnings=warnings)
    out.metrics = {
        "test": "Chi-square test of independence" + (" (Yates-corrected)" if obs.shape == (2, 2) else ""),
        "null_hypothesis": f"'{a}' and '{b}' are independent", "alternative_hypothesis": "the variables are associated", "alpha": alpha,
        "statistic_chi2": float(chi2), "df": int(dof), "p_value": float(p), "significant": bool(p < alpha), "n": int(n),
        "effect_size": {"cramers_v": v, "cramers_v_bias_corrected": v_corr, "magnitude": "small" if v < 0.3 else "medium" if v < 0.5 else "large"},
        "expected_below_5_fraction": low_exp, "fisher_exact": fisher,
        "assumptions": [{"check": "expected counts ≥ 5 in ≥ 80% of cells", "group": "all", "checked": True, "passed": bool(low_exp <= 0.2)}],
    }
    out.tables.append(make_table("observed", obs.reset_index(), ctx.row_cap))
    out.tables.append(make_table("expected", pd.DataFrame(exp, index=obs.index, columns=obs.columns).round(3).reset_index(), ctx.row_cap))
    out.tables.append(make_table("standardised_residuals", pd.DataFrame(resid, index=obs.index, columns=obs.columns).round(3).reset_index(), ctx.row_cap))
    out.charts.append(charts.grouped_bar("observed_bar", f"{a} × {b} (observed counts)", [str(i) for i in obs.index], {str(c): obs[c].tolist() for c in obs.columns}, a, "Count", stacked=True))
    out.charts.append(charts.heatmap("residual_heat", "Standardised residuals (|value| > 2 ≈ notable cell)", np.round(resid, 3).tolist(), [str(c) for c in obs.columns],
                                     [str(i) for i in obs.index], xlabel=b, ylabel=a))
    out.interpretation = (f"χ²({dof}) = {fmt(chi2, 3)}, n = {int(n)}; {_sig_text(p, alpha)} Cramér's V = {fmt(v, 3)} ({out.metrics['effect_size']['magnitude']} association). "
                          "Cells with standardised residuals beyond ±2 contribute most to any association.")
    out.summary = f"Chi-square test of '{a}' × '{b}': χ² = {fmt(chi2, 3)}, df = {dof}, p {('= ' + fmt_p(p)) if p >= 1e-4 else fmt_p(p)}, Cramér's V = {fmt(v, 3)}."
    out.warnings.append("A significant association does not imply causation. This is an exploratory test; running many tests inflates the chance of false positives.")
    out.exclusions = missing_note(ctx, [a, b], int(n))
    out.methodology = ("Pearson chi-square test of independence on the contingency table of complete pairs (Yates continuity correction for 2×2). "
                       "Effect size: Cramér's V (plain and bias-corrected). Expected counts are checked against the ≥5 rule of thumb.")
    out.missing_value_handling = "Rows missing either variable are excluded."
    out.code = f"obs = pd.crosstab(df[{a!r}], df[{b!r}])\nchi2, p, dof, expected = stats.chi2_contingency(obs)"
    return out


# --------------------------------------------------------------------------- non-parametric

def mann_whitney(ctx: Ctx) -> OpOutput:
    alpha = _alpha(ctx)
    d, col, g, levels = _two_groups(ctx)
    a = d.loc[d[g].astype(str) == levels[0], col].astype(float)
    b = d.loc[d[g].astype(str) == levels[1], col].astype(float)
    if len(a) < 2 or len(b) < 2:
        raise AnalysisError("Each group needs at least 2 observations for the Mann-Whitney U test.")
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    n1, n2 = len(a), len(b)
    rb = float(2 * u / (n1 * n2) - 1)  # rank-biserial correlation; + means group A tends to have larger values
    cles = float(u / (n1 * n2))
    out = OpOutput()
    _group_outputs(out, ctx, d, col, g, levels)
    out.metrics = {"test": "Mann-Whitney U (two-sided)", "null_hypothesis": f"the distributions of {col} in the two groups are identical (no stochastic dominance)",
                   "alternative_hypothesis": "values in one group tend to be larger", "alpha": alpha, "groups": levels, "n": [n1, n2],
                   "medians": [float(a.median()), float(b.median())], "statistic_U": float(u), "p_value": float(p), "significant": bool(p < alpha),
                   "effect_size": {"rank_biserial_r": rb, "probability_of_superiority": cles, "magnitude": _cohen_label(rb * 2)},
                   "assumptions": [{"check": "independent observations, ordinal-or-better scale", "group": "all", "checked": False, "note": "cannot be verified from the data"}]}
    out.interpretation = (f"Median {levels[0]!r} = {fmt(a.median())} (n={n1}) vs {levels[1]!r} = {fmt(b.median())} (n={n2}). U = {fmt(u, 2)}; {_sig_text(p, alpha)} "
                          f"Rank-biserial r = {fmt(rb, 3)}; the chance that a random {levels[0]!r} value exceeds a random {levels[1]!r} value is {cles * 100:.1f}%.")
    out.summary = f"Mann-Whitney U = {fmt(u, 2)}, p {('= ' + fmt_p(p)) if p >= 1e-4 else fmt_p(p)} ({'significant' if p < alpha else 'not significant'} at α = {alpha:g})."
    if min(n1, n2) < 8:
        out.warnings.append("Very small groups: the exact test has little power.")
    out.warnings.append("This is an exploratory test; running many tests inflates the chance of false positives.")
    out.methodology = "Mann-Whitney U (Wilcoxon rank-sum), two-sided; compares distributions via ranks, robust to non-normality and outliers. Effect size: rank-biserial correlation and probability of superiority."
    out.missing_value_handling = "Rows missing the measure or group are excluded."
    out.code = f"u, p = stats.mannwhitneyu(a, b, alternative='two-sided')  # a, b = values of {col!r} per {g!r} group"
    return out


def kruskal_wallis(ctx: Ctx) -> OpOutput:
    alpha = _alpha(ctx)
    col, g = ctx.plan.column, ctx.plan.group_by[0]
    d = ctx.df[[col, g]].dropna()
    counts = d[g].astype(str).value_counts()
    names = [k for k in counts.index[:30] if counts[k] >= 2]
    if len(names) < 3:
        raise AnalysisError("Kruskal-Wallis needs at least 3 groups with 2+ observations (use Mann-Whitney for two).")
    series = [d.loc[d[g].astype(str) == k, col].astype(float) for k in names]
    h, p = stats.kruskal(*series)
    k, n = len(series), sum(len(s) for s in series)
    eps2 = float((h - k + 1) / (n - k)) if n > k else float("nan")
    out = OpOutput()
    _group_outputs(out, ctx, d, col, g, names)
    post = []
    if p < alpha and k <= 12:
        npairs = k * (k - 1) // 2
        for i, j in combinations(range(k), 2):
            u, pp = stats.mannwhitneyu(series[i], series[j], alternative="two-sided")
            post.append({"group_a": names[i], "group_b": names[j], "p_value": float(pp), "p_bonferroni": float(min(1.0, pp * npairs)), "significant": bool(min(1.0, pp * npairs) < alpha)})
        out.tables.append(table_from_rows("post_hoc_pairwise_mwu", ["group_a", "group_b", "p_value", "p_bonferroni", "significant"], post, ctx.row_cap))
        out.warnings.append(f"Post-hoc pairs use Mann-Whitney U with Bonferroni adjustment across {npairs} comparisons.")
    out.metrics = {"test": "Kruskal-Wallis H", "null_hypothesis": f"the distribution of {col} is the same in all groups", "alternative_hypothesis": "at least one group differs", "alpha": alpha,
                   "groups": names, "n": [len(s) for s in series], "medians": [float(s.median()) for s in series], "statistic_H": float(h), "df": k - 1, "p_value": float(p),
                   "significant": bool(p < alpha), "effect_size": {"epsilon_squared": eps2}, "post_hoc": post,
                   "assumptions": [{"check": "independent observations; similar distribution shapes for a pure median comparison", "group": "all", "checked": False, "note": "cannot be verified from the data"}]}
    out.interpretation = f"H({k - 1}) = {fmt(h, 3)}, n = {n}; {_sig_text(p, alpha)} ε² = {fmt(eps2, 3)}."
    out.summary = f"Kruskal-Wallis H = {fmt(h, 3)}, p {('= ' + fmt_p(p)) if p >= 1e-4 else fmt_p(p)} ({'significant' if p < alpha else 'not significant'} at α = {alpha:g})."
    if min(len(s) for s in series) < 5:
        out.warnings.append("Some groups have fewer than 5 observations; the chi-square approximation for H is unreliable.")
    out.warnings.append("This is an exploratory test; running many tests inflates the chance of false positives.")
    out.methodology = "Kruskal-Wallis rank-based test across ≥3 groups (α as stated); effect size ε² = (H − k + 1)/(n − k)."
    out.missing_value_handling = "Rows missing the measure or group are excluded; groups with fewer than 2 observations are dropped."
    out.code = f"H, p = stats.kruskal(*[s[{col!r}].dropna() for _, s in df.groupby({g!r})])"
    return out


def wilcoxon_signed_rank(ctx: Ctx) -> OpOutput:
    alpha = _alpha(ctx)
    a, b, ac, bc = _paired(ctx)
    diff = a - b
    nz = diff[diff != 0]
    if len(nz) < 3:
        raise AnalysisError("Fewer than 3 non-zero paired differences; the Wilcoxon signed-rank test cannot be computed.")
    w, p = stats.wilcoxon(nz)
    ranks = stats.rankdata(nz.abs())
    wp, wm = float(ranks[nz > 0].sum()), float(ranks[nz < 0].sum())
    rb = (wp - wm) / (wp + wm)
    out = OpOutput(columns_used=[ac, bc], records_used=len(diff))
    out.metrics = {"test": "Wilcoxon signed-rank (two-sided)", "null_hypothesis": f"the median of ({ac} − {bc}) is 0", "alternative_hypothesis": "the median difference is not 0", "alpha": alpha,
                   "n_pairs": int(len(diff)), "n_nonzero_differences": int(len(nz)), "median_difference": float(diff.median()), "statistic_W": float(w), "p_value": float(p),
                   "significant": bool(p < alpha), "effect_size": {"rank_biserial_r": float(rb)}, "assumptions": [{"check": "differences are symmetric about the median", "group": "differences", "checked": False, "note": "inspect the histogram"}]}
    out.charts.append(charts.histogram_bars("diff_hist", f"Paired differences ({ac} − {bc})", *_hist(diff), f"{ac} − {bc}", None, float(diff.median())))
    out.interpretation = f"Median paired difference {fmt(diff.median())}; W = {fmt(w, 2)}; {_sig_text(p, alpha)} Rank-biserial r = {fmt(rb, 3)}."
    out.summary = f"Wilcoxon signed-rank W = {fmt(w, 2)}, p {('= ' + fmt_p(p)) if p >= 1e-4 else fmt_p(p)} (n = {len(diff)} pairs, {len(nz)} non-zero)."
    if len(diff) - len(nz):
        out.warnings.append(f"{len(diff) - len(nz)} pair(s) had a zero difference and were dropped from the ranking (Wilcoxon's convention).")
    out.warnings.append("This is an exploratory test; running many tests inflates the chance of false positives.")
    out.exclusions = missing_note(ctx, [ac, bc], len(diff))
    out.methodology = "Wilcoxon signed-rank test on within-row differences (zero differences dropped), two-sided; effect size: matched-pairs rank-biserial correlation."
    out.missing_value_handling = "A row is used only if both values are present."
    out.code = f"d = df[[{ac!r}, {bc!r}]].dropna()\ndiff = d[{ac!r}] - d[{bc!r}]\nW, p = stats.wilcoxon(diff[diff != 0])"
    return out
