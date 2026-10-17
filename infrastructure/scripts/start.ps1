<#
.SYNOPSIS
  Start the Smart IoT Parking Docker stack (build -> db -> migrate -> up).

.DESCRIPTION
  1. Verifies Docker Desktop and Docker Compose are available.
  2. Ensures infrastructure/.env exists and has real values.
  3. Builds the backend/frontend images (unless -NoBuild).
  4. Starts PostgreSQL and waits for it to become healthy.
  5. Runs the one-off database migration service (unless -SkipMigrate).
  6. Starts backend, frontend and nginx, waits for health, prints URLs.

.EXAMPLE
  .\start.ps1
  .\start.ps1 -NoBuild -SkipMigrate
#>
#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$NoBuild,
    [switch]$SkipMigrate,
    [int]$TimeoutSeconds = 300
)

$ErrorActionPreference = "Stop"
$InfraDir = Split-Path -Parent $PSScriptRoot
Set-Location $InfraDir

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "[X] $Message" -ForegroundColor Red
    exit 1
}

function Wait-ServiceHealthy([string]$Service, [int]$TimeoutSec) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $id = docker compose ps -q $Service 2>$null
        $status = ""
        if ($id) {
            $status = docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" $id 2>$null
        }
        $ErrorActionPreference = $prevEap
        if ($status -eq "healthy" -or $status -eq "running") { return $true }
        Start-Sleep -Seconds 3
    }
    return $false
}

function Get-LanIp {
    try {
        $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction Stop |
            Sort-Object RouteMetric, IfIndex | Select-Object -First 1
        if ($route) {
            $ip = Get-NetIPAddress -InterfaceIndex $route.IfIndex -AddressFamily IPv4 -ErrorAction Stop |
                Where-Object { $_.IPAddress -notlike "169.254.*" } |
                Select-Object -First 1 -ExpandProperty IPAddress
            if ($ip) { return $ip }
        }
    }
    catch { }
    return (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -ne "127.0.0.1" -and $_.IPAddress -notlike "169.254.*" } |
        Select-Object -First 1 -ExpandProperty IPAddress)
}

Write-Host ""
Write-Host "=== Smart IoT Parking - starting Docker stack ===" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------- prerequisites
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker CLI not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
}
# NOTE: Windows PowerShell 5.1 turns *redirected* native stderr into a
# terminating error while ErrorActionPreference is 'Stop'. Native docker
# probes below run with 'Continue' and rely on $LASTEXITCODE.
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
docker info *> $null
$dockerInfoExit = $LASTEXITCODE
docker compose version *> $null
$composeExit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($dockerInfoExit -ne 0) {
    Fail "Docker daemon is not running. Start Docker Desktop and try again."
}
if ($composeExit -ne 0) {
    Fail "docker compose (v2) is not available. Update Docker Desktop."
}

# ---------------------------------------------------------------- configuration
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Fail "Created infrastructure/.env from .env.example. Fill in POSTGRES_PASSWORD, secrets and tokens, then re-run start.ps1."
}

$envText = Get-Content ".env" -Raw
if ($envText -notmatch "POSTGRES_PASSWORD\s*=\s*\S+") {
    Fail "POSTGRES_PASSWORD is empty in infrastructure/.env."
}
if ($envText -match "CHANGE_ME_postgres_password") {
    Fail "POSTGRES_PASSWORD still contains the placeholder. Edit infrastructure/.env first."
}
$remainingPlaceholders = ([regex]::Matches($envText, "CHANGE_ME_[a-z_]+")).Count
if ($remainingPlaceholders -gt 0) {
    Write-Host "[!] .env still contains $remainingPlaceholders CHANGE_ME placeholder(s) (e.g. tokens/secrets)." -ForegroundColor Yellow
    Write-Host "    The stack will start, but device authentication and payments will not be secure." -ForegroundColor Yellow
    Write-Host ""
}

# ---------------------------------------------------------------- build
if (-not $NoBuild) {
    Write-Host "[1/5] Building images (backend, frontend, migrate) ..."
    docker compose build
    if ($LASTEXITCODE -ne 0) { Fail "Image build failed. See the output above." }
}
else {
    Write-Host "[1/5] Skipping build (-NoBuild)."
}

# ---------------------------------------------------------------- database
Write-Host "[2/5] Starting PostgreSQL and waiting for health ..."
docker compose up -d db
if ($LASTEXITCODE -ne 0) { Fail "Could not start the db service." }
if (-not (Wait-ServiceHealthy "db" 120)) {
    Fail "PostgreSQL did not become healthy in time. Check: docker compose logs db"
}

# ---------------------------------------------------------------- migrations
if (-not $SkipMigrate) {
    Write-Host "[3/5] Applying database migrations (one-off service) ..."
    docker compose --profile migrate run --rm migrate
    if ($LASTEXITCODE -ne 0) { Fail "Database migration failed. See the output above." }
}
else {
    Write-Host "[3/5] Skipping migrations (-SkipMigrate). The API bootstraps missing tables itself."
}

# ---------------------------------------------------------------- start all
Write-Host "[4/5] Starting backend, frontend and nginx ..."
docker compose up -d
if ($LASTEXITCODE -ne 0) { Fail "docker compose up failed." }

Write-Host "[5/5] Waiting for services to report healthy (timeout ${TimeoutSeconds}s) ..."
$services = @("backend", "frontend", "nginx")
$allHealthy = $true
foreach ($svc in $services) {
    if (Wait-ServiceHealthy $svc $TimeoutSeconds) {
        Write-Host ("  [ok]   {0}" -f $svc) -ForegroundColor Green
    }
    else {
        $allHealthy = $false
        Write-Host ("  [warn] {0} not healthy yet" -f $svc) -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------- status/URLs
Write-Host ""
docker compose ps
Write-Host ""

$port = 80
if ($envText -match "(?m)^\s*HTTP_PORT\s*=\s*(\d+)") { $port = [int]$Matches[1] }
$portSuffix = if ($port -eq 80) { "" } else { ":$port" }
$lanIp = Get-LanIp

if ($allHealthy) {
    Write-Host "Application URLs:" -ForegroundColor Cyan
    Write-Host ("  Dashboard (local) : http://localhost{0}" -f $portSuffix)
    Write-Host ("  API docs (local)  : http://localhost{0}/docs" -f $portSuffix)
    if ($lanIp) {
        Write-Host ("  Dashboard (LAN)   : http://{0}{1}" -f $lanIp, $portSuffix)
        Write-Host ("  ESP32 base URL    : http://{0}{1}   (set PARKING_API_BASE_URL accordingly)" -f $lanIp, $portSuffix)
    }
    Write-Host ""
    Write-Host "ESP32 checklist: same Wi-Fi as this PC, firewall allows TCP port $port (scripts print a command in the README)." -ForegroundColor DarkGray
}
else {
    Write-Host "Some services are not healthy yet. Check logs: docker compose logs -f" -ForegroundColor Yellow
    exit 2
}
