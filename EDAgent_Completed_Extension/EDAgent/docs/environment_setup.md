> **Note (v1.0.0):** this document is the original design plan. Where it mentions Celery/Redis, DuckDB/Polars or S3 storage, the shipped implementation differs: background work uses an in-process bounded job runner with database-persisted status, analytics use pandas/scipy/scikit-learn, and only local file storage is implemented. See the top-level `README.md` and `IMPLEMENTATION_REPORT.md` for what actually exists.

# EDAgent Environment Setup Instructions

This document provides step-by-step instructions to configure, run, and verify the EDAgent development environment.

---

## 1. Prerequisites

Ensure the following tools are installed on your workstation:

| Tool | Recommended Version | Verify Command |
| :--- | :--- | :--- |
| **Python** | `3.11+` or `3.13` | `python --version` |
| **Node.js** | `v18.0+` or `v22.0+` | `node --version` |
| **npm** | `v9.0+` or `v10.0+` | `npm --version` |
| **PostgreSQL** (Optional for local dev)| `15+` or `16+` | `psql --version` |
| **Redis** (Optional for local dev)| `7.0+` | `redis-server --version` |
| **Docker & Docker Compose** (Optional)| `v24+` | `docker compose version` |

> [!NOTE]
> For zero-dependency local development, SQLite and an in-memory/eager Celery mode are preconfigured in `.env.example`. PostgreSQL and Redis are recommended for production parity.

---

## 2. Workspace Setup

### 2.1 Clone and Environment Configuration
1. Clone the repository and navigate into the root directory:
   ```bash
   cd EDA-Dashboard
   ```
2. Create your local environment file from the template:
   ```bash
   cp .env.example .env
   ```
3. Inspect and adjust `.env` variables if required (e.g. database credentials or OpenAI API key).

---

## 3. Backend Setup (FastAPI + Python)

1. Create a dedicated Python virtual environment:
   ```bash
   python -m venv .venv
   ```
2. Activate the virtual environment:
   - **Windows PowerShell**:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS**:
     ```bash
     source .venv/bin/activate
     ```
3. Install production and development dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r backend/requirements.txt
   pip install -r backend/requirements-dev.txt
   ```
4. Verify the baseline test suite:
   ```bash
   python -m pytest backend/tests -v
   ```
5. Launch the FastAPI development server:
   ```bash
   uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
   ```
   - The interactive OpenAPI documentation will be accessible at: `http://127.0.0.1:8000/api/v1/docs`
   - Health check diagnostic: `http://127.0.0.1:8000/api/v1/health`

---

## 4. Frontend Setup (React + TypeScript)

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Launch the Vite development server:
   ```bash
   npm run dev
   ```
   - The frontend application will be available at: `http://localhost:5173`

---

## 5. Dockerized Environment (All-in-One)

If Docker is available on your machine, you can run the complete stack (PostgreSQL, Redis, FastAPI, Celery Worker, and Vite Frontend) with a single command:

```bash
docker compose up --build
```
- Frontend: `http://localhost:5173`
- Backend API Docs: `http://localhost:8000/api/v1/docs`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
