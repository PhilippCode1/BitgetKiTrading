#Requires -Version 5.1
<#
  Gemeinsame Hilfen fuer dev_*.ps1 (Windows).
  Wird per Dot-Source eingebunden: . (Join-Path $PSScriptRoot '_dev_compose.ps1')

  Windows PowerShell 5.1: In doppelten Anfuehrungszeichen keine Em-Dash-Zeichen (U+2014)
  und keine anderen mehrbyte-UTF-8-Zeichen ohne UTF-8-BOM - sonst ParserError.
  Siehe docs/cursor_execution/02_windows_smoke_and_powershell_fix.md
#>

$script:DevDefaultEnvFile = ".env.local"
$script:DevDefaultComposeFile = "docker-compose.yml"

function Get-DevComposeFileArgs {
    param([switch] $NoLocalPublish)
    if ($NoLocalPublish) {
        return @("-f", "docker-compose.yml")
    }
    return @("-f", "docker-compose.yml", "-f", "docker-compose.local-publish.yml")
}

$script:DevHealthCheckServices = @(
    "postgres", "redis", "migrate", "market-stream", "llm-orchestrator",
    "feature-engine", "structure-engine", "news-engine", "drawing-engine", "signal-engine",
    "paper-broker", "live-broker", "learning-engine", "alert-engine", "api-gateway",
    "monitor-engine", "dashboard"
)

function Initialize-DevDockerCli {
    $dockerPathScript = Join-Path $PSScriptRoot "docker-path.ps1"
    if (Test-Path -LiteralPath $dockerPathScript) {
        . $dockerPathScript
        Initialize-DockerDesktopPath
    }
    $null = Get-Command docker -ErrorAction Stop
}

function Get-DevRepoRoot {
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

function Assert-DevEnvFile {
    param(
        [string] $RepoRoot,
        [string] $EnvFile
    )
    $full = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $RepoRoot $EnvFile }
    if (-not (Test-Path -LiteralPath $full)) {
        throw "Env-Datei fehlt: $full - bitte .env.local.example nach .env.local kopieren (siehe docs/LOCAL_START_MINIMUM.md)."
    }
}

function Assert-DevEnvCriticalForCompose {
    param(
        [string] $RepoRoot,
        [string] $EnvFile,
        [switch] $WithDashboardOperator
    )
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Warning "python nicht im PATH - ueberspringe tools/validate_env_profile.py (siehe docs/LOCAL_START_MINIMUM.md)."
        return
    }
    $validator = Join-Path $RepoRoot "tools\validate_env_profile.py"
    if (-not (Test-Path -LiteralPath $validator)) { return }
    $full = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $RepoRoot $EnvFile }
    $extra = @()
    if ($WithDashboardOperator) { $extra += "--with-dashboard-operator" }
    & $py.Source $validator --env-file $full --profile local @extra
    if ($LASTEXITCODE -ne 0) {
        throw "ENV-Validierung fehlgeschlagen ($validator). Siehe docs/CONFIGURATION.md und docs/LOCAL_START_MINIMUM.md"
    }
}

function Invoke-DevMintDashboardGatewayJwt {
    param(
        [string] $RepoRoot,
        [string] $EnvFile,
        [switch] $Skip
    )
    if ($Skip) { return }
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Warning (
            "python nicht im PATH - JWT-Mint uebersprungen. Bei 503 auf Health: " +
            "python scripts/mint_dashboard_gateway_jwt.py --env-file $EnvFile --update-env-file"
        )
        return
    }
    $mint = Join-Path $RepoRoot "scripts\mint_dashboard_gateway_jwt.py"
    if (-not (Test-Path -LiteralPath $mint)) { return }
    $full = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $RepoRoot $EnvFile }
    Write-Host ""
    Write-Host "Schreibe DASHBOARD_GATEWAY_AUTHORIZATION in $EnvFile (serverseitiger Aufruf ans API-Gateway) ..." -ForegroundColor Cyan
    & $py.Source $mint --env-file $full --update-env-file
    if ($LASTEXITCODE -ne 0) {
        throw (
            "mint_dashboard_gateway_jwt fehlgeschlagen (Exit $LASTEXITCODE). " +
            "PyJWT: pip install -r requirements-dev.txt"
        )
    }
    Write-Host "Hinweis: Nach Mint Next auf dem Host neu starten (pnpm dev) oder Dashboard-Container neu erstellen (docker compose up -d --force-recreate dashboard). Diagnose: pnpm local:doctor" -ForegroundColor DarkGray
}

function Warn-DevDashboardGatewayAuth {
    param(
        [string] $RepoRoot,
        [string] $EnvFile
    )
    $path = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $RepoRoot $EnvFile }
    if (-not (Test-Path -LiteralPath $path)) { return }
    $ok = $false
    Get-Content -LiteralPath $path -ErrorAction SilentlyContinue | ForEach-Object {
        $line = $_
        if ($line -match '^\s*DASHBOARD_GATEWAY_AUTHORIZATION\s*=\s*(.+)$') {
            $v = $Matches[1].Trim().Trim('"').Trim("'")
            if ($v -and $v -notmatch 'SET_ME') { $ok = $true }
        }
    }
    if (-not $ok) {
        Write-Warning (
            "DASHBOARD_GATEWAY_AUTHORIZATION fehlt oder Platzhalter - Operator-Console kann 503 liefern. " +
            "Mint: python scripts/mint_dashboard_gateway_jwt.py --env-file $EnvFile --update-env-file"
        )
    }
}

function Get-DevEdgeHost {
    param([string] $RepoRoot, [string] $EnvFile)
    $bind = "127.0.0.1"
    $path = Join-Path $RepoRoot $EnvFile
    if (-not (Test-Path -LiteralPath $path)) { return $bind }
    foreach ($line in Get-Content -LiteralPath $path -ErrorAction SilentlyContinue) {
        if ($line -match '^\s*COMPOSE_EDGE_BIND\s*=\s*(\S+)') {
            $v = $Matches[1].Trim().Trim('"').Trim("'")
            if ($v) { return $v }
        }
    }
    return $bind
}

function Wait-DevStackHealthy {
    param(
        [string] $RepoRoot,
        [string] $EnvFile,
        [string[]] $ComposeFileArgs,
        [int] $WaitTimeoutSec = 900,
        [int] $PollSec = 5
    )
    $deadline = [DateTime]::UtcNow.AddSeconds($WaitTimeoutSec)
    $round = 0
    Write-Host ""
    Write-Host "Wir warten, bis Docker die Dienste als gesund meldet (das kann beim ersten Mal einige Minuten dauern)." -ForegroundColor Cyan
    Write-Host ""

    while ([DateTime]::UtcNow -lt $deadline) {
        $round++
        $bad = @()
        $starting = @()
        Push-Location -LiteralPath $RepoRoot
        try {
        foreach ($s in $script:DevHealthCheckServices) {
            $psArgs = if ($s -eq "migrate") { @("ps", "-a", "-q", $s) } else { @("ps", "-q", $s) }
            $cid = (& docker compose --env-file $EnvFile @ComposeFileArgs @psArgs 2>$null | Select-Object -First 1).Trim()
            if (-not $cid) {
                $bad += "${s}:kein-container"
                continue
            }
            if ($s -eq "migrate") {
                $exit = (& docker inspect --format '{{.State.Status}}|{{.State.ExitCode}}' $cid 2>$null).Trim()
                $parts = $exit -split '\|'
                if ($parts[0] -eq "exited" -and $parts[1] -eq "0") { continue }
                if ($parts[0] -eq "created" -or $parts[0] -eq "running") {
                    $starting += "${s}:Migration laeuft noch"
                    continue
                }
                if ($parts[0] -eq "exited" -and $parts[1] -ne "0") { $bad += "${s}:fehler-exit-$($parts[1])"; continue }
                $bad += "${s}:$exit"
                continue
            }
            $healthFmt = '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}'
            $healthSt = (& docker inspect --format $healthFmt $cid 2>$null).Trim()
            $runSt = (& docker inspect --format '{{.State.Status}}' $cid 2>$null).Trim()
            if ($healthSt -eq "none") {
                if ($runSt -eq "running") { continue }
                $bad += "${s}:$runSt"
                continue
            }
            if ($healthSt -eq "healthy") { continue }
            if ($healthSt -eq "starting") {
                $starting += "${s}:Healthcheck startet"
                continue
            }
            $bad += "${s}:$healthSt"
        }
        }
        finally {
            Pop-Location
        }
        if ($bad.Count -eq 0 -and $starting.Count -eq 0) {
            Write-Host ""
            Write-Host "Fertig: Alle geprueften Dienste sind bereit." -ForegroundColor Green
            return
        }
        if ($starting.Count -gt 0) {
            Write-Host ("[$round] Noch am Hochfahren: " + ($starting -join "; ")) -ForegroundColor Yellow
        }
        if ($bad.Count -gt 0) {
            Write-Host ("[$round] Offen / Problem: " + ($bad -join "; ")) -ForegroundColor DarkYellow
        }
        Start-Sleep -Seconds $PollSec
    }

    Write-Host ""
    Write-Host "Zeit abgelaufen - hier der aktuelle Stand:" -ForegroundColor Red
    Push-Location -LiteralPath $RepoRoot
    try { & docker compose --env-file $EnvFile @ComposeFileArgs ps }
    finally { Pop-Location }
    throw "Timeout nach ${WaitTimeoutSec}s: Nicht alle Container waren rechtzeitig healthy. Siehe Meldungen oben und `docker compose logs`."
}

function Show-DevPortSummary {
    param(
        [string] $EdgeHost,
        [switch] $WithLocalPublish
    )
    Write-Host ""
    Write-Host "=== Deine lokalen Adressen ===" -ForegroundColor Green
    Write-Host "  Dashboard:     http://${EdgeHost}:3000"
    Write-Host "  API-Gateway:   http://${EdgeHost}:8000  (Swagger oft unter /docs)"
    Write-Host "  Gateway-Ready: http://${EdgeHost}:8000/ready"
    if ($WithLocalPublish) {
        Write-Host "  Worker-Ports:  docker-compose.local-publish.yml mappt 8010-8120 u. a. auf ${EdgeHost} (Debugging)."
    }
    Write-Host ""
}

function Open-DevBrowserTabs {
    param(
        [string] $EdgeHost,
        [switch] $NoOpen
    )
    if ($NoOpen) { return }
    $dash = "http://${EdgeHost}:3000"
    $gw = "http://${EdgeHost}:8000/health"
    Write-Host "Browser: Dashboard und API-Gateway oeffnen ..." -ForegroundColor Cyan
    Start-Process $dash
    Start-Sleep -Milliseconds 400
    Start-Process $gw
}
