# Q044 Tier 2 Results — BPS bp_target 15% Deep Dive

Date: 2026-05-06
Role: Quant Researcher
Window: 2023-01-01 → 2026-05-06
Account: $150,000
Script: backtest/prototype/q044_bps_sizing_tier2.py

---

## 一句话结论

**A1（bp_target 15%）通过 Tier 2 所有检验，可进入 Spec 讨论。** Sharpe 不变（0.91），Peak BP% 不变（30%），年度 attribution 稳健，Q036 共存无冲突。意外发现：将 `bp_ceiling_normal` 从 35% 升至 40% 可使 A2（20%）的 PnL 超过 A1（+$27,332 vs +$22,823）——此为独立决策项，不属于 A1 Spec 范围。

---

## Part 1 — 年度 Attribution

| 年 | N A0 | PnL A0 | N A1 | PnL A1 | ΔPNL |
|---|---|---|---|---|---|
| 2024 | 1 | $3,561 | 1 | $5,342 | +$1,781 |
| 2025 | 10 | $6,152 | 10 | $9,173 | +$3,021 |
| 2026 | 4 | $5,539 | 4 | $8,309 | +$2,770 |
| **Total** | **15** | **$15,252** | **15** | **$22,823** | **+$7,571** |

**结论**：改善均匀分布在 3 年内。N 相同，胜率相同（73.3%），PnL 差异全部来自规模线性扩展，无偶发年份驱动风险。

---

## Part 2 — 完整 PM Metrics Pack

| 指标 | A0 bp=10% | A1 bp=15% | Delta | 评估 |
|---|---|---|---|---|
| N (BPS trades) | 15 | 15 | — | — |
| Win rate | 73.3% | 73.3% | — | 相同，entry/exit 逻辑不变 |
| Total BPS PnL | $15,252 | $22,823 | +$7,571 | ✅ |
| Annualized ROE pp | 3.042% | 4.552% | **+1.510pp** | ✅ |
| Marginal $/BP-day | 0.00782 | 0.00780 | **-0.3%** | ✅ 近线性 |
| Worst trade $ | -$6,253 | -$9,380 | -$3,127 | 可接受（比例放大）|
| Worst trade % acct | -4.17% | -6.25% | -2.08pp | ⚠️ 单笔最大亏损升至 6.25% |
| Disaster 60d window | -$6,476 | -$9,714 | -$3,238 | 比例放大 |
| Disaster % acct | -4.32% | -6.48% | -2.16pp | ⚠️ 60天窗口最大亏损升至 6.48% |
| **Peak concurrent BP%** | **30.0%** | **30.0%** | **+0.0pp** | ✅ 不推高 ceiling 风险 |
| CVaR 5% | -$4,076 | -$6,633 | -$2,557 | 比例放大（接受） |
| **Sharpe (BPS)** | **0.91** | **0.91** | **+0.00** | ✅ risk-adjusted return 完全保留 |

**关键验证点**：
- **Sharpe 不变**：0.91 → 0.91。A1 是纯线性扩展，没有改变策略的 risk-adjusted quality。
- **Peak concurrent BP% 不变**：单笔 A1 BPS 最多 15%，加上同时持有的其他仓位（IC 约 7%、Diagonal 约 8%），峰值维持在 30%，距 `bp_ceiling_normal=35%` 仍有 5pp 余量。
- **Worst trade % account 上升至 -6.25%**：这是 A1 最值得注意的尾部变化。对于 Portfolio Margin 账户而言，单笔最大亏损 6.25% of $NLV 是合理的，但应在 Spec 的 risk disclosure 中明确。

---

## Part 3 — A2 (bp=20%) Ceiling Cliff 解剖

### 被封堵的 8 笔 BPS（ceiling=35%）

| 日期 | PnL (A0 scale) | 性质 |
|---|---|---|
| 2024-02-13 | +$3,561 | 盈利，被封堵 |
| 2025-01-21 | -$1,447 | 亏损，被封堵（幸运地避开）|
| 2025-09-02 | +$3,522 | 盈利，被封堵 |
| 2025-09-25 | +$2,809 | 盈利，被封堵 |
| 2025-11-26 | +$2,149 | 盈利，被封堵 |
| 2026-01-14 | +$1,549 | 盈利，被封堵 |
| 2026-04-17 | +$1,959 | 盈利，被封堵 |
| 2026-04-30 | +$2,043 | 盈利，被封堵（open at end）|

**7/8 被封堵的是盈利交易。** 这是纯粹的 adverse selection：ceiling=35% 专门在"NORMAL+BULLISH 环境下其他仓位也开着"的场景封堵 BPS，而这些恰好是 BPS 表现最好的环境。

### Ceiling 敏感性

| 变体 | N | Total PnL |
|---|---|---|
| A2 ceiling=35% | 9 | **-$2,470** |
| A2 ceiling=40% | 14 | **+$27,332** |
| A1 ceiling=35% | 15 | $22,823 |

将 `bp_ceiling_normal` 从 35% 提升到 40%，A2 (bp=20%) 可恢复 5 笔被封堵的盈利交易，总 PnL 超过 A1（+$27,332 vs +$22,823）。

**这个发现不属于 A1 Spec 的范围**，但应记录为后续决策候选：若 PM 在接受 A1 之后进一步探索 bp_target=20%，需要同步考虑将 ceiling 从 35% 升到 40%。

---

## Part 4 — Q036 共存压力测试

| 场景 | BPS BP% | IC_HV 2x BP% | Combined | Ceiling | 状态 |
|---|---|---|---|---|---|
| 10/10 IC_HV episodes | 0–15% | 14% | 最高 29.0% | 50%（HIGH_VOL）| ✅ OK |
| 最高同时并发点（2025-04-24）| 15% | 14% | 29.0% | 50% | ✅ OK |

**结论**：
- Q036 Overlay-F active（2x 因子）+ BPS A1 同时持仓时，峰值合计 BP% = 29.0%
- HIGH_VOL ceiling（50%）有 21pp 余量
- NORMAL ceiling（35%）仅在 BPS 单独开仓时适用（max 15%），不受 IC_HV 影响
- **Q036 active 决策与 A1 Spec 完全兼容，无需协调**

---

## Tier 2 裁定

### A1（bp_target 15%）— ✅ 推荐进入 Spec 讨论

**通过所有 Tier 2 检验**：
- 年度 attribution 稳健（3 年均匀分布）
- Sharpe 不变（0.91 = 0.91，pure linear scaling）
- Peak concurrent BP% 不变（30.0%，ceiling 余量充足）
- Q036 共存无冲突（峰值 29% vs 50% ceiling）
- AnnROE 从 3.042% 升至 4.552%（+1.5pp），marginal decay -0.3%

**主要 risk disclosure（Spec 必须包含）**：
- 单笔最大亏损 % account 升至 -6.25%（vs 当前 -4.17%）
- 60d 灾难窗口升至 -6.48%（vs -4.32%）
- live size rule 需同步更新："Full size — risk ≤ 4.5% of account"（当前写的是 ≤ 3%）

### A2（bp_target 20%）+ ceiling 40% — 📋 记录为后续候选

- 在 ceiling=35% 下不可行（adverse selection cliff）
- 在 ceiling=40% 下 PnL $27,332 > A1 $22,823
- 若 PM 决定同步提升 ceiling，A2 是值得研究的第二阶段方向
- **不属于当前 Spec 范围**

### Axis B（wider spread）— ❌ 已关闭

Tier 1 结论不变，不重新验证。

---

## 如果进入 Spec，关键变更

```python
# 当前
bp_target_normal   = 0.10   # SPEC-024
bp_target_low_vol  = 0.10

# 提案 (SPEC-??? Q044)
bp_target_normal   = 0.15
bp_target_low_vol  = 0.15   # 同步更新

# live size rule (strategy/selector.py _size_rule())
# 当前：
"Full size — risk ≤ 3% of account ..."
"Half size — risk ≤ 1.5% of account ..."
# 提案：
"Full size — risk ≤ 4.5% of account ..."
"Half size — risk ≤ 2.25% of account ..."
```

**不变**：normal_delta、normal_dte、profit_target、stop_mult、bp_ceiling_normal、entry gates。
