# Q073 P1.5 — Governance Baseline (DECISION-GRADE P2A ANCHOR)

> **Status: P1.5 DECISION-GRADE. Provides P2A anchor.**
> **P2A baseline: stress SPX cap 50% / second-leg cap 40%.**
> 不以 actual R1-R6 (60% / 50%) 作 baseline，因 V2 仍 fail.

**Date**: 2026-05-17
**Parent**: `q073_p1_3r_unified_nlv_baseline.md`

---

## TL;DR

P1.5 收敛 Q073 到一个清楚 optimization:

```
在 stress cap 50% / second-leg cap 40% V2-pass 框架下，
找 +0.24pp ROE 把 7.76% → ≥ 8% floor.
```

---

## 1. P1.5a — Actual SPEC-103 R1-R6 (PM 修正后)

Applied actual governance (per Q072 / SPEC-103):
- Normal SPX cap = **70%** (R1 default)
- Stress SPX cap = **60%** (R5 reduces 70% → 60%)
- Second-leg cap = **50%** (R6 effective half-size)
- Stress trigger: `vix ≥ 22 OR dd_20d ≤ -4% OR dd_60d ≤ -4%`, 3-day rolling persistence
- Second-leg trigger: `dd_60d ≤ -8% AND vix ≥ 25`

### Result

```
Ann ROE (geo):    7.87%   (+0.37pp vs P1.3R bare 7.50%)
MaxDD:           -13.44%  V1 PASS (14pp buffer)
Worst 20d:       -11.82%  V2 FAIL (-0.82pp over)
Worst 63d:       -11.45%  V3 PASS (5.55pp buffer)
Sharpe:           1.76
Final equity:    $6.56M (from $894k)
```

### R6 timing analysis (DotCom 2000-2002)

- R6 first triggered **2000-02-18**
- V2 worst-20d window ends **2000-04-14**
- R6 fired BEFORE V2 breach, but R6 cap = 50% (only 10pp deeper than stress 60%) 不够深 to prevent V2 fail

**Key finding (PM 修正)**: 现有 R1-R6 的 SPX cap 范围 70% / 60% / 50% **不足以修复 V2 fail**. Stress cap 仍是 60%, R6 仅 50%. Need enhanced stress cap.

---

## 2. P1.5b — Enhanced stress cap sensitivity

Normal cap fixed at 70%. Stress cap and 2nd-leg cap varied. Cash auto-fills residual.

| Stress cap | 2nd-leg cap | Ann ROE | MaxDD | **Worst 20d** | V1 | **V2** | V3 | All veto | Floor 8% |
|---|---|---|---|---|---|---|---|---|---|
| 60% | 50% | 7.87% | -13.4% | -11.82% | ✓ | **✗** | ✓ | NO | NO |
| 55% | 45% | 7.82% | -12.5% | -11.00% | ✓ | ✗ (border) | ✓ | NO | NO |
| **50%** | **40%** | **7.76%** | **-11.6%** | **-10.18%** | ✓ | **✓** | ✓ | **YES** | NO |
| 45% | 35% | 7.71% | -10.7% | -9.37% | ✓ | ✓ | ✓ | YES | NO |
| 40% | 30% | 7.65% | -9.8% | -8.55% | ✓ | ✓ | ✓ | YES | NO |

### Findings

1. **Stress cap 50% / second-leg 40% is the V2-PASS frontier**: highest ROE 7.76% with all V1-V3 veto pass.
2. Below 50% (45% / 40%): V2 buffer grows but ROE drops marginally.
3. **No single-lever stress cap reduction reaches floor 8%**.
4. Gap to floor: **0.24pp** at the V2-pass frontier.

### Future SPEC implication

If P2A confirms stress cap 50% / 2nd-leg 40% are optimal, the existing SPEC-103 R5/R6 caps (60% / 50%) need to be tightened to (50% / 40%). This is a future SPEC consideration; **not** part of Q073 SPEC drafts (out of scope per P0).

---

## 3. Q073 现状收敛

| 维度 | 状态 |
|---|---|
| Architecture feasibility | ✓ 已找到 V1-V3 pass 架构 (stress cap 50%) |
| ROE floor 8% achievement | ❌ 0.24pp gap |
| V1 MaxDD 28% buffer | ✓ 14pp buffer |
| V2 worst-20d 11% | ✓ pass with -10.18% |
| V3 worst-63d 17% | ✓ pass with -9.87% |
| Diversification | ✓ correlations 0.28 / 0.02 / 0.00 |
| Crisis modern (GFC/COVID/2022) | ✓ all positive on PIT basis |
| **Q073 task post-P1.5** | **Find +0.24pp ROE while staying within V2-pass frontier** |

---

## 4. P2A Anchor (locked)

**P2A baseline (V2-pass frontier)**:
```
Normal SPX cap     = 70%
Stress SPX cap     = 50%
Second-leg SPX cap = 40%
HV Ladder          = 5%
Q042 Sleeve A      = 10%
Cash (BOXX)        = residual
```

**P2A levers**:
- L1: Normal SPX 70 / 75 / 80 (stress/2nd-leg locked at 50/40)
- L2: HV Ladder 5 / 7.5 / 10%
- L3: Q042 Sleeve A 10 / 12.5 / 15%
- L4: Cash floats as residual

**P2A 排序规则** (per PM):
1. 筛 V1/V2/V3 pass
2. 筛 ROE ≥ 8%
3. 在 pass 集合中选 ROE 最高

不先按 ROE 排. Tail-risk preservation 优先.

---

## 5. P2A 候选清单 (PM 起的 hypothesis-driven sweep)

| Candidate | Normal SPX | HV | Q042 | Cash | 预期 |
|---|---|---|---|---|---|
| **Base** | 70% | 5% | 10% | 15% | 7.76% (P1.5b confirmed) |
| **A** | 75% | 5% | 10% | 10% | +0.5-1pp from normal cap up |
| **B** | 70% | 7.5% | 10% | 12.5% | +0.4pp from HV up |
| **C** | 70% | 5% | 12.5% | 12.5% | +0.2pp from Q042 up |
| **D** | 75% | 7.5% | 10% | 7.5% | +0.7-1pp combined |
| **E** | 75% | 5% | 12.5% | 7.5% | +0.5-1pp combined |
| **F** | 75% | 7.5% | 12.5% | 5% | +0.9-1.5pp combined (likely best) |

Stress cap 50% / 2nd-leg 40% 在所有 candidate 保持不变 (V2-pass anchor).

---

## 6. P2A Methodology Note

- **State-dependent SPX allocation only**: stress/2nd-leg 仅降 SPX, 不动 HV/Q042 (per PM, 初版不让 HV/Q042 stress 自动降, 除非证明它们是 stress driver)
- **HV / Q042 sleeve caps are static** (不 state-dependent)
- **Cash = residual** (auto-fills)
- **PnL scaling** (rescale P1.3R outputs):
  - SPX: scale by (current_alloc / 60%) since P1.3R baseline was 60%
  - HV: scale by (HV_alloc / 5%) since P1.3R was 5% ($44.7k)
  - Q042: scale by (Q42A_alloc / 10%) since P1.3R was 10% ($89.4k)
  - Cash: scale by (cash_alloc / 25%) since P1.3R was 25% ($223.5k)

---

## 7. Stopping conditions for P2A

- If ANY candidate satisfies V1-V3 + floor 8% → **P2A SUCCESS** → confirm, move to P3 candidate architectures + P4 full simulation
- If NO candidate satisfies floor 8% (gap remains > 0pp):
  - Consider P2B cap framework relaxation (cautious — V2 buffer thin)
  - Consider P2C strategy retire / matrix redesign (per radical tear-down clause)
  - Consider lowering normal SPX cap above 80% (V1 risk reserve check needed)
- If candidate beats floor 8% AND V2 buffer significantly degrades (e.g., approach -10.8%) → flag as marginal, not preferred

---

## 8. References

- `q073_p1_3r_unified_nlv_baseline.md` — P1.3R baseline
- `q073_p1_4_idle_friction_v2_forensic.py` + outputs
- `q073_p1_5_governance_sim.py` + outputs
- `q073_p1_5b_stress_cap_sweep.csv` — full sensitivity table
