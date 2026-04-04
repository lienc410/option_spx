# SPEC-023: Concentrated Exposure + Stress Period Analysis

## 目标

**What**：量化系统在历史极端市场事件中的实际表现，评估集中风险暴露，综合三类 Warning D 风险（相关暴露、粘性高波动、乐观回测假设）的综合影响。

**Why**（Prototype 实证，`SPEC-023_stress_exposure.py`，2026-03-30，26yr 386 笔）：

---

## 核心数据（Prototype 结果）

### 主要压力事件期间 P&L

| 事件 | n | TotalPnL | WR | MaxSingleLoss |
|------|---|---------|-----|--------------|
| 2000-03 dot-com 顶部 | 19 | **$+8,402** | 89% | $−997 |
| 2001-09 9/11 | 8 | $+2,862 | 75% | $−271 |
| 2002 熊市底部 | 21 | $+2,369 | 81% | $−2,217 |
| 2008-09 雷曼崩盘 | **1** | **$−5,069** | **0%** | **$−5,069** |
| 2010-05 Flash Crash | 3 | $+1,288 | 100% | $+350 |
| 2011-08 美债降级 | 8 | $−2,511 | 75% | $−5,021 |
| 2015-08 中国崩盘 | 5 | $−3,378 | 60% | $−4,852 |
| 2018-12 Christmas Eve | 3 | $+158 | 67% | $−809 |
| 2020-02 COVID 崩盘 | 4 | **$+1,767** | **75%** | $−511 |
| 2022 Fed 加息熊市 | 29 | $−424 | 66% | $−2,461 |
| 2023-03 SVB 银行危机 | 1 | $−137 | 0% | $−137 |

### 多仓并发 short_gamma 仓位数分布（日度）

| 并发 SG 仓位数 | 天数 | 占比 |
|-------------|------|------|
| 1 个 | 3,267 | 45.5% |
| 2 个 | 931 | 13.0% |
| 3 个 | 376 | 5.2% |
| **4 个（超过 SPEC-017 上限）** | **30** | **0.4%** |

### Realism Haircut 综合调整（SPEC-016 参数）

| 指标 | Raw | Adjusted |
|-----|-----|---------|
| 26yr Total PnL | $+192,234 | **$+94,070** |
| 加权平均 haircut | — | 51.1% |
| Sharpe（估算） | 1.54 | ~0.99 |

### 最恶劣连续亏损序列（2 笔，2015 年）

| 日期 | 策略 | PnL |
|------|------|-----|
| 2015-07-16 | Bull Call Diagonal | $−1,359 |
| 2015-08-13 | Iron Condor | $−4,852 |
| 合计 | — | **$−6,210** |

背景：2015-08 中国股市崩盘 + 人民币贬值 → VIX 急升，同时 Diagonal trend_flip 出场 + IC 被 put side 击穿。

---

## 关键发现

### 发现 1：2008 年是唯一有单笔灾难性损失的事件（但整体在控制之内）

2008-09 雷曼期间仅 1 笔交易，亏损 $5,069。单笔亏损虽然是所有交易中最大的，但占 26yr 总 PnL $192k 的 2.6%，不构成毁灭性损失。原因：extreme_vix hard stop 在 VIX≥35 后阻止了大部分新入场。

**关键**：系统没有在 2008 年 VIX=80 时持有大量仓位。这验证了 SPEC-010（backwardation）和 extreme_vix 保护规则的价值。

### 发现 2：COVID 2020 是系统"设计的逆向检验"——正 PnL

2020-02 COVID 崩盘期间 4 笔交易，总 PnL=+$1,767，WR=75%。这是因为：
- VIX 从 13→80 的急升触发了 extreme_vix hard stop，阻止了高风险入场
- 已有的 4 笔交易大部分在崩盘前入场，且 roll_21dte 或 50pct_profit 已触发出场

这证明 hard stop 规则在极端事件中确实有效。

### 发现 3：2011、2015 是系统最脆弱的类型——快速 VIX 急升但未达 EXTREME_VOL

2011 美债降级（VIX 峰值 48）和 2015 中国崩盘（VIX 峰值 53）中系统受损最大：
- 这类事件 VIX 短暂突破 35，但在 extreme_vix 触发前已入场
- 既然 VIX < 35 的入场已发生，当 VIX 突破 35 时部分仓位仍然持有
- 这是 SPEC-010（backwardation）与 extreme_vix 之间的保护盲区：VIX 从 25 快速跳升到 48 时，backwardation 可能已触发，但已开的仓位无法立即退出

**结论**：最大尾部风险不是 VIX=80 的灾难（已被 hard stop 保护），而是 VIX 从 22 快速跳到 35–50 的中程急升（已有仓位 + 尚未触发 EXTREME_VOL）。

### 发现 4：有 30 天的 4 个并发 short_gamma 仓位（超过 SPEC-017 上限）

实际历史数据中出现了 30 天的 4 个并发 short_gamma 仓位（SPEC-017 的上限是 3）。这证实了 SPEC-017 设置 max=3 的必要性——在没有该限制的系统中，确实会出现 4 倍 short_gamma 集中。

### 发现 5：Realism 调整后系统仍有正期望（Sharpe ~1.0）

加权平均 haircut=51.1% 后：
- Total PnL 从 $192k 降至 $94k
- 估算 Sharpe 从 1.54 降至 ~0.99

**Sharpe ~1.0 是 "有意义的正期望"**，说明系统不是靠运气或 Precision B 乐观假设支撑，而是有真实的 alpha。这是重要的"底线确认"。

### 发现 6：Sticky HIGH_VOL spells 整体表现积极，但有结构性风险

25 个 sticky spells（≥30 天）中，所有在回测数据中有交易的 spell 都是正 PnL。这表明：
- HIGH_VOL 持续期并非"总是危险"——持续的 HIGH_VOL 提供了丰厚 premium
- 但一旦 VIX 急升（spell 内的 spike），当时持有的仓位会受损

SPEC-015（spell age throttle）解决的不是"sticky spell 有负 PnL"，而是"spell 后期的重复入场风险"——随着 spell 延续，均值回归机会在消减，但风险并没有。

---

## 综合风险画像

| 风险类型 | 严重程度 | 已有保护 | 缺口 |
|---------|---------|---------|-----|
| VIX=80 灾难级事件 | 极高（理论） | extreme_vix hard stop ✅ | 无重大缺口 |
| VIX 25→50 快速中程急升 | 高（实际已发生） | backwardation（部分）| 已有仓位的退出速度 |
| Sticky spell 重复入场 | 中 | SPEC-015（待实现）| spell age throttle 实现后改善 |
| BPS_HV + BCS_HV 合成 IC | 中 | SPEC-017（待实现）| Greek-aware dedup 实现后改善 |
| Realism haircut（50%） | 结构性 | SPEC-016（研究）| 无可消除，需持续更新估算 |
| 年度 Sharpe 波动（−0.92~+7.13）| 中 | — | 单年度波动是正常现象，不建议干预 |

---

## 不在范围内

- 实时尾部风险监控（VaR、Stress VaR）
- 极端事件期权定价模型
- 流动性风险（停盘、无法平仓）

---

## Prototype

路径：`backtest/prototype/SPEC-023_stress_exposure.py`

关键数字：
- 2008 雷曼单笔最大亏损: $−5,069
- COVID 2020 期间：正 PnL（$+1,767），验证 hard stop 有效
- 4 个并发 SG 仓位出现 30 天（支持 SPEC-017 的 max=3 设置）
- Realism 调整后 Sharpe ~0.99（仍为正期望）
- 最恶劣连续亏损: 2 笔 $−6,210（2015 年 Diagonal+IC）

---

## Review

- 结论：N/A（研究+综合性 SPEC，无 Codex 实现）

---

## 验收标准

1. PM 了解：系统在历史极端事件下有"受控"损失，不是灾难性亏损
2. PM 了解：最大实际风险是"VIX 快速跳升 25→50"，而非 VIX=80（后者已被 hard stop 阻挡）
3. PM 了解：Realism 调整（50% haircut）后系统 Sharpe 约 1.0，仍有正期望
4. PM 了解：4 个并发 SG 仓位历史上出现过（支持 SPEC-017 的必要性）
5. PM 了解：Sticky HIGH_VOL spell 中的重复入场是 SPEC-015 解决的核心风险

---
Status: DRAFT
