# Q074.1b — Block-Rate Dilution + Gate F Discovery

**Date**: 2026-05-19
**Author**: Quant Researcher
**Trigger**: PM follow-up observation (2026-05-19) on Q074.1 table — "Block%越高，Blocked 日实际 fwd 10d stress 越低"
**Status**: Sub-investigation, follow-up to Q074.1. Findings warrant 2nd Quant review for potential SPEC-105 v2 amendment.

---

## 0. TL;DR

**PM's surface observation** ("block ↑ → lift ↓") tests as weak negative correlation:
- Pearson r(block%, lift_pp) = -0.34, p = 0.17 — **not statistically significant**

**Mediating variable identified**: blocked-day absolute VIX is the real driver:
- Pearson r(avg_blocked_VIX, lift_pp) = **+0.73, p = 0.001** — **highly significant**

**Smoking gun** — Blocked days stratified by absolute VIX (baseline passed-day P(stress 10d) = 17.7%):

| Blocked VIX | n | P(stress 10d) | Lift vs baseline |
|---|---|---|---|
| **< 13** | 76 | **7.9%** | **-9.8pp anti-signal** |
| 13-15 | 213 | 13.6% | -4.1pp anti-signal |
| 15-17 | 233 | 38.6% | +20.9pp |
| 17-19 | 128 | 48.4% | +30.7pp |
| **19-22** | 109 | **73.4%** | **+55.7pp** |

→ Current `IVP_252 >= 55` gate is **statistically anti-signal when VIX < 15** (n=289). Those days have *lower* stress probability than passed days. Blocking them is anti-protective — pure ROE loss.

**Gate F** (`IVP_252 < 55 OR VIX < 15`):
- Pass rate 79.1% → 87.1% (+8.0pp)
- Marginal stress on +289 added days: **12.1%** (vs baseline 17.7%) — **NEGATIVE marginal risk**
- 2007 pass 27% → 66% / 2018 pass 33% → 90% (recovers true FP years)
- 2024 60% → 67% / 2025 70% → 70% / 2026 41% → 41% (preserves real-signal years)

Gate F is **not a precision-vs-recall trade**. It is a bug-fix: it removes days where the gate has empirically reversed signal.

---

## 1. Methodology

Sample: 26y normal-state days (n=3643), full IVP_252 + IVP_1260 (5y) coverage. Stress event defined per SPEC-104 R5/R6 (VIX≥22 OR dd_20d≤-4% OR dd_60d≤-4%, rolling 3-day). Forward stress = stress_active within next 10 / 20 trading days.

Two correlation tests (per-year aggregate, 18 years with ≥3 blocked + ≥3 passed):
- H1: block_rate predicts lift  (PM intuition direct test)
- H2: avg_blocked_VIX predicts lift  (mediation hypothesis)

Five alternative gates tested on full normal-day sample:
- A: `IVP_252 < 55` (current SPEC-105)
- F: `IVP_252 < 55 OR VIX < 15`
- F2: `IVP_252 < 55 OR VIX < 14` (conservative)
- G: `IVP_1260 < 55` (5y baseline, replace 1y)
- H: `IVP_252 < 55 OR IVP_1260 < 30` (hybrid)

Look-ahead safety: all gates use backward-looking windows. P(stress_in_next_*) is for diagnostic only, never used in gate construction.

---

## 2. Test 1 — Correlation results

```
Pearson  corr(block%, lift_pp):           r = -0.338, p = 0.170
Spearman corr(block%, lift_pp):           rho= -0.269, p = 0.280
Pearson  corr(avg_blocked_VIX, lift_pp):  r = +0.729, p = 0.001 ***
Spearman corr(avg_blocked_VIX, lift_pp):  rho= +0.734, p = 0.001 ***
```

→ PM's surface intuition (block↑ → lift↓) is weakly suggested but not significant. The actual generating mechanism is **absolute VIX of blocked days**. In low-VIX environments, IVP_252 is a percentile rank within a quiet window, which mechanically rises without absolute risk increasing.

---

## 3. Test 2 — VIX stratification (the discovery)

Full sample, n=759 blocked days stratified by VIX:

```
vix_bucket    n   P(stress 10d)  Lift vs passed baseline (17.7%)
<13          76         7.9%     -9.8pp   ←  ANTI-SIGNAL
13-15       213        13.6%     -4.1pp   ←  ANTI-SIGNAL
15-17       233        38.6%    +20.9pp
17-19       128        48.4%    +30.7pp
19-22       109        73.4%    +55.7pp
```

The current gate covers **289 days (38% of all blocked days) where it predicts LESS stress than the baseline**. Those days' average IVP is 64-67 — well above 55. So we have a high-IVP gate flagging "danger" precisely when absolute volatility is low and danger is mechanically reduced.

**Economic intuition**: IVP_252 is a relative percentile within a 252-day VIX history. In a regime where VIX has been 11-13 for 9+ months, a 13.5 VIX print is at the 70th percentile of recent history (IVP > 55) but represents ~no absolute danger. Volatility "in absolute" determines real risk, not "where it sits within a quiet baseline."

---

## 4. Test 3 — Gate comparison

```
Gate                              Pass%   Passed_P(stress 10d)  N_blocked  Blocked_P(stress 10d)
A: IVP_252<55 (current)            79.1            17.7%          759            35.2%
F: IVP_252<55 OR VIX<15            87.1            17.2%          470            49.4%
F2: IVP_252<55 OR VIX<14           83.8            17.2%          590            42.9%
G: IVP_1260<55 (5y)                75.7            17.0%          884            35.1%
H: IVP_252<55 OR IVP_1260<30       85.9            18.3%          511            40.3%
```

**Marginal stress on newly-passed days (gate F/F2/G/H pass but current A blocks)**:

```
F: VIX<15:        +289 days, P(stress 10d) 12.1% (vs 17.7% baseline) ← improvement
F2: VIX<14:       +169 days, P(stress 10d)  8.3% ← even safer
G: IVP_1260:      +531 days, P(stress 10d) 28.4% ← worse
H: hybrid:        +248 days, P(stress 10d) 24.6% ← worse
```

→ **Gate F dominates**: most pass-rate gain (+8pp) AND lowest marginal stress (12.1%, *below* baseline). F2 is a more conservative version.

**Gate G (5y baseline IVP) is REJECTED**: pass rate actually *lower* than current (75.7% vs 79.1%), because IVP_1260 catches more days where absolute VIX is genuinely at decadal lows. The 5y baseline is the wrong direction.

---

## 5. Test 4 — Slow-bull year reconciliation

| Year | A (current) | F (VIX<15) | F2 (VIX<14) | Improvement (F) |
|---|---|---|---|---|
| 2007 | 27.3% | 66.2% | 57.1% | +38.9pp |
| 2017 | 88.0% | 97.2% | 94.0% | +9.2pp |
| 2018 | 33.3% | 89.9% | 79.8% | **+56.6pp** |
| 2024 | 60.4% | 67.0% | 60.4% | +6.6pp |
| 2025 | 69.9% | 69.9% | 69.9% | 0pp |
| 2026 | 41.1% | 41.1% | 41.1% | 0pp |

→ Gate F surgically recovers PM-flagged FP years (2007/2018) while preserving real-signal years (2024-2026). 2024/2025/2026 unchanged because their blocked-day VIX averages 17-19 (Gate F doesn't apply).

---

## 6. Caveats

1. **VIX<13 stratum n=76 only** — anti-signal magnitude (-9.8pp) might be noisy. But VIX 13-15 stratum (n=213, -4.1pp) is consistent with same direction, and combined n=289 is adequate.
2. **No ROE estimate yet**. Test only measures stress probability, not booster economics. A P2-style ROE re-sweep with Gate F substituted is needed to confirm net +ROE.
3. **2026 sample small (n=56 normal days)**. The +30pp lift in 2026 blocked-day stress is from a small denominator.
4. **Stress definition fixed** at SPEC-104 R5/R6 thresholds. Robustness to ±20% threshold variation not tested in this sub-investigation.
5. **Gate F effectively imposes an absolute VIX floor of 15** (booster requires VIX < 22 *and* now either IVP < 55 OR VIX < 15). Logically: only VIX in [15, 22] is gated by IVP. PM should validate this matches strategic intent.
6. **B4 booster has 6 other AND conditions**. Gate F's added days must still satisfy `SPX > MA50`, `MA50_slope > 0`, `ddATH > -4%`, `VIX < 22`, `VIX_5d ≤ +1.5`. The 289 raw added days likely shrink after composite filter.

---

## 7. Implications for SPEC-105

**SPEC-105 is already deployed Stage 1 (shadow)**. Gate F is **NOT** a critical blocker — current B4 still passes G4 review.

But Gate F is a **substantive, statistically clean refinement** that:
- Removes an empirically anti-protective component of the gate
- Adds +8pp pass rate (more booster days)
- Adds days with *lower* stress probability than baseline (negative marginal risk)
- Surgically targets PM's flagged FP years without disturbing real-signal years

**Decision pathway for 2nd Quant**:

| Path | Action |
|---|---|
| **PROMOTE Gate F to SPEC-105 v2** | Run P2-style ROE sweep with Gate F; if ΔROE >0 and V2/V3 still pass → draft SPEC-105 v2 amendment |
| **DEFER until Stage 1 evidence** | Document Gate F in `research/q074/`; revisit after live shadow data |
| **REJECT** | Q074.1b closes; current SPEC-105 stays |
| **REVISE TO F2** | Conservative variant `VIX<14` — smaller pass-rate gain but even safer added days |

Quant prior: **PROMOTE F**. The anti-signal finding (Test 2 stratification) is the cleanest result. F's marginal stress is -5.6pp vs baseline — there is no precision-recall tradeoff to weigh.

---

## 8. Files

- `q074_1b_block_dilution.py` — analysis script
- `q074_1b_yearly_block_vs_lift.csv` — 18 years, correlation inputs
- `q074_1b_blocked_vix_strata.csv` — 5-bucket VIX stratification (smoking gun)
- `q074_1b_gate_F_G_comparison.csv` — 5 gates full-sample comparison
- `q074_1b_slow_year_gate_pass.csv` — slow-bull year pass rate per gate

Prior context:
- `q074_1_forensic_memo.md` — Q074.1 yearly breakdown (PM trigger)
- `q074_1_ivp_gate_forensic.py` — Q074.1 script
- `q074_final_memo.md` — Q074 P5 PROMOTE B4 decision
- `task/SPEC-105.md` — current Stage 1 shadow

---

## 9. Sign-off

Quant submits Q074.1b for optional 2nd Quant review. Decision sought: PROMOTE Gate F / DEFER / REJECT / REVISE.

If PROMOTE: Quant will run Q074.2 (P2-style ROE sweep with Gate F substituted, V2/V3 re-validation) before drafting SPEC-105 v2.
