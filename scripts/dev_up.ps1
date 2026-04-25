#Requires -Version 5.1
<#
.SYNOPSIS
  Ein-Klick: Stack starten, auf Gesundheit warten, Ports zeigen, Browser oeffnen.

.DESCRIPTION
  Nutzt dieselbe Compose-Kombination wie bootstrap_stack (local): docker-compose.yml +
  docker-compose.local-publish.yml - Host-Publish fuer Worker-Debugging (siehe docs/structure.md, docs/compose_runtime.md).
  Mit -NoLocalPublish nur Basis-Compose (Edge :8000/:3000, keine Worker-Ports auf dem Host).
  Schreibt standardmaessig DASHBOARD_GATEWAY_AUTHORIZATION per mint_dashboard_gateway_jwt.
  Optional: Datenbank/Redis-Volumes vorher leeren (-ResetDb).

.EXAMPLE
  pwsh scripts/dev_up.ps1
  pwsh scripts/dev_up.ps1 -ResetDb
  pwsh scripts/dev_up.ps1 -NoBuild -NoOpen
  pwsh scripts/dev_up.ps1 -Smoke   # nach Start: rc_health (Gateway/Dashboard)
  pwsh scripts/dev_up.ps1 -NoMint  # JWT in .env.local nicht anfassen (Experten)
  pwsh scripts/dev_up.ps1 -NoLocalPublish  # nur Edge-Ports (wie Shadow/Prod-Modell)
  pnpm dev:up:help                 # oder: pwsh scripts/dev_up.ps1 -Help
#>
param(
    [string] $EnvFile = ".env.local",
    [switch] $NoLocalPublish,
    [switch] $NoBuild,
    [switch] $NoOpen,
    [switch] $ResetDb,
    [switch] $Smoke,
    [switch] $NoMint,
    [switch] $Help,
    [int] $WaitTimeoutSec = 900,
    [int] $PollSec = 5
)

$ErrorActionPreference = "Stop"
if ($Help) {
    Get-Help $PSCommandPath -Full
    exit 0
}
. (Join-Path $PSScriptRoot "_dev_compose.ps1")

$Root = Get-DevRepoRoot
Set-Location -LiteralPath $Root
Assert-DevEnvFile -RepoRoot $Root -EnvFile $EnvFile
Assert-DevEnvCriticalForCompose -RepoRoot $Root -EnvFile $EnvFile
Invoke-DevMintDashboardGatewayJwt -RepoRoot $Root -EnvFile $EnvFile -Skip:$NoMint
if (-not $NoMint) {
    Assert-DevEnvCriticalForCompose -RepoRoot $Root -EnvFile $EnvFile -WithDashboardOperator
}
else {
    Warn-DevDashboardGatewayAuth -RepoRoot $Root -EnvFile $EnvFile
}
Initialize-DevDockerCli

$env:COMPOSE_ENV_FILE = $EnvFile

$composeFileArgs = Get-DevComposeFileArgs -NoLocalPublish:$NoLocalPublish
$fullEnvForPy = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $Root $EnvFile }

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
$preflight = Join-Path $Root "tools\compose_start_preflight.py"
if ($py -and (Test-Path -LiteralPath $preflight)) {
    Write-Host "==> compose_start_preflight (local)" -ForegroundColor Cyan
    & $py.Source $preflight --env-file $fullEnvForPy --profile local
    if ($LASTEXITCODE -ne 0) {
        throw "compose_start_preflight fehlgeschlagen - Compose-Config oder POSTGRES_PASSWORD pruefen."
    }
}

Write-Host ""
Write-Host "=== bitget-btc-ai - lokal starten ===" -ForegroundColor Cyan
Write-Host "Projektordner: $Root"
Write-Host "Env-Datei:     $EnvFile"
Write-Host "Compose:       $($composeFileArgs -join ' ')"
Write-Host ""

if ($ResetDb) {
    Write-Host "Du hast -ResetDb gewaehlt: Wir stoppen den Stack und entfernen die Daten-Volumes (Postgres + Redis)." -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot "dev_reset_db.ps1") -EnvFile $EnvFile -NoLocalPublish:$NoLocalPublish -Force
    Write-Host ""
}

$upArgs = @("compose", "--env-file", $EnvFile) + $composeFileArgs + @("up", "-d")
if (-not $NoBuild) { $upArgs += "--build" }

Write-Host "Starte Container: docker $($upArgs -join ' ')" -ForegroundColor Cyan
& docker @upArgs
if ($LASTEXITCODE -ne 0) {
    throw "docker compose up ist fehlgeschlagen (Exit-Code $LASTEXITCODE)."
}

Write-Host ""
Write-Host "Container sind angefordert. Wir pruefen jetzt die Healthchecks ..." -ForegroundColor Cyan

Wait-DevStackHealthy -RepoRoot $Root -EnvFile $EnvFile -ComposeFileArgs $composeFileArgs `
    -WaitTimeoutSec $WaitTimeoutSec -PollSec $PollSec

$edgeHost = Get-DevEdgeHost -RepoRoot $Root -EnvFile $EnvFile
Show-DevPortSummary -EdgeHost $edgeHost -WithLocalPublish:(-not $NoLocalPublish)

Write-Host "=== Container-Uebersicht ===" -ForegroundColor Green
& docker compose --env-file $EnvFile @composeFileArgs ps

Open-DevBrowserTabs -EdgeHost $edgeHost -NoOpen:$NoOpen

if ($Smoke) {
    Write-Host ""
    Write-Host "=== Smoke: rc_health (Gateway + Dashboard) ===" -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "rc_health.ps1") -EnvFile $EnvFile
    if ($LASTEXITCODE -ne 0) {
        throw "rc_health ist fehlgeschlagen (Exit-Code $LASTEXITCODE). Siehe Meldungen oben."
    }
}

Write-Host ""
if ($NoOpen) {
    Write-Host "Geschafft. Stack laeuft (-NoOpen: Browser bitte selbst oeffnen)." -ForegroundColor Green
}
else {
    Write-Host "Geschafft. Dashboard und API-Gateway sollten im Browser offen sein." -ForegroundColor Green
}
Write-Host "Hilfe:  pwsh scripts/dev_status.ps1   - Status anzeigen" -ForegroundColor DarkGray
Write-Host "        pwsh scripts/dev_logs.ps1    - Logs" -ForegroundColor DarkGray
Write-Host "        pwsh scripts/dev_down.ps1    - Stack stoppen" -ForegroundColor DarkGray
Write-Host "Stufen-Start (wie 02-Topologie): pwsh scripts/bootstrap_stack.ps1 local" -ForegroundColor DarkGray
Write-Host "Diagnose: pnpm local:doctor  (ENV, JWT, Gateway /health /ready vom Host)" -ForegroundColor DarkGray
Write-Host ""
