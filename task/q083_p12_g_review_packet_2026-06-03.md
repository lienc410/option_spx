# Q083 G-review Packet — SPEC-113 Proposal

**From**: Quant Researcher
**To**: 2nd Quant Reviewer
**Date**: 2026-06-03
**Re**: Matrix cell route addition `NORMAL × IV_LOW × BULL → BCD` (replaces current `reduce_wait`)
**Standard**: Execution-constraint decision (comparative, not vs-zero significance) per `feedback_decision_type_governs_significance_standard`

---

## 1. Proposal

Single cell change in `strategy/catalog.py` `CANONICAL_MATRIX`:

```diff
 "NORMAL": {
     "HIGH":    {"BULLISH": "bull_put_spread", ...},
     "NEUTRAL": {"BULLISH": "bull_put_spread", ...},
-    "LOW":     {"BULLISH": "reduce_wait",        "NEUTRAL": "reduce_wait", "BEARISH": "reduce_wait"},
+    "LOW":     {"BULLISH": "bull_call_diagonal", "NEUTRAL": "reduce_wait", "BEARISH": "reduce_wait"},
 }
```

Only `LOW × BULLISH` cell changes. `LOW × NEUTRAL/BEARISH` remain reduce_wait.

---

## 2. Root cause (P10)

PM complaint: "几乎不能开仓". Decomposition of 26y NORMAL×BULL universe (n=1515):

| Blocker | Share |
|---|---:|
| **iv_signal=LOW cell-routing** (matrix → reduce_wait) | **67.5%** (n=1023) |
| IVP gate (NEUTRAL/HIGH cell but IVP out of band) | 23.6% (n=357) |
| Both pass → BPS opens | 8.9% (n=135) |

**The dominant blocker is cell-routing, not the IVP gate**. SPEC-112 (IVP window shorten) targeted the wrong blocker — withdrawn.

## 3. Characterization of the 1023 blocked days

P10 forward-outcome analysis:

| | NORMAL × IV_LOW (proposed cell) | LOW_VOL × BULL (Q082's BCD cell) |
|---|---:|---:|
| Median VIX | 17.74 | 12.74 |
| 21d max VIX rise ≥+5vp | **29.6%** | 24.3% |
| 21d SPX max drop > 5% | 16.7% | 7.0% |
| Forward SPX positive | 60.7% | (similar) |

**These are post-spike regime-transition days, not stable low-vol.** Vol expansion frequency is HIGHER than LOW_VOL. Means:
- BPS here would be punished (Q081 P4's correct concern)
- BCD here is STRUCTURALLY REWARDED (long +vega benefits from vol expansion)

## 4. P11 BCD counterfactual (BS-flat synth, 26y, sequential ladder)

Same methodology as Q082 P6 (ratified):

| | NORMAL × IV_LOW × BULL (new) | Q082 LOW_VOL × BULL (baseline) |
|---|---:|---:|
| n trades | 82 | 137 |
| Win rate | **73.2%** | 66.4% |
| Mean PnL | **+$1,410** | +$1,016 |
| Median PnL | +$1,125 | +$895 |
| Worst trade | -$9,975 | -$6,909 |
| Mean period ROE | +10.68% | +10.47% |
| Sortino | +0.768 | +0.850 |

New cell beats baseline on win rate, mean, median. Worst-trade tail slightly deeper but bounded by SPEC-111 cap ($22k @ 60% liquid).

### Stratification (no cutpoint sensitivity — pattern smooth)

By IVP bucket (all positive):
| IVP | n | mean | win |
|---|---:|---:|---:|
| [0,10) | 35 | +$1,799 | 77% |
| [10,20) | 18 | +$912 | 61% |
| [20,30) | 12 | +$2,234 | 83% |
| [30,40) | 17 | +$554 | 71% |

By VIX absolute level (all positive):
| VIX | n | mean | win |
|---|---:|---:|---:|
| [15,16) | 17 | +$2,241 | 76% |
| [16,17) | 17 | +$1,606 | 59% |
| [17,18) | 12 | +$1,401 | 67% |
| [18,19) | 11 | +$424 | 82% |
| [19,20) | 9 | +$328 | 67% |
| [20,21) | 2 | +$1,596 | 100% |
| [21,22) | 14 | +$1,613 | 86% |

No cliff. Lowest sub-buckets (VIX 18-20) still positive.

---

## 5. Risk envelope

- **No new tail mechanism**: BCD is +vega, opposite of BPS. Q081 P4's vega-tail concern (BPS in low-IV) does NOT apply.
- **SPEC-111 cap bounds per-trade $ exposure**: worst -$9,975 < cap $22k.
- **Sequential ladder preserves "one BCD at a time"**: post-SPEC-113, BCD frequency ~6/year (LOW_VOL) + ~4/year (new cell) = ~10/year. Bounded.
- **No matrix structural change**: NEUTRAL/BEARISH stay reduce_wait. BULLISH trend filter still applies.

---

## 6. Caveats (acknowledged, may need check)

**6.1 Skew bracket not yet run** (Q082 P10 lesson). BCD synth uses BS-flat IV. Real chain skew steepens short-leg σ faster than long-leg σ in DOWN moves → real net vega gain < synth shows. Expected haircut 10-15% on mean PnL. If 15%: $1,410 → $1,200 (still beats baseline). If 30% pessimistic: $987 (slightly below baseline, still positive).

**6.2 Block-bootstrap CI not yet run**. n=82 over 23y. Pattern is smooth across 4 IVP buckets + 7 VIX buckets, but CI on aggregate not computed.

**6.3 PM is cash-bound (Q081)**. SPEC-113 increases BCD frequency from ~6/year → ~10/year. SPEC-111 cap (60% liquid) bounds per-trade. Total cash committed scales with frequency.

---

## 7. Q-G3 review questions

**Q-G3-1**: Comparative standard right? BCD beats reduce_wait on PnL / win / Sortino / engagement. Reduce_wait wins only on "$0 = no risk". With SPEC-111 cap, comparison clearly favors BCD. Agree?

**Q-G3-2**: Skew bracket direction (Q082 P10 found BCD synth understates DOWN drag ~13%). Should this block SPEC commit, or acceptable to run as commit-gate validation?

**Q-G3-3**: VIX 18-20 sub-bucket lowest mean (+$424, +$328). Should SPEC carve those out (VIX < 18 sub-condition), or keep full 15-22?

**Q-G3-4**: Q083 is iteration 4 (P2 withdrawn → P6 withdrawn → P9 withdrawn → P12). What process check should be added before SPEC commits, beyond your G-review?

**Q-G3-5**: NEUTRAL/BEARISH variants stay reduce_wait. Should NEUTRAL also route to BCD (no +delta tailwind, weaker structural case)? Default: no.

---

## 8. Files
- `research/q083/q083_p10_deep_decomposition.py` + outputs
- `research/q083/q083_p11_bcd_in_normal_low_ivr.py` + `q083_p11_bcd_normal_low_ivr_trades.csv`
- `research/q083/q083_p12_spec_113_proposal_2026-06-03.md` (full verdict)

---

## 9. Reply format

`task/q083_p12_g_review_2026-06-XX_Review.md`, Q-G3-1 through Q-G3-5.

On ratify → run block-bootstrap CI + skew bracket as commit-gate validation, then draft `task/SPEC-113.md` for dev.

On challenge of Q-G3-1 or Q-G3-2 → address before proceeding.
