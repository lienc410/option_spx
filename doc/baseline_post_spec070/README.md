# Baseline Post SPEC-070

This directory stores the post-`SPEC-070` HC baseline snapshot.

Purpose:
- compare against `doc/baseline_2026-04-24/`
- serve as the new anchor for `SPEC-068` and `SPEC-071`

Expected comparison focus:
- `IRON_CONDOR` / `IRON_CONDOR_HV` long legs move from wing-based to delta-based
- non-IC strategies should remain structurally unchanged
- trade-count and entry-date drift, if any, should be isolated and explained in the Quant compare note before downstream SPEC work continues

## Quant-style compare summary

Reference:
- old baseline: `doc/baseline_2026-04-24/`
- new baseline: `doc/baseline_post_spec070/`

### Structural result

- system trade count: `59 -> 59` (unchanged)
- `IRON_CONDOR_HV` trade count: `10 -> 10` (entry-date set identical)
- `IRON_CONDOR` trade count: `13 -> 13` (entry-date set identical)
- non-IC strategies:
  - `Bear Call Spread (High Vol)` unchanged
  - `Bull Call Diagonal` unchanged
  - `Bull Put Spread` unchanged

This means the SPEC-070 change is isolated to IC leg construction only. No selector-level route drift or cascade was introduced in the 2023-to-current baseline window.

### 2026-03 strike diff

- `2026-03-09`
  - old: `[7672, 7772, 6192, 6092]`
  - new: `[7672, 8017, 6192, 5920]`
- `2026-03-10`
  - old: `[7636, 7736, 6192, 6092]`
  - new: `[7636, 7974, 6192, 5927]`

Interpretation:
- short legs are unchanged
- both long wings move materially farther OTM under true `delta 0.08`
- the original SPEC assumption that delta-based long legs would be tighter than the old fixed-width wings was incorrect

### System metric diff

- total PnL: `93,890.04 -> 79,736.85` (`-14,153.19`)
- Sharpe: `2.36 -> 2.09` (`-0.27`)
- MaxDD: `-9,807.63 -> -9,391.92` (`+415.72`, slightly improved)

### Interpretation

SPEC-070 passes the semantic alignment goal:
- engine now matches selector’s stated `δ0.08` long-leg intent
- no trade-count drift was introduced

But this is not a free improvement:
- wings became materially wider
- IC and IC_HV average PnL both fell
- system Sharpe declined

This should be treated as a real behavioral change, not a pure cleanup.
