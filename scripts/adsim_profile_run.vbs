' Export one full cycle of axial bed profiles after an in-process warm-up.
'
' Use this instead of recording profiles for the whole run: 100+ variables over
' 30,000 cycles worth of 1 s samples is slow to export and mostly useless. Warm
' up first, then record only the cycle you will analyse.
'
' Arguments: <run directory> <warm-up cycles>
'
' ADAPT: bed names, node count, component, unit streams, CYCLE_PERIOD.
' Keep the file pure ASCII (cscript reads .vbs in the ANSI codepage).
Option Explicit
Dim root, a, app, sim, fs, logger, fso, logFile, paths, path, v, h, out
Dim i, j, k, n, warm, bed, u
Dim CYCLE_PERIOD, BEDS, NODES, COMP
CYCLE_PERIOD = 300
BEDS = Array("B1", "B2")
NODES = 20
COMP = "CO2"

root = WScript.Arguments(0)
warm = CInt(WScript.Arguments(1))
Set fso = CreateObject("Scripting.FileSystemObject")
Set logFile = fso.CreateTextFile(root & "\run_log.txt", True)
On Error Resume Next

Set a = CreateObject("ADS Application 4000")
Check "CreateObject", True
Set app = a.Application
Check "Application", True
app.OpenDocument root & "\case.ada"
Check "OpenDocument", True
Set sim = app.Simulation
Set fs = sim.Flowsheet
Set logger = sim.OutputLogger
logger.Path = root & "\aspen_output.txt"
logger.FileOutput = True
Check "OutputLogger", True
logFile.WriteLine "Caption=" & app.Caption

' Build the export list: per bed, pressure, velocity, gas fraction, loading.
ReDim paths(6 * NODES * UBound(BEDS) + 12)
n = 0
For Each bed In BEDS
  paths(n) = bed & ".Layer(1).P(0)" : n = n + 1
  paths(n) = bed & ".Layer(1).P(" & NODES & ")" : n = n + 1
  For i = 1 To NODES
    paths(n) = bed & ".Layer(1).Vg(" & i & ")" : n = n + 1
  Next
  For i = 1 To NODES
    paths(n) = bed & ".Layer(1).Y(" & i & ",""" & COMP & """)" : n = n + 1
  Next
  For i = 1 To NODES
    paths(n) = bed & ".Layer(1).W(" & i & ",""" & COMP & """)" : n = n + 1
  Next
  For i = 1 To NODES
    paths(n) = bed & ".Layer(1).P(" & i & ")" : n = n + 1
  Next
Next
For Each u In Array("F1", "P1", "W1")
  paths(n) = u & ".F" : n = n + 1
  paths(n) = u & ".Y_Fwd(""" & COMP & """)" : n = n + 1
Next
ReDim Preserve paths(n - 1)
logFile.WriteLine "PATH_COUNT=" & n

' Warm up without the profile variables recorded.
sim.EndTime = CYCLE_PERIOD - 0.0001
sim.Termination = "AtTime"
sim.RunMode = "Initialization"
sim.Run True
Check "Initialize", True
logFile.WriteLine "TimeAfterInit=" & sim.Time
For k = 1 To warm
  sim.EndTime = CYCLE_PERIOD * k - 0.0001
  sim.RunMode = "Dynamic"
  sim.Run True
  Check "Warmup " & k, True
  logFile.WriteLine "WARM " & k & " Time=" & sim.Time
  If Abs(sim.Time - (CYCLE_PERIOD * k - 0.0001)) > 0.001 Then
    logFile.WriteLine "FAILED warmup paused at " & sim.Time
    logFile.Close
    WScript.Quit 2
  End If
Next

' Record and run exactly one more cycle.
For i = 0 To UBound(paths)
  Set v = fs.Resolve(paths(i))
  Check "Resolve " & paths(i), True
  v.Record = True
  Check "Record " & paths(i), True
Next
sim.EndTime = CYCLE_PERIOD * warm + CYCLE_PERIOD - 0.0001
sim.RunMode = "Dynamic"
sim.Run True
Check "Profile cycle", True
logFile.WriteLine "PROFILE_START=" & (CYCLE_PERIOD * warm)
logFile.WriteLine "PROFILE_END=" & sim.Time

For i = 0 To UBound(paths)
  Set v = fs.Resolve(paths(i))
  Set h = v.History(CYCLE_PERIOD * warm, sim.Time, 1)
  Check "History " & paths(i), True
  Set out = fso.CreateTextFile(root & "\prof_" & i & ".tsv", True)
  out.WriteLine "Time (s)" & vbTab & paths(i)
  For j = 1 To h.Count
    out.WriteLine (h.StartTime + (j - 1) * h.Interval) & vbTab & h.Item(j)
  Next
  out.Close
  logFile.WriteLine "PROF " & i & "=" & paths(i) & " n=" & h.Count
Next

app.CloseDocument False
app.Quit
logFile.WriteLine "COMPLETED"
logFile.Close
WScript.Quit 0

Sub Check(label, fatal)
  If Err.Number <> 0 Then
    logFile.WriteLine "FAILED " & label & " " & CStr(Err.Number) & " " & Err.Description
    Err.Clear
    If fatal Then
      logFile.Close
      WScript.Quit 1
    End If
  End If
End Sub
