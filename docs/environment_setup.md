# EDAgent environment setup

All application commands in this guide use the [nested FastAPI and React app](../EDAgent_Completed_Extension/EDAgent/README.md). The root backend, frontend, and Compose file are legacy.

## Windows PowerShell

Install Python 3.11 or later and Node.js 22 or later with npm. From the repository root, set up the app and start both servers:

```powershell
Set-Location .\EDAgent_Completed_Extension\EDAgent
.\scripts\setup.ps1
.\scripts\dev.ps1
```

Run setup on first use and after dependency changes. It installs the backend dependencies into the nested `.venv`, installs the frontend dependencies from the npm lockfile, and creates `backend/.env` from the nested template if needed. Local development uses SQLite and local file storage. Edit the nested `backend/.env` to configure an optional LLM provider.

- [Web client](http://localhost:5173)
- [API documentation](http://127.0.0.1:8000/api/v1/docs)
- [API health check](http://127.0.0.1:8000/api/v1/health)

## Verify the application

From `EDAgent_Completed_Extension/EDAgent/`, after setup:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
Push-Location frontend
npm ci
npm run build
Pop-Location
```

## Docker Compose

With Docker running, use the nested [Compose file](../EDAgent_Completed_Extension/EDAgent/docker-compose.yml). From the repository root:

```powershell
Set-Location .\EDAgent_Completed_Extension\EDAgent
docker compose up --build
```

This starts PostgreSQL, FastAPI, and the web client.

The backend container runs `alembic upgrade head` before starting the API. For a PostgreSQL deployment outside Compose, set `DATABASE_URL`, then run `alembic upgrade head` from the nested `backend` directory before starting Uvicorn. SQLite development still creates its tables on startup. Run migrations once as a deployment step when using multiple API replicas.

CI uses Python 3.12 and Node.js 22 for the backend tests and frontend build.
