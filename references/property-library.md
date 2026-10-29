# User property library (`gusersub.dll`)

## When this matters

The model has `Physical_Properties : "User Procedures"`. That makes ADSIM call a
DLL for average molecular weight, viscosity, and enthalpy instead of using
internal correlations. The DLL is looked up by the `LIBRARY:` name inside
`.ada`, defaulting to `gusersub`, resolved from the working directory of the
running document.

If the component list does not match the DLL's assumption, **nothing errors**.
Adsorption is driven by partial pressure and the isotherm, so the separation
looks physically sensible while molecular weight, viscosity, and enthalpy are
wrong.

## The mapping rule

ADSIM passes per-component arrays in **ASCII order of the component name**, not
in the order the components appear in `Components : [...]`.

- Components `["Nitrogen", "CO2"]` → arrays are `[CO2, Nitrogen]`
  (`"CO2"` < `"Nitrogen"`).
- The stock air-separation DLL is built for `[N2, O2]`.

So with a CO₂/N₂ model the stock library assigns CO₂ ← N₂ constants and
N₂ ← O₂ constants. Confirmed against `Examples/N2PSA/puavmolw.f`
(`MW = [28.013, 31.999]`) and `pugvisc.f`.

## Option A — check whether an official example already fits

Look in `Examples/<case>/puavmolw.f` and `pugvisc.f` for the `Components:` line.
Useful ones seen:

| Example | Order in source | Usable for CO₂/N₂ alone? |
| --- | --- | --- |
| `N2PSA` | N₂, O₂ | no — this is the trap |
| `AirPure` | CO₂, H₂O, N₂, O₂ | no, but its CO₂ and N₂ viscosity/enthalpy coefficients are the right source |
| `NatGas` | C₂H₆, CO₂, N₂ | no — extra leading component changes the mapping |

Do not "borrow" a three-component DLL by pretending a dummy component exists.
The extra component changes every array index.

## Option B — build a correct DLL

Official wrapper sources are in
`<install>\Aspen Adsorption V14.0\Bin\ProcDefs\`: `puavmolwI.f`, `pugenthmI.f`,
`pugviscI.f`. They are thin wrappers around your `pU*` routines.

Verified C ABI (Win64, `void` return, no structs, 14 pointer arguments):

```
void SU55IF_PUAVMOLW(double *pInputs, int64_t *pInSizes, double *pOutputs,
                    int64_t *pOutSizes, int64_t *pInOffs, int64_t *pOutOffs,
                    int64_t *pIflag, int64_t *pPropsId, double *pWork,
                    int64_t *pWSize, double *pDeriv, int64_t *pNOut,
                    int64_t *pNIn, int64_t *pICall);
```

- Exported names are exactly `SU55IF_PUAVMOLW`, `SU55IF_PUGENTHM`,
  `SU55IF_PUGVISC`.
- Sizes and offsets are **64-bit** (the x64 wrapper reads them with 8-byte
  loads), even though the Fortran source declares plain `INTEGER`.
- Offsets are Fortran **1-based**; subtract 1 in C.
- For MW: `y = pInputs + pInOffs[0] - 1`, `n = pInSizes[0]`.
- For enthalpy/viscosity: `T = pInputs[pInOffs[0]-1]`,
  `P = pInputs[pInOffs[1]-1]`, `y = pInputs+pInOffs[2]-1`, and the official
  wrapper takes `n = pInSizes[0]` (not `[2]`).
- Set `*pIflag = 1` on success.

Official build settings are in `Bin/ProcDefs/LINKOpt.dat`
(`/DLL /SUBSYSTEM:CONSOLE /FORCE:MULTIPLE`) — MSVC linker conventions.

## Option C — patch the constants when no compiler is available

The constants live in `.rdata` as IEEE-754 doubles and can be located and
rewritten in a **copy**, leaving the vendor file untouched. This is what was used
here after the Windows host turned out to have no `ifort`/`ifx`/`gfortran` and the
cross-compiler download failed.

Procedure:

1. Copy the stock DLL into your run directory.
2. Locate each constant by its exact `struct.pack('<d', value)` bytes; require a
   unique match before patching.
3. Rewrite MW, the viscosity pairs, and the enthalpy coefficients for the new
   component order.
4. Re-read the patched file and assert each offset now holds the intended value.

Working example: [scripts/patch_gusersub.py](../scripts/patch_gusersub.py).

Values that were verified for CO₂-first / N₂-second:

| Quantity | CO₂ | N₂ |
| --- | --- | --- |
| MW (g/mol) | 44.010 | 28.013 |
| viscosity A | 578.08 | 90.30 |
| viscosity B | 185.24 | 46.14 |
| cp (J mol⁻¹ K⁻¹) | 37.13 | 29.12 |

Viscosity form (from `Examples/AirPure/pugvisc.f`):

```
mu = 1e-3 * sum_i y_i * 10^(A_i * (1/T - 1/B_i))     Pa*s
```

## Verify — this step is not optional

Read back a computed mixture property and compare with a hand calculation:

```
MUg(1) at y_CO2 = 0.15, 298.15 K
  CO2-first ordering : 2.8714e-5 Pa*s    <- correct
  air library (N2/O2): 3.91e-5 Pa*s      <- wrong
```

The two differ by 36%, so a single read of `MUg` distinguishes them. Do this
before running any cycles; otherwise hours of simulation rest on an unverified
property layer.

Also read back `RHOg` and check it against `P*MW/(R*T)` for the mixture.

## Isothermal models

If every `Tg(i)` is fixed and there is no energy balance, enthalpy never enters
the solution. Say so explicitly rather than implying the enthalpy function was
validated. Viscosity does matter (momentum balance / Ergun) and molecular weight
matters (density and velocity), so those two still need to be right.
