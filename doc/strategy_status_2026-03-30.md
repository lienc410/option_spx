# SPX Options Strategy — Strategy Design Status
**Date: 2026-03-30 | 适用于重建系统理解的完整策略文档**

---

## 1. 系统定位

**SPX 期权溢价收割系统（timed short-vol engine）**

- 账户类型：Portfolio Margin（OCC TIMS 风险保证金，约 0.02–0.05 × 名义敞口）
- 标的：SPX / SPY 期权
- 核心逻辑：通过 VIX regime + IV 信号 + 趋势信号三维过滤，在期望正值的市场环境中卖出期权溢价，靠 Theta 衰减和 vol premium 收割获利
- **不是**方向性趋势跟随引擎——趋势信号是风险过滤器（Risk Reducer），不是 return driver

### 实证基线（26yr 回测，2000–2026）

| 指标 | 值 |
|------|---|
| 总交易笔数 | 386 |
| 胜率 | 75.6% |
| Sharpe | 1.54（Bootstrap 95% CI: [1.18, 1.95]）|
| Calmar | 26.23 |
| CVaR 5% | $−2,591 |
| Total PnL | $+192,234（Raw）/ $+94,070（Realism-adjusted，50% haircut）|
| Adj Sharpe | ~0.99 |
| Positive 年份 | 22/27（81%）|

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

### 2.3 趋势信号（`signals/trend.py`）

**SPX vs MA50 比较**（使用 ^GSPC）

| Signal | 条件 | 含义 |
|--------|------|------|
| BULLISH | SPX > MA50 × 1.01（gap > +1%）| 偏多 |
| NEUTRAL | ±1% 范围内 | 中性 |
| BEARISH | SPX < MA50 × 0.99（gap < −1%）| 偏空 |

补充：追踪 SPX 是否高于 MA200（macro warning）

**趋势信号的实际作用**（SPEC-019 实证）：
- 作为 ENTRY hard gate：所有 386 笔均 aligned（100%），但无反趋势基准可对比
- **作为 EXIT trigger（Diagonal 专属）**：是主要价值所在，78% 的 Diagonal 亏损由 trend_flip EXIT 捕获
- MA50 vs MA20 滞后差异仅 1.2 天（可忽略），MA50 选择合理

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
- 出场：50% 利润 / 50% 亏损 / Short leg 21 DTE / **trend_flip（BEARISH 翻转 ≥ 3 天）**
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
- BP：(spread_width − net credit) × 100 × 0.1
- 出场：50% 利润 / 21 DTE / 2× credit stop
- Greek：short_gamma=True, short_vega=True, delta="bull"
- Realism haircut 72%（HIGH_VOL 期 bid-ask spread 更宽）

### 4.5 Bear Call Spread HV（HIGH_VOL + BEARISH）
- 标的：SPX，Short call δ0.20 / Long call δ0.10，DTE=45
- 规模 0.5×
- 出场：50% 利润 / 21 DTE / 2× credit stop
- Greek：short_gamma=True, short_vega=True, delta="bear"
- **最"纯" premium 策略**：SPX −5% 到 +3% 范围内 WR=100%，失败模式仅限 SPX ≥+5%

### 4.6 Iron Condor HV（HIGH_VOL + NEUTRAL）
- 与 Iron Condor 相同结构，规模 0.5×，DTE=45
- Greek：short_gamma=True, short_vega=True, delta="neut"
- 3yr Sharpe 断崖（1.83→0.60），印证 sticky spell 风险

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

### 5.2 BP 利用率（每笔仓位占账户比例）

| Regime | bp_target | bp_ceiling |
|--------|-----------|-----------|
| LOW_VOL | 5% | 25% |
| NORMAL | 5% | 35% |
| HIGH_VOL | 3.5% | 50% |

实践中 bp_ceiling 受 dedup + Greek 限制约束，并发仓位一般 2–4 个。

### 5.3 Portfolio Greek 限制（SPEC-017）

| 参数 | 默认值 | 说明 |
|------|-------|------|
| `max_short_gamma_positions` | 3 | 同时持有 short_gamma 仓位上限 |

**Synthetic IC Block**：已有 BPS_HV 时阻断 BCS_HV（反之亦然）——避免合成 Iron Condor 但 short_gamma 量翻倍（历史 both_loss 率 40–53%）

### 5.4 Vol Spell Throttle（SPEC-015）

| 参数 | 默认值 | 说明 |
|------|-------|------|
| `spell_age_cap` | 30 | HIGH_VOL spell 超过 30 天后，不开新 HV 策略 |
| `max_trades_per_spell` | 2 | 同一 spell 内最多 2 笔 HV 仓位 |

**机制**：HIGH_VOL spell 的 P90 = 29 天，30 天 cap 覆盖 90% spell。Sticky spell（>30d）的 VIX slope ≈ 0（缓慢盘整），在入场信号上难以识别，靠 spell age 控制叠加风险。

---

## 6. 出场规则（所有策略）

| 规则 | 条件 | 适用策略 |
|------|------|---------|
| `50pct_profit` | PnL ≥ 50% × |entry_credit|，且 days_held ≥ 10 | 所有信用策略 |
| `roll_21dte` | Short leg DTE ≤ 21 | 所有策略 |
| `stop_loss` | 信用：PnL ≤ −2× credit；借方：PnL ≤ −50% debit | 所有策略 |
| `roll_up` | BPS/BPS_HV，SPX 涨 ≥3%，DTE > 14，regime ≠ LOW_VOL，IVP ≥ 30 | BPS 系列 |
| `trend_flip` | Diagonal，持仓 ≥ 3 天，trend → BEARISH | Bull Call Diagonal |

### P&L 来源分解（26yr 实证，SPEC-020）

| Exit Reason | 贡献% | 说明 |
|------------|-------|------|
| 50pct_profit | +66.5% | Theta + vol premium 主引擎 |
| roll_21dte | +61.4% | 时间价值自然衰减 |
| stop_loss | −12.6% | 受控亏损 |
| trend_flip | −19.8% | Diagonal 的"保险成本" |

---

## 7. 入场守护链（engine 执行顺序）

每个交易日检查以下条件，**全部通过**才开仓：

1. `rec.strategy != REDUCE_WAIT`（selector 已发出有效策略信号）
2. `not _already_open`（同 StrategyName 无重叠持仓）
3. `not _synthetic_block`（无 BPS_HV + BCS_HV 并发）
4. `not _sg_block`（short_gamma 仓位数 < max_short_gamma_positions）
5. `not _spell_block`（HIGH_VOL spell age ≤ cap 且 spell 内交易数 < max_trades_per_spell）
6. `_used_bp + _new_bp_target ≤ _ceiling`（BP 不超限）

---

## 8. 历史性能基准

### 26yr 整体（参考值）

| 指标 | 值 |
|------|---|
| Sharpe | 1.54（CI [1.18, 1.95]）|
| Calmar | 26.23 |
| WR | 75.6% |
| MaxDD | $−7,329 |
| Skewness | −0.62（short-vol 结构性负偏）|
| CVaR 5% | $−2,591 |

### 3yr（2022–2026，压力测试）

| 指标 | 值 |
|------|---|
| Sharpe | 1.15（CI [0.39, 1.96]）|
| Calmar | 4.21 |
| WR | 66.7% |
| SPEC-015 throttle 后 | 56 trades，Sharpe 0.97（vs noop 62 trades，Sharpe 0.90）|

### 各策略族对比（Adj ROM 排名）

| 排名 | 策略 | Adj ROM | Haircut |
|------|------|---------|---------|
| #1 | Bull Put Spread | +2.433 | 30% |
| #2 | Iron Condor HV | +0.847 | 71% |
| #3 | Bull Put Spread HV | +0.747 | 72% |
| **#4↑** | **Bull Call Diagonal** | **+0.725** | **6%** |
| #5 | Bear Call Spread HV | +0.313 | 74% |
| #6 | Iron Condor | +0.269 | 74% |

**关键洞察**：Diagonal haircut 最低（6%），Sharpe 最稳定（26yr 1.69 vs 3yr 1.75），是回测可信度最高的策略。

---

## 9. 风险画像

| 风险类型 | 严重程度 | 保护机制 |
|---------|---------|---------|
| VIX=80 灾难级事件 | 极高（理论）| `extreme_vix` hard stop ✅ 有效（COVID 2020 正 PnL 验证）|
| VIX 25→50 中程急升 | 高（历史已发生）| `backwardation` 部分保护；已开仓位需靠 exit rules |
| Sticky spell 叠加 | 中 | `spell_age_cap=30` + `max_trades_per_spell=2` ✅（SPEC-015）|
| BPS_HV + BCS_HV 合成 IC | 中 | Synthetic IC block ✅（SPEC-017）|
| 系统 Realism haircut | 结构性（50%）| 研究已量化，无法消除 |

**历史最恶劣连续亏损**：2015 年两笔共 $−6,210（Diagonal trend_flip + IC put side 击穿）

---

## 10. 设计约束与研究协议

### Filter 复杂度协议（SPEC-021）

新 filter 必须满足：过滤后 n ≥ 50，26yr/3yr 方向一致，有明确期权/市场结构机制，不减少年均交易量 > 30%。

**实证结论**：filter 叠加无自动改善效果（VIX 18-26 + MA gap 1-5% 组合 WR 76% < 基准 78%）。当前 7 层 filter 已达合理上限。

### Sharpe 使用指南（SPEC-022）

- 3yr 以下的 Sharpe 统计不确定性极大（CI 宽度 1.56），不宜单独决策
- Sharpe 差异 < 0.5 视为统计噪声
- 推荐补充：正年份比例（81%）+ Calmar + 最长连续亏损年数

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
