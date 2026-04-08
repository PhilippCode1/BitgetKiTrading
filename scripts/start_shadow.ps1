#Requires -Version 5.1
param(
    [switch] $WithObservability,
    [switch] $NoBuild,
    [switch] $SkipMigrations,
    [int] $WaitTimeoutSec = 300
)
$here = $PSScriptRoot
$splat = @{
    Profile          = "shadow"
    WaitTimeoutSec   = $WaitTimeoutSec
}
if ($WithObservability) { $splat.WithObservability = $true }
if ($NoBuild) { $splat.NoBuild = $true }
if ($SkipMigrations) { $splat.SkipMigrations = $true }
& "$here/bootstrap_stack.ps1" @splat
