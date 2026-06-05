# Run the bundled Tesseract installer (GUI). After install, set GATE_TESSERACT_CMD in backend/.env
$ErrorActionPreference = "Stop"
$installer = Join-Path $PSScriptRoot "tesseract-ocr-w64-setup-5.5.0.20241111.exe"

if (-not (Test-Path $installer)) {
    Write-Host "Installer not found: $installer" -ForegroundColor Red
    exit 1
}

$defaultExe = "C:\Program Files\Tesseract-OCR\tesseract.exe"
if (Test-Path $defaultExe) {
    Write-Host "Tesseract already installed: $defaultExe" -ForegroundColor Green
    & $defaultExe --version
    exit 0
}

Write-Host "Starting Tesseract installer (follow the wizard)..." -ForegroundColor Cyan
Write-Host "Install to: C:\Program Files\Tesseract-OCR\" -ForegroundColor Yellow
Start-Process -FilePath $installer -Wait

if (Test-Path $defaultExe) {
    Write-Host ""
    Write-Host "Installed OK." -ForegroundColor Green
    & $defaultExe --version
    Write-Host ""
    Write-Host "Add to backend/.env:" -ForegroundColor Cyan
    Write-Host '  GATE_TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe'
} else {
    Write-Host ""
    Write-Host "If you chose a custom folder, set GATE_TESSERACT_CMD in backend/.env to your tesseract.exe path." -ForegroundColor Yellow
}
