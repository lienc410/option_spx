# SPX Strategy — 策略状态快照
**日期：** 2026-03-28
**账户假设：** Portfolio Margin，$150,000，risk_pct = 2%，现金缓冲 ≥ 30%

---

## 1. 决策矩阵（当前版本）

| VIX 体制 | IV 信号 | 趋势 | 策略 | 标的 | DTE |
|----------|---------|------|------|------|-----|
| LOW_VOL (<15) | any | NEUTRAL | Iron Condor | SPX | 45 |
| LOW_VOL | any | BULLISH | Bull Call Diagonal | SPX | 30短/90长 |
| LOW_VOL | any | BEARISH | Bear Call Diagonal | SPX | 45短/90长 |
| NORMAL (15–22) | HIGH | BULLISH | Bull Put Spread | SPX | 30 |
| NORMAL | HIGH | NEUTRAL | Iron Condor | SPX | 45 |
| NORMAL | HIGH | BEARISH | Bear Put Spread | SPY | 21 |
| NORMAL | NEUTRAL | BULLISH | Bull Put Spread | SPX | 30 |
| NORMAL | NEUTRAL | NEUTRAL | Iron Condor | SPX | 45 |
| NORMAL | NEUTRAL | BEARISH | Bear Call Spread | SPY | 21 |
| NORMAL | LOW | BULLISH | Bull Call Spread | SPY | 21 |
| NORMAL | LOW | NEUTRAL | Reduce / Wait | — | — |
| NORMAL | LOW | BEARISH | Bear Put Spread | SPY | 21 |
| HIGH_VOL (22–35) | any | any | Bull Put Spread HV | SPX | 35 |
| EXTREME_VOL (≥35) | any | any | Reduce / Wait | — | — |

**额外过滤器（→ REDUCE_WAIT）：**
- VIX 期限结构 backwardation（spot VIX > VIX3M）→ 禁止 BPS 和 IC 入场
- BEARISH 趋势 → 全部 REDUCE_WAIT（无看跌策略实盘执行）
- IVP < 20 或 IVP > 50 → 禁止 Iron Condor（过低保费 / 过高尾部风险）
- IVP ≥ 50 → 禁止 Bull Put Spread（stressed vol，尾部风险 > 权利金）
- VIX RISING → 禁止 BPS 和 IC 入场

---

## 2. 策略参数（StrategyParams 默认值）

```python
extreme_vix      = 35.0   # VIX ≥ 35 → EXTREME_VOL
high_vol_delta   = 0.20   # HIGH_VOL BPS 短腿 delta（比 NORMAL 更 OTM）
high_vol_dte     = 35     # HIGH_VOL BPS DTE（roll_21dte 在 ≤21 触发，有效持仓 ~14天）
high_vol_size    = 0.50   # HIGH_VOL 半仓
normal_delta     = 0.30   # NORMAL BPS 短腿 delta
normal_dte       = 30     # NORMAL BPS DTE
profit_target    = 0.50   # 止盈：权利金的 50%
stop_mult        = 2.0    # 止损：亏损 2× 权利金
min_hold_days    = 10     # 止盈触发前最低持仓天数（防假性快速退出）
```

**IV 信号阈值：**
- IVP > 70 → HIGH；IVP < 40 → LOW；40–70 → NEUTRAL
- IVP vs IVR 偏差 > 15pt 时优先使用 IVP（防 VIX spike 扭曲 IVR）

---

## 3. 退出规则

| 退出原因 | 条件 |
|---------|------|
| `50pct_profit` | PnL ≥ 50% 权利金 **且** 持仓 ≥ 10 天 |
| `stop_loss` | 信用策略亏损 ≥ 2× 权利金；借方策略亏损 ≥ 50% |
| `roll_21dte` | 短腿 DTE ≤ 21（强制滚仓/平仓） |
| `roll_up` | BPS：SPX 涨幅 ≥ 3% 且 IVP ≥ 30 且 DTE > 14 → 平仓后原价位重开 |
| `end_of_backtest` | 回测截止日强制平仓 |

---

## 4. 回测结果（Precision B，2026-03-28 运行 — **含 Fix C `_entry_value` Bug 修复**）

> Precision B 说明：Black-Scholes 定价，无 bid-ask spread，无滑点，每日用当天 VIX 作为 sigma（非锁定IV）。回测结果偏乐观。
>
> ⚠ **重要：** 此前（Fix C 前）的所有 Diagonal 数据因 `_entry_value` Bug 完全失效，已废弃。以下为修复后的正确结果。

### 3Y（2023-01-11 → 2026-02-05）
| 指标 | 数值 |
|------|------|
| 交易笔数 | 21 |
| 胜率 | 38.1% |
| Sharpe (年化) | 0.34 |
| Total PnL | $+2,116 |
| Max Drawdown | $-1,866 |
| Expectancy | $+101 / 笔 |

按策略明细：

| 策略 | 笔数 | 胜率 | 总PnL | 平均BP% |
|------|------|------|-------|---------|
| Bull Call Diagonal | 14 | 36% | $+1,237 | 2.0% |
| Iron Condor | 2 | 50% | $+1,458 | 5.1% |
| Bear Call Diagonal | 1 | 0% | $-1,559 | 2.0% |
| Bull Put Spread (High Vol) | 1 | 100% | $+1,244 | 5.0% |
| Bull Put Spread | 3 | 33% | $-264 | 6.4% |

### 1Y（2025-01-24 → 2026-02-05）
| 指标 | 数值 |
|------|------|
| 交易笔数 | 8 |
| 胜率 | 50.0% |
| Sharpe (年化) | 0.57 |
| Total PnL | $+1,350 |
| Max Drawdown | $-1,590 |
| Expectancy | $+169 / 笔 |

### ALL（2000-01-07 → 2026-02-05，175 笔）
| 指标 | 数值 |
|------|------|
| 交易笔数 | 175 |
| 胜率 | 62.3% |
| Sharpe (年化) | 1.02 |
| Total PnL | $+58,423 |
| Max Drawdown | $-8,047 |
| Expectancy | $+334 / 笔 |

按策略明细（ALL）：

| 策略 | 笔数 | 胜率 | 总PnL | 平均天数 | 平均BP% |
|------|------|------|-------|---------|---------|
| Bull Call Diagonal | 85 | 45% | $+11,641 | 52d | 2.0% |
| Bull Put Spread (High Vol) | 60 | 85% | $+27,905 | 16d | 4.9% |
| Iron Condor | 12 | 92% | $+16,749 | 29d | 6.3% |
| Bull Put Spread | 7 | 71% | $+6,603 | 13d | 6.4% |
| Bear Call Diagonal | 11 | 36% | $-4,475 | 72d | 2.0% |

退出原因分布（ALL）：trend_flip 34%，50pct_profit 30%，roll_21dte 26%，roll_up 6%，stop_loss 5%

---

## 5. Buying Power 分析（Schwab PM 规则）

本次新增 BP 字段至回测数据集，规则如下：

| 策略类型 | Schwab PM 计算公式 |
|---------|------------------|
| 信用价差（BPS / BCS） | BP = (spread_width − credit) × $100 |
| Iron Condor | BP = (max(call_width, put_width) − net_credit) × $100 |
| 借方对角线（Bull/Bear Diagonal） | BP = net_debit × $100（已付借方 = 最大损失） |
| 借方价差（BCS debit / BPS debit） | BP = net_debit × $100 |

**关键观察：**
- Bull Call Diagonal 的 BP% **恒等于 risk_pct (2.00%)**——因为 BP = 净借方 = 风险预算，完全符合 PM 逻辑
- Bull Put Spread 的 BP% 约 **6–7%**：spread_width（~150–200pt）远大于 credit（~35–45pt），BP 放大约 3× premium
- BPS_HV 因 half-size，BP% 约 **5%**
- Iron Condor 约 **5–7%**（wing ~75pt，credit ~15pt）
- 当前账户 **平均 BP 占用仅 2.6–3.0%**，极度保守，有大量 margin headroom

**Trade 数据集新增字段：**
```
spread_width      — 价差宽度（SPX 指数点）
option_premium    — 每张合约权利金（USD，绝对值）
bp_per_contract   — Schwab PM 每张合约需用 BP（USD）
contracts         — 模拟合约张数（可含小数）
total_bp          — 本笔交易总 BP 占用（USD）
bp_pct_account    — total_bp / account_size × 100
```

---

## 6. 近期主要改动（2026-03-28）

### Fix A：high_vol_dte 21 → 35
- **根因：** DTE=21 入场 + roll_21dte 在 DTE≤21 触发 → 约 1 个交易日有效持仓
- **效果（ALL，含 Bug Fix C 后数据）：** BPS_HV 60 笔，WR 85%，avg $465

### Fix B：Iron Condor IVP bounds 10–60 → 20–50
- **根因：** 4 笔最大亏损 IC 在 IVP 55–58（旧上限附近），IVP<20 时保费不足
- **效果：** 历史数据无变化（实际入场未触碰旧边界），为预防性过滤

### Fix C：`_entry_value` 定价 Bug 修复（**关键**，2026-03-28）
- **根因：** `_entry_value()` 对所有腿统一使用 `short_dte` 定价，忽略每条腿自己的 DTE。对 Bull/Bear Call Diagonal（long_dte=90, short_dte=30），long call 被以 DTE=30 定价（应为 90），导致 entry_value 严重低估（~65 vs 正确 ~270）。
- **症状：** `_current_value()` 从 Day 1 起正确用 DTE=89 定价 long call，造成虚假 Day-1 PnL 约 +56%，触发 50% 止盈（有 `min_hold_days=10` 保护才未立即退出）。所有 Diagonal 合约数量被高估 4×，PnL 绝对值也被等比膨胀。
- **影响：** 旧回测的所有 Diagonal 数据完全无效。修复后数字大幅缩水（见§4 对比）。
- **修复位置：** `backtest/engine.py` `_entry_value()` 函数，使用每条腿自己的 DTE，并移除 `dte_start` 参数。

### Fix D：Bull Call Diagonal BEARISH 趋势翻转退出（2026-03-28）
- **条件：** `days_held ≥ 3 AND trend == BEARISH → exit_reason = "trend_flip"`
- **效果：** 见§4，已包含在当前回测结果中

### Fix E：BPS 入场 IVP 过滤 43（2026-03-28）
- **NORMAL + IV_NEUTRAL + BULLISH 路径：** `IVP < 43 → REDUCE_WAIT`
- **效果：** 过滤保费不足的 BPS 入场

### Fix F：selector.py 文本修复（SPEC-1A/SPEC-3，2026-03-28）
- 将 "within 7 trading days" 替换为 "after min 10 days held"，文档与代码一致

---

## 7. 已知局限 / 技术债务

| 问题 | 影响 | 优先级 |
|------|------|--------|
| Bear Call Diagonal 全局亏损（$-4,475 / 11笔） | 36% WR，该策略在修复后的回测中表现差。需研究是否应禁用或调整 | **高** |
| Bull Call Diagonal Sharpe 仅 ~1.0（ALL） | 修复 Bug 后策略整体表现大幅下修，需重新评估策略组合权重 | **高** |
| 回测 sigma 用当天 VIX（非锁定IV） | SPX 上涨 → VIX 下降 → vega 自动获利，结果偏乐观 | 中 |
| 无 bid-ask spread / 滑点 | 实际每笔额外成本约 $50–150 | 中 |
| 路径依赖 2023–2026 强牛市 | BPS 顺风；2022 熊市未压力测试 | 中 |
| Roll Up 逻辑触发稀少（10/175笔） | 逻辑存在但效果有限 | 低 |

---

## 8. 系统部署状态

| 组件 | 状态 |
|------|------|
| Telegram Bot (@Spx_opt_bot) | launchd，每日 9:35am ET 推送 |
| Web Dashboard | https://spx.portimperialventures.com（Cloudflare Access） |
| Flask 服务 | port 5050，launchd com.spxstrat.web |
| Cloudflare Tunnel | spx-strat，ID: 6d4708bc-69de-4f96-a3d8-1fc32e4543f2 |

---

## 9. 代码结构

```
SPX_strat/
├── signals/
│   ├── vix_regime.py     VIX 体制分类（LOW/NORMAL/HIGH/EXTREME）+ 5日趋势 + VIX3M/backwardation
│   ├── iv_rank.py        IV Rank + IV Percentile（252日窗口）
│   ├── trend.py          SPX 20/50/200MA 趋势
│   └── intraday.py       日内信号：VixSpikeAlert / IntradayStopTrigger
├── strategy/
│   ├── selector.py       决策矩阵（VIX×IVP×趋势→策略+参数）
│   └── state.py          持仓状态追踪（OPEN/CLOSE_AND_OPEN/WAIT）
├── backtest/
│   ├── pricer.py         Black-Scholes（price/delta/theta/strike搜索）
│   ├── engine.py         回测引擎（walk-forward，含 BP 字段，Precision B）
│   └── experiment.py     实验管理（run_experiment/load_experiments/diff_metrics）
├── notify/telegram_bot.py Telegram 推送（HTML格式）
├── web/
│   ├── server.py         Flask API + 实验 API + 自动搜索 API
│   └── templates/        index / backtest / matrix HTML
└── main.py               CLI 入口（--dry-run / --backtest / bot 模式）
```

---

*生成于 2026-03-28（最终更新含 `_entry_value` Bug Fix）| Precision B 回测 | 账户：$150k PM，risk_pct=2%*
