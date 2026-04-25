#Requires -Version 5.1
<#
.SYNOPSIS
  Sammelt Release-/Freigabe-Nachweise: Compose-Status, oeffentliche Gateway-JSON, optional rc_health_edge.

.DESCRIPTION
  Schreibt nach artifacts/release-evidence/<timestamp>/ (JSON-Textdateien).
  Keine Secrets - nur oeffentliche Endpunkte und docker compose ps.
  Mit -BuildRun85Dossier: danach python tools/build_run85_dossier.py --ingest <evidence-ordner>
  (docs/release_evidence/85_final_release_dossier.md).

.EXAMPLE
  pwsh scripts/collect_release_evidence.ps1
  pwsh scripts/collect_release_evidence.ps1 -SkipRcHealth
  pwsh scripts/collect_release_evidence.ps1 -BuildRun85Dossier
#>
param(
    [string] $EnvFile = ".env.local",
    [string] $ComposeFile = "docker-compose.yml",
    [switch] $SkipRcHealth,
    [switch] $SkipComposePs,
    [switch] $BuildRun85Dossier
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $Root
. (Join-Path $PSScriptRoot "_dev_compose.ps1")
Assert-DevEnvFile -RepoRoot $Root -EnvFile $EnvFile
Initialize-DevDockerCli

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$outDir = Join-Path $Root "artifacts\release-evidence\$ts"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$edgeHost = Get-DevEdgeHost -RepoRoot $Root -EnvFile $EnvFile
$gw = "http://${edgeHost}:8000"
$dash = "http://${edgeHost}:3000"

function Write-JsonFile {
    param([string] $Name, [object] $Object)
    $path = Join-Path $outDir $Name
    $Object | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $path -Encoding UTF8
}

Write-Host "Evidenz-Ordner: $outDir" -ForegroundColor Cyan

if (-not $SkipComposePs) {
    Push-Location $Root
    try {
        $psLines = & docker compose --env-file $EnvFile -f $ComposeFile ps -a 2>&1 | ForEach-Object { $_.ToString() }
        Set-Content -LiteralPath (Join-Path $outDir "compose_ps.txt") -Value ($psLines -join "`n") -Encoding UTF8
    }
    finally {
        Pop-Location
    }
    Write-Host "OK  compose_ps.txt" -ForegroundColor Green
}

function Invoke-GwJson {
    param([string] $Path, [string] $OutName)
    $url = "$gw$Path"
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 15
        Set-Content -LiteralPath (Join-Path $outDir $OutName) -Value $r.Content -Encoding UTF8
        Write-Host "OK  $OutName" -ForegroundColor Green
    }
    catch {
        Set-Content -LiteralPath (Join-Path $outDir "${OutName}.error.txt") -Value $_.Exception.Message -Encoding UTF8
        Write-Host "FEHL $OutName : $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

Invoke-GwJson -Path "/health" -OutName "gateway_health.json"
Invoke-GwJson -Path "/v1/meta/surface" -OutName "meta_surface.json"
Invoke-GwJson -Path "/v1/deploy/edge-readiness" -OutName "deploy_edge_readiness.json"

try {
    $r = Invoke-WebRequest -Uri "$dash/api/health" -UseBasicParsing -TimeoutSec 15
    Set-Content -LiteralPath (Join-Path $outDir "dashboard_api_health.json") -Value $r.Content -Encoding UTF8
    Write-Host "OK  dashboard_api_health.json" -ForegroundColor Green
}
catch {
    Set-Content -LiteralPath (Join-Path $outDir "dashboard_api_health.error.txt") -Value $_.Exception.Message -Encoding UTF8
    Write-Host "Hinweis: Dashboard nicht erreichbar (ok wenn Stack ohne dashboard)." -ForegroundColor DarkGray
}

if (-not $SkipRcHealth) {
    $env:API_GATEWAY_URL = $gw
    $env:DASHBOARD_URL = $dash
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python3 -ErrorAction Stop }
    $logPath = Join-Path $outDir "rc_health_edge.stdout.txt"
    $lines = & $py.Source (Join-Path $PSScriptRoot "rc_health_edge.py") 2>&1
    $lines | Set-Content -LiteralPath $logPath -Encoding UTF8
    if ($LASTEXITCODE -eq 0) {
        Write-Host "OK  rc_health_edge (siehe rc_health_edge.stdout.txt)" -ForegroundColor Green
    }
    else {
        Write-Host "WARN rc_health_edge Exit $LASTEXITCODE - siehe $logPath" -ForegroundColor Yellow
    }
}

if ($BuildRun85Dossier) {
    $py = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $py) { $py = Get-Command python3 -ErrorAction Stop }
    if ($outDir) {
        & $py.Source (Join-Path $Root "tools\build_run85_dossier.py") "--ingest" $outDir
    } else {
        & $py.Source (Join-Path $Root "tools\build_run85_dossier.py")
    }
    if ($LASTEXITCODE -eq 0) {
        Write-Host "OK  Run-85 Dossier (docs/release_evidence/85_final_release_dossier.md)" -ForegroundColor Green
    } else {
        Write-Host "Hinweis: Säulen ggf. unvollständig (RC=$LASTEXITCODE) — pnpm release:gate:full + pnpm exec playwright test e2e/tests/run85_dossier_evidence.spec.ts" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Fertig. Inhalt anhaengen oder zip: $outDir" -ForegroundColor Cyan
