# One-time setup on Windows (PowerShell): venv, backend dependencies, frontend dependencies, .env.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r backend\requirements-dev.txt

if (-not (Test-Path backend\.env)) {
    Copy-Item .env.example backend\.env
    Write-Host "Created backend\.env from .env.example (edit it to set SECRET_KEY and optional AI settings)."
}

Push-Location frontend
npm ci
Pop-Location
Write-Host "Setup complete. Run the API:  cd backend; ..\.venv\Scripts\uvicorn app.main:app --port 8000"
Write-Host "Run the web client:           cd frontend; npm run dev"
