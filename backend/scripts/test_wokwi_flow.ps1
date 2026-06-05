# Quick test matching Wokwi parking-gate buttons (API must run on :8000)
$Base = "http://127.0.0.1:8000"
$Plate = "WK-SIM01"

Write-Host "`n=== Wokwi flow test ===" -ForegroundColor Cyan

# Health
$h = Invoke-RestMethod "$Base/health"
Write-Host "Health:" $h.status

# Entry button (green)
Write-Host "`n[1] Entry trigger..." -ForegroundColor Green
$entry = Invoke-RestMethod -Method POST -Uri "$Base/api/gate/entry/trigger" -ContentType "application/json" -Body (@{
    source = "simulator"
    mockPlate = $Plate
    autoCloseSeconds = 60
} | ConvertTo-Json)
$entry | ConvertTo-Json -Depth 5
$hash = $entry.verifyHash
$inv = $entry.invoiceId

# Payment page
Write-Host "`n[2] Active session + QR..." -ForegroundColor Yellow
$active = Invoke-RestMethod "$Base/api/payment/active-session"
$active | ConvertTo-Json
$qr = Invoke-RestMethod "$Base/api/payment/aba-qr?plateNumber=$Plate&amount=$($active.amount)"
Write-Host "QR length:" $qr.qrImage.Substring(0, [Math]::Min(50, $qr.qrImage.Length)) "..."

# Exit button (blue) — mock payment
Write-Host "`n[3] Exit trigger (mock pay)..." -ForegroundColor Blue
$exit = Invoke-RestMethod -Method POST -Uri "$Base/api/gate/exit/trigger" -ContentType "application/json" -Body (@{
    source = "simulator"
    verifyHash = $hash
    mockPlate = $Plate
    mockPayment = $true
    waitForPayment = $true
} | ConvertTo-Json)
$exit | ConvertTo-Json -Depth 3

Write-Host "`nDone. In Wokwi: set API_HOST, press Open entry then Open exit.`n" -ForegroundColor Cyan
