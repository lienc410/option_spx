# Q053 + C2 Full Session 2nd Quant Review Packet

- **Date**: 2026-05-09
- **Prepared by**: Quant Researcher
- **Audience**: 2nd Quant
- **Topic**: `/ES` research absorption → Q053 Grinding Decline → C2 engine investigation
- **Span**: From `/ES` line closure (Q012/Q051/Q052) to Q053 Tier 3 to Trade.pnl_pct Fast Path fix

---

## 1. Review Request

This packet covers a multi-step research chain that started from `/ES` line closure and ended with a small Fast Path fix to `Trade.pnl_pct`. The chain involved:

1. Absorbing `/ES` research findings into main strategy governance
2. Discovering main strategy has a hidden grinding-decline weakness
3. Investigating whether the worst trade was an engine bug
4. Reversing the engine-bug hypothesis after finding a display artifact

We are **not** asking:

- to reopen `/ES` thesis at $500k account (R-20260508-12/13 closed it)
- to redesign Q053 signal candidates (Tier 3 already evaluated 6)
- to revisit Trade.entry_credit storage (changing it would break 5+ consumers)

We **are** asking:

> Is the chain of conclusions sound, are the residual decisions correct, and is the C2 hypothesis reversal honest enough to close Q053?

Specifically (Q1–Q7 in §6 below):
- Are the 5 must-absorb principles + 3 calibrations correctly distilled from `/ES` data?
- Was the decision to convert 7 governance actions (not 3) the right decomposition?
- Is Q053 Tier 1's "main strategy lost in 2022" finding reliable given small sample?
- Is Q053 Tier 3's "no signal beats cost-benefit" verdict honest, or did we pick the wrong signal family?
- Is the C2 reversal correct? Is "no engine bug" really the right read?
- Is the Trade.pnl_pct fix complete? Should we have also changed entry_credit storage?
- Should Q053 close, or should C3 (regime-conditional strategy filter) open immediately?

---

## 2. Top-Level PM Objective (Unchanged)

PM standing objective remains:

> reasonably maximize account-level ROE

with explicit attention to drawdown control, margin stress, hidden concentration, and opportunity cost. This packet's findings should be evaluated against this objective, not against per-rule efficiency metrics.

---

## 3. Research Chain Overview

```
   ┌──────────────────────────────────────┐
   │ /ES Q012/Q051/Q052 closure           │
   │ (R-20260508-09 → R-20260509-01,      │
   │  5 rounds of research)               │
   └────────────┬─────────────────────────┘
                │
                ▼
   ┌──────────────────────────────────────┐
   │ R-20260509-02: absorption into main  │
   │   - 5 must-absorb principles         │
   │   - 3 calibrated cautions            │
   │   - 7 action items (A1-A7)           │
   └────────────┬─────────────────────────┘
                │
        ┌───────┼────────┬──────────┐
        ▼       ▼        ▼          ▼
       A1     A2/Q053  A3         A4-A7
       tool   Tier 1   Q041       governance
                │      appendix    docs
                ▼
       Q053 Tier 2 (multi-window pattern test)
                │
                ▼
       PM selects "Direction B" (signal refinement)
                │
                ▼
       Q053 Tier 3 (6 candidate signals evaluated)
                │
                ▼
       All 6 fail cost-benefit; "C2 hypothesis" emerges
       (worst trade looks like engine sizing bug)
                │
                ▼
       PM authorises C2 investigation
                │
                ▼
       C2 reverses: NOT engine bug, just display artifact
                │
                ▼
       Fast Path fix to Trade.pnl_pct
                │
                ▼
       Q053 line CLOSED
```

---

## 4. Step-by-Step Evidence Summary

### 4.1 `/ES` line closure background (already 2nd-Quant-reviewed)

5 rounds of `/ES` research concluded thesis is **scale-dependent**:
- Statistically valid in research form (Phase 4 + BSH, STOP=3.5, CI [+31, +460])
- But peak SPAN exposure ~36-45% NLV at $500k account in 2008/2020-style events
- Production-viable only at $1.5M+ NLV
- All 6 leverage-table recalibration variants failed
- All 3 PM redesign hypotheses (technical exit / roll / deep OTM + long DTE) failed

This was already 2nd-Quant-reviewed and CONFIRMED in earlier turns. **Not requesting re-review here.**

### 4.2 R-20260509-02 absorption (requesting Q1, Q2 review)

**5 must-absorb principles** (codified in `QUANT_RESEARCHER.md` "Short-Premium Risk Management Principles"):

1. **IV expansion 领先于 lagging signals** — direct evidence: `/ES` H1 study showed 244 trend-based exits with 84% loss rate, avg -$1,443/trade
2. **Main strategy entry-gated/regime-gated 风控是正确方向** — implication of #1
3. **`pnl_ratio` 止损 > credit-multiple 止损** — direct evidence: `/ES` H3 grid 0.05Δ + 180-DTE under STOP=3× had 48.9% stop rate vs baseline 26.5%
4. **2018 / 2022 grinding decline 是主策略隐藏风险** — opened as Q053
5. **IV expansion stress test 必须成为 spec-review 标准工具** — built as A1

**3 calibrated cautions**:

6. **Overlay-F scale-dependence 是 revisit hypothesis, not conclusion** — Trigger: BP utilization > 25% NLV → revisit
7. **资本效率必须用 stress-capital basis 评估**, not entry-margin %
8. **任何依赖人工执行的规则必须明确测试 T+0/T+1/T+2 delay sensitivity**

**7 action items** (mapping shown):

| # | Action | Type | Status |
|---|--------|------|--------|
| A1 | iv_expansion_stress_test tool | engineering | DONE |
| A2 | Q053 grinding decline review | research | DONE through Tier 3 |
| A3 | Q041 SPX CSP stress appendix | governance | DONE |
| A4 | Codify 5 principles | governance write | DONE in QUANT_RESEARCHER.md |
| A5 | Overlay-F revisit gate | monitoring trigger | DONE in open_questions Q036 |
| A6 | stress-capital basis spec-review | process | DONE in REVIEW_TEMPLATE §6.1 |
| A7 | T+0/T+1/T+2 delay sensitivity | process | DONE in REVIEW_TEMPLATE §6.1 |

### 4.3 Q053 Tier 1 (requesting Q3 review)

**Method**: Full main-strategy backtest 2007-2026, sliced into:
- 2018-Q4 (Oct-Dec 2018)
- 2022 full year
- "Other" (rest = baseline)

**Key result**:

| Window | n | Total PnL | WR | Avg PnL/trade | vs baseline |
|--------|---|-----------|-----|----------------|--------------|
| Other (baseline) | 260 | +$1,701,931 | 76.9% | +$6,546 | — |
| 2018-Q4 | 4 | +$10,074 | 75.0% | +$2,518 | -61% |
| **2022** | 18 | **-$26,778** | **55.6%** | **-$1,488** | **-123%** |

**Critical signal**: Stop rate in both stress windows = 0.0%. The pnl_ratio-based stop loss never fired in 2022 despite the negative-PnL year. This validates the `/ES` Principle 1 insight directly: lagging stops don't catch grinding decline.

### 4.4 Q053 Tier 2 (requesting Q3 review continuation)

Extended to 5 windows:

| Window | Pattern | Strategy outcome |
|--------|---------|------------------|
| 2011-Q3 (Eurozone, VIX peak 48) | spike-then-recover | ✓ +$97k, 100% WR |
| 2018-Q1 (Volmageddon, VIX peak 50) | spike-then-recover | ✓ +$88k, 100% WR |
| 2015-2016 (China/oil) | persistent grind | ⚠️ -$1k |
| 2018-Q4 (selloff) | persistent grind | ⚠️ avg -62% |
| 2022 (grinding bear) | persistent grind | ⚠️ -$26.8k |

**Pattern definition refined**: not "stress = weakness" but **"VIX persistent without spike to 40+ = weakness"**. Spike-and-recover windows actually benefit main strategy (EXTREME_VOL gate triggers, HIGH_VOL strategies thrive).

PM at this point chose **Direction B** (signal refinement) over A (immediate soft-overlay SPEC) and C (close).

### 4.5 Q053 Tier 3 (requesting Q4 review)

**6 candidate signals tested**:

| Signal | Cov(grinding) | Cov(spike) | FP rate | Δ avg PnL/trade | Score |
|--------|---------------|------------|---------|------------------|-------|
| T1: VIX 30d MA ≥ 20 AND SPX dd ≤ -5% | 68.8% | 56.6% | 19.1% | -$2,712 | 9/15 |
| T2: VIX 30d MA ≥ 22 AND VIX 30d min ≥ 17 | 51.4% | 49.2% | 22.5% | -$2,291 | 9/15 |
| T3: VIX 60d MA ≥ 20 + min ≥ 16 + SPX dd ≤ -5% | 49.0% | 33.3% | 15.5% | -$3,791 | 9/15 |
| T4: backwardation ≥ 30% of last 60 days | 3.7% | 50.3% | 11.2% | +$532 | 2/15 |
| T5: SPX 100d ret ≤ -5% AND VIX 30d MA ≥ 18 | 42.7% | 40.2% | 10.5% | -$923 | 7/15 |
| T6: VIX 60d MA + backwardation + SPX dd | 11.3% | 36.0% | 10.2% | -$726 | 4/15 |

**Cost-benefit projection** (50% size reduction on flagged trades, 19-year history):

| Signal | 19y Net Δ | 2022 improvement | Verdict |
|--------|-----------|------------------|---------|
| T1 | -$170,852 | +$1,086 | ❌ |
| T2 | -$195,959 | +$15,028 | ❌ |
| T3 | -$87,732 | +$2,725 | ❌ |
| T4 | -$115,850 | $0 | ❌ |
| T5 | -$119,587 | +$11,683 | ❌ |
| T6 | -$104,255 | -$3,286 | ❌ |

**All 6 signals fail cost-benefit**. Best (T3) loses $88k over 19 years to save $2.7k in 2022.

**Strategy-level alternative discovery**: 2022 losses concentrated in put-side strategies:

| Strategy | 2022 PnL | Other-years avg | Other WR |
|----------|----------|------------------|----------|
| BULL_PUT_SPREAD | -$12,537 | +$7,138 | 77.8% |
| BULL_PUT_SPREAD_HV | -$7,393 | +$7,081 | 92.3% |
| IRON_CONDOR_HV | -$11,495 | +$6,009 | 92.3% |
| BEAR_CALL_SPREAD_HV | **+$4,647** | +$1,255 | 57% |

If 2022 had suppressed put-side: total would have been **+$4,647** instead of **-$26,778** (Δ +$31,425). But this is C3-class architectural change, not a signal filter.

### 4.6 C2 Investigation (requesting Q5 review)

**Original C2 hypothesis**: 2022 worst trade (-$24,606, 92% of year's losses) looked like an engine sizing edge case:
- displayed entry_credit: -$34
- contracts: 6.89
- displayed pnl_pct: -72,058%

**Investigation method**: Reproduce trade at exact entry conditions (SPX 4583, VIX 18.6, BPS Δ0.30/Δ0.15 DTE 30) using `find_strike_for_delta` and `put_price`.

**Reproduction result**:

| Metric | Real value |
|--------|------------|
| Per-share net credit | +$34.48 (positive) |
| Per-contract credit | $3,448 |
| **Total credit collected** | **$23,757** (across 6.89 contracts) |
| Per-contract max loss | $11,052 |
| Total max-loss exposure | $76,148 (~15% NLV, normal bp_target) |
| Risk/reward | 31.2% credit / max_loss (normal BPS) |
| Actual loss | $24,606 = **32% of max loss** (normal BPS distribution after SPX -4.2% in 9 days) |

**Conclusion**: This was a **completely normal BPS** that lost a moderate amount on a regime-driven SPX drop. **NOT an engine bug.**

**Two display/semantic bugs identified** (both real but small):

- **Bug A**: `Trade.entry_credit` field comment says "positive = credit received, negative = debit paid" but field stores `position.entry_value` directly (per-share signed index points). For credit spreads: stores -$34.48 (negative = credit), not +$34.48 dollars.
- **Bug B**: `Trade.pnl_pct` property = `exit_pnl / abs(entry_credit) × 100` divides total dollars by per-share signed index points. Produces meaningless multi-thousand-percent values.

### 4.7 Fast Path fix (requesting Q6 review)

**Decision**: Fix the `pnl_pct` property + clarify `entry_credit` field comment. **Do not** change `entry_credit` storage value.

**Rationale for not changing storage**:
- `entry_credit` is read by 5+ consumers: `web/server.py:1548`, `backtest/research_views.py:43`, `scripts/export_backtest_trade_detail.py:214/294`, `backtest/prototype/SPEC-030_intraday_stop.py:116/164`, `doc/tieout_2_2026-05-02/run_tieout2.py:36`
- Several consumers (notably the export script) use `entry_credit` AS per-share signed index points (correct for their purpose)
- Changing storage requires coordinated update of all consumers — out of Fast Path scope
- Changing only the comment + the `pnl_pct` property is single-file, ≤ 30 lines, safe

**Actual fix** (`backtest/engine.py:96-130`):

```python
# Before (line 96):
entry_credit: float = 0.0   # positive = credit received, negative = debit paid

# After:
entry_credit: float = 0.0   # NET ENTRY VALUE PER SHARE (index points, signed):
                            #   negative = credit received  (e.g. BPS, IC)
                            #   positive = debit paid       (e.g. BCD, BPS_DEBIT)
                            # Field name is historical; do not assume "positive = credit".

# Before (line 117):
return self.exit_pnl / abs(self.entry_credit) * 100

# After:
position_value = abs(self.entry_credit) * 100 * self.contracts
if position_value == 0:
    return 0.0
return self.exit_pnl / position_value * 100
```

**Verification**:
- 270/270 tests PASS after fix
- 2022-04-04 BPS pnl_pct: -72,058% → **-104.6%** (sensible BPS loss)
- All 282 trades pnl_pct now in -211% to +95% range (no more outliers > ±500%)

---

## 5. Q053 Closure Decision (requesting Q7 review)

After C2 reversal, the picture is:

- 2022 weakness is **genuinely regime-driven**, not engine artifact
- No signal-based entry filter passes cost-benefit
- The only viable intervention is **C3** (regime-conditional strategy filter — suppress put-side in detected grinding-decline)
- C3 requires Tier 4 research + architecture spec, ~2 weeks

**Decision recorded in R-20260509-05**: Close Q053 line. C3 stays as standing research candidate, triggered by another 2022-style year OR PM explicit prioritization.

**Durable governance value preserved**:
- A1 tool (`research/tools/iv_expansion_stress_test.py`)
- 5 Short-Premium Risk Management Principles in `QUANT_RESEARCHER.md`
- REVIEW_TEMPLATE §6.1 stress-capital + execution-drift checks
- pnl_pct fix prevents future researchers from mis-reading trade records

---

## 6. Specific Questions for 2nd Quant

### Q1 (R-20260509-02 absorption — 5 principles)

Are the 5 must-absorb principles correctly distilled from `/ES` evidence? Specifically:

- Principle 1 (IV expansion ahead of lagging signals): is the `/ES` H1 evidence (244 trend exits, 84% loss rate, -$1,443 avg) sufficient to support a general principle, or is this overgeneralization from a single strategy family?
- Principle 3 (`pnl_ratio` > credit-multiple): does the `/ES` H3 evidence (Δ0.05+DTE180 stop rate 48.9%) translate to main strategy, where stop rates are normally < 5%?

### Q2 (action mapping — 7 vs 3)

Was the conversion from "absorption" to 7 discrete actions the right decomposition? Was anything important left out, or should some be merged/dropped?

### Q3 (Q053 Tier 1+2 sample size)

Tier 1 had 4 trades in 2018-Q4 and 18 trades in 2022. Tier 2 added 13 trades in 2011-Q3, 13 in 2015-2016, 6 in 2018-Q1.

- Is the 2022 finding (-$26.8k, 18 trades) statistically robust enough to call "systematic weakness"?
- Is the spike-recover vs grinding-decline distinction (3/3 grinding lose, 2/2 spike-recover win) reliable given samples this small?

### Q4 (Q053 Tier 3 signal verdict)

All 6 signals failed cost-benefit. But:

- Did we test the right signal family? (We focused on VIX-based and SPX-drawdown-based; not tested: cross-asset signals like credit spreads, term structure shape, sector rotation, etc.)
- Is the 50% size-reduction projection (used in cost-benefit) the right severity? Maybe a stricter "skip new entries when flagged" would change the verdict.

### Q5 (C2 reversal correctness)

- Is the reproduction methodology sound? (We used `find_strike_for_delta` and `put_price` at the exact entry conditions and matched the trade record's spread_width within 5 points.)
- Is the conclusion "this is a normal BPS, not an engine bug" actually correct? Or are we missing something else that made this trade go wrong?

### Q6 (Trade.pnl_pct fix)

- Is the fix mathematically correct?
- Does the design choice "fix property only, don't change storage" risk leaving consumers in an inconsistent state? Specifically: any consumer that uses `entry_credit` AS dollar credit (rather than per-share signed) would still be broken. Should we audit consumers more thoroughly?

### Q7 (Q053 closure correctness)

- Should Q053 close as recommended, or should C3 (regime-conditional strategy filter) open immediately given the strategy-level evidence (-$31k savings if put-side suppressed in 2022)?
- Is the "trigger to revisit" condition (another 2022-style year OR PM explicit prioritization) sound, or too lax?

---

## 7. Source Files (for cold review)

### Code/data references

| Reference | Path |
|-----------|------|
| Trade dataclass + fix | `backtest/engine.py:88-130` |
| iv_expansion_stress_test (A1) | `research/tools/iv_expansion_stress_test.py` |
| Q041 stress matrix script | `research/q012/a3_q041_stress_matrix.py` |
| Q053 Tier 1 | `research/q053/grinding_decline_review.py` |
| Q053 Tier 2 | `research/q053/tier2_pattern_and_signal.py` |
| Q053 Tier 3 | `research/q053/tier3_signal_refinement.py` |
| Q041 packet (with A3 appendix §11) | `doc/q041_execution_prep_packet_2026-05-05.md` |

### RESEARCH_LOG entries (chronological)

| Entry | Topic |
|-------|-------|
| R-20260509-02 | `/ES` absorption — 5 principles + 3 cautions + 7 actions |
| R-20260509-03 | A1/A2/A3 executed; Q053 Tier 1 finds 2022 weakness |
| R-20260509-04 | Q053 Tier 2 + Tier 3; PM selects Direction B |
| R-20260509-05 | C2 reversal; pnl_pct fix; Q053 closes |

### Governance documents

| Document | Section |
|----------|---------|
| QUANT_RESEARCHER.md | "Short-Premium Risk Management Principles" (§ at end) |
| REVIEW_TEMPLATE.md | §6.1 short-premium standard checks |
| sync/open_questions.md | Q036 Overlay-F revisit gate, Q053 + Standing Principles section |

---

## 8. Out of Scope for This Review

- `/ES` Q012/Q051/Q052 line itself (already 2nd-Quant-confirmed closed)
- Q041 paper-trading execution scope (A3 appendix is risk visibility only, not scope change)
- Main strategy production code paths (the `pnl_pct` fix is single-property, no engine math change)

---

## 9. Recommended Output Format

Please address Q1–Q7 in §6 with:

- **PASS / REVISE / REJECT** verdict per question
- For REVISE: specific change requested
- For REJECT: which finding is unsupported and why

Final overall verdict:

- **APPROVE** absorption + Q053 closure as recommended
- **APPROVE WITH ADJUSTMENTS** (specify which Qs need revision)
- **REJECT** specific paths (specify what to redo)

If you believe a question I didn't list deserves a review (e.g., a methodology concern in Tier 3 signal evaluation), please flag it explicitly.

---

*Quant Researcher, 2026-05-09*
