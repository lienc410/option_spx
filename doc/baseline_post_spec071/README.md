# Baseline Post SPEC-071

This directory stores the post-`SPEC-071` HC baseline snapshot.

Purpose:
- compare against `doc/baseline_post_spec070/`
- confirm only aftermath `IC_HV` switches to broken-wing `0.12 / 0.04 / 0.12 / 0.08`
- confirm non-aftermath `IC / IC_HV` stays on symmetric `0.16 / 0.08`

## Quant-style compare summary

Reference:
- old baseline: `doc/baseline_post_spec070/`
- new baseline: `doc/baseline_post_spec071/`

### Structural result

- closed-trade counts (vs `baseline_post_spec070`):
  - `Iron Condor (High Vol)`: `10 -> 10`
  - `Iron Condor`: `12 -> 12`
  - `Bull Call Diagonal`: `21 -> 21`
  - `Bull Put Spread`: `13 -> 13`
  - `Bear Call Spread (High Vol)`: `1 -> 1`
- note: current HC branch also includes `SPEC-068`, so `Bull Put Spread (High Vol)` is `+1` versus the older `SPEC-070` anchor; that drift is unrelated to `SPEC-071`

### Aftermath sample leg diff

Current HC baseline aftermath sample is still the same two `IC_HV` entries:
- `2026-03-09`
- `2026-03-10`

For those two dates, selector now emits:
- short call `0.12`
- long call `0.04`
- short put `0.12`
- long put `0.08`

Constructed strikes:

- `2026-03-09`
  - old (`SPEC-070`): `SC 7672 / LC 8017 / SP 6192 / LP 5920`
  - new (`SPEC-071`): `SC 7818 / LC 8322 / SP 6073 / LP 5920`
- `2026-03-10`
  - old (`SPEC-070`): `SC 7636 / LC 7974 / SP 6192 / LP 5927`
  - new (`SPEC-071`): `SC 7781 / LC 8265 / SP 6073 / LP 5927`

Interpretation:
- short legs move inward from `0.16 -> 0.12`
- put long leg stays at `0.08`
- call long leg moves further out to `0.04`
- this creates the intended asymmetric broken-wing structure

Important implementation note:
- in actual strike space, the call-side wing becomes **wider**, not tighter
- this is consistent with the selector deltas (`0.04` is farther OTM than `0.08`)
- so the spec intent is satisfied at the delta level, but the old “call wing < put wing” wording is not true after strike construction

### Metric diff

Formal compare against `baseline_post_spec070`:
- total PnL: `79,736.85 -> 73,748.04` (`-5,988.80`)
- Sharpe: `2.09 -> 1.97` (`-0.12`)
- MaxDD: unchanged at `-9,391.92`

Current-stack compare against `baseline_post_spec069` (better isolation of `SPEC-071` itself):
- total PnL: `80,765.71 -> 73,748.04` (`-7,017.67`)
- Sharpe: `2.14 -> 1.97` (`-0.17`)
- MaxDD: unchanged at `-9,391.92`
- `n_open_at_end`: unchanged at `2`

### Interpretation

`SPEC-071` is a real strategy-behavior change:
- it preserves the same aftermath entry dates
- it changes the IC_HV payoff shape through inward short deltas plus asymmetric long-wing deltas
- on the current HC baseline this lowers total PnL and Sharpe, while leaving MaxDD unchanged

So this is not a cleanup or selector/engine consistency fix only; it is a substantive structural change to the aftermath IC_HV trade shape.
