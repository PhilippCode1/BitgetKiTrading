#Requires -Version 5.1
<#
.SYNOPSIS
  Docker Compose: Build, Start, Health-Warten, Ports, optional Browser.

.DESCRIPTION
  Entspricht dev_up ohne Browser-Pflicht: Basis + local-publish (wie bootstrap_stack local).

.EXAMPLE
  pwsh scripts/compose_up.ps1
  pwsh scripts/compose_up.ps1 -EnvFile .env.local -NoBuild
  pwsh scripts/compose_up.ps1 -NoOpen
  pwsh scripts/compose_up.ps1 -NoMint
  pwsh scripts/compose_up.ps1 -NoLocalPublish
#>
param(
    [string] $EnvFile = ".env.local",
    [switch] $NoLocalPublish,
    [switch] $NoBuild,
    [switch] $NoOpen,
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
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

. (Join-Path $PSScriptRoot "_dev_compose.ps1")
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
    if ($LASTEXITCODE -ne 0) { throw "compose_start_preflight fehlgeschlagen" }
}

$upArgs = @("compose", "--env-file", $EnvFile) + $composeFileArgs + @("up", "-d")
if (-not $NoBuild) { $upArgs += "--build" }

Write-Host "==> docker $($upArgs -join ' ')"
& docker @upArgs
if ($LASTEXITCODE -ne 0) { throw "docker compose up fehlgeschlagen (Exit $LASTEXITCODE)" }

Wait-DevStackHealthy -RepoRoot $Root -EnvFile $EnvFile -ComposeFileArgs $composeFileArgs `
    -WaitTimeoutSec $WaitTimeoutSec -PollSec $PollSec

$edgeHost = Get-DevEdgeHost -RepoRoot $Root -EnvFile $EnvFile
Show-DevPortSummary -EdgeHost $edgeHost -WithLocalPublish:(-not $NoLocalPublish)

Write-Host "`n==> docker compose ps"
& docker compose --env-file $EnvFile @composeFileArgs ps

Open-DevBrowserTabs -EdgeHost $edgeHost -NoOpen:$NoOpen

Write-Host "`n==> compose_up.ps1 fertig."
