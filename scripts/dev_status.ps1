#Requires -Version 5.1
<#
.SYNOPSIS
  Kurzer Status: docker compose ps plus erreichbare Edge-URLs.

.DESCRIPTION
  Standard: gleiche Compose-Dateien wie dev_up (mit local-publish).

.EXAMPLE
  pwsh scripts/dev_status.ps1
  pwsh scripts/dev_status.ps1 -SkipHttp
  pwsh scripts/dev_status.ps1 -NoLocalPublish
#>
param(
    [string] $EnvFile = ".env.local",
    [switch] $NoLocalPublish,
    [switch] $SkipHttp
)

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "_dev_compose.ps1")

$Root = Get-DevRepoRoot
Set-Location -LiteralPath $Root

$composeFileArgs = Get-DevComposeFileArgs -NoLocalPublish:$NoLocalPublish

if (-not (Test-Path -LiteralPath (Join-Path $Root $EnvFile))) {
    Write-Host "Hinweis: $EnvFile fehlt - nur Docker-PS moeglich." -ForegroundColor Yellow
}
else {
    Initialize-DevDockerCli
    Write-Host "=== docker compose ps ===" -ForegroundColor Cyan
    & docker compose --env-file $EnvFile @composeFileArgs ps
    Write-Host ""
}

if ($SkipHttp) { exit 0 }

$edgeHost = "127.0.0.1"
if (Test-Path -LiteralPath (Join-Path $Root $EnvFile)) {
    $edgeHost = Get-DevEdgeHost -RepoRoot $Root -EnvFile $EnvFile
}

Write-Host "=== Schnelltest HTTP (Edge: $edgeHost) ===" -ForegroundColor Cyan
$urls = @(
    @{ Name = "Gateway /health"; Url = "http://${edgeHost}:8000/health" },
    @{ Name = "Gateway /ready"; Url = "http://${edgeHost}:8000/ready" },
    @{ Name = "Dashboard"; Url = "http://${edgeHost}:3000/api/health" }
)
foreach ($u in $urls) {
    Write-Host "  $($u.Name): $($u.Url)"
    try {
        $r = Invoke-WebRequest -Uri $u.Url -UseBasicParsing -TimeoutSec 6
        Write-Host "    -> HTTP $($r.StatusCode) OK" -ForegroundColor Green
    }
    catch {
        $msg = $_.Exception.Message
        Write-Host "    -> nicht erreichbar: $msg" -ForegroundColor DarkYellow
    }
}
Write-Host ""
