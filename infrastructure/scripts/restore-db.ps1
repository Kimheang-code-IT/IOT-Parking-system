<#
.SYNOPSIS
  Restore a PostgreSQL backup created by backup-db.ps1.

.DESCRIPTION
  WARNING: restoring REPLACES the current database contents with the backup
  (pg_restore --clean --if-exists drops and recreates the objects it contains).

  The script:
    1. Validates the backup file (pg_restore --list inside the db container).
    2. Requires interactive confirmation (type RESTORE) unless -Force is given.
    3. Stops the backend so no application connection blocks the restore.
    4. Restores, then starts the backend again and waits for health.

  The SQLite file (if still present) and previous backups are never touched.

.EXAMPLE
  .\restore-db.ps1 -BackupFile .\backups\iot-parking-20261017-120000.dump
  .\restore-db.ps1 -BackupFile .\backups\xxx.dump -Force
#>
#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$InfraDir = Split-Path -Parent $PSScriptRoot
Set-Location $InfraDir

function Fail([string]$Message) {
    Write-Host "[X] $Message" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail "Docker CLI not found." }

if (-not (Test-Path $BackupFile)) { Fail "Backup file not found: $BackupFile" }
$fileInfo = Get-Item $BackupFile
if ($fileInfo.Length -lt 1024) { Fail "Backup file looks invalid (too small): $BackupFile" }

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$dbId = docker compose ps -q db 2>$null
$ErrorActionPreference = $prevEap
if (-not $dbId) {
    Fail "The db container is not running. Start the stack first: .\scripts\start.ps1 -NoBuild"
}

$projectName = "iot-parking"
if (Test-Path ".env") {
    $envText = Get-Content ".env" -Raw
    if ($envText -match "(?m)^\s*COMPOSE_PROJECT_NAME\s*=\s*(\S+)") { $projectName = $Matches[1] }
}

Write-Host ""
Write-Host "  Restore backup : $($fileInfo.FullName)" -ForegroundColor Yellow
Write-Host "  Target         : PostgreSQL service 'db' of project '$projectName'"
Write-Host ""
Write-Host "  THIS REPLACES THE CURRENT DATABASE CONTENT with the backup." -ForegroundColor Yellow
Write-Host "  The backend will be stopped during the restore and started again afterwards."
Write-Host ""

if (-not $Force) {
    $answer = Read-Host "Type RESTORE (all caps) to continue, anything else aborts"
    if ($answer -ne "RESTORE") {
        Write-Host "Aborted - no changes were made."
        exit 0
    }
}

# --- validate the dump inside the container ---------------------------------
$containerFile = "/tmp/restore-$([System.IO.Path]::GetFileName($BackupFile))"
Write-Host "Copying backup into the db container ..."
docker compose cp "$($fileInfo.FullName)" "db:$containerFile"
if ($LASTEXITCODE -ne 0) { Fail "Could not copy the backup into the container." }

Write-Host "Validating backup ..."
docker compose exec -T db sh -c "pg_restore --list $containerFile > /dev/null"
if ($LASTEXITCODE -ne 0) {
    $prevEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    docker compose exec -T db rm -f $containerFile *> $null
    $ErrorActionPreference = $prevEap
    Fail "pg_restore --list could not read the backup - restore aborted."
}

# --- stop backend, restore, restart backend ---------------------------------
Write-Host "Stopping backend (drops active DB connections) ..."
$prevEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
docker compose stop backend *> $null
$ErrorActionPreference = $prevEap

Write-Host "Restoring database ..."
docker compose exec -T db sh -c "pg_restore -U `"`$POSTGRES_USER`" -d `"`$POSTGRES_DB`" --clean --if-exists --no-owner $containerFile"
$restoreExit = $LASTEXITCODE

$prevEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
docker compose exec -T db rm -f $containerFile *> $null

Write-Host "Starting backend again ..."
docker compose start backend *> $null
$ErrorActionPreference = $prevEap

if ($restoreExit -ne 0) {
    Write-Host "[!] pg_restore reported warnings/errors (exit $restoreExit)." -ForegroundColor Yellow
    Write-Host "    Verify the application data before relying on this restore."
}

# --- health + verification ---------------------------------------------------
Write-Host "Waiting for backend health ..."
$deadline = (Get-Date).AddSeconds(120)
$healthy = $false
while ((Get-Date) -lt $deadline) {
    $prevEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $backendId = docker compose ps -q backend 2>$null
    $status = ""
    if ($backendId) {
        $status = docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" $backendId 2>$null
    }
    $ErrorActionPreference = $prevEap
    if ($status -eq "healthy" -or $status -eq "running") { $healthy = $true; break }
    Start-Sleep -Seconds 3
}

Write-Host ""
if ($healthy) {
    Write-Host "Restore complete; backend is running." -ForegroundColor Green
}
else {
    Write-Host "Restore finished but backend is not healthy yet. Check: docker compose logs backend" -ForegroundColor Yellow
}

$dbUser = "iot_parking"; $dbName = "iot_parking"
if ($envText) {
    if ($envText -match "(?m)^\s*POSTGRES_USER\s*=\s*(\S+)") { $dbUser = $Matches[1] }
    if ($envText -match "(?m)^\s*POSTGRES_DB\s*=\s*(\S+)") { $dbName = $Matches[1] }
}
Write-Host "Verify data (sessions/invoices):"
Write-Host ("  docker compose exec -T db psql -U {0} -d {1} -c `"SELECT COUNT(*) FROM parking_sessions;`"" -f $dbUser, $dbName)
