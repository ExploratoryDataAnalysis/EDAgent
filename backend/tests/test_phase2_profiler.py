"""
Phase 2: Automatic Dataset Profiler Test Suite
Verifies all 12 sections of the automatic EDA profiling engine specification.
Deterministic calculations with zero LLM dependency.
"""

import io
import math
import os
import uuid
import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.schemas.profiler import (
    ProfilerResultResponse,
    SemanticRoleEnum,
    SeverityEnum,
)
from app.services.profiler.profiler_engine import ProfilerEngine


# ==============================================================================
# 1. Known-Answer Benchmark Dataset Verification
# ==============================================================================

def test_profiler_known_benchmark_dataset(sample_csv_path: str):
    """
    Verifies all 12 profiler sections on known-answer benchmark:
    - 12 total rows (including duplicate row 1 and row 12)
    - 8 total columns
    - Exact duplicate rows count == 1 (repeated ID in row 5 not treated as duplicate row)
    - Missingness: exactly 3 missing cells in age, annual_income, credit_score
    - Semantic roles: IDs, Measures, Datetime with invalid dates, Categories, Text
    - Statistics: correct mean, min, max, percentiles
    - Correlations: measures included, IDs and categories excluded
    - Quality warnings: possible ID, invalid date, high missingness
    """
    profile = ProfilerEngine.profile_csv_file(sample_csv_path, delimiter=",")

    # 1. Dataset Overview
    overview = profile["overview"]
    assert overview["total_rows"] == 12
    assert overview["total_columns"] == 8
    assert overview["file_size_bytes"] > 0
    assert overview["memory_estimate_bytes"] > 0
    assert overview["load_time_seconds"] >= 0.0
    assert overview["profiling_duration_seconds"] >= 0.0

    # 2. Duplicate Analysis
    duplicates = profile["duplicates"]
    assert duplicates["exact_duplicate_rows_count"] == 1
    assert duplicates["exact_duplicate_percentage"] == round((1 / 12) * 100, 2)
    # Repeated IDs (CUST-101 in row 1 and row 5) are NOT treated as exact duplicate rows
    assert len(duplicates["duplicate_rows_sample"]) > 0

    # 3. Missing-Value Analysis
    missingness = profile["missingness"]
    assert missingness["total_cells"] == 96  # 12 * 8
    assert missingness["missing_cells"] == 3
    assert missingness["overall_missing_percentage"] == round((3 / 96) * 100, 2)
    assert set(missingness["columns_with_missing"]) == {"age", "annual_income", "credit_score"}
    assert len(missingness["missingness_chart_data"]) == 8
    assert missingness["missingness_chart_data"][0]["missing_count"] == 1

    # 4. Column Inventory & Semantic Roles
    cols_by_name = {c["name"]: c for c in profile["columns"]}
    assert len(cols_by_name) == 8

    # id -> identifier
    assert cols_by_name["id"]["semantic_role"] == SemanticRoleEnum.IDENTIFIER.value
    assert cols_by_name["id"]["role_confidence"] >= 0.85

    # customer_id -> identifier
    assert cols_by_name["customer_id"]["semantic_role"] == SemanticRoleEnum.IDENTIFIER.value

    # age -> measure
    assert cols_by_name["age"]["semantic_role"] == SemanticRoleEnum.MEASURE.value
    assert cols_by_name["age"]["missing_count"] == 1
    assert cols_by_name["age"]["non_null_count"] == 11
    age_stat = cols_by_name["age"]["numeric_summary"]
    assert age_stat is not None
    assert age_stat["count"] == 11
    assert age_stat["min"] == 19.0
    assert age_stat["max"] == 88.0
    assert age_stat["mean"] == round((25 + 34 + 45 + 28 + 52 + 19 + 31 + 60 + 41 + 88 + 25) / 11, 4)

    # annual_income -> measure
    assert cols_by_name["annual_income"]["semantic_role"] == SemanticRoleEnum.MEASURE.value
    inc_stat = cols_by_name["annual_income"]["numeric_summary"]
    assert inc_stat is not None
    assert inc_stat["count"] == 11
    assert inc_stat["min"] == 15000.0
    assert inc_stat["max"] == 450000.0

    # credit_score -> measure
    assert cols_by_name["credit_score"]["semantic_role"] == SemanticRoleEnum.MEASURE.value

    # signup_date -> datetime
    assert cols_by_name["signup_date"]["semantic_role"] == SemanticRoleEnum.DATETIME.value
    date_stat = cols_by_name["signup_date"]["date_summary"]
    assert date_stat is not None
    assert date_stat["invalid_date_count"] == 1  # 'invalid-date' test cell
    assert date_stat["min_date"].startswith("2023-01-15")
    assert date_stat["max_date"].startswith("2023-10-10")

    # status -> category
    assert cols_by_name["status"]["semantic_role"] == SemanticRoleEnum.CATEGORY.value
    cat_stat = cols_by_name["status"]["categorical_summary"]
    assert cat_stat is not None
    assert cat_stat["unique_count"] == 4
    assert cat_stat["most_frequent_value"] == "Active"

    # notes -> text (prompt injection treated purely as data)
    assert cols_by_name["notes"]["semantic_role"] in (
        SemanticRoleEnum.TEXT.value,
        SemanticRoleEnum.CATEGORY.value,
    )

    # 5. Distribution Analysis
    distributions = profile["distributions"]
    assert len(distributions["histograms"]) >= 3
    assert len(distributions["boxplots"]) >= 3
    # Check outlier detection: 450000 income and 88 age
    income_boxplot = next(b for b in distributions["boxplots"] if b["column"] == "annual_income")
    assert income_boxplot["outlier_count"] >= 1
    assert 450000.0 in income_boxplot["outliers_sample"]

    # 6. Quality Warnings
    quality_warnings = profile["quality_warnings"]
    warning_types = [w["check_type"] for w in quality_warnings]
    assert "invalid_dates" in warning_types
    assert "possible_id" in warning_types

    # 7. Relationships
    relationships = profile["relationships"]
    assert relationships["pearson"] is not None
    assert relationships["spearman"] is not None
    # IDs, status, notes, dates must be excluded from numeric correlation
    assert "id" in relationships["excluded_columns"]
    assert "customer_id" in relationships["excluded_columns"]
    assert "status" in relationships["excluded_columns"]
    assert "notes" in relationships["excluded_columns"]
    # Measures must be present
    assert "age" in relationships["pearson"]["columns"]
    assert "annual_income" in relationships["pearson"]["columns"]
    assert "credit_score" in relationships["pearson"]["columns"]

    # 8. Suggested Analyses & Recommendations
    suggested = profile["suggested_analyses"]
    assert len(suggested) > 0
    assert any("outlier" in s["operation"] for s in suggested)
    assert any("group_by" in s["operation"] for s in suggested)

    # 9. Pydantic Contract Validation
    validated = ProfilerResultResponse(dataset_id=uuid.uuid4(), **profile)
    assert validated.overview.total_rows == 12


# ==============================================================================
# 2. Semantic Role Inference Rules
# ==============================================================================

def test_semantic_role_postal_codes_are_categorical():
    """Verifies that postal/zip codes with numeric digits are inferred as CATEGORY, not MEASURE."""
    headers = ["user_id", "zip_code", "city"]
    rows = [
        ["1", "90210", "Beverly Hills"],
        ["2", "10001", "New York"],
        ["3", "30301", "Atlanta"],
        ["4", "94102", "San Francisco"],
        ["5", "90210", "Beverly Hills"],
        ["6", "10001", "New York"],
    ]
    profile = ProfilerEngine.profile_data(headers, rows)
    cols = {c["name"]: c for c in profile["columns"]}

    assert cols["zip_code"]["semantic_role"] == SemanticRoleEnum.CATEGORY.value
    assert cols["zip_code"]["role_confidence"] >= 0.90
    assert cols["zip_code"]["role_uncertainty_reason"] is not None
    assert "Postal" in cols["zip_code"]["role_uncertainty_reason"]


def test_semantic_role_student_ids_are_identifiers():
    """Verifies that numeric student IDs are inferred as IDENTIFIER, not MEASURE."""
    headers = ["student_id", "gpa", "major"]
    rows = [
        ["101", "3.8", "CS"],
        ["102", "3.5", "Math"],
        ["103", "3.9", "Physics"],
        ["104", "3.2", "Biology"],
        ["105", "3.7", "Chemistry"],
    ]
    profile = ProfilerEngine.profile_data(headers, rows)
    cols = {c["name"]: c for c in profile["columns"]}

    assert cols["student_id"]["semantic_role"] == SemanticRoleEnum.IDENTIFIER.value
    assert cols["gpa"]["semantic_role"] == SemanticRoleEnum.MEASURE.value


def test_semantic_role_severity_and_status_codes():
    """Verifies that numeric severity/priority codes are inferred as CATEGORY."""
    headers = ["ticket_id", "severity_code", "resolution_hours"]
    rows = [
        ["T-1", "1", "2.5"],
        ["T-2", "2", "8.0"],
        ["T-3", "1", "1.0"],
        ["T-4", "3", "24.0"],
        ["T-5", "2", "6.5"],
        ["T-6", "3", "48.0"],
    ]
    profile = ProfilerEngine.profile_data(headers, rows)
    cols = {c["name"]: c for c in profile["columns"]}

    assert cols["severity_code"]["semantic_role"] == SemanticRoleEnum.CATEGORY.value
    assert cols["resolution_hours"]["semantic_role"] == SemanticRoleEnum.MEASURE.value


def test_semantic_role_booleans_and_free_text():
    """Verifies boolean binary flags and long free-text inference."""
    headers = ["id", "is_verified", "user_comments"]
    rows = [
        ["1", "true", "The platform was exceptionally easy to set up and very intuitive to navigate."],
        ["2", "false", "Encountered a small bug when trying to download the resulting summary file."],
        ["3", "true", "Great customer support and immediate response to inquiries regarding billing."],
        ["4", "false", "Needs more integration with third-party cloud data warehouses like Snowflake."],
    ]
    profile = ProfilerEngine.profile_data(headers, rows)
    cols = {c["name"]: c for c in profile["columns"]}

    assert cols["is_verified"]["semantic_role"] == SemanticRoleEnum.BOOLEAN.value
    assert cols["user_comments"]["semantic_role"] == SemanticRoleEnum.TEXT.value


# ==============================================================================
# 3. Descriptive Statistics & Percentiles
# ==============================================================================

def test_descriptive_statistics_calculations():
    """Verifies exact mean, std, quartiles, median, IQR, zeros, skewness, and kurtosis."""
    headers = ["measure"]
    # Known dataset: 10, 20, 30, 40, 50
    rows = [["10"], ["20"], ["30"], ["40"], ["50"]]
    profile = ProfilerEngine.profile_data(headers, rows)
    num_stat = profile["columns"][0]["numeric_summary"]

    assert num_stat["count"] == 5
    assert num_stat["mean"] == 30.0
    assert num_stat["min"] == 10.0
    assert num_stat["max"] == 50.0
    assert num_stat["median"] == 30.0
    assert num_stat["q25"] == 20.0
    assert num_stat["q75"] == 40.0
    assert num_stat["iqr"] == 20.0
    assert math.isclose(num_stat["std"], 15.8114, rel_tol=1e-3)
    assert num_stat["zeros_count"] == 0
    assert num_stat["zeros_percentage"] == 0.0


# ==============================================================================
# 4. Infinite-Value and NaN Handling
# ==============================================================================

def test_infinite_and_nan_value_handling():
    """Verifies that infinite values ('inf', '-inf') and NaNs do not crash and are tracked."""
    headers = ["sensor_reading"]
    rows = [
        ["10.0"],
        ["20.0"],
        ["inf"],
        ["30.0"],
        ["-inf"],
        ["nan"],
        ["40.0"],
    ]
    profile = ProfilerEngine.profile_data(headers, rows)
    num_stat = profile["columns"][0]["numeric_summary"]

    assert num_stat["infinite_count"] == 2
    assert num_stat["nan_count"] == 1
    # Clean finite numbers: 10, 20, 30, 40
    assert num_stat["count"] == 4
    assert num_stat["mean"] == 25.0
    assert num_stat["min"] == 10.0
    assert num_stat["max"] == 40.0

    # Quality check must warn about infinite values
    warnings = profile["quality_warnings"]
    inf_warn = next((w for w in warnings if w["check_type"] == "infinite_values"), None)
    assert inf_warn is not None
    assert inf_warn["severity"] == SeverityEnum.HIGH.value
    assert inf_warn["affected_count"] == 2


# ==============================================================================
# 5. Data Quality Checks: Constant, Placeholders, Mixed Types, Out-of-Range
# ==============================================================================

def test_data_quality_constant_and_near_constant():
    """Detects constant columns and near-constant columns."""
    headers = ["constant_col", "near_constant_col"]
    rows = [["Fixed", "ValA"] for _ in range(98)]
    rows.append(["Fixed", "ValB"])
    rows.append(["Fixed", "ValB"])

    profile = ProfilerEngine.profile_data(headers, rows)
    warnings = profile["quality_warnings"]

    const_warn = next((w for w in warnings if w["column"] == "constant_col" and w["check_type"] == "constant"), None)
    assert const_warn is not None
    assert const_warn["severity"] == SeverityEnum.HIGH.value

    near_warn = next((w for w in warnings if w["column"] == "near_constant_col" and w["check_type"] == "near_constant"), None)
    assert near_warn is not None


def test_data_quality_suspicious_placeholders():
    """Detects placeholder values like 'N/A', '?', 'null'."""
    headers = ["score"]
    rows = [["85"], ["90"], ["N/A"], ["78"], ["?"], ["95"]]
    profile = ProfilerEngine.profile_data(headers, rows)

    warnings = profile["quality_warnings"]
    susp_warn = next((w for w in warnings if w["check_type"] == "suspicious_values"), None)
    assert susp_warn is not None
    assert susp_warn["affected_count"] == 2


def test_data_quality_out_of_range():
    """Detects possible out-of-range negative ages or percentages."""
    headers = ["age", "completion_pct"]
    rows = [
        ["-5", "50"],
        ["25", "110"],
        ["30", "-10"],
        ["40", "85"],
    ]
    profile = ProfilerEngine.profile_data(headers, rows)
    warnings = profile["quality_warnings"]
    out_warns = [w for w in warnings if w["check_type"] == "possible_out_of_range"]
    assert len(out_warns) >= 2


# ==============================================================================
# 6. Relationships: Pearson, Spearman, Cramér's V
# ==============================================================================

def test_relationships_pearson_and_spearman():
    """Verifies accurate Pearson and Spearman correlation calculation."""
    headers = ["x", "y"]
    # Perfect linear relationship y = 2x
    rows = [
        ["1", "2"],
        ["2", "4"],
        ["3", "6"],
        ["4", "8"],
        ["5", "10"],
    ]
    profile = ProfilerEngine.profile_data(headers, rows)
    relationships = profile["relationships"]

    p_corr = relationships["pearson"]["matrix"]["x"]["y"]
    s_corr = relationships["spearman"]["matrix"]["x"]["y"]
    assert math.isclose(p_corr, 1.0, abs_tol=1e-3)
    assert math.isclose(s_corr, 1.0, abs_tol=1e-3)


def test_relationships_zero_variance_exclusion():
    """Verifies that columns with zero variance are safely excluded from correlation."""
    headers = ["variance_col", "constant_measure"]
    rows = [
        ["10", "5"],
        ["20", "5"],
        ["30", "5"],
        ["40", "5"],
    ]
    profile = ProfilerEngine.profile_data(headers, rows)
    relationships = profile["relationships"]
    assert any("zero variance" in w for w in relationships["warnings"])


# ==============================================================================
# 7. Edge Cases: Empty Dataset, Single Row, All Nulls
# ==============================================================================

def test_empty_dataset_edge_case():
    """Verifies that an empty dataset (0 rows, 0 columns) produces a clean payload without crashing."""
    profile = ProfilerEngine.profile_data(headers=[], rows=[])
    assert profile["overview"]["total_rows"] == 0
    assert profile["overview"]["total_columns"] == 0
    assert profile["columns"] == []
    assert profile["missingness"]["total_cells"] == 0
    assert profile["duplicates"]["exact_duplicate_rows_count"] == 0


def test_single_row_dataset_edge_case():
    """Verifies that a 1-row dataset computes statistics without division by zero."""
    headers = ["name", "score"]
    rows = [["Alice", "95.5"]]
    profile = ProfilerEngine.profile_data(headers, rows)
    assert profile["overview"]["total_rows"] == 1
    score_profile = profile["columns"][1]
    assert score_profile["numeric_summary"]["count"] == 1
    assert score_profile["numeric_summary"]["std"] == 0.0
    assert score_profile["numeric_summary"]["mean"] == 95.5


def test_all_missing_column():
    """Verifies that a column with all missing values is profiled safely."""
    headers = ["id", "empty_col"]
    rows = [["1", ""], ["2", " "], ["3", "NA"]]
    profile = ProfilerEngine.profile_data(headers, rows)
    empty_col = profile["columns"][1]
    assert empty_col["missing_count"] == 3
    assert empty_col["missing_percentage"] == 100.0
    assert empty_col["non_null_count"] == 0


# ==============================================================================
# 8. API Integration: Automatic Profiling on Ingestion & Profiler Endpoints
# ==============================================================================

def test_api_profiling_endpoints_and_auto_ingestion(client: TestClient):
    """
    Verifies:
    1. Automatic profiling runs upon file upload.
    2. GET /api/v1/profiling/{dataset_id} retrieves cached profile.
    3. POST /api/v1/profiling/{dataset_id} triggers recalculation.
    """
    csv_content = (
        "emp_id,department,salary,join_date,is_manager\n"
        "E-101,Engineering,95000,2021-03-15,true\n"
        "E-102,Marketing,65000,2022-06-20,false\n"
        "E-103,Engineering,110000,2020-01-10,true\n"
        "E-104,HR,55000,2023-08-01,false\n"
        "E-105,Marketing,72000,2021-11-18,false\n"
        "E-106,Engineering,125000,2019-05-22,false\n"
    )

    # 1. Upload dataset
    files = {"file": ("employees.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    upload_res = client.post("/api/v1/datasets/upload", files=files)
    assert upload_res.status_code == 200
    dataset_id = upload_res.json()["data"]["dataset_id"]

    # 2. Retrieve profile via GET /api/v1/profiling/{dataset_id}
    profile_res = client.get(f"/api/v1/profiling/{dataset_id}")
    assert profile_res.status_code == 200
    p_data = profile_res.json()["data"]

    assert p_data["overview"]["total_rows"] == 6
    assert p_data["overview"]["total_columns"] == 5
    assert p_data["duplicates"]["exact_duplicate_rows_count"] == 0

    cols = {c["name"]: c for c in p_data["columns"]}
    assert cols["emp_id"]["semantic_role"] == SemanticRoleEnum.IDENTIFIER.value
    assert cols["department"]["semantic_role"] == SemanticRoleEnum.CATEGORY.value
    assert cols["salary"]["semantic_role"] == SemanticRoleEnum.MEASURE.value
    assert cols["join_date"]["semantic_role"] == SemanticRoleEnum.DATETIME.value
    assert cols["is_manager"]["semantic_role"] == SemanticRoleEnum.BOOLEAN.value

    # Check distribution data returned
    assert len(p_data["distributions"]["histograms"]) >= 1
    assert len(p_data["distributions"]["boxplots"]) >= 1
    assert len(p_data["distributions"]["categorical_frequencies"]) >= 1

    # Check suggested analyses
    assert len(p_data["suggested_analyses"]) > 0

    # 3. Trigger profiling via POST /api/v1/profiling/{dataset_id}
    trigger_res = client.post(f"/api/v1/profiling/{dataset_id}")
    assert trigger_res.status_code == 200
    t_data = trigger_res.json()["data"]
    assert t_data["dataset_id"] == dataset_id
    assert t_data["overview"]["total_rows"] == 6


def test_api_profiling_not_found(client: TestClient):
    """Verifies that non-existent dataset IDs return 404."""
    non_existent_id = uuid.uuid4()
    res = client.get(f"/api/v1/profiling/{non_existent_id}")
    assert res.status_code == 404


# ==============================================================================
# 9. Format Support: Excel XLSX and TSV Profiling
# ==============================================================================

def test_profiler_excel_xlsx(tmp_path):
    """Verifies profiling directly on an Excel workbook (.xlsx)."""
    file_path = str(tmp_path / "sales.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "2023_Sales"
    ws.append(["order_id", "product", "sales_amount", "discount_pct"])
    ws.append(["ORD-001", "Laptop", 1200.50, 5.0])
    ws.append(["ORD-002", "Monitor", 350.00, 10.0])
    ws.append(["ORD-003", "Keyboard", 75.25, 0.0])
    ws.append(["ORD-004", "Mouse", 25.00, 0.0])
    ws.append(["ORD-005", "Desk", 450.00, 15.0])
    wb.save(file_path)

    profile = ProfilerEngine.profile_dataset(file_path, format_str="xlsx", sheet_name="2023_Sales")
    assert profile["overview"]["total_rows"] == 5
    assert profile["overview"]["total_columns"] == 4
    assert profile["overview"]["selected_sheet"] == "2023_Sales"

    cols = {c["name"]: c for c in profile["columns"]}
    assert cols["order_id"]["semantic_role"] == SemanticRoleEnum.IDENTIFIER.value
    assert cols["product"]["semantic_role"] == SemanticRoleEnum.CATEGORY.value
    assert cols["sales_amount"]["semantic_role"] == SemanticRoleEnum.MEASURE.value
    assert cols["discount_pct"]["semantic_role"] == SemanticRoleEnum.MEASURE.value


def test_profiler_tsv(tmp_path):
    """Verifies profiling on a tab-separated values file (.tsv)."""
    file_path = str(tmp_path / "measurements.tsv")
    content = (
        "station_id\ttemperature\thumidity\n"
        "ST-1\t22.5\t65\n"
        "ST-2\t24.0\t60\n"
        "ST-3\t19.8\t75\n"
        "ST-4\t21.2\t70\n"
    )
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    profile = ProfilerEngine.profile_dataset(file_path, format_str="tsv", delimiter="\t")
    assert profile["overview"]["total_rows"] == 4
    assert profile["overview"]["total_columns"] == 3

    cols = {c["name"]: c for c in profile["columns"]}
    assert cols["station_id"]["semantic_role"] == SemanticRoleEnum.IDENTIFIER.value
    assert cols["temperature"]["semantic_role"] == SemanticRoleEnum.MEASURE.value
    assert cols["humidity"]["semantic_role"] == SemanticRoleEnum.MEASURE.value


# ==============================================================================
# 10. High-Cardinality Categorical & Distribution Details
# ==============================================================================

def test_high_cardinality_categorical_other_bucket():
    """Verifies that categorical frequency charts cap at top 10 and aggregate remainder into 'Other'."""
    headers = ["category_code"]
    # 20 distinct categories with differing counts
    rows = []
    for i in range(20):
        code = f"CAT_{i:02d}"
        for _ in range(25 - i):
            rows.append([code])

    profile = ProfilerEngine.profile_data(headers, rows)
    dist = profile["distributions"]
    cat_freq = dist["categorical_frequencies"][0]

    assert len(cat_freq["categories"]) == 10
    assert cat_freq["other_count"] > 0
    assert cat_freq["other_percentage"] > 0.0


def test_time_distribution_hour_and_day():
    """Verifies that datetime columns with timestamps calculate day of week and hour of day."""
    headers = ["timestamp"]
    rows = [
        ["2023-05-01 08:30:00"],  # Monday
        ["2023-05-02 14:15:00"],  # Tuesday
        ["2023-05-03 14:45:00"],  # Wednesday
        ["2023-05-04 18:00:00"],  # Thursday
        ["2023-05-05 20:30:00"],  # Friday
    ]
    profile = ProfilerEngine.profile_data(headers, rows)
    time_dist = profile["distributions"]["time_distributions"][0]

    assert "Monday" in time_dist["day_of_week"]
    assert time_dist["day_of_week"]["Monday"] == 1
    assert "14" in time_dist["hour_of_day"]
    assert time_dist["hour_of_day"]["14"] == 2


def test_cramers_v_categorical_associations():
    """Verifies Cramér's V calculation between two associated categorical variables."""
    headers = ["department", "floor"]
    # Strong association: Eng on Floor 1, Sales on Floor 2, HR on Floor 3
    rows = (
        [["Engineering", "Floor_1"] for _ in range(15)]
        + [["Sales", "Floor_2"] for _ in range(15)]
        + [["HR", "Floor_3"] for _ in range(15)]
    )
    profile = ProfilerEngine.profile_data(headers, rows)
    assoc = profile["relationships"]["categorical_associations"]

    assert len(assoc) == 1
    assert assoc[0]["column_x"] == "department"
    assert assoc[0]["column_y"] == "floor"
    assert assoc[0]["cramers_v"] > 0.8
