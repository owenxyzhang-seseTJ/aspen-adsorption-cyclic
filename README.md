# aspen-adsorption-cyclic

A Claude Code skill for running and auditing **Aspen Adsorption (ADSIM)** dynamic
cyclic simulations — PSA / VSA / TSA — through Windows COM automation.

It exists because the expensive failures in this workflow are silent. The batch
interface reports success while writing empty files; a mis-ordered property
library changes molecular weight and viscosity without changing the mass
balance; a `RecordFrequency` of 2 deletes every other cycle from history and
leaves sentinel values that look like a solver crash. Every item in the failure
catalogue produced a *plausible wrong answer* before it produced an error.

## What it covers

- generating cyclic `.ada` models from a template by script (CRLF-safe,
  VarPath-addressed valve actions, duplicated step times);
- fixing the user property library (`gusersub.dll`) for a new component pair,
  including a byte-pattern patch route when no Fortran compiler is available;
- launching ADSIM in the interactive Windows session via a scheduled task;
- stepping hundreds of cycles while collecting per-cycle balances;
- exporting one full cycle of axial bed profiles;
- proving cyclic steady state, with the inventory term, before reporting numbers.

## Install

```bash
git clone https://github.com/owenxyzhang-seseTJ/aspen-adsorption-cyclic.git \
  ~/.claude/skills/aspen-adsorption-cyclic
```

Claude Code discovers skills in `~/.claude/skills/`. The directory name should
stay `aspen-adsorption-cyclic` so it matches the `name:` in `SKILL.md`.

## Requirements

- Windows host with Aspen Adsorption V14 and a working automation licence.
- An SSH alias to that host. The helper defaults to the `ADSIM_SSH_HOST`
  environment variable, or pass `--host`.
- Python 3.9+ on the machine running the helper scripts (no third-party packages).
- The `.vbs` runners are templates: edit the variable arrays at the top for your
  flowsheet. Keep them pure ASCII — `cscript` reads `.vbs` in the ANSI codepage.

## Structure

```
SKILL.md                          workflow and the five rules that decide whether a result is real
references/failure-catalogue.md   14 failure modes: symptom, wrong conclusion, cause, fix
references/steady-state.md        CSS criteria, the inventory trap, two independent balances
references/property-library.md    user DLL ABI, component ordering, constant patching
references/profiles.md            which axial variables to record and how to read them
scripts/                          model generator, DLL patcher, launchers, runners, analyser
```

## Scope and honesty

The examples are generalised from a real two-bed VSA study; specific performance
figures from that study are deliberately omitted. Screening calculations are not
Aspen evidence, and a transient is not steady state — the skill says so in the
places where it is tempting to blur the two.

## Licence

No licence file yet. Until one is added, default copyright applies; open an issue
if you want a specific licence.
