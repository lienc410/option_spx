# Q083 P2 G-review 1 Packet — Dual-Gating Audit Verdict Signal

**From**: Quant Researcher (1st quant)
**To**: 2nd Quant Reviewer
**Subject**: Q083 P0+P1+P1b complete, verdict signal H3 (regime-conditional). Methodology + verdict ratification needed before P3 or SPEC.
**Date**: 2026-06-03

---

## Short version

PM's "dual gate" framing turned out wrong, but the underlying complaint was directionally right. Three findings:

1. **State (b) = 0 across 26y** — IVR-cell-routing and IVP gate are nested, not dual. Single binding constraint is IVP gate.

2. **Counterfactual evidence supports H3 (regime-conditional over-restriction)** at 252d range width ≥ 30 VIX-points:
   - State (a) [PM's current pain pattern]: narrow-tertile (range < 22) mean -$16 Sortino -0.02; **wide-tertile (range ≥ 30) mean +$279 Sortino 0.549**
   - State (c) [IVP too high]: similar pattern with wide-tertile materially positive
   - Gradient: narrow → mid → wide, monotonically increasing edge

3. **PM's current state isn't in the broken regime**. Current 252d range = 17.58 (narrow tertile). Counterfactual mean is zero with downside risk. Gate is correctly protective NOW. The H3 over-restriction only bites when range ≥ 30 (historical: post-2008, post-2020 March, post-2022 declines).

---

## Verdict candidate

**Recommend**: SPEC for regime-conditioned IVP gate. When 252d range ≥ 30 VIX points, relax IVP_LOW from 40 to ~25 for state (a) days; keep BPS_NNB band relaxed similarly. Below range threshold, current gate stands.

But **don't commit to SPEC yet** — your G1 ratification needed first.

---

## Specific questions

### Q1 — Methodology validity

- BS-flat IV synth (same as Q082) — adequate for relative tertile comparison?
- 30 DTE entry / 21 DTE roll / 60% profit target / 2× credit stop — adequate exit model?
- n=1022 (state a) + n=357 (state c) — adequate sample size for tertile-level claims?

### Q2 — H3 vs H1 (mostly H3 in narrow tertile)

The aggregate result for state (a) is Sharpe 0.18 (≈ H1 threshold). Only when stratified by 252d range does H3 emerge clearly. Is this a legitimate H3, or a "fishing for stratum that works" risk?

My view: the regime variable (252d range width) was hypothesis-driven (from framing memo H3 statement), not data-mined post-hoc. So stratification is legitimate. But you should check.

### Q3 — Is "PM's current pain isn't in broken regime" honest, or status-quo bias?

This is the tricky part. Per memory `feedback_status_quo_bias_in_verdicts`, I'm supposed to be skeptical of "status quo OK" conclusions. Here I'm saying:
- (Wide regime): gate is wrong → SPEC needed
- (Narrow regime, PM's current state): gate is right → no immediate help

Is the narrow-regime conclusion robust? Block-bootstrap CI on narrow-tertile Sortino would help confirm.

### Q4 — Should I run P3 (alternative gate design simulation)?

Framing memo §3 P3 step said "simulate 4 alternative designs over 26y." Specifically:
- D1: Drop IVP gate, rely on IVR cell only — but P0 shows state (b)=0 so this is equivalent to dropping nothing (IVR never independently allows when IVP blocks)
- D2: Drop IVR routing, use IVP only — equivalent to current since they're nested
- D3: Use IVP63 (shorter lookback) instead of IVP252
- D4: Regime-conditioned (the H3 SPEC candidate)

D1/D2 are moot per P0. Worth running D3 + D4 simulation? Or go straight to SPEC for D4 (H3 candidate)?

### Q5 — Anything I'm missing?

Pattern from Q081/Q082: I tend to converge to "no major change needed" on ambiguous evidence. This time the data forces a SPEC for one regime (wide) but maintains status quo for another (narrow). Is the partition itself a self-serving compromise, or actual finding?

---

## Reply format

`task/q083_p2_g1_2nd_quant_review_2026-06-XX_Review.md`. Q1-Q5 ratify/challenge.

On ratify → either run P3 (D3/D4 simulation) OR draft SPEC for D4 regime-conditioned gate.

Estimated reply window: 24-48h.

---

## Files attached
- `research/q083/q083_p0_state_assignments.csv` (per-day classification)
- `research/q083/q083_p0_state_counts.csv` (per-year summary)
- `research/q083/q083_p1_counterfactual_trades.csv` (state c, n=357)
- `research/q083/q083_p1_stratified.csv`
- `research/q083/q083_p1b_state_a_trades.csv` (state a, n=1022)
- `research/q083/q083_p1b_state_a_stratified.csv`
- `research/q083/q083_p2_verdict_signal_2026-06-03.md` (full verdict signal)
