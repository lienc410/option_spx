# Q075 P2 — Constrained Simulator Memo (Forced-Exit-on-Stress)

**Date**: 2026-05-19
**Author**: Quant Researcher
**Status**: **P2 DONE** — IC PASS clean, BCS PASS base + FAIL under +5% squeeze, C2 diagnostic PASS with caveats
**Source**: `research/q075/q075_p2_constrained_simulator.py` + 5 CSVs
**Locked parameters**: PM 2026-05-19 (stress slippage base 2x, sensitivity 1.5/2/3; IV+20%; put skew+10%; BCS squeeze +2/+3/+5%; cash hurdle = fair BP-day BOXX)
**G2 verdict**: PASS to limited P2 (2nd Quant 2026-05-19)

---

## 0. TL;DR

```
Candidate         Slip   n   Cand $    Cash $   Excess $   Worst    %force  PASS
C3 IC w15         2.0x  58  +$27,502    +$26   +$27,476     +$42    56.9%   ✅
C3 IC w25         2.0x  58  +$48,044    +$44   +$48,001    +$271    56.9%   ✅
C3 IC w35         2.0x  58  +$68,827    +$61   +$68,766    +$533    56.9%   ✅
C4 BCS            2.0x  58  +$80,876   +$131   +$80,745    +$887    56.9%   ✅ (BASE)
C2 sBPS (diag)    2.0x  58  +$48,723    +$81   +$48,642  -$1,493    41.4%   ✅ (diagnostic)
```

**Three structural findings**:

1. **All candidates beat the fair BP-day cash hurdle decisively** at base 2x slippage. Even C2 sBPS diagnostic survives the pass criteria.

2. **IC is robust across all sensitivities** (slip 1.5/2/3x, width 15/25/35pt). Worst single IC trade in 26y subset is **+$42** (positive). 57% of IC trades are force-exited by stress activation mid-trade, yet still profitable — confirms IC's natural defense (1-sigma OTM strikes + call wing offset).

3. **🚨 BCS breaks down under +5% / 10d synthetic squeeze**:

   | Squeeze scenario | n | Cum PnL | Worst | Hit% |
   |---|---|---|---|---|
   | +2% / 5d | 58 | +$61,030 | +$979 | 100.0% |
   | +3% / 5d | 58 | +$61,030 | +$979 | 100.0% |
   | **+5% / 10d** | **58** | **-$98,357** | **-$2,458** | **10.3%** |

   → BCS's apparent 100% hit rate in base case is **sample-bound**. Type C historical sample did not contain a sustained +5% melt-up. If next decade includes one, BCS would have lost $98k cumulative.

---

## 1. Locked Parameters (PM 2026-05-19)

| Parameter | Value |
|---|---|
| Entry | First-in-cluster Type C only (n=58) |
| Planned exit | 14 DTE (IC, BCS), 7 DTE (C2 sBPS diag) |
| Forced exit | stress_active flip True OR second_leg_active flip True → exit end-of-day |
| Trade-level stop | 2x credit loss |
| Normal friction | $50 round-trip per defined-risk trade |
| Stress-exit slippage | BASE 2.0x; sensitivity 1.5x / 2.0x / 3.0x |
| IV shock on forced exit (put side) | +20% (≈ 30% credit additional mark loss) |
| Put skew shock | +10% (additional 10% credit mark loss) |
| IV shock on forced exit (call side) | +20% IV but call usually OTM in downside stress → 10% credit mark loss only; no skew shock |
| BCS upside squeeze (parametric) | +2% / 5d, +3% / 5d, +5% / 10d; VIX compression assumed |
| IC wing width sensitivity | 15 / 25 / 35 pt |
| Cash hurdle | FAIR BP-day: max_loss × (4.3% / 252) × actual_holding_days |
| Cluster rule | STRICT 1 per cluster (≤3 cal-day gap) |
| Pass criteria | [1] excess > 0, [2] worst ≥ -$8,940 (1% NLV), [3] n ≥ 30 |

---

## 2. IC (C3) — Cleanest Candidate

```
Slip   Width  n   Cum PnL    Worst   Excess vs cash  %force
1.5x   15pt   58  +$27,660    +$42    +$27,634       56.9%
1.5x   25pt   58  +$48,448   +$436    +$48,404       56.9%
1.5x   35pt   58  +$69,297   +$630    +$69,236       56.9%
2.0x   15pt   58  +$27,502    +$42    +$27,476       56.9%
2.0x   25pt   58  +$48,044   +$271    +$48,001       56.9%
2.0x   35pt   58  +$68,827   +$533    +$68,766       56.9%
3.0x   15pt   58  +$27,186    +$42    +$27,160       56.9%
3.0x   25pt   58  +$47,404   +$104    +$47,360       56.9%
3.0x   35pt   58  +$67,888   +$339    +$67,827       56.9%
```

**Findings**:
- **Scales linearly with wing width** (15→25→35 → 28k→48k→69k cumulative). Wider wings = more credit per trade = more $$$ but more max-loss capital risked.
- **Robust across slippage**: 1.5x → 3.0x reduces cumulative by only $400-1400 per width. Stress-exit slippage is not the dominant risk for IC.
- **Worst single trade is POSITIVE across all width × slippage combos** (+$42 to +$630). IC's structural defense (1-sigma OTM both sides + call wing offset) protects against single-trade large losses.
- **57% of trades force-exited by stress** — confirms Type C's 50% next-10d stress prob from P1. Stress fires often but IC still profits because:
  1. Short strikes are 1 sigma OTM → cushion before breach
  2. Stress trigger (dd_20d ≤ -4%) can fire from a 20d-high reference well above entry SPX, not requiring large move from t0
  3. Combining put + call legs at 1/3 size dampens single-side losses

**Quant verdict**: IC at width 25 is the **primary P3/P4 candidate**. Width 35 has best ROE per trade but higher max-loss capital; width 15 has best capital efficiency but smaller $. Width 25 is the balanced middle.

---

## 3. BCS (C4) — PASS Base, FAIL +5% Squeeze

### 3.1 Base case (no synthetic squeeze)
```
Slip   n   Cum PnL    Worst    Excess vs cash  %force
1.5x  58  +$80,932   +$913    +$80,801        56.9%
2.0x  58  +$80,876   +$887    +$80,745        56.9%
3.0x  58  +$80,765   +$835    +$80,633        56.9%
```

BCS base case shows **+$80k cumulative, 100% hit, worst trade positive across all slippage**. Slippage barely affects BCS because:
- BCS's stress exit is usually relief (SPX selloff → call short OTM)
- IV shock on call side modeled at 10% credit only (vs 30% for put)

### 3.2 Synthetic upside squeeze — the smoking gun
```
Scenario       n    Cum PnL    Worst    Hit%
+2% / 5d       58   +$61,030    +$979   100.0%   ← survives
+3% / 5d       58   +$61,030    +$979   100.0%   ← survives (1 sigma cushion absorbs)
+5% / 10d      58   -$98,357  -$2,458    10.3%   ← BREAKS DOWN
```

The +5% / 10d scenario blows past the 1-sigma short call strike. Of 58 trades, only 6 (10.3%) survive; the rest are forced into mark loss approaching width-credit (~$1,500-$2,500 per trade).

**Interpretation**: BCS's 100% hit rate in base case is **sample-bound**. Type C historical sample (n=58) did not contain a sustained +5%/10d melt-up. If realized future sample contains a 2019-Q1-style or 2023-late-rally-style melt-up:
- 90% of BCS trades would have been forced into max-loss territory
- Net $98k loss would offset 2+ years of base-case gains
- Single-trade worst -$2,458 is still within 1% NLV ($8.9k), but cumulative damage is severe

### 3.3 BCS verdict

| Criterion | Result | Status |
|---|---|---|
| [1] Beats cash (base case) | +$80k vs $131 | ✅ |
| [2] Worst single trade (base) | +$887 | ✅ |
| [2'] Worst single trade (+5% squeeze) | -$2,458 | ✅ (still within 1% NLV) |
| [3] Sample size | 58 | ✅ |
| **+5% squeeze cumulative** | **-$98k** | **❌** |

**Quant verdict on BCS**: NOT promotable to P3 as primary candidate. Eligible as **secondary candidate with mandatory historical melt-up stress test in P3**. The base-case +$80k is not robust to upside regime shift.

---

## 4. C2 Short-DTE BPS (Diagnostic)

```
Slip   n   Cum PnL    Worst    Excess vs cash  %force
1.5x  58  +$51,181  -$1,493   +$51,100        41.4%
2.0x  58  +$48,723  -$1,493   +$48,642        41.4%
3.0x  58  +$45,004  -$1,493   +$44,923        41.4%
```

C2 sBPS shows positive cumulative across all slippage, but with the **only negative worst trade across all candidates (-$1,493)**. Slippage degradation more pronounced than IC ($6k reduction from 1.5x→3.0x, vs IC's ~$1.4k).

**Note**: forced_by_stress rate is 41.4% for C2 (vs 56.9% for IC/BCS) because 7 DTE planned hold means many trades expire before stress can fire within 10d window.

**Quant verdict on C2**: confirms 2nd Quant G2 directive — keep as diagnostic only, NOT promotable from P2. Structurally risky in 50% stress regime even though backtest survives. Higher gamma + 7 DTE = pin/gap risk that this simplistic mark model doesn't fully capture.

---

## 5. Fair BP-Day Cash Hurdle

Per PM directive: cash hurdle uses `max_loss × (4.3% / 252) × actual_holding_days`, not the simplistic per-trade $3 from P1.

```
Candidate      Cash hurdle (cumulative, slip 2.0x)   Excess
C3 IC w15      $26     +$27,476
C3 IC w25      $44     +$48,001
C3 IC w35      $61     +$68,766
C4 BCS         $131    +$80,745  (or -$98k - $131 = -$98,488 under +5% squeeze)
C2 sBPS        $81     +$48,642
```

Cash hurdle is **tiny relative to candidate PnL** because:
- 58 trades × ~14 days × ~$2.5k max_loss × 4.3%/252 ≈ $25-130 cumulative
- Defined-risk capital at risk is small per trade

This is the correct fair-comparison framework, but at this scale the cash hurdle barely matters. The relevant comparison is **candidate PnL vs zero (cash holds the capital, earns 4.3%/yr, no risk)** — which all candidates beat by 2-3 orders of magnitude.

**Interpretation**: at $894k NLV running 1 contract per Type C cluster (~2.6 trades/yr), Q075's ROE contribution is **~$1.8k - $3.5k / year**. On $894k NLV that's +0.20pp to +0.40pp annualized for IC w25 — at the **Strong threshold** per P0 §8.

But the contribution is small in absolute $. At $5M NLV with proportional scaling, $9k-18k/yr. At $20M, $36k-72k/yr. Linear scaling.

---

## 6. Crisis Window Behavior

```
[DotCom 2000_03]  no Type C trades in window
[PreGFC 2007_07]  IC w25: +$2,581 (n=3); BCS: +$4,453 (n=3); sBPS: +$1,003 (n=3, worst -$1,285)
[Vol 2018_02]     IC w25: +$1,314 (n=1); BCS: +$2,177 (n=1); sBPS: +$1,754 (n=1)
[COVID 2020_02]   no Type C trades in window
[Bear 2022_01]    no Type C trades in window
```

**Findings**:
- Only 2 of 5 named crisis windows had Type C entries (PreGFC 2007 and Vol 2018)
- All crisis-window trades were **net positive** for all candidates
- C2 sBPS had one -$1,285 trade in PreGFC 2007 — its worst overall

→ No crisis-window failure for any candidate. Q075 P3 P4 forensic should add synthetic stress scenarios (already done for BCS squeeze; should add for IC and C2).

---

## 7. Pass/Fail Per Candidate Summary

| Candidate | [1] Beats cash | [2] Worst ≥ -1%NLV | [3] n≥30 | +5% squeeze | Verdict |
|---|---|---|---|---|---|
| C3 IC w15 | ✅ | ✅ (+$42) | ✅ (58) | not tested | **PRIMARY P3 candidate** |
| C3 IC w25 | ✅ | ✅ (+$271) | ✅ (58) | not tested | **PRIMARY P3 candidate** |
| C3 IC w35 | ✅ | ✅ (+$533) | ✅ (58) | not tested | **PRIMARY P3 candidate** |
| C4 BCS | ✅ | ✅ (+$887 base) | ✅ (58) | **❌ -$98k** | **SECONDARY P3 candidate** (requires historical melt-up test) |
| C2 sBPS | ✅ | ✅ (-$1,493) | ✅ (58) | not applicable | **DIAGNOSTIC only** (not promotable, per G2 directive) |

---

## 8. Recommendation for P3/P4

### P3 Transition Forensic — required scope
1. **IC w15/25/35**: complete transition forensic — episode-level pre-stress behavior, crisis-window detail, failed-benign episode characterization. Add **synthetic upside squeeze test** for IC (P0 §6 said IC needs both downside and upside breach tests; only forced-exit modeled in P2).
2. **BCS**: mandatory historical melt-up analog injection — Quant proposes injecting **2019-Q1 rally** (SPX +13% over 90d, VIX -40% compression), **2023-Q4 rally** (SPX +14% Nov-Dec), **2024-H1 rally** as overlay to each BCS trade. Pass = cum PnL ≥ -$10k under each. Fail = REJECT BCS for production.
3. **C2 sBPS**: minimal forensic (one-pass episode count), kept as documented fallback.

### P4 Portfolio Integration — required scope
- IC (likely w25 base case) added on top of SPEC-104 + SPEC-105 v2 baseline
- Measure incremental ΔROE, MaxDD, W20d, W63d, capital competition with SPX/Q042, correlation
- Sharpe, bootstrap (block=250, 20 seeds), walk-forward H1/H2
- If IC w25 ΔROE ≥ +0.20pp annualized AND V1/V2/V3 pass AND Worst20d degradation ≤ 0.25pp → PROMOTE

### Promotion bar (per P0 §8.2 Q075-specific)
```
Strong:  ΔROE ≥ +0.20pp at portfolio level
Soft:    +0.05 to +0.20pp
Reject:  < +0.05pp
+ all V1/V2/V3 pass + Worst 20d degradation ≤ +0.25pp + no crisis-window failure
```

Quant estimate (rough, P2 → P4 extrapolation): IC w25 ~+$1.6k/yr annualized = +0.18% NLV/yr. **Borderline Strong/Soft**. P4 with portfolio interactions may shift slightly.

---

## 9. Caveats

1. **Sample size n=58 over 26y is small** for definitive inference. Bootstrap CI in P4 mandatory.
2. **Type C historical sample lacks sustained upside melt-up** — this is exactly why BCS's base 100% hit is suspicious. P3 historical-analog test will confirm or reject BCS.
3. **Stress-exit mark model is simplified** — uses theta + parametric IV/skew shock, not full options pricer. Real exits face spread bid/ask + liquidity at stress moments. Slippage 2x base + 3x sensitivity attempts to bracket this; production must verify against live execution data.
4. **IC's worst-case +$42 is suspiciously clean.** Possible explanations: (a) 1-sigma strike selection is genuinely safe in Type C; (b) sample-path-specific; (c) my model's stress mark too lenient (didn't fully capture worst intraday breach). P3 forensic should specifically probe IC trades where stress fired with non-trivial SPX drop.
5. **Cash hurdle is correct but small** — at $894k NLV, defined-risk capital is small per trade. Real value of Q075 candidates is the ROE contribution itself, not the cash arbitrage.
6. **2 of 5 crisis windows had ANY Type C entries.** Q075 candidates are by design rare — limited crisis exposure is expected, but limits crisis-validation power.
7. **57% forced-by-stress rate is the dominant feature.** Q075 candidates work *because* stress mid-trade doesn't necessarily breach strikes. If future Type C regime evolves to faster/sharper stress moves, this property may not hold.
8. **C2 sBPS forced-by-stress only 41.4%** because 7 DTE planned hold expires before 10d stress window completes — diagnostic confound; not a real advantage of short DTE.

---

## 10. P2 → P3 Readiness

**Quant recommends advancing to P3 with**:
- ✅ **IC C3 (width 25 primary, 15/35 sensitivity)** as **primary candidate**
- ⚠️ **BCS C4** as **secondary candidate, conditional on passing historical melt-up analog**
- 📝 **C2 sBPS** as **documented diagnostic** (no further investment unless IC fails)

**Decisions PM/2nd Quant may want to make before P3 starts**:
- D5: confirm IC width 25 as base; or test all three (15/25/35) through full P3/P4?
- D6: confirm BCS historical analog list (2019-Q1, 2023-Q4, 2024-H1); add others?
- D7: any concerns about IC's suspiciously clean worst-case before P3 begins?

Quant prior: (D5) test all three in P4, base case decided after seeing portfolio integration; (D6) those three analogs sufficient for P3 first pass; (D7) probe in P3 forensic explicitly.

---

## 11. Files

- `research/q075/q075_p2_constrained_simulator.py` — script with locked params
- `research/q075/q075_p2_trade_log.csv` — 870 rows (5 candidates × 3 slippages × ~58 trades)
- `research/q075/q075_p2_summary_per_candidate.csv` — pass/fail table
- `research/q075/q075_p2_squeeze_scenarios.csv` — BCS under +2/+3/+5%
- `research/q075/q075_p2_cash_hurdle.csv` — fair BP-day baseline
- `research/q075/q075_p2_crisis_breakdown.csv` — crisis-window detail

Upstream:
- `task/q075_p1_g2_2nd_quant_review_2026-05-19_Review.md` — G2 PASS to limited P2
- `research/q075/q075_p1_attribution_memo.md` — Type C subset definition
- `research/q075/q075_p0_anchored_memo_2026-05-19.md` — P0 locked scope (Type C renamed)

---

## 12. Sign-off

Q075 P2 constrained simulator complete. **No DOCUMENT path yet — IC clearly beats cash with clean worst-case across slippage sensitivities. BCS conditional on melt-up test. C2 sBPS diagnostic only.**

> Q075 P2 with PM-locked parameters (forced-exit-on-stress, 2x slippage base, fair BP-day cash hurdle, BCS parametric squeeze) finds: IC at all three wing widths beats fair cash by $27k-$69k cumulative over 26y with positive worst-case across all slippage sensitivities. BCS beats cash by $80k in base case but loses $98k under +5%/10d synthetic squeeze, revealing its 100% hit rate as sample-bound. C2 short-DTE BPS survives criteria but kept as G2-directed diagnostic only. Quant recommends P3 advances IC as primary candidate and BCS as conditional secondary requiring historical melt-up analog. ~$1.6k/yr ROE contribution at $894k NLV places IC borderline Strong/Soft per P0 §8.2 thresholds; P4 portfolio integration final-determines.
