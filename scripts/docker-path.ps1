<#
.SYNOPSIS
  Docker Desktop legt docker.exe oft ausserhalb des PATH ab - vor Get-Command docker aufrufen.
#>
function Initialize-DockerDesktopPath {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        return
    }
    $dirs = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin")
    )
    $pf86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    if ($pf86) {
        $dirs += (Join-Path $pf86 "Docker\Docker\resources\bin")
    }
    foreach ($d in $dirs) {
        if (-not $d) { continue }
        $exe = Join-Path $d "docker.exe"
        if (Test-Path -LiteralPath $exe) {
            $env:Path = "$d;$env:Path"
            return
        }
    }
}
