"""Per-cycle material balance, removal/recovery/purity, and a CSS verdict.

Reads the `cycles.tsv` written by adsim_cycle_run.vbs and reports, for every
cycle, the component balance including the inventory term. Refuses to declare
cyclic steady state unless both the flows and the inventory are flat.

Usage:
    python3 analyze_cycles.py RUN_DIR
    python3 analyze_cycles.py RUN_DIR --component CO2 --units F1 P1 W1
    python3 analyze_cycles.py RUN_DIR --skip-first 5
"""
from pathlib import Path
import argparse
import csv
import json
import math

ap = argparse.ArgumentParser()
ap.add_argument("directory", type=Path)
ap.add_argument("--component", default="CO2")
ap.add_argument("--feed", default="F1")
ap.add_argument("--light", default="P1", help="light-product unit (CO2-lean)")
ap.add_argument("--heavy", default="W1", help="heavy-product unit (CO2-rich)")
ap.add_argument("--skip-first", type=int, default=1,
                help="cycles to drop at the start (initial transient)")
ap.add_argument("--drift-tol", type=float, default=0.5,
                help="inventory drift limit, percent of feed per cycle")
ap.add_argument("--flow-tol", type=float, default=0.5,
                help="cycle flow change limit, percent")
ap.add_argument("--metric-tol", type=float, default=0.05,
                help="removal/recovery change limit, percentage points")
ap.add_argument("--balance-tol", type=float, default=0.01,
                help="balance residual limit, percent of feed")
ap.add_argument("--out", default="cycle_analysis.json")
args = ap.parse_args()

SENTINEL = 1e20


def read_rows(path):
    with path.open() as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def value(row, key):
    v = float(row[key])
    if not math.isfinite(v) or abs(v) >= SENTINEL:
        raise ValueError(f"invalid Aspen value for {key}: {v}")
    return v


def inventory(row):
    """Sum every per-component holdup column: bed inventories and tank Mc."""
    return sum(value(row, k) for k in row
               if ("Inventory" in k or ".Mc(" in k) and args.component in k)


def delta(row, prev, unit, base, suffix):
    """Per-cycle amount, forward minus reverse, from cumulative totals.

    `base` is the variable stem ('Total_Component' or 'Total_Material') and
    `suffix` the component index, so the key is e.g.
    F1.Total_Component_Fwd("CO2").
    """
    stem = f"{unit}.{base}"
    fwd = f"{stem}_Fwd{suffix}"
    d = value(row, fwd) - value(prev, fwd)
    rev = f"{stem}_Rev{suffix}"
    if rev in row:
        d -= value(row, rev) - value(prev, rev)
    return d


rows = read_rows(args.directory / "cycles.tsv")
if len(rows) < 3:
    raise SystemExit("need at least 3 cycle rows")

COMP = 'Total_Component'
MAT = 'Total_Material'
SUFFIX = f'("{args.component}")'

results = []
for i in range(1, len(rows)):
    row, prev = rows[i], rows[i - 1]

    feed = delta(row, prev, args.feed, COMP, SUFFIX)
    light = delta(row, prev, args.light, COMP, SUFFIX)
    heavy = delta(row, prev, args.heavy, COMP, SUFFIX)
    heavy_total = delta(row, prev, args.heavy, MAT, '')

    d_inv = inventory(row) - inventory(prev)
    residual = feed - light - heavy - d_inv

    rec = {
        "cycle": i,
        "time_s": value(row, "Time (s)"),
        "feed_component": feed,
        "light_component": light,
        "heavy_component": heavy,
        "inventory_component": inventory(row),
        "inventory_change": d_inv,
        "balance_residual": residual,
        "balance_residual_pct_feed": 100 * residual / feed if feed else None,
        "removal_pct": 100 * (1 - light / feed) if feed else None,
        "recovery_pct": 100 * heavy / feed if feed else None,
        "heavy_purity_pct": (100 * heavy / heavy_total) if heavy_total else None,
    }
    if results:
        p = results[-1]
        rec["flow_change_pct"] = 100 * max(
            abs(rec[k] - p[k]) / max(abs(rec[k]), 1e-30)
            for k in ("feed_component", "light_component", "heavy_component"))
        rec["removal_change_pp"] = abs(rec["removal_pct"] - p["removal_pct"])
        rec["recovery_change_pp"] = abs(rec["recovery_pct"] - p["recovery_pct"])
        rec["inventory_drift_pct_feed"] = 100 * abs(d_inv) / max(abs(feed), 1e-30)
    results.append(rec)


def passes(r):
    return (abs(r["balance_residual_pct_feed"]) < args.balance_tol
            and r.get("inventory_drift_pct_feed", 1e9) < args.drift_tol
            and r.get("flow_change_pct", 1e9) < args.flow_tol
            and r.get("removal_change_pp", 1e9) < args.metric_tol
            and r.get("recovery_change_pp", 1e9) < args.metric_tol)


usable = [r for r in results if r["cycle"] > args.skip_first]
css_range = None
for start in range(len(usable) - 2):
    window = usable[start:start + 3]
    if all(passes(r) for r in window):
        css_range = (window[0]["cycle"], window[-1]["cycle"])

record = {
    "source": str(args.directory / "cycles.tsv"),
    "component": args.component,
    "cycles": results,
    "criteria": {
        "balance_pct_feed": args.balance_tol,
        "inventory_drift_pct_feed": args.drift_tol,
        "flow_change_pct": args.flow_tol,
        "metric_change_pp": args.metric_tol,
        "consecutive_cycles": 3,
    },
    "css_range": css_range,
    "css_verified": css_range is not None,
    "max_balance_residual_pct_feed": max(
        abs(r["balance_residual_pct_feed"]) for r in results),
}

(args.directory / args.out).write_text(
    json.dumps(record, ensure_ascii=False, indent=2))

last = results[-1]
print(f"cycles analysed: {len(results)} (skipped first {args.skip_first})")
print(f"balance residual, max |.|: {record['max_balance_residual_pct_feed']:.3e} % of feed")
print(f"last cycle {last['cycle']}: removal {last['removal_pct']:.2f} %, "
      f"recovery {last['recovery_pct']:.2f} %, purity {last['heavy_purity_pct']:.2f} %")
if css_range:
    lo, hi = css_range
    seg = [r for r in results if lo <= r["cycle"] <= hi]
    print(f"CSS verified over cycles {lo}-{hi}")
    print(f"  removal  {min(r['removal_pct'] for r in seg):.2f}-"
          f"{max(r['removal_pct'] for r in seg):.2f} %")
    print(f"  recovery {min(r['recovery_pct'] for r in seg):.2f}-"
          f"{max(r['recovery_pct'] for r in seg):.2f} %")
    print(f"  purity   {min(r['heavy_purity_pct'] for r in seg):.2f}-"
          f"{max(r['heavy_purity_pct'] for r in seg):.2f} %")
else:
    drifts = [r.get("inventory_drift_pct_feed") for r in results[-3:]]
    print("CSS NOT verified. Last three inventory drifts (% of feed): "
          + ", ".join(f"{d:.3f}" for d in drifts if d is not None))
