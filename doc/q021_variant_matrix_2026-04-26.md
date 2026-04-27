# Q021 Variant Matrix - V0/V1/V2/V3/V_A/V_B/V_C/V_D/V_E/V_F/V_G/V_H/V_I/V_J/V_K

- Date: 2026-04-26
- Author: Codex summary from existing Q021 detailed-layer docs
- Purpose: provide one canonical matrix for all Q021 `V_i` variants, their rule formulas, and the standard metrics pack used in later rounds

## Source Docs

- Phase 1 attribution: [doc/q021_phase1_attribution_2026-04-25.md](/Users/lienchen/Documents/workspace/SPX_strat/doc/q021_phase1_attribution_2026-04-25.md)
- Phase 2 full-engine: [doc/q021_phase2_full_engine_2026-04-25.md](/Users/lienchen/Documents/workspace/SPX_strat/doc/q021_phase2_full_engine_2026-04-25.md)
- Phase 3 half-size and V_D supplement: [doc/q021_phase3_half_size_2026-04-25.md](/Users/lienchen/Documents/workspace/SPX_strat/doc/q021_phase3_half_size_2026-04-25.md)
- Phase 4 sizing curve: [doc/q021_phase4_sizing_curve_2026-04-26.md](/Users/lienchen/Documents/workspace/SPX_strat/doc/q021_phase4_sizing_curve_2026-04-26.md)
- Phase 3 prototype: [backtest/prototype/q021_phase3_half_size.py](/Users/lienchen/Documents/workspace/SPX_strat/backtest/prototype/q021_phase3_half_size.py)
- Phase 4 prototype: [backtest/prototype/q021_phase4_sizing_curve.py](/Users/lienchen/Documents/workspace/SPX_strat/backtest/prototype/q021_phase4_sizing_curve.py)

## Reading Guide

- `V0-V3` are the Phase 2 semantic reconstruction variants.
- `V_A-V_D` first appear in Phase 3.
- `V_A/V_D/V_E/V_G/V_H/V_J` are the six formal Phase 4 sizing-curve variants.
- `V_F/V_I/V_K` were discussed as candidates, but not promoted to formal tested variants.
- Some variants have a full standard metrics-pack table. Others only have the smaller PnL / Sharpe / MaxDD package from their phase document.

## Core Rule Dimensions

All Q021 variants are modifying the same aftermath IC_HV structure:

```text
AFTERMATH_IC_HV_RULE =
  gate(peak_10d, off_peak_pct, regime, cluster_state, overlap_state, disaster_state)
  x size_multiplier(first_or_second_entry)
  x cap_policy(cluster_cap, global_cap, total_bp_cap)
```

The main levers are:

| Lever | Typical choices |
|---|---|
| `AFTERMATH_OFF_PEAK_PCT` | `0.05`, `0.10` |
| same-cluster 2nd-entry policy | allow, block, half-size, split-entry/no-bounce |
| first-entry size | `1.0x`, `1.5x`, `2.0x` |
| overlap / disaster / cap controls | no-overlap, disaster-cap, global cap, total BP cap |

## Complete Variant Matrix

| Variant | Phase | Rule Formula | Research Intent | Status | Known Outcome |
|---|---|---|---|---|---|
| `V0` | Phase 2 | `IC_HV_MAX_CONCURRENT = 1`; `AFTERMATH_OFF_PEAK_PCT = 0.05` | Pre-SPEC-064/066 baseline | Tested | Old baseline; weaker than later `V1` / `V_A` |
| `V1` | Phase 2 | `IC_HV_MAX_CONCURRENT = 2`; `AFTERMATH_OFF_PEAK_PCT = 0.10` | Current `SPEC-066` reference in Phase 2 | Tested | Becomes the production reference carried forward |
| `V2` | Phase 2 | same-cluster aftermath max `1`; no global cap; `OFF_PEAK = 0.10` | Pure PM-intent "multi-peak capture" version | Tested | Slightly positive PnL vs `V1`, but max concurrent IC_HV rises to `6`, operationally unacceptable |
| `V3` | Phase 2 | same-cluster aftermath max `1`; global `IC_HV cap = 2`; `OFF_PEAK = 0.10` | PM-intent plus minimal risk guardrail | Tested | Captures distinct 2nd peak in 2026-03, but loses materially vs `V1` |
| `V_A` | Phase 3 / 4 | `SPEC-066`: `cap = 2`; `OFF_PEAK = 0.10`; normal `1.0x` size | Unified production baseline | Tested | Wins on capital efficiency; retained as baseline |
| `V_B` | Phase 3 | base = `V_A`; if same-cluster 2nd aftermath `IC_HV`, then `size = 0.5x`; else `1.0x` | Keep the 2nd trade but de-risk it | Tested | Linear scaled-down version of `V_A`; no structural improvement |
| `V_C` | Phase 3 | base = `V_A`; if same-cluster 2nd aftermath `IC_HV`, `block`; distinct-cluster aftermath still allowed | Force "distinct cluster only" second trade | Tested | Better semantic purity, but worse economics than `V_A` |
| `V_D` | Phase 3 / 4 | `cap = 1 per cluster`; first aftermath entry `size = 2.0x`; distinct cluster may re-arm | Replace same-cluster 2nd trade with oversized first entry | Tested | Looks best on raw PnL, but Phase 4 shows it is leverage drag |
| `V_E` | Phase 4 | same logic as `V_D`, but first aftermath entry `size = 1.5x` | Midpoint on the sizing curve | Tested | Capital efficiency below baseline |
| `V_F` | Phase 4 candidate | conditional `2.0x`: size up only when cluster quality is strong enough; otherwise stay `1.0x` | Search for a conditional smart edge between `1x` and `2x` | Candidate only | Discussed, not formally implemented |
| `V_G` | Phase 4 | `V_D` rules, but if current-day `VIX >= disaster threshold` then downgrade `2.0x -> 1.0x` | Keep first-entry upsizing but cap disaster-window leverage | Tested | Cleanest doubler, but still below `V_A` on marginal efficiency |
| `V_H` | Phase 4 | keep `V_A cap = 2`; same-cluster 2nd entry allowed only if VIX has not bounced | Split-entry / no-bounce gate | Tested | Effectively `V_A - 1 trade`; not a real independent alpha source |
| `V_I` | Phase 4 candidate | `V_D + total IC_HV BP cap` | Add portfolio-level BP ceiling to first-entry doubler | Candidate only | Discussed, not separately formalized |
| `V_J` | Phase 4 | first entry `2.0x`; but if any `IC_HV` already open, downgrade to `1.0x`; same-cluster 2nd entry blocked | No-overlap version of `V_D` | Tested | Confirms much of `V_D` uplift came from overlapping leverage |
| `V_K` | Phase 4 candidate | no new rule; recent-era-only validation of `V_D` | Check if `V_D` is only a modern-era phenomenon | Candidate only | Covered conceptually by recent-slice analysis, not as standalone implementation |

## Phase 2 Result Snapshot

Source: [doc/q021_phase2_full_engine_2026-04-25.md](/Users/lienchen/Documents/workspace/SPX_strat/doc/q021_phase2_full_engine_2026-04-25.md)

### System-Level

| Variant | n trades | Total PnL | Sharpe | MaxDD | MaxConc IC_HV |
|---|---:|---:|---:|---:|---:|
| `V0 baseline` | 404 | +400,734 | 0.41 | -13,213 | 2 |
| `V1 spec066` | 400 | +403,850 | 0.42 | -10,323 | 2 |
| `V2 pm_intent` | 405 | +404,793 | 0.41 | -12,617 | 6 |
| `V3 pm_intent+cap2` | 389 | +395,643 | 0.41 | -10,323 | 2 |

### Key Takeaway

- `V2` proves the PM semantic intuition can capture the second 2026-03 peak, but it does so with unacceptable concurrency.
- `V3` restores risk discipline, but loses materially versus `V1`.
- Phase 2 recommendation: keep `SPEC-066`, record the semantic deviation, do not open a new draft spec.

## Phase 3 Result Snapshot

Source: [doc/q021_phase3_half_size_2026-04-25.md](/Users/lienchen/Documents/workspace/SPX_strat/doc/q021_phase3_half_size_2026-04-25.md)

### System-Level Full Sample

| Variant | n | Total PnL | Sharpe | MaxDD | Delta vs `V_A` | MaxConc IC_HV |
|---|---:|---:|---:|---:|---:|---:|
| `V_A SPEC-066` | 400 | +403,850 | 0.42 | -10,323 | - | 2 |
| `V_B half-size` | 400 | +397,226 | 0.41 | -10,323 | -6,624 | 2 |
| `V_C distinct` | 389 | +395,643 | 0.41 | -10,323 | -8,207 | 2 |

### BP-Adjusted Snapshot

| Variant | PnL | BP-days | PnL/BP-day |
|---|---:|---:|---:|
| `V_A` | +403,850 | 83,201 | +4.8539 |
| `V_B` | +397,226 | 81,829 | +4.8543 |
| `V_C` | +395,643 | 81,703 | +4.8425 |

### Key Takeaway

- `V_B` does not create a better compromise; it is almost exactly a linear half-size version of the same-cluster 2nd-entry contribution.
- `V_C` improves semantic cleanliness, but not economics.
- Phase 3 temporarily reopened the question, but `V_A` remained the best operational baseline before Phase 4 widened the sizing study.

## Phase 4 Result Snapshot

Source: [doc/q021_phase4_sizing_curve_2026-04-26.md](/Users/lienchen/Documents/workspace/SPX_strat/doc/q021_phase4_sizing_curve_2026-04-26.md)

### System-Level Full Sample

| Variant | n | Total PnL | Sharpe | MaxDD | Delta vs `V_A` |
|---|---:|---:|---:|---:|---:|
| `V_A` | 400 | +403,850 | +0.42 | -10,323 | - |
| `V_D` | 394 | +431,673 | +0.45 | -9,749 | +27,823 |
| `V_E` | 394 | +414,173 | +0.43 | -10,036 | +10,323 |
| `V_J` | 394 | +414,394 | +0.43 | -9,749 | +10,544 |
| `V_H` | 399 | +401,976 | +0.42 | -10,323 | -1,874 |
| `V_G` | 394 | +418,372 | +0.43 | -9,749 | +14,522 |

### Standard Metrics Pack

| Variant | PnL/BP-day | Marginal $/BP-day vs `V_A` | Worst Trade | IC_HV CVaR 5% | Max BP% | Concurrent 2x Overlap Days |
|---|---:|---:|---:|---:|---:|---:|
| `V_A` | +4.85 | - | -8,564 | -2,383 | 14.0% | 0 |
| `V_D` | +4.72 | +3.37 | -8,564 | -2,580 | 42.0% | 27 |
| `V_E` | +4.76 | +2.70 | -8,564 | -2,580 | 31.5% | 27 |
| `V_J` | +4.78 | +2.98 | -8,564 | -2,580 | 28.0% | 0 |
| `V_H` | +4.84 | +24.34 (not comparable; effectively `V_A - 1 trade`) | -8,564 | -2,383 | 14.0% | 0 |
| `V_G` | +4.81 | +3.83 | -8,564 | -2,580 | 35.0% | 5 |

### Sizing-Curve Interpretation

The decisive Phase 4 finding is:

```text
V_A baseline capital efficiency = 4.85 PnL/BP-day

All sizing-up variants have marginal $/BP-day below 4.85:
  V_G = 3.83
  V_D = 3.37
  V_J = 2.98
  V_E = 2.70
```

That means:

- the full `[1x, 2x]` aftermath sizing curve has no smart-edge segment
- `V_D` is not a better rule, only a more levered rule
- `V_G` is the cleanest future-research note, but still not strong enough to promote

## Standard Metrics Pack Definition

This is the permanent comparison framework established after Q021 Phase 4. Future strategy / spec / variant / prototype comparisons should include the full pack, not only `PnL / Sharpe / MaxDD`.

| Metric | Definition | Why It Matters |
|---|---|---|
| `PnL/BP-day` | total PnL divided by BP-days consumed | base capital-efficiency measure |
| `Marginal $/BP-day` | incremental PnL divided by incremental BP-days vs baseline | distinguishes smart edge from pure leverage |
| `Worst Trade` | single worst realized trade PnL | catches concentrated tail blowups |
| `Disaster Window` | performance across designated stress windows | shows whether a variant survives regime stress |
| `Max BP%` | peak BP usage as a percent of account size | operational risk and deployability |
| `Concurrent 2x Days` | count of days spent in a doubled / overlap-amplified posture | shows how much extra leverage is actually being lived in |
| `CVaR 5%` | average of worst 5 percent tail outcomes | smoother tail-risk measure than one worst trade |

## Bottom Line

1. `V0-V3` answered the semantic question: does PM-style distinct-peak capture beat current production? Answer: no, not cleanly enough.
2. `V_A-V_G` answered the sizing question: does replacing same-cluster 2nd entry with larger first-entry sizing create a smarter rule? Answer: no.
3. The final Q021 synthesis is:
   - keep `SPEC-066`
   - do not open `SPEC-067`
   - record the semantic deviation
   - keep `V_G` only as a future research note

