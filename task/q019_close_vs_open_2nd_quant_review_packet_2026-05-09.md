# Q019 Close vs Open VIX 2nd Quant Review Packet

- **Date**: 2026-05-09
- **Prepared by**: Quant Researcher
- **Audience**: 2nd Quant
- **Topic**: VIX timing convention sensitivity — close-based (backtest) vs open-based (live)
- **Span**: Tier 1 selector-level scan + Tier 2 full-history backtest comparison

---

## 1. Review Request

PM authorised Q019 Tier 1 + Tier 2 in sequence after MC's prior measurement (regime flip 9.71% in their 27-year sample) flagged that backtest uses VIX close while live uses intraday VIX near open. We tested whether this matters economically.

We are **not** asking:

- to reopen MC's 9.71% measurement (we replicated and confirmed it)
- to decide A/B/C path immediately (PM decides)
- to make any production change without further validation

We **are** asking:

> Is the Tier 1 + Tier 2 methodology sound, are the conclusions honest, and is the recommended next step (Tier 2.5 mixed-mode) the right gate before production decision?

Specific questions Q1–Q6 in §6.

---

## 2. Background

- Backtest (`backtest/engine.py`): reads `row["vix"]` = EOD close at each iteration step. Builds VIX 5d MA, IV history, peak_10d from the close-based series.
- Live (`web/server.py`, `notify/telegram_bot.py`): recommendation runs near market open, current VIX value is approximately the day's open (or first 1h-bar mark).
- Open-vs-close magnitude: mean abs diff $1.03 (4.84% of VIX); P90 $2.29 (10%); P99 $6.80 (24%). Real divergence happens.
- HIGH_VOL threshold sits at VIX 22, LOW_VOL at 15 — open vs close commonly straddles these.

---

## 3. Tier 1 — Selector-Level Scan

### Method
For each of 4868 trading days (2007-2026), build TWO VixSnapshots with `current_vix = close` vs `current_vix = open`, but identical 5d MA / peak_10d / IV history (close-based, matches live behavior). Run `select_strategy()` with each. Record diffs per layer.

### Results

| Layer | Flip count | Flip rate | vs MC reference |
|-------|-----------|-----------|-----------------|
| Regime (LOW/NORMAL/HIGH) | 461 | **9.48%** | MC 9.71% (Δ 0.23pp, replicates) |
| IV signal | 486 | 9.99% | — |
| Final strategy | 708 | 14.56% | — |
| Position action | 620 | 12.75% | — |

### Concentration — VIX bucket
| VIX | n_days | Regime flip% | Strat flip% |
|-----|--------|-------------|-------------|
| <15 | 1,539 | 9.4% | 12.7% |
| 15-20 | 1,558 | 6.7% | 12.3% |
| **20-25** | **884** | **23.1%** | **20.2%** |
| 25-30 | 433 | 1.8% | 17.3% |
| 30-35 | 196 | 0.0% | 23.5% |
| ≥35 | 253 | 0.4% | 8.3% |

**Threshold-driven concentration**: VIX 20-25 (straddles HIGH_VOL=22) accounts for 44% of all regime flips while representing 18% of days. Inside-band buckets (25-30, 30-35) show low regime flip but elevated strategy flip — driven by aftermath / VIX_RISING / ivp63 gates that reference current VIX level.

### Strategy flip direction (top 5)
| Direction | Count | % flip |
|-----------|-------|--------|
| BCD → Reduce/Wait | 123 | 17.4% |
| IC → Reduce/Wait | 77 | 10.9% |
| Reduce/Wait → IC | 75 | 10.6% |
| Reduce/Wait → IC_HV | 73 | 10.3% |
| Reduce/Wait → BCD | 65 | 9.2% |

**~60% of strat flips are "active ↔ Reduce/Wait"** — i.e. open vs close changes the "trade or not" decision, not just the strategy choice. This is the more concerning category.

### Tier 1 Verdict

regime flip 9.48% > 5% threshold → triggers PM/Planner review per pre-set criteria. PM authorised Tier 2.

---

## 4. Tier 2 — Full Backtest Comparison

### Method
1. Run baseline `run_backtest(start="2007-01-01", account=$500k)` with default close-based VIX
2. Monkey-patch `fetch_vix_history` to return OPEN values (full series substitution)
3. Run substituted backtest
4. Compare headline metrics + per-strategy + per-year diff + trade overlap

**Important caveat**: This substitutes the entire VIX series with opens. 5d MA, IV history, peak_10d all become open-based — NOT what live actually does. Live uses close-based history + intraday-current. So this is an **upper bound** on real impact.

### Results — Headline (19.3y, $500k start NLV)

| Metric | Close (baseline) | Open (substituted) | Δ |
|--------|------------------|---------------------|-----|
| Trades | 282 | 271 | -11 (-3.9%) |
| Win rate | 75.5% | 71.6% | -3.95pp |
| Stop rate | 0.7% | 0.7% | +0.03pp (unchanged) |
| Total PnL | $1,684,057 | $1,205,629 | **-$478,428 (-28.4%)** |
| End NLV | $2,184,057 | $1,705,629 | -$478,428 |
| **AnnROE** | **7.92%** | **6.55%** | **-1.37pp** |
| MaxDD | 7.92% | 12.37% | **+4.45pp** |
| Worst trade | -$44,117 | -$55,489 | -$11,373 |

### Per-strategy

| Strategy | Close n | Open n | Δn | Close PnL | Open PnL | Δ PnL |
|----------|---------|--------|-----|-----------|----------|-------|
| BULL_CALL_DIAGONAL | 72 | 77 | +5 | +$598k | +$395k | **-$204k** |
| IRON_CONDOR | 58 | 50 | -8 | +$272k | +$169k | -$103k |
| BULL_PUT_SPREAD | 38 | 35 | -3 | +$244k | +$146k | -$99k |
| IRON_CONDOR_HV | 77 | 75 | -2 | +$379k | +$323k | -$56k |
| BULL_PUT_SPREAD_HV | 28 | 24 | -4 | +$177k | +$138k | -$38k |
| BEAR_CALL_SPREAD_HV | 9 | 10 | +1 | +$13k | +$35k | +$22k |

**Counter-intuitive**: BCD has +5 MORE trades on open path but -$204k LESS PnL. Open-substitution routes BCD into more low-quality entries. Consistent with Tier 1's threshold-boundary concentration finding.

### Per-year hot spots

Worst 3 years (open underperforms close):
- 2018: -$108,845
- 2019: -$87,637
- 2021: -$77,451

These align with prolonged VIX 15-25 ranges where threshold-flip frequency is highest (Tier 1 concentration).

### Trade overlap

Only 56/282 = **19.9% trades shared** (same date + same strategy). 80% of trades are completely different between the two paths — but average per-trade PnL stays similar ($5,972 → $4,449). Cumulative difference comes from many small decisions, not a few catastrophic ones.

### Tier 2 Verdict

|ΔAnnROE| = 1.37pp upper bound → **MARGINAL** (between 0.5 and 2.0pp). Real live impact is bounded above by this; genuine impact lies somewhere in [0, -1.37pp].

---

## 5. Quant Recommendation

**Recommended path: Tier 2.5 mixed-mode test (1 day work)** before any production decision.

Rationale:
- Tier 2 upper bound -1.37pp is meaningful but doesn't isolate the source
- Most of Tier 1's flip rate came from current-VIX threshold proximity (VIX 20-25)
- Rolling 5d MA and IV history would smooth most divergence
- Heuristic estimate: real live impact is ~50-80% of upper bound, but not measured

**Tier 2.5 proposal**: modify engine to use VIX_open as `vix` (current decision) but VIX_close history for `vix_window` (5d MA, IV calc). Single-line engine change. Run with 1-day Q-style scope.

Decision matrix Tier 2.5 produces:
- |ΔAnnROE| < 0.5pp → real impact NEGLIGIBLE → write to governance, no production change (Path A)
- 0.5pp ≤ |ΔAnnROE| < 1.0pp → MARGINAL → PM decides A vs C
- ≥ 1.0pp of -1.37pp upper bound → most error from current-VIX substitution → consider Path C (align production to close-based)

**Not recommending direct Path C now** because:
- Production currently uses intraday VIX for live recommendation, which has informational advantage in spike scenarios
- Switching to close-based would delay decisions ~1 trading day
- Without Tier 2.5 evidence, can't determine if the 1pp+ AnnROE cost actually flows from current-VIX choice

---

## 6. Specific Questions for 2nd Quant

### Q1 — Tier 1 methodology
The Tier 1 substitution replaces ONLY `current_vix` while keeping 5d MA / peak_10d / IV history close-based, matching live behavior precisely. Is this the right snapshot composition, or did we miss any current-VIX-derived field that should also vary?

### Q2 — MC replication strength
Tier 1 produced regime flip 9.48% vs MC's 9.71% (Δ 0.23pp on 4868-day vs MC's 27y sample). Is this convergence meaningful evidence that the underlying selector behavior is consistent across HC/MC, or could it be coincidental?

### Q3 — Tier 2 upper-bound interpretation
We argue the full open-substitution overstates live impact because:
- Live uses close-based 5d MA / IV history (historical context unchanged)
- Only current-VIX uses open
- Most "drift" should come from current-VIX threshold proximity, not history changes

Is this reasoning sound? Or could rolling-stat changes (open-based 5d MA) actually be a non-trivial component?

### Q4 — Tier 2.5 vs accept upper bound
Two possible PM decisions:
- (a) Take the -1.37pp upper bound at face value, decide A/C without further measurement
- (b) Spend 1 day on mixed-mode Tier 2.5 to isolate current-VIX vs history components

Is (b) genuinely worth the day, or does the upper bound already give PM enough to decide?

### Q5 — Per-year concentration
2018 / 2019 / 2021 are the worst-impact years (~$80-110k each lost in open-path vs close-path). These are years with extended VIX 15-25 ranges. Is this concentration a signal that:
- (a) the impact is structural — happens reliably whenever VIX hovers near 22 threshold
- (b) the impact is sample-specific — those years had unusual current-vs-close divergence patterns

If (a), the impact will recur. If (b), future years may not show similar divergence.

### Q6 — Path C ("align production to close-based") risk assessment
Quant claims Path C is risky because live would delay reactions to intraday VIX spikes. Is this correct, or am I overstating? Consider: the production system's intraday alerts (SPEC-086 etc.) operate independently of the daily recommendation; switching daily-recommendation VIX to close-based wouldn't disable intraday alerts.

If Path C only delays the *daily recommendation* by one trading day (not the intraday alerts), is the risk lower than I represented?

---

## 7. Source Files

| Reference | Path |
|-----------|------|
| Tier 1 selector scan | `research/q019/close_vs_open_sensitivity.py` |
| Tier 2 backtest comparison | `research/q019/tier2_close_vs_open_backtest.py` |
| VIX OHLC source | `data/market_cache/yahoo__VIX__max__1d.pkl` (Open + Close fields) |
| Engine entry point | `backtest/engine.py:803` (where `vix = vix_eod` defaults) |
| MC reference | `sync/open_questions.md` Q019 (27-year regime 9.71% / aftermath 4.6%) |

---

## 8. Out of Scope for This Review

- Q053 line (already closed, R-20260509-07)
- Production code changes (PM decides path A/B/C after this review)
- Mixed-mode Tier 2.5 implementation (only proposed, not done)
- Any spec drafting

---

## 9. Recommended Output Format

Please address Q1–Q6 with **PASS / REVISE / REJECT** verdicts. Final overall:

- **APPROVE** Tier 1 + Tier 2 + Tier 2.5 recommendation as-is
- **APPROVE WITH ADJUSTMENTS** (specify which Qs need revision)
- **REJECT** specific paths (specify what to redo)

If you believe Path A (accept upper bound, document) is sufficient without Tier 2.5, please make the case and we will close Q019 immediately.

If you think Path C (align production to close) is safer than Quant represented, please flag specifically — this could collapse the entire chain.

---

*Quant Researcher, 2026-05-09*
