"""Rewrite the property constants inside a copy of an ADSIM gusersub.dll.

ADSIM passes per-component arrays in ASCII order of component name, so an
air-separation library ([N2, O2]) silently mis-maps a CO2/Nitrogen model. This
patches the copy's .rdata doubles in place and leaves the vendor file untouched.

Constants are located by their exact IEEE-754 bytes, not by hard-coded offsets:
offsets differ between builds. Each original value must match exactly once, or
the script refuses -- an ambiguous match means you are about to corrupt the DLL.

Verify afterwards (see references/property-library.md): read back a computed
mixture property such as `B1.Layer(1).MUg(1)` and compare with a hand
calculation. A wrong library is invisible in the mass balance.

Usage:
    python3 patch_gusersub.py --src gusersub.dll --dst gusersub_co2_n2.dll
    python3 patch_gusersub.py --inspect gusersub.dll
"""
from pathlib import Path
import argparse
import struct

# Verified for CO2-first / Nitrogen-second ordering.
# viscosity: mu = 1e-3 * sum y_i * 10^(A_i*(1/T - 1/B_i))  [Pa s]
# cp: mean isobaric molar heat capacity near 298 K, J/(mol K)
DEFAULT = {
    "MW": [44.010, 28.013],
    "VISC_A": [578.08, 90.30],
    "VISC_B": [185.24, 46.14],
    "CP": [37.13, 29.12],
    # The vendor enthalpy function computes sum(y_i * (A + B*T + C*T^2 + D*T^3))
    # * (T - Tref). Keeping the original B/C/D while swapping A would leave a
    # temperature-dependent cp whose coefficients belong to the old components,
    # so they are zeroed and the constant cp above defines the enthalpy.
    "CP_B": [0.0, 0.0],
    "CP_C": [0.0, 0.0],
    "CP_D": [0.0, 0.0],
    # air-separation originals in the same array order, used to find them
    "_from": {"MW": [28.013, 31.999],
              "VISC_A": [90.30, 85.68],
              "VISC_B": [46.14, 51.50],
              "CP": [31.15, 28.106],
              "CP_B": [-0.01356, -3.68e-06],
              "CP_C": [2.679e-05, 1.745e-05],
              "CP_D": [-1.168e-08, -1.065e-08]},
}

ap = argparse.ArgumentParser()
ap.add_argument("--src", type=Path, required=True)
ap.add_argument("--dst", type=Path)
ap.add_argument("--inspect", action="store_true",
                help="report where each source constant appears, then exit")
ap.add_argument("--allow-empty-cp", action="store_true",
                help="tolerate not finding the enthalpy coefficients")
args = ap.parse_args()

data = bytearray(args.src.read_bytes())


def f32(x):
    """Widen a float32 constant to double, the way the compiler stored it.

    The vendor DLL holds these as REAL(4) widened to REAL(8), so 90.30 is
    actually 90.3000030517578. Matching the exact double of 90.3 finds nothing.
    """
    return struct.unpack("<f", struct.pack("<f", x))[0]


def find(value):
    """Offsets where this constant appears, trying double and widened float32."""
    hits = []
    for candidate in {value, f32(value)}:
        pattern = struct.pack("<d", candidate)
        start = 0
        while True:
            i = data.find(pattern, start)
            if i < 0:
                break
            if i not in hits:
                hits.append(i)
            start = i + 1
    return sorted(hits)


if args.inspect:
    for group, values in DEFAULT["_from"].items():
        for v in values:
            print(f"{group:<7} {v:>10.6g}  at {find(v)}")
    raise SystemExit(0)

if args.dst is None:
    raise SystemExit("--dst is required unless --inspect is used")

plan = []
for group, new_values in DEFAULT.items():
    if group.startswith("_"):
        continue
    old_values = DEFAULT["_from"][group]
    for old, new in zip(old_values, new_values):
        hits = find(old)
        if len(hits) != 1:
            if group == "CP" and args.allow_empty_cp and not hits:
                print(f"skip {group} {old}: not found (allowed)")
                continue
            raise SystemExit(
                f"{group} {old}: found {len(hits)} matches, need exactly 1. "
                "Refusing to patch a build this script was not written for.")
        plan.append((hits[0], old, new))

for offset, old, new in plan:
    struct.pack_into("<d", data, offset, new)
args.dst.write_bytes(data)

readback = Path(args.dst).read_bytes()
for offset, old, new in plan:
    got = struct.unpack_from("<d", readback, offset)[0]
    assert abs(got - new) < 1e-12, f"offset {offset}: wrote {new}, read {got}"
    print(f"{offset}: {old:.6g} -> {got:.6g}")
print(f"PATCHED {args.dst}")
print("Now verify by reading back a mixture property in ADSIM; do not skip this.")
