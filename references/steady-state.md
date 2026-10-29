# Proving cyclic steady state (and the trap that looks like it)

## The definition to use

A cyclic process is at CSS when, for two consecutive cycles at the same phase,

1. every unit's per-cycle flow is unchanged,
2. the system inventory (beds + all buffers) is unchanged, and
3. the derived metrics (removal, recovery, purity) are unchanged.

Conditions 1 and 2 are independent. Checking only 1 is the classic mistake,
because the flows can be flat while the beds are still accumulating.

## The trap

On a two-bed VSA model, the removal rate reached a plateau early and then stayed
flat to the last decimal for the remaining sixty-odd cycles. Anyone sampling only
removal would have declared CSS at that point.

The inventory told a different story. Bed holdup fell for tens of cycles,
bottomed out, then rose again — a slow oscillation with a period far longer than
one cycle — while the recovery drifted across a band of several percentage
points and removal sat still.

The cause was mundane: two light-product buffer tanks started at the feed
composition and needed ~100 cycles to wash out. That is a modelling
initial-condition artefact, not process physics — but you cannot tell which it is
unless you plot inventory.

## Practical protocol

Sample exactly at cycle boundaries (`EndTime = n*period - 1e-4`) and record:

- cumulative `*_Total_Component_Fwd` and `*_Total_Component_Rev` for every feed
  and product unit, plus `*_Total_Material_Fwd` / `_Rev`;
- `BedAdsorbedInventory(comp)` and `BedGasInventory(comp)` for every bed;
- `Mc(comp)` for every buffer tank;
- bed pressures at the two ends.

Then per cycle:

```
feed    = dF1_total_fwd - dF1_total_rev
light   = dP1_total_fwd - dP1_total_rev
heavy   = dW1_total_fwd - dW1_total_rev
dinv    = inventory(this cycle) - inventory(previous cycle)
residual = feed - light - heavy - dinv
```

Thresholds that were used and held:

| check | suggested threshold |
| --- | --- |
| balance residual / feed | < 1e-4 |
| inventory drift / feed per cycle | < 0.5% |
| cycle flow change | < 0.5% |
| removal / recovery change | < 0.05 pp |

These are starting points, not universal constants; state the ones you used. In
practice the inventory drift is the last to settle, usually an order of magnitude
above the balance residual.

Report the cycle range that passes, not just one cycle. State plainly if no range
passes.

## Cross-check the accounting itself

Do not trust a balance you have not tested. Two independent routes:

1. **Cumulative differences** at fixed phase (above).
2. **History integration**: trapezoid-integrate the 1 s unit flows over a cycle
   and compare with the per-cycle cumulative delta.

On the case this was developed against, the two routes agreed to roughly 1e-11
relative on feed material. If they disagree by more than a fraction of a percent,
the phase alignment is wrong (see the history-label issue in the failure
catalogue) or the units differ.

Also check composition consistency for free: feed CO₂ by `Total_Component` must
equal `y_feed * Total_Material`. Agreement to all printed digits means the
component and material counters are consistent.

## Initial conditions that cost cycles

Beds and buffers carry the template's composition. If the template was an
air-separation case, every vessel may start at 21% "O2" (renamed CO2) at 3 bar.
Washing that out can take a hundred cycles and will masquerade as a slow process
drift.

Fixed by setting bed initial composition to the feed composition at the operating
pressure — but note the constraint from the failure catalogue: write only the
component whose `spec` is `Initial`, not both.

## What to report

- the cycle range used for the numbers;
- the balance residual over that range;
- the CSS verdict with its thresholds;
- if CSS was not reached, the observed drift per cycle and the direction, so the
  reader can judge how far the number could move.
