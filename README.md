# EDAgent

EDAgent combines a general-purpose exploratory data analysis workspace with the Allegheny County road-safety research described in [Project Plan v2](docs/EDAgent_Project_Plan_v2.pdf).

## Run the application on Windows

The active FastAPI and React application lives in [`EDAgent_Completed_Extension/EDAgent/`](EDAgent_Completed_Extension/EDAgent/README.md). From the repository root in PowerShell, run:

```powershell
Set-Location .\EDAgent_Completed_Extension\EDAgent
.\scripts\setup.ps1
.\scripts\dev.ps1
```

Open the [web client](http://localhost:5173) or the [API documentation](http://127.0.0.1:8000/api/v1/docs). See the [environment setup guide](docs/environment_setup.md) for prerequisites, configuration, and verification commands.

## Research and repository layout

- [`analysis/`](analysis/README.md) contains the canonical v6 notebook, reproduction instructions, and frozen research outputs.
- [Project Plan v2](docs/EDAgent_Project_Plan_v2.pdf) governs the road-safety work.
- The root `backend/`, `frontend/`, and `docker-compose.yml` belong to the legacy EDA prototype. Use the nested app for development, tests, and Compose.
- The [legacy generic EDA roadmap](docs/implementation_plan.md) records the earlier prototype plan.
