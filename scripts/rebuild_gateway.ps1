#Requires -Version 5.1
<#
.SYNOPSIS
  api-gateway Docker-Image neu bauen und Container neu starten (machine-Felder in /v1/system/health).

.EXAMPLE
  pwsh scripts/rebuild_gateway.ps1
  pwsh scripts/rebuild_gateway.ps1 -EnvFile .env.local
#>
param(
    [string] $EnvFile = ".env.local",
    [string] $ComposeFile = "docker-compose.yml"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $Root

$envPath = Join-Path $Root $EnvFile
if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Env-Datei fehlt: $envPath"
}

Write-Host "docker compose build api-gateway ..." -ForegroundColor Cyan
& docker compose --env-file $EnvFile -f $ComposeFile build api-gateway
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "docker compose up -d api-gateway ..." -ForegroundColor Cyan
& docker compose --env-file $EnvFile -f $ComposeFile up -d api-gateway
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Fertig. Pruefen: curl -s http://127.0.0.1:8000/v1/system/health (mit Auth) - Feld warnings_display[].machine" -ForegroundColor Green
