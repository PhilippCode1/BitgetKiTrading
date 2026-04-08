#Requires -Version 5.1
<#
.SYNOPSIS
  Parse alle scripts/*.ps1 mit dem AST-Parser - faellt bei ParserError sofort auf.

.DESCRIPTION
  Regression gegen kaputte UTF-8-Zeichen in Strings (z. B. Em-Dash U+2014), die unter
  Windows PowerShell 5.1 ohne BOM als mehrere Bytes gelesen werden und den Parser zerlegen.

.EXAMPLE
  pwsh scripts/verify_powershell_syntax.ps1
  pnpm ps:verify-syntax
#>
$ErrorActionPreference = "Stop"
$scriptsDir = $PSScriptRoot
$fail = $false
$files = Get-ChildItem -LiteralPath $scriptsDir -Filter "*.ps1" | Sort-Object Name
foreach ($f in $files) {
    $path = $f.FullName
    $tokens = $null
    $errs = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$errs)
    if ($errs -and $errs.Count -gt 0) {
        Write-Host "PARSE FAIL: $path" -ForegroundColor Red
        foreach ($e in $errs) {
            Write-Host ("  {0}" -f $e.ToString()) -ForegroundColor Red
        }
        $fail = $true
    }
    else {
        Write-Host ("OK: {0}" -f $f.Name) -ForegroundColor Green
    }
}
if ($fail) {
    Write-Host ""
    Write-Host "Hinweis: Em-Dash (U+2014) und andere Nicht-ASCII-Zeichen in doppelten Strings" -ForegroundColor Yellow
    Write-Host "  vermeiden oder Datei als UTF-8 mit BOM speichern (Windows PowerShell 5.1)." -ForegroundColor Yellow
    exit 1
}
Write-Host ""
Write-Host "Alle $($files.Count) PowerShell-Dateien in scripts/ sind syntaktisch gueltig." -ForegroundColor Green
exit 0
