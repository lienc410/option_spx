# SPX Strategy — 策略状态快照
**日期：** 2026-03-29（最终更新）
**账户假设：** Portfolio Margin，$150,000，单笔 BP 目标 5%（NORMAL / LOW_VOL）/ 3.5%（HIGH_VOL）

---

## 1. 决策矩阵（当前版本）

### 核心矩阵

| VIX 体制 | IV 信号 | 趋势 | 策略 | 标的 | DTE |
|----------|---------|------|------|------|-----|
| EXTREME_VOL (VIX ≥ 35) | any | any | Reduce / Wait | — | — |
| HIGH_VOL (22–35) | any | BEARISH | Bear Call Spread HV ¹ | SPX | 45 |
| HIGH_VOL | any | NEUTRAL | Iron Condor HV ² | SPX | 45 |
| HIGH_VOL | any | BULLISH | Bull Put Spread HV ³ | SPX | 35 |
| LOW_VOL (< 15) | any | NEUTRAL | Iron Condor ⁴ | SPX | 45 |
| LOW_VOL | any | BULLISH | Bull Call Diagonal | SPX | 45短/90长 |
| LOW_VOL | any | BEARISH | Reduce / Wait | — | — |
| NORMAL (15–22) | HIGH | BULLISH | Bull Put Spread ⁵ | SPX | 30 |
| NORMAL | HIGH | NEUTRAL | Iron Condor ⁴ | SPX | 45 |
| NORMAL | HIGH | BEARISH | Iron Condor ⁶ | SPX | 45 |
| NORMAL | NEUTRAL | BULLISH | Bull Put Spread ⁷ | SPX | 30 |
| NORMAL | NEUTRAL | NEUTRAL | Iron Condor ⁴ | SPX | 45 |
| NORMAL | NEUTRAL | BEARISH | Iron Condor ⁶ | SPX | 45 |
| NORMAL | LOW | any | Reduce / Wait | — | — |

> **注**：Bear Call Diagonal（LOW_VOL + BEARISH）已从活跃矩阵中移除（研究结论：11/11 笔交易均触发翻转，无区分能力）。

### 入场过滤器（触发 → REDUCE_WAIT）

| 过滤器 | 适用策略 | 说明 |
|--------|---------|------|
| VIX RISING（5日均线上穿）| BPS、IC、BCS_HV | 权利金成本上升，short leg 暴露扩大 |
| backwardation（spot VIX > VIX3M）| BPS、BPS_HV、IC | near-term 恐慌超过长期预期，put 侧风险高 |
| IVP < 20 或 IVP > 50 | Iron Condor | 保费过薄 / 尾部风险超过 IC 双边信用 |
| IVP ≥ 50 | Bull Put Spread | stressed vol，put 尾部风险超过收益 |
| IVP < 43 | Bull Put Spread（NEUTRAL IV 路径） | 边际保费不足，过滤 2025-10-03 类亏损 |
| VIX ≥ 35（EXTREME_VOL）| 所有策略 | BS 定价失效区，全面空仓 |

### 各策略进入条件备注

¹ **Bear Call Spread HV**：VIX 非 RISING（恐慌未升级）
² **Iron Condor HV**：VIX 非 RISING + 无 backwardation
³ **Bull Put Spread HV**：无 backwardation + VIX 非 RISING
⁴ **Iron Condor（常规）**：VIX 非 RISING + IVP 20–50
⁵ **Bull Put Spread（IV HIGH）**：无 backwardation + VIX 非 RISING + IVP < 50
⁶ **Iron Condor（BEARISH 路径）**：VIX 非 RISING + IVP < 50（SPEC-007 新增）
⁷ **Bull Put Spread（IV NEUTRAL）**：无 backwardation + VIX 非 RISING + IVP 43–50

---

## 2. 策略参数（StrategyParams 默认值）

```python
# VIX 阈值
extreme_vix          = 35.0    # VIX ≥ 35 → EXTREME_VOL

# HIGH_VOL 参数
high_vol_delta       = 0.20    # short leg delta（比 NORMAL 更 OTM）
high_vol_dte         = 35      # DTE 入场；roll_21dte 在 ≤21 触发（有效持仓 ~14 天）
high_vol_size        = 0.50    # 半仓乘数（现主要用于 size_rule 文案，定仓由 bp_target 控制）

# NORMAL Bull Put Spread 参数
normal_delta         = 0.30
normal_dte           = 30

# 退出规则
profit_target        = 0.50    # 止盈：收到权利金的 50%
stop_mult            = 2.0     # 止损：亏损 2× 权利金（信用策略）
min_hold_days        = 10      # 止盈触发前最低持仓天数

# BP 目标（单笔，SPEC-013）
bp_target_low_vol    = 0.05    # LOW_VOL：5%
bp_target_normal     = 0.05    # NORMAL：5%（基准）
bp_target_high_vol   = 0.035   # HIGH_VOL：3.5%（风险上升，保留缓冲）

# BP 总 ceiling（多仓并行，SPEC-014）
bp_ceiling_low_vol   = 0.25    # LOW_VOL：25%
bp_ceiling_normal    = 0.35    # NORMAL：35%
bp_ceiling_high_vol  = 0.50    # HIGH_VOL：50%（高溢价补偿）
```

**IV 信号阈值：**
- IVP > 70 → HIGH；IVP < 40 → LOW；40–70 → NEUTRAL
- IVP vs IVR 偏差 > 15pt 时优先使用 IVP（防 VIX spike 扭曲 IVR）

---

## 3. 退出规则

| 退出原因 | 条件 | 适用 |
|---------|------|------|
| `50pct_profit` | PnL ≥ 50% 权利金 **且** 持仓 ≥ 10 天 | 所有 |
| `stop_loss` | 信用策略亏损 ≥ 2× 权利金；借方策略亏损 ≥ 50% | 所有 |
| `roll_21dte` | 短腿 DTE ≤ 21 | 所有 |
| `roll_up` | BPS/BPS_HV：SPX 涨幅 ≥ 3% + IVP ≥ 30 + 短腿 DTE > 14 → 平仓后原价位重开 | BPS 类 |
| `trend_flip` | Bull Call Diagonal：`days_held ≥ 3` 且 `trend == BEARISH` → 提前止损 | Diagonal |
| `end_of_backtest` | 回测截止日强制平仓 | 回测专用 |

---

## 4. 仓位管理架构（SPEC-013 + SPEC-014）

### 定仓公式

```python
contracts = account_size × bp_target / bp_per_contract
```

- `bp_target`：当日 regime 对应的 BP 目标（5% / 3.5%）
- `bp_per_contract`：BS 定价 + Schwab PM 规则计算的单合约保证金
- 替代了旧的 `account_size × risk_pct / opt_prem` 公式（premium risk 2%）

### 多仓并行入场条件

```python
used_bp = sum(p.bp_target for p in positions)          # 现有仓位已用 BP
new_bp  = params.bp_target_for_regime(regime)          # 新仓预计占用
ceiling = params.bp_ceiling_for_regime(regime)         # regime BP 上限

允许入场 iff:
  rec.strategy != REDUCE_WAIT
  AND 未持有相同 StrategyName（dedup）
  AND used_bp + new_bp ≤ ceiling
```

### BP 计算规则（Schwab Portfolio Margin）

| 策略类型 | BP per Contract 公式 |
|---------|---------------------|
| 信用价差（BPS / BCS / BCS_HV） | (spread_width − credit) × $100 |
| Iron Condor / IC_HV | (max(call_width, put_width) − net_credit) × $100 |
| 借方对角线（Bull Call Diagonal） | net_debit × $100 |
| 借方价差（Bull/Bear Call/Put Spread） | net_debit × $100 |

---

## 5. 回测结果（Precision B，SPEC-013 后基线，2026-03-29）

> **Precision B 说明**：Black-Scholes 中间价定价；无 bid-ask spread，无滑点；sigma 使用当天 VIX（非锁定 IV）。实际表现约为回测结果 × 0.7–0.8。

### 3yr（2022-01-01 → 2026-03-29）

| 指标 | 数值 |
|------|------|
| 交易笔数 | 47 |
| 胜率 | 61.7% |
| Sharpe（年化） | 0.93 |
| Total PnL | +$16,094 |
| Max Drawdown | −$4,774 |

**按策略 ROM（年化 Return on Margin）：**

| 策略 | n | WR | avg_rom | 说明 |
|------|---|----|---------|----|
| Iron Condor HV | 6 | — | +2.98 | HIGH_VOL 环境溢价丰厚 |
| Bear Call Spread HV | 10 | — | +1.13 | SPEC-006 新增，有效 |
| Bull Call Diagonal | 17 | — | −0.147 | 2022–2023 熊市/加息拖拽 |
| Bull Put Spread HV | 3 | — | −6.60 | 样本过小，不代表性 |

### 1yr（2024-01-01 → 2026-03-29，单仓基线）

| 指标 | 数值 |
|------|------|
| 交易笔数 | 23 |
| 胜率 | 60.9% |
| Sharpe（年化） | 1.48 |
| Total PnL | +$13,952 |
| Max Drawdown | −$4,213 |
| Bull Call Diagonal avg_rom | +1.36（2024 牛市恢复正常） |

**注**：SPEC-014（多仓并行）上线后，1yr trades = **30**（+30%）；完整 Sharpe / PnL 待重跑确认。

### 历史 BP 利用率验证

| Regime | bp_target | 实测 bp% |
|--------|-----------|---------|
| NORMAL | 5.0% | 5.0% ✅ |
| HIGH_VOL | 3.5% | 3.5% ✅ |

---

## 6. 主要改动历史（2026-03-28 → 2026-03-29）

### SPEC-006：Bear Call Spread HV（HIGH_VOL + BEARISH）
- **原状态**：HIGH_VOL + BEARISH → REDUCE_WAIT（空转约 13% 交易日）
- **改动**：HIGH_VOL + BEARISH + VIX 非 RISING → Bear Call Spread HV（SELL δ0.20 CALL / BUY δ0.10 CALL，DTE=45）
- **依据**：策略扫描显示 BCS_HV WR 86%，Sharpe +0.577——BEARISH 确认时 MA50 滞后使下跌通常已完成，OTM call 到期价外概率高；借方方向性策略（LEAP Put、Bear Put Spread）反而因 V 型反转失效

### SPEC-007：Iron Condor for BEARISH + NORMAL（IV HIGH & NEUTRAL 路径）
- **原状态**：BEARISH + NORMAL + IV HIGH/NEUTRAL → REDUCE_WAIT
- **改动**：VIX 非 RISING + IVP 20–50 时允许开 IC（δ0.16 两翼）
- **结果**：Total PnL +$7,655，Sharpe +0.17
- **注意**：IV LOW + BEARISH 路径保持 REDUCE_WAIT（15 笔额外 IC 每笔平均亏损 $553，v2 已回滚）

### SPEC-008：Iron Condor HV（HIGH_VOL + NEUTRAL）
- **原状态**：HIGH_VOL + NEUTRAL → REDUCE_WAIT
- **改动**：VIX 非 RISING + 无 backwardation → Iron Condor HV（δ0.16/δ0.08，DTE=45，半仓）
- **依据**：HIGH_VOL NEUTRAL 环境双侧权利金均被拉高，IC 对称结构最适合捕获

### SPEC-009：移除 NORMAL + IV LOW + BULLISH → Diagonal
- **原状态**：NORMAL + IV LOW + BULLISH → Bull Call Diagonal
- **改动**：→ REDUCE_WAIT（IVP < 40 时 Diagonal long leg 昂贵、short leg 收入薄，净 PnL 负）
- **结果**：3yr Sharpe +0.20，WR +3.7pp；26yr 小幅让步 PnL（$−3,357）
- **通用教训**：Sequential Replacement Effect——"过滤"不等于"删除"，等于以更差价格延迟入场

### SPEC-012：ROM（Return on Margin）指标
- **改动**：`Trade` dataclass 新增 `rom_annualized` property；`compute_metrics` by_strategy 新增 `avg_rom` / `median_rom`
- **公式**：`exit_pnl / total_bp × (365 / hold_days)`

### SPEC-013：BP 利用率驱动的仓位定量
- **改动**：`contracts = account_size × bp_target / bp_per_contract`，替代旧的 `account_size × risk_pct / opt_prem`
- **参数**：LOW_VOL=5%，NORMAL=5%，HIGH_VOL=3.5%
- **效果**：单笔 BP 从原来的 2–3% 提升至 5%（与 tastytrade PM 实践对齐）；P&L 绝对值 ×2–3

### SPEC-014：多仓并行引擎架构
- **改动**：`position: Optional[Position]` → `positions: list[Position]`；入场条件从 `position is None` 改为 BP ceiling 检查 + dedup 检查
- **BP ceiling**：LOW_VOL 25%，NORMAL 35%，HIGH_VOL 50%
- **效果**：1yr trades 23 → 30（+30%）；BP ceiling 和 dedup 守护均无违规

---

## 7. 已知局限 / 待研究

| 问题 | 影响 | 优先级 |
|------|------|--------|
| Bull Call Diagonal 3yr avg_rom = −0.147 | 2022–2023 熊市/加息拖拽；2024 单年已恢复（+1.36）；长期结构待观察 | 中 |
| SPEC-014 多仓后 Sharpe / PnL 未重跑 | 1yr trades 已确认 23→30，完整指标待确认 | **待做** |
| PM cross-margin netting 未建模 | 多仓总 BPR 被高估约 20–40%；当前以独立加总为保守基准 | 低 |
| 回测 sigma 用当天 VIX（非锁定 IV） | SPX 上涨 → VIX 下降 → vega 自动获利，结果偏乐观（折扣 ×0.7–0.8） | 中 |
| 无 bid-ask spread / 滑点 | 实际每笔额外成本约 $50–150 | 中 |
| Sharpe 为 trade-level（非日收益率）| 多仓并行下为近似；不影响策略相对比较 | 低 |

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
│   ├── selector.py       决策矩阵（VIX×IVP×趋势→策略+参数）+ StrategyParams（含BP字段）
│   └── state.py          持仓状态追踪（OPEN/CLOSE_AND_OPEN/WAIT）
├── backtest/
│   ├── pricer.py         Black-Scholes（price/delta/theta/strike搜索）
│   ├── engine.py         回测引擎（多仓并行，BP 定仓，ROM 指标，Precision B）
│   └── experiment.py     实验管理（run_experiment/load_experiments/diff_metrics）
├── notify/telegram_bot.py Telegram 推送（HTML格式）
├── web/
│   ├── server.py         Flask API + 实验 API + 自动搜索 API
│   └── templates/        index / backtest / matrix HTML
├── task/                 SPEC 文件（SPEC-001~014）
├── doc/                  research_notes.md / strategy_status / SYSTEM_DESIGN
└── main.py               CLI 入口（--dry-run / --backtest / bot 模式）
```

---

## 10. SPEC 状态汇总

| SPEC | 标题 | 状态 |
|------|------|------|
| SPEC-001~003 | 旧格式存档（strategy_spec.md） | DONE |
| SPEC-004 | *(已归档)* | DONE |
| SPEC-005 | Bear Call Diagonal 入场过滤 | REJECTED |
| SPEC-006 | Bear Call Spread HV | DONE |
| SPEC-007 | Iron Condor for BEARISH+NORMAL | DONE |
| SPEC-008 | Iron Condor HV | DONE |
| SPEC-009 | 移除 NORMAL+IV_LOW+BULLISH→Diagonal | DONE |
| SPEC-010~011 | *(跳过或归档)* | — |
| SPEC-012 | ROM 指标 | DONE |
| SPEC-013 | BP 利用率驱动定仓 | DONE |
| SPEC-014 | 多仓并行引擎架构 | DONE |

---

*生成于 2026-03-29 | Precision B 回测 | 账户：$150k PM | SPEC-013+014 后基线*
