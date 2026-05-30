# Q080 Closure Memo — Methodology Primitives Calibration

**Date**: 2026-05-29
**Owner**: Quant Researcher
**Phases**: P1 (MTM smoothing) + P2 (block bootstrap) + P3 (σ calibration)
**Trigger**: ChatGPT 2nd Quant external review of Q078/SPEC-108 + Q079 + SPEC-109 (2026-05-29)
**Status**: CLOSED

---

## 1. Top-level findings

| ChatGPT challenge | Q080 result | SPEC-108 impact |
|---|---|---|
| Q4: daily MTM linear smoothing inflates tail benefits | ΔROE invariant; W20d/W63d/MaxDD within 0.1pp; **Sharpe inflated +1.20 vs unsmoothed +0.48** | **Sharpe headline number wrong** — must revise SPEC-108 §0 |
| Q5: 20 seeds + independent bootstrap → 500 + block bootstrap | Block-bootstrap CI width 0.7-1.1× of P4 P1; ΔROE p05 = +1.68pp robust; W20d p05 = -0.52pp consistent with P4 CI lower bound | Headline +1.80pp robust; tail claims need lower-CI disclosure |
| Q18: 0.5pp noise threshold uncalibrated to σ | 0.5pp = 0.026σ of cross-year baseline annROE (this σ is market noise, not strategy estimate noise); 0.5pp = ~4σ of bootstrap estimate uncertainty | 0.5pp is **adequate at the right level of comparison** (estimate σ, not market σ); no change needed to noise threshold |

**Net implication**:
- SPEC-108 +1.80pp ROE claim is **robust**
- Tail improvements are directionally robust but **5% probability tail of no improvement should be disclosed in SPEC-108 §0**
- **Sharpe number must be revised from +1.20 (smoothing-inflated) to +0.48 (true)**
- Noise threshold 0.5pp framework is defensible

---

## 2. P1 — Unsmoothed MTM control

Script: `research/q080/q080_p1_unsmoothed_mtm.py`

**Method**: Re-run P4 portfolio integration with both `smoothed` (P4 default) and `unsmoothed` (full PnL on exit_date) MTM accounting. Same 20 seeds, same V3 + S3 + production gates.

**Results (20 seeds)**:

| Metric | Smoothed mean | Unsmoothed mean | Diff (un-sm) |
|---|---|---|---|
| ΔROE pp | +1.802 | +1.800 | **-0.002** |
| ΔMaxDD pp | +1.318 | +1.178 | -0.141 |
| ΔW20d pp | +1.161 | +1.081 | -0.080 |
| ΔW63d pp | +3.592 | +3.501 | -0.092 |
| **ΔSharpe** | **+1.196** | **+0.482** | **-0.714** |

**Verdict P1**:
- ΔROE completely invariant — confirms smoothing is PnL-preserving (expected)
- W20d/W63d/MaxDD impact small (< 0.15pp) — well within 0.5pp noise threshold
- **Sharpe materially inflated** by smoothing (-0.71 going to unsmoothed) because smoothing reduces daily PnL volatility (Sharpe denominator)
- Unsmoothed W20d p05 = -1.30% vs smoothed p05 = -0.80% — tail in 5% of scenarios is slightly worse than smoothed view; this is a real disclosure gap

**P1 ChatGPT Q4 specific answer**: ChatGPT was directionally correct (smoothing flattens differences) but the magnitude on the headline ladder claims (ROE, W20d, W63d, MaxDD) is small. The **only material smoothing artifact is the Sharpe inflation**, which is significant.

---

## 3. P2 — Block bootstrap CI

Script: `research/q080/q080_p2_block_bootstrap.py`

**Method**: 500 replicates of 5-day block bootstrap on the combined daily PnL path (baseline + ladder, using reference seed 42 for ladder generation). Block bootstrap preserves within-block autocorrelation.

**Results**:

| Metric | Block-BS Mean | p05 | p95 | CI width | vs P4 P1 CI width (ratio) |
|---|---|---|---|---|---|
| ΔROE pp | +1.872 | **+1.677** | +2.083 | 0.406 | 1.1× |
| ΔMaxDD pp | +1.293 | -0.278 | +3.647 | 3.925 | 1.0× |
| ΔW20d pp | +0.868 | **-0.516** | +2.179 | 2.695 | 0.7× |
| ΔW63d pp | +2.021 | +0.387 | +4.244 | 3.857 | 0.8× |
| ΔSharpe | +0.969 | +0.810 | +1.137 | 0.327 | 0.9× |

**Verdict P2**:
- ΔROE p05 = +1.68pp > 0 → ROE claim robustly positive under block bootstrap
- ΔMaxDD p05 = -0.28pp → 5% probability ladder makes MaxDD slightly worse (not a robust improvement at 5% CI)
- ΔW20d p05 = -0.52pp → 5% probability ladder makes W20d worse (consistent with P4 P1 lower CI bound -0.80pp)
- ΔW63d p05 = +0.39pp → barely positive
- CI width: block-bs 0.7-1.1× of P4 P1 — block bootstrap does NOT systematically widen CI. P4's trade-pool resampling actually generated MORE variance for some metrics because it draws fresh trades; block bootstrap on the daily PnL path preserves more structure.

**P2 ChatGPT Q5 specific answer**: ChatGPT was correct that block bootstrap is methodologically better for autocorrelated data. But P4's original CI was NOT misleadingly narrow — it already disclosed W20d/MaxDD lower bounds that go negative. P2 reaffirms the existing finding rather than overturning it.

---

## 4. P3 — σ-relative noise threshold calibration

Script: `research/q080/q080_p3_sigma_calibration.py`

**Method**: Compute baseline annROE σ overall + per VIX regime; express 0.5pp as multiplier of each σ.

**Results**:

| Cut | n years | Mean ROE | σ | 0.5pp / σ |
|---|---|---|---|---|
| Overall | 26 | 26.43% | 19.44% | 0.026 |
| benign (max VIX < 18) | 2 | 32.35% | 28.37% | 0.018 |
| normal (18-22) | 2 | 38.05% | 39.16% | 0.013 |
| elevated (22-28) | 5 | 33.96% | 20.09% | 0.025 |
| stress (≥28) | 17 | 22.15% | 16.87% | 0.030 |

**Verdict P3 — the right interpretation**:

P3 measured cross-year σ of baseline annROE (~19pp overall). At face value, **0.5pp = 0.026σ = trivially small**, suggesting noise threshold is way too strict.

**BUT this is the wrong σ for noise threshold comparison**. The relevant σ is:

- **Cross-year baseline σ** (P3 measurement, 19pp) = how variable is baseline year-to-year. Driven by market regime variance (2008 vs 2013). Not relevant for strategy comparison.
- **Bootstrap-estimate σ of ΔROE** (P2 measurement, 0.125pp) = how uncertain is our estimate of ladder ROE benefit. **This is what noise threshold should be compared against.**

**Right calibration**:
```
0.5pp ÷ 0.125pp (bootstrap σ of ΔROE estimate) = 4.0σ
```

A 4σ confidence margin is **defensible** — it correctly treats small estimated differences as noise even when each strategy has high inherent yearly variance.

**Verdict P3 (corrected)**: 0.5pp noise threshold is **adequate at the right level of comparison**. The threshold operates on strategy-comparison estimate uncertainty, not on baseline market variance. Current threshold defensible without regime-conditional adjustment.

**Caveat for future use**: in cross-strategy comparisons where both strategies see the same market sequence (e.g., V3 vs V1b ladder), 0.5pp ≈ 4σ. In cross-period comparisons (e.g., "is 2025 ROE different from 2024"), 0.5pp = 0.03σ and is useless. The 0.5pp threshold is for **same-period strategy comparisons** only.

---

## 5. SPEC-108 implications

### 5.1 What survives

- **ΔROE +1.80pp mean** (P4) confirmed; block bootstrap p05 = +1.68pp robust
- Bias-deflated realistic range +0.8 to +1.3pp still applies
- V3 cadence + S3 sizing + production gates structurally sound
- Stage 1 shadow mandatory continues to be the right safety posture

### 5.2 What must be revised (SPEC-108 §0 TL;DR)

**Current SPEC-108 §0 line**:
> Sharpe: 2.02 → 3.21 (+1.20)

**Should become**:
> Sharpe: 2.02 → 2.50 (+0.48) — *previously reported +1.20 was inflated by daily-MTM linear smoothing; unsmoothed control (Q080 P1) gives true +0.48 improvement*

**Current SPEC-108 §0 confidence framing**:
> CI [+1.61, +1.97]

**Should add (block bootstrap honest CI)**:
> ΔROE block-bootstrap p05 = +1.68pp (robust positive)
> ΔMaxDD p05 = -0.28pp (5% probability tail does NOT improve)
> ΔW20d p05 = -0.52pp (5% probability ladder makes 20-day tail slightly worse)
> ΔW63d p05 = +0.39pp (marginally positive)

### 5.3 Stage 2 advancement gate (update)

ChatGPT R8 challenges (Q1: portfolio overnight gap gate; Q7: regime-coverage gate; Q8: per-strategy drift monitor) remain valid. **Stage 2 freeze stays in place** until:
- SPEC-108.1 micro-revisions applied (R1-R5 from ChatGPT response)
- Stage 1 shadow actually accumulates ≥10 entries (per existing R5)
- Shadow data shows real W20d trajectory consistent with mean +1.08pp, not the p05 -0.52pp pessimistic scenario

### 5.4 V3 vs V1b decision (ChatGPT Q6)

P1 confirms ΔROE difference between V3 and V1b is < 0.5pp = 4σ of bootstrap estimate (per P3 corrected calibration). So **noise threshold WAS the right framework for that decision**. But ChatGPT's parallel-shadow recommendation is still valid because:
- Shadow cost is low
- Tail-metric difference between V3 and V1b in P4 (V1b slightly better on W20d/MaxDD) is within noise but worth confirming with live data
- Per `feedback_methodology_primitives.md`, shared primitives should not pre-decide downstream design

**Action**: SPEC-108.1 will add V1b parallel shadow (low-cost, no production risk).

---

## 6. SPEC-108.1 micro-revisions (now unblocked)

Per Q080 P1 result preserving the core SPEC-108 ROE claim, the SPEC-108.1 micro-revision package outlined in `chatgpt_review_response_2026-05-29.md` is now **GO** (not paused):

1. R1: Add portfolio-stress overnight gap gate (ChatGPT Q1)
2. R2: V1b parallel shadow (Q6)
3. R3: Stage 2 advancement gate → regime-coverage + per-strategy coverage (Q7)
4. R4: Per-strategy drift monitor (Q8)
5. R5: Bias wording "resolves" → "defers" (Q3)
6. **R6: Sharpe revision +1.20 → +0.48** (Q080 P1 finding — new)
7. **R7: Tail-metric p05 disclosure** (Q080 P2 finding — new)

These will be packaged into a SPEC-108.1 revision after PM sees Q080 closure.

---

## 7. Memory updates required

Already done (2026-05-29 morning):
- `feedback_noise_threshold.md`: marked uncalibrated
- `feedback_kill_gate_external_read.md`: new
- `feedback_boundary_research_dual_threshold.md`: new
- `feedback_methodology_primitives.md`: new

Update needed post-Q080:
- `feedback_noise_threshold.md`: REMOVE "uncalibrated" warning; ADD: 0.5pp is correctly calibrated at strategy-comparison level (4σ of bootstrap estimate σ), explicitly NOT at cross-year baseline σ level (where it's 0.026σ and meaningless)
- New memory: `feedback_sharpe_smoothing_artifact.md` — daily-MTM linear smoothing inflates Sharpe ~+0.7; for Sharpe reporting use exit-day unsmoothed accounting

---

## 8. Files

```
research/q080/q080_framing_memo_2026-05-29.md           ← framing
research/q080/q080_p1_unsmoothed_mtm.py                 ← P1 critical-path script
research/q080/q080_p1_results.csv                       ← P1 per-seed results
research/q080/q080_p1_distribution.csv                  ← P1 distribution
research/q080/q080_p2_block_bootstrap.py                ← P2 script
research/q080/q080_p2_results.csv                       ← P2 500-rep CI raw
research/q080/q080_p2_ci_table.csv                      ← P2 CI summary
research/q080/q080_p3_sigma_calibration.py              ← P3 script
research/q080/q080_p3_annual_baseline.csv               ← P3 per-year baseline
research/q080/q080_p3_regime_sigma.csv                  ← P3 per-regime σ
research/q080/q080_memo.md                              ← this closure memo
```

---

## 9. Topic / Findings / Risks / Confidence / Next / Recommendation

**Topic**: Validation of 3 methodology primitives load-bearing across Q078/SPEC-108 and Q079

**Findings**:
1. **Daily MTM smoothing** (Q4) was a marginal artifact for ladder ROE/MaxDD/W20d/W63d claims (< 0.15pp impact each) but **materially inflated Sharpe** (+1.20 vs true +0.48). SPEC-108 Sharpe number must be revised.
2. **Block bootstrap CI** (Q5) gave comparable CI width to P4 P1; ΔROE p05 = +1.68pp robust positive; W20d p05 = -0.52pp confirms 5% tail risk that P4 had already shown but PM may not have noticed. SPEC-108 should explicitly disclose p05 alongside mean.
3. **0.5pp noise threshold σ-calibration** (Q18): wrong σ comparison (cross-year baseline σ ~19pp) makes it look trivially small; right σ comparison (bootstrap estimate σ ~0.13pp) makes it 4σ which is defensible. Current threshold OK at strategy-comparison level.

**Risks / Counterarguments**:
- P1 used 20 seeds; with 500 seeds + actual block-bootstrap of trade pool, ΔROE estimate could move slightly. But P2 confirms block-bootstrap of daily PnL gives p05 +1.68pp, so this risk is small.
- P3 used yearly bucket which may be coarse; sub-yearly regime classification could give different σ but unlikely to change the verdict that strategy-comparison level is the right benchmark.
- 2026 ytd has only 100 days — was excluded from P3 annual calc. Doesn't affect verdict.

**Confidence**: High — three independent tests on same data, all directionally consistent with each other.

**Next Tests**: None at the primitives level. The Sharpe inflation finding should feed into SPEC-108.1 R6 (immediate). For future research, methodology primitives should default to unsmoothed-Sharpe accounting from now on.

**Recommendation**:
- `enter SPEC-108.1 revision` (incorporate Q080 findings + ChatGPT R1-R5)
- `update feedback_noise_threshold.md` (calibration note)
- `add feedback_sharpe_smoothing_artifact.md` (new memory)
- **DO NOT** roll back SPEC-108 deployment — Stage 1 shadow remains correct posture; Stage 2 freeze stays until SPEC-108.1 + live shadow evidence accumulate
