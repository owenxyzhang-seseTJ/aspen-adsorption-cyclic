' Cycle-by-cycle driver for Aspen Adsorption dynamic runs.
'
' Steps the simulation one controller cycle at a time and writes cumulative
' totals plus inventories at every cycle boundary, then exports a bounded
' history window. Per-cycle stepping gives an exactly phase-aligned sample for
' the material balance and detects a solver pause immediately.
'
' Arguments: <run directory> <final time, s>
'
' ADAPT THE TWO ARRAYS BELOW to your model. Variable names differ between
' flowsheets; enumerate them once with fs.FindMatchingVariables("~") instead of
' guessing. In VBScript a double quote inside a string is written "".
'
' This file must stay pure ASCII: cscript reads .vbs in the ANSI codepage, and
' UTF-8 bytes in comments can corrupt the parse.
Option Explicit
Dim root, a, app, sim, fs, logger, fso, logFile, paths, path, v, h, out
Dim cycleOut, cyclePaths, k, stopTime, row, j, historyStart, finalTime
Dim CYCLE_PERIOD, HISTORY_WINDOW
CYCLE_PERIOD = 300          ' s per controller cycle; must match the model
HISTORY_WINDOW = 600        ' s of history to export at the end

root = WScript.Arguments(0)
finalTime = CDbl(WScript.Arguments(1))
Set fso = CreateObject("Scripting.FileSystemObject")
Set logFile = fso.CreateTextFile(root & "\run_log.txt", True)
On Error Resume Next

Set a = CreateObject("ADS Application 4000")
Check "CreateObject", True
Set app = a.Application
app.Visible = True
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
logFile.WriteLine "TimeStart=" & sim.Time

' Time series exported at the end, 1 s resolution.
paths = Array( _
  "F1.F", _
  "P1.F", "P1.Y_Fwd(""CO2"")", _
  "W1.F", "W1.Y_Fwd(""CO2"")", _
  "B1.Layer(1).P(0)", "B1.Layer(1).P(20)", _
  "B2.Layer(1).P(0)", "B2.Layer(1).P(20)")
For Each path In paths
  Set v = fs.Resolve(path)
  Check "Resolve " & path, True
  v.Record = True
  Check "Record " & path, True
Next

' Cumulative totals and holdups read at every cycle boundary.
' Use *_Fwd / *_Rev on reversible units; the unsuffixed Total_Component has no
' history there and reads as Count=0.
cyclePaths = Array( _
  "F1.Total_Component_Fwd(""CO2"")", "P1.Total_Component_Fwd(""CO2"")", _
  "W1.Total_Component_Fwd(""CO2"")", _
  "F1.Total_Material_Fwd", "P1.Total_Material_Fwd", "W1.Total_Material_Fwd", _
  "F1.Total_Component_Rev(""CO2"")", "P1.Total_Component_Rev(""CO2"")", _
  "W1.Total_Component_Rev(""CO2"")", _
  "F1.Total_Material_Rev", "P1.Total_Material_Rev", "W1.Total_Material_Rev", _
  "B1.BedAdsorbedInventory(""CO2"")", "B2.BedAdsorbedInventory(""CO2"")", _
  "B1.BedGasInventory(""CO2"")", "B2.BedGasInventory(""CO2"")", _
  "T1.Mc(""CO2"")", "T2.Mc(""CO2"")", "T3.Mc(""CO2"")", _
  "B1.Layer(1).P(0)", "B2.Layer(1).P(0)")

sim.EndTime = finalTime
sim.Termination = "AtTime"
sim.RunMode = "Initialization"
sim.Run True
Check "Initialize", True
logFile.WriteLine "TimeAfterInit=" & sim.Time
If Abs(sim.Time) > 0.001 Then
  logFile.WriteLine "FAILED initialization did not settle at t=0"
  logFile.Close
  WScript.Quit 1
End If

Set cycleOut = fso.CreateTextFile(root & "\cycles.tsv", True)
row = "Time (s)"
For Each path In cyclePaths
  row = row & vbTab & path
Next
cycleOut.WriteLine row
WriteCycle

sim.RunMode = "Dynamic"
k = 1
Do
  stopTime = CYCLE_PERIOD * k - 0.0001
  If stopTime > finalTime Then stopTime = finalTime
  sim.EndTime = stopTime
  sim.Run True
  Check "Dynamic cycle " & k, True
  logFile.WriteLine "TimeEnd=" & sim.Time
  WriteCycle
  ' A shortfall means the solver paused (cycle limit, convergence, or a
  ' numerical failure) rather than reaching the requested time.
  If Abs(sim.Time - stopTime) > 0.001 Then
    logFile.WriteLine "FAILED simulation paused at " & sim.Time & _
                      " before requested " & stopTime
    cycleOut.Close
    logFile.Close
    WScript.Quit 2
  End If
  If stopTime >= finalTime - 0.001 Then Exit Do
  k = k + 1
Loop
cycleOut.Close

historyStart = sim.Time - HISTORY_WINDOW
If historyStart < 0 Then historyStart = 0
For i = 0 To UBound(paths)
  Set v = fs.Resolve(paths(i))
  Set h = v.History(historyStart, sim.Time, 1)
  Check "History " & paths(i), True
  ' Cache h and only touch h.Item; re-reading v.History resets the range.
  logFile.WriteLine "HISTORY " & paths(i) & " Count=" & h.Count & _
                    " Start=" & h.StartTime & " Interval=" & h.Interval
  Set out = fso.CreateTextFile(root & "\history_" & i & ".tsv", True)
  out.WriteLine "Time (s)" & vbTab & paths(i)
  For j = 1 To h.Count
    row = CStr(h.StartTime + (j - 1) * h.Interval) & vbTab & CStr(h.Item(j))
    Check "History item " & paths(i), True
    out.WriteLine row
  Next
  out.Close
Next

app.CloseDocument False
app.Quit
logFile.WriteLine "COMPLETED"
logFile.Close
WScript.Quit 0

Sub WriteCycle
  row = CStr(sim.Time)
  For Each path In cyclePaths
    Set v = fs.Resolve(path)
    row = row & vbTab & CStr(v.Value)
    Check "Read " & path, True
  Next
  cycleOut.WriteLine row
End Sub

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
