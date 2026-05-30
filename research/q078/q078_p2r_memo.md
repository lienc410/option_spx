# Q078 P2 REVISED — eff_count + daily MTM + 20-seed CI Fixes

**Date**: 2026-05-28
**Author**: Quant Researcher
**Status**: **P2R DONE** — daily MTM smoothing CHANGES verdict from REJECT to STRONG PROMOTE on mean; but CI is wide (p5 W63d still fails)
**Source**: `research/q078/q078_p2r_revised.py` + 2 CSVs
**Decision sought**: PM + 2nd Quant verdict (G3 mandatory review)

---

## 0. TL;DR — original P2 verdict REVERSED on mean

```
Variant            Layer        AnnROE%   MaxDD%   W20d%    W63d%   EffCount  Verdict (mean)
V1b weekly catchup L2 prod     +15.21    -4.90    -2.98    -3.46     1.05    STRONG PROMOTE
V3  daily cluster  L2 prod     +17.03    -4.95    -2.78    -3.77     1.05    STRONG PROMOTE
Baseline B cluster L2 prod      +7.21    -6.17    -2.86    -3.71     1.00    baseline
```

```
Hard gates on MEAN (Layer 2 production):
                      Original P2          P2 REVISED
W20d degradation V1b: -0.26pp ❌FAIL → -0.13pp ✓PASS  (daily MTM smoothing)
W63d degradation V3:  -0.32pp ❌FAIL → -0.06pp ✓PASS  (daily MTM smoothing)
ΔROE V1b:             +8.81pp     → +8.00pp   (similar)
ΔROE V3:              +8.87pp     → +9.82pp   (similar)
```

**3 headline findings**:

1. **L4 (daily MTM smoothing) flipped the gate verdict**. Original P2 booked each trade PnL on a single day (exit_date), making W20d/W63d see lumpy spikes. P2 REVISED distributes PnL across hold days (~14 days), producing more realistic daily P&L curves. W20d/W63d both within 0.25pp gate on the mean.

2. **L1 (eff_count fix to monthly bucketing) GREATLY reduced diversification metric**. P1b-2 reported eff_count 3.17-3.42; P2 REVISED reports **1.05** (Layer 2 production). Root cause: P1b-2 grouped by exit_date (each calendar day = unique "expiry") which over-counted. Real expiry is monthly. **Ladder's diversification benefit is much smaller than P1b-2 suggested** — eff_count 1.05 vs Baseline 1.00 = "barely better than single-month exposure".

3. **CI is wide — p5 W63d Δ fails gate for both variants**. Even though mean passes, 20-seed bootstrap shows W63d Δ at 5%-tile = -3.61pp (V1b) / -3.14pp (V3) — far outside ±0.25pp gate. This is bootstrap noise from small per-strategy empirical pools (n=38-94 per strategy).

**Quant verdict**: 
- **Mean-based reading**: STRONG PROMOTE both
- **Worst-case CI reading**: SOFT PROMOTE V3 only (W20d p5 ✓; W63d p5 fail — but smaller fail than V1b)
- **Diversification reality**: eff_count 1.05 is barely above Baseline 1.00 — ladder's diversification benefit is **smaller than original framing**

---

## 1. Fixes applied (per PM agreement 2026-05-28)

### L1 — Eff_count metric fix
**Before** (P1b-2 + original P2): group by exit_date (each unique calendar day = separate "expiry"). Over 26y with hundreds of trades, hundreds of unique dates → eff_count up to 808.

**After** (P2 REVISED): group by **monthly expiry bucket** (entry_date + strategy DTE → month of expiry). All trades in same month share one expiry bucket. Result: eff_count 1.05 (production Layer 2) vs 1.00 (Baseline B).

### L4 — Daily MTM smoothing
**Before**: each trade's PnL booked entirely on its single exit_date. W20d/W63d see lumpy single-day spikes. → V1b W20d Δ -0.26pp, V3 W63d Δ -0.32pp (FAIL gates).

**After**: each trade's PnL distributed **linearly across its hold period** (~14 business days). Daily PnL series is smoother. → V1b W20d Δ -0.13pp, V3 W63d Δ -0.06pp (PASS gates on mean).

**Implication**: original P2 result was an artifact of aggregation method, not a real risk signal. Daily MTM smoothing is the more realistic baseline.

### L5 — 20-seed bootstrap CI
20 random seeds per (variant, layer). Report mean + 5%-95% CI. Captures bootstrap-sampling noise.

---

## 2. Updated metrics (mean + CI)

### V1b weekly catchup Layer 2
```
Ann ROE:   +15.21% [13.25%, 16.63%]
MaxDD:     -4.90%  [-8.20%, -3.12%]
W20d:      -2.98%  [-3.76%, -2.83%]
W63d:      -3.46%  [-6.29%, -2.19%]
Worst:     -4.29% NLV (single-trade fixed)
EffCount:  1.05    [1.04, 1.05]
```

### V3 daily cluster Layer 2
```
Ann ROE:   +17.03% [15.30%, 18.96%]
MaxDD:     -4.95%  [-7.84%, -3.18%]
W20d:      -2.78%  [-2.78%, -2.76%]
W63d:      -3.77%  [-5.81%, -2.32%]
Worst:     -4.29% NLV
EffCount:  1.05    [1.05, 1.06]
```

### Baseline B Layer 2
```
Ann ROE:   +7.21%  [5.44%, 8.39%]
MaxDD:     -6.17%  [-10.21%, -3.43%]
W20d:      -2.86%  [-3.08%, -2.59%]
W63d:      -3.71%  [-4.61%, -2.67%]
Worst:     -4.29% NLV
EffCount:  1.00    [1.00, 1.00]
```

---

## 3. Hard gate analysis (CI-aware)

### Mean-based (P0 §7 default)

```
V1b L2 vs Baseline B:
  ΔROE = +8.00pp (Strong threshold +0.20pp easily met) ✓
  W20d Δ = -0.13pp (gate ≤ +0.25pp) ✓
  W63d Δ = +0.24pp ✓ (better than baseline)
  All absolute V1/V2/V3 pass ✓
  Worst -4.29% NLV ✓ (gate 5%)
  → STRONG PROMOTE on mean

V3 L2 vs Baseline B:
  ΔROE = +9.82pp ✓
  W20d Δ = +0.08pp ✓ (slightly better than baseline)
  W63d Δ = -0.06pp ✓ (within 0.25pp)
  All absolute V1/V2/V3 pass ✓
  → STRONG PROMOTE on mean
```

### CI 5%-tile worst-case reading

```
V1b L2 worst case:
  W20d Δ p5 = -1.17pp → ❌ FAIL gate (-0.25pp limit)
  W63d Δ p5 = -3.61pp → ❌ FAIL gate by large margin
  → REJECT under strict worst-case CI

V3 L2 worst case:
  W20d Δ p5 = -0.19pp → ✓ PASS
  W63d Δ p5 = -3.14pp → ❌ FAIL gate
  → REJECT under strict worst-case CI

Both variants fail W63d Δ at 5%-tile.
```

### Why CI is wide

Bootstrap samples per-trade PnL from engine empirical pool (per strategy). Strategy pools small:
- BPS NORMAL: n=38
- BPS HV: n=42
- IC NORMAL: n=69
- IC HV: n=112
- BCD: n=94

Small empirical pools + per-trade independent draws → 20-seed CI for cum metrics is ±10-30% of mean. For metric-of-metric like W63d (worst rolling 63-day return), CI especially wide because dominant bad-streak depends on which exact trades sampled.

**Methodologically**: CI is wide because we're applying bootstrap to per-trade PnL; in production, real trades aren't independent — they're correlated through market regime. Bootstrap likely OVERSTATES tail uncertainty.

---

## 4. Critical interpretation of low eff_count

```
P1b-2 (broken metric):  eff_count 3.17 (V1b) / 3.42 (V3) — over-counted
P2 REVISED (fixed):     eff_count 1.05 (both ladders) vs 1.00 (Baseline B)
```

**Why is eff_count so close to 1.00 even for ladder?**

At S3 sizing (3 contracts) + 14-day hold + concurrency cap (1 per strategy):
- At any given week, ladder has ~1-2 positions active (selectorbias toward few strategies)
- Most positions in same calendar month → same expiry bucket
- Different strategies (BPS + IC + BCD) might be open simultaneously in same month → still one expiry bucket
- Cross-month overlap rare due to 14-day hold

**Implication**: ladder's "diversification benefit" is largely illusory at this sizing. Most concurrent positions cluster in single monthly cohort.

PM observed problem (8-at-6/18 expiry) corresponds to:
- 8 spreads all entered around same date → all same monthly expiry → eff_count 1.00
- This DID materialize empirically; baseline B simulates it

Ladder at S3 produces eff_count 1.05 — **slightly** spread (some months have 2 expiries via different strategies), but mostly still single-month. **Not the 3-4x improvement P1b-2 claimed.**

This is an important finding: **ladder's diversification value at S3 is marginal**. The big improvement claimed by P1b-2 was a metric bug.

---

## 5. Updated verdict considerations

Per P0 §7 promotion rule + P2 REVISED data:

| Aspect | Status |
|---|---|
| Per-trade worst gate (5% NLV) | ✓ PASS (-4.29% NLV) |
| V1/V2/V3 absolute thresholds | ✓ PASS (all variants well within) |
| ΔROE Strong threshold (+0.20pp) | ✓ PASS easily (+8-10pp) |
| W20d degradation ≤ +0.25pp (mean) | ✓ PASS (V1b -0.13, V3 +0.08) |
| W63d degradation ≤ +0.25pp (mean) | ✓ PASS (V1b +0.24, V3 -0.06) |
| W20d / W63d at 5%-tile CI | ❌ FAIL for both |
| Eff_count diversification | ⚠ MARGINAL (1.05 vs 1.00) |
| Crisis window analysis | ⏸ NOT YET DONE (P3) |

**Promotion candidates**:
- (a) STRONG PROMOTE on mean — ΔROE big, all mean gates pass
- (b) SOFT PROMOTE — ΔROE strong but worst-case CI fails
- (c) DOCUMENT — promote pending bias/CI cleanup, no SPEC
- (d) REJECT — strict CI-based gate enforcement

---

## 6. The fundamental question

**ROE comes from somewhere**. V1b at S3 ann ROE +15% NLV/yr = +$134k/yr on $894k NLV. That's a lot.

Source of ROE:
- 524 trades over 26y = 20/yr
- Avg ~$6,700 per trade at S3 sizing
- Versus engine's average ~$1,500/trade per contract × 3 = $4,500
- Hmm 6.7k > 4.5k suggests bootstrap selecting better trades on average — selection bias?

Wait — but Layer 2 production with concurrency. So which days produce the +15% ROE?

Most likely: ladder's higher trade count (520 vs Baseline B's 254) at similar per-trade PnL ≈ 2x cum PnL. At baseline +7.2% NLV, ladder ≈ +14-15% NLV. Matches.

So ladder ROE advantage = more trades per year, not better PnL per trade. **Cadence captures more opportunities** that Baseline B's sparse cluster misses.

This makes economic sense: ladder fires on more selector-PASS days within the gate constraints.

But ALSO selection bias: ladder's 520 trades use bootstrap from engine's 373-trade pool. Engine's pool already includes the best trades. Ladder's "extra" trades on top of engine's 14/yr come from days engine filtered out — those should be WORSE quality. Bootstrap doesn't capture this.

Realistic deflation: if ladder's incremental trades are ~50% quality of engine's filtered pool, then:
- Ladder true PnL ≈ 50% × (520-254)/520 + 100% × 254/520 = 75% of reported
- V1b true ROE ≈ 0.75 × 15.21% = +11.4% NLV/yr → ΔROE +4.2pp vs baseline

Still substantial but less dramatic than reported.

This is consistent with earlier P1b-1 selection bias estimate (3-5x inflation). After concurrency correction (P2R Layer 2), inflation reduced to maybe 1.5-2x.

**Honest reading**: ladder probably adds +3-5pp ROE annualized vs baseline at S3, not +8-10pp. Still material.

---

## 7. Open questions for PM / 2nd Quant

### D1 — Mean vs CI-worst-case gate?
P0 §7 doesn't specify whether gates apply to mean or worst-case CI. Mean = STRONG PROMOTE; CI = REJECT.

- (a) Mean-based gate enforcement (current Quant prior)
- (b) Require p5 to pass (conservative)
- (c) Require expected violation rate < 5% (statistical)

### D2 — Eff_count 1.05 vs 1.00 — material diversification or noise?
- Real benefit: 0.05 of an expiry — tiny
- Conceptual benefit: ladder DOES reduce cluster concentration when entries naturally span multiple months
- But practically: 14-day hold means most positions clear before next month's entries → low overlap

Should diversification claim be **softened**?

### D3 — Bootstrap selection bias residual
Even Layer 2 (concurrency + BP) probably still inflates by 1.5-2x due to bootstrap from filtered pool. Should P3 address this further?

- (a) Adjust per-incremental-trade quality assumption
- (b) Run engine WITHOUT filters to get unbiased pool (2nd Quant's original D1(a))
- (c) Accept residual bias; advance with caveat

---

## 8. Recommendation

**Quant prior** for verdict:

> **SOFT PROMOTE V3 daily-cluster S3** based on:
> - Mean ΔROE +9.82pp (Strong threshold easily met)
> - Mean gates all pass (W20d Δ +0.08pp, W63d Δ -0.06pp)
> - V3 W20d p5 passes (+/-0.19pp within 0.25pp)
> - V3 lower MaxDD (-4.95% vs baseline -6.17%) — actually BETTER
>
> **NOT PROMOTE V1b** based on:
> - W20d p5 fail (-1.17pp wide CI)
> - W63d p5 fail (-3.61pp wide CI)
> - V1b less robust than V3 under bootstrap uncertainty
>
> **Caveat**:
> - eff_count 1.05 marginal — PM should not expect dramatic concentration reduction
> - Bootstrap selection bias likely still inflates ROE by 1.5-2x
> - Real production deployment should reflect these caveats in SPEC

Alternative: **DOCUMENT both** as operational discipline, advance to P3 if PM wants formal verdict.

---

## 9. Caveats

1. **Eff_count metric semantic shift**: P1b-2 vs P2 REVISED use different definitions. P2 REVISED (monthly bucketing) is more correct, but reverses the "ladder strongly diversifies" finding.

2. **Daily MTM smoothing (linear distribution)** is a simplification. Real options have non-linear theta decay. P2 REVISED uses linear → may underestimate worst-day MTM swings.

3. **Bootstrap CI wide** — driven by small per-strategy empirical pools (n=38-112). Real production correlations would reduce uncertainty but pool size remains constraint.

4. **Selection bias not fully resolved** — Layer 2 applies concurrency + BP but not all engine filters. Residual bias likely 1.5-2x.

5. **No crisis window analysis** — P3 forensic should validate hard gates hold during 2008/2020/2022 stress periods.

6. **PM operational burden**: V1b ≤30 action days/yr ✓; V3 daily check ✓. Both viable.

7. **Strategy mix shifts with cadence**: V1b/V3 enter mix of BPS/IC/BCD/HV variants per selector. PM should not expect "weekly BPS" cadence.

8. **Worst-trade -4.29% NLV** is per-IC-NORMAL-trade × 3 contracts. PM's current 4-contract BPS-only entry has different worst case (-4.3% NLV BPS-only); 5% gate analysis applies to mixed-strategy ladder only.

---

## 10. P2R → P3/G3 readiness

P2 REVISED resolved the original P2 gate failure on mean basis. But uncertainty remains:
- CI shows worst-case fail
- Diversification benefit smaller than P1b-2 claimed
- Selection bias not fully resolved

**Next step options**:

| Path | Action |
|---|---|
| **G3 mandatory review** | Transfer P2 REVISED to 2nd Quant for verdict + decide P3 forensic scope |
| **P3 directly** | Run crisis window forensic + walk-forward H1/H2 + tighter bias correction |
| **DOCUMENT** | Skip further work; close Q078 with operational note + 2nd Quant sign-off |

**Quant prior**: **G3 mandatory review** before P3. 2nd Quant should weigh in on mean-vs-CI gate question, diversification reality, and final verdict pathway.

---

## 11. Files

- `research/q078/q078_p2r_revised.py` — script with L1/L4/L5 fixes
- `research/q078/q078_p2r_metrics.csv` — mean + CI per (variant, layer)
- `research/q078/q078_p2r_gate_check.csv` — hard gate pass/fail w/ CI

Predecessor:
- `research/q078/q078_p2_memo.md` (original P2, eff_count broken, daily MTM not smoothed)
- `research/q078/q078_p2_portfolio_integration.py`

Upstream:
- `research/q078/q078_p0_anchored_memo_2026-05-27.md` (P0 with 5% NLV gate)
- `research/q078/q078_p1b_1_memo.md` and `q078_p1b_2_memo.md`
- `task/q078_p1b_g2_5_2nd_quant_review_2026-05-28_Review.md`

---

## 12. Sign-off

Q078 P2 REVISED applies 3 fixes from G2.5 / PM agreement: eff_count metric (monthly bucketing), daily MTM smoothing (linear distribution across hold days), 20-seed bootstrap CI. Daily MTM fix is the decisive one — it flips W20d/W63d degradation from FAIL to PASS on mean. Both V1b and V3 STRONG PROMOTE on mean basis with ΔROE +8-10pp annualized. BUT 20-seed CI shows W63d Δ at 5%-tile fails gate for both variants (-3.14 to -3.61pp); V3 marginally more robust than V1b. Eff_count 1.05 (vs Baseline 1.00) is a much smaller diversification benefit than P1b-2's broken metric suggested — ladder's diversification value at S3 is marginal, not dramatic. ROE advantage real but partially attributable to higher trade count not better per-trade PnL.

**Recommend G3 mandatory review with 2nd Quant** to weigh: (1) mean-vs-CI gate enforcement, (2) marginal diversification benefit reality, (3) residual selection bias, (4) verdict pathway (SOFT PROMOTE V3 / DOCUMENT both / REJECT / PROCEED to P3 crisis forensic).

> Q078 P2 REVISED: daily MTM smoothing flipped gate verdict from REJECT → STRONG PROMOTE on mean (V1b ΔROE +8.0pp, V3 +9.8pp; all mean gates pass); but 20-seed CI shows W63d Δ p5 = -3.14 (V3) / -3.61 (V1b) — both fail gate at worst case. Eff_count metric fixed (monthly bucketing) shows ladder diversification = 1.05 vs Baseline 1.00 — much smaller than P1b-2's broken 3.17 metric suggested. ROE advantage robust on mean but uncertainty wide; selection bias residual ~1.5-2x. V3 marginally more robust than V1b (W20d p5 passes for V3). Recommend G3 mandatory review before P3 forensic.
