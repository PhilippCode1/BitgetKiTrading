# Lokaler Testlauf (Windows, Prompt 29)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:PYTHONPATH = "$(Join-Path $Root 'shared/python/src');$env:PYTHONPATH"
$env:CI = if ($env:CI) { $env:CI } else { "false" }

Write-Host "[run_tests] pytest (ohne integration)"
python -m pytest -q tests shared/python/tests -m "not integration"

Write-Host "[run_tests] coverage"
python -m coverage erase
python -m coverage run -m pytest tests shared/python/tests -m "not integration"
python -m coverage report

if ($env:RUN_INTEGRATION -eq "1") {
    Write-Host "[run_tests] integration"
    python -m pytest -q tests/integration -m integration
}

if (Test-Path (Join-Path $Root "apps/dashboard/package.json")) {
    Write-Host "[run_tests] dashboard"
    Set-Location (Join-Path $Root "apps/dashboard")
    npm test
    Set-Location $Root
}

Write-Host "[run_tests] fertig"
