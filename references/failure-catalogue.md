# Failure catalogue

Each entry: what you see, what you would wrongly conclude, what is actually
happening, and the fix. All of these were hit on the same two-bed VSA model.

## Contents

1. Silent success from the batch interface
2. `sim.Run` returns 245 "problem is not complete"
3. Model looks empty after loading
4. Whole cycles missing from history
5. Sentinel values `1.99999988842394e+28`
6. Per-step `Manipulated(k)` indices are not stable
7. Zero-length steps
8. CRLF lost when generating `.ada`
9. Property library silently mis-mapped
10. `Cycle_Total_*` phase is undocumented
11. History time labels do not match values
12. Non-existent property names raise 438, not a clear error
13. Aspen automation outside the interactive session
14. Stale Aspen processes

---

## 1. Silent success from the batch interface

**See:** `ADSIMTools400.Batch.StartUp/Run/History/WriteHistory` all return `True`
or `"OK"`, and the history files exist but are 0 bytes. `aspen_output.txt` is empty.

**Wrong conclusion:** the run worked.

**Cause:** the wrapper's return value reflects only that the call was marshalled.

**Fix:** use the direct interface instead —
`CreateObject("ADS Application 4000")` → `a.Application` → `app.OpenDocument` →
`app.Simulation` → `sim.Flowsheet`. Then verify with `sim.Time` after the run and
with non-empty exported files. Treat file size and row count as the evidence.

## 2. `sim.Run` returns 245 "problem is not complete"

**See:** `FAILED Initialize 245 A simulation run could not be started, check
problem is complete and not already running`.

**Wrong conclusion:** a stale process holds a lock.

**Cause:** the model is over-specified. Two confirmed triggers on this model:

- adding `F1.F.spec : Fixed` to a feed unit that already specifies pressure;
- writing **both** `Y(i,"CO2")` (whose `spec` is `Initial`) and
  `Y(i,"Nitrogen")` (whose `spec` is `Free`) as initial guesses for all 20 nodes.

**Fix:** bisect one change at a time. Keep a probe script that writes a single
variant `.ada`, launches it with a near-zero end time, and prints
`TimeAfterInit`. Do not guess; the search space is small.

Confirmed working: set only the `spec : Initial` component and let the solver
normalise the free one.

## 3. Model looks empty after loading

**See:** `fs.FindMatchingVariables("*")` returns 3 variables
(`ActiveTasks`, `ComponentList`, `UserNotes`).

**Wrong conclusion:** the document failed to load, or the flowsheet is empty.

**Cause:** `*` does not cross hierarchy levels.

**Fix:** `fs.FindMatchingVariables("~")` recurses (thousands of variables on a two-bed
model); `fs.FindMatchingVariables("F1.~")` lists a subtree (dozens on a feed unit). This is
also how you discover the real variable name instead of guessing one.

## 4. Whole cycles missing from history

**See:** history has a valid block, then a block of sentinels, then resumes.

**Cause:** `Cycle_Organizer.Cycle_Data(1).RecordFrequency` is 2 in the template,
so only every second cycle is recorded.

**Fix:** set `RecordFrequency : 1`. Note `TimeSettings.RecordHistory : True`
records all variables but does not override `RecordFrequency`.

## 5. Sentinel values `1.99999988842394e+28`

**See:** impossible values in an exported column.

**Cause:** ADSIM writes a sentinel for a point that was never recorded
(see item 4) or for a variable that has no history (`Count = 0`, `StartTime = -1`).

**Fix:** filter `abs(v) >= 1e20` before any arithmetic, and check
`h.Count` — a zero count on `Total_Component` (no `_Fwd`/`_Rev` suffix) on a
reversible model is expected, not a bug.

## 6. Per-step `Manipulated(k)` indices are not stable

**See:** a valve ends up with `Active_Specification : 5e-05` (not a legal
enumeration) after you set index 10 in every step.

**Cause:** `Step_Data(n).Manipulated(k)` is a sparse list whose contents and
ordering differ between steps. Index 10 is `VW1.Active_Specification` in one step
and `VW1.Cv` in another.

**Fix:** parse each step's `.VarPath` lines and address by path:

```
Cycle_Organizer.Cycle_Data(1).Step_Data(2).Manipulated(4).VarPath : "VF2_1.Cv";
```

Build `{path: index}` per step, then write the index that matches the path.

## 7. Zero-length steps

**See:** a repressurisation step that never happens; bed pressure jumps
immediately.

**Cause:** the task script has its own copies of the step times, e.g.
`Cycle_Organizer.Cycle_Data(1).Step_Time(2) : 0;`. Editing
`Step_Data(2).StepTime` alone leaves the actual controller time at zero.

**Fix:** replace the `: 0;` assignments with references to
`Step_Data(n).StepTime`, or write the value in both places.

## 8. CRLF lost when generating `.ada`

**See:** the generated file is smaller than the template by roughly one byte per
line, and any `(?m)$`-anchored substitution behaves differently.

**Cause:** `Path.read_text()` performs universal-newline translation.

**Fix:** `text = SRC.read_bytes().decode('utf-8')`, then write back with
`newline=''` and restore `\r\n` if the source had it.

## 9. Property library silently mis-mapped

**See:** nothing. The model runs, mass balance closes, only the numbers are wrong.

**Cause:** `Physical_Properties = "User Procedures"` calls a DLL whose arrays are
ordered by the component names' ASCII order. An air-separation `gusersub.dll`
holds `[N2, O2]`; with components `CO2` and `Nitrogen`, CO₂ receives the N₂
constants and N₂ receives the O₂ constants.

**Fix:** see [property-library.md](property-library.md). Verify by reading back a
computed mixture property and comparing with a hand calculation.

## 10. `Cycle_Total_*` phase is undocumented

**See:** at the end of cycle 1, `Cycle_Total_Component_Fwd` is either 0 or the
full cycle value depending on where the sample lands; the official text only
says "for last cycle".

**Fix:** do not build the balance on `Cycle_Total_*`. Read the cumulative
`Total_Component_Fwd` / `_Rev` at a fixed phase and difference consecutive
cycles. Keep `Cycle_Total_*` as a secondary cross-check only.

## 11. History time labels do not match values

**See:** `h.Count = 901`, `h.StartTime = 0`, `h.Interval = 1`, but `h.Item(1)`
is not the value at t=0 and a 300 s block is displaced.

**Cause:** not documented. The official contract is 1-based `Item` with
`t = StartTime + (i-1)*Interval`, and there is no alternate signature.

**Fix:** do not trust the label for phase alignment. Derive phase from an
independent physical signal (e.g. the sharp pressure transition between
adsorption and evacuation) and verify the window by integrating a unit flow and
comparing with the independently measured per-cycle total. On this model that
cross-check agreed to about 1e-11 relative.

## 12. Non-existent property names raise 438

**See:** `438 对象不支持此属性或方法` for `fs.Ready`, `sim.Status`,
`fs.Complete`.

**Cause:** these properties do not exist on the ADSIM automation objects.

**Fix:** probe state with `sim.Time` and the last `Err.Number` instead. Do not
invent status properties; enumerate with `FindMatchingVariables("~")` when unsure
of a variable name.

## 13. Aspen automation outside the interactive session

**See:** `OpenDocument` fails with 263 ("A new document could not be created") or
the licence broker errors, even though the path exists and the file is readable.

**Cause:** the automation server needs the logged-on interactive desktop session.

**Fix:** register a scheduled task with
`New-ScheduledTaskPrincipal -LogonType Interactive` running `cscript.exe`, and
start it. Do not launch Aspen from a non-interactive SSH child.

## 14. Stale Aspen processes

**See:** repeated 245s that persist after killing `AspenModeler.exe -Embedding`.

**Cause:** often *not* the process — see item 2. Killing them is a legitimate
first step only if you then re-test with a known-good `.ada`; otherwise you will
misattribute an over-specification bug to a lock.

**Fix:** kill only the automation instances (`-Embedding`), never a user's GUI
session, then re-run the known-good model to establish a baseline.
