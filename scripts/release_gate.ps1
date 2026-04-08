#Requires -Version 5.1
<#
.SYNOPSIS
  Release-Gate (Python): API-Smoke, Dashboard-HTTP-Probe, optional Playwright.

.EXAMPLE
  pwsh scripts/release_gate.ps1
  $env:PLAYWRIGHT_E2E = "1"; pwsh scripts/release_gate.ps1
#>
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $Root
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction Stop }
& $py.Source (Join-Path $PSScriptRoot "release_gate.py")
exit $LASTEXITCODE
