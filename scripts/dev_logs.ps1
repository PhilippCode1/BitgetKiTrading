#Requires -Version 5.1
<#
.SYNOPSIS
  docker compose logs --tail (alle oder gewaehlte Dienste).

.DESCRIPTION
  Standard: gleiche Compose-Dateien wie dev_up.

.EXAMPLE
  pwsh scripts/dev_logs.ps1
  pwsh scripts/dev_logs.ps1 -Services api-gateway,dashboard -Tail 80 -Follow
  pwsh scripts/dev_logs.ps1 -NoLocalPublish
#>
param(
    [string] $EnvFile = ".env.local",
    [switch] $NoLocalPublish,
    [int] $Tail = 200,
    [string] $Services = "",
    [switch] $Follow
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_dev_compose.ps1")

$Root = Get-DevRepoRoot
Set-Location -LiteralPath $Root
Assert-DevEnvFile -RepoRoot $Root -EnvFile $EnvFile
Initialize-DevDockerCli

$composeFileArgs = Get-DevComposeFileArgs -NoLocalPublish:$NoLocalPublish
$logArgs = @("compose", "--env-file", $EnvFile) + $composeFileArgs + @("logs", "--tail", "$Tail")
if ($Follow) { $logArgs += "-f" }

if ($Services.Trim().Length -gt 0) {
    $names = $Services -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $logArgs += $names
    Write-Host "Logs (Tail=$Tail): $($names -join ', ')" -ForegroundColor Cyan
}
else {
    Write-Host "Logs aller Compose-Services (Tail=$Tail)" -ForegroundColor Cyan
}

& docker @logArgs
