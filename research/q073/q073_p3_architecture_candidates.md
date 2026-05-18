# Q073 P3 — Architecture Candidates Comparison

> **Status: P3 DECISION-GRADE.**
> **Arch-3 is the leading risk-adjusted candidate, pending P4 robustness validation.**
> Arch-2 (E5) remains incremental fallback. P4 must validate BOTH in parallel.

**Date**: 2026-05-17
**Parent**: `q073_p2a_plus_e5_candidate_memo.md`

---

## TL;DR

| | Arch-2 (E5) | **Arch-3 (no HV)** |
|---|---|---|
| Net ROE | 7.99% | 7.95% (-0.04pp) |
| MaxDD | -11.68% | **-8.71%** (+2.97pp) |
| Worst 20d | -10.25% | **-7.04%** (+3.21pp) |
| Bear 2022 | +0.65% | **+1.47%** |
| Decision impact | incremental | demote HV Ladder + raise Q042 cap |

> **Arch-3 sacrifices 0.04pp ROE for 3pp MaxDD improvement and 3.21pp V2 buffer expansion. The trade favors Arch-3 on risk-adjusted basis but requires HV Ladder demotion and SPEC-094 sleeve cap increase. P4 双轨 validation is required.**

---

## 1. P3 Four-Architecture Results (Net of Friction)

| Arch | SPX n/s/2L | HV | Q42 | Cash (normal) | Net ROE | MaxDD | Worst 20d | Worst 63d | Sharpe | V1 | V2 | V3 | Floor 8% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Arch-0 status quo | 60/60/60 | 5% | 10% | 25% | 7.42% | -14.09% | **-12.52%** | -11.78% | 1.63 | ✓ | **✗** | ✓ | ✗ |
| Arch-1 conservative (R5/R6 60/50) | 70/60/50 | 5% | 10% | 15% | 7.79% | -13.50% | **-11.88%** | -11.30% | 1.74 | ✓ | **✗** | ✓ | ✗ |
| **Arch-2 moderate (E5)** | 80/50/40 | 5% | 12.5% | 2.5% | **7.99%** | -11.68% | -10.25% | -9.94% | 1.87 | ✓ | ✓ | ✓ | gap 0.01pp |
| **Arch-3 radical (no HV)** | 80/50/40 | **0%** | **17.5%** | 2.5% | **7.95%** | **-8.71%** | **-7.04%** | **-6.94%** | 2.02 | ✓ | ✓ | ✓ | gap 0.05pp |

### Crisis Window Returns (% of equity at window start)

| Arch | DotCom 2000-2002 | GFC 2008 acute | COVID 2020 | Bear 2022 |
|---|---|---|---|---|
| Arch-0 | +30.25% | -2.96% | +0.31% | -0.17% |
| Arch-1 | +31.71% | -2.01% | +0.29% | +0.36% |
| Arch-2 | +29.11% | -1.44% | +0.20% | +0.65% |
| **Arch-3** | **+30.37%** | **-1.22%** | -0.20% | **+1.47%** |

Arch-3 wins modern crises (GFC, Bear 2022); Arch-2 slightly better on COVID; DotCom roughly equivalent.

---

## 2. Head-to-Head: Arch-2 vs Arch-3

### Risk-adjusted comparison

| Metric | Arch-2 (E5) | Arch-3 (no HV) | Δ |
|---|---|---|---|
| Net ROE | 7.99% | 7.95% | **-0.04pp** (within bootstrap noise expectation) |
| Sharpe | 1.87 | **2.02** | +0.15 (8% relative) |
| MaxDD | -11.68% | **-8.71%** | **+2.97pp improvement** |
| Worst 20d | -10.25% | **-7.04%** | **+3.21pp improvement** |
| Worst 63d | -9.94% | **-6.94%** | **+3.00pp improvement** |
| V2 buffer (from 11%) | 0.75pp | 3.96pp | **5.3x larger buffer** |
| V1 buffer (from 28%) | 16.3pp | 19.3pp | +18% buffer |

**Verdict**: Arch-3 is Pareto-superior on risk dimensions and marginal-inferior on ROE. **Risk-adjusted return clearly favors Arch-3** (Sharpe 2.02 vs 1.87).

### Cost vs benefit of HV Ladder retirement

```
Lose:   HV Ladder 5% × 0.74% arith contribution = 0.04pp Net ROE
Lose:   HV Ladder's small diversification benefit (correlation 0.28 with SPX)
Gain:   3pp MaxDD improvement
Gain:   3.21pp worst-20d improvement (V2 buffer 5.3x larger)
Gain:   Operational simplification (one fewer strategy to monitor)
Gain:   No need for future SPEC tightening R5/R6 caps as urgently (V2 has bigger buffer)
```

The ROE giveup is in noise; the tail improvement is consequential.

---

## 3. Why HV Ladder is a Tail Driver (Evidence Accumulation)

P3 confirms a pattern observed across multiple prior analyses:

| Source | Evidence |
|---|---|
| **Q072 P4** | HV identified as 2022 stress co-driver |
| **P2A original sweep** | HV 5% → 7.5% directly broke V2 (-11.82% worst-20d in all variants B/D/F) |
| **P3 Arch-2 vs Arch-3** | Removing HV (5% → 0%) improves V2 by 3.21pp and MaxDD by 2.97pp |

HV Ladder is **opportunistic high-vol sleeve by design** (entry on VIX ≥ 22). The same regime trigger that makes it occasionally profitable also makes it active during early-stage selloffs (2000-04 DotCom, 2022 February) where its short-put positions accumulate losses before broader hedges (V3-A Aftermath, Q042) can engage.

This is a **structural property**, not a parameter bug. HV Ladder is correctly designed per Q071 but has irreducible tail exposure that cannot be fixed by sizing alone.

---

## 4. Q042 Cap Increase Implication (Arch-3)

Arch-3 requires Q042 Sleeve A allocation 10% → **17.5%**, which:

1. **Exceeds current SPEC-094 sleeve cap** (10% per sleeve)
2. Requires PM acceptance to amend SPEC-094 sleeve cap (or invoke P0 "激进 tear-down" lever G)
3. **Q042 paper status**: Sleeve A has 5 paper-trade entries since 2026-05-10 (live forward sample minimal)

### Q042 17.5% Concentration Risk Question (P4 must answer)

The +5pp Q042 allocation contributes ~0.4-0.5pp Net ROE. If this comes from concentrated drawdown-recovery episodes (rather than steady accumulation), Arch-3 is brittle:

- **35 backtest trades over 19y** = ~1.8/yr
- If top 3-5 trades drive most PnL, +5pp allocation amplifies idiosyncratic dependency
- Need P4 to extract: top-N trade contribution, worst trade at 17.5% sizing, year-by-year stability

If concentration is high → Arch-3 should be **shadow / staged**, not immediate production. If diffuse → Arch-3 can be promoted.

---

## 5. P4 Validation Scope (双轨 per PM)

P4 must validate BOTH Arch-2 AND Arch-3 on these dimensions:

### V6 Bootstrap Significance (Q071 method)
- Block=250, 20 seeds
- For each architecture's PnL series → bootstrap sig_rate
- If Arch-3 sig_rate ≥ Arch-2 sig_rate → robust risk advantage real
- Per Rule (V6 is promotion-level evidence gate, not hard veto)

### V7 Walk-Forward / Split-Sample Robustness
- Split 26y into 2 halves (2000-2013 and 2013-2026)
- Compute ROE / V1-V3 in each
- If Arch-3 leads in BOTH halves → robust
- If Arch-3 only leads in one half → fragile (e.g., due to one period concentration)

### Q042 Concentration Analysis (Arch-3 specific)
- Top-1 / top-3 / top-5 Q042 trade contribution to total PnL
- Worst Q042 trade at 17.5% sizing (~$15.6k notional × loss%)
- Year-by-year Q042 PnL distribution
- Removing top 1 / top 3 trades — does Arch-3 still beat Arch-2?

### Friction Sensitivity
- Test friction estimates ±50% (so SPX 0.175%/yr to 0.525%/yr)
- Does Arch-2 vs Arch-3 ordering change under different friction assumptions?

### Crisis Stress (Synthetic Shock Injection)
- 2008 / 2020 / 2022 style shocks applied at different dates
- Does Arch-3's tail benefit hold under shocks NOT in historical 26y?
- Particularly: VIX spike to 80 + SPX -30% in 30 days (covid-style synthetic)

### Correlated Model Error
- Simultaneous: slippage worse, fills worse, margin model wrong, VIX data delayed
- Both Arch-2 and Arch-3 robustness under combined adverse assumption

---

## 6. P4 Possible Outcomes & Decision Tree

| P4 Outcome | Recommendation |
|---|---|
| Arch-3 robust on all P4 dimensions | **Promote Arch-3 as primary**; demote HV Ladder to research/paper-only |
| Arch-3 fails Q042 concentration check | **Arch-2 production**, Arch-3 staged paper (Q042 incremental size-up) |
| Arch-3 fails walk-forward in one half | **Arch-2 production**, Arch-3 deferred to Q074 |
| Both pass all P4 checks | **Arch-2 production** (less ops disruption), Arch-3 paper-validation |
| Both fail Q042 17.5% concentration check | Fall back to Arch-2 only; revisit Q042 sizing in Q074 |
| Bootstrap shows Arch-3 ROE 0.04pp drop is statistically zero | Risk wins → **Arch-3 promote** |

**HV Ladder language** (per PM): not "retire". Use **"demote HV Ladder from production candidate to research/paper-only"** until enhanced HV-specific tail gating is developed.

---

## 7. P3 Verdict

**Arch-3 (radical, no HV, Q42 17.5%) is the leading risk-adjusted candidate.**

**Arch-2 (E5) is the incremental fallback.**

Both pass V1-V3 + floor 8% (within rounding). Arch-3 has materially better tail.

**Decision: P4 must validate BOTH in parallel.** No single-candidate path forward until P4 robustness checks complete.

---

## 8. References

- `q073_p3_architectures.py` — 4-architecture simulator
- `q073_p3_architecture_comparison.csv` — full comparison table
- `q073_p2a_plus_e5_candidate_memo.md` — Arch-2 (E5) origin
- `q073_p1_3r_unified_nlv_baseline.md` — Arch-0 (status quo)
- `q073_p1_5_governance_baseline.md` — Arch-1 (current SPEC-103 R5/R6 baseline) + P2A anchor (stress cap 50% / 2nd-leg 40%)
