#Requires -Version 5.1
<#
.SYNOPSIS
  Prueft, ob API-Gateway und (optional) Dashboard erreichbar sind.

.EXAMPLE
  pwsh scripts/check_local_edge.ps1
#>
$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "docker-path.ps1")
Initialize-DockerDesktopPath
$Root = Split-Path -Parent $PSScriptRoot
$gwReady = "http://127.0.0.1:8000/ready"
$gwHealth = "http://127.0.0.1:8000/health"
$dashCandidates = @(
    "http://127.0.0.1:3000/api/health",
    "http://localhost:3000/api/health"
)

function Test-DockerAvailable {
    $cmd = Get-Command docker -ErrorAction SilentlyContinue
    if ($cmd) { return $true }
    $pf86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    $candidates = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe")
    )
    if ($pf86) {
        $candidates += (Join-Path $pf86 "Docker\Docker\resources\bin\docker.exe")
    }
    foreach ($p in $candidates) {
        if ($p -and (Test-Path -LiteralPath $p)) { return $true }
    }
    return $false
}

function Test-Url {
    param([string] $Label, [string] $Url, [int] $TimeoutSec = 8)
    Write-Host "==> $Label"
    Write-Host "    $Url"
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        Write-Host "    OK (HTTP $($r.StatusCode))"
        if ($r.Content.Length -lt 500) {
            Write-Host "    $($r.Content.Trim())"
        }
        return $true
    }
    catch {
        Write-Host "    FEHL: $($_.Exception.Message)"
        return $false
    }
}

Write-Host ""
Write-Host "Lokale Edge-Pruefung (127.0.0.1 vermeidet IPv6-localhost-Probleme unter Windows)."
Write-Host "Next.js laedt .env.local aus dem Repo-Root (apps/dashboard/next.config.js -> envDir)."
Write-Host ""

if (-not (Test-DockerAvailable)) {
    Write-Host "WARN: 'docker' nicht im PATH (Docker Desktop installiert und Shell neu gestartet?)."
    Write-Host "     Ohne Docker startet das API-Gateway unter :8000 typisch nicht."
    Write-Host ""
}

$okGw = Test-Url "API-Gateway /health" $gwHealth
$null = Test-Url "API-Gateway /ready" $gwReady

$okDash = $false
foreach ($dashHealth in $dashCandidates) {
    if (Test-Url "Dashboard /api/health" $dashHealth 15) {
        $okDash = $true
        break
    }
}

Write-Host ""
if (-not $okGw) {
    Write-Host "Das Dashboard (Next.js) allein reicht nicht: Monitor, Drift, Live-Daten kommen vom API-Gateway."
    Write-Host "Backend starten (Docker Desktop muss laufen und 'docker' im PATH sein):"
    Write-Host "  pnpm dev:up"
    Write-Host "  (alternativ: pnpm bootstrap:local / pwsh scripts/start_local.ps1)"
    Write-Host ""
    Write-Host "ENV: .env.local im Repo-ROOT (nicht unter apps/dashboard)."
    Write-Host "Nach Aenderung an .env.local: next dev / pnpm dev neu starten."
    Write-Host "Siehe docs/compose_runtime.md"
    Write-Host "Diagnose: pnpm local:doctor"
    exit 1
}

if (-not $okDash) {
    Write-Host "Hinweis: Gateway OK, Dashboard nicht erreichbar - z. B. pnpm dev in apps/dashboard oder Stack mit dashboard-Service."
}

Write-Host "OK - Gateway antwortet. Bei weiteren 503/502: Engines pruefen (docker compose ps, Logs)."
Write-Host "Tiefendiagnose (JWT, API_GATEWAY_URL, /ready): pnpm local:doctor"
exit 0
