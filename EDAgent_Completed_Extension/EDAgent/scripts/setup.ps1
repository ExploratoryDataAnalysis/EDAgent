# One-time setup on Windows (PowerShell): venv, backend dependencies, frontend dependencies, .env.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# Native commands do not automatically stop Windows PowerShell on a nonzero exit.
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Failed to create the virtual environment." }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r backend\requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Failed to install backend dependencies." }

if (-not (Test-Path backend\.env)) {
    Copy-Item .env.example backend\.env
    Write-Host "Created backend\.env from .env.example (edit it to set SECRET_KEY and optional AI settings)."
}

Push-Location frontend
npm ci
if ($LASTEXITCODE -ne 0) { throw "Failed to install frontend dependencies." }
Pop-Location
Write-Host "Setup complete. Run the API:  cd backend; ..\.venv\Scripts\uvicorn app.main:app --port 8000"
Write-Host "Run the web client:           cd frontend; npm run dev"
