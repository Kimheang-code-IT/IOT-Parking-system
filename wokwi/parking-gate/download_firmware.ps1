# One-time: download ESP32 MicroPython firmware for Wokwi VS Code
$bin = "ESP32_GENERIC-20251209-v1.27.0.bin"
$url = "https://github.com/wokwi/wokwi-vscode-micropython/raw/main/esp32/$bin"
$out = Join-Path $PSScriptRoot $bin

if (Test-Path $out) {
    Write-Host "Already exists: $out" -ForegroundColor Green
    exit 0
}

Write-Host "Downloading $bin ..."
Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
Write-Host "Saved: $out" -ForegroundColor Green
