# ES_Puts Strategy (SPX 版)

> 原始参考：`spec_initial.md`（基于 /ES 期货期权的实盘体系）
> 本 spec 将 /ES → SPX 期权，Long VTI → Long SPY

相关材料：
- [原始体系说明](/Users/lienchen/Documents/workspace/SPX_strat/research/strategies/ES_puts/spec_initial.md)
- [详细研究记录](/Users/lienchen/Documents/workspace/SPX_strat/research/strategies/ES_puts/research_notes.md)
- [回测代码](/Users/lienchen/Documents/workspace/SPX_strat/research/strategies/ES_puts/backtest.py)

---

## 整体架构

三层叠加：

| 层 | 内容 | 占比 |
|----|------|------|
| Layer 1 | Long SPY（核心 beta 敞口） | 目标 70% NLV |
| Layer 2 | SPX Short Puts（theta 收益引擎） | 动态，受杠杆表约束 |
| Layer 3 | Black Swan Hedges（尾部保护） | ~3%/年 drag |

---

## Layer 1 — Long SPY

- 买入 SPY，目标持仓 = 70% NLV
- 每月末用 theta 收益或现金充值维持比例
- 不做择时

---

## Layer 2 — SPX Short Puts（核心策略）

### 合约参数

| 参数 | 值 |
|------|----|
| 标的 | SPX（欧式，现金结算） |
| 结构 | 裸卖 put（naked short put） |
| Delta | ~20 delta（±5 delta 弹性空间） |
| DTE | 21 / 28 / 35 / 42 / 49，同时持有多档 |
| 仓位频率 | 趋势明确时，每周分批开 1–2 个到期档 |

### 入场时机（trend filter）

| 市场状态 | 操作 |
|---------|------|
| 明确上涨趋势 / 去风险后反弹（如选举后、VIX spike 后） | 积极开仓，可加到杠杆上限 |
| 下跌趋势 / 回调中 | 仅维持现有仓位，不新开；到达止损线才砍仓 |

### 出场规则

| 情形 | 操作 |
|------|------|
| 亏损达权利金 -300% | 硬止损，立即平仓 |
| 临近到期且被测试 | 提前平仓，规避 gamma risk |
| 正常盈利，上涨趋势明确且杠杆宽裕 | 持有至 +80–90% |
| binary event 前（FOMC/财报等）且心存疑虑 | +50% 提前止盈 |
| 止盈同时 | 同步开新仓（相当于 roll up for credit） |

---

## 杠杆管理（VIX-Based）

SPY Beta-Weighted Delta / NLV 上限：

| VIX 水平 | 最大 BPu | 最大杠杆（B-Delta/NLV×SPY） |
|----------|---------|--------------------------|
| 40+      | 50%     | 2.5× |
| 30–40    | 40%     | 2.25× |
| 20–30    | 35%     | 2.0× |
| 15–20    | 30%     | 1.75× |
| 10–15    | 25%     | 1.5× |

超出上限：优先砍仓；若认为是 panic-induced 且确信方向，可临时买短期 NTM put 对冲至回到阈值内。

---

## Layer 3 — Black Swan Hedges（BSH）

| 条件 | 工具 | 频率 | 成本 |
|------|------|------|------|
| VIX > 20 | SPY 7 DTE、10% OTM put | 每周买 | 0.04% NLV/周 |
| VIX ≤ 20 | SPY 30 DTE、20% OTM put | 每周买 | 0.04% NLV/周 |
| VIX < 15 | VIX 120 DTE、10 delta call | 每月买 | 0.08% NLV/月 |
| **合计** | | | **~3% NLV/年** |

管理原则：BSH 仓位只在对应平仓其他亏损头寸时才兑现盈利；其余任其到期。

---

## 与现有 SPX Credit 策略的关键差异

| 维度 | SPX Credit（现有） | ES_Puts（本策略） |
|------|-------------------|-----------------|
| 结构 | Spread（有限风险） | 裸 put（无限风险，靠杠杆表） |
| 方向性 | 中性（IC 为主） | 明确做多 delta |
| 入场触发 | VIX regime + IV signal（量化） | 趋势判断（规则+主观混合） |
| 杠杆控制 | 固定 BP% per trade | 动态，VIX 分档 |
| 尾部对冲 | 无 | BSH 系统 |
| 止损 | 信号变化触发 | -300% credit 硬止损 |

---

## 研究问题（优先级排序）

1. **Q1（最关键）**：Trend filter 是否有显著 alpha？上涨趋势入场 vs 无条件机械入场，P&L 差异的统计显著性
2. **Q2**：DTE 梯度（21/28/35/42/49）vs 单一 45 DTE 的 Sharpe 差异
3. **Q3**：裸 put vs put spread 的 risk-adjusted return（相同 delta、相同 stop）
4. **Q4**：BSH 3% drag 的 CVaR 改善是否合算

---

## 回测范围

- 数据：SPX（现有 `data/market_cache`），SPY 用于 BSH 定价
- 起始日期：2000-01-01（与现有策略对齐）
- 基准：Long SPY（同期年化已知：6.1%）
- 对比：现有 SPX Credit 策略（年化 8.2%，Sharpe 1.33）

---

## 实施阶段

- [ ] Phase 1：Q1 验证 — 单一 45 DTE / 20 delta / -300% stop，加 trend filter vs 无 filter
- [ ] Phase 2：Q2 验证 — DTE 梯度实现与对比
- [ ] Phase 3：完整体系（含 BSH + 杠杆表）
- [ ] Phase 4：与现有策略合并持仓的相关性分析

---

## 最新研究结果（2026-04-11）

当前判断：**研究继续，状态为 `hold`，暂不进入生产 Spec。**

当前不直接推进实现的原因：
- 主要结果仍基于 SPX proxy，不是 /ES 真实期权历史数据
- 裸 put、动态杠杆表、BSH 赔付属于体系级建模，不是单一低风险实现单元
- 下一步更合理的做法是先收缩为最小可验证 cell，而不是直接实现完整三层系统

### Phase 1：单一 45 DTE / 20 delta / -300% stop

| 指标 | SPX Credit | baseline | filtered |
|------|------------|----------|----------|
| 年化收益 | 8.2% | -0.1% | 0.2% |
| 最大回撤 | -13.1% | -18.3% | -16.0% |
| Sharpe | 1.33 | -0.00 | 0.08 |
| 胜率 | — | 78.7% | 80.6% |
| avg P&L/trade | — | -$12 | +$29 |
| 止损率 | — | 19.0% | 16.0% |
| Bootstrap CI | — | `[-83,+65]` | `[-60,+112]` |

结论：
- Trend filter 方向上有效，`filtered` 在各维度均优于 `baseline`
- 但统计显著性不足，bootstrap CI 仍跨 0
- 单槽位下仓位过小，收益与 Sharpe 被明显压制

### Phase 2：多 DTE 梯度

| 维度 | baseline | filtered | 结论 |
|------|----------|----------|------|
| 年化收益 | 1.3% | 1.2% | 相近 |
| 最大回撤 | -38.5% | -23.3% | filtered 明显更优 |
| Sharpe | 0.16 | 0.20 | filtered 略优 |
| 笔数 | 1966 | 1317 | 样本显著增加 |
| avg P&L | $97 | $135 | filtered 高 39% |
| Bootstrap | `[-33,+238]` | `[+30,+276]` | filtered 首次达到显著 |

结论：
- Trend filter 的主要价值体现在风险控制，不是显著提升年化收益
- DTE 梯度提升了交易频率与统计稳定性

### PM 保证金公式校正

原先使用 `15% of notional` 偏保守。基于 OCC Portfolio Margin：

```text
Method A = 15% × notional − OTM金额 + premium
Method B = 10% × strike × 100 + premium
BP Required = max(Method A, Method B)
```

在当前 20-delta / 45 DTE 条件下，实际 PM 约为 **notional 的 10.7%**。

影响：
- 同样 BP target 下，可做约 1.40 倍更多合约
- filtered 的 avg P&L 与 bootstrap 显著性进一步改善
- 但回撤也同步扩大，裸 put 的尾部风险更加清晰

### Phase 3：杠杆表 + BSH 成本

| 模式 | 年化 | 最大回撤 | Bootstrap |
|------|------|----------|-----------|
| P2 filtered | 1.6% | -30.4% | `[+47,+393]` |
| P3 baseline | -1.9% | -71.5% | 不显著 |
| P3 filtered | 0.0% | -44.0% | `[+71,+415]` |

结论：
- 动态杠杆表不能脱离 trend filter 单独评估
- 若无 trend filter，高 VIX 时加仓会在下跌中放大亏损
- BSH 成本已扣除，但赔付未建模时，P3 回撤仍偏保守

### Phase 4：BSH 赔付建模 + 与 SPX Credit 的相关性

| 指标 | P3 cost-only | P4 BSH payoff |
|------|--------------|---------------|
| 年化收益 | 0.0% | 1.3% |
| Sortino | 0.05 | 0.98 |
| 最小净值/起始 | 57.3% | 64.0% |
| 最终净值 | $501k | $699k |
| avg P&L | $216 | $256 |

关键发现：
- BSH 在建模赔付后确实改善了组合生存性
- 与现有 SPX Credit 的日收益相关性约为 **-0.028**
- 若体系最终成立，最有价值的属性之一可能是**分散化**，而非单独收益最大化

## 当前研究判断

### 已得到的稳定结论

1. Trend filter 很可能有效，且主要改善风险控制
2. 多 DTE 梯度提高了统计稳定性，但不是唯一 alpha 来源
3. 动态杠杆表必须与 trend filter 配套使用
4. BSH 若计入真实赔付，尾部保护有实际价值
5. 与现有 SPX Credit 近零相关，是值得继续追踪的组合层发现

### 仍未解决的关键不确定点

1. 当前结果仍大量依赖 SPX proxy
2. 裸 put 需要独立于 spread engine 的 P&L / 风险建模
3. 完整体系范围过大，不适合直接进入实现阶段

### 建议的下一步范围

若后续推进，应先收缩为单一 research cell：

- `/ES short put`
- 单一 45 DTE
- 20 delta
- trend filter
- `-300%` credit stop
- 暂不纳入动态杠杆表
- 暂不纳入 BSH

该最小单元验证通过后，再考虑是否拆分为后续独立 Spec。

---

Status: DRAFT
