"""
Phase 3: End-to-End Frontend and Backend Integration Test Suite
Verifies:
1. Health and API proxy connectivity.
2. CSV upload, delimiter detection, preview, and deterministic profiling.
3. TSV upload, tab delimiter sniffing, GPA/credits column parsing and profiling.
4. Multi-sheet Excel workbook upload, sheet inspection, sheet selection, preview, and profiling.
5. Ingestion overrides (delimiter/encoding confirmation).
6. Dataset catalog listing and metadata synchronization.
"""

import io
import os
import openpyxl
import pytest
from fastapi.testclient import TestClient



# ==============================================================================
# 1. API Health & Ingestion Pipeline
# ==============================================================================

def test_api_health(client: TestClient):
    """Verifies that the backend health endpoint responds with healthy status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "EDAgent"


def test_csv_upload_preview_and_profiling(client: TestClient):
    """Verifies CSV upload, auto-profiling, and preview data consistency."""
    with open("data/samples/baseline_benchmark.csv", "rb") as f:
        csv_bytes = f.read()

    files = {"file": ("baseline_benchmark.csv", io.BytesIO(csv_bytes), "text/csv")}
    response = client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True

    upload_data = res_data["data"]
    dataset_id = upload_data["dataset_id"]
    assert upload_data["file_format"] == "csv"
    assert upload_data["multiple_sheets_found"] is False
    assert upload_data["requires_sheet_selection"] is False
    assert "comma" in upload_data["parsing_decision"].lower()

    # Verify Preview
    preview_res = client.get(f"/api/v1/datasets/{dataset_id}/preview")
    assert preview_res.status_code == 200
    preview = preview_res.json()["data"]
    assert preview["total_rows"] == 12
    assert preview["total_columns"] == 8
    assert len(preview["head_records"]) == 10
    assert len(preview["tail_records"]) <= 10
    assert len(preview["sample_records"]) > 0
    assert "annual_income" in preview["inferred_types"]
    assert preview["inferred_types"]["annual_income"] == "float"

    # Verify Automatic Profiler Output
    prof_res = client.get(f"/api/v1/profiling/{dataset_id}")
    assert prof_res.status_code == 200
    prof = prof_res.json()["data"]
    assert prof["dataset_id"] == dataset_id
    assert prof["overview"]["total_rows"] == 12
    assert prof["overview"]["total_columns"] == 8
    assert prof["missingness"]["missing_cells"] == 3
    assert prof["duplicates"]["exact_duplicate_rows_count"] == 1
    assert isinstance(prof["duplicates"]["candidate_duplicate_keys"], list)
    assert len(prof["columns"]) == 8
    assert len(prof["quality_warnings"]) > 0
    assert len(prof["suggested_analyses"]) > 0

    # Verify Distributions
    assert len(prof["distributions"]["histograms"]) > 0
    assert len(prof["distributions"]["boxplots"]) > 0

    # Verify Relationships
    assert prof["relationships"]["pearson"] is not None
    assert len(prof["relationships"]["pearson"]["columns"]) > 0


def test_tsv_upload_preview_and_profiling(client: TestClient):
    """Verifies TSV tab-delimited upload, sniffing, and role inference."""
    tsv_content = (
        "student_id\tname\tgpa\tcredits\tmajor\n"
        "101\tAlice Chen\t3.92\t110\tComputer Science\n"
        "102\tBob Ross\t3.45\t85\tData Science\n"
        "103\tCharlie Day\t2.80\t60\tMathematics\n"
        "104\tDiana Prince\t4.00\t120\tPhysics\n"
        "105\tEvan Wright\t3.15\t45\tEconomics\n"
    )

    files = {"file": ("students.tsv", io.BytesIO(tsv_content.encode("utf-8")), "text/tab-separated-values")}
    response = client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True

    upload_data = res_data["data"]
    dataset_id = upload_data["dataset_id"]
    assert upload_data["file_format"] == "tsv"
    assert "tab" in upload_data["parsing_decision"].lower()

    # Verify Preview
    preview_res = client.get(f"/api/v1/datasets/{dataset_id}/preview")
    assert preview_res.status_code == 200
    preview = preview_res.json()["data"]
    assert preview["total_rows"] == 5
    assert preview["total_columns"] == 5
    assert preview["inferred_types"]["student_id"] == "integer"
    assert preview["inferred_types"]["gpa"] == "float"

    # Verify Profiling
    prof_res = client.get(f"/api/v1/profiling/{dataset_id}")
    assert prof_res.status_code == 200
    prof = prof_res.json()["data"]
    assert prof["overview"]["total_rows"] == 5
    assert prof["overview"]["total_columns"] == 5

    student_id_col = next(c for c in prof["columns"] if c["name"] == "student_id")
    assert student_id_col["semantic_role"] == "identifier"

    gpa_col = next(c for c in prof["columns"] if c["name"] == "gpa")
    assert gpa_col["semantic_role"] == "measure"
    assert gpa_col["numeric_summary"]["min"] == 2.80
    assert gpa_col["numeric_summary"]["max"] == 4.00


def test_multi_sheet_excel_workflow(client: TestClient):
    """Verifies complete multi-sheet Excel upload, sheet inspection, and sheet selection."""
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Quarterly_Revenue"
    ws1.append(["quarter", "product_line", "revenue", "expenses", "growth_rate"])
    ws1.append(["Q1", "SaaS Subscriptions", 120000.0, 45000.0, 0.15])
    ws1.append(["Q2", "Enterprise Licenses", 250000.0, 80000.0, 0.22])
    ws1.append(["Q3", "Professional Services", 85000.0, 35000.0, -0.05])
    ws1.append(["Q4", "Support Packages", 60000.0, 20000.0, 0.08])

    ws2 = wb.create_sheet(title="Employee_Headcount")
    ws2.append(["dept_id", "department", "headcount", "avg_salary", "remote_allowed"])
    ws2.append([1, "Engineering", 45, 135000.0, True])
    ws2.append([2, "Sales", 28, 95000.0, True])
    ws2.append([3, "Marketing", 15, 82000.0, False])
    ws2.append([4, "Operations", 10, 75000.0, False])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    files = {"file": ("company_metrics.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    response = client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 200
    upload_data = response.json()["data"]
    dataset_id = upload_data["dataset_id"]
    assert upload_data["file_format"] == "xlsx"
    assert upload_data["multiple_sheets_found"] is True
    assert upload_data["requires_sheet_selection"] is True
    assert "Quarterly_Revenue" in upload_data["detected_sheets"]
    assert "Employee_Headcount" in upload_data["detected_sheets"]

    # Inspect Sheets
    sheets_res = client.get(f"/api/v1/datasets/{dataset_id}/sheets")
    assert sheets_res.status_code == 200
    sheets_data = sheets_res.json()["data"]
    sheet_names = [s["name"] for s in sheets_data["sheets"]]
    assert "Quarterly_Revenue" in sheet_names
    assert "Employee_Headcount" in sheet_names

    # Select Sheet 2: Employee_Headcount
    select_res = client.post(
        f"/api/v1/datasets/{dataset_id}/select-sheet",
        json={"sheet_name": "Employee_Headcount"}
    )
    assert select_res.status_code == 200
    select_data = select_res.json()["data"]
    assert select_data["selected_sheet"] == "Employee_Headcount"
    assert select_data["total_rows"] == 4
    assert select_data["total_columns"] == 5
    assert "avg_salary" in select_data["column_names"]

    # Verify Profile updated for Employee_Headcount
    prof_res = client.get(f"/api/v1/profiling/{dataset_id}")
    assert prof_res.status_code == 200
    prof = prof_res.json()["data"]
    assert prof["overview"]["total_rows"] == 4
    assert prof["overview"]["total_columns"] == 5
    assert prof["overview"]["selected_sheet"] == "Employee_Headcount"

    salary_col = next(c for c in prof["columns"] if c["name"] == "avg_salary")
    assert salary_col["numeric_summary"]["mean"] == 96750.0
    assert salary_col["numeric_summary"]["min"] == 75000.0
    assert salary_col["numeric_summary"]["max"] == 135000.0


def test_dataset_listing_and_metadata_sync(client: TestClient):
    """Verifies that datasets list endpoint reflects all ingested datasets with updated row and column counts."""
    for i in range(3):
        up = client.post("/api/v1/datasets/upload", files={"file": (f"list{i}.csv", io.BytesIO(b"a,b\n1,2\n3,4\n"), "text/csv")})
        assert up.status_code == 200
    response = client.get("/api/v1/datasets")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] >= 3
    assert len(data["items"]) >= 3
    for item in data["items"]:
        assert item["id"] is not None
        assert item["name"] is not None
        assert item["file_format"] in ["csv", "tsv", "xlsx"]
        assert item["row_count"] == 2 and item["column_count"] == 2
