# Baseline Post SPEC-068

This directory stores the post-`SPEC-068` HC baseline snapshot.

Purpose:
- compare against `doc/baseline_post_spec070/`
- confirm the per-strategy HV spell budget fix is behaviorally neutral on the current HC baseline unless a real HV multi-strategy collision appears

## Quant-style compare summary

Reference:
- old baseline: `doc/baseline_post_spec070/`
- new baseline: `doc/baseline_post_spec068/`

### Structural result

- system trade count: `59 -> 60`
- the only new trade is:
  - `Bull Put Spread (High Vol)`
  - entry `2025-05-02`
  - exit `2025-05-13`
  - PnL `+1727.97`

All pre-existing strategies keep their original counts:
- `Iron Condor (High Vol)`: `10 -> 10`
- `Iron Condor`: `13 -> 13`
- `Bull Call Diagonal`: `21 -> 21`
- `Bull Put Spread`: `14 -> 14`
- `Bear Call Spread (High Vol)`: `1 -> 1`

Interpretation:
- this was not a purely defensive no-op
- the per-strategy spell budget fix released one real `BPS_HV` trade that had previously been blocked by aggregate HV spell counting

### System metric diff

- total PnL: `79,736.85 -> 81,464.82` (`+1,727.97`)
- Sharpe: `2.09 -> 2.13` (`+0.04`)
- MaxDD: unchanged at `-9,391.92`

### Interpretation

SPEC-068 behaves as intended:
- `IC_HV` can consume its own spell budget without incorrectly exhausting the `BPS_HV / BCS_HV` budget
- the current HC baseline contains one real case where the old aggregate counter was too strict
- the fix produces a positive, isolated cascade rather than broad drift
