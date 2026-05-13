# Addon Greek Orthogonality — Aftermath vs Q042 Drawdown Overlay

**Date**: 2026-05-12
**Author**: Quant Researcher
**Purpose**: 明确两个 "post-decline entry" addon（SPEC-064 Aftermath broken-wing IC vs Q042 Drawdown Overlay）在 portfolio Greek 维度的正交关系，避免概念上误判为"功能重复"。

---

## TL;DR

**Aftermath 与 Q042 是 low-overlap, structurally non-redundant addon，不应合并或竞争**。两者在四个维度独立：

1. **信号空间**：Aftermath 用 VIX 结构；Q042 用 SPX 价格 drawdown
2. **方向 / Greek 符号**：Aftermath = short vega + short gamma；Q042 = long delta + long gamma + long vega（**符号反向**）
3. **规模**：Aftermath 走主 sleeve；Q042 capped 10-20% combined BP（[q042_gate.py](../strategy/q042_gate.py)）
4. **执行**：Aftermath 自动入场（[selector.py](../strategy/selector.py)）；Q042 Telegram → 手动

> **Wording caveat（per Q066 2nd Quant Review 2026-05-12）**：本文档使用 **"non-redundant"** 而非 **"fully orthogonal"**。Greek sign opposition supports non-redundancy 但 **does not guarantee PnL hedge effectiveness**——vega/gamma 的 strike location、profile 形态、notional 不同，符号反向 ≠ portfolio 风险缓和。同时持仓时存在 co-loss failure path（见 §3 修订 + §7 新增）。

---

## 1. 信号机制对照

| 维度 | SPEC-064 Aftermath | Q042 Drawdown Overlay |
|---|---|---|
| **核心信号** | trailing 10-TD VIX peak ≥ 28 且 当前 VIX ≤ peak × 0.90 且 VIX < 40 | A: SPX `ddATH ≤ -4%`（首次穿越自上次 re-arm）；B: `ddATH ≤ -15%` outer + MA10 reclaim 30-TD inner |
| **信号空间** | **波动率结构**（VIX peak 与回落幅度）| **价格 drawdown**（SPX vs ATH） |
| **触发场景代表** | 2008Q4 余震、2020-03 COVID 后段、2025-04 关税回落 | A: 任何 SPX -4% 回撤；B: 大型熊市拐点 |
| **Re-arm** | 自动（每日窗口）| A/B: `ddATH ≥ -2%` 之后 |
| **频率（2007-2026）** | 518 trading days ≈ 27 days/yr（见 Q065 R-20260512-01）| A: 估算 ~2-4 次/yr；B: ~1-2 次/十年 |

## 2. 结构 / Greek 对照

| Greek | SPEC-064 Aftermath（Broken-wing IC V3-A）| Q042 Sleeve A（30 DTE Long Call Spread）| Q042 Sleeve B（90 DTE Long Call Spread）|
|---|---|---|---|
| **Delta** | 微 negative（broken-wing tilt 决定 net delta）| **Long delta**（call spread）| **Long delta** |
| **Gamma** | **Short gamma**（卖 IC 中央）| Long gamma（凸性多头）| Long gamma |
| **Vega** | **Short vega**（IV 收缩获利）| Long vega（IV 上升获利）| Long vega |
| **Theta** | **Long theta**（premium decay 获利）| Short theta（持有期 decay 损失）| Short theta |
| **赚什么钱** | IV elevated 已开始 mean-revert + 价格在 short wings 之间停留 | SPX 反弹 → call spread 接近 max payoff | SPX 持续反弹 → 90D 兑现凸性 |
| **如何失败** | IV 维持高位 + 价格穿出 short wings；VIX 反弹 ≥ 40 | SPX 进一步深跌 / 横盘到 expiry | SPX 进一步深跌 |

**关键观察**：**Aftermath 是 short vol-of-vol bet，Q042 是 long convexity bet**。两者 Vega 符号相反；两者 Gamma 符号相反；两者 Theta 符号相反。

## 3. 共持仓的 portfolio 层 Greek 符号（不等于 PnL hedge）

如果两个 addon 在某事件下都触发（例如 SPX -10% + VIX 30→25 后回落），portfolio 层 net Greek **符号** 大致：

| Greek | Aftermath 贡献 | Q042 A 贡献 | Q042 A+B 贡献 | Sign net |
|---|---|---|---|---|
| Vega | − | + | + | 符号反向 |
| Gamma | − | + | + | 符号反向 |
| Delta | 微 − | + | + | 净 long delta（仍偏多）|
| Theta | + | − | − | 净 sign 取决于 BP 比例 |

**结论**：同时触发时 **Greek 符号不同向**，所以两个 addon 不是机械重复。但：

> **Greek sign opposition supports non-redundancy, but does not guarantee PnL hedge effectiveness.**
> （per Q066 2nd Quant Review 2026-05-12 Q7.4）

具体局限：
- vega exposure 的 strike location 不同：Aftermath IC short vega 集中在 short wings 附近；Q042 call spread long vega 集中在 ATM 至上 wing
- gamma profile 形态不同：IC short gamma 在 adverse move 下非线性扩大，与 call spread long gamma 形态不对称
- notional / BP / premium size 不同——符号反向无法直接等价为"对冲"
- Q042 long vega 对 SPX 下跌时的保护有限（call spread delta 受损会主导）

**正确措辞**：`Greek directions are opposite and therefore the two sleeves are not mechanically redundant. However, Greek sign offset is not a reliable hedge claim because magnitude and strike localization differ.`

## 4. 为什么"看起来都是抄底"是错觉

| 表层相似点 | 实际差异 |
|---|---|
| 都在"市场下跌后入场" | Aftermath 等 **vol 回落**；Q042 等 **price 触底信号**——两者完全可以异步 |
| 都期望"恢复" | Aftermath 押 **IV 恢复**；Q042 押 **SPX 价格恢复**——不同变量 |
| 都有 re-arm 机制 | Aftermath 每日窗口判断；Q042 require ddATH ≥ -2%（更长记忆）|
| 都属于 addon / overlay | Aftermath 内嵌 selector regime 决策；Q042 完全独立 sleeve 走 Telegram |

## 5. 历史 disambiguation 例子

| 事件 | SPX ddATH | VIX peak | Aftermath fires? | Q042 A fires? | Q042 B fires? |
|---|---|---|---|---|---|
| 2018-02 Volmageddon | ~-10% | 50.3 | ✅ | ✅ | ❌（未 -15%）|
| 2020-03 COVID 急跌 | -34% | 82.7 | ❌（VIX ≥ 40，被 EXTREME 拒）| ✅ | ✅ (待 MA10 reclaim) |
| 2020-04 COVID 余震 | -20% → -10% | 40 → 28 | ✅ | (已 fire) | (已 fire) |
| 2024-08 carry unwind | -6% | 38.6 | ✅ | ✅ | ❌ |
| 2025-04 关税 | -18% | 52.3 | ✅（窗口分段，见 Q064/Q065）| ✅ | ✅ |
| 2023-10 SPX 平静 -7% | -7% | 21（峰未达 28） | ❌ | ✅ | ❌ |

不同事件下两者触发组合多样——证明信号不冗余。

## 6. Co-fire Downside Scenario（per Q066 2nd Quant Review Q7.3）

虽然两个 addon Greek 符号反向、触发空间 14-26% 重叠，仍存在**同向亏损路径**，作为 portfolio failure mode 正式记录：

```text
T0:  VIX peak → off-peak (≥10%) → Aftermath broken-wing IC enters
T1:  SPX ddATH ≤ -4% (or -15% + MA10 reclaim) → Q042 enters
T2:  Second-leg selloff develops:
       VIX re-expands
       SPX breaks lower
       → Aftermath IC put-side stress → loss
       → Q042 call spread decays / expires worthless → loss
       → BOTH sleeves lose simultaneously
```

机制（Greek 反向不能消除该路径风险）：
- **Q042 long vega 可帮一部分 IV expansion，但若 SPX 跌幅大，call spread delta/intrinsic 损失会主导**
- **Aftermath IC short vega + short gamma 在 adverse move 下非线性扩大**，与 Q042 long gamma 形态不对称无法抵消
- 两个 addon 的 BP / notional / strike location 不同——符号反向无法保证 magnitude 上等价对冲

**历史 candidate windows**：2008-09 雷曼时期、2020-02 → 2020-03 COVID 加速段、2022-04 → 2022-05 双重下跌段。N 小（生产中 Q042 paper trading 才刚启动）但 conceptually real。

**Monitoring 触发条件**：若 live 中观察到任一 co-fire 事件出现同向亏损 → 立即启动 Q067 PnL correlation 研究。无需提前 block 任一 addon。

---

## 7. PM / Planner 决策上下文

**何时该考虑合并 / 竞争**：
- 如果未来真实数据显示**两个 addon 在所有 fire 日 100% 同步触发** —— 即从未异步过 —— 那才提示信号冗余。但前文示例已经显示同步率不高
- 如果两个 addon 在同一历史窗口都 LOSS（例如 2018-02 都失败），且 loss correlation > 0.8 —— 则提示**风险叠加**。这是 Q066 co-firing 研究要量化的核心问题
- 如果 Q042 ROE 长期为负但 Aftermath ROE 为正（反之亦然），可考虑 retiring 弱者

**何时不该合并**：
- 当前状态：Greeks 正交、信号源不同、规模与执行路径独立——保持双 addon 是结构上正确的设计

---

## Related

- [task/SPEC-064.md](../task/SPEC-064.md) Aftermath broken-wing IC
- [task/SPEC-094.md](../task/SPEC-094.md) Q042 production deployment
- [task/SPEC-098.md](../task/SPEC-098.md) Q042 frontend dashboard
- [research/q066/](../research/q066/) Co-firing frequency 实证研究（正在进行）
- [strategy/selector.py](../strategy/selector.py) `is_aftermath()` line 295
- [signals/q042_trigger.py](../signals/q042_trigger.py)
- [strategy/q042_gate.py](../strategy/q042_gate.py) BP combined cap

## 修订记录

- 2026-05-12 created — Quant 起草，PM 触发（"功能重复性评估"问题）
- 2026-05-12 revised — 按 Q066 2nd Quant Review 修订：
  - TL;DR 从 "完全正交" 改 "non-redundant"
  - §3 加 PnL hedge 局限性说明，移除 "partial hedge" 表述
  - 新增 §6 Co-fire Downside Scenario（同向亏损路径正式记录）
  - 章节重编号 §6 → §7（决策上下文）
