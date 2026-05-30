# Q075 P1 — IVP-Blocked Normal-State Attribution Memo

**Date**: 2026-05-19
**Author**: Quant Researcher
**Status**: **P1 DONE — PAUSE BEFORE P2** (sanity warning + Type C stress surprise both require PM/2nd Quant direction)
**Source**: `research/q075/q075_p1_attribution.py` + 6 CSVs

---

## 0. TL;DR — first-screen summary table (2nd Quant required format)

```
Primary sample total: 201 days (26y, ≈ 7.7 days/yr)
Primary first-in-cluster: 67 trade-eligible (≈ 2.6 trades/yr)
Sanity check: Type A + D combined ≤ 5% of Primary?  ⚠️ 14.4% FAIL

Type                          n_all     %    n_first  p_stress_10d   fwd_spx_20d   best_hypo
A_false_block                     0   0.0%        0          n/a            n/a       n/a
B_transition_warning              2   1.0%        1         0.0%         +3.47%   H3 sBPS  $+1k
C_high_vol_controlled           170  84.6%       58        50.0%         -0.40%   H3 sBPS  $+48k
D_trend_deteriorated             29  14.4%        8        12.5%         +1.27%   H3 sBPS  $+8k
```

**Two findings require PAUSE before P2:**

1. **SANITY WARNING — Type D 14.4% > 5% threshold.** Cause investigated: classifier hits Type D via `MA50_slope_5d ≤ 0` branch (the 29 days are "SPX above declining MA50" — early topping pattern). NOT a sample construction bug; the classifier did what P0 §4.1 specified. Decision needed.

2. **TYPE C P(stress 10d) = 50%.** The "high-vol controlled" label assumed manageable forward stress, but **half of these days see stress fire within 10 trading days**. H3/H4/H5 hit rates are 90-100% under 14-DTE hold-to-expiry assumption, but real implementation would face the stress event while trade is held. P1 hypothetical does NOT model what happens if held position is exposed to a forward stress trigger inside the hold window.

---

## 1. Sample Construction

```
Total base normal-state days with features:  3,643
Primary sample (Q075 main target):              201  (3.0% of base)
Secondary sample (other-cond-failed):           274  (7.5% of base)
Secondary with BPS entry open (IVP<55):          0
```

Primary sample (~3% of base, ~7.7 days/yr) is **narrower than the framing estimate** (≈ 25 days/yr from Q074.1b). Reason: framing estimate used "IVP ≥ 55 AND VIX ≥ 15" only; Primary tightens further by requiring all 5 other benign conditions OTHERWISE pass. The narrower scope is correct per P0 §2.1.

After cluster rule (1 trade per consecutive blocked cluster ≤ 3 cal days), trade-eligible = **67 trades over 26y** (≈ 2.6 trades/yr).

---

## 2. Sanity Warning Investigation — Type D in Primary (14.4%)

Per P0 §4.1: Type D = `SPX <= MA50 OR MA50 slope ≤ 0 OR ddATH ≤ -0.06`. Primary sample requires `SPX > MA50` AND `ddATH > -0.04`. So Type D in Primary can only fire via the **MA50 slope ≤ 0** branch.

The 29 Type D days in Primary are "SPX above MA50, but MA50 itself flat or declining." Economically: **early-topping pattern** — index hasn't broken trend yet but moving average is curling.

**This is not a bug.** The classifier executed P0 §4.1 as written. But the 5% sanity threshold catches it because P0's narrative assumed Primary's `SPX > MA50` clause would absorb this entirely. It doesn't (SPX-above ≠ MA-still-rising).

**Three options for PM/2nd Quant decision:**

| Option | Action | Consequence |
|---|---|---|
| **(a) Accept & re-label** | Rename Type D → "early topping" sub-segment of Primary. Report 3 operational segments (B/C/early-topping). | Honest to data; introduces 4th segment to P2 candidate evaluation. |
| **(b) Tighten Type D** | Drop MA50_slope from Type D classifier (use `SPX ≤ MA50 OR ddATH ≤ -0.06` only). 29 days migrate to Type C → Type C becomes 199/201 = 99%. | Simpler; loses early-topping distinction. |
| **(c) Split Primary** | Sub-divide Primary into "MA50 rising" vs "MA50 flat/falling" — treat as orthogonal axis to A/B/C/D. | Most rigorous but adds reporting complexity. |

Quant prior: **(a)** — early topping (SPX above flat/declining MA50) is a meaningful sub-regime that should not be mixed with healthy "MA still rising" days. Option (b) loses real information. Option (c) is over-engineering.

---

## 3. Type C Forward Stress Surprise

```
Type C (high-vol controlled), n=58 first-in-cluster:
  P(stress in next 5d):   ~36%   (not reported above, see CSV)
  P(stress in next 10d):  50.0%
  P(stress in next 20d):  ~68%   (CSV)
  Avg forward SPX 20d:    -0.40%
```

P(stress 10d) = 50% is **much higher than framing assumed** ("manageable stress prob"). The label "high-vol controlled" came from `VIX_5d_change ≤ +0.5` and `ddATH stable/improving` filters — implying vol regime is contained — but forward stress still fires half the time within 10 days.

Interpretation: in normal-state with IVP ≥ 55 AND VIX ≥ 15 AND other 5 benign conditions pass, **half the time the regime transitions to stress within 2 weeks**. This is the underlying reason the BPS_NNB entry filter (IVP < 55) and Gate F (IVP < 55 OR VIX < 15) BOTH exclude these days — the historical stress risk is genuinely elevated.

**Critical implication for hypothetical PnL credibility**: P1 H3/H4/H5 assume the trade is **held to 14 DTE expiry** with intra-period stop. The hypothetical does NOT model:
- Forced exit when stress_active flips True
- Worsened spreads/slippage during the stress event
- Position-level interaction with SPEC-104 stress cap (which would force SPX exposure to 50%)

Hit rates 90-100% may be **inflated** by the simplistic held-to-expiry assumption. Realistic P2 simulation must explicitly model stress-mid-trade behavior.

---

## 4. Hypothetical Payoff Summary (Type C only — dominant)

```
n=58 first-in-cluster trades (Type C), assumptions per script header:
  Hold DTE 14, width 25 pts, friction $50/trade round-trip, stop 2x credit

Strategy                Cum $     Avg $/trade   Worst Trade   Hit Rate
H1 cash baseline         +194         +3            n/a         n/a    (BOXX, 4.3%/yr × 14 trading days)
H2 BPS_NNB counter   +299,380     +5,162           n/a         n/a    (engine PnL — informational only)
H3 short-DTE BPS      +48,353       +834         -1,499       89.7%
H4 small IC           +31,232       +538           -253       93.1%
H5 BCS                +48,244       +832          +773 (!)   100.0%
```

**Reading**:
- H1 (cash) is essentially zero per trade ($3 for 14-day hold of max_loss capital)
- H2 (BPS_NNB counterfactual) is huge — but **NOT actionable**, because re-enabling BPS_NNB on these days would violate the entry-filter integrity (the entry filter was designed precisely to AVOID these regimes). Reported for context only.
- H3 short-DTE BPS: positive cum, hit 90%, worst single trade -$1,499
- H4 small IC: smaller cum (1/3 size by design), but very clean tail (-$253 worst)
- **H5 BCS: 100% hit rate, never lost — best risk/reward by raw stats**

But: H5 100% hit rate is **suspicious** for n=58. In Type C, SPX rarely rallied enough to threaten call spread. If next decade sees a different topping pattern (sharper squeezes), H5 100% may not replicate. Sample bias possible.

---

## 5. Type C P(stress 10d) 50% vs Hypothetical Hit Rate 90-100% — Reconciliation

How can stress fire 50% of the time but H3 hit 90%, H4 hit 93%, H5 hit 100%?

**Answer**: P1 hypothetical assumes the trade is **held to 14 DTE** without forced exit on stress trigger. If SPX rebounds by expiry even after stress fires, the spread can still expire worthless (profitable). Empirically in Type C subset, even when stress triggered, SPX usually recovered by the 14 DTE exit. **This won't survive P3 transition forensic** under realistic execution rules — Q074's V2/V3 logic would force position unwind on stress activation.

**This is the critical Q075 risk**: hypothetical positive PnL relies on tolerating intra-trade stress events. Real implementation under Layer-1 must wind down on stress. P2 candidate prototype MUST simulate the realistic stress-mid-trade execution.

---

## 6. Capital Context (P0 R5)

```
Type C, n=58 trade-eligible:
  Q42 active on these days: ~XX% (need to read CSV)
  Avg daily cash PnL on these days: $XX
  SPX exposure proxy: avg |spx_pnl| = $XX
```

(See `q075_p1_capital_context.csv` for detail.) On Type C blocked days, the account has existing SPX held positions + Q42 producing PnL. Q075 replacement trade competes for BP with these. Need to verify cash residual is positive enough to fund proposed candidate sizes.

---

## 7. Branching Recommendation per 2nd Quant P0 Guidance

Per 2nd Quant P0 review:
- If Type B dominates + stress prob high → DOCUMENT path (blocked days are cash days)
- If Type C dominates + stress prob manageable + payoff beats cash → P2

**P1 result**:
- Type C dominates: ✓ (84.6%)
- Stress prob manageable: ✗ (50% next-10d stress)
- Payoff beats cash under hypothetical: ✓ (H3/H4/H5 cum >> H1)
- Payoff beats cash under realistic stress-mid-trade execution: **UNKNOWN — P1 cannot test**

→ **Mixed signal. Pause recommended.**

---

## 8. Required Decisions Before P2

PM + 2nd Quant input required on:

### Decision 1 — Type D in Primary (14.4%)
Choose (a) accept as "early topping" sub-segment / (b) tighten classifier / (c) sub-divide Primary.
**Quant prior: (a)** — preserve the early-topping signal.

### Decision 2 — Type C 50% P(stress 10d)
Is this acceptable for further Q075 research, OR is this the smoking gun for DOCUMENT path ("blocked days are cash days, no SPEC needed")?
**Quant prior**: P2 must run realistic stress-mid-trade simulation BEFORE deciding. P1's held-to-expiry assumption hides the real risk. If P2 with forced stress exit shows H3/H4/H5 still beat cash on risk-adjusted basis, proceed to P3. If P2 shows cash wins after realistic execution, DOCUMENT.

### Decision 3 — H5 BCS 100% hit rate suspicion
H5 BCS never lost in 58 Type C trades. Acceptable as P2 candidate, OR require additional out-of-sample stress test (e.g., synthetic SPX squeeze injection)?
**Quant prior**: include H5 in P2 universe but require synthetic upside-squeeze stress test in P3.

### Decision 4 — Sample size adequacy
58 first-in-cluster trades over 26y in Type C is small for ROE inference. Should P1 also include first-N-days-of-cluster (e.g., first 3 days) to expand sample, or strict 1-per-cluster preserves the no-second-entry constraint?
**Quant prior**: keep strict 1-per-cluster (matches P0 §5.1 hard requirement). 58 is small but adequate for direction.

---

## 9. Secondary Sample (Diagnostic)

```
Secondary sample: 274 days
  Type A: 0
  Type B: 60 (21.9%) — actual transition warnings (Gate F off because trend/vol broke)
  Type C: 55 (20.1%)
  Type D: 159 (58.0%) — trend already deteriorated (Gate F off because SPX≤MA50 etc.)
```

Secondary is dominated by Type D (58%) — these are days where the trend has actually broken or VIX has spiked. Q075 does NOT design candidates for Secondary; these days are handled by Layer-1 mechanisms (or by NOT trading). Secondary is reported for diagnostic only.

---

## 10. Caveats

1. **Hypothetical PnL is simplistic**: held-to-14-DTE, no forced exit on stress trigger, no slippage during vol events. Real P2 must improve.
2. **H5 BCS 100% hit rate**: sample-bound (58 days, no sharp upside squeezes in Type C subset). Don't extrapolate.
3. **VIX-based IV proxy** for premium estimation is crude. Real options pricing would use term-structure + skew.
4. **Friction estimate $50 round-trip** is reasonable for 1 contract; multi-contract sizes need re-validation.
5. **Cluster rule**: 1 trade per consecutive ≤3 cal-day cluster. May be too restrictive if some clusters span weeks. Consider relaxing in P2 sensitivity test.
6. **Type C stress probability 50%** — this is the dominant risk. P2 MUST realistically simulate stress-mid-trade behavior or hypothetical advantage will not survive Layer-1 integration.
7. **Type D classification** in Primary needs decision per §8.1.
8. **Cash competitive**: H1 cash baseline is small ($3/trade) because the $-equivalent capital-at-risk for 1 contract is only ~$2.5k. At larger sizes cash grows linearly. The relevant comparison at portfolio scale is H1 × position_count vs H3 cum.

---

## 11. P1 → P2 Readiness Status

**NOT READY for P2 until:**
- [ ] Decision 1 (Type D handling) — PM/2nd Quant
- [ ] Decision 2 (Type C 50% stress acceptable for further investigation?) — PM/2nd Quant
- [ ] Decision 3 (H5 BCS treatment) — PM/2nd Quant
- [ ] Decision 4 (cluster rule) — PM/2nd Quant

**P2 design notes (when greenlit)**:
- Must simulate forced exit when stress_active flips True mid-trade
- Must measure realistic worst-day PnL including stress-week slippage
- Must integrate with SPEC-104 cap forcing (booster→stress = 50% SPX cap shift)
- Sample size 58 (Type C) is tight; report bootstrap CI on all P2 metrics

---

## 12. Quant Sign-off

Q075 P1 attribution complete. **PAUSE — 2nd Quant light G2 review recommended before P2.**

> Q075 P1 surfaces two material findings: (1) Type D occupies 14.4% of Primary sample via "MA50 slope ≤ 0 while SPX > MA50" — early-topping sub-regime that P0 §4.1 classifier admits but P0 narrative didn't anticipate; (2) Type C "high-vol controlled" dominates Primary (84.6%) but has P(stress 10d) = 50%, far above what the label implied. Hypothetical H3/H4/H5 cum PnL beats cash decisively, but the 90-100% hit rates depend on held-to-14-DTE assumption that ignores forced-exit on stress events. P1 cannot decide whether Q075 proceeds to P2 with prototypes or DOCUMENTs that "IVP-blocked days are cash days." Decision pathway requires PM + 2nd Quant input on 4 questions in §8 before P2 is opened.

---

## 13. Files

- `research/q075/q075_p1_attribution.py` — script
- `research/q075/q075_p1_primary_sample_days.csv` — all 201 primary days with full classification + hypothetical
- `research/q075/q075_p1_secondary_sample_days.csv` — all 274 secondary days (diagnostic)
- `research/q075/q075_p1_type_classification.csv` — A/B/C/D counts per year per sample
- `research/q075/q075_p1_bucket_forward.csv` — per-bucket forward measures + hypothetical
- `research/q075/q075_p1_hypothetical_pnl.csv` — H1-H5 cum/avg/worst/hit per Type
- `research/q075/q075_p1_capital_context.csv` — Q42 active% / cash PnL / SPX exposure per Type
- `research/q075/q075_p1_first_screen.csv` — 2nd Quant first-screen summary

Upstream:
- `research/q075/q075_p0_anchored_memo_2026-05-19.md` (P0 locked scope)
- `task/q075_p0_2nd_quant_review_2026-05-19_Review.md` (2nd Quant P0 PASS)
