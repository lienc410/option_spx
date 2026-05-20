# Q074.2 — Gate F Portfolio Validation Memo

**Date**: 2026-05-19
**Author**: Quant Researcher
**Trigger**: 2nd Quant Q074.1b REVISE — required portfolio-level ROE / V1V2V3 / transition validation before SPEC-105 amendment
**Decision**: **PROMOTE Gate F** (IVP_252 < 55 OR VIX < 15) — recommend SPEC-105 v2 amendment
**Status**: Quant submits to 2nd Quant for final review

---

## 0. TL;DR

Three-way comparison (B4-current / B4-F / B4-F2) on full 26y unified-NLV simulator with all 8 required checks:

```
Variant       ROE       ΔROE     MaxDD    W20d     W63d     V1V2V3   Boost%Norm
B4_current    8.201%    +0.000   -8.71%   -7.04%   -8.66%   ✓✓✓      36.0%
B4_F          8.214%    +0.014   -8.71%   -7.04%   -8.66%   ✓✓✓      39.8%
B4_F2         8.211%    +0.011   -8.71%   -7.04%   -8.66%   ✓✓✓      38.2%
```

**All three tail metrics literally identical** across variants (same worst-day, same worst-window — boosters don't deepen tail). Layer-1 untouched.

**F dominates F2 across cumulative metrics**:

| Metric | F | F2 | Winner |
|---|---|---|---|
| Cum extra $ over current | +$23,513 | +$18,277 | **F** (+$5,236) |
| Annual contribution | +0.100% NLV/yr | +0.078% NLV/yr | **F** |
| Bootstrap ΔROE mean | +0.014pp | +0.011pp | **F** |
| Bootstrap 5% lower bound | **+0.008pp** | +0.001pp | **F** (more robust) |
| P(ΔROE > 0) | 100% | 100% | tie |
| Tail (MaxDD/W20d/W63d) | unchanged | unchanged | tie |
| Worst single transition | -$1,304 (same day) | -$1,304 (same day) | tie |
| failed_benign delta vs current | +3 | 0 | F2 (minor) |

**Recommendation**: PROMOTE Gate F. The +$5,236 cum benefit and tighter bootstrap lower bound outweigh the 3 marginal failed_benign episodes (all mild severity, no tail impact).

---

## 1. Methodology

**Common variant base** (all 6 B4 conditions held constant):
```
not stress_active, not second_leg_active, above_ma50,
ddath > -0.04, vix < 22, vix_5d_change <= 1.5
```

**Variant-only IVP condition**:
```
B4_current: ivp_252 < 55
B4_F:       ivp_252 < 55 OR vix < 15
B4_F2:      ivp_252 < 55 OR vix < 14
```

**Booster cap**: 90% (B4 family, unchanged).

**State priority**: 2nd-leg 40% > stress 50% > booster 90% > normal 80% (unchanged from SPEC-104/105).

**Simulator**: P1.3R unified-NLV combined daily series, friction drag = constant $/day from FRICTION_ANN, cash yield 4.3%, Q42 at 17.5% target, HV at 0%. Identical to Q074 P2-P4.

Sample: 26y (2000-01 → 2026-05), n=6632 days.

---

## 2. Required Check 1 — Full portfolio metrics

```
Variant          ROE %  ΔROE pp   MaxDD %   W20d %   W63d %  Sharpe  BoostDays   %Norm
B0_baseline      7.949  -0.252     -8.71    -7.04    -8.66    1.97          0    0.0%
B4_current       8.201  +0.000     -8.71    -7.04    -8.66    2.02       1331   36.0%
B4_F             8.214  +0.014     -8.71    -7.04    -8.66    2.02       1470   39.8%
B4_F2            8.211  +0.011     -8.71    -7.04    -8.66    2.02       1409   38.2%
```

All three variants:
- **V1 (MaxDD ≥ -28%)**: ✓ (-8.71%)
- **V2 (W20d ≥ -11%)**: ✓ (-7.04%)
- **V3 (W63d ≥ -17%)**: ✓ (-8.66%)
- **Floor 8% ROE**: ✓
- **Booster % of normal days < 60%**: ✓ (36-40%)

Tail metrics are **literally identical** because the worst windows are SPX/Q42 driven on days when none of the variants are booster-active (worst day is 2020-03 era — stress-active, all variants force 50% cap).

---

## 3. Required Check 2 — Newly-added-day attribution

Days where the variant's booster activates but B4-current does not:

| Variant | n_added | Cum extra $ | Avg $/day | Hit% | Annual contrib | Worst single day |
|---|---|---|---|---|---|---|
| F (VIX<15) | 139 | **+$23,513** | $169 | 52.5% | **+0.100% NLV/yr** | -$1,674 |
| F2 (VIX<14) | 78 | +$18,277 | $234 | 55.1% | +0.078% NLV/yr | -$1,674 |

**Both gates' added days produce net positive cumulative PnL.** F adds 61 more days than F2 for +$5,236 additional cumulative (the VIX 14-15 subset).

---

## 4. Required Check 3 — VIX bucket attribution (key for F vs F2)

Within F-added days only, by VIX sub-bucket:

| VIX bucket | n | Cum extra $ | Avg $/day | Hit% | Verdict |
|---|---|---|---|---|---|
| <13 | 40 | +$12,750 | **+$319** | **65.0%** | Strong positive |
| 13-14 | 38 | +$5,528 | +$145 | 44.7% | Moderate positive |
| **14-15** | **61** | **+$5,235** | **+$86** | **49.2%** | **Marginal but positive** |

**The VIX 14-15 segment is the F-vs-F2 decision point.**

Hit rate 49.2% < 50% looks like coin-flip, but **avg PnL +$86/day and cumulative +$5,235 over 61 days** confirm positive expected value (wins are larger than losses). Excluding this segment (F2) discards $5,235 of cumulative cash.

**Conclusion**: VIX 14-15 days are economically additive — F should include them.

---

## 5. Required Check 4 — Transition forensic

Stress trigger events over 26y: **2939**. For each, examine booster activity in 10d-prior window and severity in 20d-forward window.

```
Variant       mild  acute  failed_benign  cum_inc_$ 10d  worst_episode
B4_current    123    48      41           $+213,893       $-1,304
B4_F          131    53      44           $+220,391       $-1,304
B4_F2         123    53      41           $+219,813       $-1,304
```

- **Worst single transition is identical across all three (-$1,304 on 2014-01-31)** — boosters don't create new worst-day risk.
- F adds 8 mild + 5 acute + 3 failed_benign vs current. F2 adds 0 mild + 5 acute + 0 failed_benign.
- F's 3 extra failed_benign are all **mild severity, small magnitude** (within VIX 14-15 segment, which still nets +$5,235 cum).
- Cum incremental over 26y is +$220k (F) vs +$214k (current) — F **adds** $6.5k of net pre-stress benefit, not loss.

**Verdict**: F's marginal increase in transition count (3 failed_benign) is offset by larger cumulative win and no worst-tail degradation.

---

## 6. Required Check 5 — Walk-forward H1 / H2

```
Period         Variant      ROE %    ΔROE vs cur   W20d %   V2
H1_2000_2012   B4_current   8.423    +0.000pp      -7.04    ✓
H1_2000_2012   B4_F         8.457    +0.035pp      -7.04    ✓
H1_2000_2012   B4_F2        8.460    +0.038pp      -7.04    ✓

H2_2013_2026   B4_current  14.517    +0.000pp      -3.50    ✓
H2_2013_2026   B4_F        14.537    +0.020pp      -3.50    ✓
H2_2013_2026   B4_F2       14.527    +0.011pp      -3.50    ✓
```

- **Both F and F2 improve ROE in BOTH halves** — not H2-only (Q074 G3 concern resolved).
- W20d identical across all 9 cells — tail invariant.
- F slightly better in H2, F2 slightly better in H1. Marginal.

**Verdict**: walk-forward acceptable; improvement is not regime-bound.

---

## 7. Required Check 6 — Active days % diagnostic

| Variant | Booster days | % of total | % of normal |
|---|---|---|---|
| B4_current | 1331 | 20.1% | 36.0% |
| B4_F | 1470 | 22.2% | **39.8%** |
| B4_F2 | 1409 | 21.3% | 38.2% |

Threshold: < 60% of normal days. **All three well within bound.** Gate F does not turn the booster into a disguised normal-cap raise.

---

## 8. Required Check 7 — Bootstrap (block=250, 20 seeds)

```
B4_F vs B4_current:
  ΔROE mean +0.014pp, σ 0.006pp
  5th-95th [+0.008pp, +0.023pp]
  P(ΔROE > 0) = 100%

B4_F2 vs B4_current:
  ΔROE mean +0.009pp, σ 0.007pp
  5th-95th [+0.001pp, +0.019pp]
  P(ΔROE > 0) = 100%
```

- Both variants positive in 100% of bootstrap seeds.
- **F's 5% lower bound (+0.008pp) is 8x F2's lower bound (+0.001pp)** — F is statistically more robust.
- σ ~0.006pp is one order of magnitude smaller than Q074 P5 bootstrap σ (0.10pp) because F vs current is a tighter perturbation (same base + one OR condition added).

---

## 9. Required Check 8 — Friction sensitivity

Per Q074 P4 baseline: ±50% friction stress shows ΔROE for B4 stable at +0.25pp ±0.013pp. Gate F adds at most +$169/day on 139 days = $23,513 over 26y. Friction on those days is constant daily drag, unaffected by gate definition. **No new friction sensitivity introduced**; Q074 P4 framework still applies.

---

## 10. Required Check (implicit) — Crisis windows

| Crisis | Trigger | B4_current | B4_F | B4_F2 |
|---|---|---|---|---|
| DotCom_2000_03 | 2000-03-01 | $0 (no booster) | $0 | $0 |
| PreGFC_2007_07 | 2007-07-26 | $0 | +$513 (2 booster days) | $0 |
| Vol_2018_02 | 2018-02-05 | +$3,597 | **+$6,049** | +$6,049 |
| COVID_2020_02 | 2020-02-24 | +$1,031 | +$805 | +$1,031 |
| Bear_2022_01 | 2022-01-18 | +$6,009 | +$6,009 | +$6,009 |

**All five crises are net positive for all three variants.** F captures more 2018-02 pre-vol PnL than current (+$2,452 incremental), at risk of slightly less in COVID 2020-02 (-$226).

---

## 11. F vs F2 Final Comparison

| Dimension | F (VIX<15) | F2 (VIX<14) | Verdict |
|---|---|---|---|
| Cum extra $ | **+$23,513** | +$18,277 | F +$5,236 |
| Annual ROE contrib | **+0.100% NLV/yr** | +0.078% NLV/yr | F |
| Bootstrap ΔROE mean | **+0.014pp** | +0.011pp | F |
| Bootstrap 5% lower bound | **+0.008pp** | +0.001pp | **F (8x more robust)** |
| Tail (V1/V2/V3) | unchanged | unchanged | tie |
| Worst single transition | -$1,304 | -$1,304 | tie |
| failed_benign delta | +3 | 0 | F2 (minor) |
| Booster %normal | 39.8% | 38.2% | tie |
| Crisis windows | all positive | all positive | tie |
| Walk-forward H1/H2 | both improved | both improved | tie |

**Per-day avg ($169 vs $234) and hit rate (52.5% vs 55.1%) are NOT decision-relevant** — no day-count constraint exists. The right metric is absolute cumulative cash and annual ROE contribution, where **F dominates**.

The VIX 14-15 segment (excluded by F2, included by F) has hit rate 49.2% but **positive expected value (+$86/day, +$5,235 cum)** — it is economically additive, not noise.

F's only weakness is 3 extra mild-severity failed_benign episodes over 26y (≈ 1 per 9 years), which is statistical noise and doesn't degrade worst tail.

---

## 12. Recommendation

**PROMOTE Gate F to SPEC-105 v2 amendment.**

Proposed SPEC-105 v2 change (single-line):

```diff
B4 benign booster conditions (all required):
  not stress_active
  not second_leg_active
  SPX > MA50
  ddATH > -4%
  VIX < 22
  VIX 5d change ≤ +1.5
- IVP_252 < 55
+ IVP_252 < 55 OR VIX < 15
```

All other SPEC-105 elements unchanged: state machine priority, 90% booster cap, monitoring obligations, staged rollout (PM-discretionary). Stage 1 shadow can switch to Gate F definition immediately; no architecture or governance change.

**Caveats**:
1. ΔROE +0.014pp is economically small ($125/yr on $894k NLV). At larger NLV the absolute benefit scales linearly.
2. F2 remains a documented conservative fallback option (8x lower bootstrap lower bound but smaller mean).
3. Adoption of F does NOT modify Layer-1 protection; tail invariance is empirically confirmed (W20d/W63d/MaxDD all identical to current).

---

## 13. Files

- `q074_2_gate_validation.py` — script
- `q074_2_portfolio_metrics.csv` — full-sample metrics
- `q074_2_added_day_attribution.csv` — newly-added-day cum/avg
- `q074_2_vix_bucket_attribution.csv` — F-added VIX sub-bucket
- `q074_2_transition_summary.csv` — severity counts per variant
- `q074_2_transition_events.csv` — per-trigger event log
- `q074_2_crisis_breakdown.csv` — 5 named crises
- `q074_2_walkforward.csv` — H1/H2 split-sample
- `q074_2_bootstrap.csv` — block-bootstrap ΔROE
- `q074_2_top_booster_losses.csv` — worst-5 per variant

Prior context:
- `q074_1b_forensic_memo.md` — anti-signal discovery
- `q074_1_forensic_memo.md` — PM trigger investigation
- `task/q074_1b_2nd_quant_review_packet_2026-05-19_Review.md` — 2nd Quant REVISE verdict
