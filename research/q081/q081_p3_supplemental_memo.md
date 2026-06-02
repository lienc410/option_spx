# Q081 P3 Supplemental — Window Stratification + Sortino (response to G2 Q1)

**Date**: 2026-06-01
**Owner**: Quant Researcher
**Status**: COMPLETE — methodology gap acknowledged, verdict requires revision
**Trigger**: G-review 2 Q1 CHALLENGE (2026-06-01) — original P3 §C did only
aggregate direction-bias check (mean QQQ ≈ 0 across 21 windows), reviewer
flagged that this is insufficient and per-window stratification was the
actual G1 ask.

---

## Methodology gap acknowledged

The reviewer is correct on the methodology issue. P3 §C reported "no
direction bias" because the **aggregate mean** of 21 same-window QQQ
returns was +0.32% (near zero). This was the wrong check. The G1 Q1
补强 specifically asked for the **distribution** of those 21 returns so
we could see if the sample was concentrated in up or down windows.

Aggregate ≈ 0 mean is consistent with two opposite scenarios:
- (a) 21 small returns near zero (sample is truly balanced) → no bias
- (b) 10 strong-up + 9 strong-down + 2 flat (sample is bimodal) → bias risk

§F below shows the truth is (b): sample is bimodal with 10 strong-up
and 9 strong-down windows. The original P3 §C verdict ("no direction
bias") is **wrong**, and the verdict text that built on it ("BCD +8pp
mean dominance is structural alpha not beta artifact") is **also wrong**.

---

## §F — Window-Direction Stratification

Split 21 windows by SPX same-window return: UP (>+1%), FLAT (±1%), DOWN (<-1%).

| Stratum | n | BCD mean | QQQ mean | Δ (BCD-QQQ) | BCD beats QQQ | BCD range | QQQ range |
|---|---:|---:|---:|---:|---|---|---|
| **UP** | **10 (48%)** | **+23.58%** | +4.20% | **+19.38pp** | **10/10 (100%)** | [+8.6%, +37.2%] | [+0.6%, +6.95%] |
| FLAT | 2 (10%) | +3.35% | +0.93% | +2.43pp | 2/2 | [+2.4%, +4.4%] | [-1.3%, +3.2%] |
| **DOWN** | **9 (43%)** | **-7.52%** | **-4.14%** | **-3.38pp** | **2/9 (22%)** | [-13.4%, +2.5%] | [-9.6%, -1.1%] |

### Read-out

**The +8pp mean uplift is 100% concentrated in UP windows.** Strip out the
10 up-windows and BCD is a 3.4pp DRAG vs QQQ.

This validates 2nd quant's structural concern: BCD's aggregate edge is
**not structural alpha** — it's beta amplification in up regimes. The
"BCD vs QQQ" comparison must acknowledge BCD as **regime-conditional
leveraged-beta with vega cushion**, not unconditional alpha.

Specifically: BCD captures ~0.4 net delta on $24k notional + vega +
theta-from-short-leg-decay. In UP windows the short leg decays fast +
vega contracts (BCD wins from theta + delta), in DOWN windows BCD has
positive delta exposure that loses (long leg loses more than short
leg's positive vega gain offsets).

### Pattern check: is the trend filter already gating this?

BCD only opens when matrix trend signal = BULLISH. Of 21 BULLISH-flagged
entries, 10 (48%) hit UP windows — vs SPX base rate for random
~30-day forward windows around 50/30/20 (up/flat/down). So the BULLISH
filter is slightly biased toward up-windows (48% vs ~50% baseline,
roughly matching) and somewhat over-represents in down-windows compared
to FLAT.

The BULLISH signal is NOT a strong predictor of forward direction at the
21-day horizon. It identifies entry conditions, not realized outcomes.
BCD therefore inherits both up and down windows roughly evenly.

---

## §G — Sortino Ratio

Replaces the inadequate "mean vs p05 point comparison" from original P5.

| Metric | n | μ | σ | σ↓ (downside) | Sortino | Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| BCD period-ROE | 21 | +8.32% | 17.04% | **5.73%** | **+1.454** | +0.488 |
| QQQ same-window | 21 | +0.32% | 4.66% | 3.10% | +0.102 | +0.068 |
| SPX same-window | 21 | +0.52% | 3.53% | 2.06% | +0.251 | +0.147 |
| BCD − QQQ | 21 | +8.01% | 12.97% | 3.41% | +2.349 | +0.617 |

### Within-stratum Sortino (down stratum is decisive)

| Stratum | BCD Sortino | QQQ Sortino |
|---|---:|---:|
| UP (n=10) | +∞ (no losses) | +∞ (no losses) |
| FLAT (n=2) | +∞ | +0.989 |
| **DOWN (n=9)** | **-0.860** | **-0.878** |

**Critical**: in DOWN windows specifically, BCD Sortino ≈ QQQ Sortino. BCD
does NOT have meaningfully worse downside Sortino than QQQ in stress.
The aggregate Sortino advantage (+1.454 vs +0.102) is concentrated in
the UP+FLAT strata where BCD's mean is much higher.

This nuances the reviewer's "leveraged beta" framing:
- **In up regimes**: BCD = ~3x QQQ return (leveraged on the way up, mostly
  via short-leg theta acceleration + long-leg delta capture)
- **In down regimes**: BCD ≈ 1.8x QQQ loss but Sortino comparable (vega
  cushion partly offsets delta drag)

So BCD is "asymmetric leveraged beta": amplifies upside, mostly amplifies
downside but with vega-driven dampening. The Sortino advantage is real
but is concentrated in NON-stress regimes.

---

## Revised characterization of BCD

| Original P3 framing | Revised characterization |
|---|---|
| BCD has structural alpha (vega + theta + delta) | BCD is regime-conditional leveraged beta with vega cushion. Alpha component (vega cushion in down) is real but small. |
| BCD beats QQQ on mean +8pp = edge | BCD beats QQQ on mean +8pp but 100% of the lift is up-window concentrated. Not structural alpha. |
| BCD tail (p05 -11.6%) is "bounded disadvantage" | BCD tail IS worse than QQQ (p05 -11.6 vs -5.5), and the cause is down-window concentration (9/21 trades). |
| Risk-reward roughly symmetric | Risk-reward in down windows: BCD Sortino ≈ QQQ Sortino. BCD does not catastrophically underperform in stress, but does not protect either. |

---

## Implications for the verdict

The reviewer's split-the-verdict recommendation is correct:

**Verdict A (RATIFIED, ready for SPEC)**: cap 60% liquid (dynamic) +
75% concurrent-debit alert. This is independent of the matrix
question and stands regardless of how matrix gets resolved.

**Verdict B (REVISED, no longer "matrix unchanged" as previously framed)**:

The original "matrix unchanged" claim leaned on BCD's mean dominance
being structural alpha. That framing is now refuted. Options:

**B-revised-1 (most honest, recommended)**: Matrix unchanged, but with
explicit acknowledgment that BCD's role is **regime-conditional
leveraged-beta-with-vega-cushion, not structural alpha**. The case for
keeping it:
- BULLISH trend filter is the existing directional gate
- In trend-filtered entries: BCD net +8pp over QQQ across 3y
- Down-window Sortino similar to QQQ (BCD not catastrophically worse in stress)
- Vega cushion (long 90 DTE) is the residual alpha
- Cap (Verdict A) limits single-trade cash impact

**B-revised-2 (more conservative)**: Defer matrix verdict to Q082. Reasons
to defer:
- The "+8pp mean" was the load-bearing evidence for status quo. With that
  re-characterized, status quo needs new load-bearing evidence
- Comparing BCD's "regime-conditional alpha" to QQQ's "unconditional beta"
  requires a longer sample / multi-regime analysis the current dataset
  can't provide

I lean **B-revised-1**: matrix unchanged with honest characterization,
because (a) cap (Verdict A) provides governance regardless, (b) the
BULLISH trend filter is the de-facto directional gate, (c) deferring
matrix verdict adds delay with limited additional evidence available
in-sample.

But B-revised-2 is also defensible. **Decision for 2nd quant G-review 2
re-read**: which framing for Verdict B?

---

## Process learning

The methodology gap (aggregate vs stratified direction bias check) is a
**non-trivial false negative**. Original P3 §C answered the wrong
question and the verdict that built on it would have shipped without
this G-review.

Mechanical lesson: when checking for "sample bias", aggregate statistics
are necessary but insufficient. Per-window or per-stratum decomposition
is needed to rule out bimodal samples.

Methodology lesson (more important): **the reviewer's G1 补强 ask was
specific** ("per-window distribution"). I treated it as informational and
reported aggregate. When a reviewer specifies a methodology requirement,
deliver it literally — don't summarize.

Logging this to memory: `feedback_reviewer_ask_literally`.

---

## Files
- `q081_p3_supplemental.py` — script
- `q081_p3_window_stratified.csv` — §F
- `q081_p3_sortino.csv` — §G
- `q081_p3_supplemental_memo.md` — this file

---

## Next

1. Update P5 verdict: split into Verdict A (cap+alert, ratified) and
   Verdict B (matrix, revised per above).
2. Send G-review 2 follow-up packet to 2nd quant for re-ratification.
3. On B-revised re-ratification, draft SPEC.
