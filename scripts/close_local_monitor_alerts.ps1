#Requires -Version 5.1
<#
.SYNOPSIS
  Schliesst offene monitor-engine Alerts in ops.alerts (nur lokale Dev-Profile).

.DESCRIPTION
  docker compose exec -T postgres psql ...
  - PublicProbe: scripts/sql/close_open_monitor_alerts_local.sql
  - AllOpen: ALLE state=open -> resolved (aggressiv) - zusaetzlich -Force erforderlich

  Bricht ab, wenn die Env-Datei PRODUCTION=true oder APP_ENV shadow/production setzt
  (Ausnahme: -DangerouslyIgnoreProductionGuard nur fuer Notfall-Recovery mit Schriftfreigabe).

.EXAMPLE
  pwsh scripts/close_local_monitor_alerts.ps1
  pwsh scripts/close_local_monitor_alerts.ps1 -Scope AllOpen -Force
#>
param(
    [string] $EnvFile = ".env.local",
    [string] $ComposeFile = "docker-compose.yml",
    [ValidateSet("PublicProbe", "AllOpen")]
    [string] $Scope = "PublicProbe",
    [switch] $Force,
    [switch] $DangerouslyIgnoreProductionGuard
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

$ef = Join-Path $Root $EnvFile
if (-not (Test-Path -LiteralPath $ef)) {
    throw "Env-Datei fehlt: $ef"
}

if ($Scope -eq "AllOpen" -and -not $Force) {
    throw "Scope AllOpen erfordert -Force (bewusste Bestaetigung)."
}

function Get-DotEnvValue {
    param([string] $Path, [string] $Key)
    foreach ($line in Get-Content -LiteralPath $Path -ErrorAction Stop) {
        $t = $line.Trim()
        if ($t.StartsWith("#") -or -not $t) { continue }
        if ($t -match "^\s*${Key}\s*=\s*(.*)$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

if (-not $DangerouslyIgnoreProductionGuard) {
    $prodRaw = Get-DotEnvValue -Path $ef -Key "PRODUCTION"
    $prodOn = $false
    if ($prodRaw) {
        $v = $prodRaw.Trim().ToLowerInvariant()
        if ($v -in @("1", "true", "yes", "on")) { $prodOn = $true }
    }
    $appEnv = (Get-DotEnvValue -Path $ef -Key "APP_ENV")
    $ae = if ($appEnv) { $appEnv.Trim().ToLowerInvariant() } else { "" }
    $badEnv = $ae -in @("shadow", "production")
    if ($prodOn -or $badEnv) {
        throw (
            "Abbruch: $EnvFile sieht nach Produktions-/Shadow-Profil aus " +
            "(PRODUCTION=$prodRaw APP_ENV=$appEnv). Alert-Massenschliessung nur fuer lokales Dev. " +
            "Bei dokumentierter Notfall-Freigabe: -DangerouslyIgnoreProductionGuard"
        )
    }
}

$pgUser = Get-DotEnvValue -Path $ef -Key "POSTGRES_USER"
if (-not $pgUser) { $pgUser = "postgres" }
$pgDb = Get-DotEnvValue -Path $ef -Key "POSTGRES_DB"
if (-not $pgDb) { $pgDb = "bitget_ai" }

$sqlRel = if ($Scope -eq "AllOpen") {
    "scripts\sql\close_open_monitor_alerts_local_all.sql"
} else {
    "scripts\sql\close_open_monitor_alerts_local.sql"
}
$sqlPath = Join-Path $Root $sqlRel
$sql = Get-Content -LiteralPath $sqlPath -Raw -Encoding UTF8

$null = Get-Command docker -ErrorAction Stop

Write-Host "==> ops.alerts Scope=$Scope (psql -U $pgUser -d $pgDb)" -ForegroundColor Cyan
$sql | & docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres `
    psql -v ON_ERROR_STOP=1 -U $pgUser -d $pgDb

if ($LASTEXITCODE -ne 0) {
    throw "psql fehlgeschlagen (Exit $LASTEXITCODE). Laeuft postgres? docker compose ps"
}
Write-Host "OK." -ForegroundColor Green
