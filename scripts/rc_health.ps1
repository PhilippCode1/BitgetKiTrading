#Requires -Version 5.1
<#
.SYNOPSIS
  Release-Candidate Edge-Health (Python, kein Git-Bash/curl noetig).

.DESCRIPTION
  Nutzt scripts/rc_health_runner.py (laedt .env.local, setzt URLs aus COMPOSE_EDGE_BIND)
  und scripts/rc_health_edge.py. Linux/macOS: scripts/rc_health.sh

.EXAMPLE
  pwsh scripts/rc_health.ps1
  pwsh scripts/rc_health.ps1 -EnvFile .env.local
  pwsh scripts/rc_health.ps1 -Stress
#>
param(
  [string] $EnvFile = ".env.local",
  [switch] $Stress
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "_dev_compose.ps1")

Set-Location -LiteralPath $Root
Assert-DevEnvFile -RepoRoot $Root -EnvFile $EnvFile

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction Stop }

$rcRunner = Join-Path $PSScriptRoot "rc_health_runner.py"
if ($Stress) {
  & $py.Source $rcRunner "--stress" $EnvFile
} else {
  & $py.Source $rcRunner $EnvFile
}
exit $LASTEXITCODE
