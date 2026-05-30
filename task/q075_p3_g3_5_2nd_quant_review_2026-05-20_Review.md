# Q075 P3 — 2nd Quant Light Review (G3.5 Waived)

**Reviewer**: 2nd Quant
**Date**: 2026-05-20
**Source**: `research/q075/q075_p3_memo.md`
**Verdict**: **PASS — G3.5 waived. Proceed directly to P4.**

---

## Final verdict statement

> P3 accepted. Use P3 refactored mark model as authoritative. Advance only IC w25 and IC w35 to P4. Reject IC w15, BCS, and C2. P4 should determine whether the IC overlay adds +0.05-0.20pp / +0.20pp ROE without degrading worst-20d / worst-63d by more than 0.25pp and without creating capital competition with SPX / Q042. No G3.5 required.

---

## P3 → P4 advancement

| Candidate | Status | Rationale |
|---|---|---|
| **IC w25** | **PRIMARY → P4** | Survives Probes A/B/Mild C/Base C/D; balanced credit cushion |
| **IC w35** | **ALTERNATIVE → P4** | Same probes pass; larger absolute PnL; capital cost ↑ proportionally |
| IC w15 | REJECTED | Fails Mild downside shock — thin credit cushion |
| BCS | REJECTED | 4/4 melt-up analogs fail (-$107k to -$131k cum); P2 100% hit was sample-bound |
| C2 sBPS | REJECTED | P3 refactored model shows negative cum (-$5k); confirms P2 mark accounting was lenient |

---

## Key acknowledgments

1. **P3 mark model is the new standard** — P2's simpler formula systematically overstated PnL when SPX above short strike at stress trigger. Going forward (Q07X+), use `mtm_at()` style.
2. **IC's Severe shock failure** is explainable — Severe (-5%/10d + IV+40% + skew+20%) bypasses SPEC-104 stress intervention by design. In production, dd_20d ≤ -4% trigger would activate before Severe completes. P4 must verify with realistic SPEC-104 interaction.
3. **No more analog testing required for IC** — Probe C 3-tier shocks are sufficient to characterize IC's downside profile; further analog injection would not change conclusions.

---

## P4 scope (locked)

```
Candidates: IC w25 (primary), IC w35 (alternative)
Excluded:   IC w15, BCS, C2, calendar/diagonal, multi-entry cluster

Required metrics:
  ΔROE vs SPEC-104 + SPEC-105 v2 baseline
  MaxDD (V1 ≥ -28%)
  Worst 20d (V2 ≥ -11%)
  Worst 63d (V3 ≥ -17%)
  Sharpe
  Capital competition with SPX / Q042 (BP-day consumption)
  Correlation with existing sleeves
  Crisis window behavior (5 named windows)
  Bootstrap (block=250, 20 seeds)
  Walk-forward H1 / H2
  Operational burden

Special table required:
  IC overlay active during stress-adjacent periods:
    entry count
    forced-exit count
    cumulative PnL
    worst 20d contribution
  (Because Q075's core concern is stress-front-edge behavior)

Promotion bar:
  Strong:  ΔROE ≥ +0.20pp + ALL risk thresholds pass
  Soft:    +0.05 to +0.20pp + ALL risk thresholds pass
  Reject:  < +0.05pp OR any risk threshold fail

Risk thresholds (mandatory for any promotion):
  Worst 20d degradation ≤ +0.25pp vs baseline
  Worst 63d degradation ≤ +0.25pp vs baseline
  No new crisis-window failure
  No capital competition with SPX / Q042 safety reserve
```

---

## 2nd Quant Sign-off

- [x] G3.5 waived
- [x] P3 mark model authoritative
- [x] IC w25 primary + IC w35 alternative → P4
- [x] BCS / C2 / IC w15 rejected (final)
- [x] P4 scope locked
- [x] Stress-adjacent period special table required
- [x] No additional research blockers

→ Quant proceeds to draft Q075 P4 portfolio integration.
