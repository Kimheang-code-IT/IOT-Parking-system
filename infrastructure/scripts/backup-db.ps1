<#
.SYNOPSIS
  Create a timestamped PostgreSQL backup of the running stack.

.DESCRIPTION
  Runs pg_dump (custom format) inside the db container, validates the dump,
  copies it to a host directory outside Docker (default: infrastructure/backups)
  and removes the container-side temp file.

  Passwords are never printed: pg_dump uses the in-container trust socket and
  the POSTGRES_* variables already configured for the service.

.EXAMPLE
  .\backup-db.ps1
  .\backup-db.ps1 -OutputDir D:\Backups\iot-parking
  .\backup-db.ps1 -KeepDays 14
#>
#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$OutputDir,
    [int]$KeepDays = 0
)

$ErrorActionPreference = "Stop"
$InfraDir = Split-Path -Parent $PSScriptRoot
Set-Location $InfraDir

function Fail([string]$Message) {
    Write-Host "[X] $Message" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail "Docker CLI not found." }

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$dbId = docker compose ps -q db 2>$null
$ErrorActionPreference = $prevEap
if (-not $dbId) {
    Fail "The db container is not running. Start the stack first: .\scripts\start.ps1 -NoBuild"
}
$dbState = docker inspect --format "{{.State.Status}}" $dbId
if ($dbState -ne "running") {
    Fail "The db container is not running (state: $dbState)."
}

if (-not $OutputDir) {
    $OutputDir = "backups"
    if (Test-Path ".env") {
        $envText = Get-Content ".env" -Raw
        if ($envText -match "(?m)^\s*BACKUP_DIR\s*=\s*(\S+)") { $OutputDir = $Matches[1] }
    }
}
if (-not [System.IO.Path]::IsPathRooted($OutputDir)) {
    $OutputDir = Join-Path $InfraDir $OutputDir
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$fileName = "iot-parking-$timestamp.dump"
$hostFile = Join-Path $OutputDir $fileName
$containerFile = "/tmp/$fileName"

Write-Host "Creating backup inside the db container ..."
docker compose exec -T db sh -c "pg_dump -U `"`$POSTGRES_USER`" -d `"`$POSTGRES_DB`" -Fc -f $containerFile"
if ($LASTEXITCODE -ne 0) { Fail "pg_dump failed (see output above)." }

Write-Host "Validating dump ..."
docker compose exec -T db sh -c "pg_restore --list $containerFile > /dev/null"
if ($LASTEXITCODE -ne 0) { Fail "pg_restore --list could not read the dump - backup is invalid." }

Write-Host "Copying backup to host ($hostFile) ..."
docker compose cp "db:$containerFile" "$hostFile"
if ($LASTEXITCODE -ne 0) { Fail "Could not copy the backup file to the host." }

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
docker compose exec -T db rm -f $containerFile *> $null
$ErrorActionPreference = $prevEap

$fileInfo = Get-Item $hostFile
if ($fileInfo.Length -lt 1024) {
    Fail "Backup file is suspiciously small ($($fileInfo.Length) bytes). Investigate before relying on it."
}

Write-Host ""
Write-Host ("Backup complete: {0} ({1:N1} KB)" -f $hostFile, ($fileInfo.Length / 1KB)) -ForegroundColor Green

if ($KeepDays -gt 0) {
    $cutoff = (Get-Date).AddDays(-$KeepDays)
    Get-ChildItem $OutputDir -Filter "iot-parking-*.dump" |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        ForEach-Object {
            Write-Host ("Removing old backup (>{0} days): {1}" -f $KeepDays, $_.Name)
            Remove-Item $_.FullName -Force
        }
}

Write-Host "Restore with: .\scripts\restore-db.ps1 -BackupFile `"$hostFile`""
