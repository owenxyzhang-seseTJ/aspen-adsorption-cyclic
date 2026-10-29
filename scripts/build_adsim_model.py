"""Generate an ADSIM .ada model from a template by script, not by hand.

Hand-editing .ada burns you on three things this skeleton handles: CRLF
round-tripping, per-step Manipulated(k) indices that differ between steps, and
step durations duplicated in the task script.

Copy this file and edit the TABLES, then run it. Every substitution is asserted:
if a path is not found exactly once, the script stops instead of silently
producing a model that is missing a setting.

Usage:
    python3 build_adsim_model.py --template base.ada --output case.ada
"""
from pathlib import Path
import argparse
import re

# ---------------------------------------------------------------- edits
# Simple assignments: full variable path -> value as written into the .ada.
# A path that does not resolve to exactly one assignment stops the build.
SETTINGS = {
    # 'B1.Layer(1).Hb': 0.50,
    # 'B1.Layer(1).Db': 0.050,
    # 'F1.P': 1.3,
}

# Values that only exist as ".record" lines need to be inserted, not replaced.
INSERT_AFTER = {
    # 'F1.T.Fwd.record': ('F1.T_Fwd', 298.15),
}

# Valve actions per step, addressed by VarPath rather than Manipulated index.
# path -> {step: value}
STEP_ACTIONS = {
    # 'VF1.Active_Specification': {1: 2, 2: 2, 3: 2, 4: 2},
}

# Step durations, written to Step_Data(n).StepTime and to the task script.
STEP_SECONDS = {
    # 1: 120.0, 2: 30.0, 3: 120.0, 4: 30.0,
}

# Cycle organiser settings.
CYCLE_SETTINGS = {
    'MaxCycles': 500,
    # RecordFrequency must be 1, or whole cycles vanish from history.
    'RecordFrequency': 1,
}

# Integrator tolerances. Loosening these moves the mass balance; see
# references/steady-state.md.
INTEGRATOR = {
    'Integration.AbsErrorTol': '1.e-008',
    'Integration.RelErrorTol': '1.e-007',
    'TimeSettings.RecordHistory': 'True',
    'TimeSettings.CommunicationInterval': '1.',
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--template', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--rename', action='append', default=[],
                    metavar='OLD=NEW',
                    help='component rename, e.g. --rename Oxygen=CO2')
    args = ap.parse_args()

    # read_bytes keeps CRLF; read_text() would normalise it away and change
    # how every (?m)$ pattern behaves.
    text = args.template.read_bytes().decode('utf-8')
    crlf = '\r\n' in text
    text = text.replace('\r\n', '\n')

    for pair in args.rename:
        old, new = pair.split('=', 1)
        text = re.sub(rf'\b{re.escape(old)}\b', new, text)

    def put(path, value):
        nonlocal text
        pattern = r'(?m)^  ' + re.escape(path) + r' : [^;]+;'
        new, count = re.subn(pattern, f'  {path} : {value};', text)
        if count != 1:
            raise SystemExit(f'path not unique: {path} (matched {count})')
        text = new

    for path, value in SETTINGS.items():
        put(path, value)

    for anchor, (path, value) in INSERT_AFTER.items():
        if not re.search(rf'(?m)^  {re.escape(path)} : ', text):
            text = text.replace(f'  {anchor} : False;\n',
                                f'  {anchor} : False;\n  {path} : {value};\n')

    for path, per_step in STEP_ACTIONS.items():
        for step, value in per_step.items():
            pattern = (rf'(?m)^  (Cycle_Organizer\.Cycle_Data\(1\)\.Step_Data\({step}\)'
                       rf'\.Manipulated\(\d+\)\.VarPath : "{re.escape(path)}";)')
            block = re.search(pattern, text)
            if not block:
                raise SystemExit(f'step {step}: no Manipulated entry for {path}')
            index = re.search(r'Manipulated\((\d+)\)', block.group(1)).group(1)
            put(f'Cycle_Organizer.Cycle_Data(1).Step_Data({step})'
                f'.Manipulated({index}).VarValue', value)

    for step, seconds in STEP_SECONDS.items():
        pre = f'Cycle_Organizer.Cycle_Data(1).Step_Data({step})'
        # Event-driven steps in the template carry no StepTime assignment at
        # all; insert one rather than failing.
        if re.search(rf'(?m)^  {re.escape(pre)}\.StepTime : ', text):
            put(f'{pre}.StepTime', seconds)
        else:
            anchor = f'  {pre}.StepTimeBaseUOM : '
            pos = text.index(anchor)
            text = text[:pos] + f'  {pre}.StepTime : {seconds};\n' + text[pos:]
        if re.search(rf'(?m)^  {re.escape(pre)}\.StepTimeUnits : ', text):
            put(f'{pre}.StepTimeUnits', '"s"')
        else:
            anchor = f'  {pre}.StepTimeBaseUOM : '
            pos = text.index(anchor)
            text = text[:pos] + f'  {pre}.StepTimeUnits : "s";\n' + text[pos:]
        # The task script keeps its own copy; a leftover ": 0;" makes the step
        # instantaneous no matter what StepData says.
        text = text.replace(
            f'Cycle_Organizer.Cycle_Data(1).Step_Time({step}) : 0;',
            f'Cycle_Organizer.Cycle_Data(1).Step_Time({step}) : '
            f'Cycle_Organizer.Cycle_Data(1).Step_Data({step}).StepTime;')

    for key, value in CYCLE_SETTINGS.items():
        put(f'Cycle_Organizer.Cycle_Data(1).{key}', value)

    for key, value in INTEGRATOR.items():
        text = re.sub(rf'(?m)^  {re.escape(key)}: [^;]+;', f'  {key}: {value};', text)

    if crlf:
        text = text.replace('\n', '\r\n')
    args.output.write_text(text, encoding='utf-8', newline='')
    print(args.output)


if __name__ == '__main__':
    main()
