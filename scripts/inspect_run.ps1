# Report the state of an ADSIM automation run without disturbing it.
#   python3 win_ps.py inspect_run.ps1 --extra " -Root C:\temp\adsim_20260101_120000"
param([string]$Root = '', [string]$TaskName = 'ADSIM_Run')
$t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($t) {
  $i = Get-ScheduledTaskInfo -TaskName $TaskName
  Write-Output ("TASK_STATE=" + $t.State)
  Write-Output ("LAST_RUN=" + $i.LastRunTime)
  Write-Output ("LAST_RESULT=" + $i.LastTaskResult)
} else { Write-Output 'TASK=absent' }
Get-CimInstance Win32_Process -Filter "Name='AspenModeler.exe'" |
  ForEach-Object { Write-Output ("ASPEN_PID=" + $_.ProcessId + " " + $_.CommandLine) }
Get-CimInstance Win32_Process -Filter "Name='cscript.exe'" |
  ForEach-Object { Write-Output ("CSCRIPT_PID=" + $_.ProcessId + " " + $_.CommandLine) }
if ($Root -and (Test-Path $Root)) {
  Get-ChildItem $Root | ForEach-Object {
    if ($_.PSIsContainer) { Write-Output ("DIR=" + $_.Name) }
    else { Write-Output ("FILE=" + $_.Name + " " + $_.Length) }
  }
}
