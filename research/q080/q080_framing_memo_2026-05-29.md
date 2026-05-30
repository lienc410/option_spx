# Q080 — Methodology Primitives Calibration

**Date**: 2026-05-29
**Owner**: Quant Researcher
**Trigger**: ChatGPT 2nd Quant review of Q078/SPEC-108 + Q079 + SPEC-109 (2026-05-29) flagged 2 unvalidated load-bearing primitives
**Type**: Primitives research (NOT a strategy SPEC) — per `feedback_methodology_primitives.md`
**Status**: FRAMING + P1 START

---

## Question

Two primitives were reused across 3 closed research lines without independent validation:

1. **Daily MTM linear smoothing** — Q078 P2 REVISED introduced this to make W20d/W63d degradation pass 0.25pp gate; carried into P3, P4. **Did this artificially manufacture the +1.16pp W20d / +3.59pp W63d / +1.32pp MaxDD improvements that justify SPEC-108?**
2. **0.5pp noise threshold** — used to kill Q079, justify V3-over-V1b in SPEC-108, pass W20d/W63d in P2 REVISED. Never calibrated to baseline σ. **Is 0.5pp 0.4σ in benign regimes (i.e., legitimate noise) or 1.2σ in stress (i.e., signal misclassified)?**

If either primitive turns out to be alpha-fabricating rather than noise-filtering, SPEC-108 +1.80pp claim does not survive.

---

## Probabilistic prior (pre-Q080)

| Scenario | Prior | Implication |
|---|---|---|
| Both primitives survive — Q080 confirms current methodology | 40-50% | SPEC-108 +0.8-1.3pp realistic deflated band intact; Stage 1 shadow continues; Stage 2 unfreeze possible |
| MTM smoothing inflates W20d/W63d improvement but ΔROE survives | 30-40% | SPEC-108 reframed: ROE-cadence without tail benefit; no Stage 2 advancement on tail grounds |
| Both fail — most of +1.80pp is artifact | 15-20% | SPEC-108 ROE claim collapses; full re-eval; V3-vs-V1b decision reopened |

---

## Plan

### P1 — Unsmoothed MTM control (CRITICAL PATH)

**Question (Q4)**: Does linear MTM smoothing across hold days inflate ladder's tail improvement?

**Method**:
- Modify `research/q078/q078_p4_portfolio_integration.py` to accept a `--mtm-mode {smoothed,unsmoothed}` flag
- `smoothed` (current default): PnL linearly distributed across hold days
- `unsmoothed` (new control): PnL realized entirely on exit_date (single-day spike)
- Re-run P4 portfolio integration with both modes, same 20 seeds, same selectors
- Compare smoothed vs unsmoothed:
  - ΔROE: should be invariant (smoothing is conservative, doesn't change total)
  - MaxDD: may differ — unsmoothed creates single-day drawdown spikes
  - **W20d / W63d**: this is where divergence is expected. If unsmoothed shows worse degradation, smoothing was masking actionable tail
  - Sharpe: should track

**Decision rule**:
- If unsmoothed shows ladder W20d/W63d still net-positive vs baseline (margin ≥ +0.5pp current threshold or σ-multiplier per P3) → SPEC-108 robust
- If unsmoothed shows ladder W20d/W63d ≈ baseline or net-negative → SPEC-108 tail claim collapses; reframe to "ROE-cadence overlay without tail benefit"
- If ΔROE collapses too (unlikely given smoothing should be PnL-preserving) → root-cause investigation

**Expected runtime**: ~30 min (re-running existing 20-seed P4 with one new flag)

### P2 — Block bootstrap CI calibration

**Question (Q5)**: Is CI [+1.61, +1.97] artificially narrow due to (a) too few seeds (20) and (b) independent bootstrap ignoring daily PnL autocorrelation?

**Method**:
- Implement 5-day block bootstrap (5 trading days per block = ~1 week)
- Increase seeds: 20 → 500
- Re-run on **unsmoothed** P4 output from P1 (use the version that best survives P1)
- Report:
  - ΔROE 95% CI (block bootstrap, 500 seeds)
  - Same for MaxDD, W20d, W63d, Sharpe
  - Compare CI widths to current [+1.61, +1.97] (~36 bp wide)

**Decision rule**:
- If new CI excludes 0 → ROE delta robust, just less narrow than reported
- If new CI includes 0 → reported +1.80pp was over-confident, no significant ROE improvement
- Expected widening: 2-3× given autocorrelation

**Expected runtime**: ~1 hr (500 seeds × current per-seed time)

### P3 — σ-relative noise threshold calibration

**Question (Q18)**: What is the natural σ of the SPEC-104+105v2 baseline annROE, overall and per regime? Express 0.5pp as a multiplier of that σ.

**Method**:
- From baseline (no ladder) P4 simulation: compute annROE per simulation seed × per year
- Two cuts:
  - **Overall σ**: across all (seed × year) pairs
  - **Per-regime σ**: stratify years by dominant VIX regime — benign (max VIX < 18), normal (18 ≤ max VIX < 22), elevated (22 ≤ max VIX < 28), stress (max VIX ≥ 28)
- Compute 0.5pp ÷ σ for each cut
- Tabulate: how many σ is 0.5pp in each regime?

**Decision rule**:
- If 0.5pp is uniformly ~1σ or higher across regimes → current noise threshold is too lenient (treating signal as noise)
- If 0.5pp is uniformly < 0.3σ → too strict (treating noise as signal)
- If 0.5pp is regime-dependent (e.g., 0.3σ in benign, 1.5σ in stress) → noise threshold should be **regime-conditional**

**Decision output**: regime-conditional table or σ-multiplier formula to replace flat 0.5pp.

**Expected runtime**: ~30 min (pure statistics on P1/P2 output, no new simulation)

### Out of scope (Q080 explicitly does not do)

- Re-implement P4 simulator from scratch (modify, don't rewrite)
- Change strategy selection logic
- Modify SPEC-108 directly (Q080 outputs feed forward into SPEC-108.1 evaluation)
- 3rd primitive validation (regime classification thresholds, etc.) — only the 2 flagged by ChatGPT
- Path B greek attribution — separate orthogonal work
- Production code change of any kind

### Files

```
research/q080/q080_framing_memo_2026-05-29.md       ← this file
research/q080/q080_p1_unsmoothed_mtm.py             ← P1 script (modifies P4 + new flag)
research/q080/q080_p1_results.csv                   ← P1 outputs (smoothed vs unsmoothed)
research/q080/q080_p1_memo.md                       ← P1 verdict
research/q080/q080_p2_block_bootstrap.py            ← P2 script
research/q080/q080_p2_results.csv
research/q080/q080_p2_memo.md
research/q080/q080_p3_sigma_calibration.py          ← P3 script
research/q080/q080_p3_results.csv
research/q080/q080_p3_memo.md
research/q080/q080_memo.md                          ← Q080 closure memo, feed back to SPEC-108
```

### Expected output to SPEC-108

After Q080 closes:
- Either: SPEC-108 +1.80pp claim survives → unfreeze Stage 2 advancement (still needs PM signoff + ≥10 shadow entries)
- Or: SPEC-108 +1.80pp claim deflates → SPEC-108 either reframed (drop tail claim) or rolled back to RESEARCH

### Sequencing

P1 is **critical path** because it most directly tests the alpha-fabrication hypothesis. P2 follows P1 (uses P1 output). P3 is independent and can run parallel to P1, but its result is most useful after P1 (so the σ comparison is against the methodology that actually survives).

Suggested order: **P1 → (P3 || P2) → Q080 memo → SPEC-108 evaluation**.

---

## What we are NOT promising

- Q080 does not promise +1.80pp survives or collapses. It promises an honest test of the methodology that produced +1.80pp.
- Q080 does not pre-commit to a verdict on SPEC-108. The output is *evidence*; whether SPEC-108 reframes / freezes / unfreezes is a separate evaluation step.
- Q080 P3 calibration does not auto-rewrite past memos. The 0.5pp threshold remains the documented historical decision; future research uses the σ-multiplier (if regime-conditional) or recalibrated flat threshold from P3.
