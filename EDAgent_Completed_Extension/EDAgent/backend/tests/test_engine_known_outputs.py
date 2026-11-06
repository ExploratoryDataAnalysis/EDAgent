"""Known-answer tests: tiny synthetic datasets whose correct results can be computed by hand or with scipy."""

import io
import uuid

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from app.schemas.analysis import StructuredAnalysisPlan
from app.services.analysis import engine
from app.services.analysis.common import AnalysisError, PlanValidationError
from app.services.data.loader import load_dataset
from app.services.profiler.profiler_engine import ProfilerEngine


def load(df: pd.DataFrame, tmp_path, name="d"):
    path = tmp_path / f"{name}.csv"
    df.to_csv(path, index=False)
    prof = ProfilerEngine.profile_dataset(str(path), "csv")
    return load_dataset(name + uuid.uuid4().hex, str(path), "csv", uuid.uuid4().hex, None, prof["columns"])


def run(loaded, **plan):
    return engine.run_analysis(loaded, StructuredAnalysisPlan(**plan), uuid.uuid4(), use_cache=False)


@pytest.fixture
def frame():
    rng = np.random.default_rng(1)
    n = 200
    g = rng.choice(["a", "b"], n)
    x = rng.normal(50, 10, n) + (g == "b") * 8
    y = 2 * x + rng.normal(0, 5, n)
    return pd.DataFrame({"g": g, "x": x.round(3), "y": y.round(3), "k": rng.choice(["u", "v", "w"], n)})


def test_descriptive_stats_match_pandas(frame, tmp_path):
    r = run(load(frame, tmp_path), operation="descriptive_stats", target_columns=["x"])
    row = r.tables[0].rows[0]
    assert row["mean"] == pytest.approx(frame.x.mean(), rel=1e-6)
    assert row["std"] == pytest.approx(frame.x.std(ddof=1), rel=1e-6)
    assert row["median"] == pytest.approx(frame.x.median(), rel=1e-6)
    assert r.records_used == 200 and not r.is_approximate


def test_pearson_spearman_match_scipy(frame, tmp_path):
    r = run(load(frame, tmp_path), operation="correlation", target_columns=["x", "y"], method="both")
    pairs = {row["method"]: row for row in r.tables[0].rows}
    assert pairs["pearson"]["r"] == pytest.approx(stats.pearsonr(frame.x, frame.y)[0], abs=1e-4)
    assert pairs["spearman"]["r"] == pytest.approx(stats.spearmanr(frame.x, frame.y)[0], abs=1e-4)
    assert pairs["pearson"]["n"] == 200


def test_welch_t_test_matches_scipy(frame, tmp_path):
    r = run(load(frame, tmp_path), operation="t_test_independent", column="x", group_by=["g"])
    a, b = frame[frame.g == "a"].x, frame[frame.g == "b"].x
    ref = stats.ttest_ind(a, b, equal_var=False)
    m = r.metrics
    assert m["statistic"] == pytest.approx(ref.statistic, abs=1e-3)
    assert m["df"] == pytest.approx(ref.df, rel=1e-4)
    assert m["p_value"] == pytest.approx(ref.pvalue, rel=1e-3, abs=1e-12)


def test_anova_and_chi_square_match_scipy(frame, tmp_path):
    loaded = load(frame, tmp_path)
    r = run(loaded, operation="anova_one_way", column="x", group_by=["k"])
    ref = stats.f_oneway(*[d.x for _, d in frame.groupby("k")])
    assert r.metrics["statistic_F"] == pytest.approx(ref.statistic, rel=1e-4)
    r2 = run(loaded, operation="chi_square", target_columns=["g", "k"])
    ct = pd.crosstab(frame.g, frame.k)
    chi = stats.chi2_contingency(ct)
    assert r2.metrics["statistic_chi2"] == pytest.approx(chi.statistic, rel=1e-4)
    assert r2.metrics["p_value"] == pytest.approx(chi.pvalue, rel=1e-4)


def test_linear_regression_matches_numpy(frame, tmp_path):
    r = run(load(frame, tmp_path), operation="linear_regression", column="y", target_columns=["x"])
    slope, intercept = np.polyfit(frame.x, frame.y, 1)
    coefs = {row["term"]: row for row in r.tables[0].rows}
    assert coefs["x"]["coefficient"] == pytest.approx(slope, rel=1e-4)
    assert coefs["intercept"]["coefficient"] == pytest.approx(intercept, rel=1e-3) if "intercept" in coefs else True
    assert r.metrics["r_squared"] == pytest.approx(np.corrcoef(frame.x, frame.y)[0, 1] ** 2, rel=1e-4)


def test_iqr_outliers_flag_but_never_remove(tmp_path):
    df = pd.DataFrame({"v": [10, 11, 12, 11, 10, 12, 11, 500], "c": list("abababab")})
    loaded = load(df, tmp_path)
    r = run(loaded, operation="outlier_iqr", column="v")
    assert "1" in r.summary_text and r.records_examined == 8
    assert loaded.n_rows == 8  # the data itself is untouched


def test_filters_and_or_logic_and_null_semantics(tmp_path):
    df = pd.DataFrame({"r": ["N", "S", "N", "E", None], "v": [1, 2, 3, 4, 5]})
    loaded = load(df, tmp_path)
    f_and = {"logic": "and", "conditions": [{"column": "r", "operator": "eq", "value": "N"}, {"column": "v", "operator": "gt", "value": 1}]}
    assert run(loaded, operation="filter_rows", filters=f_and).records_used == 1
    f_or = {"logic": "or", "conditions": [{"column": "r", "operator": "eq", "value": "S"}, {"column": "v", "operator": "gte", "value": 4}]}
    assert run(loaded, operation="filter_rows", filters=f_or).records_used == 3
    # SQL-like: a missing region does not match "not equal N"
    f_ne = {"logic": "and", "conditions": [{"column": "r", "operator": "ne", "value": "N"}]}
    assert run(loaded, operation="filter_rows", filters=f_ne).records_used == 2


def test_missing_values_are_excluded_and_reported_not_imputed(tmp_path):
    df = pd.DataFrame({"x": [1.0, 2.0, None, 4.0, None], "g": list("aabbb")})
    r = run(load(df, tmp_path), operation="descriptive_stats", target_columns=["x"])
    assert r.records_used == 3 and r.records_excluded == 2 and r.tables[0].rows[0]["mean"] == pytest.approx(7 / 3)
    with pytest.raises(AnalysisError):
        run(load(df, tmp_path, "d2"), operation="descriptive_stats", target_columns=["x"], missing_policy="fail_on_missing")


def test_sampling_is_labelled_and_seeded(tmp_path):
    df = pd.DataFrame({"x": np.arange(2000.0), "g": ["a", "b"] * 1000})
    loaded = load(df, tmp_path)
    r1 = run(loaded, operation="descriptive_stats", target_columns=["x"], scope="sample", sample_size=500, seed=7)
    r2 = run(loaded, operation="descriptive_stats", target_columns=["x"], scope="sample", sample_size=500, seed=7)
    assert r1.is_approximate and r1.sample_size == 500 and "sample" in r1.methodology.lower()
    assert r1.tables[0].rows[0]["mean"] == r2.tables[0].rows[0]["mean"]
    assert not run(loaded, operation="descriptive_stats", target_columns=["x"]).is_approximate


def test_invalid_plans_are_rejected_with_suggestions(frame, tmp_path):
    loaded = load(frame, tmp_path)
    with pytest.raises(PlanValidationError) as e:
        run(loaded, operation="histogram", column="xx")
    assert "x" in str(e.value)
    with pytest.raises(PlanValidationError):
        run(loaded, operation="histogram", column="g")  # categorical is not numeric


def test_classification_has_no_leakage_and_reports_metrics(tmp_path):
    rng = np.random.default_rng(3)
    n = 400
    a = rng.normal(0, 1, n)
    label = np.where(a + rng.normal(0, .8, n) > 0, "yes", "no")
    df = pd.DataFrame({"a": a, "noise": rng.normal(0, 1, n), "label": label})
    r = run(load(df, tmp_path), operation="classification", column="label", target_columns=["a", "noise"], parameters={"model": "logistic_regression"})
    m = r.metrics
    assert m["n_train"] + m["n_test"] == m["n_used"] == 400 and m["n_test"] == 80
    assert m["accuracy"] > 0.7 and m["accuracy"] > m["baseline_accuracy_majority_class"] + 0.1
    assert 0.5 < m["roc_auc"] <= 1.0
    for k in ("precision_macro", "recall_macro", "f1_macro"):
        assert 0 <= m[k] <= 1
    assert any("confusion" in t.name for t in r.tables)
    # Putting the target among the predictors must not leak it into the model.
    leaky = run(load(df, tmp_path, "leaky"), operation="classification", column="label", target_columns=["a", "label"])
    assert any("leakage" in w for w in leaky.warnings)
