---
name: aspen-adsorption-cyclic
description: "Run and audit Aspen Adsorption (ADSIM) dynamic cyclic simulations — PSA/VSA/TSA — through Windows COM automation: generate .ada models by script, drive them from a scheduled task in the interactive session, export per-cycle balances and axial profiles, and prove cyclic steady state before reporting numbers. Use for Aspen Adsorption, ADSIM, PSA, VSA, TSA, breakthrough cycles, gusersub.dll user property library, ADS Application 4000."
---

# Aspen Adsorption: dynamic cyclic runs that survive audit

This skill carries the failure modes that cost real time on a two-bed VSA model.
Read it before writing any ADSIM automation: almost every item in
[references/failure-catalogue.md](references/failure-catalogue.md) produces a
*plausible wrong answer* rather than an error, which is the expensive kind.

Companion skill: `aspen-athena-chem-sim` covers Aspen Plus, the Windows/SSH
routing contract, and screening-model discipline. Use that one for the licensing
and host questions, this one for cyclic ADSIM work.

## The five rules that decide whether the result is real

1. **A return code is not evidence.** `ADSIMTools400.Batch` and the direct COM
   `sim.Run` both return success while writing empty files. Only file size,
   row count, and a value that could only come from a solve count as evidence.
2. **Prove mass balance per cycle, including inventory.** Feed − light − heavy −
   Δ(inventory) must close to ~1e-5 of feed. Without Δ(inventory) the residual is
   meaningless during any transient.
3. **Never call it cyclic steady state from a plateau.** Two independent
   quantities must be flat: the per-cycle flows *and* the system inventory.
   Bed inventory can drift by percent-level per cycle while removal looks
   constant — see the worked case in [references/steady-state.md](references/steady-state.md).
4. **Bed profiles are the cheapest sanity check.** If measured loading is far
   below the equilibrium loading at the operating partial pressure, the run is
   not limited by the material — the bed is oversized or under-fed, and the
   headline removal number is an artefact of excess capacity.
5. **Report removal, recovery, and purity as separate numbers with their
   definitions.** They are different integrals and they disagree during
   transients. A recovery above 100% means inventory is being drained, not that
   the process works.

## Workflow

### 0. Decide the evidence layer

Aspen output is Aspen evidence. A Python compartment model is screening. Never
let a screening number appear in an Aspen row of a table. If the licensed run
fails, report it verbatim and keep the screening result labelled as screening.

### 1. Generate the model by script, not by hand

Hand-editing `.ada` does not survive a parameter sweep, and the file has
traps (`CRLF`, per-step `Manipulated(k)` indices that differ between steps,
duplicated step times in the task script). Copy
[scripts/build_adsim_model.py](scripts/build_adsim_model.py) and change the
`PATHS`/`SETTINGS` tables at the top. Rules it encodes:

- read with `read_bytes().decode('utf-8')` — `read_text()` silently converts
  CRLF to LF and every `(?m)$` pattern then behaves differently;
- locate valve actions by `.VarPath`, never by `Manipulated(k)` index;
- set step durations in **both** `Step_Data(n).StepTime` and the task script's
  `Step_Time(n)` — the latter may still be `0`;
- never set a specification on a variable the unit already specifies
  (adding `F1.F.spec : Fixed` to a pressure-driven feed makes the problem
  incomplete and `sim.Run` fails with 245);
- do not overwrite both components' `Y(i,...)` initial guesses when one of them
  carries `spec : Initial` — write only the specified one and let the solver
  normalise the other.

### 2. Fix the user property library before believing any number

ADSIM passes component arrays in **ASCII order of component name**, so renaming
`Oxygen` to `CO2` silently maps CO₂ onto the N₂ constants in an air-separation
`gusersub.dll`. Mole fraction, isotherms, and pressures stay correct, so the
error is invisible in the output. See
[references/property-library.md](references/property-library.md) for the
verified ABI and for the constant-patching route when no Fortran compiler is
available.

Verification that actually works: read back a computed mixture property and
compare with a hand calculation from the correlation. In the worked case the
mixture viscosity had to be 2.8714e-5 Pa·s for CO₂-first ordering; the old
library gave 3.91e-5.

### 3. Launch in the interactive session

Aspen automation from a non-interactive SSH child fails on licensing even when
the file paths are right. Register a scheduled task with
`-LogonType Interactive` that runs `cscript.exe` on the VBS, then start it.
[scripts/adsim_launch.ps1](scripts/adsim_launch.ps1) does this and refuses to
start a second copy.

### 4. Drive the run and collect per-cycle data

[scripts/adsim_cycle_run.vbs](scripts/adsim_cycle_run.vbs) is a template: it
initialises, then steps the simulation one controller cycle at a time
(`EndTime = n*period - 1e-4`), writing cumulative totals and inventories at each
cycle boundary. Adapt the `cyclePaths` array to the model.

Why per-cycle stepping instead of one long run: it gives an exact phase-aligned
sample for the balance, it detects a solver pause immediately
(`sim.Time` short of the requested end), and it keeps memory bounded on runs of
hundreds of cycles.

### 5. Audit, then report

```
python3 scripts/analyze_cycles.py RUN_DIR --cycle 300
```

prints the per-cycle balance residual, removal, recovery, purity, and the CSS
verdict against explicit thresholds. Do not report a number from a cycle that
fails the balance check.

For profiles, [scripts/adsim_profile_run.vbs](scripts/adsim_profile_run.vbs)
warms up in-process and then exports one full cycle of axial variables.

## Pitfalls that produce plausible wrong answers

Full list with symptoms and fixes in
[references/failure-catalogue.md](references/failure-catalogue.md). The three
that cause the most damage:

- **`FindMatchingVariables("*")` does not recurse.** It returns only root
  variables (3 of them), which reads as "the model did not load". Use `"~"`.
- **`RecordFrequency = 2` deletes every other cycle from history** and leaves
  sentinel `1.99999988842394e+28` gaps that look like a solver failure. Set it
  to 1.
- **Loosening integrator tolerances to make a stiff run finish** moves the mass
  balance. `AbsErrorTol 5e-4` gave a 0.3% closure error; `1e-8` gave 2e-5%.
  Tighten the tolerance instead of explaining the residual.

## Scripts in this skill

| Script | Role |
| --- | --- |
| `scripts/build_adsim_model.py` | edit a `.ada` template from tables; asserts every substitution and preserves CRLF |
| `scripts/patch_gusersub.py` | rewrite property constants in a **copy** of a DLL, located by byte pattern |
| `scripts/adsim_launch.ps1` | register and start the interactive scheduled task |
| `scripts/adsim_cycle_run.vbs` | step cycles, write per-cycle balances, export history |
| `scripts/adsim_profile_run.vbs` | warm up, then export one full cycle of axial profiles |
| `scripts/analyze_cycles.py` | balance, removal/recovery/purity, CSS verdict |
| `scripts/win_ps.py` | run a PowerShell script on the Windows host over SSH |
| `scripts/inspect_run.ps1` | task state, live Aspen processes, run-directory listing |
| `scripts/clear_stale_adsim.ps1` | kill automation instances only |

The two `.vbs` files are templates: edit the variable arrays at the top for your
flowsheet. Keep them pure ASCII — `cscript` reads `.vbs` in the ANSI codepage and
UTF-8 comment bytes can corrupt the parse.

## Reading bed profiles

[references/profiles.md](references/profiles.md) covers which axial variables to
record, the warm-up-then-record strategy, and how to read the result. The short
version: if the mean loading is far below the equilibrium loading at the
operating partial pressure, the bed is oversized and the headline removal number
is partly bought with excess adsorbent.

## Output contract

Every deliverable states, separately:

- **software and interface** (`ADS Application 4000`, exact call used);
- **input** (generated `.ada`, property library, and the generator that made them);
- **status** (initialised at t=0, reached time T, cycles completed, any pause);
- **verification performed** (balance residual, cross-check method, CSS verdict);
- **assumptions** (isotherm parameters, mass-transfer coefficients, geometry);
- **limitations** (what the model does not represent).

Never describe a transient as steady state, and never describe screening as Aspen.
