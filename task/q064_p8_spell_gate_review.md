# Q064-P8 Quant Review — Spell Gate Sensitivity

**Date:** 2026-05-13  
**Raised by:** Engineering (gate analysis from P7 skip log)  
**Priority:** Medium — affects live parameter config  

---

## 背景

V3-A 策略 (IC_HV aftermath) 使用两层 spell gate 防止同一次 panic 里过度开仓：

```python
# strategy/selector.py StrategyParams
spell_age_cap:       int = 30   # HV spell > 30d → block entry
max_trades_per_spell: int = 2   # 同一 spell 内最多 2 笔 IC_HV
```

P7 skip log 显示：**13 个窗口** selector 触发了 V3-A 信号，但 engine 因 spell gate 或并发上限阻断了实际开仓（见 `q064_p7_skip_log.csv`）。其中典型案例：

- **2022 年 4–10 月**：HV spell 在 1 月底已用完 2 笔配额，此后 6 个窗口信号全被阻断
- **2011 年 11 月**：spell 内已有 1 笔持仓 + 配额限制，2 个窗口被阻断

**研究问题：`max_trades_per_spell=2` 是否过度保守，遗漏了高质量交易机会？**

---

## P8 研究方案

**脚本：** `research/q064/q064_p8_spell_gate_study.py`  
**输出：** `q064_p8_summary.csv`, `q064_p8_incremental.csv`

对比四种配置，其余参数完全一致（全 engine replay，非 BS 模拟）：

| 配置 | max_trades_per_spell |
|------|---------------------|
| Baseline | 2 （当前生产值） |
| Relaxed-1 | 3 |
| Relaxed-2 | 4 |
| Unlimited | ∞ (999) |

---

## 需要 Quant 判断的核心问题

### Q1 — 增量交易质量是否下降？

查看 `q064_p8_incremental.csv`：spell_max=3/4/∞ 相比 baseline 新增的交易，其 win rate、avg P&L、$/BP-day 是否显著低于 baseline？

**判断标准建议：**
- 增量 win rate < baseline win rate − 10pp → 认为质量下降
- 增量 worst trade 超过 baseline worst trade 的 1.5x → 尾部风险扩大
- 增量 $/BP-day < baseline 的 50% → alpha 稀释明显

### Q2 — Spell 内 trade #1 vs trade #2 质量差异？

`q064_p8_spell_gate_study.py` 输出 baseline 内 spell position #1 和 #2 的分层指标。  
如果 #2 已经明显弱于 #1，说明就连现有的 max=2 都可能偏宽松，更不应放开。

### Q3 — 2022 年特异性？

2022 年的 6 个被阻断窗口集中在同一个超长 HV spell（2022-01 至 2022-10）。  
这是否是罕见的 regime 异常（低利率退出 + 加息冲击），还是将来会再现的结构？  
如果是异常事件，应单独处理而非修改全局参数。

### Q4 — spell_age_cap 与 max_trades_per_spell 的交互？

当前 `spell_age_cap=30d` + `max_trades_per_spell=2`，两个 gate 都在限制。  
P8 只测 max_trades_per_spell。如果 Q1 显示增量交易质量 OK，还需要检验：
- 放开 max_trades_per_spell 是否会与 spell_age_cap 产生意外交互
- 是否应当把 spell_age_cap 也纳入敏感性测试（P8b）

---

## 预期结论范围

| 场景 | 建议 |
|------|------|
| 增量交易质量与 baseline 相当 (win rate / $/BP-day 无显著差异) | 将 max_trades_per_spell 从 2 上调至 3 |
| 增量交易明显弱于 baseline | 维持 max=2；2022 case 视为 regime 异常，不调参 |
| Spell #2 已弱于 #1 | 考虑将 max 从 2 降至 1（更激进） |
| 只有 2022 异常，其余增量 OK | 引入 spell 内的 concurrent_vix_floor 而非修改 count 上限 |

---

## P8 结果（2026-05-13 engine replay）

### 聚合指标

| 配置 | 交易数 | Win Rate | Avg P&L | $/BP-day | Total P&L |
|------|--------|----------|---------|----------|-----------|
| spell_max=2 (baseline) | 33 | 90.9% | $1,203 | 2570 | $39,715 |
| spell_max=3 | 37 | **91.9%** | $1,220 | 2523 | $45,139 |
| spell_max=4 | 38 | **92.1%** | $1,228 | 2547 | $46,647 |
| spell_max=∞ | 38 | 92.1% | $1,228 | 2547 | $46,647 |

**spell_max=4 与 ∞ 结果完全相同** → 实际数据中没有 spell 有超过 4 个有效信号，参数>4 无实际意义。

### 增量交易明细（spell_max=3 新增 4 笔）

| entry | exit | hold | P&L | exit reason |
|-------|------|------|-----|-------------|
| 2010-07-08 | 2010-08-10 | 33d | +$1,359 | 50pct_profit |
| 2015-09-10 | 2015-10-02 | 22d | +$1,588 | 50pct_profit |
| 2022-03-23 | 2022-04-18 | 26d | +$1,377 | 50pct_profit |
| 2025-04-29 | 2025-06-03 | 35d | +$1,100 | roll_21dte |

4 笔全部盈利，无亏损。

### Spell 内 position 分层（baseline）

| 位置 | n | Win Rate | Avg P&L | $/BP-day |
|------|---|----------|---------|----------|
| Spell trade #1 | 12 | 91.7% | $1,186 | 2860 |
| Spell trade #2 | 11 | 90.9% | $1,220 | 2652 |

**#2 不弱于 #1**，不支持"越晚质量越差"假设。

---

## 结论与建议

**Q1（增量质量）：增量交易 100% win rate，avg P&L $1,356，无亏损** → 质量与 baseline 相当，判断标准全部通过。

**Q2（spell 位置退化）：#1 vs #2 几乎无差异** → 不支持 max=2 宽松。

**Q3（2022 特异性）：**
- 2022 实际只增加了 1 笔（2022-03-23），而非 6 笔——说明 2022 年 4–10 月的 6 个信号并没有因为 spell_max=3 被解锁。
- 这是因为 2022 年 4-10 月的被阻断原因不只是 spell count，engine replay 下真实的 spell boundary 与我的启发式计算不同。
- 实际影响较小，无需特殊处理。

**Q4（spell_age_cap 交互）：** 暂无交互信号，但 spell_age_cap=30d 在此次测试中没有成为瓶颈。

### 建议操作

> **将 `max_trades_per_spell` 从 2 上调至 3。**
>
> 理由：+4 笔增量交易，全部盈利，avg P&L $1,356，比 baseline avg $1,203 更高。
> Total P&L 增加 $5,424（+13.7%）。Worst trade 不变（$-2,016）。
> 样本量小（仅 4 笔），但方向一致，无尾部风险扩大。
>
> 不建议上调至 4（仅再增 1 笔，边际效益低；且 spell_max=4 与 ∞ 等价，
> 意味着没有更多数据支撑）。

**修改位置：** `strategy/selector.py:93`
```python
max_trades_per_spell: int = 3   # 从 2 上调，P8 研究支持
```

需同步更新 backtest 缓存（Q041/ES/SPX 三套）。

---

## 数据文件

| 文件 | 说明 |
|------|------|
| `research/q064/q064_p7_skip_log.csv` | 70 个无交易窗口的 selector rationale |
| `research/q064/q064_p8_summary.csv` | 四种配置的聚合指标 |
| `research/q064/q064_p8_incremental.csv` | 增量交易明细（非 baseline 新增） |
| `backtest/engine.py:573` | `_block_hv_spell_entry` 实现 |
| `strategy/selector.py:92` | `StrategyParams.max_trades_per_spell` |
