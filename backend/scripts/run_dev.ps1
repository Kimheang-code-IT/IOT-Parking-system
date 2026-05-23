# Development API server (SQLite) — run from backend/
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example" -ForegroundColor Yellow
}

pip install -r requirements.txt -q
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
