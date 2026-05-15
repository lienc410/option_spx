# Q071 — /ES Sell Put Integration Design Review
## ES V2f + Q041 T1 IVP/Regime Signal Framework

**Date**: 2026-05-14  
**Prepared by**: Planner  
**Audience**: 2nd Quant Reviewer  
**Stage**: Pre-research design review — validate integration concept before full backtest  
**Reviewer response**: `task/q071_es_q041t1_integration_design_review_2026-05-14_Review.md`

---

## 0. TL;DR

PM 希望将 /ES V2f 滚动 ladder（当前研究最优结构）与 Q041 T1 的 IVP/regime 入场过滤框架整合，形成统一的"ES Sell Put"策略。核心假设：

> V2f 解决了 Q041 T1 的尾部风险问题（STOP_MULT=15），而 Q041 T1 的 IVP 窗口信号（IVP 43–55）可能提升 V2f 的入场质量。

本文档请 2nd Quant 评估：这个整合假设是否成立，以及应该如何设计研究验证它。

---

## 1. 两个策略的当前状态

### 1.1 /ES V2f（研究最优，backtest-only）

| 参数 | 值 |
|---|---|
| 入场 DTE | 49 trading days |
| 退出 DTE | 21 trading days |
| 入场频率 | 每 5 TD 一张（M1 模式：N≥4 并发时改为 10 TD）|
| 最大并发 | 5 |
| 止损 | premium × 15（STOP_MULT=15）|
| 入场过滤 | `trend_ok`（简单 BULLISH trend filter）+ `warmed` |
| **无 IVP gate** | V2f 不检查 IVP；只要 trend 和 warmup 满足就入场 |

**性能（BS-flat 26yr）**：Ann ROE +2.46% geometric，Sharpe 0.22，historical worst -9.24% NLV（V1 PASS）

### 1.2 Q041 T1 SPX CSP（2026-05-10 正式淘汰）

| 参数 | 值 |
|---|---|
| 工具 | SPX European cash-settled put，Δ0.20，DTE 30 |
| 入场过滤 | IVP_252 ∈ [43, 55]（"sweet spot" window）|
| Regime 要求 | HIGH_VOL（VIX ≥ 22）|
| 止损 | **无**（hold to expiry 或 profit target）|
| **V1 FAIL 原因** | 无止损机制 + 2020 COVID worst -17.99% NLV > -15% 门槛 |

**淘汰原因**：尾部风险，不是信号质量。IVP 43–55 窗口本身从未被单独证伪。

---

## 2. 整合假设

### 2.1 为什么这个组合可能有效

**V2f 提供什么**：
- STOP_MULT=15 修复了 Q041 T1 的 V1 veto 失败根因（止损机制）
- True rolling ladder 分散入场时点，降低单次 timing 风险
- 历史验证：26yr BS-flat，bootstrap 100% seeds 显著

**Q041 T1 的 IVP gate 可能提供什么**：
- IVP_252 ∈ [43, 55] 是"IV 不高不低的 sweet spot"——避免在 premium 已经过低（IVP < 43）或恐慌峰值（IVP > 55）时入场
- 当前 V2f 的 `trend_ok` 过滤仅检查价格趋势，不检查 IV 定价环境
- Q063 已确认 IVP gate 在主策略（BPS NNB）上有正向 alpha（2024-2026 blocked entries counterfactual -$13.7k），但 Q063 是在 DTE 30 / Δ0.20 的 SPX CSP 上测的
- 在 /ES V2f（DTE 49，rolling，STOP 保护）上 IVP gate 的效果未知

### 2.2 核心风险

- **频率损失**：V2f 每 5 TD 入场，加 IVP gate 后部分日期被 block，ladder 可能变稀
- **IVP gate 与 /ES 期权溢价的关系未验证**：Q063 的 IVP gate 研究基于 SPX 主策略（BPS NNB），/ES 期货期权的定价结构（SPAN margined，不同 term structure）可能使 IVP 信号的效力不同
- **双过滤叠加 overfitting**：`trend_ok` + IVP gate 是两个独立过滤器，在 26yr 数据上联合优化存在过拟合风险

---

## 3. 提议的整合机制

### 3.1 整合点（最小干预）

在 `run_phase2_v2f()` 的 `should_enter` 判断中，在现有 `trend_ok` 之后追加 IVP gate：

```python
# 当前 V2f should_enter（简化）
should_enter = (
    warmed
    and trend_ok                          # price trend filter
    and day_counter % entry_freq == 0
    and n_active < V2F_MAX_SLOTS
)

# 整合后（proposed）
ivp_ok = IVP_LOWER <= ivp_252 <= IVP_UPPER   # Q041 T1 gate 移植
should_enter = (
    warmed
    and trend_ok
    and ivp_ok                            # ← 新增 IVP gate
    and day_counter % entry_freq == 0
    and n_active < V2F_MAX_SLOTS
)
```

其中 `IVP_LOWER = 43`，`IVP_UPPER = 55`（直接复用 `BPS_NNB_IVP_LOWER / UPPER`）。

### 3.2 待研究的变体

| 变体 | 描述 | 研究意义 |
|---|---|---|
| V2f_base | 无 IVP gate（当前 baseline）| 对照组 |
| V2f_ivp_narrow | IVP ∈ [43, 55]（完整 Q041 T1 gate）| 完整移植 |
| V2f_ivp_upper_only | IVP ≤ 55（仅屏蔽极端高 IV）| 宽松版本 |
| V2f_ivp_lower_only | IVP ≥ 43（仅屏蔽极端低 IV）| 分解测试 |
| V2f_regime_only | HIGH_VOL only（VIX ≥ 22 才入场）| Regime filter 单独效果 |

---

## 4. 已有证据汇总

| 证据来源 | 内容 | 对整合的含义 |
|---|---|---|
| Q063 | IVP gate 在 SPX BPS NNB 上确认正向 alpha（-$13.7k counterfactual 2024-2026）| IVP gate 有信号价值，但是在 DTE 30 / Δ0.20 SPX 上验证的 |
| SPEC-095 / R-20260510-xx | V2f（无 IVP）26yr Ann ROE +2.46%，bootstrap 100%，V1 PASS | baseline 已经稳健 |
| Q041 T1 elimination | V1 FAIL 原因是无止损，不是 IVP signal | IVP gate 本身价值未被证伪 |
| doc/strategy_status_2026-05-10.md §1 | naked put slot 永久归 /ES，SPX CSP T1 路径关闭 | 整合方向确认为 /ES-only |
| Q067 | IVP_252 有 7.37% daily flip rate（jitter）| gate 在 rolling ladder 下可能产生频繁 on/off 切换 |

---

## 5. 研究范围（待 2nd Quant 确认后启动）

### P1 — IVP gate 频率影响分析

在 26yr /ES V2f 回测数据上，统计 IVP_252 ∈ [43,55] 的日期覆盖率：
- 有多少比例的 V2f should_enter 日期会被 IVP gate blocked？
- blocked 日期的 VIX / realized forward return 分布如何？
- ladder 在加 gate 后稳态并发数（avg slots filled）如何变化？

### P2 — 结构 counterfactual

对 V2f_base vs V2f_ivp_narrow，26yr backtest 对比：
- Ann ROE、Sharpe、worst trade、max drawdown
- V1 veto 状态是否保持
- bootstrap 显著性（block=250，20 seeds）

### P3 — IVP 子窗口分解

分别测试 V2f_ivp_upper_only / V2f_ivp_lower_only / V2f_regime_only，理解哪半个 gate 贡献了 alpha，哪半个只是降频。

---

## 6. Review Questions（2nd Quant 请明确回答）

**Q1 — IVP gate 的信号迁移有效性**  
Q063 的 IVP gate alpha 是在 SPX BPS NNB（DTE 30，主策略）上验证的，迁移到 /ES V2f（DTE 49，rolling ladder，STOP=15）时，你认为信号是否仍然有效？有哪些使这个迁移可疑的结构性差异？

**Q2 — Jitter 在 rolling ladder 下的影响**  
Q067 发现 IVP_252 有 7.37%/11.5% daily flip rate。在 V2f 每 5 TD 入场的节奏下，IVP gate 的 jitter 是否会造成系统性 on/off 切换而非真正的质量过滤？

**Q3 — 频率损失的可接受性**  
如果加 IVP gate 后 V2f 入场频率降低 20-40%，ladder 稳态并发从 5 降至 3-4，Ann ROE delta 是正还是负？你认为"更少但更优质的入场"在 rolling ladder 结构下是否成立？

**Q4 — 替代整合路径**  
除了 IVP gate，Q041 T1 还有 HIGH_VOL regime filter（VIX ≥ 22）。你认为 regime filter 单独（不含 IVP gate）用于 V2f 是否更简洁、更稳健？

**Q5 — 研究设计建议**  
P1-P3 的研究顺序和范围是否合理？有没有你会优先做或跳过的部分？什么结果可以让你支持整合，什么结果会让你建议停止？

---

## 7. 不在范围内

- SPX CSP 路径重启（Q041 T1 已正式淘汰，不重议）
- 修改生产代码（所有研究在 `backtest.py` 研究层）
- V2f 参数本身的修改（DTE / STOP_MULT / entry_freq 保持 SPEC-095 值）
- /ES live bot 任何改动

---

## 8. 参考文件

```
strategy/selector.py:180-206      ← BPS_NNB_IVP_LOWER/UPPER 定义（43/55）
research/strategies/ES_puts/backtest.py  ← run_phase2_v2f() 实现
task/SPEC-095.md                   ← V2f 基础参数
task/q063_phase4_closure_memo_2026-05-11.md  ← IVP gate alpha 证据
task/q041_t1_es_governance_review_archive_2026-05-09.md §1  ← T1 淘汰记录
doc/strategy_status_2026-05-10.md  ← naked put slot 归属决定
```
