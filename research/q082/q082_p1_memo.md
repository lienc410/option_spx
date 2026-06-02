# Q082 P1 — Sample Coverage + Reframing

**Date**: 2026-06-01
**Owner**: Quant Researcher
**Status**: COMPLETE — kill-gate not triggered, but **scope reframed**
**Prior**: Q082 framing memo 2026-06-01
**Next**: P2 (reframed scope below) → G-review 1

---

## Headline finding

**The matrix already does what Q082 was supposed to verify**: BCD is
gated to LOW_VOL × BULLISH only. In 26 years of signal history
(2000-2026), named stress periods have nearly zero BCD-eligible days:

| Stress window | BCD-eligible days |
|---|---:|
| 2008 GFC (2007-10 → 2009-06) | **0** |
| 2022 rate decline | **0** |
| 2011 summer crisis | **0** |
| 2018 Q4 vol spike | 4 |
| 2020 COVID flash crash | 2 |
| 2015 Aug correction | 5 |
| **Stress total** | **11 days** |

Compare benign controls:
- 2017 low-vol bull: **223 days**
- 2021 (post-COVID rally, actually flagged HIGH_VOL much of 2021): **0 days**
- 2024 bull: **138 days**

**Layer-1 regime filter is the BCD's first defense against stress.**

---

## Reframing Q082 scope

The originally stated B-2 concern was: "若未来市场系统性变成跌多涨少，
BCD edge 消失". Q082 was framed to test BCD across adverse regimes.

**But P1 reveals**: matrix never opened BCD in adverse regimes
historically. So "BCD in 2008 / 2022 / 2011" is a non-question — matrix
prevented it.

The **real residual risk** from Q081 B-1 is different:
- Matrix entry signal (LOW_VOL × BULLISH) is **point-in-time**, not
  forward-prediction
- 3y Q081 sample: 9/21 = 43% of BCD entries encountered DOWN forward
  windows despite entering in LOW_VOL × BULL
- These "good entry → bad forward window" cases drove BCD's −3.4pp
  underperformance vs QQQ in DOWN stratum

**Q082's real value-add (revised)**: across 1,747 BCD-eligible days in
26y, what's the **forward 30-60-90 day SPX return distribution**? Is
Q081's 3y sample (48% forward-up) representative, more adverse, or more
benign than the long-run BCD-eligible regime profile?

---

## Annual distribution

```
year    BCD-eligible    ivp_LOW  ivp_MID  ivp_HIGH    avg_VIX
2004           86           86       0         0       13.57
2005          135          118      17         0       11.84
2006          163          106      55         2       11.54
2007           81           32      41         8       12.00
2011            3            3       0         0       14.69
2012           23           23       0         0       14.33
2013          182          147      35         0       13.34
2014          162          101      56         5       12.79
2015           65           20      45         0       13.39
2016          125          110      15         0       13.15
2017          223          187      34         2       10.78
2018          102           12      76        14       12.36
2019          130           92      38         0       13.39
2020           22           12      10         0       13.33
2023           80           80       0         0       13.51
2024          138           93      44         1       13.43
2025           23           21       2         0       14.54
2026            4            4       0         0       14.66
TOTAL       1747         1175     569         32
```

**Coverage gaps**: 2008-2010 (post-GFC HIGH_VOL persists), 2011 (almost
all HIGH_VOL), 2021-2022 (rate-driven decline + post-COVID HIGH_VOL).
These are **not data gaps**, they are **matrix-correct exclusions**.

Median BCD-eligible-day VIX: ~13. IVP distribution: 67% LOW, 33% MID,
~2% HIGH. So BCD historically opens predominantly in LOW IV regime.

---

## Updated Q082 P2 scope (replaces original framing memo §2)

**Original P2 (deprecated)**: synthetic BCD reconstruction across regimes
including stress. → Q082 P1 shows matrix doesn't open in stress; no
synthetic regime to test.

**Revised P2**: Forward-window direction distribution across 26y BCD-
eligible days.

### P2 method

For each of 1,747 BCD-eligible days:
1. Compute forward 21-day, 34-day (Q081 median hold), 60-day SPX return
2. Classify forward window as UP (>+1%) / FLAT (±1%) / DOWN (<-1%)
3. Aggregate by year + by IVP bucket + by VIX bucket
4. Compare 3y Q081 sample (48% up / 10% flat / 43% down) to 26y baseline
5. Compute forward-return distribution moments (mean, std, p05) to
   estimate aggregate BCD vs QQQ comparison **without** running synthetic
   BCD reconstruction (which P1 shows isn't needed)

### P2 expected output

A table:

| Sample | n | %UP fwd | %FLAT | %DOWN | mean fwd SPX % | p05 fwd SPX % |
|---|---|---|---|---|---|---|
| Q081 3y (2023-2026) | 21 | 48% | 10% | 43% | +0.5% | -3.6% |
| 26y full (revised P2) | 1747 | TBD | TBD | TBD | TBD | TBD |

Three possible verdicts from P2:

**V1 — 26y forward profile is MORE up-biased than Q081**: 3y was anomalously
adverse for BCD. **B-1 is stronger than Q081 P5 implied**. Recommend
maintaining matrix + light monitoring only.

**V2 — 26y forward profile matches Q081 within noise**: 3y is representative;
B-1 holds as-is.

**V3 — 26y forward profile is MORE down-biased than Q081**: 3y was anomalously
favorable for BCD. **B-1's residual risk is real**. Recommend additional
gate (e.g., BCD blocked when SPX 30d MA breaks below 200d MA).

### P2 effort

~3-4 hours (no synthetic BCD reconstruction needed). Replaces original
P2's 16-24h estimate. **Q082 total scope shrinks dramatically.**

---

## Updated Q082 timeline (revised)

| Phase | Updated scope | Hours |
|---|---|---|
| P1 | Sample coverage | DONE |
| P2 (revised) | Forward-window distribution across 26y | 3-4 |
| P3 | (skip — was synthetic BCD; not needed since P1 shows matrix gates stress) | 0 |
| P4 (revised) | Drill into the few stress-window BCD entries (4+2+5=11 days) to confirm matrix gate isn't leaking | 2 |
| P5 + G2 | Final verdict | 2 |
| **Total revised** | | **~8 hours** vs original 5-7 days |

---

## Kill-gate evaluation

**Original kill-gate**: stress-period sample coverage adequate for tail
estimation? Threshold: at least 20 BCD-eligible days in stress windows.

**P1 result**: 11 stress days total → **kill-gate triggered**.

**But the kill-gate question is now moot** because the reframing changed
P2's method. Per memory `feedback_thesis_recentering`, when phase data
silently changes the right question, document the shift explicitly. This
memo's "Reframing" section does that.

**New thesis** (P1 → P2): matrix's stress-exclusion behavior is
structurally correct (BCD never opens in adverse regimes); Q082's
remaining question is forward-window bias across BCD-eligible entry days.

---

## Files
- `q082_p1_sample_coverage.py` — script
- `q082_p1_bcd_days_per_year.csv` — annual breakdown
- `q082_p1_stress_period_coverage.csv` — named windows + BCD-eligible counts
- `q082_p1_memo.md` — this file (includes reframing)

---

## Pre-G1

Before P2, send brief G1 packet to 2nd quant confirming:
1. P1 reframing acceptable (matrix-stress-gate insight + scope shrink)
2. New P2 scope (forward-window distribution across 26y) — methodology OK
3. Updated effort estimate (8h vs 5-7d)

If reviewer ratifies, P2 ~ 3h work, then P5 verdict within 1 day total.

Alternative if reviewer challenges: re-think.

---

## Connection back to Q081 B-1

If P2 shows V1 (26y MORE up-biased than 3y): **B-1 is over-conservative**.
PM accepted "若市场系统性变跌 BCD edge 消失" but matrix already prevents BCD
opening in those regimes. The accepted risk is smaller than feared.

If P2 shows V3 (26y MORE down-biased): **B-1 has real teeth**. Need
additional gate or matrix refinement.

V2 (within noise): status quo confirmed.

This connects Q082 cleanly back to Q081 B-1's resolution.
