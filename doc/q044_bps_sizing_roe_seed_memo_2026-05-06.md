# Q044 — BPS Spread Sizing and Account-Level ROE Seed Memo

Date: 2026-05-06
Status: seed / Tier 1 research candidate
Priority: low-to-medium (排在 Q036 shadow observation 和 Q041 paper-trading startup 之后)

---

## 触发问题

PM 提出：BPS 在 live trading 中每笔只使用 ≤ 10% 账户 BP，当账户只有一笔 BPS 持仓时，剩余 25% 的"结构性闲置 BP"（天花板 35% - 实际使用 10%）是否是一种浪费？能否通过加大 BPS 规模来提升账户级 ROE？

---

## 现状

### 当前 BPS sizing 参数

```python
# strategy/selector.py
bp_target_normal   = 0.10   # NORMAL 每笔目标 BP（回测引擎用）
bp_ceiling_normal  = 0.35   # 全部持仓合计上限
max_short_gamma_positions = 3
```

### live trading 实际 size rule

```
Full size — risk ≤ 3% of account (signals agree + VIX flat/falling)
Half size — risk ≤ 1.5% of account (VIX rising or signals mixed)
```

### 当前 BPS 参数（NORMAL regime）

- Short put δ0.30，Long put δ0.15，DTE 30
- max risk = spread_width − net_credit
- BP = max risk（垂直价差 PM 账户下 BP ≈ 最大亏损额）

### 结构性 BP 分布（典型 NORMAL 环境）

| 来源 | BP 占比 |
|---|---|
| 单笔 BPS | 10% |
| aftermath（如有） | ~5–7% via Overlay-F |
| 结构性闲置 | ~25% |

---

## 核心研究问题

**Q1 — 加宽 spread width 对 ROE 的影响**
如果把 BPS 的 spread width 从当前水平（δ0.30/δ0.15，约 70–90 points）拉宽到更大区间（如 120–150 points），使 bp_target 从 10% 升到 15% 甚至 20%：
- 回测 ROE 是否提升？
- marginal $/BP-day 是否保持合理？
- 尾部风险（worst trade / CVaR）如何变化？

**Q2 — 加大合约数量（保持 width，加倍合约）**
在相同 spread width 下将合约数从 1 提到 2（bp_target → 20%）：
- 和加宽 width 相比，哪种方式的 Sharpe / CVaR 更优？
- 是否会超出 bp_ceiling_normal（35%）？

**Q3 — BPS 加大 vs Q036 Overlay-F 竞争**
BPS 加大和 Overlay-F 都在消耗同一块闲置 BP（~25%）：
- 两者应如何分配这块 BP？
- BPS 加大是否会与未来的 Q036 active 模式产生 BP 争抢？

**Q4 — 与 live sizing rule 的一致性**
当前 live recommendation 写的是"risk ≤ 3% of account"（full size），但 bp_target 是 10%。
两者的对应关系需要明确：
- 在多大的账户规模下，3% risk ≈ 10% BP？
- 如果账户是 Portfolio Margin 账户，actual BP consumed 可能远低于 spread width × contracts × 100

---

## 初步直觉（Tier 1 Quick Scan）

1. **加大 BPS 有 ROE 上行潜力**，前提是：spread 是定义风险结构，不会触发 naked short 风险。max risk 已完全 capped。
2. **主要风险是尾部敏感性**：更大的 spread width 意味着在黑天鹅事件中亏损更多美元（即使 % 亏损不变）。
3. **marginal $/BP-day 可能递减**：更大 spread 的信用收取比例通常低于窄 spread（gamma 定价的非线性），需回测验证。
4. **与 Q036 的关系需厘清**：如果 Q036 Overlay-F 未来进入 active，与更大 BPS 同时存在可能超出 bp_ceiling。应先解决 Q036 的 active 决策，再考虑 BPS 加大。

---

## 明确排除在研究范围外

- 不改变 BPS 的入场条件（IVP 区间、regime gate、VIX 趋势）
- 不改变 delta 目标（δ0.30/δ0.15）
- 不改变 DTE（30 DTE）
- 不评估是否允许 BPS 重叠持仓
- 不与 Q041 paper-trading 竞争 BP 分析（两者账户物理分离）

---

## 前置依赖

- Q036 Overlay-F shadow observation 结果（影响闲置 BP 的实际可用量）
- 明确 live PM 账户中 BPS 的 actual Schwab BP consumed（与 max risk 之间可能有折扣）

---

## 建议下一步（如 PM 决定推进）

1. **Tier 1 Quick Scan**（Quant，Sonnet）：在现有回测框架里运行 3 个 width variant，读 marginal $/BP-day 和 worst trade
2. 如果 Tier 1 结论积极，再做 **Tier 2**：参数扫描 + CVaR + Q036 竞争分析
3. 不急于进入 Spec，先观察 Q036 active 决策结果

---

## 关联研究

- `Q036` — Overlay-F idle BP 部署（竞争同一块闲置 BP）
- `SPEC-077` — profit_target 从 0.50 升到 0.60（已对 BPS 生效）
- `SPEC-024` — 原始 bp_target 设定和 2× scale 校准
- `doc/q036_pm_decision_packet_2026-04-26.md`
