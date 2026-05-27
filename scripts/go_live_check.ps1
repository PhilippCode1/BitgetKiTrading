#Requires -Version 5.1
<#
.SYNOPSIS
  Go-Live-Vorabprüfung (ein Einstieg): Launch-Checklist mit ENV, Ops-Preflight, Vault.

.EXAMPLE
  pwsh scripts/go_live_check.ps1
  pwsh scripts/go_live_check.ps1 -Strict
#>
param(
    [switch] $Strict,
    [string] $EnvFile = ".env.production",
    [switch] $SkipAudit
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

function Resolve-Python {
    foreach ($c in @("python", "python3")) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    throw "Kein python im PATH."
}

$py = Resolve-Python
$fullEnv = Join-Path $Root $EnvFile
$exampleEnv = Join-Path $Root ".env.production.example"

if (-not (Test-Path -LiteralPath $fullEnv)) {
    Write-Warning "Fehlt: $EnvFile — kopiere .env.production.example und setze Secrets."
    if (-not (Test-Path -LiteralPath $exampleEnv)) {
        throw ".env.production.example fehlt."
    }
    $fullEnv = $exampleEnv
    Write-Host "==> Fallback auf Template: .env.production.example" -ForegroundColor Yellow
}

$argsList = @(
    (Join-Path $Root "tools\go_live_launch_checklist.py"),
    "--env-file", $fullEnv
)
if ($Strict) { $argsList += "--strict-runtime" }
if ($SkipAudit) { $argsList += "--skip-audit" }

Write-Host "==> Go-Live Launch-Checklist" -ForegroundColor Cyan
& $py @argsList
exit $LASTEXITCODE
