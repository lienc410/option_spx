# Q083 P6 G-review 2 Packet — Final verdict on dual-gating audit

**From**: Quant Researcher (1st quant)
**To**: 2nd Quant Reviewer
**Re**: Q083 post-G1 reorientation complete. All 4 outstanding items (A1/A2/A3 direct diagnostics + D3 head-to-head + Q1 skew bracket + Q2 sensitivity/split + Q3 bootstrap CI) addressed. Verdict: SHADOW-TEST, not immediate SPEC.
**Date**: 2026-06-03

---

## TL;DR

You were right on every challenge. Q083 verdict pivots from "ship D3 SPEC" to "shadow-test IVP63 alongside current, no immediate replacement".

Three independent pieces of evidence converge on "evidence too weak for SPEC":
1. **Bootstrap CI** crosses zero for all designs' per-trade PnL
2. **Time-split** shows edge concentrated in 2013-2026 (not robust to first-half data)
3. **Skew bracket** (per your Q1 demand) pulls IVP63 Sortino from 0.878 → 0.379, below the 0.5 verdict threshold

BUT direct fact-finding (per your §4.A demand, replacing my P1 circular validation) DOES confirm PM's complaint:
1. **Pass rate**: 0.8% aggregate, 3-14% per VIX bucket — quantifies "几乎不放行"
2. **Lag**: median 23d alignment, 71-117d for major spikes (3-5 months back to normal IVP) — quantifies "spike 后 6-10 月不可交易" (PM overstated, real is 3-5 months for big spikes)
3. **Tail behavior of alternatives**: IVP63 disaster rate 0%, IVP252 9.1% — D3 alternatives are not worse-tailed than current

So PM's complaint mechanism is real, but the proposed fix doesn't pass robustness bar for SPEC. The right move is shadow-test.

---

## Specific answers to G1 questions

### Q1 (skew bracket — outstanding became completed)

**Done in P7** with proper per-leg pricing. Results above. Skew haircut -30%, Sortino drops below 0.5.

**Caveat**: My +5vp short-leg bump is approximate (real chain skew varies by VIX level + put-side delta). Worth ranging +3vp to +8vp for sensitivity. I picked +5vp as median historical chain skew in NORMAL VIX. Open to your guidance.

### Q2a (window sensitivity — smooth vs cliff)

P5 ran IVP40/60/63/90/126/180/252. Result is a SMOOTH gradient with "good zone" 60-126 and "bad zone" 180-252:

| Window | Sortino |
|---|---:|
| 40 | +0.041 |
| 60 | +0.968 |
| 63 | +0.878 |
| 90 | +0.354 |
| 126 | +0.666 |
| 180 | -0.344 |
| 252 | -0.012 |

Multi-point confirmation in each zone. Not a cliff at one window. But the "U-shape" with peak at IVP60 is interesting — IVP40 also fails (too short → noisy strikes). So the answer isn't "shorter is always better" but "there's a sweet spot around 60-126".

### Q2b (time split — first half train, second half validate)

P5 split at 2013-03 (midpoint). Result: pattern is RECENT.

| Period | IVP63 Sortino | IVP126 Sortino | IVP252 Sortino |
|---|---:|---:|---:|
| 2000-2013 | +0.258 | +0.038 | +0.397 |
| 2013-2026 | +inf (small n) | +2.605 | -0.095 |

First half: IVP252 actually had BEST Sortino, just barely. Pattern doesn't generalize backward.

This is concerning — the recommended change is mostly justified by recent regime. **Caveat for verdict**.

### Q3 (block bootstrap CI — narrow tertile claim)

P5 ran block bootstrap (block_size=4) on all three designs:

| Design | Mean$ point | 95% CI Mean$ |
|---|---:|---|
| IVP63 | +$308 | **[-$38, +$547]** crosses zero |
| IVP126 | +$372 | **[-$189, +$698]** crosses zero |
| IVP252 | -$21 | **[-$252, +$942]** crosses zero |

**All three have mean-PnL CI crossing zero**. NONE is statistically significantly > 0 per-trade.

The original "IVP252 narrow-tertile gate is correct now" claim from P2 was based on circular validation (per your §3). The narrow-tertile CI from P5 also crosses zero, so even with the right framework, we cannot claim "gate is correctly protecting now" — only "gate is consistent with zero edge now".

PM operational implication: not enough evidence to ship a SPEC change in either direction.

---

## Updated verdict structure

### Confirmed (with direct evidence)

1. PM's complaint mechanism: IVP252 contamination is real, normal-VIX pass rate is structurally single-digit
2. Direction of D3 fix: shorter window (60-126) is consistently directionally better in 26y aggregate
3. Tail behavior: D3 alternatives have BETTER, not worse, disaster rate

### Not confirmed (or weakened by robustness checks)

1. Statistical significance of IVP63/126 edge: bootstrap CIs cross zero
2. Time-stability: edge concentrated post-2013
3. Skew-robustness: -30% haircut pulls Sortino below verdict threshold

### Recommended path

**Shadow-test IVP63 in parallel with IVP252 for 6-12 months**, do NOT replace.

Implementation:
- Add IVP63 + IVP126 readings to daily snapshot (free, observational)
- Log decisions: when IVP63-would-have-allowed but IVP252-blocked, record the would-be trade
- Track real fills (PM's actual brokerage trades) as ground truth
- After 6-12 months, real-chain PnL would inform SPEC

This buys us:
- Real-chain data (skew bracket no longer hypothetical)
- Recent regime data (resolves time-split concern)
- Tighter CI from longer sample
- No risk if D3 turns out poorly

---

## What I'd ask you to ratify

**Q-G2-1**: Is the shadow-test recommendation the right call given mixed evidence, or am I being status-quo biased again?

My honest read: this is NOT status-quo bias. The mechanism IS real (Fact 1-3 in §2 of P6 verdict). But the proposed SPEC parameter (IVP63 specifically) doesn't meet robustness bar. Shadow-test resolves this without committing to a specific window.

**Q-G2-2**: Is +5vp short-leg σ a reasonable skew bracket magnitude? Should I range +3/+5/+8?

**Q-G2-3**: PM offered a "3-fact checklist" — the 3 facts I documented are pass rate / lag / tail. Are these the right 3 facts to anchor PM's decision?

**Q-G2-4**: I added 2 new memory entries (`feedback_circular_metric_validation`, `feedback_stratum_cutpoint_overfit`) as you suggested. Anything else worth documenting from this round?

---

## Files for review
- `research/q083/q083_p3_metric_diagnostics.py` — A1 / A2 / A3 direct facts
- `research/q083/q083_p3a1_lag_per_spike.csv`, `q083_p3a2_pass_rate_by_vix.csv`
- `research/q083/q083_p4_d3_head_to_head.py` — D3 simulation
- `research/q083/q083_p4_d3_trades_compare.csv`, `q083_p4_d3_pass_rate_compare.csv`
- `research/q083/q083_p5_robustness.py` — Q2 sensitivity + time-split, Q3 bootstrap
- `research/q083/q083_p5_q2_window_sensitivity.csv`
- `research/q083/q083_p7_skew_bracket.py` — Q1 skew bracket
- `research/q083/q083_p7_skew_bracket.csv`
- `research/q083/q083_p6_final_verdict_2026-06-03.md` — full verdict
- `task/q083_p2_g1_2nd_quant_review_2026-06-03_Review.md` — your G1 (this packet replies to it)

---

## Reply format

`task/q083_p6_g2_2nd_quant_review_2026-06-XX_Review.md`. Q-G2-1 to Q-G2-4 ratify/challenge.

On ratification → I write Q083 close memo + shadow-test infrastructure design doc (separate task). No SPEC drafted.
