# Starts the API (port 8000) and the web client (port 5173). Ctrl+C or closing window stops both.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "Starting EDAgent Backend (port 8000)..." -ForegroundColor Cyan
$apiProcess = Start-Process -FilePath "$Root\.venv\Scripts\uvicorn.exe" -ArgumentList "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload" -WorkingDirectory "$Root\backend" -PassThru

Write-Host "Starting EDAgent Web Client (port 5173)..." -ForegroundColor Cyan
Set-Location "$Root\frontend"

try {
    npm run dev
} finally {
    Write-Host "`nStopping EDAgent Backend..." -ForegroundColor Yellow
    if ($apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
