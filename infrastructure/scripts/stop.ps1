<#
.SYNOPSIS
  Stop the Smart IoT Parking Docker stack.

.DESCRIPTION
  Default: `docker compose down --remove-orphans` - stops and removes the
  containers/network. Named volumes (postgres_data, receipts_data) are
  preserved, so database contents and receipts survive.

  -KeepContainers: only stops the containers (`docker compose stop`), keeping
  them around for inspection.

  This script NEVER deletes volumes (`down -v` is not used anywhere).

.EXAMPLE
  .\stop.ps1
  .\stop.ps1 -KeepContainers
#>
#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$KeepContainers
)

$ErrorActionPreference = "Stop"
$InfraDir = Split-Path -Parent $PSScriptRoot
Set-Location $InfraDir

function Fail([string]$Message) {
    Write-Host "[X] $Message" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker CLI not found."
}

if ($KeepContainers) {
    Write-Host "Stopping containers (keeping them for inspection) ..."
    docker compose stop
}
else {
    Write-Host "Stopping and removing containers (volumes are preserved) ..."
    docker compose down --remove-orphans
}
if ($LASTEXITCODE -ne 0) { Fail "Stop failed. See output above." }

Write-Host ""
Write-Host "Stack stopped." -ForegroundColor Green
Write-Host "Named volumes (PostgreSQL data + receipts) are preserved."
Write-Host "Restart with: .\scripts\start.ps1 -NoBuild"
Write-Host "To delete data permanently (DANGER): docker compose down -v  (do not run unless intended)"
