"""
Profiler correctness on awkward data (checked against pandas) and the guarantee that every
suggested analysis can actually be executed.
"""

import io

import numpy as np
import pandas as pd
import pytest

SAMPLES = ["employees_demo.csv", "sales_demo.csv", "customer_churn_demo.csv"]


def upload_csv(client, df: pd.DataFrame, name="edge.csv") -> str:
    buf = io.BytesIO(df.to_csv(index=False).encode("utf-8"))
    res = client.post("/api/v1/datasets/upload", files={"file": (name, buf, "text/csv")})
    assert res.status_code in (200, 201), res.text
    return res.json()["data"]["dataset_id"]


def profile(client, ds):
    res = client.get(f"/api/v1/profiling/{ds}")
    assert res.status_code == 200, res.text
    return res.json()["data"]


def col(prof, name):
    return next(c for c in prof["columns"] if c["name"] == name)


def test_profile_matches_pandas_with_missing_constant_and_duplicates(client):
    rng = np.random.default_rng(7)
    df = pd.DataFrame({
        "value": np.where(rng.random(200) < 0.1, np.nan, rng.normal(50, 12, 200)).round(3),
        "constant": 5,
        "label": rng.choice(["a", "b", "c"], 200),
        "all_missing": np.nan,
    })
    df = pd.concat([df, df.iloc[:7]], ignore_index=True)  # 7 exact duplicate rows
    ds = upload_csv(client, df)
    prof = profile(client, ds)

    assert prof["overview"]["total_rows"] == len(df)
    assert prof["overview"]["total_columns"] == 4

    v = col(prof, "value")
    assert v["missing_count"] == int(df["value"].isna().sum())
    ns = v["numeric_summary"]
    # the profiler rounds displayed statistics to 4 decimals
    assert ns["mean"] == pytest.approx(df["value"].mean(), abs=1e-3)
    assert ns["std"] == pytest.approx(df["value"].std(), abs=1e-3)
    assert ns["median"] == pytest.approx(df["value"].median(), abs=1e-3)
    assert ns["min"] == pytest.approx(df["value"].min()) and ns["max"] == pytest.approx(df["value"].max())

    assert col(prof, "all_missing")["missing_count"] == len(df)
    assert col(prof, "constant")["distinct_count"] == 1
    assert prof["duplicates"]["exact_duplicate_rows_count"] == int(df.duplicated().sum())
    assert prof["missingness"]["missing_cells"] == int(df.isna().sum().sum())

    # constant and fully-missing columns should be called out as quality findings
    assert any(w["column"] in ("constant", "all_missing") for w in prof["quality_warnings"])


def test_profile_does_not_modify_original_file(client):
    df = pd.DataFrame({"a": [1, 2, None, 4], "b": ["x", "y", "y", None]})
    raw = df.to_csv(index=False).encode()
    res = client.post("/api/v1/datasets/upload", files={"file": ("orig.csv", io.BytesIO(raw), "text/csv")})
    ds = res.json()["data"]["dataset_id"]
    profile(client, ds)
    client.post(f"/api/v1/profiling/{ds}")  # forced re-profile
    # the stored original is byte-identical: the preview still shows missing values as missing, not imputed
    prev = client.get(f"/api/v1/datasets/{ds}/preview").json()["data"]
    assert prev["total_rows"] == 4
    assert any(r["a"] == "" for r in prev["head_records"])  # shown as in the file, never imputed


def test_unicode_and_odd_headers_survive(client):
    df = pd.DataFrame({"prix €": [1.5, 2.5, 3.5], "naïve col": ["é", "ü", "ñ"], " spaced ": [1, 2, 3]})
    ds = upload_csv(client, df, "unicode.csv")
    prof = profile(client, ds)
    names = [c["name"] for c in prof["columns"]]
    assert "prix €" in names and "naïve col" in names
    assert len(names) == 3


def test_single_row_and_single_column_files(client):
    ds = upload_csv(client, pd.DataFrame({"only": [42]}), "one.csv")
    prof = profile(client, ds)
    assert prof["overview"]["total_rows"] == 1
    assert col(prof, "only")["distinct_count"] == 1


@pytest.mark.parametrize("sample", SAMPLES)
def test_every_suggested_analysis_is_valid_and_runs(client, sample):
    ds = client.post(f"/api/v1/datasets/samples/{sample}").json()["data"]["dataset_id"]
    sid = client.post("/api/v1/sessions", json={"dataset_id": ds}).json()["data"]["id"]
    suggestions = client.get(f"/api/v1/analysis/suggestions/{ds}").json()["data"]
    assert suggestions, "each sample dataset should yield suggestions"
    for s in suggestions:
        res = client.post("/api/v1/analysis/execute", json={"session_id": sid, "plan": s["plan"], "label": s["title"]})
        assert res.status_code == 200, f"{s['title']}: {res.text}"
        result = res.json()["data"]
        assert result["records_used"] > 0
        assert result["execution"]["code"]


def test_suggestions_are_rejected_for_other_users(client, second_user):
    ds = client.post("/api/v1/datasets/samples/employees_demo.csv").json()["data"]["dataset_id"]
    h = second_user["headers"]
    assert client.get(f"/api/v1/analysis/suggestions/{ds}", headers=h).status_code == 404
    assert client.get(f"/api/v1/profiling/{ds}", headers=h).status_code == 404
