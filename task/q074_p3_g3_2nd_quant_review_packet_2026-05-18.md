# Q074 P3 — G3 Mid-Review Packet for 2nd Quant

**Date**: 2026-05-18
**Author**: Quant Researcher
**Reviewer**: 2nd Quant
**Type**: **G3 mid-review (mandatory per P0 §9)** — gate before P4 full validation
**Decision sought**: PASS / REVISE / REJECT P3 conclusions + P4 scope authorization

---

## 0. TL;DR

Q074 P3 transition-risk forensic returned **surprisingly clean** results across all 4 candidates:

| Cand | ΔROE | Worst single 10d loss | Cum incremental | 5/5 crisis positive? | P3 verdict |
|---|---|---|---|---|---|
| B1 strict 85 | +0.11pp | -0.03% NLV | +$70k | YES | clean, small ROE |
| B2 moderate 85 | +0.13pp | -0.07% NLV | +$107k | YES | clean |
| B3 strict 90 | +0.22pp | -0.06% NLV | +$141k | YES | clean, backup |
| **B4 moderate 90** | **+0.25pp** | **-0.15% NLV** | **+$214k** | **YES** | **leading** |

**All 4 candidates pass P3 transition test with significant buffer** (worst single loss < 0.15% NLV vs 2% NLV P0 threshold = 13x buffer).

**B4 is the leading candidate** because:
- Highest ROE upside (+0.25pp, closest to Strong pass +0.30pp threshold)
- Worst single loss only -0.15% NLV
- Cumulative incremental during transitions POSITIVE (+$214k over 26y)
- All 5 crisis events positive incremental
- VIX 20-22 inclusion (concern from P1) NOT a real loss driver

**Q074 elevated from Soft Pass to Strong Pass candidate** (pending P4 validation).

**Quant recommendation**: PASS G3, run P4 on B4 primary + B3 backup, skip P4 for B1/B2 (too small ROE for SPEC effort).

---

## 1. Why G3 review is mandatory

Per P0 §9 mid-review gates:
> **G3 P3 architecture review** (mandatory): Top 1-2 booster candidates identified, before P4 full simulation. P4 is compute-heavy and any methodology issue surfaced post-P4 wastes 2-3 days of work.

Q074 P3 produces a result that **deserves scrutiny before P4**:
- "Cumulative incremental POSITIVE during stress transitions" is counter-intuitive
- Worst single loss far below threshold (13x buffer) — could indicate methodology generosity

If 2nd Quant flags a methodology concern, fix before P4. If 2nd Quant PASSES, P4 runs on B4 + B3.

---

## 2. P3 Methodology

Per P0 §5 + 2nd Quant Revisions 2/3:

```
Primary transition window: 10 TD before stress trigger, booster active any day
Secondary diagnostic: 20 TD before stress trigger
Severity classification:
  mild  = stress trigger without second-leg next 20d
  acute = stress trigger AND second-leg next 20d
  failed-benign = booster active in window AND incremental PnL < 0
Incremental PnL = candidate booster-active-day PnL − B0 baseline same-day PnL
Crisis exam: 5 named events (DotCom / PreGFC / Vol 2018 / COVID / Bear 2022)
VIX 20-22 attribution for B2/B4
```

Stress trigger events identified in 26y: **2929 total**. Of these, transitions where booster was active in prior 10d:
- B1/B3 strict: 131 (4.5%)
- B2/B4 moderate: 171 (5.8%)

---

## 3. Six Questions for 2nd Quant

### Q1 — Is the "POSITIVE cumulative incremental during transitions" real, or methodological artifact?

Result: cumulative incremental PnL during booster-active transition windows is POSITIVE for all 4 candidates (+$70k to +$214k). Loss-only cumulative (subtracting only the negative transitions) is tiny (-$1.7k to -$9.3k over 26y).

**Possible explanations**:
- **(A) Real**: Multi-condition signal genuinely self-protective — booster turns OFF before stress fires, and on the few days where booster active in pre-stress window, the SPX BPS trade is still slightly profitable on average.
- **(B) Methodological generosity**: Incremental computed only on booster-active days (when booster ON), not full window. If booster turns OFF before stress fires, those OFF days don't count in our incremental tally. So we're measuring "ON-day-only" PnL contribution.

**Quant assessment**: (B) is technically true but (A) is the substantive finding. We DO want to know "what is the booster's contribution given that it was ON" — that's the proper P3 question. Off-day PnL is the Arch-3 baseline, which is the comparison.

**2nd Quant: confirm methodology valid?**

### Q2 — Is failed-benign sample (41-43 events / 26y) sufficient for statistical confidence?

41-43 events ~ 1.6 events/year. Bootstrap (in P4) will test distributional stability, but the underlying sample is sparse.

**Concern**: If we're estimating P(failed-benign | booster active) from 131-171 booster-present transitions and 41-43 failed-benign outcomes, that's ~25-30% failed rate. Per-event tiny ($-281 to -$1,304 incremental) — but is the rate stable?

**2nd Quant: accept the sample size, or recommend additional resampling?**

### Q3 — Worst single loss -0.15% NLV vs 2% threshold (13x buffer) — too good?

**Concern**: A 13x buffer suggests either:
- (A) Q074 design is genuinely conservative (signal definition tight enough)
- (B) Friction model undercounts margin cost when booster at 90% pushes cash < 0
- (C) Backtest doesn't capture realistic execution slippage during stress periods

P4 friction sensitivity ±50% will partly address (B). Synthetic stress injection in P4 will partly address (C).

**2nd Quant: are there additional stress scenarios we should add to P4 to challenge the 0.15% number?**

### Q4 — VIX 20-22 surprise: B4 includes danger zone but produces positive incremental

P1 attribution: VIX 20-22 normal-state has 59% next-10d stress probability (highest of all VIX buckets).
P3 result: B4 (VIX < 22) cum incremental on transitions including VIX 20-22 days = +$47k POSITIVE.

**Hypothesis**: IVP < 55 filter is dominant. When VIX 20-22 + IVP < 55 simultaneously, premium is rich enough to overcome stress risk.

**Possible alternative**: VIX 20-22 days that also satisfy IVP<55 might be RARE (because high VIX usually means high IVP). The intersection may be small enough that statistical inference is weak.

**2nd Quant: does this need a deeper data slice (e.g., joint VIX×IVP×ddATH bucket within VIX 20-22 transitions)?**

### Q5 — Should P4 run B4 alone or B4 + B3 in parallel?

Quant proposal: **B4 primary + B3 backup**.

Rationale:
- B4 leading ROE, but if walk-forward (V7) shows ROE H1 < H2 disproportionately, B4 might be over-fit to recent regime
- B3 is conservative backup at +0.22pp (vs B4 +0.25pp). 0.03pp delta — easily within noise.
- Running both costs ~30% more P4 compute (single shared simulator + 2 candidate paths)

**2nd Quant: agree B4+B3 parallel? Or B4 alone, fall back to B3 only if B4 fails?**

### Q6 — Strong pass eligibility: B4 +0.25pp vs +0.30pp threshold

B4 ΔROE +0.25pp is below the +0.30pp Strong pass criterion.

**Quant proposal for P5**: If P4 bootstrap on B4 shows ROE std-error > 0.05pp, then the +0.25pp delta is statistically indistinguishable from +0.30pp threshold → argue Strong pass.

If P4 bootstrap is tight (e.g., ΔROE noise < 0.02pp), then +0.25pp is decidedly below +0.30pp → Soft pass only (paper/shadow).

**2nd Quant: support this approach, or require ΔROE ≥ +0.30pp strict regardless of bootstrap noise?**

---

## 4. Caveats Self-Disclosed

1. **DotCom 2000-03 + PreGFC 2007-07 booster fully OFF**: signals never activated within 20d pre-trigger. This is conservative design working but also means Q074 framework hasn't been tested in those specific transition profiles. Synthetic stress test in P4 should inject "missed signal" scenarios.

2. **VIX 20-22 sample = 33 transitions / 26y**: sparse. The +$47k cumulative may be averaging across very different conditions.

3. **All top-5 worst booster losses are in 2013-2014 (low-vol regime)**: NOT clustered in crises. This suggests worst losses are false-alarm mild events, not systemic transition risk.

4. **Cumulative incremental positive across all candidates** could indicate the signal definition itself is well-tuned to the specific 26y sample. Walk-forward in P4 will test out-of-sample robustness.

5. **Margin cost modeling**: Cash component currently uses BOXX 4.3% yield. Negative cash = margin loan, charged at same 4.3%. Real margin loans cost more (typically broker call rate + spread). P4 friction sensitivity ±50% will partly address this.

6. **Q042 17.5% interaction**: Q42 stays at 17.5% even during booster days. Combined SPX 90% + Q42 17.5% = 107.5% exposure (cash -7.5%, margin loan). PM dashboard / monitoring needs to confirm margin headroom comfortable. Not directly Q074 scope but worth flagging for SPEC implementation if B4 promotes.

---

## 5. Decision Matrix

| Reviewer verdict | Action |
|---|---|
| **PASS G3** + Q1-Q6 answered satisfactorily | Quant runs P4 on B4 (+ B3) → 2-3 day compute |
| **REVISE** specific methodology points | Quant updates P3 + re-run as needed before P4 |
| **REJECT** Q074 (sample too thin / methodology flawed) | Q074 closes; Arch-3 SPEC-104 stays as-is |
| **REVISE** to require additional P4 scope (synthetic stress variants, joint bucket analysis, etc.) | Quant expands P4; longer compute |

---

## 6. Quant Researcher Sign-off

Quant submits Q074 P3 for G3 mid-review 2026-05-18. Awaiting verdict before P4 full validation.

> **P3 evidence is unusually clean — all 4 candidates pass transition forensic, all 5 named crisis events show positive booster incremental, worst single loss tiny. This either reflects genuinely well-tuned signal design OR methodological generosity that P4 must stress-test. 2nd Quant judgment requested.**

---

## 7. Supporting Files

- `research/q074/q074_p3_transition_forensic_memo.md` — full P3 narrative
- `research/q074/q074_p3_transition_forensic.py` — simulator code
- `research/q074/q074_p3_transition_events.csv` — all 11,716 transition event rows
- `research/q074/q074_p3_severity_summary.csv` — per-candidate counts
- `research/q074/q074_p3_crisis_breakdown.csv` — 5 named crisis × 4 candidates
- `research/q074/q074_p3_top_booster_losses.csv` — worst-5 per candidate
- `research/q074/q074_p2_booster_sweep_memo.md` — P2 reference
- `research/q074/q074_p1_attribution_memo.md` — P1 reference
