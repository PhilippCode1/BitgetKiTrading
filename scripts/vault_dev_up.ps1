#Requires -Version 5.1
<#
.SYNOPSIS
  Startet lokalen Vault-Dev (Docker) und wartet auf Health.

.EXAMPLE
  pwsh scripts/vault_dev_up.ps1
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

function Test-DockerDaemon {
    try {
        docker info *> $null
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-DockerDaemon)) {
    Write-Host "FAIL: Docker-Daemon laeuft nicht." -ForegroundColor Red
    Write-Host ""
    Write-Host "1. Docker Desktop starten und warten bis 'Running'"
    Write-Host "2. Erneut: pnpm vault:dev:up"
    Write-Host "3. Dann:    pnpm vault:dev:seed"
    Write-Host "4. Check:   pnpm vault:status"
    exit 1
}

Write-Host "==> Vault Dev Container starten" -ForegroundColor Cyan
docker compose -f docker-compose.yml -f docker-compose.vault-dev.yml up -d vault
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$py = (Get-Command python -ErrorAction SilentlyContinue)?.Source
if (-not $py) { $py = (Get-Command python3 -ErrorAction SilentlyContinue)?.Source }
if (-not $py) {
    Write-Warning "python fehlt — Health-Wait uebersprungen."
    Write-Host "Weiter mit: pnpm vault:dev:seed"
    exit 0
}

Write-Host "==> Warte auf Vault Health (max 60s)" -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds(60)
do {
    & $py tools/check_vault_runtime.py --env-file .env.vault-dev.example 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "PASS Vault bereit auf http://127.0.0.1:8200" -ForegroundColor Green
        Write-Host "Weiter mit: pnpm vault:dev:seed"
        exit 0
    }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)

Write-Host "FAIL: Vault nicht rechtzeitig erreichbar." -ForegroundColor Red
exit 1
