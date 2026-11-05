# EDAgent

> **Your AI-Powered Data Analysis Workspace**  
> *Upload your data. Discover insights. Ask anything. Verify every result.*

EDAgent is an AI-assisted Exploratory Data Analysis (EDA) platform built on the fundamental principle of **deterministic computation, AI-guided analysis, and transparent, reproducible outputs**.

---

## 🎯 Key Capabilities

1. **Automatic Dataset Profiling**: Ingests CSV, TSV, and Excel files to immediately calculate dataset dimensions, missingness, exact duplicate rows, candidate keys, descriptive statistics, and data quality warnings without requiring an AI call.
2. **Conversational Analysis (AI Chat)**: Allows users to interrogate their datasets using natural language. The AI translates questions into a machine-validated `StructuredAnalysisPlan`, and the backend compute worker calculates exact numerical outputs.
3. **On-Demand Analytical Tool Catalogue**: Predefined, controlled operations for histograms, boxplots, correlation matrices, group-by aggregations, outlier fences (IQR), crosstabs, and time trends.
4. **Interactive Plotly Visualizations & One-Click Reports**: Reusable result objects featuring interactive charts, underlying data tables, reproducible execution code, and downloadable PDF/HTML reports.

---

## 🏗️ Architecture Summary

- **Frontend**: React 18, TypeScript, Tailwind CSS, Plotly.js, Vite.
- **Backend API**: Python 3.11+, FastAPI, Pydantic v2.
- **Data Engine**: Pandas (in-memory profiling), DuckDB & Polars (columnar analytical queries, filter pushdown).
- **Metadata Database**: PostgreSQL 16 (SQLAlchemy 2.0 async ORM, Alembic migrations) with SQLite fallback for local zero-dependency dev.
- **Background Processing**: Redis + Celery worker queue with progress tracking and task cancellation.
- **Storage Abstraction**: Pluggable storage provider supporting local filesystem storage for dev and S3/MinIO for cloud production.

For in-depth details, see:
- [System Architecture](file:///docs/architecture.md)
- [Folder Structure](file:///docs/folder_structure.md)
- [Database Schema Design](file:///docs/database_schema.md)
- [API Contract Specification](file:///docs/api_specification.md)
- [Risks & Architectural Decisions](file:///docs/risks_and_decisions.md)
- [Phased Implementation Roadmap](file:///docs/implementation_plan.md)

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.11+
- Node.js v18+ & npm
- PostgreSQL & Redis (optional, SQLite/Eager mode pre-configured for dev)

### 2. Configure Environment
```bash
cp .env.example .env
```

### 3. Backend Setup
```bash
# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
pip install -r backend/requirements-dev.txt

# Run baseline verification tests
python -m pytest backend/tests -v

# Start FastAPI server
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```
Interactive API documentation will be available at: `http://127.0.0.1:8000/api/v1/docs`

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Web client will be available at: `http://localhost:5173`

### 5. Dockerized Setup (Alternative)
```bash
docker compose up --build
```

---

## 🧪 Test Suite

The automated test suite verifies configuration loading, file ingestion, delimiter sniffing, character encoding detection, Excel workbook inspection & sheet selection, empty/corrupted/malformed/oversized file rejection, storage isolation, and deterministic statistical calculations:

```bash
python -m pytest backend/tests -v
```

All 22 test cases currently pass with zero failures.

---

## 🗺️ Project Roadmap
- [x] **Phase 0: Repository Analysis & Project Foundation** (Complete)
- [x] **Phase 1: Dataset Upload, Ingestion and Validation** (Complete)
- [ ] **Phase 2: Automatic Profiler & Baseline EDA**
- [ ] **Phase 3: Analysis Workspace & AI Chat**
- [ ] **Phase 4: Export Centre & One-Click EDA Report**
- [ ] **Phase 5: Quality, Security & Sandboxing**
- [ ] **Phase 6: Scale, Performance & Advanced Capabilities**

See [Phased Implementation Roadmap](file:///docs/implementation_plan.md) for details.
