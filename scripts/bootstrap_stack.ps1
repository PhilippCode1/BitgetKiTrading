#Requires -Version 5.1
<#
.SYNOPSIS
  Windows-Aequivalent zu scripts/bootstrap_stack.sh: staged Docker-Compose-Start + Migrationen.

.EXAMPLE
  pwsh scripts/bootstrap_stack.ps1 production
  pwsh scripts/bootstrap_stack.ps1 local
  pwsh scripts/bootstrap_stack.ps1 shadow -WithObservability
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("local", "shadow", "production")]
    [string] $Profile,

    [switch] $WithObservability,
    [switch] $NoBuild,
    [switch] $SkipMigrations,
    [int] $WaitTimeoutSec = 300,
    [int] $PollIntervalSec = 2,
    [int] $BootstrapPollMaxSec = 10
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

$envFile = switch ($Profile) {
    "local" { ".env.local" }
    "shadow" { ".env.shadow" }
    "production" { ".env.production" }
}

if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Fehlendes Profil: $envFile. Kopiere .env.$Profile.example nach $envFile und setze Secrets (z. B. POSTGRES_PASSWORD, BITGET_*, OPENAI_*)."
}

function Resolve-PythonBootstrap {
    foreach ($c in @("python", "python3")) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    throw "Kein python/python3 im PATH."
}

$validator = Join-Path $Root "tools\validate_env_profile.py"
$pyValidate = Get-Command python -ErrorAction SilentlyContinue
$fullEnv = Join-Path $Root $envFile
$pythonBin = Resolve-PythonBootstrap

if ($Profile -eq "shadow") {
    $mintPy = Join-Path $Root "scripts\mint_dashboard_gateway_jwt.py"
    if (Test-Path -LiteralPath $mintPy) {
        Write-Host "==> JWT fuer Dashboard->Gateway (Shadow: DASHBOARD_GATEWAY_AUTHORIZATION, Standard wie local)" -ForegroundColor Cyan
        Write-Host "    Hinweis: Dashboard-Container nach Aenderung an .env.shadow neu erstellen (compose up --force-recreate dashboard)." -ForegroundColor DarkGray
        & $pythonBin $mintPy --env-file $fullEnv --update-env-file
        if ($LASTEXITCODE -ne 0) {
            throw "mint_dashboard_gateway_jwt (shadow) fehlgeschlagen. PyJWT: pip install -r requirements-dev.txt"
        }
    }
}

if ($pyValidate -and (Test-Path -LiteralPath $validator)) {
    $map = @{ local = "local"; shadow = "shadow"; production = "production" }
    $pyProfile = $map[$Profile]
    & $pyValidate.Source $validator --env-file $fullEnv --profile $pyProfile
    if ($LASTEXITCODE -ne 0) {
        throw "ENV-Validierung fehlgeschlagen ($validator). Siehe docs/CONFIGURATION.md"
    }
}

function Import-DotEnvFile {
    param([string] $Path)
    Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.TrimEnd("`r")
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) { return }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { return }
        $key = $line.Substring(0, $eq).Trim()
        $val = $line.Substring($eq + 1).Trim()
        [Environment]::SetEnvironmentVariable($key, $val, "Process")
    }
}

Import-DotEnvFile $envFile
$env:COMPOSE_ENV_FILE = $envFile

if (-not $env:POSTGRES_DB) { $env:POSTGRES_DB = "bitget_ai" }
if (-not $env:POSTGRES_USER) { $env:POSTGRES_USER = "postgres" }
if (
    ([string]::IsNullOrWhiteSpace($env:DATABASE_URL_DOCKER)) -and
    -not [string]::IsNullOrWhiteSpace($env:POSTGRES_PASSWORD)
) {
    $u = $env:POSTGRES_USER
    $db = $env:POSTGRES_DB
    $env:DATABASE_URL_DOCKER = "postgresql://${u}:$($env:POSTGRES_PASSWORD)@postgres:5432/${db}"
}
if ([string]::IsNullOrWhiteSpace($env:REDIS_URL_DOCKER)) {
    $env:REDIS_URL_DOCKER = "redis://redis:6379/0"
}

$composeFiles = @()
switch ($Profile) {
    "local" { $composeFiles = @("-f", "docker-compose.yml", "-f", "docker-compose.local-publish.yml") }
    default { $composeFiles = @("-f", "docker-compose.yml") }
}

$buildImages = -not $NoBuild
$runMigrations = -not $SkipMigrations

if ($Profile -eq "local") {
    $mintPy = Join-Path $Root "scripts\mint_dashboard_gateway_jwt.py"
    if (Test-Path -LiteralPath $mintPy) {
        Write-Host "==> JWT fuer Dashboard->Gateway (DASHBOARD_GATEWAY_AUTHORIZATION)"
        & $pythonBin $mintPy --env-file $fullEnv --update-env-file
        if ($LASTEXITCODE -ne 0) {
            throw "mint_dashboard_gateway_jwt fehlgeschlagen. PyJWT: pip install -r requirements-dev.txt"
        }
    }
    if ($pyValidate -and (Test-Path -LiteralPath $validator)) {
        Write-Host "==> validate_env_profile (mit DASHBOARD_GATEWAY_AUTHORIZATION nach Mint)"
        & $pythonBin $validator --env-file $fullEnv --profile local --with-dashboard-operator
        if ($LASTEXITCODE -ne 0) {
            throw "ENV-Validierung nach Mint fehlgeschlagen. Siehe docs/CONFIGURATION.md"
        }
    }
}

function Invoke-StackCompose {
    param([string[]] $ComposeArgs)
    $env:COMPOSE_ENV_FILE = $envFile
    $env:DATABASE_URL_DOCKER = $env:DATABASE_URL_DOCKER
    $env:REDIS_URL_DOCKER = $env:REDIS_URL_DOCKER
    $env:POSTGRES_DB = $env:POSTGRES_DB
    $env:POSTGRES_USER = $env:POSTGRES_USER
    $env:POSTGRES_PASSWORD = $env:POSTGRES_PASSWORD
    & docker @("compose") @composeFiles @("--env-file", $envFile) @ComposeArgs
    if ($LASTEXITCODE -ne 0) { throw "docker compose failed: $ComposeArgs" }
}

function Get-DatastoreMode {
    $d = $env:DATABASE_URL_DOCKER
    $r = $env:REDIS_URL_DOCKER
    if (($d -like "*@postgres:*") -or ($r -like "redis://redis:*")) {
        return "compose"
    }
    return "external"
}

$datastoreMode = Get-DatastoreMode

function Test-ExternalDatastores {
    Write-Host "==> Externe Datastores pruefen"
    $env:DATABASE_URL = $env:DATABASE_URL
    $env:REDIS_URL = $env:REDIS_URL
    $code = @'
import os
import psycopg
import redis
dsn = os.environ.get("DATABASE_URL", "").strip()
rurl = os.environ.get("REDIS_URL", "").strip()
if not dsn:
    raise SystemExit("DATABASE_URL fehlt fuer externen Datastore-Modus")
if not rurl:
    raise SystemExit("REDIS_URL fehlt fuer externen Datastore-Modus")
with psycopg.connect(dsn, connect_timeout=5, autocommit=True) as conn:
    conn.execute("select 1")
client = redis.Redis.from_url(rurl, socket_connect_timeout=5, socket_timeout=5)
if not client.ping():
    raise SystemExit("Redis ping fehlgeschlagen")
print("external datastores ok")
'@
    & $pythonBin -c $code
    if ($LASTEXITCODE -ne 0) { throw "Externe Datastores nicht erreichbar." }
}

function Wait-ComposeService {
    param([string] $ServiceName)
    $deadline = [DateTime]::UtcNow.AddSeconds($WaitTimeoutSec)
    $cid = ""
    $pollN = 0
    while ([DateTime]::UtcNow -lt $deadline) {
        $out = & docker @("compose") @composeFiles @("--env-file", $envFile) @("ps", "-q", $ServiceName) 2>$null
        if ($out) {
            $cid = ($out | Out-String).Trim()
            if ($cid) { break }
        }
        $pollN++
        $sleepSec = [Math]::Min($BootstrapPollMaxSec, $PollIntervalSec + [int]($pollN / 4))
        Start-Sleep -Seconds $sleepSec
    }
    if (-not $cid) {
        Write-Host "---- letzte Logs: $ServiceName ----"
        & docker @("compose") @composeFiles @("--env-file", $envFile) @("logs", "--tail", "120", $ServiceName) 2>$null
        throw "FAIL ${ServiceName}: kein Container aus docker compose ps"
    }

    $pollN = 0
    $status = ""
    while ([DateTime]::UtcNow -lt $deadline) {
        $fmt = '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}'
        $status = (& docker @("inspect", "--format", $fmt, $cid)).Trim()
        if ($status -eq "healthy" -or $status -eq "running") {
            Write-Host "OK  $ServiceName (docker state: $status)"
            return
        }
        if ($status -eq "unhealthy" -or $status -eq "exited" -or $status -eq "dead") {
            Write-Host "---- letzte Logs: $ServiceName ----"
            & docker @("compose") @composeFiles @("--env-file", $envFile) @("logs", "--tail", "120", $ServiceName) 2>$null
            throw "FAIL $ServiceName (docker state: $status)"
        }
        $pollN++
        $sleepSec = [Math]::Min($BootstrapPollMaxSec, $PollIntervalSec + [int]($pollN / 3))
        Start-Sleep -Seconds $sleepSec
    }
    Write-Host "---- letzte Logs: $ServiceName ----"
    & docker @("compose") @composeFiles @("--env-file", $envFile) @("logs", "--tail", "120", $ServiceName) 2>$null
    throw "FAIL $ServiceName (timeout; letzter Status: $status)"
}

function Invoke-RunMigrations {
    if (-not $runMigrations) {
        Write-Host "==> Migrationen uebersprungen (-SkipMigrations)"
        return
    }
    Write-Host "==> Migrationen anwenden (kanonisch + optional demo-seeds)"
    $env:DATABASE_URL = $env:DATABASE_URL
    & $pythonBin "infra/migrate.py"
    if ($LASTEXITCODE -ne 0) { throw "migrate.py fehlgeschlagen" }
    & $pythonBin "infra/migrate.py" "--demo-seeds"
    if ($LASTEXITCODE -ne 0) { throw "migrate.py --demo-seeds fehlgeschlagen" }
}

function Invoke-BuildApplicationImages {
    if (-not $buildImages) { return }
    Write-Host "==> Baue Applikations-Images einmalig"
    Invoke-StackCompose @(
        "build",
        "market-stream", "llm-orchestrator", "feature-engine", "structure-engine", "news-engine",
        "drawing-engine", "signal-engine", "paper-broker", "live-broker", "learning-engine",
        "api-gateway", "alert-engine", "monitor-engine", "dashboard"
    )
    $script:buildImages = $false
}

function Start-Stage {
    param([string] $Label, [string[]] $Services)
    Write-Host "==> Stage: $Label"
    Write-Host ("    Dienste: " + ($Services -join " "))
    $upArgs = @("up", "-d", "--no-deps")
    if ($buildImages) { $upArgs += "--build" }
    Invoke-StackCompose ($upArgs + $Services)
    foreach ($s in $Services) {
        Wait-ComposeService $s
    }
}

function Start-ObservabilityStage {
    if (-not $WithObservability) { return }
    Write-Host "==> Stage: observability"
    Invoke-StackCompose @("--profile", "observability", "up", "-d", "--no-deps", "prometheus", "grafana")
    Wait-ComposeService "prometheus"
    Wait-ComposeService "grafana"
}

. (Join-Path $PSScriptRoot "docker-path.ps1")
Initialize-DockerDesktopPath
$null = Get-Command docker -ErrorAction Stop

$preflightPy = Join-Path $Root "tools\compose_start_preflight.py"
if (Test-Path -LiteralPath $preflightPy) {
    Write-Host "==> compose_start_preflight ($Profile)" -ForegroundColor Cyan
    & $pythonBin $preflightPy --env-file $fullEnv --profile $Profile
    if ($LASTEXITCODE -ne 0) {
        throw "compose_start_preflight fehlgeschlagen - docker compose config oder POSTGRES_PASSWORD pruefen."
    }
}

Write-Host "==> Bootstrap Profil=$Profile env=$envFile datastores=$datastoreMode build=$buildImages observability=$WithObservability"

if ($datastoreMode -eq "compose") {
    Write-Host "==> Stage: datastores"
    Invoke-StackCompose @("up", "-d", "postgres", "redis")
    Wait-ComposeService "postgres"
    Wait-ComposeService "redis"
}
else {
    Test-ExternalDatastores
}

Invoke-RunMigrations
Invoke-BuildApplicationImages

Start-Stage "1-kernfeeds" @("market-stream", "llm-orchestrator")
Start-Stage "2-ableitende-engines" @("feature-engine", "structure-engine", "news-engine")
Start-Stage "3-signale" @("drawing-engine", "signal-engine")
Start-Stage "4-broker-live" @("paper-broker", "live-broker")
Start-Stage "5-learning" @("learning-engine")
Start-Stage "6-alert-vor-gateway" @("alert-engine")
Start-Stage "7-gateway" @("api-gateway")
Start-Stage "8-monitor" @("monitor-engine")
Start-ObservabilityStage
Start-Stage "dashboard" @("dashboard")

Write-Host "==> Finaler Smoke-Test"
if ($Profile -eq "shadow" -or $Profile -eq "production") {
    $env:HEALTHCHECK_EDGE_ONLY = "true"
}
$pf86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
$bashCandidates = @(
    (Join-Path $env:ProgramFiles "Git\bin\bash.exe")
)
if ($pf86) {
    $bashCandidates += (Join-Path $pf86 "Git\bin\bash.exe")
}
$bashCandidates += "bash"
$bashExe = $null
foreach ($b in $bashCandidates) {
    if ($b -eq "bash") {
        $cmd = Get-Command bash -ErrorAction SilentlyContinue
        if ($cmd) { $bashExe = $cmd.Source; break }
    }
    elseif (Test-Path -LiteralPath $b) {
        $bashExe = $b
        break
    }
}
if (-not $bashExe) {
    Write-Warning "bash nicht gefunden (Git for Windows). Healthcheck uebersprungen - bitte manuell: bash scripts/healthcheck.sh"
}
else {
    Push-Location $Root
    try {
        & $bashExe "scripts/healthcheck.sh"
        if ($LASTEXITCODE -ne 0) { throw "healthcheck.sh Exit $LASTEXITCODE" }
    }
    finally {
        Pop-Location
    }
}

Write-Host "==> Bootstrap erfolgreich abgeschlossen"
