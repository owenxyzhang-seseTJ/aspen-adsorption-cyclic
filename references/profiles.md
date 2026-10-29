# Axial profiles: what to export and how to read them

## Why bother

Per-cycle totals tell you the process works. Profiles tell you *why*, and they
catch design errors that totals hide.

On a two-bed VSA case the totals looked fine — removal was high and stable, purity
looked plausible. The profiles showed the adsorbed CO₂ was confined to the first
fifth of the bed:

| axial position (% of bed length) | loading (fraction of inlet value) |
| --- | --- |
| 2.5% | 1.00 |
| 7.5% | 0.65 |
| 12.5% | 0.38 |
| 17.5% | 0.22 |
| 22.5% | 0.15 |
| 60% | 0.04 |
| 97.5% | 0.11 |

The mean loading was a few percent of the equilibrium capacity at the operating
partial pressure, and the CO₂ fed per cycle was under a tenth of the bed's
capacity — an order of magnitude of oversizing.

That reframes the headline number: a high removal rate can be bought with excess
adsorbent. Reporting removal alone, without the utilisation, is misleading.

## Variables to record

Per bed, per node `i = 1..N`:

```
B1.Layer(1).P(i)              pressure
B1.Layer(1).Vg(i)             interstitial velocity
B1.Layer(1).Y(i,"CO2")        gas-phase mole fraction
B1.Layer(1).W(i,"CO2")        adsorbed loading
B1.Layer(1).C(i,"CO2")        gas-phase concentration
```

Plus the unit streams, so the profile cycle can be tied to the balance:

```
F1.F, P1.F, W1.F
u.Y_Fwd("CO2"), u.Y_Rev("CO2")
```

Set `Record = True` on all of them, then export with a bounded
`v.History(start, end, interval)`.

## Recording strategy for long runs

Recording 173 variables for 35,000 s at 1 s resolution is wasteful and slow to
export. Two-stage approach used here:

1. initialise, then warm up N cycles **without** the profile variables recorded;
2. turn `Record = True` on the profile set;
3. run exactly one more cycle;
4. export only that window.

This keeps the export to a few hundred points per variable and gives a clean,
phase-aligned cycle.

## Reading the result

- **Front position.** Where does loading drop to a few percent of the inlet
  value? If it is a small fraction of bed length, the bed is oversized for this
  feed rate.
- **Utilisation.** Compare mean loading with `q_eq` at the operating partial
  pressure. Under ~20% is worth flagging.
- **Regeneration completeness.** Compare end-of-evacuation loading with the
  equilibrium loading at the regeneration pressure. A large gap means the step is
  too short or the conductance too low.
- **Purity limit.** Look at the gas-phase CO₂ profile at end of evacuation: if it
  falls steeply along the bed, the desorbate is being diluted by N₂ held in the
  upstream part of the bed. That is a structural purity ceiling, not a tuning
  problem.

## Aligning the profile cycle to steps

Do not trust history time labels (see failure catalogue item 11). Derive step
boundaries from a physical signal — the sharp pressure transition when one bed
switches from adsorption to evacuation — then verify the whole window by
integrating `F1.F` over it and comparing with the independently measured
per-cycle feed total.

On this model the 300 s window integrated to 5.75228e-4 kmol against a per-cycle
cumulative delta of 5.75228e-4 kmol (ratio 1.0000), which fixed the phase
unambiguously.

## Plotting checklist

- both beds, same fields, one row each, so asymmetry is visible;
- adsorption-end and evacuation-end as two series per panel;
- axial position in metres from the feed end, not node index;
- loading in mol/kg (convert from kmol/kg), pressure in bar, velocity in m/s;
- export both PNG (600 dpi) and SVG with editable text.
