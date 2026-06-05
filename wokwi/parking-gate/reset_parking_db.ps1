# Clear active sessions so Wokwi entry works fresh (API must run on :8000)
$Base = "http://127.0.0.1:8000"
Write-Host "Resetting parking DB..." -ForegroundColor Cyan
Push-Location (Join-Path $PSScriptRoot "..\..\backend")
try {
    & python scripts/reset_db.py
    Write-Host "Done. Restart Wokwi entry test with green button." -ForegroundColor Green
} finally {
    Pop-Location
}
