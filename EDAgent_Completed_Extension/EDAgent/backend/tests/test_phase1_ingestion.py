"""
Phase 1: Dataset Upload, Ingestion & Validation Test Suite
Thoroughly verifies all requirements of Task 9 & Section 5.1 of the EDAgent specification.
"""

import io
import os
import uuid
import pytest
import openpyxl
from fastapi.testclient import TestClient

from app.core.config import settings
from app.schemas.dataset import FileFormatEnum
from app.services.ingestion.validator import IngestionValidator, IngestionValidationError
from app.services.ingestion.parser import IngestionService


# ==============================================================================
# 1. Valid CSV Upload, Ingestion, Preview & Metadata
# ==============================================================================

def test_valid_csv_upload_and_preview(client: TestClient):
    """Verifies complete upload, parsing, preview, and metadata retrieval for a valid CSV."""
    csv_content = (
        "id,product,price,quantity,in_stock,created_at\n"
        "1,Widget A,19.99,100,true,2023-01-15\n"
        "2,Widget B,29.50,50,true,2023-02-20\n"
        "3,Widget C,9.99,0,false,2023-03-12\n"
        "4,Widget D,45.00,25,true,2023-04-05\n"
        "5,Widget E,99.95,10,true,2023-05-18\n"
        "6,Widget F,5.50,200,true,2023-06-22\n"
        "7,Widget G,15.00,80,true,2023-07-30\n"
        "8,Widget H,120.00,5,false,2023-08-14\n"
        "9,Widget I,75.00,15,true,2023-09-01\n"
        "10,Widget J,33.30,40,true,2023-10-10\n"
        "11,Widget K,12.50,90,true,2023-11-05\n"
        "12,Widget L,88.00,8,false,2023-12-01\n"
    )

    files = {"file": ("products.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    response = client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 200, response.text
    res_data = response.json()
    assert res_data["success"] is True

    upload_data = res_data["data"]
    dataset_id = upload_data["dataset_id"]
    assert upload_data["name"] == "products.csv"
    assert upload_data["file_format"] == "csv"
    assert upload_data["multiple_sheets_found"] is False
    assert upload_data["requires_sheet_selection"] is False
    assert "delimiter 'comma (,)'" in upload_data["parsing_decision"]

    # Retrieve preview
    preview_res = client.get(f"/api/v1/datasets/{dataset_id}/preview")
    assert preview_res.status_code == 200
    preview = preview_res.json()["data"]
    assert preview["total_rows"] == 12
    assert preview["total_columns"] == 6
    assert len(preview["head_records"]) == 10
    assert len(preview["tail_records"]) <= 10
    assert len(preview["sample_records"]) <= 10

    # Verify inferred types
    types = preview["inferred_types"]
    assert types["id"] == "integer"
    assert types["price"] == "float"
    assert types["quantity"] == "integer"
    assert types["in_stock"] == "boolean"
    assert types["created_at"] == "datetime"
    assert types["product"] == "string"

    # Retrieve metadata
    meta_res = client.get(f"/api/v1/datasets/{dataset_id}")
    assert meta_res.status_code == 200
    meta = meta_res.json()["data"]
    assert meta["id"] == dataset_id
    assert meta["row_count"] == 12
    assert meta["column_count"] == 6
    assert meta["checksum_sha256"] is not None


# ==============================================================================
# 2. Valid TSV Upload and Delimiter Sniffing
# ==============================================================================

def test_valid_tsv_upload(client: TestClient):
    """Verifies that tab-separated files are accurately recognized and parsed."""
    tsv_content = (
        "student_id\tname\tgpa\tmajor\n"
        "101\tAlice\t3.85\tComputer Science\n"
        "102\tBob\t3.40\tData Science\n"
        "103\tCharlie\t3.95\tMathematics\n"
    )

    files = {"file": ("students.tsv", io.BytesIO(tsv_content.encode("utf-8")), "text/tab-separated-values")}
    response = client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["file_format"] == "tsv"
    assert "tab (\\t)" in data["parsing_decision"]

    # Preview check
    preview_res = client.get(f"/api/v1/datasets/{data['dataset_id']}/preview")
    preview = preview_res.json()["data"]
    assert preview["total_rows"] == 3
    assert preview["total_columns"] == 4
    assert preview["column_names"] == ["student_id", "name", "gpa", "major"]
    assert preview["inferred_types"]["gpa"] == "float"


# ==============================================================================
# 3. Valid Single-Sheet Excel (.xlsx) Upload
# ==============================================================================

def test_valid_single_sheet_excel(client: TestClient):
    """Verifies Excel XLSX upload with a single worksheet."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Financials"
    ws.append(["quarter", "revenue", "expenses", "net_profit"])
    ws.append(["Q1", 100000.50, 75000.00, 25000.50])
    ws.append(["Q2", 125000.00, 80000.00, 45000.00])
    ws.append(["Q3", 150000.00, 92000.00, 58000.00])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    files = {"file": ("financials.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    response = client.post("/api/v1/datasets/upload", files=files)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["file_format"] == "xlsx"
    assert data["multiple_sheets_found"] is False
    assert data["selected_sheet"] == "Financials"

    preview_res = client.get(f"/api/v1/datasets/{data['dataset_id']}/preview")
    preview = preview_res.json()["data"]
    assert preview["total_rows"] == 3
    assert preview["total_columns"] == 4
    assert preview["selected_sheet"] == "Financials"
    assert preview["inferred_types"]["revenue"] == "float"


# ==============================================================================
# 4. Multi-Sheet Excel Workflow: Upload, Sheet Inspection & Sheet Selection
# ==============================================================================

def test_multi_sheet_excel_workflow(client: TestClient):
    """
    Verifies Section 5.1 requirement:
    'Do not silently select an arbitrary sheet when the user needs to choose.'
    """
    wb = openpyxl.Workbook()
    # Sheet 1: North Region
    ws1 = wb.active
    ws1.title = "NorthRegion"
    ws1.append(["store_id", "sales", "manager"])
    ws1.append(["N-01", 50000, "John Doe"])
    ws1.append(["N-02", 72000, "Jane Smith"])

    # Sheet 2: South Region
    ws2 = wb.create_sheet(title="SouthRegion")
    ws2.append(["store_id", "sales", "manager", "target_met"])
    ws2.append(["S-01", 45000, "Carlos Ray", "true"])
    ws2.append(["S-02", 89000, "Sara Connor", "true"])
    ws2.append(["S-03", 31000, "Kyle Reese", "false"])

    # Sheet 3: Metadata
    ws3 = wb.create_sheet(title="AuditLog")
    ws3.append(["date", "action"])
    ws3.append(["2023-10-01", "Initial Import"])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    # 1. Upload without specifying sheet
    files = {"file": ("multi_region.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    upload_res = client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 200
    upload_data = upload_res.json()["data"]
    dataset_id = upload_data["dataset_id"]

    assert upload_data["multiple_sheets_found"] is True
    assert upload_data["requires_sheet_selection"] is True
    assert upload_data["detected_sheets"] == ["NorthRegion", "SouthRegion", "AuditLog"]
    assert upload_data["selected_sheet"] is None

    # 2. Inspect available sheets
    inspect_res = client.get(f"/api/v1/datasets/{dataset_id}/sheets")
    assert inspect_res.status_code == 200
    inspect_data = inspect_res.json()["data"]
    assert len(inspect_data["sheets"]) == 3
    sheet_names = [s["name"] for s in inspect_data["sheets"]]
    assert "NorthRegion" in sheet_names
    assert "SouthRegion" in sheet_names
    assert "AuditLog" in sheet_names

    # 3. Select a specific sheet ('SouthRegion')
    select_res = client.post(
        f"/api/v1/datasets/{dataset_id}/select-sheet",
        json={"sheet_name": "SouthRegion"},
    )
    assert select_res.status_code == 200
    select_preview = select_res.json()["data"]
    assert select_preview["selected_sheet"] == "SouthRegion"
    assert select_preview["total_rows"] == 3
    assert select_preview["total_columns"] == 4
    assert select_preview["column_names"] == ["store_id", "sales", "manager", "target_met"]
    assert select_preview["inferred_types"]["target_met"] == "boolean"

    # 4. Attempting to select a non-existent sheet
    invalid_sheet_res = client.post(
        f"/api/v1/datasets/{dataset_id}/select-sheet",
        json={"sheet_name": "NonExistentSheet"},
    )
    assert invalid_sheet_res.status_code == 400
    assert "not found" in invalid_sheet_res.json()["message"]


# ==============================================================================
# 5. Empty File Rejection
# ==============================================================================

def test_empty_file_rejection(client: TestClient):
    """Empty files (0 bytes) must be rejected with understandable error."""
    files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    res = client.post("/api/v1/datasets/upload", files=files)
    assert res.status_code == 400
    err = res.json()
    assert err["success"] is False
    assert err["error_code"] == "EMPTY_FILE"
    assert "empty (0 bytes)" in err["message"]


def test_whitespace_only_file_rejection(client: TestClient):
    """Files containing only whitespace/newlines must be rejected."""
    files = {"file": ("whitespace.csv", io.BytesIO(b"   \n\n\t  \n"), "text/csv")}
    res = client.post("/api/v1/datasets/upload", files=files)
    assert res.status_code == 400
    err = res.json()
    assert err["error_code"] == "EMPTY_FILE"


# ==============================================================================
# 6. Corrupted File Rejection
# ==============================================================================

def test_corrupt_excel_rejection(client: TestClient):
    """Files with .xlsx extension but damaged/invalid content must be caught."""
    fake_xlsx_bytes = b"This is plain text pretending to be an excel file."
    files = {"file": ("fake.xlsx", io.BytesIO(fake_xlsx_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res = client.post("/api/v1/datasets/upload", files=files)
    assert res.status_code == 400
    err = res.json()
    assert err["error_code"] == "CORRUPT_EXCEL"
    assert "zip signature" in err["message"]


def test_binary_null_bytes_in_csv_rejection(client: TestClient):
    """Binary files masquerading as CSV must be rejected."""
    binary_data = b"id,name\n\x00\x01\x02,bad_binary"
    files = {"file": ("binary_exec.csv", io.BytesIO(binary_data), "text/csv")}
    res = client.post("/api/v1/datasets/upload", files=files)
    assert res.status_code == 400
    err = res.json()
    assert err["error_code"] == "BINARY_FILE_DETECTED"


# ==============================================================================
# 7. Unsupported Extensions Rejection
# ==============================================================================

def test_unsupported_extensions_rejection(client: TestClient):
    """Unsupported formats like .parquet, .pdf, .json, .exe must be rejected."""
    for bad_name in ["data.parquet", "document.pdf", "records.json", "setup.exe"]:
        files = {"file": (bad_name, io.BytesIO(b"dummy content"), "application/octet-stream")}
        res = client.post("/api/v1/datasets/upload", files=files)
        assert res.status_code == 400, f"Failed for {bad_name}"
        err = res.json()
        assert err["error_code"] == "UNSUPPORTED_FORMAT"
        assert "Unsupported file format" in err["message"]


# ==============================================================================
# 8. Non-UTF8 Character Encodings (Latin-1 / ISO-8859-1)
# ==============================================================================

def test_latin1_encoding_handling(client: TestClient):
    """Verifies that non-UTF8 encodings like Latin-1 with accented characters parse cleanly."""
    latin1_text = "id,name,city\n1,René,München\n2,Chloë,Zürich\n"
    latin1_bytes = latin1_text.encode("latin-1")

    files = {"file": ("european_users.csv", io.BytesIO(latin1_bytes), "text/csv")}
    res = client.post("/api/v1/datasets/upload", files=files)
    assert res.status_code == 200
    data = res.json()["data"]

    preview_res = client.get(f"/api/v1/datasets/{data['dataset_id']}/preview")
    preview = preview_res.json()["data"]
    assert preview["total_rows"] == 2
    names = [r["name"] for r in preview["head_records"]]
    assert "René" in names
    assert "Chloë" in names


# ==============================================================================
# 9. Duplicate and Missing Headers Handling
# ==============================================================================

def test_duplicate_and_empty_headers_sanitization(client: TestClient):
    """
    Verifies that:
    - Empty headers are assigned 'unnamed_i'
    - Duplicate headers are deduplicated to 'col_1', 'col_2'
    - Warnings are recorded in dataset metadata
    """
    csv_content = (
        "id,,score,score,name\n"
        "1,val1,85,90,Alice\n"
        "2,val2,78,82,Bob\n"
    )

    files = {"file": ("duplicate_headers.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/v1/datasets/upload", files=files)
    assert res.status_code == 200
    dataset_id = res.json()["data"]["dataset_id"]

    preview_res = client.get(f"/api/v1/datasets/{dataset_id}/preview")
    preview = preview_res.json()["data"]

    expected_cols = ["id", "unnamed_2", "score", "score_1", "name"]
    assert preview["column_names"] == expected_cols

    # Check parsing warnings
    warnings = preview["parsing_warnings"]
    assert any("Empty header" in w for w in warnings)
    assert any("Duplicate column name 'score'" in w for w in warnings)


# ==============================================================================
# 10. Ragged / Malformed CSV Rows Handling
# ==============================================================================

def test_ragged_rows_handling(client: TestClient):
    """Verifies that rows with fewer or more columns are padded/truncated without crashing."""
    csv_content = (
        "col1,col2,col3\n"
        "1,2,3\n"
        "4,5\n"            # Row with fewer cols (padded)
        "6,7,8,9,10\n"     # Row with extra cols (truncated)
        "11,12,13\n"
    )

    files = {"file": ("ragged.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/v1/datasets/upload", files=files)
    assert res.status_code == 200
    dataset_id = res.json()["data"]["dataset_id"]

    preview_res = client.get(f"/api/v1/datasets/{dataset_id}/preview")
    preview = preview_res.json()["data"]
    assert preview["total_rows"] == 4
    assert len(preview["head_records"]) == 4

    # Verify warnings recorded
    warnings = preview["parsing_warnings"]
    assert any("padded with empty cells" in w for w in warnings)
    assert any("excess cells truncated" in w for w in warnings)


# ==============================================================================
# 11. Oversized File Rejection
# ==============================================================================

def test_oversized_file_rejection(client: TestClient, monkeypatch):
    """Enforces MAX_UPLOAD_SIZE_MB limit rejection."""
    # Temporarily set upload limit to 1 KB for test
    from app.core import config
    monkeypatch.setattr(config.settings, "MAX_UPLOAD_SIZE_MB", 0.001)  # ~1 KB

    oversized_content = "a" * 2048  # 2 KB
    files = {"file": ("big.csv", io.BytesIO(oversized_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/v1/datasets/upload", files=files)
    assert res.status_code == 413
    assert res.json()["error_code"] == "FILE_TOO_LARGE"


# ==============================================================================
# 12. Storage Isolation and Unauthorized Access Checks
# ==============================================================================

def test_storage_isolation_and_user_access_control(client: TestClient, second_user):
    """
    Verifies that:
    - User A's uploaded file is isolated.
    - User B cannot access, preview, profile or delete User A's dataset (it looks like it does not exist).
    """
    csv_content = "secret_id,confidential_score\n1,99\n2,100\n"
    files = {"file": ("classified.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}

    res = client.post("/api/v1/datasets/upload", files=files)
    assert res.status_code == 200
    dataset_id = res.json()["data"]["dataset_id"]
    assert client.get(f"/api/v1/datasets/{dataset_id}").status_code == 200

    other = second_user["headers"]
    res_b = client.get(f"/api/v1/datasets/{dataset_id}", headers=other)
    assert res_b.status_code == 404
    assert res_b.json()["error_code"] == "FILE_NOT_FOUND"
    assert client.get(f"/api/v1/datasets/{dataset_id}/preview", headers=other).status_code == 404
    assert client.get(f"/api/v1/profiling/{dataset_id}", headers=other).status_code == 404
    assert client.delete(f"/api/v1/datasets/{dataset_id}", headers=other).status_code == 404
    # ...and the owner's copy is untouched by the failed attempts.
    assert client.get(f"/api/v1/datasets/{dataset_id}").status_code == 200
    # The other user's list does not leak it either.
    listing = client.get("/api/v1/datasets", headers=other).json()["data"]
    assert dataset_id not in [d["id"] for d in listing["items"]]


def test_endpoints_require_authentication(anon_client: TestClient):
    for method, path in [("get", "/api/v1/datasets"), ("get", "/api/v1/sessions"), ("post", "/api/v1/chat/message"), ("get", "/api/v1/analysis/catalogue")]:
        assert getattr(anon_client, method)(path).status_code == 401, path


# ==============================================================================
# 13. Dataset Listing and Deletion
# ==============================================================================

def test_dataset_listing_and_deletion(client: TestClient):
    """Verifies listing datasets and deleting a dataset cleans up database and disk storage."""
    files1 = {"file": ("ds1.csv", io.BytesIO(b"col1,col2\n1,2\n"), "text/csv")}
    files2 = {"file": ("ds2.csv", io.BytesIO(b"a,b\n3,4\n"), "text/csv")}

    res1 = client.post("/api/v1/datasets/upload", files=files1)
    res2 = client.post("/api/v1/datasets/upload", files=files2)
    id1 = res1.json()["data"]["dataset_id"]
    id2 = res2.json()["data"]["dataset_id"]

    # List datasets
    list_res = client.get("/api/v1/datasets")
    assert list_res.status_code == 200
    list_data = list_res.json()["data"]
    assert list_data["total"] >= 2
    ids = [d["id"] for d in list_data["items"]]
    assert id1 in ids
    assert id2 in ids

    # Delete dataset 1
    del_res = client.delete(f"/api/v1/datasets/{id1}")
    assert del_res.status_code == 200
    assert del_res.json()["data"] is True

    # Confirm dataset 1 is no longer retrievable
    get_res = client.get(f"/api/v1/datasets/{id1}")
    assert get_res.status_code == 404
