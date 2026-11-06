# API overview (v1.0.0)

All routes are under `/api/v1` and, except `health`, `auth/register` and `auth/login`, require `Authorization: Bearer <token>`. Interactive documentation with full request/response schemas is served at `/api/v1/docs` (OpenAPI JSON at `/api/v1/openapi.json`).

## Conventions

- Success: `{"success": true, "message": "...", "data": ...}`.
- Failure: `{"success": false, "message": "...", "errors": [...], "error_code"?: "...", "detail"?: ...}` with an appropriate HTTP status. Server errors never include internals.
- Every dataset, session, result, report and job is owned by one user; other users receive `404`.
- Long operations (`/analysis/execute-async`, `/reports/generate`) return `202` with a `job_id`; poll `GET /jobs/{job_id}`.
- Analysis results are structured objects: metrics, tables, Plotly charts, warnings, methodology, rows examined/used/excluded, sampling flags, and the reproducible code.
- Limits (upload size, datasets per user, concurrent jobs, rate limits, row caps) come from environment settings; see `.env.example`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/analysis/catalogue` | List Approved Analysis Tools |
| `POST` | `/api/v1/analysis/execute` | Execute An Analysis Plan |
| `POST` | `/api/v1/analysis/execute-async` | Execute An Analysis As A Background Job |
| `GET` | `/api/v1/analysis/results/{result_id}` | Get Analysis Result |
| `GET` | `/api/v1/analysis/suggestions/{dataset_id}` | Suggested Analyses For A Dataset |
| `POST` | `/api/v1/auth/login` | User Login |
| `GET` | `/api/v1/auth/me` | Current User |
| `POST` | `/api/v1/auth/register` | Register User |
| `POST` | `/api/v1/chat/message` | Process Natural Language Analysis Query |
| `GET` | `/api/v1/chat/status` | AI Configuration Status |
| `GET` | `/api/v1/datasets` | List Datasets |
| `POST` | `/api/v1/datasets/import-url` | Import Dataset From URL |
| `GET` | `/api/v1/datasets/samples` | List Sample Datasets |
| `POST` | `/api/v1/datasets/samples/{sample_id}` | Load Sample Dataset |
| `POST` | `/api/v1/datasets/upload` | Upload Tabular Dataset |
| `GET` | `/api/v1/datasets/{dataset_id}` | Get Dataset Metadata |
| `DELETE` | `/api/v1/datasets/{dataset_id}` | Delete Dataset |
| `POST` | `/api/v1/datasets/{dataset_id}/confirm` | Confirm Ingestion Options |
| `GET` | `/api/v1/datasets/{dataset_id}/preview` | Get Dataset Preview |
| `POST` | `/api/v1/datasets/{dataset_id}/select-sheet` | Select Excel Sheet |
| `GET` | `/api/v1/datasets/{dataset_id}/sheets` | Inspect Excel Sheets |
| `GET` | `/api/v1/exports/datasets/{dataset_id}/profile` | Export Dataset Profile |
| `GET` | `/api/v1/exports/results/{result_id}/bundle` | Download Everything For One Result (ZIP) |
| `GET` | `/api/v1/exports/results/{result_id}/charts/{chart_id}` | Export A Chart |
| `GET` | `/api/v1/exports/results/{result_id}/code` | Export Reproducible Code |
| `GET` | `/api/v1/exports/results/{result_id}/metadata` | Export Analysis Metadata (JSON) |
| `GET` | `/api/v1/exports/results/{result_id}/tables/{index}` | Export A Result Table |
| `GET` | `/api/v1/exports/sessions/{session_id}/bundle` | Download All Results Of A Session (ZIP) |
| `GET` | `/api/v1/health` | System Health Check |
| `GET` | `/api/v1/jobs` | List My Jobs |
| `GET` | `/api/v1/jobs/{job_id}` | Job Status |
| `POST` | `/api/v1/jobs/{job_id}/cancel` | Cancel Job |
| `POST` | `/api/v1/profiling/{dataset_id}` | Re-run Automatic Profiling |
| `GET` | `/api/v1/profiling/{dataset_id}` | Get Dataset Profile |
| `GET` | `/api/v1/reports` | List Reports |
| `POST` | `/api/v1/reports/generate` | Generate EDA Report |
| `GET` | `/api/v1/reports/{report_id}` | Report Status |
| `DELETE` | `/api/v1/reports/{report_id}` | Delete Report |
| `GET` | `/api/v1/reports/{report_id}/download` | Download Report File |
| `POST` | `/api/v1/sessions` | Create Session |
| `GET` | `/api/v1/sessions` | List Sessions |
| `GET` | `/api/v1/sessions/{session_id}` | Restore Session |
| `PATCH` | `/api/v1/sessions/{session_id}` | Rename Session |
| `DELETE` | `/api/v1/sessions/{session_id}` | Delete Session |
