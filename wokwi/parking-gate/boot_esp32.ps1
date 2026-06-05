# Boot / reset ESP32 in Wokwi and show Serial output.
# Prerequisite: Wokwi simulation RUNNING (play on diagram.json) — port 4000 listening.
#
# Usage:
#   .\boot_esp32.ps1              # reset only (boot messages in Wokwi Serial Monitor)
#   .\boot_esp32.ps1 -Upload      # upload .py files then reset
#   .\boot_esp32.ps1 -Repl        # open mpremote REPL in this terminal (Ctrl+] to exit)

param(
    [switch]$Upload,
    [switch]$Repl
)

$ErrorActionPreference = "Stop"
$Port = "port:rfc2217://localhost:4000"
$Here = $PSScriptRoot

function Test-WokwiPort {
    try {
        return [bool](Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction Stop | Select-Object -First 1)
    }
    catch { return $false }
}

if (-not (Get-Command mpremote -ErrorAction SilentlyContinue)) {
    Write-Host "Install mpremote: pip install mpremote==1.23" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-WokwiPort)) {
    Write-Host "ERROR: Port 4000 not open. Start Wokwi simulation first:" -ForegroundColor Red
    Write-Host "  VS Code -> wokwi/parking-gate/diagram.json -> green PLAY"
    Write-Host "  Open: View -> Output -> Wokwi Serial Monitor"
    exit 1
}

if ($Upload) {
    & (Join-Path $Here "upload_to_wokwi.ps1")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    exit 0
}

Write-Host "Resetting ESP32 (watch Wokwi Serial Monitor)..." -ForegroundColor Green
& mpremote connect $Port reset
Start-Sleep -Seconds 1

Write-Host ""
Write-Host "Expected in Serial Monitor:" -ForegroundColor Cyan
Write-Host "  boot.py: MicroPython starting"
Write-Host "  Booting..."
Write-Host "  Import OK: i2c_lcd.I2cLcd"
Write-Host "  I2C devices: [39]"
Write-Host "  LCD: IOT Parking | LCD Working"
Write-Host "  API online  (when backend + wokwigw are running)"
Write-Host ""

if ($Repl) {
    Write-Host "Opening REPL in this terminal (exit: Ctrl+]) ..." -ForegroundColor Yellow
    & mpremote connect $Port repl
}
