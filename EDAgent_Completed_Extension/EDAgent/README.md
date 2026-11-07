# EDAgent

> Upload your data. Discover insights. Ask anything. Verify every result.

EDAgent is an exploratory data analysis (EDA) workspace built on one rule: **the backend computes every number; AI only plans and explains.** Datasets are profiled automatically, analyses run through a catalogue of validated tools, and every result carries its methodology, the rows used, and reproducible code. A language model is optional.

## What it does

- **Accounts and isolation** – registration and login (JWT). Datasets, sessions, results, reports and jobs belong to one user; everyone else gets `404`.
- **Ingestion** – CSV, TSV and multi-sheet XLSX upload, sample datasets, and SSRF-protected import from a URL. Delimiter/encoding detection with manual override, sheet selection, size/zip-bomb limits. Your original file is never modified.
- **Automatic profiling** – dimensions, types and semantic roles, missing values, exact duplicates, candidate keys, descriptive statistics, outliers, distributions, correlations and quality warnings, all computed by the backend.
- **Analysis engine** – 27 approved operations: descriptive statistics, frequencies, histograms, box/violin plots, IQR and z-score outliers, correlation (Pearson/Spearman), scatter, crosstabs, group-by and group comparison, filtering (AND/OR), time trends, date distributions, custom charts, **hypothesis tests** (Welch/Student t, paired t, one-way ANOVA, chi-square, Mann-Whitney, Kruskal-Wallis, Wilcoxon), **K-Means, PCA, linear regression and classification** (train-only fitting, no leakage). Results state rows examined/used/excluded, missing-value handling, sampling, warnings and multiple-testing cautions.
- **AI chat** – question → dataset context → LLM plan → validation → clarification if needed → run an approved tool → validate → explanation. Follow-up questions keep context. The model never runs code, never supplies numbers (numbers in its prose are checked against the result), and treats column names and cell values as data. Without a configured provider the chat says so honestly and everything else keeps working.
- **Workspace UI** – upload, overview, column inventory, quality, distributions, correlations, suggested analyses, a catalogue-driven analysis builder, chat with embedded charts/tables, history with session restore, report builder and export centre. Dark mode, responsive layout.
- **Exports** – charts as PNG/SVG/HTML, tables as CSV/XLSX (full tables, formula-injection safe), metadata JSON, reproducible `.py`/`.ipynb`, per-result and per-session ZIP bundles, dataset profile as XLSX/JSON, and **PDF/HTML reports** with 16 sections in concise or detailed mode, where AI-written text is labelled separately from computed findings.
- **Performance** – cached dataframes and results, labelled sampling for heavy modelling, background jobs with status/progress/cancel for reports and modelling, per-user concurrency and rate limits.

## Architecture

| Layer | Technology |
| --- | --- |
| Web client | React 18, TypeScript, Vite, Tailwind CSS, Plotly.js |
| API | Python 3.11+, FastAPI, Pydantic v2 |
| Analytics | pandas, NumPy, SciPy, scikit-learn |
| Charts / reports | Plotly figure JSON in the UI, matplotlib for PNG/SVG, ReportLab (PDF), Jinja2 (HTML), openpyxl (XLSX) |
| Database | SQLAlchemy 2 (async) on SQLite (default) or PostgreSQL, Alembic migrations |
| Background work | Bounded in-process job runner with database-persisted status |
| AI | Optional; OpenAI-compatible or Anthropic over HTTPS |

See `docs/` for the API overview, AI data-processing notes and the original design documents.

## Quick start

Prerequisites: Python 3.11+, Node.js 18+ and npm.

```bash
# 1. One-time setup (virtualenv, dependencies, backend/.env from .env.example)
scripts/setup.sh                 # Windows: scripts\setup.ps1

# 2. Run API (http://127.0.0.1:8000) and web client (http://localhost:5173)
scripts/dev.sh                   # Windows: scripts\dev.ps1
```

Manual equivalent:

```bash
python -m venv .venv && source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cp .env.example backend/.env                               # set SECRET_KEY, optionally the AI settings

cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000      # API; docs at /api/v1/docs
cd frontend && npm ci && npm run dev                                   # web client
```

Open `http://localhost:5173`, create an account, then upload a file or launch a sample dataset. The Vite dev server proxies `/api` to port 8000.
If an upload file is still present in `backend/data/uploads` but is missing from your dataset list, open **Ingest Dataset** and use **Restore saved uploads**. Only files stored under the signed-in account can be restored.

Tables are created automatically on start-up. To manage a database with migrations instead, run `alembic upgrade head` from `backend/`.

### Docker

```bash
docker compose up --build        # PostgreSQL + API on :8000 + web client on :5173
```

Set `SECRET_KEY` (and optionally `LLM_PROVIDER`, `LLM_API_KEY`) in your shell or an `.env` beside `docker-compose.yml`.

## Configuration

All settings are environment variables; `.env.example` lists every name with comments (no secrets). The important ones:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Signs login tokens. Required in production; the app refuses the placeholder when `ENVIRONMENT=production`. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./edagent.db` (default) or `postgresql+asyncpg://...` |
| `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` | Optional AI. `openai` (or any OpenAI-compatible gateway) or `anthropic`. `mock`/empty means "AI not configured". |
| `MAX_UPLOAD_SIZE_MB`, `MAX_DATASETS_PER_USER`, `*_RATE_LIMIT_PER_MINUTE` | Limits. |

Secrets are read server-side only; no endpoint or frontend bundle exposes them.
The environment template defaults to `LLM_PROVIDER=mock`, so adding a key alone does not enable chat. Set `LLM_PROVIDER=openai` for an OpenAI-compatible API or `anthropic` for Anthropic, choose the matching model (and optional base URL), then restart the backend.

### AI and privacy

When a provider is configured, the dataset structure (column names, types, summary statistics) and a few sanitised sample values are sent to it to plan analyses and write explanations; raw files and full tables are not. Details and controls are in [`docs/AI_DATA_PROCESSING.md`](docs/AI_DATA_PROCESSING.md). Leave AI unconfigured to keep all data local.

## Tests

```bash
python -m pytest backend/tests -q          # run from the repository root
cd frontend && npm run build               # type-checks (tsc) and builds the client
```

The backend suite uses a throw-away database and storage and a scripted fake LLM, so it needs no network or API key. It covers ingestion and limits, profiling against pandas, engine results against SciPy/NumPy, the full AI chat flow (grounding, injection, failures), exports and reports, authentication, isolation, SSRF, rate limiting and the end-to-end user journey.

## Repository layout

```
backend/app/        api/v1 endpoints, services (ingestion, profiler, analysis, ai, export, jobs), models, schemas
backend/alembic/    migrations
backend/data/samples/  bundled sample datasets
backend/tests/      pytest suite
frontend/src/       pages, components, contexts, services, types
docs/               API overview, AI data processing, design documents
scripts/            setup and dev helpers
```

## Known limitations

See `IMPLEMENTATION_REPORT.md` for the full list. Notably: only local file storage is implemented; background jobs run in-process (soft timeouts, no external queue); rate limiting is per process; the AI path is tested with a scripted fake model, not a live provider.
