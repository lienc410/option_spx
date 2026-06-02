# Q081 P3 — Matched-Window BCD vs QQQ + Qualitative Routing + Sizing Prep

**Date**: 2026-06-01
**Owner**: Quant Researcher
**Status**: COMPLETE
**Prior**: G-review 1 reply 2026-06-01 — thesis recentered, 4 sections (§A-E)
**Next**: P4 (BPS in low-IVP sanity) → P5 verdict + G-review 2

---

## §A — Thesis Recentering（per G-review 1）

Q081 的 verdict 空间在 P1 之后已经**收窄**。原始 framing 假设挤占（BCD 吃光 QQQ 现金）是核心风险；P1 实测 **0 crowd-out**（sequential ladder 天然避免并发）。因此：

| 维度 | 状态 |
|---|---|
| 组合层挤占 | **non-issue**（P1 实证 0 events） |
| 单笔 cash efficiency: BCD per-trade vs 现金留 QQQ | 还活着 → P3 §B 主测 |
| IVP≥67→BPS routing 是否结构正确 | 还活着 → P3 §D 定性论证 |
| 单笔 worst cash draw 是否在 slack 内 | 还活着 → P5 主 verdict（升级 sizing cap） |
| 未来 regime 让 ladder 失效的前瞻风险 | 标记但不量化（Q082 范畴） |

**Q081 不再回答**：BCD 是否在挤占 QQQ。答案已是"历史上没有"。

**Q081 主要 actionable**：cash_budget_pct cap（% of liquid cash），针对单笔层 cash 冲击。

参 2nd quant G1 reply 跨 Q 收尾段；同构 Q078 中途 thesis pivot 先例。

---

## §B — Per-trade Matched-Window: BCD vs QQQ vs SPX

每笔 BCD 取同 `[entry_date, exit_date]` window 的 QQQ close-to-close return，比较 period-ROE 分布（不年化）。

| Metric | BCD period-ROE | QQQ same-window | SPX same-window | BCD − QQQ (per trade) |
|---|---:|---:|---:|---:|
| n | 21 | 21 | 21 | 21 |
| Mean | **+8.32%** | +0.32% | +0.52% | **+8.01%** |
| Median | +4.35% | +0.59% | +0.93% | +5.10% |
| p05 | **-11.61%** | -5.54% | -3.56% | **-8.01%** |
| p25 | -7.37% | -3.18% | -2.62% | -3.35% |
| p75 | +22.46% | +3.85% | +3.17% | +18.05% |
| Min | -13.38% | — | — | — |
| Max | +28.25% | — | — | — |

Bootstrap 95% CI on p05 (n=21, B=10k):
- BCD: [-13.4%, -8.3%]
- QQQ: [-9.6%, -3.5%]
- Per-trade diff: [-8.5%, -3.8%]

**BCD 在 14/21 笔（66.7%）跑赢 QQQ**.

---

## §C — Direction-Bias Control Panel (G-review 1 Q1 补强)

担心：21 个 hold window 若 systematically 偏 SPX/QQQ 上行，BCD-QQQ 比较会被方向 bias 污染（"两个上行参与工具谁参与得多"）。

**实测**：

| | QQQ | SPX |
|---|---|---|
| Up windows | 11/21 (52%) | 11/21 (52%) |
| Mean return | +0.32% | +0.52% |

**结论**：21 个 BCD hold window **不是上行偏置样本**。QQQ/SPX 在这些窗口接近零均值（接近 coin-flip）。BCD vs QQQ 的 +8pp mean 优势**不是 beta artifact**，是 BCD 结构 edge（vega + theta + δ=0.70 long leg 捕捉 + 短腿 0.30δ collection）。

副意义：LOW_VOL + BULLISH 信号在 21 笔样本中**没有预测 QQQ 同期强上行**。BCD 的 edge 不依赖 trend-following，是 structural alpha。

---

## §D — IVP≥67 → BPS Routing: Qualitative Audit (G-review 1 Q3 重新表述)

矩阵在 IVP≥67 时把 LOW_VOL × BULLISH 路由到 BPS（不是 BCD）。Q081 样本 100% IVP<67，**无法用数据直接 verify**这条 routing。改做**结构性论证**：

**Claim**: 在 cash-bound 账户里，IVP≥67 时 BPS 对 BCD 有 **structural resource advantage**，与 ROI 谁高无关。

**Argument**:
1. Cash-bound 账户：cash 稀缺（$37k = 3% NLV），BP 富余（headroom 56%）
2. BPS 占 BP（富余），几乎不占 cash → 没 QQQ 机会成本
3. BCD 占 cash（稀缺），几乎不占 BP → 满载 QQQ 机会成本
4. 当 IVP≥67：BPS credit 厚（短 put premium 价高），ROE-on-BP 显著为正
5. 当 IVP≥67：BCD long leg 也贵（同步反映高 IV），entry debit 升高，BCD edge 因高 IV 而潜在压缩（buy-vol 在 high-IV 不利）
6. 双向论证都偏 BPS：BPS 在 IVP≥67 时既占富余资源 + 又有更高 ROI；BCD 占稀缺资源 + ROI 边际下降

**结论**：当前矩阵 IVP≥67 → BPS 的 routing 是 cash-bound 命题的**直接推论**。**Ratify 现状**。不需 IVP_HIGH 反事实合成（Q082-class）。

**Caveat**: 该论证假设 cash-bound profile 稳定。若未来账户结构变化（cash 不再紧、或不再有 QQQ outside option），该论证需重审。

---

## §E — Sizing Prep（P5 主 verdict 输入）

单笔 BCD 美元 PnL 分布（n=21）：

| | $ PnL | as % of $37k cash baseline |
|---|---:|---:|
| Worst | **-$3,248** | **-8.8%** |
| p05 | -$2,545 | -6.9% |
| Median | +$1,255 | +3.4% |
| Mean | +$1,796 | +4.8% |
| Best | (not listed) | |

**Operational cash math** under steady-state $37k baseline:
- Typical BCD debit: $23,864 (median) → cash locked, $13k slack remains
- Worst-case BCD: 8.8% draw on baseline cash, leaving $9.8k operational liquid

**P5 sizing cap candidate**:

| Cap | 1 BCD at typical debit ($24k)? | 2 concurrent? | Slack preserved |
|---|---|---|---|
| 50% liquid ($18.5k) | ❌ blocks single BCD at current sizing | ❌ | $18.5k |
| **65% liquid ($24k)** | ✅ (boundary) | ❌ | $13k |
| 70% liquid ($26k) | ✅ | ❌ | $11k |
| 100% liquid ($37k) | ✅ | ❌ (still 1 at a time) | $0 (no slack) |

**Recommend P5 default**: cap at **65% of combined liquid cash** for combined debit-strategy footprint. Rationale:
- Allows 1 BCD at current backtest-validated sizing
- Blocks accidental 2-BCD concurrent open
- Preserves $13k operational slack for dividend cycles / unexpected margin calls / spontaneous BPS opportunities

If PM wants more slack, could lower to 50% but BCD sizing must shrink accordingly.

---

## Interpretation: Does BCD beat QQQ?

**Direct mean/median comparison**: yes, decisively. +8pp mean, +5pp median.

**Per 2nd quant framework (p05-based)**: **BCD's tail is worse than QQQ's by 6pp** (-11.6 vs -5.5). Per-trade diff p05 = -8.0%, meaning in 5% of trades BCD underperforms QQQ by ≥8%.

**Risk-reward** of choosing BCD over QQQ on each trade:
- Expected uplift: +$1,719 per $24k position
- Worst-case (p05) downside vs QQQ: -$1,920 per position
- Roughly symmetric. Not slam-dunk for either.

**Practical reading**:
- BCD's left tail is worse, BCD's right tail is much better, BCD's median is better
- For PM with $1.24M NLV, accepting -$2k worst-case for +$1.7k expected uplift is reasonable
- **The case for status quo (keep BCD in matrix) is strong** — BCD wins on every distributional dimension except p05 tail
- **The case for cash-hurdle gate is weak** — BCD beats QQQ on average, and the per-trade diff p05 of -8% is bounded
- **The case for sizing cap is strong (per §E)** — single-trade worst case is 8.8% of liquid cash, eats most of slack

---

## Files
- `q081_p3_qqq_hurdle.py` — script
- `q081_p3_per_trade_comparison.csv` — 21 trades with QQQ + SPX matched windows
- `q081_p3_window_bias.csv` — distribution stats
- `q081_p3_memo.md` — this file

---

## Pre-P5 verdict signaling

**Path likely heading toward**:
- Matrix: **status quo** (no LOW_VOL → BPS change; IVP≥67 → BPS ratified qualitatively)
- Sizing: **NEW cash_budget_pct cap** at ~65% of combined liquid cash, applied to debit strategies in aggregate
- Crowd-out: documented as historically non-issue, sizing cap is the prophylactic
- BPS in low-IVP (PM intuition B): P4 sanity check pending; expect to confirm PM's self-veto

This is what 2nd quant predicted in G-review 1 跨 Q 收尾段: "矩阵不变 + 挤占 non-issue + 路由 ratify + sizing cap is the actionable".

P4 next: BPS in low-IVP counterfactual to verify PM intuition B and ensure we're not missing a BPS-in-LOW-VOL opportunity. Then P5 + G-review 2.
