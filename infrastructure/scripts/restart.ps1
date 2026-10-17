<#
.SYNOPSIS
  Restart the Smart IoT Parking stack (or selected services).

.DESCRIPTION
  Restarts all long-running services with `docker compose restart` and prints
  the resulting status. The database volume and generated receipts are kept.

.EXAMPLE
  .\restart.ps1
  .\restart.ps1 backend
  .\restart.ps1 backend nginx
#>
#requires -Version 5.1
[CmdletBinding()]
param(
    [string[]]$Services = @()
)

$ErrorActionPreference = "Stop"
$InfraDir = Split-Path -Parent $PSScriptRoot
Set-Location $InfraDir

function Fail([string]$Message) {
    Write-Host "[X] $Message" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail "Docker CLI not found." }

if ($Services.Count -gt 0) {
    Write-Host ("Restarting: {0}" -f ($Services -join ", "))
    docker compose restart @Services
}
else {
    Write-Host "Restarting all services ..."
    docker compose restart
}
if ($LASTEXITCODE -ne 0) { Fail "Restart failed. See output above." }

Write-Host ""
Start-Sleep -Seconds 4
docker compose ps
Write-Host ""
Write-Host "Restart complete. If a service stays unhealthy, inspect: docker compose logs -f <service>" -ForegroundColor Cyan
