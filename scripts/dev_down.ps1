#Requires -Version 5.1
<#
.SYNOPSIS
  Docker-Stack sauber stoppen (docker compose down).

.DESCRIPTION
  Standard: dieselben Compose-Dateien wie dev_up (Basis + local-publish). Mit -NoLocalPublish nur Basis-Compose.

.EXAMPLE
  pwsh scripts/dev_down.ps1
  pwsh scripts/dev_down.ps1 -RemoveVolumes
  pwsh scripts/dev_down.ps1 -NoLocalPublish
#>
param(
    [string] $EnvFile = ".env.local",
    [switch] $NoLocalPublish,
    [switch] $RemoveVolumes
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_dev_compose.ps1")

$Root = Get-DevRepoRoot
Set-Location -LiteralPath $Root
Assert-DevEnvFile -RepoRoot $Root -EnvFile $EnvFile
Initialize-DevDockerCli

$composeFileArgs = Get-DevComposeFileArgs -NoLocalPublish:$NoLocalPublish
$dcArgs = @("compose", "--env-file", $EnvFile) + $composeFileArgs + @("down")
if ($RemoveVolumes) {
    $dcArgs += "-v"
    Write-Host "Achtung: -RemoveVolumes loescht benannte Volumes (frische DB beim naechsten Start)." -ForegroundColor Yellow
}

Write-Host "Fuehre aus: docker $($dcArgs -join ' ')" -ForegroundColor Cyan
& docker @dcArgs
if ($LASTEXITCODE -ne 0) { throw "docker compose down fehlgeschlagen (Exit $LASTEXITCODE)." }

Write-Host ""
Write-Host "Stack ist gestoppt." -ForegroundColor Green
if (-not $RemoveVolumes) {
    Write-Host "Daten in Postgres/Redis bleiben erhalten. Komplett leeren: dev_down.ps1 -RemoveVolumes oder dev_reset_db.ps1" -ForegroundColor DarkGray
}
Write-Host ""
