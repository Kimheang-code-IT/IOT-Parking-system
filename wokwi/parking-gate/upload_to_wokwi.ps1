# Upload MicroPython files to the running Wokwi simulator.
#
# REQUIRED: Wokwi simulation must be RUNNING (green play on diagram.json).
# Port 4000 only exists while the sim is open and running.
#
# Usage: .\upload_to_wokwi.ps1

$Port = "port:rfc2217://localhost:4000"
$Here = $PSScriptRoot
$files = @("boot.py", "main.py", "lcd_api.py", "i2c_lcd.py")

function Test-WokwiPort {
    try {
        $c = Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction Stop | Select-Object -First 1
        return [bool]$c
    }
    catch {
        return $false
    }
}

function Run-Mpremote {
    param([string[]]$MpremoteArgs)
    $output = & mpremote @MpremoteArgs 2>&1
    $output | ForEach-Object { Write-Host $_ }
    return $LASTEXITCODE
}

Write-Host ""
if (-not (Test-WokwiPort)) {
    Write-Host "ERROR: Nothing is listening on port 4000." -ForegroundColor Red
    Write-Host ""
    Write-Host "mpremote says 'no device found' when the Wokwi simulator is NOT running." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Fix:" -ForegroundColor Cyan
    Write-Host "  1. Open wokwi/parking-gate/diagram.json in VS Code"
    Write-Host "  2. Click the green PLAY button (Start Simulation)"
    Write-Host "  3. Wait for MicroPython >>> in the Wokwi Serial Monitor"
    Write-Host "  4. Run this script again: .\upload_to_wokwi.ps1"
    Write-Host ""
    Write-Host "Keep the simulation tab visible (closing it stops port 4000)." -ForegroundColor DarkGray
    exit 1
}

Write-Host "Port 4000 OK - uploading to Wokwi..." -ForegroundColor Green
Write-Host ""

$failed = @()
foreach ($f in $files) {
    $path = Join-Path $Here $f
    if (-not (Test-Path $path)) {
        Write-Host "MISSING $f" -ForegroundColor Red
        $failed += $f
        continue
    }

    $ok = $false
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        Write-Host "Uploading $f (attempt $attempt)..." -ForegroundColor Yellow
        $code = Run-Mpremote -MpremoteArgs @("connect", $Port, "fs", "cp", $path, ":$f")
        if ($code -eq 0) {
            $ok = $true
            break
        }
        if (-not (Test-WokwiPort)) {
            Write-Host "  Simulation stopped - start Wokwi play, then run upload again." -ForegroundColor Red
            exit 1
        }
        Write-Host "  Retry in 2s (Wokwi Serial: Ctrl+C, then Ctrl+A)..." -ForegroundColor DarkGray
        Start-Sleep -Seconds 2
    }

    if (-not $ok) {
        $failed += $f
    }
}

if ($failed.Count -eq 0) {
    Write-Host "Reset ESP32..." -ForegroundColor Green
    Run-Mpremote -MpremoteArgs @("connect", $Port, "reset") | Out-Null
    Write-Host "Done. Check Wokwi Serial: Booting... -> API online" -ForegroundColor Green
}
else {
    Write-Host "Failed: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
