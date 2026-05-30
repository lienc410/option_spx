# ChatGPT 2nd Quant Review Packet — 2026-05-28 ~ 05-29

**From**: Quant Researcher (Claude / Opus 4.7)
**To**: ChatGPT (2nd Quant external review)
**Date**: 2026-05-29
**Scope**: 3 research lines completed in 24-hr window — Q078 → SPEC-108, SPEC-109, Q079
**Format**: cold-read self-contained. Provide review verdict per line + cross-cutting comments.

---

## 0. Context

PM trades SPX put credit spreads in a Schwab + E*Trade PM (portfolio margin) account, ~$500k NLV.

Strategy stack (parents, **NOT** modified in any of the work below):
- **SPEC-103** — V1-V7 portfolio-level vetoes (regime / drawdown)
- **SPEC-104 Arch-3** — sleeve governance caps (80% SPX_PM / 50% short-vol / 40% second-leg-episode / etc.)
- **SPEC-105 v2** — Gate F booster (90% benign-regime BP cap up)
- **SPEC-077** — exit rules (21 DTE roll / 60% profit / min 10d held / stress force-exit)
- **Selector** (`strategy/selector.py`) — VIX regime + IVP + trend → strategy routing

3 new research lines closed in last 24 hrs:

| Line | Type | Outcome | Status |
|---|---|---|---|
| **Q078 / SPEC-108** | strategy execution-layer overlay | V3 daily-cluster cadence + S3 sizing ladder | DONE, deployed |
| **SPEC-109** | journal UX enhancement | Greek attribution KPI strip + area fill | DONE, deployed |
| **Q079** | regime-boundary hardness research | DROP — below threshold | CLOSED |

---

## 1. Q078 → SPEC-108 — Selector-Gated SPX Execution Ladder

### 1.1 Trigger

PM observed 8 SPX BPS spreads all clustered at 6/18 expiry. Questioned whether systematic "ladder" entries (vs ad-hoc clustered entries) would improve portfolio outcomes.

### 1.2 Research path (11 phases, 5 G-reviews, 2 days)

```
Framing → P0 anchored → P1a cadence attribution
  → G2 PASS
  → P1b-1/-2 sizing sweep (S3 = 3 contracts)
  → G2.5 PASS
  → P2 (eff_count metric correction) → P2 REVISED (daily MTM smoothing fix)
  → P3 crisis windows + walk-forward + bias
  → G4 REVISE
  → P4 portfolio integration (decision-grade)
  → G4 PASS (9 SPEC revisions R1-R9)
  → SPEC-108 DRAFT
  → Comprehensive Audit
  → AUDIT PASS (7 micro-revisions R1-R7)
  → PM APPROVED
  → Developer implemented (commit 50a72df)
  → Quant fidelity review PASS
  → SPEC-108 Status: DONE
```

### 1.3 Headline findings

| Metric | Baseline (SPEC-104+105v2) | With ladder | Δ |
|---|---|---|---|
| Net Ann ROE | 8.21% | 10.02% | **+1.80pp mean** (CI [+1.61, +1.97]) |
| MaxDD | -8.71% | -7.40% | **+1.32pp** improved |
| W20d | -7.04% | -5.88% | +1.16pp improved |
| W63d | -8.66% | -5.06% | +3.59pp improved |
| Sharpe | 2.02 | 3.21 | +1.20 |
| Crisis windows improved | 5/5 (incl COVID 2020 — combined REDUCES baseline COVID loss by +$15k) | | |

**Bias caveat**: P4 mean +1.80pp is upper bound. Stage-1-shadow-only path (Option B for bias resolution) realistic deflated range: **+0.8pp to +1.3pp**.

### 1.4 Thesis reframing (mid-research)

PM's original hypothesis: "ladder improves expiry diversification (8 spreads at one expiry)."

After P2 fixed an `eff_count` measurement bug (was over-counting by grouping by exit_date instead of monthly bucket; over-counted 200-800x), the **diversification claim collapsed to noise**.

But cadence overlay alone still produced material ROE addition. **Final thesis**: SPEC-108 is **ROE-cadence overlay, NOT diversification fix**. PM accepted reframing.

### 1.5 Methodology choices (please review)

1. **5% NLV worst-trade gate** (replaces earlier 1% NLV gate based on PM's actual risk tolerance)
2. **Noise threshold framework**: any portfolio metric Δ < 0.5pp annualized treated as noise, NOT signal
3. **Daily MTM smoothing**: linear distribute trade PnL across hold days (avoid single-exit-day spike distorting W20d/W63d)
4. **2-axis stratified bootstrap** (strategy × year × VIX bucket) — 20 seeds for CI
5. **eff_count fix**: group by monthly-expiry bucket, NOT exit_date
6. **Bias correction = Option B (Stage-1 shadow)**: real-live shadow validates trade quality vs P4 expectation; explicitly NOT engine-without-filters approach
7. **V3 daily-cluster chosen over V1b weekly catch-up** despite V1b slightly better on tail metrics — because portfolio-level diff < noise threshold, V1b operationally lighter, but PM accepted daily check; V1b documented as historical alternative with explicit Developer prohibition (`Developer must not implement V1b under SPEC-108`)

### 1.6 SPEC-108 final shape

```
Cadence:       daily selector evaluation
               ≤ 1 entry per 5-trading-day cluster (≈35 action days/yr)
Sizing:        S3 = 3 contracts (≈7.5% BP) — fixed
Strategy:      agnostic (selector-provided per VIX regime — BPS / IC / BCD / HV variants)
Exit:          SPEC-077 unchanged
Gates:         concurrency (1/strategy, 2 for IC_HV) + BP ceiling 35% NORMAL
Stage 1:       SHADOW-ONLY MANDATORY (LADDER_MODE_DEFAULT="shadow", env-default)
Stage 2:       PM signoff + ≥10 shadow entries + 7 advancement conditions
Stage 3:       PM-discretionary
```

**Production safety**: `production_order_allowed(eligible, mode)` returns False unless mode=="active". 2 CI tests (AC-108-17/18) enforce that shadow default cannot accidentally activate production.

### 1.7 Monitoring obligations (Stage 1 shadow standing)

8 monitors: signal rate / skip reason distribution / BP ceiling skip / theoretical PnL / action burden / Q042+SPX overlap / shadow trade quality / **ladder-only W20d+W63d incremental tail monitor** (added per audit R1).

### 1.8 Questions for ChatGPT on SPEC-108

| # | Question |
|---|---|
| **Q1** | 5% NLV worst-trade gate — is 5% the right ceiling for PM-scale account? Or too lenient? |
| **Q2** | Noise threshold 0.5pp annualized ROE — is this calibrated correctly for SPX BPS strategy variance? |
| **Q3** | Option B (Stage-1 shadow) for bias correction — does this actually resolve selection bias, or just defer the question to live data with no statistical resolution? |
| **Q4** | Daily MTM smoothing (linear distribute PnL across hold days) — is this an appropriate smoothing, or does it artificially suppress legitimate tail spikes that matter for W20d/W63d governance? |
| **Q5** | 2-axis stratified bootstrap (strategy × year × VIX bucket), 20 seeds — sufficient for distribution-level CI? Should add 3rd axis (e.g., trend bucket)? |
| **Q6** | V3 daily-cluster vs V1b weekly catch-up decision: portfolio-level diff < 0.5pp noise but V1b operationally lighter. Is choosing V3 only because "downstream tests already V3-based" a sufficient justification, or does V1b deserve a separate Stage-1 shadow as well? |
| **Q7** | Stage 2 advancement ≥10 shadow entries minimum — adequate for limited production, not full? At 35 entries/yr expected, 10 = ~3.5 months. Should bar be higher? |
| **Q8** | Strategy-agnostic ladder consuming selector verdict — is there a risk that ladder amplifies selector errors (e.g., if selector overweights IC in some regime, ladder mechanically reinforces)? |

---

## 2. SPEC-109 — Journal Greek Attribution Chart UX Enhancement

### 2.1 Context

PM looks at a `/journal` chart that decomposes daily PnL for open SPX put credit spreads into Δ / Γ / Θ / V / Residual using BS reverse-solve (Path A, until broker chain greeks Path B is wired in).

Method (frozen, NOT modified by SPEC-109):
1. Per leg per day: pull `day_close` from `q041_massive_snapshot/{date}/SPX.parquet` (prefer SPXW ticker)
2. Reverse-solve IV via brentq on `bs_put(S, K, T, r=0.05, q=0.013, σ) = mark`
3. Compute BS greeks at solved IV
4. Decompose ΔPnL = `Δ·ΔS + ½Γ·ΔS² + Θ·Δt + V·ΔIV + Residual` (first-order Taylor, t0 greeks, left-Riemann)
5. Spread convention: short put side=-1, long put side=+1
6. Daily MTM via spread credit reconciliation at edge days

Current cum residual ~5% (PM accepted as acceptable for 1st-order Taylor framework).

### 2.2 SPEC-109 UX changes (just shipped)

PM was misreading "gamma 一路向下" as anomaly; actual fact: short put spread = net short gamma, gamma_attr structurally negative regardless of SPX direction. Solution:

| Tier | Change |
|---|---|
| A1 | 4-card KPI strip above chart: **Premium captured** (Θ + max(V,0)) / **Vol risk paid** (Γ + min(V,0)) / **Direction** (Δ) / **Net attribution** + Closure% |
| A2 | Footer 2 lines: formula + r/q disclosure + teaching line "Short put spread = net short gamma · 健康标准: \|Θ+V\| > \|Γ\|" |
| A3 | Closure% threshold 1% green/orange, displayed in Net attribution card |
| B1 | Theta = green area fill upward from zero; Gamma = red area fill downward from zero; Δ/V/Residual stay thin lines |
| B2 | Synthetic gap-day visual: gray band + tooltip "⚠ Chain data gap · BS interpolated" + dashed line segment crossing synthetic days |

Algorithm completely untouched. `scripts/compute_greek_attribution.py` frozen.

### 2.3 Known limitations of Path A attribution (acknowledged in design)

- 1st-order Taylor only — Vanna / Volga / Charm / 2nd-order cross terms all flow into Residual
- t0 greeks (left-Riemann) — large ΔS days lose precision (trapezoidal would be ~1pp better residual)
- IV freeze synth on chain-gap days (`q041_massive_snapshot` has multi-day gaps; synthetic_t0/_t1 flag added)
- Entry-credit split adjustment for open positions (cm/cl chain marks shifted symmetrically so ms_t0 - ml_t0 = broker entry credit — necessary for unrealized reconciliation but slight IV bias)

### 2.4 Questions for ChatGPT on SPEC-109

| # | Question |
|---|---|
| **Q9** | "Premium captured = Θ + max(V, 0)" / "Vol risk paid = Γ + min(V, 0)" — is this the right slicing for short-premium strategy comprehension? Or should Vega be its own row (treated as a separate exposure)? |
| **Q10** | Closure% threshold of 1% (\|Actual - Net\| < 1% × \|Actual\|) for green badge — too strict for 1st-order Taylor with 5% baseline residual? |
| **Q11** | KPI calculation uses `payload.totals` (sum across all trades + all dates) rather than terminal endpoint of cum series. For Stage 1 (1 open position) these match; for multi-position should they sum trade-by-trade then aggregate, or per-day then cumulate? |
| **Q12** | Is showing both "Net attribution" (Σ of 5 greeks) AND "Actual" (broker truth) on same card a clean reconciliation framework, or will PM confuse "net" as "PnL"? |
| **Q13** | Area fill green Θ vs red Γ — does this visual mass comparison risk misleading PM in mixed-regime periods where Θ and Γ alternate sign (e.g., 7d/30d rolling on choppy weeks)? |

---

## 3. Q079 — VIX=15 Boundary Hardness Research

### 3.1 PM observation

"Current selector has hard split at VIX=15 (LOW_VOL → NORMAL). If VIX=15.3 with IVP=20, shouldn't it route to LOW_VOL strategies?"

### 3.2 Boundary structure (verified)

Hard thresholds (no hysteresis):
- LOW_VOL: VIX < 15
- NORMAL: 15 ≤ VIX < 22
- HIGH_VOL: 22 ≤ VIX < 35

IV signal thresholds (independent):
- IV HIGH: IVP > 70
- IV LOW: IVP < 40

At VIX=14.9 (LOW_VOL) vs 15.3 (NORMAL), with IVP=20:

| Trend | LOW_VOL side | NORMAL side | Δ |
|---|---|---|---|
| BULLISH | Bull Call Diagonal (BCD, debit) | Reduce/Wait (SPEC-060) | open → no open |
| NEUTRAL | Iron Condor (45 DTE) | Reduce/Wait | open → no open |
| BEARISH | Reduce/Wait | Bear Put Spread (defensive debit) | wait → defensive |

Cliff structurally hard — 0.4 VIX point flips strategy entirely. PM intuition: physics doesn't justify the cliff.

### 3.3 Tier 2 P1 quantification (26y, 6639 trading days)

**Edge cell definition**: VIX ∈ [15, 16) + IVP ∈ [20, 40) + trend ∈ {BULLISH, NEUTRAL} + selector = "Reduce / Wait"

**Decision thresholds** (set by PM): < 5 days/yr → drop; ≥ 10 days/yr → full Tier 2

| Stat | Value |
|---|---|
| Total triggered days | **38** over 26.4 years |
| Avg per year | **1.4** |
| Extended buffer (VIX [14, 17)) | 3.9 days/yr |
| Years with zero triggers | 19 / 27 (70%) |
| VIX=15 crossings in [14, 16) band | ~10 per year |
| Chatter : actionable trigger ratio | 7:1 |

### 3.4 Annual concentration

8 non-zero years: 2004 (8), 2012 (3), 2013 (3), 2016 (3), 2019 (4), 2023 (2), 2025 (11), 2026 ytd (4).

**2026 ytd notable**: 4 triggers all in 9-day window (2026-01-13 → 2026-01-22). Most concentrated trigger cluster in history. But:
- 2026 ytd linear extrapolation = 9.7 days/yr (close to but below 10/yr threshold)
- 2026 cluster SPX +30d mean = **−1.49%** (only negative-counterfactual year on record)
- Suggests boundary rejection was *correct* for that cluster — SPX did pull back

### 3.5 SPX forward returns on edge-cell days (counterfactual proxy)

| Horizon | Mean | Median | p05 | n |
|---|---|---|---|---|
| SPX +30d | +2.68% | +2.75% | -2.10% | 38 |
| SPX +60d | +5.40% | +5.61% | +0.10% | 38 |
| SPX +90d | +8.07% | +7.60% | +3.35% | 36 |

Theoretically positive (BULLISH-trend selection → SPX trends up). But 38 trades / 26 years = 1.4 trades/yr × theoretical BCD ROI per trade ≈ sub-noise annual ROE.

### 3.6 Verdict: `drop`

Three independent reasons:
1. **Frequency**: 1.4 days/yr ≪ 5/yr threshold; even extended buffer 3.9 < 5
2. **Counterfactual ceiling**: even at max 38 trades, marginal portfolio ROE < 0.5pp noise threshold
3. **Chatter dominance**: 7:1 (would-be softening rule triggered by chatter 7× more often than actionable decisions)

Watch condition for reopen: 2027+ continues > 10/yr **AND** counterfactual SPX +30d > +2% on concentrated clusters.

### 3.7 Questions for ChatGPT on Q079

| # | Question |
|---|---|
| **Q14** | Decision threshold "< 5 days/yr → drop" — fair gate for boundary research, or too low? Should account for ROE-per-trade asymmetry? |
| **Q15** | Counterfactual = pure SPX forward return is upper bound for BCD/IC PnL (ignores IV expansion, stop-loss triggers, exit timing). Is this a sufficient proxy for the gating decision, or should we have done actual BCD payoff simulation? |
| **Q16** | 2026 concentrated cluster with negative SPX +30d — I interpreted this as "boundary worked correctly" and *strengthened* the drop verdict (i.e., suggests selector's NORMAL+IV LOW rejection is well-calibrated). Is that the right read, or is it actually weak evidence (n=4, single-cluster)? |
| **Q17** | Should Q079 have audited the OTHER boundaries (VIX=22, IVP=40, IVP=70) before dropping? Or is it OK to drop on the one boundary studied and treat others as separate questions? |

---

## 4. Cross-cutting questions

| # | Question |
|---|---|
| **Q18** | Across 3 lines, the "noise threshold < 0.5pp annualized ROE" framework was load-bearing: it killed Q079 effectively, justified V3 over V1b in SPEC-108, and was used in P2 REVISED daily-MTM smoothing fix. **Is this threshold defensible as a portable framework, or is it artifact of SPEC-104/105v2 baseline variance?** |
| **Q19** | All 3 lines deployed in 24-hr window. Q078 had 5 rounds of 2nd Quant review (G2/G2.5/G4/G4-resubmit/comprehensive audit) and Q079 had zero external review before close. Asymmetric scrutiny — appropriate (Q079 didn't pass kill gate) or insufficient (we should have had at least 1 external read on Q079 P1 methodology)? |
| **Q20** | SPEC-108 + SPEC-109 + Q079 closed all on 2026-05-28 / 05-29. Is the velocity itself a concern from a research-discipline standpoint? Should I throttle to allow longer review windows between major artifacts? |

---

## 5. Files & evidence pointers (for ChatGPT cold-read)

### Q078 / SPEC-108
- `task/SPEC-108.md` — full SPEC (DONE, w/ ## Review section)
- `research/q078/q078_p4_memo.md` — decision-grade portfolio integration
- `research/q078/q078_p4_portfolio_integration.py` — main simulator (V3 + V1b bonus)
- `task/q078_p4_g4_resubmit_2026-05-28_Review.md` — final G4 PASS verdict (9 R-revisions R1-R9)
- `task/q078_spec108_comprehensive_audit_2026-05-28_Review.md` — audit PASS verdict (7 R-revisions R1-R7)
- `strategy/q078_ladder.py` — implementation
- `tests/test_spec_108.py` — 12 ACs incl. AC-108-17/18 CI tests

### SPEC-109
- `task/SPEC-109.md` — full SPEC (DONE, w/ ## Review section)
- `scripts/compute_greek_attribution.py` — Path A method (FROZEN)
- `web/templates/journal.html` — UI implementation
- `web/server.py:2185-2263` — `/api/strategy/greek-attribution` endpoint
- Commit `db6c1af`

### Q079
- `research/q079/q079_framing_memo_2026-05-29.md` — framing + Tier 1 scope
- `research/q079/q079_p1_boundary_frequency.py` — main quant script
- `research/q079/q079_p1_annual_breakdown.py` — annual + 2026 deep-dive
- `research/q079/q079_p1_memo.md` — closing memo + DROP recommendation
- `research/q079/q079_p1_cells.csv` — 38 trigger days raw
- `research/q079/q079_p1_annual_full.csv` — per-year breakdown
- `research/q079/q079_p1_2026_dates.csv` — 4 specific 2026 trigger dates

---

## 6. Requested review format

For each of Q1-Q20:

- **Verdict**: AGREE / CHALLENGE / NEEDS-MORE-INFO
- **Comment**: 1-2 sentences with the *why*
- **If CHALLENGE**: what specific evidence would change my mind / what test should have been run

Cross-cutting closing: any patterns across 3 lines that suggest a research-discipline gap or strength?

---

## 7. Disclosure

- Quant Researcher = Claude Opus 4.7 acting in research role
- PM operates the account real-time; all 3 deployments are live (Stage 1 shadow for SPEC-108; full-on for SPEC-109; no deployment for Q079)
- Historical signal cache used (`research/q078/_signal_history_cache.csv`, 2000-01-03 → 2026-05-27) is the same engine output used by SPEC-103/104/105/107 production tests
- No external models or papers consulted in this 24-hr window — all reasoning from in-codebase data and existing SPEC stack
