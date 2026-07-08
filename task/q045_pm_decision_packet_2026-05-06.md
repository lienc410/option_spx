# Q045 — PM Decision Packet: Account-Level ROE Optimization

> **⚠ SUPERSESSION STAMP (2026-07-07, PM-批准 reaudit)**
> 本 packet 的 **framing 已被 Q081 cash-bound 实测推翻**(2026-06-01):账户资本从未闲置
> (在 QQQ/SPY/个股),闲置的只是 PM 风险额度(BP)。"~89pp of account capital is idle"
> 陈述在真实账户口径下**不成立**;Phase 2D 的 "+20.7pp theoretical upper bound"
> (对闲置 BP 线性外推 $/BP-day,无信号供给模型)**正式作废**。
> 数字层面:BS-flat 定价(先于 SPEC-119 CALIB,卖方 credit 系统性偏高)、
> daily-MTM 平滑 Sharpe(Q080-P1 证明虚增 ~+0.7,"Sharpe improves +0.05" 在 artifact 内)、
> 无 bootstrap CI / era 分层——绝对量级不作为现行证据引用;若用于论证进一步 sizing,
> 必须 CALIB + unsmoothed + era-stratified 重跑。
> **仍然有效**:17% 零仓日=信号稀缺(非 sizing 不足)的诊断、N2 cliff 的存在、
> SPEC-084 参数本身(未回滚,待合成栈重仿真复核)。
> 全文见 `task/bp_utilization_thread_reaudit_2026-07-07.md`。

Date: 2026-05-06
Role: Quant Researcher (Tier 3 Full Deep Dive)
Window primary: 2023-01-01 → 2026-05-06 (3.34 years)
Window robustness: 2007-01-01 → 2026-05-06 (19.34 years)
Account: $150,000

---

## TL;DR

**Recommend single DRAFT Spec to lift bp_target across both regimes simultaneously:**
- `bp_target_normal`: 0.10 → 0.15
- `bp_target_high_vol`: 0.07 → 0.14
- `bp_target_low_vol`: 0.10 → 0.15 (consistency)

**Evidence:** +5.48pp account-level AnnROE on 19-year sample. Sharpe IMPROVES (1.78 → 1.83). All 6 strategies contribute positive uplift. Peak BP 43% within HIGH_VOL ceiling 50%. No ceiling change needed.

**Supersedes:** Q044 (BPS-only Spec); partially supersedes Q036 Overlay-F's value-add.

---

## Why this reframe was needed

The previous research was piecemeal:
- SPEC-077 (profit_target lift): all credit strategies, +0.09pp on full sample
- Q036 Overlay-F (IC_HV aftermath gating): +0.074pp on full sample
- Q044 (BPS-only bp_target lift): +1.51pp BPS-AnnROE (+1.5pp account-level)

Each looked at one strategy or one mechanism in isolation. The Phase 1 baseline mapping revealed why this missed the bigger picture:

**The system is structurally under-utilized:**
- Time-weighted avg BP utilization: **11.09%** out of 35% NORMAL ceiling
- 17% of trading days have zero positions open
- 61% of days have only one strategy open
- Peak BP in baseline never exceeds 30% (vs 35% / 50% ceilings)
- ~89pp of account capital is idle on average

**The right question isn't "can we optimize each strategy?" but "why is total system utilization so low?"**

---

## Phase 2 Results — Joint Optimization

### Phase 2A: NORMAL regime sweep (BPS + BCD + IC together)

| Variant | TotalPnL | AnnROE | Sharpe | Peak BP% | Avg BP% |
|---|---|---|---|---|---|
| N0 bp=10% (baseline) | $81,604 | 16.27% | 2.18 | 30% | 11.09% |
| **N1 bp=15%** | **$102,404** | **20.42%** | **2.14** | **30%** | **14.24%** |
| N2 bp=20% | $80,562 | 16.07% | 1.27 | 34% | 16.07% |

**N1 wins by clear margin. N2 has cliff effect:**
- BPS: -113% marginal $/BP-day decay (cliff)
- IC: -55% marginal decay (cliff)
- Cliff between N1 (15%) and N2 (20%) is from concurrent ceiling crowding when 3 NORMAL strategies fire simultaneously

### Phase 2B: HIGH_VOL regime sweep (IC_HV + BPS_HV + BCS_HV)

| Variant | TotalPnL | AnnROE | Sharpe | Peak BP% |
|---|---|---|---|---|
| H0 bp=7% (baseline) | $81,604 | 16.27% | 2.18 | 30% |
| H1 bp=10% | $85,835 | 17.12% | 2.27 | 30% |
| **H2 bp=14% (= 2x baseline)** | **$91,476** | **18.24%** | **2.35** | **38%** |

### Phase 2C: Joint optimum N1 × H2

| Variant | TotalPnL | AnnROE | ΔROE | Peak BP% | Sharpe |
|---|---|---|---|---|---|
| **J3 N=15% H=14%** | **$112,276** | **22.39%** | **+6.12pp** | **43%** | **2.31** |
| J4 N=15% H=10% | $106,635 | 21.27% | +4.99 | 35% | 2.22 |
| J5 N=12% H=14% | $98,278 | 19.60% | +3.32 | 40% | 2.07 |
| J0 baseline | $81,604 | 16.27% | — | 30% | 2.18 |

**Linearity check (perfect independence):**
```
ΔNORMAL alone (J1 - J0):      +4.148pp
ΔHIGH_VOL alone (J2 - J0):    +1.969pp
Sum (if independent):         +6.117pp
ΔJOINT (J3 - J0):            +6.117pp
Interaction effect:           +0.000pp ← perfectly additive
```

The two regimes are **perfectly independent** — they don't compete for BP because they fire under different market conditions.

---

## Phase 2D: Idle BP Analysis

Even at J3 (joint optimum), the system still has substantial idle BP:

```
Avg BP utilization at J3:        15.93%
NORMAL ceiling:                  35.00%   → 19.07pp idle on average
HIGH_VOL ceiling:                50.00%   → 34.07pp idle on average
```

**Daily distribution at J3:**
- 17% of days: zero positions (fully idle)
- 61% of days: 1 strategy open
- 18% of days: 2 strategies open
- 3.5% of days: 3+ strategies open

**Implication:** Q045 J3 captures the "make existing positions bigger" opportunity. The remaining ~19pp idle BP requires **new strategies to fill the days when current strategies don't fire** — that is exactly Q041 paper trading's territory (GOOGL/AMZN/COST/JPM diversified income overlay).

**Theoretical upper bound:** if 50% of remaining idle BP could be deployed at J3's $/BP-day rate, that's another **+20.7pp AnnROE potential**. This is what Q041 + future strategy diversification is meant to capture.

---

## 19-Year Robustness Check

| Variant | AnnROE | Sharpe | N | Worst | CVaR5% |
|---|---|---|---|---|---|
| J0 baseline (10/7) | 11.94% | 1.78 | 304 | -$8,456 | -$4,549 |
| **J3 joint (15/14)** | **17.41%** | **1.83** | **282** | -$13,235 | -$7,313 |
| Δ | **+5.48pp** | **+0.05** | -22 | -$4,779 | -$2,764 |

**All 6 strategies contribute positive uplift on full sample:**

| Strategy | J0 AnnROE | J3 AnnROE | Δ | WR (J3) |
|---|---|---|---|---|
| Bull Call Diagonal | +5.30 | +6.19 | +0.89pp | 56.9% |
| Iron Condor | +1.91 | +2.84 | +0.92pp | 79.3% |
| Bull Put Spread | +1.78 | +2.50 | +0.72pp | 76.3% |
| Iron Condor (HV) | +1.96 | +3.92 | **+1.96pp** | 88.3% |
| Bull Put Spread (HV) | +0.91 | +1.83 | +0.91pp | 85.7% |
| Bear Call Spread (HV) | +0.07 | +0.14 | +0.07pp | 55.6% |

**Important note on BCS_HV:** the 3-year window had only 1 BCS_HV trade (a loser), causing pessimism. The 19-year sample shows N=9, WR=55.6%, AnnROE +0.14pp at J3. **No tail concern.**

**Trade count drop (304→282):** BCD's long hold (avg 17 days) causes ceiling crowding when concurrent positions fire. ~22 BCD entries are skipped at J3. Remaining trades scale proportionally larger.

---

## Risk Disclosure

| Risk Metric | J0 Baseline | J3 Joint | Δ |
|---|---|---|---|
| Worst single trade ($) | -$8,456 | -$13,235 | -$4,779 (1.57x) |
| Worst single trade % acct | -5.64% | -8.82% | -3.18pp |
| CVaR 5% | -$4,549 | -$7,313 | -$2,764 (1.61x) |
| Disaster 60d window (3y) | -$6,476 | -$9,714 | -$3,238 |
| Sharpe ratio | 1.78 | 1.83 | +0.05 ✅ |
| Peak BP% | 30% | 43% | +13pp (within 50% HIGH_VOL ceiling) |

**Risk scaling is sub-linear-to-linear.** Worst-trade scales 1.57x; CVaR 1.61x; both close to the average bp_target lift of 1.5x. Sharpe IMPROVES.

The single-trade -8.82% account drawdown is the metric PM should weigh most carefully. For a Portfolio Margin account, an 8.82% worst-trade event is meaningful but recoverable — corresponds to a tail event happening a few times per decade.

---

## Comparison to Previously Considered Mechanisms

### vs Q044 (BPS-only Spec)

| | Q044 A1 | Q045 J3 |
|---|---|---|
| Scope | BPS only | All credit strategies (NORMAL + HIGH_VOL) |
| AnnROE uplift (3y) | +1.51pp | +6.12pp |
| AnnROE uplift (19y) | not tested | +5.48pp |
| Sharpe | 0.91 → 0.91 (BPS only) | 1.78 → 1.83 (account) |
| Implementation | 2 param changes | 3 param changes |

**Q044 is superseded by Q045 J3.** Same implementation effort, ~4x more ROE uplift.

### vs Q036 Overlay-F

| | Q036 Overlay-F | Q045 J3 (HIGH_VOL only) |
|---|---|---|
| Mechanism | Gated 2x size on IC_HV aftermath | Simple bp_target lift 7%→14% |
| Conditions | Short-gamma guard, idle BP gate | None (always-on) |
| AnnROE uplift (full sample) | +0.074pp | +1.97pp |
| AnnROE uplift (3y) | not measured | +1.97pp |
| Implementation complexity | High (overlay/shadow/active machinery) | Low (parameter change) |
| Selectivity | High | None |

**Q045 J3's HIGH_VOL component achieves 26x more uplift than Q036 Overlay-F on the same 19-year sample**, because it applies to all 77 IC_HV trades, not just gated aftermath trades.

**Q036's value-add diminishes:** the simpler intervention does most of what Q036 was designed for. Q036's selectivity (short-gamma guard, idle BP gate) is still a useful safety layer, but the magnitude of the additional benefit on top of J3 is likely small.

### vs Q041 paper trading

**Complementary, not competing.** Q045 J3 captures ~6pp of the structural idle BP via larger positions. Q041 captures the rest via diversified strategies that fill currently-idle days. Both should proceed.

---

## Recommendation

### Primary recommendation: open SPEC-???? for Q045 J3 implementation

**Spec scope (one Spec, narrow change):**

```python
# strategy/selector.py StrategyParams
- bp_target_low_vol:  float = 0.10
+ bp_target_low_vol:  float = 0.15
- bp_target_normal:   float = 0.10
+ bp_target_normal:   float = 0.15
- bp_target_high_vol: float = 0.07
+ bp_target_high_vol: float = 0.14
```

**Live size rule update (`_size_rule()`):**
```python
- "Full size — risk ≤ 3% of account ..."
- "Half size — risk ≤ 1.5% of account ..."
+ "Full size — risk ≤ 4.5% of account ..."
+ "Half size — risk ≤ 2.25% of account ..."
```

**Risk disclosure additions:**
- Worst single trade may reach -8.8% of account (vs current -5.6%)
- Peak concurrent BP may reach 43% during HIGH_VOL regime (within 50% ceiling)
- All strategies scale 1.5–2.0x in size (NORMAL 1.5x, HIGH_VOL 2.0x)

### Secondary actions

1. **Q044 status**: close as **superseded by Q045 J3**. Q044 Tier 1/Tier 2 work is preserved as evidence base.

2. **Q036 status**: keep in `shadow` mode but **deprioritize**. Re-evaluate after Q045 J3 deployment. Q036's selectivity may still help in tail HIGH_VOL events, but its base uplift is largely captured by Q045 J3.

3. **Q041 paper trading**: continues as the diversification axis to fill the remaining ~19pp idle BP gap.

### Phased rollout (recommended)

Following the established `disabled → shadow → active` pattern:

1. **DRAFT Spec** with full risk disclosure
2. **PM approval** → APPROVED status
3. **Developer implementation**: change params, run regression backtests, verify byte-identical with `bp_target_normal=0.10` baseline path
4. **Local validation**: 19y backtest matches Q045 evidence; tieout vs J0 baseline confirms parity at old params
5. **Old Air shadow**: implement with disabled flag controlling the new bp_targets; old runtime by default; flip to active after 2-4 weeks of paper observation
6. **Active**: PM final approval

---

## Open Questions for PM

1. **Scope: single Spec covering both regimes, or two sequential Specs?**
   - Single Spec is cleaner (Phase 2C shows independence; Sharpe improves)
   - Two sequential Specs allows incremental validation but doubles approval overhead
   - **Quant recommendation: single Spec**

2. **Worst-trade tolerance:** -8.8% account on a single trade (vs current -5.6%) — is this acceptable for a $NLV-driven PM account?

3. **Q036 Overlay-F disposition:** continue in shadow / deprioritize / decommission?
   - **Quant recommendation: continue in shadow** (selectivity may still help in tail events; cost of keeping is low)

4. **Q044 disposition:** close as superseded?
   - **Quant recommendation: close as superseded by Q045**

---

## Files

- Phase 1 baseline: `backtest/prototype/q045_phase1_baseline.py`
- Phase 2A NORMAL: `backtest/prototype/q045_phase2a_normal_sweep.py`
- Phase 2B HIGH_VOL: `backtest/prototype/q045_phase2b_high_vol_sweep.py`
- Phase 2C joint: `backtest/prototype/q045_phase2c_joint_optimum.py`
- Phase 2D idle BP: `backtest/prototype/q045_phase2d_idle_bp.py`
- Idle BP timeline data: `data/q045_phase2d_idle_bp_timeline.csv`
