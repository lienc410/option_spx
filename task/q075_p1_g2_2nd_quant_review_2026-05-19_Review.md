# Q075 P1 G2 — 2nd Quant Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-19
**Source**: `research/q075/q075_p1_attribution_memo.md`
**Verdict**: **PASS TO LIMITED P2** — not full P2; constrained scope with forced-exit simulation requirement

---

## Final verdict statement

> Q075 P1 passes G2 as an attribution study. It does not support broad strategy promotion. It supports a limited P2 focused on whether small IC or BCS can survive realistic stress-mid-trade execution. Cash remains the default unless forced-exit P2 proves otherwise.

---

## Required Type C rename

```diff
- Type C: high-vol controlled
+ Type C: Elevated-IV pre-stress controlled  (alt: "Controlled but fragile")
```

Reason: P1 measured P(stress 10d) = 50%. The "controlled" label was too optimistic. Apply rename across P0 + P1 memos and forward documentation.

---

## 4 decisions — 2nd Quant answers

| Decision | Answer |
|---|---|
| D1 Type D handling | **Keep as early-topping sub-segment**, do NOT merge into C |
| D2 Type C 50% stress | **Proceed to limited P2 with forced stress exit**; do NOT DOCUMENT yet |
| D3 H5 BCS treatment | **Include in P2**; require synthetic upside squeeze stress test |
| D4 Cluster rule | **Keep strict 1-per-cluster** |

---

## P2 constrained scope

### Core candidates (full prototype)
- **C3 small IC** — best tail in P1 hypothetical (-$253 worst), neutral, defined-risk
- **C4 BCS** — best raw stats, avoids put-side exposure pre-stress, but suspicious 100% hit must be stress-tested

### Diagnostic only (NOT promotable from P2)
- **C2 low-delta short-DTE BPS** — structurally dangerous in 50% stress-within-10d regime; only retain if forced-exit simulation proves put side clean

### Excluded from P2
- **C5 calendar / diagonal** — P1 didn't support term-structure logic
- **multi-entry clusters** — keep strict 1/cluster per P0 §5.1

---

## P2 design requirements (mandatory)

### Entry rule
```
First-in-cluster Type C only
(Type B too few; Type D not a candidate regime; Type A empty)
```

### Exit logic — forced-exit-on-stress is the central requirement
```
Planned: exit at 14 DTE (or strategy-defined)
Forced: exit immediately when stress_active flips True
Forced: exit immediately when second_leg_active flips True
Stop: trade-level stop if breach happens before either above
```

### Cost model
```
Normal friction: ~$50 round-trip per defined-risk trade
Stress-exit slippage multiplier: TBD (Quant proposes 1.5-2x normal bid/ask)
Gap / spread widening on stress exit: model both vega + skew shift
```

### BCS-specific stress tests (required)
```
Synthetic upside squeeze: +2%, +3%, +5% SPX over 5-10d
VIX compression scenario (rapid IV crush + SPX rally)
Call spread mark-to-market loss under each
2019 / 2023 melt-up analog inclusion
```

### IC-specific stress tests
```
Both downside and upside breach scenarios
Stress-trigger forced exit
Wing width sensitivity (15 / 25 / 35 pt)
```

### BPS-diagnostic tests
```
Gap-down stress entry failure (overnight gap → strike breach at open)
Short-DTE gamma loss under VIX spike
Stress-exit slippage
```

---

## P2 pass/fail logic (before any P3 advancement)

Candidate must pass ALL of:
```
[1] Beats cash after forced stress exit (positive ΔROE vs C1 baseline)
[2] No material transition loss concentration (per P0 §8.2 thresholds)
[3] Worst single trade acceptable (≤ 1% NLV per trade)
[4] No new crisis-window failure (5 named windows, incremental ≥ -$2k)
[5] Reasonable trade count (≥ 30 over 26y for inference)
[6] Operationally simple (clear entry / exit / stop rules)
```

If NO candidate passes: **DOCUMENT** outcome — "IVP-blocked normal-state days are cash days."

If at least one passes: proceed to P3 transition forensic + P4 portfolio integration.

---

## 2nd Quant Sign-off

- [x] G2 PASS to limited P2
- [x] Type C rename required
- [x] 4 decisions answered
- [x] Constrained scope (IC + BCS core; sBPS diagnostic; calendar excluded)
- [x] Forced-exit on stress is non-negotiable
- [x] Synthetic upside squeeze required for BCS
- [x] DOCUMENT cash is valid endpoint if all candidates fail
- [x] No additional blockers

→ Quant proceeds to draft Q075 P2 constrained simulator.
