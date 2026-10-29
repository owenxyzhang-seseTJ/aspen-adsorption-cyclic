# Launch an ADSIM automation script in the interactive Windows session.
#
# Aspen automation started from a non-interactive SSH child fails on licensing
# even with correct paths. A task registered with -LogonType Interactive runs in
# the user's logged-on desktop session, which is what the automation server needs.
#
# Adjust the staging paths, then:
#   python3 win_ps.py adsim_launch.ps1 --end-time 6000
param(
  [double]$EndTime = 6000,
  [string]$Stage = 'C:\temp\adsim_stage',
  [string]$Model = 'case.ada',
  [string]$Runner = 'adsim_cycle_run.vbs',
  [string]$PropertyDll = 'gusersub.dll',
  [string]$TaskName = 'ADSIM_Run',
  [int]$TimeLimitMinutes = 120
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = 'C:\temp\adsim_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
New-Item -ItemType Directory -Path $root | Out-Null

# Every run gets its own directory so results are never mixed between attempts.
Copy-Item (Join-Path $Stage $Model) (Join-Path $root 'case.ada')
Copy-Item (Join-Path $Stage $Runner) $root
$dll = Join-Path $Stage $PropertyDll
if (Test-Path $dll) { Copy-Item $dll $root }

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing -and $existing.State -eq 'Running') {
  throw "$TaskName is already running; stop it before starting another run"
}

$action = New-ScheduledTaskAction -Execute "$env:WINDIR\System32\cscript.exe" `
  -Argument "//nologo $root\$Runner $root $EndTime" -WorkingDirectory $root
$principal = New-ScheduledTaskPrincipal `
  -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
  -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
  -ExecutionTimeLimit (New-TimeSpan -Minutes $TimeLimitMinutes) `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Principal $principal `
  -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Output "RUN_DIRECTORY=$root"
