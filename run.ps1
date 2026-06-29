# XMUOJ Auto Answer - PowerShell Launcher
# Usage: .\run.ps1 -Contest 361 -Problems "JD027,JD029"
#        .\run.ps1 -Contest 361 -Range "27-40"
#        .\run.ps1 -Setup
param(
    [int]$Contest = 0,
    [string]$Problems = "",
    [string]$Range = "",
    [int]$Limit = 0,
    [switch]$Setup,
    [switch]$DryRun,
    [int]$Retries = 0
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if ($Setup) {
    python start.py --setup
    return
}

$args = @("start.py")
if ($Contest) { $args += "-c", $Contest }
if ($Problems) { $args += "-p", $Problems }
if ($Range)    { $args += "-r", $Range }
if ($Limit)    { $args += "-n", $Limit }
if ($DryRun)   { $args += "--dry-run" }
if ($Retries)  { $args += "--retries", $Retries }

python -u $args
