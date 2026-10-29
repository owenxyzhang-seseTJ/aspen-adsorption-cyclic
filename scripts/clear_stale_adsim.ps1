# Kill only Aspen automation instances, never a user's interactive GUI session.
# Re-test with a known-good model afterwards: a persisting failure is usually an
# over-specified model (error 245), not a stale lock.
Get-CimInstance Win32_Process -Filter "Name='AspenModeler.exe'" | ForEach-Object {
  if ($_.CommandLine -match '-Embedding') {
    try { Stop-Process -Id $_.ProcessId -Force; Write-Output ("KILLED=" + $_.ProcessId) } catch {}
  }
}
Get-CimInstance Win32_Process -Filter "Name='cscript.exe'" | ForEach-Object {
  if ($_.CommandLine -match 'adsim_') {
    try { Stop-Process -Id $_.ProcessId -Force; Write-Output ("KILLED=" + $_.ProcessId) } catch {}
  }
}
Write-Output ("REMAINING=" + ((Get-Process AspenModeler -ErrorAction SilentlyContinue | Measure-Object).Count))
