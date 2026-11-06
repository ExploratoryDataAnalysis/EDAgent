"""
Advanced exploratory analytics: K-Means clustering, PCA, linear regression and a focused
classification workflow.

Principles applied throughout:
  * Preprocessing is explicit and reported (listwise deletion, scaling, encoding) - nothing is
    imputed or removed from the stored dataset; only the model's working copy is affected.
  * All scalers/encoders/imputers live inside a scikit-learn Pipeline fitted on the *training*
    split only, so no information from the test split leaks into preprocessing.
  * Randomness is seeded from the plan (default 42) so every run is reproducible.
  * These are exploratory baselines, not validated predictive systems - results say so.
"""

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, calinski_harabasz_score, confusion_matrix, davies_bouldin_score,
    precision_recall_fscore_support, roc_auc_score, roc_curve, silhouette_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from app.core.config import settings
from app.schemas.analysis import ExclusionNote
from app.services.analysis import charts
from app.services.analysis.common import (
    AnalysisError, Ctx, OpOutput, coerce_warnings, fmt, fmt_p, make_table, missing_note, table_from_rows,
)

MAX_DRAW = 5000


def _complete_numeric(ctx: Ctx, cols: List[str], min_rows: int, what: str) -> pd.DataFrame:
    """Listwise-deleted numeric matrix; raises a clear error when too little data remains."""
    X = ctx.df[cols].astype(float).dropna()
    if len(X) < min_rows:
        raise AnalysisError(f"Only {len(X)} complete row(s) remain across the selected columns after removing rows with missing values; {what} needs at least {min_rows}.")
    const = [c for c in cols if X[c].nunique() < 2]
    if const:
        raise AnalysisError(f"Constant column(s) carry no information and cannot be used: {', '.join(const)}. Remove them and retry.")
    return X


def _preprocessing_text(n_total: int, n_used: int) -> str:
    return (f"Listwise deletion: {n_total - n_used:,} of {n_total:,} rows with a missing value in any selected column were left out of the model; "
            f"{n_used:,} complete rows were used. Features are standardised (mean 0, SD 1) in memory only; the dataset itself is never changed.")


# --------------------------------------------------------------------------- K-Means

def kmeans(ctx: Ctx) -> OpOutput:
    p = ctx.plan
    cols = list(p.target_columns)
    X = _complete_numeric(ctx, cols, 20, "K-Means")
    n_all = len(X)
    out = OpOutput(columns_used=cols, records_used=n_all)
    out.warnings += coerce_warnings(ctx, cols)
    scaler = StandardScaler().fit(X)
    Xs_all = scaler.transform(X)
    rng_idx = np.random.default_rng(p.seed)
    if n_all > settings.MAX_MODELLING_ROWS:
        fit_idx = rng_idx.choice(n_all, settings.MAX_MODELLING_ROWS, replace=False)
        out.approximate = True
        out.sampling_note = f"Centroids were fitted on a seeded random sample of {settings.MAX_MODELLING_ROWS:,} of {n_all:,} rows; every row was then assigned to its nearest centroid."
        out.warnings.append(out.sampling_note)
        scaler = StandardScaler().fit(X.iloc[fit_idx])
        Xs_all = scaler.transform(X)
        Xs_fit = Xs_all[fit_idx]
    else:
        Xs_fit = Xs_all

    requested = ctx.param("n_clusters", 3)
    sweep_rows = []
    if requested == "auto":
        # Pick k with the best silhouette between 2 and 8; the whole sweep is shown for transparency.
        sub = Xs_fit if len(Xs_fit) <= 5000 else Xs_fit[rng_idx.choice(len(Xs_fit), 5000, replace=False)]
        best_k, best_s = 2, -1.0
        for k in range(2, min(9, len(sub))):
            km = KMeans(n_clusters=k, n_init=10, random_state=p.seed).fit(sub)
            s = float(silhouette_score(sub, km.labels_))
            sweep_rows.append({"k": k, "silhouette": s, "inertia": float(km.inertia_)})
            if s > best_s:
                best_k, best_s = k, s
        k = best_k
        out.tables.append(table_from_rows("k_selection", ["k", "silhouette", "inertia"], sweep_rows, ctx.row_cap))
        out.warnings.append(f"k = {k} was chosen automatically as the value with the highest silhouette score between 2 and 8; this is a heuristic, not a ground truth.")
    else:
        try:
            k = int(requested)
        except (TypeError, ValueError):
            raise AnalysisError("n_clusters must be an integer between 2 and 12, or 'auto'.")
        if not 2 <= k <= 12:
            raise AnalysisError("n_clusters must be between 2 and 12.")
    if k >= len(Xs_fit):
        raise AnalysisError(f"Cannot form {k} clusters from {len(Xs_fit)} rows.")

    model = KMeans(n_clusters=k, n_init=10, random_state=p.seed).fit(Xs_fit)
    labels = model.predict(Xs_all)
    sizes = np.bincount(labels, minlength=k)
    ss = Xs_all if len(Xs_all) <= 10000 else Xs_all[rng_idx.choice(len(Xs_all), 10000, replace=False)]
    sl = labels if len(Xs_all) <= 10000 else labels[rng_idx.choice(len(Xs_all), 10000, replace=False)]  # noqa: E501
    # (silhouette needs >= 2 distinct labels in the evaluated subset)
    sil = float(silhouette_score(ss, sl)) if len(set(sl)) > 1 else float("nan")
    db = float(davies_bouldin_score(Xs_all, labels)) if len(set(labels)) > 1 else float("nan")
    ch = float(calinski_harabasz_score(Xs_all, labels)) if len(set(labels)) > 1 else float("nan")

    centroids = pd.DataFrame(scaler.inverse_transform(model.cluster_centers_), columns=cols)
    summ = pd.DataFrame({"cluster": range(k), "size": sizes, "percent": sizes / n_all * 100})
    means = X.assign(_c=labels).groupby("_c")[cols].mean().reset_index(drop=True)
    summ = pd.concat([summ, means.add_prefix("mean_")], axis=1)
    out.tables.append(make_table("cluster_summary", summ, ctx.row_cap))
    out.tables.append(make_table("centroids_original_scale", centroids.assign(cluster=range(k))[["cluster"] + cols], ctx.row_cap))
    assign = X.copy()
    assign.insert(0, "cluster", labels)
    assign.insert(0, "row_number", X.index.to_numpy() + 1)
    out.tables.append(make_table("cluster_assignments", assign, ctx.row_cap))

    # 2-D view: the two original features if only two were chosen, else the first two principal components.
    if len(cols) == 2:
        coords, xl, yl = X.to_numpy(), cols[0], cols[1]
    else:
        pc = PCA(n_components=2, random_state=p.seed).fit(Xs_all)
        coords = pc.transform(Xs_all)
        xl, yl = f"PC1 ({pc.explained_variance_ratio_[0] * 100:.1f}% var.)", f"PC2 ({pc.explained_variance_ratio_[1] * 100:.1f}% var.)"
    draw = np.arange(len(coords)) if len(coords) <= MAX_DRAW else rng_idx.choice(len(coords), MAX_DRAW, replace=False)
    out.charts.append(charts.scatter("cluster_scatter", f"K-Means clusters (k = {k})", [
        {"name": f"cluster {c} (n={int(sizes[c])})", "x": coords[draw][labels[draw] == c, 0].tolist(), "y": coords[draw][labels[draw] == c, 1].tolist()} for c in range(k)], xl, yl))
    out.charts.append(charts.bar("cluster_sizes", "Cluster sizes", [f"cluster {c}" for c in range(k)], sizes.tolist(), "cluster", "rows", text=[f"{s / n_all * 100:.1f}%" for s in sizes]))
    if len(coords) > MAX_DRAW:
        out.warnings.append(f"The scatter plot shows a seeded sample of {MAX_DRAW:,} points; all metrics and assignments use every row.")

    out.metrics = {"k": k, "n_rows": int(n_all), "inertia": float(model.inertia_), "silhouette": sil, "davies_bouldin": db, "calinski_harabasz": ch,
                   "cluster_sizes": sizes.tolist(), "features": cols, "scaling": "StandardScaler (z-score)", "seed": p.seed, "n_init": 10}
    quality = "weak" if sil < 0.25 else "fair" if sil < 0.5 else "good" if sil < 0.7 else "strong"
    out.summary = (f"K-Means with k = {k} on {len(cols)} standardised feature(s) over {fmt(n_all)} rows: sizes {', '.join(str(int(s)) for s in sizes)}; "
                   f"silhouette {fmt(sil, 3)} ({quality} separation), Davies-Bouldin {fmt(db, 3)}.")
    out.interpretation = ("Cluster means in the summary table describe each segment in original units. Silhouette ranges from −1 to 1 (higher = better separated); "
                          "Davies-Bouldin is better when lower. Clusters are a descriptive partition of this data, not proof that natural groups exist.")
    if min(sizes) / n_all < 0.02:
        out.warnings.append("At least one cluster holds under 2% of the rows; it may be driven by outliers.")
    if sil < 0.25:
        out.warnings.append("Low silhouette score: the data may not contain well-separated clusters at this k.")
    out.warnings.append("K-Means assumes roughly spherical, similarly sized clusters and is sensitive to outliers and to the features chosen.")
    out.exclusions = missing_note(ctx, cols, n_all)
    out.methodology = (_preprocessing_text(ctx.df.shape[0], n_all) + f" K-Means (k-means++ initialisation, n_init = 10, random_state = {p.seed}). "
                       "Evaluation: inertia, silhouette (≤10,000 rows), Davies-Bouldin and Calinski-Harabasz indices.")
    out.missing_value_handling = "Listwise deletion across the selected feature columns (rows with any missing feature are not clustered)."
    out.code = (f"X = df[{cols!r}].astype(float).dropna()\nXs = StandardScaler().fit_transform(X)\n"
                f"km = KMeans(n_clusters={k}, n_init=10, random_state={p.seed}).fit(Xs)\nlabels = km.labels_")
    return out


# --------------------------------------------------------------------------- PCA

def pca(ctx: Ctx) -> OpOutput:
    p = ctx.plan
    explicit = bool(p.target_columns)
    cols = list(p.target_columns) if explicit else ctx.loaded.numeric_columns()
    if len(cols) < 2:
        raise AnalysisError("PCA needs at least two numeric columns.")
    if len(cols) > 50:
        raise AnalysisError("PCA is limited to 50 columns at a time.")
    X = _complete_numeric(ctx, cols, max(10, len(cols) + 1), "PCA")
    n = len(X)
    standardize = bool(ctx.param("standardize", True))
    nc = int(ctx.param("n_components", min(len(cols), 10)))
    nc = max(2, min(nc, len(cols), n - 1))
    out = OpOutput(columns_used=cols, records_used=n)
    out.warnings += coerce_warnings(ctx, cols)
    if not explicit:
        out.warnings.append("Columns were chosen automatically from numeric measures (identifiers and numeric codes excluded).")
    Z = StandardScaler().fit_transform(X) if standardize else (X - X.mean()).to_numpy()
    model = PCA(n_components=nc, random_state=p.seed, svd_solver="full").fit(Z)
    scores = model.transform(Z)
    ratio = model.explained_variance_ratio_
    cum = np.cumsum(ratio)
    ev = model.explained_variance_
    names = [f"PC{i + 1}" for i in range(nc)]
    out.tables.append(table_from_rows("explained_variance", ["component", "eigenvalue", "explained_percent", "cumulative_percent"],
                                      [{"component": names[i], "eigenvalue": float(ev[i]), "explained_percent": float(ratio[i] * 100), "cumulative_percent": float(cum[i] * 100)} for i in range(nc)], ctx.row_cap))
    # Loadings = eigenvector × sqrt(eigenvalue): for standardised data these are the correlations between a feature and a component.
    load = pd.DataFrame(model.components_.T * np.sqrt(ev), index=cols, columns=names)
    out.tables.append(make_table("loadings", load.round(4).reset_index().rename(columns={"index": "feature"}), ctx.row_cap))
    top = []
    for i, nm in enumerate(names[:min(nc, 5)]):
        s = load[nm].abs().sort_values(ascending=False).head(3).index
        top.append({"component": nm, "top_features": ", ".join(f"{f} ({load.loc[f, nm]:+.2f})" for f in s)})
    out.tables.append(table_from_rows("top_loadings", ["component", "top_features"], top, ctx.row_cap))

    scree = {"data": [{"type": "bar", "name": "explained variance %", "x": names, "y": (ratio * 100).tolist(), "marker": {"color": charts.PALETTE[0]}},
                      {"type": "scatter", "mode": "lines+markers", "name": "cumulative %", "x": names, "y": (cum * 100).tolist(), "line": {"color": charts.PALETTE[3]}}],
             "layout": charts._layout("Scree plot", "component", "explained variance (%)", yaxis={"title": {"text": "explained variance (%)"}, "range": [0, 105]})}
    out.charts.append(charts.chart("scree", "bar", "Scree plot", scree["data"], scree["layout"]))
    draw = np.arange(n) if n <= MAX_DRAW else np.random.default_rng(p.seed).choice(n, MAX_DRAW, replace=False)
    color_by = ctx.param("color_by")
    groups: List[Dict[str, Any]] = []
    if color_by and color_by in ctx.df.columns:
        lab = ctx.df.loc[X.index, color_by].astype(str).to_numpy()[draw]
        for g in pd.Series(lab).value_counts().index[:10]:
            m = lab == g
            groups.append({"name": str(g), "x": scores[draw][m, 0].tolist(), "y": scores[draw][m, 1].tolist()})
    else:
        groups.append({"name": "observations", "x": scores[draw, 0].tolist(), "y": scores[draw, 1].tolist()})
    out.charts.append(charts.scatter("pca_scores", "PCA scores (PC1 vs PC2)", groups, f"PC1 ({ratio[0] * 100:.1f}%)", f"PC2 ({ratio[1] * 100:.1f}%)"))
    out.charts.append(charts.heatmap("pca_loadings", "Component loadings", load.round(3).values.tolist(), names, cols, -1, 1))
    if n > MAX_DRAW:
        out.warnings.append(f"The scores plot shows a seeded sample of {MAX_DRAW:,} points; the decomposition uses every complete row.")
    n80 = int(np.searchsorted(cum, 0.80) + 1) if cum[-1] >= 0.80 else None
    n90 = int(np.searchsorted(cum, 0.90) + 1) if cum[-1] >= 0.90 else None
    kaiser = int((ev > 1).sum()) if standardize else None
    out.metrics = {"n_rows": n, "n_features": len(cols), "n_components": nc, "standardized": standardize, "explained_variance_ratio": ratio.tolist(),
                   "cumulative_variance": cum.tolist(), "components_for_80_percent": n80, "components_for_90_percent": n90, "kaiser_components": kaiser, "seed": p.seed}
    out.summary = (f"PCA on {len(cols)} {'standardised ' if standardize else ''}feature(s), {fmt(n)} rows: PC1 explains {ratio[0] * 100:.1f}% and PC1-PC2 together {cum[1] * 100:.1f}% of the variance"
                   + (f"; {n80} component(s) reach 80%." if n80 else "."))
    out.interpretation = ("Loadings show how strongly each original feature contributes to a component (for standardised data they equal the feature-component correlation). "
                          "Components are linear combinations: PCA summarises variance, it does not identify causes or guarantee the leading components are the most relevant ones.")
    if not standardize:
        out.warnings.append("PCA was run on unscaled data, so features with larger units dominate. Standardising is usually recommended.")
        if X.var().max() / max(X.var().min(), 1e-12) > 100:
            out.warnings.append("Feature variances differ by more than 100×, which makes unscaled PCA misleading.")
    out.warnings.append("The sign of a component is arbitrary (flipping it gives an equivalent solution). PCA captures linear structure only and is sensitive to outliers.")
    out.exclusions = missing_note(ctx, cols, n)
    out.methodology = (_preprocessing_text(ctx.df.shape[0], n).replace("Features are standardised", "Features are standardised" if standardize else "Features are only mean-centred (not scaled)") +
                       f" Principal components from a full SVD (scikit-learn PCA), {nc} component(s) retained.")
    out.missing_value_handling = "Listwise deletion across the selected feature columns."
    out.code = (f"X = df[{cols!r}].astype(float).dropna()\nZ = StandardScaler().fit_transform(X)\n"
                f"pca = PCA(n_components={nc}).fit(Z)\nscores = pca.transform(Z)")
    return out


# --------------------------------------------------------------------------- linear regression

def _design(ctx: Ctx, features: List[str], rows: pd.Index) -> Tuple[pd.DataFrame, List[str]]:
    """Builds the design matrix: numeric as-is, categorical one-hot (first level dropped)."""
    parts: List[pd.DataFrame] = []
    notes: List[str] = []
    for f in features:
        s = ctx.df.loc[rows, f]
        if ctx.info(f).is_numeric:
            parts.append(s.astype(float).to_frame(f))
        else:
            levels = s.astype(str).nunique()
            if levels > 15:
                raise AnalysisError(f"Categorical predictor '{f}' has {levels} levels (limit 15); it would create too many dummy variables.")
            dum = pd.get_dummies(s.astype(str), prefix=f, prefix_sep="=", drop_first=True, dtype=float)
            notes.append(f"'{f}' was one-hot encoded; reference level = {sorted(s.astype(str).unique())[0]!r}.")
            parts.append(dum)
    return pd.concat(parts, axis=1), notes


def _ols(X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    n, p1 = X.shape
    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    fitted = X @ beta
    resid = y - fitted
    rss = float(resid @ resid)
    dfree = n - p1
    sigma2 = rss / dfree if dfree > 0 else float("nan")
    se = np.sqrt(np.diag(xtx_inv) * sigma2)
    return {"beta": beta, "fitted": fitted, "resid": resid, "rss": rss, "df": dfree, "sigma2": sigma2, "se": se, "xtx_inv": xtx_inv}


def linear_regression(ctx: Ctx) -> OpOutput:
    p = ctx.plan
    target, feats = p.column, list(p.target_columns)
    if target in feats:
        raise AnalysisError("The target column cannot also be a predictor.")
    cols = [target] + feats
    d = ctx.df[cols].dropna()
    n = len(d)
    out = OpOutput(columns_used=cols, records_used=n)
    out.warnings += coerce_warnings(ctx, cols)
    Xdf, enc_notes = _design(ctx, feats, d.index)
    names = list(Xdf.columns)
    k = len(names)
    if n < k + 5:
        raise AnalysisError(f"Only {n} complete row(s) for {k} predictor term(s); need at least {k + 5}.")
    y = d[target].astype(float).to_numpy()
    if np.std(y) == 0:
        raise AnalysisError(f"Target '{target}' is constant; regression is undefined.")
    X = np.column_stack([np.ones(n), Xdf.to_numpy()])
    if np.linalg.matrix_rank(X) < X.shape[1]:
        raise AnalysisError("Predictors are perfectly collinear (one is a linear combination of others). Remove redundant predictors and retry.")
    fit = _ols(X, y)
    beta, se, dfree = fit["beta"], fit["se"], fit["df"]
    tvals = beta / se
    pvals = 2 * stats.t.sf(np.abs(tvals), dfree)
    tcrit = stats.t.ppf(0.975, dfree)
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - fit["rss"] / tss
    adj = 1 - (1 - r2) * (n - 1) / dfree
    fstat = ((tss - fit["rss"]) / k) / (fit["rss"] / dfree)
    fp = float(stats.f.sf(fstat, k, dfree))
    rmse, mae = float(np.sqrt(fit["rss"] / n)), float(np.mean(np.abs(fit["resid"])))
    ysd = float(np.std(y, ddof=1))
    coef_rows = []
    for i, nm in enumerate(["(intercept)"] + names):
        xsd = float(np.std(X[:, i], ddof=1)) if i else None
        coef_rows.append({"term": nm, "coefficient": float(beta[i]), "std_error": float(se[i]), "t": float(tvals[i]), "p_value": float(pvals[i]),
                          "ci95_low": float(beta[i] - tcrit * se[i]), "ci95_high": float(beta[i] + tcrit * se[i]),
                          "std_beta": float(beta[i] * xsd / ysd) if xsd else None})
    out.tables.append(table_from_rows("coefficients", ["term", "coefficient", "std_error", "t", "p_value", "ci95_low", "ci95_high", "std_beta"], coef_rows, ctx.row_cap))

    # --- diagnostics
    resid, fitted = fit["resid"], fit["fitted"]
    h = np.einsum("ij,jk,ik->i", X, fit["xtx_inv"], X)  # leverage = diag of the hat matrix
    cooks = (resid ** 2 / ((k + 1) * fit["sigma2"])) * h / np.clip(1 - h, 1e-12, None) ** 2
    infl = int((cooks > 4 / n).sum())
    dw = float(np.sum(np.diff(resid) ** 2) / np.sum(resid ** 2))
    shap_p = None
    if 3 <= n:
        sample = resid if n <= 5000 else np.random.default_rng(p.seed).choice(resid, 5000, replace=False)
        shap_p = float(stats.shapiro(sample).pvalue)
    # Breusch-Pagan: regress squared residuals on the predictors; LM = n·R² ~ χ²(k)
    aux = _ols(X, resid ** 2)
    tss_aux = float(((resid ** 2 - (resid ** 2).mean()) ** 2).sum())
    r2_aux = 1 - aux["rss"] / tss_aux if tss_aux > 0 else 0.0
    bp_p = float(stats.chi2.sf(n * r2_aux, k))
    vifs = []
    if k >= 2:
        for j in range(k):
            others = np.column_stack([np.ones(n), np.delete(Xdf.to_numpy(), j, axis=1)])
            f2 = _ols(others, Xdf.to_numpy()[:, j])
            tss_j = float(((Xdf.to_numpy()[:, j] - Xdf.to_numpy()[:, j].mean()) ** 2).sum())
            r2_j = 1 - f2["rss"] / tss_j if tss_j > 0 else 0.0
            vifs.append({"term": names[j], "vif": float(1 / (1 - r2_j)) if r2_j < 1 else float("inf")})
        out.tables.append(table_from_rows("multicollinearity_vif", ["term", "vif"], vifs, ctx.row_cap))
    diag = [{"diagnostic": "Durbin-Watson (≈2 = no autocorrelation)", "value": dw},
            {"diagnostic": "Shapiro-Wilk p-value of residuals", "value": shap_p},
            {"diagnostic": "Breusch-Pagan p-value (heteroscedasticity)", "value": bp_p},
            {"diagnostic": f"Influential points (Cook's D > 4/n)", "value": infl},
            {"diagnostic": "Max leverage", "value": float(h.max())}]
    out.tables.append(table_from_rows("diagnostics", ["diagnostic", "value"], diag, ctx.row_cap))

    # --- holdout evaluation on a separate train/test split (inference above uses all complete rows)
    hold = None
    if n >= 40:
        tr, te = train_test_split(np.arange(n), test_size=0.2, random_state=p.seed)
        ftr = _ols(X[tr], y[tr])
        pred = X[te] @ ftr["beta"]
        ss_res, ss_tot = float(((y[te] - pred) ** 2).sum()), float(((y[te] - y[te].mean()) ** 2).sum())
        hold = {"n_train": int(len(tr)), "n_test": int(len(te)), "r2": float(1 - ss_res / ss_tot) if ss_tot > 0 else None,
                "rmse": float(np.sqrt(ss_res / len(te))), "mae": float(np.mean(np.abs(y[te] - pred)))}
    out.metrics = {"n": n, "n_predictors": k, "r_squared": r2, "adj_r_squared": adj, "rmse": rmse, "mae": mae, "f_statistic": float(fstat), "f_p_value": fp, "df_residual": int(dfree),
                   "residual_std_error": float(np.sqrt(fit["sigma2"])), "durbin_watson": dw, "shapiro_p_residuals": shap_p, "breusch_pagan_p": bp_p, "influential_points": infl,
                   "max_vif": max((v["vif"] for v in vifs), default=None), "holdout": hold, "coefficients": {r["term"]: r["coefficient"] for r in coef_rows}}

    # --- charts (sampled for drawing only)
    draw = np.arange(n) if n <= MAX_DRAW else np.random.default_rng(p.seed).choice(n, MAX_DRAW, replace=False)
    lo, hi = float(min(y.min(), fitted.min())), float(max(y.max(), fitted.max()))
    out.charts.append(charts.scatter("actual_vs_predicted", "Actual vs predicted", [{"name": "observations", "x": fitted[draw].tolist(), "y": y[draw].tolist()}], "predicted", "actual",
                                     {"name": "perfect fit", "x": [lo, hi], "y": [lo, hi]}))
    out.charts.append(charts.scatter("residuals_vs_fitted", "Residuals vs fitted (look for a patternless band)", [{"name": "residuals", "x": fitted[draw].tolist(), "y": resid[draw].tolist()}], "fitted", "residual",
                                     {"name": "zero", "x": [float(fitted.min()), float(fitted.max())], "y": [0, 0]}))
    counts, edges = np.histogram(resid, bins="auto")
    out.charts.append(charts.histogram_bars("residual_hist", "Residual distribution", edges.tolist(), counts.tolist(), "residual", float(resid.mean()), float(np.median(resid))))
    cf = [r for r in coef_rows if r["term"] != "(intercept)"]
    out.charts.append(charts.bar("coefficients", "Coefficients with 95% CI", [r["term"] for r in cf], [r["coefficient"] for r in cf], "term", "coefficient",
                                 horizontal=True, error=[tcrit * r["std_error"] for r in cf]))
    if n > MAX_DRAW:
        out.warnings.append(f"Diagnostic scatter plots show a seeded sample of {MAX_DRAW:,} points; all statistics use every complete row.")

    # --- warnings & interpretation
    out.warnings += enc_notes
    if n < 10 * k:
        out.warnings.append(f"Only {n / k:.1f} observations per predictor (≥10 recommended): coefficients may be unstable.")
    if vifs and max(v["vif"] for v in vifs) > 10:
        out.warnings.append("Severe multicollinearity (VIF > 10): coefficient estimates are unstable and hard to interpret individually.")
    elif vifs and max(v["vif"] for v in vifs) > 5:
        out.warnings.append("Moderate multicollinearity (VIF > 5) among predictors.")
    if shap_p is not None and shap_p < 0.05:
        out.warnings.append("Residuals deviate from normality (Shapiro-Wilk p < 0.05); confidence intervals and p-values are approximate.")
    if bp_p < 0.05:
        out.warnings.append("Evidence of heteroscedasticity (Breusch-Pagan p < 0.05): residual spread changes with the predictors, so standard errors may be too small.")
    if infl:
        out.warnings.append(f"{infl} observation(s) have Cook's distance > 4/n and may disproportionately influence the fit.")
    if abs(dw - 2) > 0.7:
        out.warnings.append("Durbin-Watson is far from 2; if rows are ordered in time, residuals may be autocorrelated (ignore if row order is arbitrary).")
    out.warnings.append("Regression describes association in this dataset; coefficients are not causal effects, and extrapolating beyond the observed range is unreliable.")
    sig = sorted([r for r in cf if r["p_value"] < 0.05], key=lambda r: r["p_value"])
    out.summary = (f"Linear regression of '{target}' on {len(feats)} predictor(s) (n = {fmt(n)}): R² = {r2:.3f} (adjusted {adj:.3f}), RMSE {fmt(rmse)}, "
                   f"F-test p {('= ' + fmt_p(fp)) if fp >= 1e-4 else fmt_p(fp)}."
                   + (f" Strongest term: '{sig[0]['term']}' (coef {fmt(sig[0]['coefficient'])}, p {fmt_p(sig[0]['p_value'])})." if sig else " No individual term is significant at 5%."))
    out.interpretation = (f"The model explains {r2 * 100:.1f}% of the variance in '{target}' on the data it was fitted to"
                          + (f"; on a held-out 20% split R² was {hold['r2']:.3f} (RMSE {fmt(hold['rmse'])})." if hold and hold["r2"] is not None else ".")
                          + " Each coefficient is the expected change in the target for a one-unit increase in that predictor, holding the others fixed.")
    out.exclusions = missing_note(ctx, cols, n)
    out.methodology = (_preprocessing_text(ctx.df.shape[0], n).replace("Features are standardised (mean 0, SD 1) in memory only; the dataset itself is never changed.", "Predictors are used in original units (categoricals one-hot encoded); the dataset itself is never changed.")
                       + " Ordinary least squares with an intercept; t-tests/CIs on coefficients (df = n − p − 1); diagnostics: Durbin-Watson, Shapiro-Wilk, Breusch-Pagan, VIF, Cook's distance. "
                         "Holdout metrics (if shown) come from a separate OLS fit on a seeded 80/20 split. This is exploratory modelling, not a validated predictive model.")
    out.missing_value_handling = "Listwise deletion across the target and all predictors."
    out.code = (f"d = df[{cols!r}].dropna()\nX = sm.add_constant(pd.get_dummies(d[{feats!r}], drop_first=True).astype(float))\nmodel = sm.OLS(d[{target!r}].astype(float), X).fit()\nprint(model.summary())"
                "\n# (EDAgent fits the same OLS model with NumPy/SciPy; statsmodels shown for convenience)")
    return out


# --------------------------------------------------------------------------- classification

def _build_model(kind: str, class_weight: Any, seed: int) -> Any:
    if kind == "logistic_regression":
        return LogisticRegression(max_iter=2000, class_weight=class_weight, random_state=seed)
    if kind == "random_forest":
        return RandomForestClassifier(n_estimators=200, min_samples_leaf=2, class_weight=class_weight, random_state=seed, n_jobs=1)
    if kind == "decision_tree":
        return DecisionTreeClassifier(max_depth=5, class_weight=class_weight, random_state=seed)
    raise AnalysisError("model must be one of logistic_regression, random_forest, decision_tree.")


def classification(ctx: Ctx) -> OpOutput:
    p = ctx.plan
    target = p.column
    out = OpOutput()
    feats = [f for f in p.target_columns if f != target]
    auto = not feats
    if auto:
        feats = [c for c, i in ctx.columns.items() if c != target and i.role in ("measure", "category", "boolean") and i.distinct_count <= max(50, 1)][:30]
        out.warnings.append("No predictors were specified, so numeric measures and low-cardinality categories were used (identifiers and free text are excluded).")
    if not feats:
        raise AnalysisError("No suitable predictor columns were found. Choose predictors explicitly.")
    if target in p.target_columns:
        out.warnings.append("The target was removed from the predictor list to prevent leakage.")
    for f in feats:
        if ctx.info(f).role == "identifier" and not auto:
            out.warnings.append(f"'{f}' looks like an identifier; identifiers rarely generalise and can leak information. Consider removing it.")

    impute = str(ctx.param("impute", "none"))
    model_kind = str(ctx.param("model", "logistic_regression"))
    test_size = float(ctx.param("test_size", 0.2))
    if not 0.1 <= test_size <= 0.5:
        raise AnalysisError("test_size must be between 0.1 and 0.5.")
    cw = "balanced" if ctx.param("class_weight") == "balanced" else None

    d = ctx.df[[target] + feats]
    d = d[d[target].notna()]  # rows without a label can never be used
    n_total_rows = len(ctx.df)
    if impute == "none":
        d = d.dropna()
    n = len(d)
    out.columns_used = [target] + feats
    out.records_used = n
    if n < 20:
        raise AnalysisError(f"Only {n} usable row(s) after removing rows with missing values; classification needs at least 20.")
    y_raw = d[target].astype(str)
    classes = y_raw.value_counts()
    if classes.size < 2:
        raise AnalysisError(f"Target '{target}' has only one class; there is nothing to predict.")
    if classes.size > 20:
        raise AnalysisError(f"Target '{target}' has {classes.size} classes; classification is limited to 20 (is it a continuous or identifier column?).")
    if classes.min() < 2:
        rare = ", ".join(classes[classes < 2].index[:5])
        raise AnalysisError(f"Class(es) with a single example cannot be split into train/test: {rare}. Filter them out or merge them first.")
    if n > settings.MAX_MODELLING_ROWS:
        d = d.sample(settings.MAX_MODELLING_ROWS, random_state=p.seed)
        y_raw = d[target].astype(str)
        classes = y_raw.value_counts()
        out.approximate = True
        out.sampling_note = f"Modelling used a seeded random sample of {settings.MAX_MODELLING_ROWS:,} of {n:,} usable rows."
        out.warnings.append(out.sampling_note)
        n = len(d)

    num = [f for f in feats if ctx.info(f).is_numeric]
    cat = [f for f in feats if f not in num]
    for f in cat:
        if d[f].astype(str).nunique() > 30:
            raise AnalysisError(f"Predictor '{f}' has more than 30 distinct values; one-hot encoding would explode. Remove it or choose a lower-cardinality column.")
    X = d[feats].copy()
    for f in cat:
        X[f] = X[f].astype(object).where(X[f].notna(), np.nan).map(lambda v: v if pd.isna(v) else str(v))

    num_steps = ([("impute", SimpleImputer(strategy="median"))] if impute != "none" else []) + [("scale", StandardScaler())]
    cat_steps = ([("impute", SimpleImputer(strategy="most_frequent"))] if impute != "none" else []) + [("onehot", OneHotEncoder(handle_unknown="ignore"))]
    pre = ColumnTransformer([("num", Pipeline(num_steps), num), ("cat", Pipeline(cat_steps), cat)], remainder="drop")
    pipe = Pipeline([("pre", pre), ("model", _build_model(model_kind, cw, p.seed))])
    baseline = Pipeline([("pre", pre), ("model", DummyClassifier(strategy="most_frequent"))])

    strat = y_raw if classes.min() >= 2 and int(n * test_size) >= classes.size else None
    X_tr, X_te, y_tr, y_te = train_test_split(X, y_raw, test_size=test_size, random_state=p.seed, stratify=strat)
    if strat is None:
        out.warnings.append("The split could not be stratified (too few rows per class); class proportions may differ between train and test.")
    pipe.fit(X_tr, y_tr)
    baseline.fit(X_tr, y_tr)
    pred, pred_tr = pipe.predict(X_te), pipe.predict(X_tr)
    labels = sorted(classes.index.tolist())
    acc, bacc = float(accuracy_score(y_te, pred)), float(balanced_accuracy_score(y_te, pred))
    base_acc = float(accuracy_score(y_te, baseline.predict(X_te)))
    train_acc = float(accuracy_score(y_tr, pred_tr))
    prec, rec, f1, sup = precision_recall_fscore_support(y_te, pred, labels=labels, zero_division=0)
    macro = precision_recall_fscore_support(y_te, pred, average="macro", zero_division=0)[:3]
    weighted = precision_recall_fscore_support(y_te, pred, average="weighted", zero_division=0)[:3]
    cm = confusion_matrix(y_te, pred, labels=labels)

    roc_auc = None
    roc_trace = None
    proba = pipe.predict_proba(X_te) if hasattr(pipe, "predict_proba") else None
    if proba is not None:
        cls_order = list(pipe.classes_)
        try:
            if len(cls_order) == 2 and y_te.nunique() == 2:
                pos = cls_order[1]
                yb = (y_te == pos).astype(int)
                roc_auc = float(roc_auc_score(yb, proba[:, 1]))
                fpr, tpr, _ = roc_curve(yb, proba[:, 1])
                keep = np.linspace(0, len(fpr) - 1, min(len(fpr), 200)).astype(int)
                roc_trace = {"fpr": fpr[keep].tolist(), "tpr": tpr[keep].tolist(), "positive": pos}
            elif len(cls_order) > 2 and y_te.nunique() == len(cls_order):
                roc_auc = float(roc_auc_score(y_te, proba, multi_class="ovr", average="macro", labels=cls_order))
        except ValueError:
            roc_auc = None

    cv = None
    n_tr = len(X_tr)
    if n_tr >= 50 and classes.min() >= 5:
        folds = 5 if n_tr >= 100 else 3
        scores = cross_val_score(pipe, X_tr, y_tr, cv=StratifiedKFold(folds, shuffle=True, random_state=p.seed), scoring="accuracy")
        cv = {"folds": folds, "mean_accuracy": float(scores.mean()), "std": float(scores.std())}

    # Feature importance in the model's transformed space (one-hot columns keep their names).
    feat_names = list(pipe.named_steps["pre"].get_feature_names_out())
    m = pipe.named_steps["model"]
    if hasattr(m, "coef_"):
        imp = np.abs(m.coef_).mean(axis=0) if m.coef_.shape[0] > 1 else m.coef_[0]
        imp_label = "coefficient (standardised features)" if len(labels) == 2 else "mean |coefficient|"
    else:
        imp, imp_label = m.feature_importances_, "importance"
    imp_df = pd.DataFrame({"feature": [f.split("__", 1)[-1] for f in feat_names], "importance": imp}).sort_values("importance", key=lambda s: s.abs(), ascending=False).head(15)

    # --- tables & charts
    cls_rows = [{"class": labels[i], "precision": float(prec[i]), "recall": float(rec[i]), "f1": float(f1[i]), "support": int(sup[i])} for i in range(len(labels))]
    out.tables.append(table_from_rows("per_class_metrics", ["class", "precision", "recall", "f1", "support"], cls_rows, ctx.row_cap))
    out.tables.append(make_table("confusion_matrix", pd.DataFrame(cm, index=[f"actual {l}" for l in labels], columns=[f"predicted {l}" for l in labels]).reset_index().rename(columns={"index": "actual"}), ctx.row_cap))
    out.tables.append(make_table("feature_importance", imp_df, ctx.row_cap))
    out.charts.append(charts.heatmap("confusion", "Confusion matrix (test set)", cm.tolist(), [f"pred {l}" for l in labels], [f"actual {l}" for l in labels], diverging=False, fmt_text=False, xlabel="predicted", ylabel="actual"))
    out.charts[-1].spec["data"][0].update({"text": [[str(int(v)) for v in row] for row in cm], "texttemplate": "%{text}"})
    if roc_trace:
        out.charts.append(charts.line("roc", f"ROC curve (AUC = {roc_auc:.3f}, positive class = {roc_trace['positive']})", [
            {"name": "model", "x": roc_trace["fpr"], "y": roc_trace["tpr"]}, {"name": "chance", "x": [0, 1], "y": [0, 1], "dash": "dot"}], "false positive rate", "true positive rate"))
    out.charts.append(charts.bar("importance", f"Top features ({imp_label})", imp_df["feature"].tolist(), imp_df["importance"].tolist(), "feature", imp_label, horizontal=True))

    minority = float(classes.min() / classes.sum())
    out.metrics = {"model": model_kind, "n_used": int(n), "n_train": int(len(X_tr)), "n_test": int(len(X_te)), "classes": labels, "class_counts": {k: int(v) for k, v in classes.items()},
                   "accuracy": acc, "balanced_accuracy": bacc, "baseline_accuracy_majority_class": base_acc, "train_accuracy": train_acc,
                   "precision_macro": float(macro[0]), "recall_macro": float(macro[1]), "f1_macro": float(macro[2]),
                   "precision_weighted": float(weighted[0]), "recall_weighted": float(weighted[1]), "f1_weighted": float(weighted[2]),
                   "roc_auc": roc_auc, "cross_validation": cv, "minority_class_share": minority, "features": feats, "test_size": test_size, "seed": p.seed,
                   "class_weight": cw or "none", "imputation": "median/most-frequent (fit on training split)" if impute != "none" else "none (listwise deletion)"}
    out.summary = (f"{model_kind.replace('_', ' ').title()} predicting '{target}' ({len(labels)} classes) from {len(feats)} feature(s): test accuracy {acc:.3f} "
                   f"(majority-class baseline {base_acc:.3f}), balanced accuracy {bacc:.3f}, macro F1 {macro[2]:.3f}" + (f", ROC-AUC {roc_auc:.3f}." if roc_auc is not None else "."))
    out.interpretation = (f"Evaluated on {len(X_te):,} held-out rows that were never used for fitting or preprocessing. "
                          + ("The model beats the trivial majority-class baseline." if acc > base_acc + 0.01 else "The model does not clearly beat always predicting the majority class.")
                          + " This is an exploratory baseline from a single random split, not a validated predictive model.")
    # warnings
    if minority < 0.10:
        out.warnings.append(f"Class imbalance: the smallest class is only {minority * 100:.1f}% of the data. Accuracy can look high while the minority class is missed; rely on recall/F1 and balanced accuracy, or try class_weight='balanced'.")
    if base_acc >= 0.9:
        out.warnings.append(f"A model that always predicts the majority class already scores {base_acc:.3f}, so accuracy alone is misleading.")
    if len(X_tr) < 100 or classes.min() < 10:
        out.warnings.append("Small sample (fewer than 100 training rows or fewer than 10 examples in a class): metrics from one split are very noisy.")
    if train_acc - acc > 0.15:
        out.warnings.append(f"Training accuracy ({train_acc:.3f}) is much higher than test accuracy ({acc:.3f}): the model is likely overfitting.")
    if acc >= 0.999 and len(X_te) >= 10:
        out.warnings.append("Test accuracy is (nearly) perfect, which is unusual. Check whether a predictor leaks the answer (e.g. a column derived from the target).")
    # single-feature leakage screen for numeric predictors vs a binary target
    if len(labels) == 2:
        yb = (y_raw == labels[1]).astype(float)
        for f in num:
            col = d[f].astype(float)
            if col.nunique() > 1 and col.notna().sum() > 5:
                r = abs(np.corrcoef(col.fillna(col.median()), yb)[0, 1])
                if r > 0.98:
                    out.warnings.append(f"'{f}' is almost perfectly correlated with the target (|r| = {r:.3f}); it may leak the answer.")
    out.exclusions = []
    miss_t = int(ctx.df[target].isna().sum())
    if miss_t:
        out.exclusions.append(ExclusionNote(reason="missing target label", count=miss_t, column=target))
    if impute == "none":
        out.exclusions += [e for e in missing_note(ctx, feats, n) if e.column in feats]
    out.warnings += coerce_warnings(ctx, [target] + feats)
    out.methodology = (f"{model_kind.replace('_', ' ')} (scikit-learn) with a stratified {int((1 - test_size) * 100)}/{int(test_size * 100)} train/test split (random_state = {p.seed}). "
                       "Numeric features are standardised and categorical features one-hot encoded inside a Pipeline fitted on the training split only (no leakage into the test set). "
                       + ("Missing feature values are imputed (median / most-frequent) using training data only. " if impute != "none" else "Rows with missing values in the target or any feature are excluded (listwise). ")
                       + "Metrics are computed on the held-out test split; a majority-class dummy model provides the baseline. ROC-AUC is one-vs-rest macro for multi-class targets. "
                         "Cross-validation (training split only) is shown when there is enough data.")
    out.missing_value_handling = "Rows with a missing target are dropped; features: " + ("listwise deletion." if impute == "none" else "imputed inside the training pipeline.")
    out.code = (f"X, y = df[{feats!r}], df[{target!r}].astype(str)\nX_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size={test_size}, random_state={p.seed}, stratify=y)\n"
                f"pre = ColumnTransformer([('num', StandardScaler(), {num!r}), ('cat', OneHotEncoder(handle_unknown='ignore'), {cat!r})])\n"
                f"model = Pipeline([('pre', pre), ('clf', {_build_model(model_kind, cw, p.seed)!r})]).fit(X_tr, y_tr)\nprint(classification_report(y_te, model.predict(X_te)))")
    return out
