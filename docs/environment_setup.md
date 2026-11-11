# EDAgent environment setup

Use the PowerShell scripts in the [nested FastAPI and React app](../EDAgent_Completed_Extension/EDAgent/README.md) as the entry point for setup and development.

## Windows PowerShell

Install Python 3.11 or later and Node.js 18 or later with npm. From the repository root, set up the app and start both servers:

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
npm run build
Pop-Location
```
