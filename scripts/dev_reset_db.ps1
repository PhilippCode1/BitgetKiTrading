#Requires -Version 5.1
<#
.SYNOPSIS
  Stack stoppen und Compose-Volumes (Postgres, Redis, ...) entfernen - naechster Start = leere DB + neue Migrationen.

.DESCRIPTION
  Nutzt dieselbe Compose-Datei-Kombination wie dev_up (Standard: mit local-publish).

.EXAMPLE
  pwsh scripts/dev_reset_db.ps1
  pwsh scripts/dev_reset_db.ps1 -Force
  pwsh scripts/dev_reset_db.ps1 -NoLocalPublish -Force
#>
param(
    [string] $EnvFile = ".env.local",
    [switch] $NoLocalPublish,
    [switch] $Force
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_dev_compose.ps1")

$Root = Get-DevRepoRoot
Set-Location -LiteralPath $Root
Assert-DevEnvFile -RepoRoot $Root -EnvFile $EnvFile
Initialize-DevDockerCli

if (-not $Force) {
    Write-Host "Alle Daten in den Compose-Volumes dieses Projekts gehen verloren (u. a. Postgres, Redis)." -ForegroundColor Yellow
    $yn = Read-Host "Fortfahren? (j/N)"
    if ($yn -notmatch '^(j|J|y|Y)$') {
        Write-Host "Abgebrochen." -ForegroundColor DarkGray
        exit 0
    }
}

$composeFileArgs = Get-DevComposeFileArgs -NoLocalPublish:$NoLocalPublish
Write-Host "Stoppe Stack und entferne Volumes ..." -ForegroundColor Cyan
& docker compose --env-file $EnvFile @composeFileArgs down -v
if ($LASTEXITCODE -ne 0) {
    throw "docker compose down -v fehlgeschlagen (Exit $LASTEXITCODE)."
}

Write-Host ""
Write-Host 'Erledigt. Beim naechsten dev_up.ps1 oder "docker compose up" werden Migrationen neu ausgefuehrt.' -ForegroundColor Green
Write-Host ""
