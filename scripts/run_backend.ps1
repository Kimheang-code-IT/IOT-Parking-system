# Start FastAPI from repo root (creates backend/.env if missing)
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvActivate = Join-Path $Root ".venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) { . $VenvActivate }
Set-Location (Join-Path $Root "backend")
& ".\scripts\run_dev.ps1"
