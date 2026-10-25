# ==============================================================================
# Stream Cloner — Windows PowerShell Launcher
# Usage: .\scripts\launch\launch.ps1 [-Reinstall] [-Update]
# ==============================================================================
param(
    [switch]$Reinstall,
    [switch]$Update
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Resolve-Path "$ScriptDir\..\.."
Set-Location $ProjectRoot

$ArgsList = @()
if ($Reinstall) { $ArgsList += "--reinstall" }
if ($Update)    { $ArgsList += "--update" }

& "$ScriptDir\launch.bat" @ArgsList
