# SPEC-030: Intraday Stop Loss Analysis — OHLC 日内触及率研究

## 目标

**What**：量化现有 `stop_loss` 规则的延迟程度——在所有最终触发 `stop_loss` 的交易中，有多少笔在触发当日之前，其日内 Low 对应的 BPS short put 价值已经超过止损阈值？平均提前几天触达？

**Why**：

现有引擎用**收盘价**重估期权价值，stop loss 只在收盘后才判断。SPEC-023（发现3）已确认：最大尾部风险是 VIX 25→50 的中程急升。这类事件的典型日内形态是"盘中大幅下跌 + 尾盘反弹"——收盘价低估了当日实际发生的最坏情形，stop loss 有系统性延迟偏差。

量化这个偏差是决策前提：
- 若日内提前触及率很高（>30%）且提前量 ≥ 1 天 → 有实际改进空间，值得设计日内 stop 机制
- 若提前率低或提前量 < 0.5 天 → 现有收盘判断已足够，不需要引入 OHLC 复杂性

---

## 研究问题

**主要问题**

1. 在所有 `stop_loss` 交易中，用 `spx_low` 重估 short put 价值，有多少笔在收盘触发日**之前**已超过止损阈值？
2. 提前量分布：0天（同日日内）、1天、2天、3天+？
3. 集中在哪类市场事件（2008、2011、2015、2020、2022）？

**次要问题**

4. `50pct_profit` 的日内提前触及率：用 `spx_high` 重估，有多少笔在收盘达到前日内已触及？
5. 日内 stop 提前触发的 PnL 差异：提前 N 天出场 vs 收盘出场，节省了多少进一步亏损？

---

## 方法设计

### 数据获取

yfinance 的 `ticker.history()` 默认返回 OHLC 四列。现有 `fetch_spx_history` 只取了 `Close`，需要扩展为保留 `Open/High/Low/Close`。

```python
# 现有（只保留 Close）
return df[["Close"]].rename(columns={"Close": "close"})

# Prototype 中扩展（保留 OHLC）
return df[["Open", "High", "Low", "Close"]].rename(columns={
    "Open": "open", "High": "high", "Low": "low", "Close": "close"
})
```

**注意**：Prototype 中直接扩展本地数据获取逻辑，不修改 `signals/trend.py`。

### 日内最坏价值估算

对于 BPS（Bull Put Spread）：
- Short put：`spx_low` 时价值最高（最大亏损方向）
- Long put：`spx_low` 时也价值最高（对冲）
- 净亏损最坏点：用 `spx_low` 替代 `close` 重估 `_current_value(legs, spx_low, sigma)`

`sigma` 仍使用当日 VIX close（VIX 的日内 High 在此研究中不引入，控制变量）。

### 止损阈值定义

沿用现有规则：
```python
pnl_ratio = pnl / abs(entry_value)
intraday_stop_triggered = pnl_ratio <= -params.stop_mult  # 默认 -2.0
```

### 分析流程

```
1. 从 26yr 回测结果中取出所有 exit_reason == "stop_loss" 的交易
2. 对每笔交易，遍历其持仓期内的每一天：
   - 用 spx_low 重估期权价值
   - 记录第一个日内 intraday_stop_triggered 的日期
3. 计算：intraday_first_hit_date vs actual_stop_date 的差（天数）
4. 分布统计：提前0天/1天/2天/3天+的笔数和比例
5. 按年份（压力事件）分组查看集中度
```

---

## 接口定义

### 输入

- 26yr 回测的完整 `trades` list（exit_reason 筛选）
- `spx_ohlc`：扩展的 SPX OHLC DataFrame（含 `low` 列）
- `params`：StrategyParams（用于 stop_mult）

### 核心输出

**Report 1：日内 Stop 触及分布**

| 提前天数 | 笔数 | 比例 |
|---------|------|------|
| 同日（0天提前，日内触及但收盘未触发）| — | — |
| 提前1天 | — | — |
| 提前2天 | — | — |
| 提前3天+ | — | — |
| 从未提前（收盘先触发）| — | — |

**Report 2：提前触发的 PnL 节省**

| 提前天数 | 平均节省亏损（$）| 最大节省（$）|
|---------|--------------|------------|

**Report 3：按压力事件分布**

| 年份/事件 | stop_loss 笔数 | 日内提前触及笔数 | 提前率 |
|---------|--------------|--------------|------|

**Report 4：`50pct_profit` 日内提前触及（次要）**

---

## 边界条件与约束

- **只分析 BPS / BPS_HV**：这两个策略的日内最坏点是 `spx_low`（short put，方向明确）。IC/IC_HV 是双向仓位，日内 low 对 net PnL 的影响方向不确定，分析更复杂，本 SPEC 不覆盖。
- **sigma 固定用收盘 VIX**：不引入 VIX 日内 High，控制变量，防止混淆"日内价格移动"和"日内波动率跳升"两个效应。
- **Precision B 局限性保持不变**：此研究是在现有 BS 框架内的近似估算，不模拟真实 bid/ask。

---

## 不在范围内

- 修改 `engine.py` 加入日内出场逻辑（本 SPEC 只做诊断，不实施）
- VIX OHLC 分析（日内 VIX High 作为信号）
- IC / Diagonal 的 OHLC 分析
- 日内入场时机优化

---

## Prototype

路径：`backtest/prototype/SPEC-030_intraday_stop.py`

关键步骤：
1. 扩展 SPX 数据获取，保留 OHLC
2. 复用 engine 的 `_current_value()` 和 `_close_position()` 逻辑（只替换 spx 参数）
3. 对每笔 stop_loss 交易做日内回溯扫描

---

## 验收标准

1. **AC1**：Report 1 产出：日内提前触及分布（按提前天数分桶）
2. **AC2**：Report 2 产出：提前触发的平均 PnL 节省
3. **AC3**：Report 3 产出：按年份分布，确认是否集中在 2011/2015/2020/2022
4. **AC4**：结论明确二选一：
   - 「提前触及率 > 30% 且平均提前量 ≥ 1 天」→ 建议立项 SPEC-031 实现日内 stop 机制
   - 「提前触及率 ≤ 30% 或平均提前量 < 1 天」→ 现有收盘判断足够，关闭此研究方向

---

## Review

- 结论：PASS
- Bug 1 修复确认：`fetch_spx_ohlc()` 优先复用 `yahoo__GSPC__max__1d.pkl`，4 列 OHLC 齐全，不触发网络请求
- Bug 2 修复确认：删除线性近似，改用 `_build_legs()` 重建真实 BPS legs + `_current_value(legs, spx_low, sigma, days_held)` 精确重估
- AC4 结论：BPS/BPS_HV stop_loss 提前率=0.0%，平均提前=0.00天 → **关闭日内止损研究方向，收盘判断已足够**
- 次要发现：50pct_profit 日内提前触及率 17.4%（4/23 笔，平均提前 1.50 天），数据信息存档，不触发 SPEC-031
- 测试：29/29 全通过（含 2 个 SPEC-030 regression tests）

---

Status: DONE
