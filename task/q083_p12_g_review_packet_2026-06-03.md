# Q083 P12 G-review Packet — SPEC-113 Proposal: NORMAL × IV_LOW × BULL → BCD

**From**: Quant Researcher (1st quant)
**To**: 2nd Quant Reviewer
**Re**: New proposal after SPEC-112 withdrawal. Matrix cell route addition: `NORMAL × IV_LOW × BULL` from `reduce_wait` to `bull_call_diagonal`.
**Date**: 2026-06-03
**Severity**: High — this is the FOURTH verdict iteration on Q083 (P2 → P6 → P9 → P12). Want G-review before proposing SPEC.

---

## 0. Trail of prior verdicts (you've corrected me twice; this is iteration 4)

| Iteration | Verdict | Status |
|---|---|---|
| P2 (initial) | H3 regime-conditional 252d-range gate | Withdrawn (G1 caught circular validation + cutpoint overfit) |
| P6 (post-G1) | Shadow-test only, no production change | Withdrawn (G2 PM caught status-quo bias under "alpha standard") |
| P9 (post-G2 PM) | SPEC-112: IVP252 → IVP126 (止血) | **Withdrawn (I caught reconstruction-vs-cache mismatch)** — IVP63 cache value actually LOWER than IVP252 in current regime |
| **P12 (this)** | **SPEC-113: matrix cell `NORMAL × IV_LOW × BULL` → BCD (not reduce_wait)** | **Pending your review** |

Per PM directive: "做一轮深入研究和思考，不要怕大改动，在不增加大额风险的前提下，解决这个痛点". This iteration goes structural — matrix routing change instead of gate parameter tweak.

---

## 1. Decision type (declared up front per `feedback_decision_type_governs_significance_standard`)

**Execution-constraint decision** (matrix routing change). Standard: comparative across alternatives, not vs zero.

Compared dimensions:
- Mean PnL on the affected days
- Tail (worst trade bounded by SPEC-111 cap)
- Win rate / Sortino
- Operational engagement (can PM trade these days)

Not used: "is BCD per-trade Sharpe statistically > 0" (that's alpha standard, wrong for this decision type).

---

## 2. Root-cause reframe (P10)

P10 deep decomposition of 26y NORMAL × BULL universe (n=1515 days):

| Blocker | Share | Note |
|---|---:|---|
| iv_signal=LOW (matrix routes reduce_wait) | **67.5%** (1023) | **Dominant** — IVR cell-routing |
| IVP gate (NEUTRAL/HIGH cell but IVP out of band) | 23.6% (357) | Secondary |
| Both pass | 8.9% (135) | Where BPS actually opens |

**PM's "几乎不能开仓" is dominated by the iv_signal=LOW cell-routing, NOT by IVP gate**. SPEC-112's window-shortening targeted the wrong blocker.

### What "iv_signal=LOW" days actually look like

P10 characterization of those 1023 days:
- **Absolute VIX**: median 17.74, distributed 15-22 (NOT "low absolute vol")
- **IVR**: median 7.4 (spike-contaminated 52w range)
- **IVP**: median 10
- **Forward 21d outcomes**:
  - 29.6% see VIX rise ≥ +5vp (high vol-expansion frequency)
  - 16.7% see SPX drop > 5% (drawdown frequency)
  - 60.7% have positive forward SPX return

**This is "regime transition after spike, not fully recovered" — structurally distinct from LOW_VOL stable periods**.

### Comparative: NORMAL × IV_LOW vs LOW_VOL (Q081 P4's concern)

| Metric | NORMAL × IV_LOW (proposed) | LOW_VOL (Q081 P4's case) |
|---|---:|---:|
| n days | 1023 | 1793 |
| Median VIX | 17.74 | 12.74 |
| Forward 21d SPX worst | -16.7% | -29.3% |
| 21d max drop > 5% | **16.7%** | 7.0% |
| 21d max VIX rise ≥+5vp | **29.6%** | 24.3% |

**Counterintuitively, NORMAL × IV_LOW has MORE vol-expansion + drawdown risk than LOW_VOL**. This supports Q081 P4's "don't sell BPS here" logic even more strongly — but it also means **+vega instruments (BCD) get rewarded MORE here**.

---

## 3. The structural fix: route BCD, not BPS, into this cell

If BPS-here is wrong (vega tail risk), what about BCD-here?
- BCD is **+vega** (long_leg_vega > short_leg_vega)
- BCD is **+delta** (~0.4 net)
- The 29.6% vol-expansion frequency in this regime is a **structural reward for +vega**

If Q082 already validated BCD in LOW_VOL × BULL (where vol-expansion frequency is only 24.3%), BCD in NORMAL × IV_LOW × BULL (where vol expansion is 29.6%) should work AT LEAST as well.

P11 counterfactual confirms this.

---

## 4. P11 results — BCD synth across 26y in proposed new cell

Same BS-flat methodology as Q082 P6 (90 DTE δ0.70 long + 45 DTE δ0.30 short, sequential ladder, daily walk-forward).

### Headline aggregate

| Metric | NORMAL × IV_LOW × BULL (NEW PROPOSAL) | Q082 LOW_VOL × BULL (BASELINE, ratified) |
|---|---:|---:|
| n trades | 82 | 137 |
| Win rate | **73.2%** | 66.4% |
| Mean PnL/trade | **+$1,410** | +$1,016 |
| Median PnL | +$1,125 | +$895 |
| Worst trade | -$9,975 | -$6,909 |
| Mean period ROE | +10.68% | +10.47% |
| Sortino | +0.768 | +0.850 |

**Comparative reading**: new cell beats baseline on win rate (+6.8pp), mean PnL (+$394), median PnL (+$230). Slightly worse Sortino (-0.08, both above 0.5 threshold). Worst trade slightly deeper but bounded by SPEC-111 cap.

### Stratification (per memory `feedback_reviewer_ask_literally` — raw data not aggregates)

By IVP bucket within iv_signal=LOW universe:
| IVP | n | mean | median | worst | win rate |
|---|---:|---:|---:|---:|---:|
| [0,10) | 35 | +$1,799 | +$1,373 | -$5,849 | 77.1% |
| [10,20) | 18 | +$912 | +$1,025 | -$6,654 | 61.1% |
| [20,30) | 12 | +$2,234 | +$1,997 | -$1,866 | 83.3% |
| [30,40) | 17 | +$554 | +$1,050 | -$9,975 | 70.6% |

By VIX absolute level:
| VIX | n | mean | median | worst | win rate |
|---|---:|---:|---:|---:|---:|
| [15,16) | 17 | +$2,241 | +$1,467 | -$2,504 | 76.5% |
| [16,17) | 17 | +$1,606 | +$725 | -$4,445 | 58.8% |
| [17,18) | 12 | +$1,401 | +$1,518 | -$4,465 | 66.7% |
| **[18,19)** | 11 | **+$424** | +$912 | -$5,849 | 81.8% |
| **[19,20)** | 9 | **+$328** | +$1,050 | -$9,975 | 66.7% |
| [20,21) | 2 | +$1,596 | +$1,596 | +$1,149 | 100% |
| [21,22) | 14 | +$1,613 | +$1,861 | -$6,654 | 85.7% |

**All buckets positive mean**. Lowest-mean buckets: VIX 18-20 ($328-$424). No "cliff" — pattern is smooth.

---

## 5. Self-audit against prior failure modes

Per accumulated memory entries from Q081/Q082/Q083 G-reviews. Pre-emptive checklist:

| Failure mode | Memory entry | Applies to this proposal? |
|---|---|---|
| Status-quo bias | `status_quo_bias_in_verdicts` | NOT status-quo (proposing change). But CHECK: am I over-correcting to "change is good"? See §6. |
| Caveat sign error | `unquantified_caveat_sign_risk` | YES — skew bracket needed. Acknowledged in §7.1 below. |
| Circular validation | `circular_metric_validation` | NOT circular here — validating BCD with BCD PnL data, not IVP-derived stratification |
| Cutpoint overfit | `stratum_cutpoint_overfit` | LOW risk — pattern smooth across all IVP+VIX buckets, no single-point spike |
| Decision-type error | `decision_type_governs_significance_standard` | DECLARED §1 — comparative standard, not vs-zero |
| Reviewer ask literally | `reviewer_ask_literally` | Provided stratified tables in §4 |
| Short-DTE entry signal | `short_dte_entry_signal_cannot_gate_forward` | NOT proposing an entry signal gate. Cell-routing change is regime classification, not forward prediction |
| Thesis recentering | `thesis_recentering` | YES — Q083 thesis shifted from "fix IVP gate" to "fix cell routing". Documented in §0 and P10 memo |

---

## 6. Am I over-correcting? (Honest pre-emptive question)

After SPEC-112 was withdrawn, am I now anchored on "must propose a change" and missing that BCD-here might be wrong?

Counter-arguments to ratify BCD-here over reduce_wait:
- Reduce_wait has $0 PnL on these 1023 days; SPEC-113 has +$1,410 mean per trade
- Reduce_wait misses 29.6% vol-expansion frequency (genuine alpha opportunity)
- BCD's vega cushion is structurally suited

Counter-counter (challenge me):
- Is +$1,410 mean per trade enough margin to overcome real-chain skew haircut + cash opportunity cost?
- 82 trades over 23 years = 3.5/year. Block bootstrap CI not yet computed.
- Does the addition shift PM's exposure profile in a way that violates Q081 cash-bound thesis?

These are real questions. Open to your judgment.

---

## 7. Outstanding work (acknowledged caveats)

### 7.1 Block bootstrap CI not yet computed

n=82 for new cell, n=137 for baseline. Need block-bootstrap CI on mean PnL + Sortino. Estimate from prior work patterns: probably CI tight enough but should verify.

### 7.2 Skew bracket not run

Per Q082 P10 lesson (memory `unquantified_caveat_sign_risk`): BCD synth uses BS-flat IV. Real-chain skew direction for BCD (net +vega): skew steepening in DOWN moves makes short-leg σ expand faster, eroding net vega gain. Estimated haircut: 10-15% on mean PnL.

If haircut is 15%: mean PnL drops from $1,410 → $1,200. Still strongly positive and still beats Q082 baseline.

If haircut is 30% (pessimistic): mean PnL → $987. Still positive, slightly below Q082 baseline.

Should run before SPEC commits.

### 7.3 Sub-bucket sensitivity

VIX [18,19) and [19,20) sub-buckets have lowest mean (+$424, +$328). Question: should SPEC-113 route only VIX < 18 (or some other cutoff)?

My take: probably no. Smooth pattern, removing those 20 trades concentrates PnL only modestly. But worth your judgment.

### 7.4 State (c) not addressed

23.6% of NORMAL × BULL days are IVP-gate-blocked but matrix-says-BPS. SPEC-113 doesn't touch them. Separate question for potentially Q084.

---

## 8. Specific G-review questions

**Q-G3-1 (most important)**: Does the comparative standard hold up? On 4/5 dimensions BCD > reduce_wait. Is that the right framework for a matrix routing add?

**Q-G3-2 (skew direction)**: BCD net +vega. Skew expected to haircut by 10-15% (per Q082 P10). Acceptable margin remains. Agree?

**Q-G3-3 (sample size)**: n=82 over 23y for this new cell. Adequate for SPEC, or want me to run block bootstrap CI first?

**Q-G3-4 (interaction with Q081 cash-bound)**: SPEC-113 increases BCD frequency from ~6/year to ~10/year. PM is cash-bound. SPEC-111 cap bounds per-trade. Does this concentration concern you?

**Q-G3-5 (process)**: Q083 is now on iteration 4 with three withdrawn verdicts. Are my failure-mode self-audits adequate, or do you want a more structured pre-commit check?

---

## 9. Files attached
- `research/q083/q083_p10_deep_decomposition.py` + outputs
- `research/q083/q083_p11_bcd_in_normal_low_ivr.py` + outputs (q083_p11_bcd_normal_low_ivr_trades.csv)
- `research/q083/q083_p12_spec_113_proposal_2026-06-03.md` (full verdict text)

Prior iterations (deprecated but available for context):
- `research/q083/q083_p9_reversal_2026-06-03.md` (deprecated SPEC-112)
- `research/q083/q083_p6_final_verdict_2026-06-03.md` (deprecated shadow-only)
- `research/q083/q083_p2_verdict_signal_2026-06-03.md` (deprecated H3)

---

## 10. Reply format

`task/q083_p12_g_review_2026-06-XX_Review.md`. Q-G3-1 to Q-G3-5 ratify/challenge.

If ratified → I'll:
1. Run block-bootstrap CI + skew bracket as commit-gate validation
2. Draft `task/SPEC-113.md` for code change
3. Hand to dev (~0.5 day implementation — single matrix cell)

If challenged on any of Q-G3-1 through Q-G3-5 → I'll address before proceeding.

Estimated turnaround: 24-48h.

---

## 11. PM is waiting

PM's actual operational pain: can't open BPS, hasn't opened BCD since LOW_VOL last visited, currently parked in QQQ/SGOV. SPEC-113 gives PM ~10 BCD opportunities/year vs current ~0-2. The frequency issue resolved (subject to your review).

Hesitations welcome. The point of G-review is to catch what I miss.
