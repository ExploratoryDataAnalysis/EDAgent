# EDAgent API Contract Specification

All API endpoints reside under the `/api/v1` namespace and follow standard REST conventions with JSON payloads.

---

## 1. Standard Response Formats

### 1.1 Success Envelope
```json
{
  "success": true,
  "message": "Operation description",
  "data": { ... },
  "errors": null
}
```

### 1.2 Error Envelope
```json
{
  "success": false,
  "message": "Human-readable failure description",
  "errors": ["Specific validation or execution error details"],
  "error_code": "RESOURCE_NOT_FOUND"
}
```

---

## 2. Core API Endpoints

### 2.1 Health & Diagnostics
#### `GET /api/v1/health`
Checks backend and service connectivity.
- **Response**: `200 OK`
```json
{
  "status": "healthy",
  "app_name": "EDAgent",
  "environment": "development",
  "storage_backend": "local",
  "timestamp": "2026-11-04T18:30:00Z"
}
```

---

### 2.2 Datasets & Ingestion
#### `POST /api/v1/datasets/upload`
Uploads a CSV, TSV, or Excel (.xlsx) file with automatic delimiter sniffing, encoding recovery, and isolated storage.
- **Content-Type**: `multipart/form-data`
- **Headers**: `X-User-ID` (optional UUID string for isolated user access)
- **Form Fields**:
  - `file`: Binary file upload (max 100MB)
  - `sheet_name`: Optional string (for targeting a specific Excel sheet)
- **Response**: `200 OK`
```json
{
  "success": true,
  "message": "Dataset uploaded and validated successfully.",
  "data": {
    "dataset_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "sales_q3.csv",
    "original_filename": "sales_q3.csv",
    "file_format": "csv",
    "file_size_bytes": 1048576,
    "multiple_sheets_found": false,
    "detected_sheets": null,
    "selected_sheet": null,
    "requires_sheet_selection": false,
    "parsing_decision": "Parsed CSV with encoding 'utf-8' and delimiter 'comma (,)'. Detected 6 columns and 10500 rows.",
    "storage_uri": "anonymous/3fa85f64-5717-4562-b3fc-2c963f66afa6/sales_q3.csv",
    "created_at": "2026-11-05T01:30:00Z"
  }
}
```

#### `GET /api/v1/datasets/{dataset_id}/sheets`
Inspects all worksheet names and estimated dimensions of an uploaded multi-sheet Excel file.
- **Response**: `200 OK`
```json
{
  "success": true,
  "message": "Found 3 sheets in workbook.",
  "data": {
    "dataset_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "sheets": [
      { "name": "NorthRegion", "row_count_estimate": 120, "column_count_estimate": 5 },
      { "name": "SouthRegion", "row_count_estimate": 85, "column_count_estimate": 5 },
      { "name": "AuditLog", "row_count_estimate": 10, "column_count_estimate": 2 }
    ],
    "default_sheet": "NorthRegion"
  }
}
```

#### `POST /api/v1/datasets/{dataset_id}/select-sheet`
Selects and ingests a specific worksheet from a multi-sheet Excel workbook.
- **Request Body**:
```json
{
  "sheet_name": "SouthRegion"
}
```
- **Response**: `200 OK` (returns `DatasetPreview`)

#### `POST /api/v1/datasets/{dataset_id}/confirm`
Re-parses the dataset with confirmed parameters (e.g. override delimiter, encoding, or sheet).
- **Request Body**:
```json
{
  "delimiter": ";",
  "encoding": "latin-1",
  "sheet_name": null
}
```
- **Response**: `200 OK` (returns `DatasetPreview`)

#### `GET /api/v1/datasets/{dataset_id}/preview`
Returns first 10 records, last 10 records, random sample, inferred column storage types, and parsing warnings without loading the full dataset into memory.
- **Query Parameters**: `limit` (default: 10)
- **Response**: `200 OK`
```json
{
  "success": true,
  "message": "Preview retrieved.",
  "data": {
    "dataset_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "selected_sheet": null,
    "total_rows": 10500,
    "total_columns": 6,
    "column_names": ["id", "amount", "category", "in_stock", "created_date"],
    "inferred_types": {
      "id": "integer",
      "amount": "float",
      "category": "string",
      "in_stock": "boolean",
      "created_date": "datetime"
    },
    "head_records": [{ "id": 1, "amount": 120.5, "category": "Retail", "in_stock": "true", "created_date": "2023-01-01" }],
    "tail_records": [{ "id": 10500, "amount": 95.0, "category": "Tech", "in_stock": "false", "created_date": "2023-12-31" }],
    "sample_records": [{ "id": 4821, "amount": 310.2, "category": "Retail", "in_stock": "true", "created_date": "2023-06-15" }],
    "parsing_warnings": []
  }
}
```

#### `GET /api/v1/datasets/{dataset_id}`
Retrieves dataset metadata, checksum, dimensions, and parsing decisions.
- **Response**: `200 OK`
```json
{
  "success": true,
  "message": "Dataset retrieved successfully.",
  "data": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "user_id": null,
    "name": "sales_q3.csv",
    "original_filename": "sales_q3.csv",
    "file_format": "csv",
    "file_size_bytes": 1048576,
    "row_count": 10500,
    "column_count": 6,
    "checksum_sha256": "21fc764ec7e3ce55fe4d9ad8f698839fd998c0fc4ddf14ce8d6c55bab6894d19",
    "is_deleted": false,
    "created_at": "2026-11-05T01:30:00Z",
    "updated_at": "2026-11-05T01:30:00Z",
    "metadata_summary": {
      "inferred_schema": { "id": "integer", "amount": "float" },
      "quality_warnings": [],
      "parsed_sheets": null
    }
  }
}
```

#### `GET /api/v1/datasets`
Lists user's datasets with pagination and user isolation.
- **Query Parameters**: `skip` (default: 0), `limit` (default: 20)
- **Response**: `200 OK`
```json
{
  "success": true,
  "message": "Retrieved 2 datasets.",
  "data": {
    "items": [
      {
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "name": "sales_q3.csv",
        "original_filename": "sales_q3.csv",
        "file_format": "csv",
        "file_size_bytes": 1048576,
        "row_count": 10500,
        "column_count": 6,
        "created_at": "2026-11-05T01:30:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

#### `DELETE /api/v1/datasets/{dataset_id}`
Deletes a dataset, marks it deleted in the database, and safely purges the isolated storage directory.
- **Response**: `200 OK`
```json
{
  "success": true,
  "message": "Dataset '3fa85f64-5717-4562-b3fc-2c963f66afa6' successfully deleted.",
  "data": true
}
```

---

### 2.3 Automatic Profiler
#### `POST /api/v1/profiling/{dataset_id}`
Triggers deterministic baseline profiling for an ingested dataset. Computes descriptive statistics, distributions, missingness, duplicates, quality checks, relationships, and suggested analyses without any LLM dependency.
- **Query Parameters**: `sheet_name` (optional for Excel workbooks)
- **Headers**: `X-User-ID` (optional)
- **Response**: `200 OK`

#### `GET /api/v1/profiling/{dataset_id}`
Retrieves cached baseline profiling results. If not previously computed, automatically generates the deterministic profile and caches the results.
- **Headers**: `X-User-ID` (optional)
- **Response**: `200 OK`
```json
{
  "success": true,
  "message": "Profiling generated successfully.",
  "data": {
    "dataset_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "overview": {
      "dataset_name": "sales_q3.csv",
      "total_rows": 10500,
      "total_columns": 4,
      "file_size_bytes": 1048576,
      "memory_estimate_bytes": 3145728,
      "selected_sheet": null,
      "load_time_seconds": 0.12,
      "profiling_duration_seconds": 0.08,
      "parsing_warnings": []
    },
    "columns": [
      {
        "name": "amount",
        "storage_dtype": "float",
        "inferred_type": "float",
        "semantic_role": "measure",
        "role_confidence": 0.98,
        "role_uncertainty_reason": null,
        "non_null_count": 10450,
        "missing_count": 50,
        "missing_percentage": 0.48,
        "distinct_count": 4200,
        "is_unique": false,
        "numeric_summary": {
          "count": 10450,
          "mean": 154.23,
          "std": 45.12,
          "min": 10.0,
          "q25": 115.0,
          "median": 150.0,
          "q75": 185.0,
          "max": 850.0,
          "iqr": 70.0,
          "skewness": 1.25,
          "kurtosis": 2.45,
          "zeros_count": 0,
          "zeros_percentage": 0.0,
          "infinite_count": 0,
          "nan_count": 50
        },
        "categorical_summary": null,
        "date_summary": null,
        "sample_values": [120.5, 95.0, 310.2]
      }
    ],
    "missingness": {
      "total_cells": 42000,
      "missing_cells": 50,
      "overall_missing_percentage": 0.12,
      "per_column": { "amount": 0.48 },
      "columns_with_missing": ["amount"],
      "missingness_chart_data": [
        { "column": "amount", "missing_count": 50, "missing_percentage": 0.48, "present_count": 10450 }
      ],
      "missingness_patterns": [
        { "missing_columns": ["amount"], "row_count": 50, "percentage": 0.48 }
      ]
    },
    "duplicates": {
      "exact_duplicate_rows_count": 0,
      "exact_duplicate_percentage": 0.0,
      "candidate_duplicate_keys": ["order_id"],
      "duplicate_rows_sample": []
    },
    "distributions": {
      "histograms": [
        {
          "column": "amount",
          "bins": [
            { "bin_start": 10.0, "bin_end": 94.0, "count": 1200, "percentage": 11.48 },
            { "bin_start": 94.0, "bin_end": 178.0, "count": 6800, "percentage": 65.07 }
          ]
        }
      ],
      "boxplots": [
        {
          "column": "amount",
          "min": 10.0,
          "q25": 115.0,
          "median": 150.0,
          "q75": 185.0,
          "max": 850.0,
          "iqr": 70.0,
          "lower_fence": 10.0,
          "upper_fence": 290.0,
          "outlier_count": 42,
          "outliers_sample": [320.0, 450.0, 850.0]
        }
      ],
      "categorical_frequencies": [],
      "date_distributions": [],
      "time_distributions": []
    },
    "quality_warnings": [],
    "relationships": {
      "pearson": {
        "columns": ["amount"],
        "matrix": { "amount": { "amount": 1.0 } }
      },
      "spearman": {
        "columns": ["amount"],
        "matrix": { "amount": { "amount": 1.0 } }
      },
      "categorical_associations": [],
      "warnings": [],
      "excluded_columns": ["order_id", "category"]
    },
    "suggested_analyses": [
      {
        "title": "Investigate statistical outliers in amount",
        "description": "Analyze 42 outlier observation(s) falling outside 1.5x IQR fences [10.0, 290.0].",
        "operation": "outlier",
        "columns": ["amount"],
        "rationale": "42 points detected beyond upper fence 290.0."
      }
    ],
    "suggested_questions": [
      "What is the distribution and outlier range of amount?"
    ],
    "computed_at": "2026-11-05T01:30:00Z"
  }
}
```

---

### 2.4 Analysis Execution
#### `POST /api/v1/analysis/execute`
Executes an approved analytical operation against the actual dataset.
- **Request Body**:
```json
{
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "user_query": "Histogram of amount excluding refunds",
  "override_plan": {
    "operation": "histogram",
    "column": "amount",
    "filter_expression": "category != 'Refund'",
    "bins": "auto",
    "missing_policy": "exclude_and_report",
    "scope": "full_dataset"
  }
}
```
- **Response**: `200 OK`
```json
{
  "success": true,
  "message": "Analysis executed successfully.",
  "data": {
    "id": "7ca24e12-4299-4ba0-a924-f7b5921820bc",
    "request_id": "8bb35f21-1234-4567-9876-abcdef012345",
    "operation_type": "histogram",
    "summary_text": "Amount exhibits a right-skewed distribution with a median of $150.00 across 10,400 included observations. 50 missing values and 50 refund records were excluded.",
    "execution_code": "df[df['category'] != 'Refund']['amount'].dropna()",
    "records_examined": 10500,
    "records_used": 10400,
    "is_sampled": false,
    "sample_size": null,
    "plot_spec": { "data": [{ "type": "histogram", "x": [...] }] },
    "data_table": [{ "bin": "100-150", "count": 4200 }],
    "warnings": ["50 missing records excluded."],
    "execution_time_ms": 42.5
  }
}
```

---

### 2.5 Conversational Analysis (AI Chat)
#### `POST /api/v1/chat/message`
Translates user queries to plans, triggers isolated computation, and returns explanations with guardrails.
- **Request Body**:
```json
{
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "message": "Compare median amount by category",
  "conversation_history": []
}
```
- **Response**: `200 OK`
```json
{
  "success": true,
  "message": "Chat response generated.",
  "data": {
    "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "reply_text": "Here is the comparison of median amount across categories. 'Tech' leads with a median of $190.00, followed by 'Retail' at $145.00.",
    "is_clarification_needed": false,
    "clarifying_question": null,
    "cannot_answer_reason": null,
    "analysis_plan": {
      "operation": "group_by",
      "column": "amount",
      "group_by_column": "category",
      "aggregation": "median"
    },
    "analysis_result": { ... }
  }
}
```

---

### 2.6 Report Generation & Exports
#### `POST /api/v1/reports/generate`
Compiles an EDA report into PDF or HTML.
- **Request Body**:
```json
{
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Quarterly Sales EDA Report",
  "format": "pdf",
  "concise_mode": false,
  "included_sections": [
    "cover",
    "executive_summary",
    "dataset_structure",
    "data_quality",
    "univariate_analysis",
    "user_requested_analyses",
    "limitations",
    "appendix"
  ]
}
```
- **Response**: `200 OK` (returns report metadata and download URL)

---

### 2.7 Background Jobs
#### `GET /api/v1/jobs/{job_id}`
Polls status and progress of long-running operations.
- **Response**: `200 OK`
```json
{
  "success": true,
  "message": "Job status retrieved.",
  "data": {
    "job_id": "task-uuid-12345",
    "job_type": "profiling",
    "status": "PROCESSING",
    "progress_percentage": 65.0,
    "status_message": "Computing distribution histograms...",
    "error_details": null,
    "created_at": "2026-11-04T18:30:00Z",
    "completed_at": null
  }
}
```

#### `POST /api/v1/jobs/{job_id}/cancel`
Cancels or terminates an active background job.
