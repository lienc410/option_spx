# SPX Options Strategy — Strategy Design Status
**Date: 2026-04-05（更新版，含 SPEC-030~038）| 适用于重建系统理解的完整策略文档**

*承接 `strategy_status_2026-03-30.md`。主要变更（初版）：ATR 趋势信号（SPEC-020）、Portfolio Risk Infrastructure（SPEC-024/025/026）、bp_target 2× 放大（SPEC-024 Fast Path）。*
*追加变更（SPEC-030~038）：策略/信号/回测逻辑无变更；系统新增真实交易链路全链路（trade log / correction / void / Schwab API / performance 页面 / paper trade filter），见 system_status_2026-04-05.md §4.20–4.24。*

---

## 1. 系统定位

**SPX 期权溢价收割系统（timed short-vol engine）**

- 账户类型：Portfolio Margin（OCC TIMS 风险保证金，约 0.02–0.05 × 名义敞口）
- 标的：SPX / SPY 期权
- 核心逻辑：通过 VIX regime + IV 信号 + 趋势信号三维过滤，在期望正值的市场环境中卖出期权溢价，靠 Theta 衰减和 vol premium 收割获利
- **不是**方向性趋势跟随引擎——趋势信号是风险过滤器（Risk Reducer），不是 return driver

### 实证基线（26yr 回测，2000–2026，ATR filter 启用后）

| 指标 | 值 |
|------|---|
| 总交易笔数 | 309（ATR 筛选后；baseline 354） |
| Sharpe（trade-level） | 1.43 |
| Sharpe（daily portfolio） | 0.86（EXP-full，SPEC-026 overlay active） |
| MaxDD | -11.21% |
| IS Sharpe（2000–2019） | 1.48 |
| IS MaxDD | -11.21% |
| OOS Sharpe（2020–2026） | 1.68 |
| OOS MaxDD | -4.94% |

注：trade-level Sharpe（激进口径）与 daily portfolio Sharpe（保守口径）使用不同计量基础，两者均有效，分别用于策略族对比与组合风险控制。

---

## 2. 信号体系（三维过滤）

### 2.1 VIX Regime（`signals/vix_regime.py`）

| Regime | VIX 范围 | 说明 |
|--------|---------|------|
| LOW_VOL | VIX < 15 | 低波动，thin premium |
| NORMAL | 15 ≤ VIX < 22 | 标准环境 |
| HIGH_VOL | 22 ≤ VIX < 35（`extreme_vix`）| 高溢价，需缩小规模 |
| EXTREME_VOL | VIX ≥ 35 | 强制 REDUCE_WAIT，不开新仓 |

补充信号：
- **VIX 5 日趋势**（RISING/FALLING/FLAT）：5 日均值 vs 前 5 日均值，变化 > 5% 才判为 RISING/FALLING
- **VIX 期限结构（backwardation）**：spot VIX > ^VIX3M → 触发保护过滤（BPS/BPS_HV 不入场）

### 2.2 IV 信号（`signals/iv_rank.py`）

使用 VIX 作为 IV 代理。两个指标并行计算：
- **IV Rank (IVR)**：(当前 VIX − 52 周低) / (52 周高 − 低) × 100
- **IV Percentile (IVP)**：过去 252 天中 VIX 低于今日的百分比

**有效 IV 信号逻辑**：若 IVR 与 IVP 偏差 > 15 点，则使用 IVP（避免单次 VIX 尖峰扭曲 IVR）

| IV Signal | IVP 阈值 | 含义 |
|-----------|---------|------|
| HIGH | IVP > 70 | 卖期权有优势 |
| NEUTRAL | 40 ≤ IVP ≤ 70 | 无强方向 |
| LOW | IVP < 40 | 溢价不足，避免信用策略 |

### 2.3 趋势信号（`signals/trend.py`）— ATR 标准化版本（SPEC-020 RS-020-2 生产）

**ATR-Normalized Entry Gate**（`use_atr_trend=True`，当前默认）：

```python
atr14 = close.diff().abs().rolling(14).mean()   # True Range 近似
gap_sigma = (SPX - MA50) / atr14                # ATR 标准化距离
ATR_THRESHOLD = 1.0                             # 统一阈值
```

| Signal | 条件 | 含义 |
|--------|------|------|
| BULLISH | `gap_sigma >= +1.0` | 偏多（ATR 标准化） |
| NEUTRAL | `-1.0 < gap_sigma < +1.0` | 中性 |
| BEARISH | `gap_sigma <= -1.0` | 偏空 |

**设计理由**：固定 1% band 在不同波动环境下含义不一致（VIX=12 时门槛过宽，VIX=30 时过窄）。ATR 标准化后阈值语义一致，OOS Sharpe +6bp，Full MaxDD 改善 2.73pp。

**Persistence Filter 已拒绝（RS-020-2）**：`bearish_streak >= 3` 方案使 OOS Sharpe -5bp，MaxDD 恶化 3.84pp。当前保持"单日即翻转"（`bearish_persistence_days=1`）。

`TrendSnapshot` 新增字段：`atr14: Optional[float]`、`gap_sigma: Optional[float]`

额外追踪：SPX > MA200（macro warning，仅展示，不影响 selector 决策）

---

## 3. 决策矩阵（`strategy/catalog.py` → `CANONICAL_MATRIX`）

```
VIX Regime    IV Signal   Trend      → Strategy
─────────────────────────────────────────────────────────
LOW_VOL       any         BULLISH    → Bull Call Diagonal (SPX 90/45 DTE)
LOW_VOL       any         NEUTRAL    → Iron Condor        (SPX 45 DTE)
LOW_VOL       any         BEARISH    → Reduce / Wait
NORMAL        HIGH/NEUTRAL BULLISH   → Bull Put Spread    (SPX 30 DTE) *
NORMAL        HIGH/NEUTRAL NEUTRAL   → Iron Condor        (SPX 45 DTE)
NORMAL        HIGH/NEUTRAL BEARISH   → Iron Condor        (SPX 45 DTE)
NORMAL        LOW         any        → Reduce / Wait
HIGH_VOL      any         BULLISH    → Bull Put Spread HV (SPX 35 DTE) *
HIGH_VOL      any         NEUTRAL    → Iron Condor HV     (SPX 45 DTE) *
HIGH_VOL      any         BEARISH    → Bear Call Spread HV(SPX 45 DTE) *
EXTREME_VOL   any         any        → Reduce / Wait
─────────────────────────────────────────────────────────
* BPS/BPS_HV: 若 backwardation（spot VIX > VIX3M）→ 覆盖为 Reduce/Wait
* HIGH_VOL + BEARISH + VIX RISING → 覆盖为 Reduce/Wait（panic escalating）
```

---

## 4. 六大策略及参数

### 4.1 Bull Call Diagonal（LOW_VOL + BULLISH）
- 标的：SPX，Long 90 DTE δ0.70 call + Short 45 DTE δ0.30 call
- BP 计算：net debit × 100
- 出场：50% 利润 / 50% 亏损 / Short leg 21 DTE / **trend_flip（单日 BEARISH 即触发）**
- Greek：short_gamma=False, short_vega=False（Long vega — vol 上升时受益）
- Realism haircut：**6%**（最可靠，vega bias 与 bid-ask 相互抵消）

### 4.2 Bull Put Spread（NORMAL + BULLISH）
- 标的：SPX，Short put δ0.30 / Long put δ0.15，DTE=30
- BP 计算：(spread_width − net credit) × 100 × 0.1
- 出场：50% 利润（≥10天后）/ 21 DTE / 2× credit stop / roll_up（SPX 涨 ≥3% + regime ≠ LOW_VOL + IVP ≥ 30）
- Greek：short_gamma=True, short_vega=True, delta="bull"
- Raw ROM 排名 #1，Adj ROM 排名 **#1**（haircut 30%，最稳健）

### 4.3 Iron Condor（LOW_VOL/NORMAL + NEUTRAL）
- 标的：SPX，Short call δ0.16 + Short put δ0.16 + wings δ0.08，DTE=45
- Wing width：max(50, SPX × 1.5%，取整至 $50)
- BP 计算：(spread_width − net credit) × 100 × 0.1
- 出场：50% 利润（≥10天后）/ 21 DTE / 2× credit stop
- Greek：short_gamma=True, short_vega=True, delta="neut"
- **结构性最危险**：CVaR 5% $−5,045，skewness −2.66，payoff ratio 0.43
- Realism haircut 74%（4腿 bid-ask 最贵）

### 4.4 Bull Put Spread HV（HIGH_VOL + BULLISH）
- 标的：SPX，Short put δ0.20 / Long put δ0.10，DTE=35
- 规模缩小至 0.5×（high_vol_size = 0.50）
- 出场：50% 利润 / 21 DTE / 2× credit stop
- Greek：short_gamma=True, short_vega=True, delta="bull"
- Realism haircut 72%

### 4.5 Bear Call Spread HV（HIGH_VOL + BEARISH）
- 标的：SPX，Short call δ0.20 / Long call δ0.10，DTE=45
- 规模 0.5×
- 出场：50% 利润 / 21 DTE / 2× credit stop
- Greek：short_gamma=True, short_vega=True, delta="bear"
- **最"纯" premium 策略**：SPX −5% 到 +3% 范围内 WR=100%，失败模式仅限 SPX ≥+5%

### 4.6 Iron Condor HV（HIGH_VOL + NEUTRAL）
- 与 Iron Condor 相同结构，规模 0.5×，DTE=45
- Greek：short_gamma=True, short_vega=True, delta="neut"

---

## 5. 仓位管理参数（`StrategyParams`）

### 5.1 基础参数

| 参数 | 默认值 | 说明 |
|------|-------|------|
| `extreme_vix` | 35.0 | VIX ≥ 35 → EXTREME_VOL，强制 REDUCE_WAIT |
| `high_vol_delta` | 0.20 | HIGH_VOL BPS short leg delta |
| `high_vol_dte` | 35 | HIGH_VOL BPS DTE |
| `high_vol_size` | 0.50 | HIGH_VOL 规模倍数 |
| `normal_delta` | 0.30 | NORMAL BPS short leg delta |
| `normal_dte` | 30 | NORMAL BPS DTE |
| `profit_target` | 0.50 | 信用策略利润目标（50% max credit）|
| `stop_mult` | 2.0 | 止损倍数（2× credit received）|
| `min_hold_days` | 10 | 利润目标触发最少持仓天数 |

### 5.2 BP 利用率（SPEC-024 2× 放大，已部署）

| Regime | bp_target | bp_ceiling |
|--------|-----------|-----------|
| LOW_VOL | **10%** | 25% |
| NORMAL | **10%** | 35% |
| HIGH_VOL | **7%** | 50% |

SPEC-024 实证：bp_ceiling 从未是 binding constraint（实际利用率 ~3.5%），放大 bp_target 使 Sharpe 不变（1.34），仅线性放大绝对 PnL（+100%）。

### 5.3 Portfolio Greek 限制（SPEC-017）

| 参数 | 默认值 | 说明 |
|------|-------|------|
| `max_short_gamma_positions` | 3 | 同时持有 short_gamma 仓位上限 |

**Synthetic IC Block**：已有 BPS_HV 时阻断 BCS_HV（反之亦然）

### 5.4 Vol Spell Throttle（SPEC-015）

| 参数 | 默认值 | 说明 |
|------|-------|------|
| `spell_age_cap` | 30 | HIGH_VOL spell 超过 30 天后，不开新 HV 策略 |
| `max_trades_per_spell` | 2 | 同一 spell 内最多 2 笔 HV 仓位 |

### 5.5 Portfolio Risk Infrastructure（SPEC-024/025/026 新增字段）

| 参数 | 默认值 | 说明 |
|------|-------|------|
| `initial_equity` | 100,000 | 回测初始净值 |
| `shock_mode` | `"shadow"` | Shock engine 模式（`"shadow"` / `"active"`）|
| `shock_budget_core_normal` | 0.0125 | Core shock 预算（NORMAL regime，占 NAV）|
| `shock_budget_core_hv` | 0.0100 | Core shock 预算（HIGH_VOL regime）|
| `shock_budget_incremental` | 0.0040 | 新仓位增量 shock 预算（NORMAL）|
| `shock_budget_incremental_hv` | 0.0030 | 新仓位增量 shock 预算（HIGH_VOL）|
| `shock_budget_bp_headroom` | 0.15 | BP headroom 下限（15%）|
| `overlay_mode` | `"disabled"` | Overlay 状态机（`"disabled"` / `"active"`）|
| `overlay_freeze_accel` | 0.15 | L1 Freeze 触发：vix_accel_3d 阈值 |
| `overlay_freeze_vix` | 30.0 | L1 Freeze 触发：VIX 绝对水位 |
| `overlay_trim_accel` | 0.25 | L2 Trim 触发：vix_accel_3d（AND）|
| `overlay_trim_shock` | 0.01 | L2 Trim 触发：book_core_shock（AND）|
| `overlay_hedge_accel` | 0.35 | L3 Hedge 触发：vix_accel_3d（AND）|
| `overlay_hedge_shock` | 0.015 | L3 Hedge 触发：book_core_shock（AND）|
| `overlay_emergency_vix` | 40.0 | L4 Emergency 触发：VIX（OR）|
| `overlay_emergency_shock` | 0.025 | L4 Emergency 触发：book_core_shock（OR）|
| `overlay_emergency_bp` | 0.10 | L4 Emergency 触发：bp_headroom（OR）|
| `use_atr_trend` | `True` | 使用 ATR 标准化趋势信号（RS-020-2 生产）|
| `bearish_persistence_days` | 1 | 趋势翻转所需连续天数（1 = 单日即翻转）|

---

## 6. 出场规则（所有策略）

| 规则 | 条件 | 适用策略 |
|------|------|---------|
| `50pct_profit` | PnL ≥ 50% × \|entry_credit\|，且 days_held ≥ 10 | 所有信用策略 |
| `roll_21dte` | Short leg DTE ≤ 21 | 所有策略 |
| `stop_loss` | 信用：PnL ≤ −2× credit；借方：PnL ≤ −50% debit | 所有策略 |
| `roll_up` | BPS/BPS_HV，SPX 涨 ≥3%，DTE > 14，regime ≠ LOW_VOL，IVP ≥ 30 | BPS 系列 |
| `trend_flip` | Diagonal，持仓 ≥ 3 天，trend → BEARISH（单日即触发）| Bull Call Diagonal |
| `overlay_trim` | overlay L2/L3/L4 触发，强制清仓 | 所有仓位 |
| `overlay_emergency` | overlay L4 触发 | 所有仓位 |

### P&L 来源分解（26yr 实证，SPEC-020）

| Exit Reason | 贡献% | 说明 |
|------------|-------|------|
| 50pct_profit | +66.5% | Theta + vol premium 主引擎 |
| roll_21dte | +61.4% | 时间价值自然衰减 |
| stop_loss | −12.6% | 受控亏损 |
| trend_flip | −19.8% | Diagonal 的"保险成本" |

---

## 7. 入场守护链（engine 执行顺序）

每个交易日执行以下步骤：

```
Step 0  【每日开始，独立于入场路径】
  → 对现有仓位 run_shock_check(candidate_position=None) → _daily_book_shock
  → compute_overlay_signals(vix, vix_3d_ago, _daily_book_shock, bp_headroom, params) → overlay

Step pre-entry
  → if overlay.force_trim: 强制平所有仓位（exit_reason="overlay_trim"/"overlay_emergency"）

Steps 1–6 【候选入场检查】
  1. rec.strategy != REDUCE_WAIT
  2. not overlay.block_new_entries（overlay L1+ → 禁止新开 short-vol）
  3. not _already_open（同 StrategyName 无重叠持仓）
  4. not _synthetic_block（无 BPS_HV + BCS_HV 并发）
  5. not _sg_block（short_gamma 仓位数 < max_short_gamma_positions）
  6. not _spell_block（HIGH_VOL spell age ≤ cap 且 spell 内交易数 < max_trades_per_spell）

Step 7  【SPEC-025 Shock Gate】
  → run_shock_check(existing_positions + candidate, ...) → ShockReport
  → shock_mode="active" 时：若 post_max_core > budget → 拒绝入场

Step 8  【BP ceiling】
  → _used_bp + _new_bp_target ≤ _ceiling
```

---

## 8. Portfolio Risk Infrastructure

### 8.1 VIX Acceleration Overlay（SPEC-026，`signals/overlay.py`）

| Level | 触发条件 | 逻辑 | 行动 |
|---|---|---|---|
| L0 Normal | — | — | 正常运行 |
| L1 Freeze | `accel_3d > 15%` OR `vix >= 30` | OR | 禁止新开 short-vol |
| L2 Freeze+Trim | `accel_3d > 25%` AND `book_core_shock >= 1%` | AND | Freeze + 强制平仓 |
| L3 Freeze+Trim+Hedge | `accel_3d > 35%` AND `book_core_shock >= 1.5%` | AND | v1 同 L2；v2 额外 long put spread |
| L4 Emergency | `vix >= 40` OR `book_core_shock >= 2.5%` OR `bp_headroom < 10%` | OR | 强制退出所有仓位 |

- `vix_accel_3d = (VIX_t / VIX_{t-3}) - 1`
- `book_core_shock` = 现有仓位在 8 个 Core 场景下的最差损失 / NAV（每日独立计算，Step 0）
- `overlay_mode="disabled"` 时恒返回 L0（向后兼容）

**EXP-full（overlay active）vs EXP-baseline：**
- Full MaxDD 改善：-15.35% → -12.22%（+20.4%）
- Full Sharpe（daily portfolio）：0.70 → 0.86
- 2011/2015 压力窗口 MaxDD 显著改善

### 8.2 Portfolio Shock-Risk Engine（SPEC-025，`backtest/shock_engine.py`）

8 个标准场景：

| 场景 | Spot_pct | vix_shock_pt | 分类 |
|---|---:|---:|---|
| S1 下行轻冲击 | -2% | +5pt | Core |
| S2 下行中冲击 | -3% | +8pt | Core |
| S3 下行重冲击 | -5% | +15pt | Core |
| S4 纯波动率冲击 | 0% | +10pt | Core |
| S5–S7 | 上行 | — | Tail（记录，不入预算） |
| S8 | -2% | +5pt | 独立记录 |

- sigma = max(0.05, min(2.00, current_vix / 100))（使用当日 VIX，非历史入场 sigma）
- S1–S4 Core Scenarios 用于 `max_core_loss_pct_nav` 预算控制
- shadow mode（默认）：所有入场通过，仅记录审计日志
- active mode：`post_max_core > budget` → 拒绝入场

### 8.3 Daily Portfolio Tracking（SPEC-024）

- `PortfolioTracker`（`backtest/portfolio.py`）：每日追踪 `DailyPortfolioRow`（17 字段）
- `compute_portfolio_metrics()`（`backtest/metrics_portfolio.py`）：daily_sharpe、daily_calmar、cvar_95、pnl_per_bp_day 等
- `generate_experiment_id()` / `config_hash()`（`backtest/registry.py`）：实验 ID 与参数哈希，支持结果回放与对比
- `pnl_per_bp_day = total_net_pnl / sum(daily_used_bp)`：资本效率核心指标

---

## 9. 历史性能基准

### 26yr（2000–2026，ATR filter 启用）

| 指标 | 值 |
|------|---|
| Sharpe（trade-level） | 1.43 |
| Sharpe（daily portfolio） | 0.86（EXP-full） |
| Calmar | 0.70（daily portfolio Calmar） |
| MaxDD | -11.21% |
| 总交易数 | 309 |

### IS（2000–2019） / OOS（2020–2026）

| 窗口 | Sharpe | MaxDD |
|------|-------|-------|
| IS（2000–2019） | 1.48 | -11.21% |
| OOS（2020–2026） | 1.68 | -4.94% |

### OOS 验收标准结果

| AC | 阈值 | 结果 |
|---|---|---|
| OOS-1 Sharpe > 0 | > 0 | **PASS**（1.68） |
| OOS-2 MaxDD improvement | ≥ 5pp | **FAIL**（1.49pp；注：OOS baseline MaxDD 本身仅 -5.01%）|
| OOS-3 PnL retention | ≥ 85% | **PASS**（94.4%）|
| OOS-4 Trade drop | ≤ 15% | **PASS**（OOS 频率 +12%）|

OOS-2 FAIL 不代表 overlay 无效——OOS 期 baseline 风险本来就低，overlay 在 IS 压力期（2008-2009、2011）作用更显著。

### 各策略族对比（Adj ROM 排名，2026-03-30 基准）

| 排名 | 策略 | Adj ROM | Haircut |
|------|------|---------|---------|
| #1 | Bull Put Spread | +2.433 | 30% |
| #2 | Iron Condor HV | +0.847 | 71% |
| #3 | Bull Put Spread HV | +0.747 | 72% |
| **#4** | **Bull Call Diagonal** | **+0.725** | **6%** |
| #5 | Bear Call Spread HV | +0.313 | 74% |
| #6 | Iron Condor | +0.269 | 74% |

---

## 10. 风险画像

| 风险类型 | 严重程度 | 保护机制 |
|---------|---------|---------|
| VIX=80 灾难级事件 | 极高（理论）| `extreme_vix` hard stop ✅；COVID 2020 正 PnL 验证 |
| VIX 25→50 中程急升 | 高（历史已发生）| **VIX Acceleration Overlay L2/L4 ✅**（SPEC-026，2011/2015 显著改善）|
| VIX 快速加速（vix_accel_3d > 15%）| 中高 | **L1 Freeze**（禁止新开 short-vol）|
| 组合 Core shock > budget | 中 | **Shock Gate Step 7**（active 模式阻断）|
| Sticky spell 叠加 | 中 | `spell_age_cap=30` + `max_trades_per_spell=2` ✅（SPEC-015）|
| BPS_HV + BCS_HV 合成 IC | 中 | Synthetic IC block ✅（SPEC-017）|
| 系统 Realism haircut | 结构性（50%）| 研究已量化，无法消除 |

---

## 11. 设计约束与研究协议

### Filter 复杂度协议（SPEC-021）

新 filter 必须满足：过滤后 n ≥ 50，26yr/3yr 方向一致，有明确期权/市场结构机制，不减少年均交易量 > 30%。

**实证结论**：filter 叠加无自动改善效果。当前 filter 层已达合理上限，ATR 趋势改进是通过替换（非叠加）实现的。

### Sharpe 使用指南（SPEC-022）

- 3yr 以下的 Sharpe 统计不确定性极大（CI 宽度 1.56），不宜单独决策
- Sharpe 差异 < 0.5 视为统计噪声
- 推荐补充：正年份比例 + Calmar + 最长连续亏损年数
- trade-level Sharpe（~1.43）与 daily portfolio Sharpe（~0.86）用途不同，不可混用

---

## 附：策略 Greek 签名速查

| 策略 key | short_gamma | short_vega | delta_sign |
|---------|------------|-----------|-----------|
| bull_call_diagonal | False | False | bull |
| bull_put_spread | True | True | bull |
| bull_put_spread_hv | True | True | bull |
| bear_call_spread_hv | True | True | bear |
| iron_condor | True | True | neut |
| iron_condor_hv | True | True | neut |
| reduce_wait | False | False | neut |
