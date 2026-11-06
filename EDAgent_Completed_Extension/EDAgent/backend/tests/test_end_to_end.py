"""
The full user journey from the specification, run against the real API:

 upload -> preview -> profile -> suggestions -> AI question -> plan -> execute -> chart/table ->
 contextual follow-up -> downloads -> PDF + HTML report -> restore session -> delete everything.
"""

import io
import json
import os
import time
import zipfile

import openpyxl
import pytest

from app.services.ai.llm import set_llm_client_override
from tests.test_chat_flow import FakeLLM, plan_reply


def wait_for(client, job_id, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(f"/api/v1/jobs/{job_id}").json()["data"]
        if job["status"] in ("SUCCESS", "FAILURE", "REVOKED"):
            return job
        time.sleep(0.2)
    raise AssertionError("job did not finish in time")


def test_full_workflow(client):
    # 1. upload + preview + profile
    up = client.post("/api/v1/datasets/samples/employees_demo.csv").json()["data"]
    ds = up["dataset_id"]
    prev = client.get(f"/api/v1/datasets/{ds}/preview").json()["data"]
    assert prev["total_rows"] == 600 and "salary" in prev["column_names"]
    prof = client.get(f"/api/v1/profiling/{ds}").json()["data"]
    assert prof["overview"]["total_rows"] == 600
    sugg = client.get(f"/api/v1/analysis/suggestions/{ds}").json()["data"]
    assert len(sugg) >= 5

    # 2. session + AI question
    sid = client.post("/api/v1/sessions", json={"dataset_id": ds}).json()["data"]["id"]
    set_llm_client_override(FakeLLM(
        planner=lambda u: plan_reply(operation="time_trend", column="salary", date_column="hire_date", aggregation="mean", interval="year", parameters={"compare_with": "previous_year"})
        if "Plan used" in u else plan_reply(operation="group_by", column="salary", group_by=["department"], aggregation="mean"),
        explainer="Average salary differs by department; see the table for each figure.",
    ))
    first = client.post("/api/v1/chat/message", json={"session_id": sid, "message": "Average salary by department?"}).json()["data"]
    assert first["kind"] == "analysis" and first["analysis_result"]["tables"] and first["analysis_result"]["charts"]
    result_id = first["analysis_result"]["id"]

    # 3. contextual follow-up
    second = client.post("/api/v1/chat/message", json={"session_id": sid, "message": "Now show the yearly trend and compare it with last year"}).json()["data"]
    assert second["kind"] == "analysis" and second["analysis_plan"]["operation"] == "time_trend"

    # 4. downloads
    chart_id = first["analysis_result"]["charts"][0]["id"]
    for fmt, magic in [("png", b"\x89PNG"), ("svg", b"<?xml"), ("html", b"<html")]:
        r = client.get(f"/api/v1/exports/results/{result_id}/charts/{chart_id}?format={fmt}")
        assert r.status_code == 200 and magic in r.content[:200].lower().replace(b"<!doctype", b"<html") or r.content.startswith(magic), fmt
    csv_resp = client.get(f"/api/v1/exports/results/{result_id}/tables/0?format=csv")
    assert csv_resp.status_code == 200 and b"department" in csv_resp.content
    x = client.get(f"/api/v1/exports/results/{result_id}/tables/0?format=xlsx")
    wb = openpyxl.load_workbook(io.BytesIO(x.content))
    assert wb.active.max_row == 6  # header + 5 departments
    meta = client.get(f"/api/v1/exports/results/{result_id}/metadata").json()
    assert meta["plan"]["operation"] == "group_by" and meta["exact_or_sampled"].startswith("exact")
    code = client.get(f"/api/v1/exports/results/{result_id}/code").text
    compile(code.replace("\r", ""), "reproduce.py", "exec")  # the exported code is valid Python
    bundle = client.get(f"/api/v1/exports/results/{result_id}/bundle")
    names = zipfile.ZipFile(io.BytesIO(bundle.content)).namelist()
    assert any(n.endswith("metadata.json") for n in names) and any(n.endswith(".png") for n in names)
    assert client.get(f"/api/v1/exports/sessions/{sid}/bundle").status_code == 200
    assert client.get(f"/api/v1/exports/datasets/{ds}/profile?format=xlsx").status_code == 200

    # 5. reports (PDF + HTML, concise + detailed)
    outputs = {}
    for fmt, concise in [("pdf", False), ("html", False), ("pdf", True)]:
        r = client.post("/api/v1/reports/generate", json={"session_id": sid, "format": fmt, "concise_mode": concise, "title": f"Test <b>report</b> {fmt}"})
        assert r.status_code == 202, r.text
        rep = r.json()["data"]
        job = wait_for(client, rep["job_id"])
        assert job["status"] == "SUCCESS", job
        dl = client.get(f"/api/v1/reports/{rep['report_id']}/download")
        assert dl.status_code == 200
        outputs[(fmt, concise)] = dl.content
    assert outputs[("pdf", False)].startswith(b"%PDF") and len(outputs[("pdf", False)]) > len(outputs[("pdf", True)])
    html = outputs[("html", False)].decode()
    for title in ["Cover and dataset information", "Executive summary", "Missing-value analysis", "Duplicate analysis", "Relevant correlations", "Reproducibility information"]:
        assert title in html
    assert "&lt;b&gt;report&lt;/b&gt;" in html and "<b>report</b>" not in html  # user text is escaped
    assert "AI-written" in html and "Computed" in html  # profiler vs AI text is labelled

    # 6. restore session: everything is still there, including charts
    restored = client.get(f"/api/v1/sessions/{sid}").json()["data"]
    assert [t["kind"] for t in restored["turns"]] == ["analysis", "analysis"]
    assert restored["turns"][0]["result"]["tables"][0]["rows"][0]
    assert any(s["id"] == sid for s in client.get("/api/v1/sessions").json()["data"])

    # 7. deletion cleans up rows and files
    rep_list = client.get(f"/api/v1/reports?session_id={sid}").json()["data"]
    assert len(rep_list) == 3
    storage_files = []
    from app.services.export_storage import export_path
    from app.services import dataset_service
    for r in rep_list:
        storage_files.append(export_path(f"reports/{client.current_user['id']}/{r['report_id']}.{r['format']}"))
    assert all(os.path.isfile(p) for p in storage_files)
    dataset_dir = os.path.dirname(dataset_service.absolute_path(up["storage_uri"]))
    assert os.path.isdir(dataset_dir)
    assert client.delete(f"/api/v1/datasets/{ds}").status_code == 200
    assert not any(os.path.exists(p) for p in storage_files) and not os.path.exists(dataset_dir)
    assert client.get(f"/api/v1/sessions/{sid}").status_code == 404
    assert client.get(f"/api/v1/analysis/results/{result_id}").status_code == 404


def test_report_and_export_isolation(client, second_user):
    ds = client.post("/api/v1/datasets/samples/sales_demo.csv").json()["data"]["dataset_id"]
    sid = client.post("/api/v1/sessions", json={"dataset_id": ds}).json()["data"]["id"]
    res = client.post("/api/v1/analysis/execute", json={"session_id": sid, "plan": {"operation": "frequency", "column": "region"}}).json()["data"]
    rep = client.post("/api/v1/reports/generate", json={"session_id": sid, "format": "html"}).json()["data"]
    wait_for(client, rep["job_id"])
    other = second_user["headers"]
    for path in [
        f"/api/v1/reports/{rep['report_id']}", f"/api/v1/reports/{rep['report_id']}/download", f"/api/v1/jobs/{rep['job_id']}",
        f"/api/v1/exports/results/{res['id']}/metadata", f"/api/v1/exports/results/{res['id']}/bundle", f"/api/v1/exports/sessions/{sid}/bundle",
        f"/api/v1/exports/datasets/{ds}/profile", f"/api/v1/analysis/suggestions/{ds}",
    ]:
        assert client.get(path, headers=other).status_code == 404, path
    assert client.post("/api/v1/reports/generate", json={"session_id": sid}, headers=other).status_code == 404
    assert client.delete(f"/api/v1/reports/{rep['report_id']}", headers=other).status_code == 404
    assert client.get(f"/api/v1/reports/{rep['report_id']}/download").status_code == 200


def test_async_analysis_job(client):
    ds = client.post("/api/v1/datasets/samples/customer_churn_demo.csv").json()["data"]["dataset_id"]
    sid = client.post("/api/v1/sessions", json={"dataset_id": ds}).json()["data"]["id"]
    plan = {"operation": "classification", "column": "churned", "target_columns": ["tenure_months", "monthly_charges", "contract", "support_tickets"], "parameters": {"model": "logistic_regression"}}
    r = client.post("/api/v1/analysis/execute-async", json={"session_id": sid, "plan": plan})
    assert r.status_code == 202, r.text
    job = wait_for(client, r.json()["data"]["job_id"])
    assert job["status"] == "SUCCESS" and job["progress_percentage"] == 100
    res = client.get(f"/api/v1/analysis/results/{job['result_ref']['result_id']}").json()["data"]
    assert res["operation"] == "classification" and "accuracy" in json.dumps(res["metrics"]).lower()
    bad = client.post("/api/v1/analysis/execute-async", json={"session_id": sid, "plan": {"operation": "histogram", "column": "nope"}})
    assert bad.status_code == 422


def test_job_concurrency_limit_and_cancel(client, monkeypatch):
    from app.core.config import settings
    from app.services.jobs import runner

    monkeypatch.setattr(settings, "MAX_CONCURRENT_JOBS_PER_USER", 1)
    uid = __import__("uuid").UUID(client.current_user["id"])
    first = runner.create_job(user_id=uid, job_type="analysis")
    with pytest.raises(runner.JobLimitError):
        runner.create_job(user_id=uid, job_type="analysis")
    assert client.post(f"/api/v1/jobs/{first}/cancel").json()["data"]["cancelled"] is True
    runner.create_job(user_id=uid, job_type="analysis")  # a slot is free again
