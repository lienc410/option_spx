# Strategy Research Notes

研究记录：策略设计决策、参数校准、止损规则等的回测验证结论。

---

## 1. Bull Call Diagonal — BEARISH 趋势翻转止损

**状态：✅ 已实施（2026-03-28）**

### 研究背景

分析历史上所有 Bull Call Diagonal 止损（stop_loss）出场的交易，寻找是否存在可提前识别的信号。

### 数据发现

全部 8 笔历史 Diagonal 亏损均在持仓第 1–8 天内出现 BEARISH 趋势信号：

| 入场日期 | BEARISH 首次出现（days_held） | 最终出场原因 | PnL |
|---------|--------------------------|------------|-----|
| 所有8笔 | days 1–8 | stop_loss | 全部亏损 |

盈利交易中，BEARISH 信号若出现，均在 days 1–2 内（单日振荡噪声）后恢复。

### 规则设计

```
持仓 days_held ≥ 3 且 trend == BEARISH → exit_reason = "trend_flip"
```

`days_held ≥ 3`：过滤单日噪声，3 天持续出现 BEARISH 才视为真实信号。

### 全局回测影响（26年，2000–2026）

| 指标 | 实施前 | 实施后 | 变化 |
|------|-------|-------|------|
| Diagonal WR | ~97% | 99.3% | +2.3pp |
| 总 PnL | 基准 | +$5,700 | +$5,700 |
| Sharpe | 6.42 | 5.90 | -0.52 |

Sharpe 下降原因：43 笔赢利交易被提前退出，PnL 分布方差改变，非真实风险上升。净 PnL 为正，WR 提升，规则有效。

> ⚠️ **数据作废（2026-03-29）**：以上 WR 97%/99.3% 及 Sharpe 6.42/5.90 均基于存在 `_entry_value` Bug 的旧引擎（见 §13）。Bug 修复后，Diagonal 实际 WR = **48.2%**（26 年，85 笔）。Diagonal 不是高胜率策略，而是低胜率 + 不对称收益（少量大赢覆盖多量小输）。趋势翻转规则仍然有效（限制了亏损），但 WR 数字本身不再有参考价值。

### 实现位置

`backtest/engine.py`：roll_up 检查之后，`if exit_reason:` 之前。

---

## 2. Bull Put Spread — IVP > 50 持仓期止损

**状态：❌ 已测试，否决**

### 研究背景

2025-10-03 BPS 入场后，第 4 天 IVP 升至 51.4，最终亏损 -$1,590。测试"持仓期 IVP 超过阈值即止损"规则。

### 测试范围

测试阈值：IVP > 45 / 50 / 55 / 60 / 65 / 70，全部26年数据。

### 结果

**所有阈值均伤害全局 PnL，幅度 -$13,000 至 -$27,000。**

根本原因：2001–2003 熊市、2009 金融危机恢复期、2020 疫情期间，IVP 长期维持 > 50，但 BPS_HV 持仓高度盈利。规则在结构性高波动期产生大量假阳性（误止盈利仓位）。

### 结论

IVP 持仓期阈值止损不适用于 BPS / BPS_HV。这类规则对历史数据过度拟合对单一亏损事件，对整体策略有害。

---

## 3. Bull Put Spread — IVP Spike 止损（IVP > 70 + 非 BULLISH 趋势）

**状态：❌ 已测试，否决（2026-03-28）**

### 研究背景

分析所有 BPS 亏损交易的持仓期信号，发现 3 笔显著亏损均有 VIX 单日大涨 + IVP 飙破 70 + 趋势转 NEUTRAL 的组合信号。

### 亏损案例中的触发情况

| 交易 | VIX 单日涨幅 | 触发 days_held | IVP | Trend |
|------|------------|--------------|-----|-------|
| 2015-11-27 | +13.8% | Day 4 | 74.1 | NEUTRAL |
| 2025-02-13 | +16.3% | Day 5 | 79.7 | NEUTRAL |
| 2025-10-03 | +31.8% | Day 5 | 82.1 | NEUTRAL |

### 规则设计（测试版）

```
持仓 days_held ≥ 3 且 strategy == BPS 且 IVP > 70 且 trend ≠ BULLISH → exit_reason = "ivp_spike"
```

### 全局回测影响

| 交易 | 无规则 | 有规则 | 净影响 |
|------|-------|-------|-------|
| 2015-11-27 | -1,792 | -1,892 | **-100** |
| 2021-12-10 | **+1,382** | -1,451 | **-2,833** ← 赢家变亏损 |
| 2025-02-13 | -3,922 | -1,656 | **+2,266** |
| 2025-10-03 | -1,590 | -2,211 | **-621** |
| **合计** | | | **-1,288** |

### 否决原因

1. **IVP 飙升是 BPS 平仓成本最高的时刻**：short put 深度价内，外在价值高，此时平仓极贵。
2. **2021-12-10**：IVP > 70 出现但 SPX 随后反弹，赢利仓位被强制平出，损失 $2,833。
3. **2025-10-03**：早退反而亏更多，因 SPX 在 IVP 高峰后小幅反弹。

BPS 与 Diagonal 的结构差异决定了止损逻辑不同：Diagonal 早退时 short call 跌价，平仓变便宜；BPS 早退时 short put 价内，平仓极贵。

---

## 4. Bull Put Spread — 入场 IVP 门槛提升 40 → 43

**状态：✅ 已实施（2026-03-28）**

### 研究背景

2025-10-03 BPS 入场时 IVP = 43.0（正好在原门槛 40 附近），最终亏损 -$1,590。IVP 过低意味着期权权利金不足以覆盖风险收益比。

### 规则变更

`strategy/selector.py`，NORMAL + IV_NEUTRAL + BULLISH 路径：

```python
# 原规则：IVP >= 40 即可入场（隐含，无下限）
# 新规则：IVP >= 43 才允许入场
if iv.iv_percentile < 43:
    return _reduce_wait(...)
```

注：IV_HIGH 路径（IVP > 70）的 BPS 分支已有 `IVP >= 50` 过滤，该路径实际为死代码（HIGH 环境 IVP 恒 > 70，永远满足 >= 50 而被拒绝）。只有 IV_NEUTRAL 路径（IVP 40–50）是 BPS 实际唯一入场通道。

### 意义

过滤边界溢价不足的 BPS 入场，如 2025-10-03 IVP=43.0 这类情形。该笔损失的主因仍是 SPX 急跌，但入场时权利金溢价更充裕可提高整体风险收益比。

---

## 5. Iron Condor — 各类提前止损规则

**状态：❌ 全部测试，全部否决**

### 背景

Iron Condor 历史上仅有 2 笔亏损，均为突发性制度性变化（非渐进信号）。测试多种提前止损规则。

### 测试结果

所有测试规则（趋势翻转、IVP 阈值、VIX 水平止损）均伤害全局 PnL。

**根本原因**：IC 的 2 笔亏损是黑天鹅式制度突变（VIX 急涨不给时间反应），而渐进信号（趋势、IVP）在损失发生前并未持续出现。规则只能误杀盈利仓位，无法拦截真实风险事件。

### 结论

IC 持仓期无可行的提前止损机制。IC 的风险管理应在**入场过滤**（选择合适的 regime + IV 条件）而非持仓期止损。

---

## 6. Bear Call Diagonal — BULLISH 趋势翻转退出

**状态：❌ 已验证，否决（2026-03-29）**

### 假设

Bull Call Diagonal 有效的 BEARISH exit 规则（days≥3 → trend_flip）理论上有对称镜像：Bear Call Diagonal 遇 BULLISH 信号提前平仓。

### 数据验证（ALL 2000–2026，11 笔）

BULLISH 信号（days_held ≥ 3）出现情况：

| 结果 | 笔数 | BULLISH 触发 | 说明 |
|------|------|------------|------|
| WIN | 5 | **5/5** | 全部赢利交易也出现了 BULLISH |
| LOSS | 6 | **6/6** | 全部亏损交易出现了 BULLISH |

规则在 100% 的交易中都会触发，完全无法区分赢家和输家。

### 原因分析

Bear Call Diagonal 结构（long deep-ITM put + short OTM put）：SPX 上涨时，short OTM put 加速 theta decay，持仓仍可盈利。BULLISH 信号出现时，持仓可能仍处于盈利区间。Bull Call Diagonal 不同——BEARISH 时 short call 主动被追入，产生持续亏损且极少在赢利交易中出现。

### 结论

Bear Call Diagonal 无可行的持仓期趋势止损规则。风险管理应前置到**入场过滤**，不在持仓期干预。

---

## 7. BPS_HV DTE 参数修复：21 → 35

**状态：✅ 已实施（2026-03-26 前）**

### 问题发现

回测显示 HIGH_VOL 环境下 BPS_HV 的表现异常差：409 笔交易，WR 57.5%，平均每笔仅 $23。

根本原因：
- DTE 入场 = 21 天
- 退出规则：`roll_21dte` 在 DTE ≤ 21 时触发

→ 入场时 DTE=21，当日即满足 DTE≤21 退出条件，**有效持仓约 1 个交易日**。

### 修复

将 `high_vol_dte` 从 21 改为 35。入场 DTE=35，roll_21dte 在 DTE≤21 时触发，有效持仓约 14 个交易日。

### 结果对比（ALL，26年）

| 指标 | 修复前 | 修复后 |
|------|-------|-------|
| BPS_HV 交易笔数 | 409 | 62 |
| BPS_HV 胜率 | 57.5% | 84% |
| BPS_HV 平均每笔 | $23 | ~$475 |
| 全局 Sharpe | 4.43 | 6.42 |

这是迄今为止单次参数修复对 Sharpe 影响最大的改动。

### 通用原则

**DTE 入场值必须显著大于 DTE 退出阈值（建议差距 ≥ 10天）。** 检查方式：`DTE_entry - DTE_exit_threshold = 实际最短有效持仓天数`。任何接近0或为负的设计是逻辑错误。

---

## 7. Iron Condor IVP 入场范围：20–50

**状态：✅ 已实施（2026-03-26 前，预防性）**

### 设计逻辑

Iron Condor 是 theta decay + vol compression 策略。入场条件需要：
1. **IVP > 20**：保费不足以支持 IC 的双边风险（IVP 过低时权利金接近 0）
2. **IVP < 50**：IVP ≥ 50 进入 stressed vol 环境，尾部风险超过 IC 双边保费

历史数据中，4 笔最大亏损 IC 入场时 IVP 在 55–58（旧上限 60 附近）。

### 注意

在历史回测中修改上限后（60 → 50）并无实际差异——现有逻辑中 IVP ≥ 50 早于 IC 路径就被过滤了。该修改是预防性的边界保护。

---

## 8. HIGH_VOL 策略：LEAP → BPS_HV

**状态：✅ 已实施（策略主要演进）**

### 原设计

HIGH_VOL（VIX ≥ 22）时推荐 Buy LEAP Call/Put（delta 0.70，365 DTE）。

**问题：**
- LEAP 是方向性赌注，在 HIGH_VOL 时方向判断难度最高
- 365 DTE LEAP 的回测 P&L 与模型误差高度耦合（vega 极大，Black-Scholes 偏差放大）
- theta 收入为负（付出时间价值），与策略主要目标矛盾

### 现设计

HIGH_VOL → **Bull Put Spread (High Vol)**：
- DTE = 35，delta = 0.20（比 NORMAL 的 0.30 更 OTM，减小尾部暴露）
- size_mult = 0.5（半仓，因 HIGH_VOL 时风险放大）
- stop_mult 适用（2× 权利金止损）

**结果（ALL，62笔）：** WR 84%，theta income 与主体策略一致，风险可控。

### EXTREME_VOL 阈值（VIX ≥ 35）

HIGH_VOL 内部有一个硬停：VIX ≥ 35 时全部 REDUCE_WAIT，不入场任何策略。

**逻辑：** VIX ≥ 35 通常对应危机期间（2008、2020 疫情高峰）。此时 Black-Scholes 定价失效（实际 vol surface 极度偏斜），delta 计算不可靠，任何方向判断都是赌博。保持空仓等待正常化。

---

## 9. 入场过滤器设计

### VIX RISING 过滤器

**规则：** VIX 5日均线上穿（VIX > 5d_SMA × 1.05）时，禁止 BPS 和 Iron Condor 入场，推荐 REDUCE_WAIT。

**逻辑：** BPS 和 IC 均为卖出期权策略。VIX 上升趋势意味着权利金成本上升，short put 的 delta 暴露在扩大。等待 VIX 稳定后再入场。

**注意：** VIX RISING 不影响 Bull Call Diagonal（借方策略，vega 正向）。

### 宏观过滤器（SPX < 200MA）

**规则：** SPX 低于 200 日均线时，推荐减仓 25–50%（显示警告），但**不改变策略选择**。

**为何不强制 REDUCE_WAIT：** 200MA 以下仍可能有反弹行情（2022年多次反弹），强制停止会错过大量机会。警告让用户根据自身判断调整仓位，系统不越权替用户决策。

### VIX 期限结构 Backwardation 过滤器

**规则：** spot VIX > VIX3M（短端高于长端）时，禁止 BPS 和 IC 入场。

**逻辑：** 正常情况下 VIX 期限结构 contango（VIX < VIX3M），反映市场对未来不确定性的升水。Backwardation 意味着**当前短期恐慌超过长期预期**，即市场预期近期波动将高于未来——恰好是 BPS 和 IC（卖短期波动）的最差入场时机。

---

## 10. IV 信号：IVR vs IVP 分歧处理

**规则：** `|IVR - IVP| > 15` 时，放弃 IVR，改用 IVP 配合修正阈值（HIGH > 70，LOW < 40）。

### 问题场景

当过去 52 周内出现过一次 VIX 极端峰值（如 VIX=80 in 2020），IVR 分母被该峰值拉大，导致当前 VIX=18 的 IVR 计算结果异常低（"LOW"），但实际市场波动并不低。

| 条件 | IVR 读数 | IVP 读数 | 实际环境 |
|------|---------|---------|---------|
| 峰值后正常恢复期 | 极低（分母被峰值拉大） | 正常 40–60 | 正常/中等波动 |

IVR 给出"LOW"信号 → 系统可能推荐 Bull Call Spread（低 IV 买方策略），实际环境是 NEUTRAL → 错误。

### 修正逻辑

IVP 使用百分位计算，不受单次峰值影响。当 IVR/IVP 分歧 > 15pt 时，IVP 更可靠。修正阈值（70/40 vs IVR 的 50/30）反映两者量纲不同。

---

## 11. 持仓管理参数设计

### 止盈目标：50% 权利金

**原则：** 在 50% 利润时平仓是期权卖方策略的标准实践，有两个依据：
1. 收取剩余 50% 权利金所需承担的 gamma/theta 风险不成比例地高（随 DTE 减少风险加速）
2. 研究（tastyworks 数据）显示 50% 止盈 vs 持有到期在长期 WR 和期望值上接近，但大幅降低持仓期内的波动暴露

### min_hold_days = 10

**规则：** 止盈触发前必须持仓至少 10 天。

**问题背景：** 无此限制时，入场后 1–3 天遇到 SPX 小幅跳涨（Bull Call Diagonal），short call 快速减值，系统立即触发 50% 止盈。虽然赚了钱，但持仓时间极短（1–3天）导致：
1. 资金利用率低（绝大多数时间空仓）
2. Sharpe 分母（交易频率）失真

10天门槛确保至少收到合理的 theta decay，避免靠运气触发的超短期套利。

### 止损倍数：2× 权利金（stop_mult = 2.0）

**逻辑：** 信用策略最大净亏损 = 价差宽度 - 权利金。2× 权利金止损约在最大亏损的 20–30% 处（典型价差宽度 50–100pt，权利金 30–45pt）。过紧（1×）则正常波动也会触发，过松（3×）则失去风险控制意义。

### BPS_HV 半仓（size_mult = 0.5）

HIGH_VOL 环境下，每笔 BPS 的 BP 占用约是 NORMAL 的 2× 以上（spread_width 更宽，权利金占比更低）。半仓使 HIGH_VOL 下每笔 BP% 与 NORMAL 下相当（约 5% vs 6.5%）。

---

## 12. 回测方法论说明

### Precision B：已知偏差

当前回测使用"Precision B"（Black-Scholes 中间价定价，无买卖价差）。已知的乐观偏差来源：

1. **sigma 使用当日 VIX（非锁定 IV）**：实际 sigma 应为开仓时的隐含波动率。用当日 VIX 意味着 SPX 上涨时 VIX 下降，short put 自动获得 vega 收益——这是真实账户无法获得的。
2. **无 bid-ask spread / 滑点**：SPX 期权每笔真实成本额外约 $50–150。
3. **无保证金资金成本**：PM 账户 margin 资金有利率成本。

**实际期望表现 ≈ 回测 P&L × 0.7–0.8**（粗估折扣）。

### Sharpe 计算公式

```python
sharpe = expectancy / std_pnl * sqrt(252 / avg_hold_days)
```

`sqrt(252 / avg_hold_days)` 将每笔交易视角的 Sharpe 年化。使用实际平均持仓天数（非假设固定周期），使不同策略之间的 Sharpe 可比。

### P&L 符号约定（常见错误）

```python
# 正确：
pnl = current_value - entry_value

# 错误（结果反向）：
pnl = entry_value - current_value
```

信用策略：`entry_value` 为负（收到权利金），平仓时 `current_value` 更小的负数（回购更便宜）→ `pnl` 为正。此约定在 `engine.py` 中严格执行。

---

## 总体结论

### 止损研究

| 策略 | 持仓期提前止损 | 结论 |
|------|-------------|------|
| Bull Call Diagonal | BEARISH 趋势翻转（days≥3） | ✅ 有效，已实施 |
| Bull Put Spread | IVP > 50 阈值 | ❌ 全局负面，否决 |
| Bull Put Spread | IVP > 70 + 非BULLISH（days≥3） | ❌ 全局负面，否决 |
| Bull Put Spread | — | 唯一有效防御是**入场过滤**（IVP≥43） |
| Iron Condor | 所有规则 | ❌ 全部否决，IC 无可行持仓期止损 |
| Bear Call Diagonal | BULLISH 趋势翻转（days≥3） | ❌ 全局触发（11/11），无区分能力，否决 |

### 参数与设计

| 决策 | 结论 |
|------|------|
| BPS_HV DTE | 35（非21），避免1天有效持仓陷阱 |
| IC IVP 范围 | 20–50（不含极低保费和stressed vol） |
| HIGH_VOL 策略 | BPS_HV（非LEAP），保持theta income方向一致 |
| EXTREME_VOL | VIX≥35 全部停止，Black-Scholes 失效区间 |
| IVR/IVP 分歧 | >15pt 时切换到 IVP+修正阈值 |
| min_hold_days | 10天，防止运气性超短期止盈 |
| stop_mult | 2.0×，在最大亏损20-30%处止损 |
| profit_target | 50%，收益/风险比在此处最优 |
| 仓位定量 | BP 利用率驱动（5%/5%/3.5%），替代 premium-risk 2%（§20） |
| 总 BP ceiling | 多仓并行：LOW_VOL 25%，NORMAL 35%，HIGH_VOL 50%（§21） |
| ROM 指标 | ann. exit_pnl/total_bp×365/hold_days，策略横向比较基准（§19） |

**核心洞察**：止损规则的有效性取决于策略结构。Diagonal 早退 short leg 便宜（call 在BEARISH时贬值），止损有利。BPS/IC 早退 short leg 最贵（put 在恐慌时最贵），止损锁定最大损失。**BPS 和 IC 的风险管理应前置到入场过滤，而非持仓期干预。**

### 当前基线（SPEC-013 后，多仓 SPEC-014 后）

| 窗口 | Trades | WR | Sharpe | Total PnL | Max DD |
|------|-------|----|----|---------|--------|
| 3yr (2022-01-01) | 47 | 61.7% | 0.93 | +$16,094 | -$4,774 |
| 1yr (2024-01-01) | 23→30* | 60.9%* | 1.48* | +$13,952* | -$4,213* |

*1yr 数字为 SPEC-013 后、SPEC-014 前的单仓基线（trades=23）；SPEC-014 多仓后 trades=30，Sharpe/PnL 待重跑确认。

---

## 13. SPEC-1B：7 日快速退出 — 研究结论（2026-03-28）

**状态：❌ 否决（规则等效于死规则，同时发现并修复 `_entry_value` 定价 Bug）**

### 背景

`strategy/selector.py` 描述的规则包含 "within first 7 trading days" 字样，但 `engine.py` 的实际实现是 `days_held >= min_hold_days (=10)`。SPEC-1B 探讨是否应实现一个真正的 7 日快速退出路径（即 `days_held <= 7` 时绕过 `min_hold_days` 检查）。

### Bug 发现：`_entry_value` 定价错误

在测试 SPEC-1B 时（添加 `or position.days_held <= 7`），发现所有 Bull Call Diagonal 在第 1 天即退出，导致交易数从 14 笔爆炸至 2000+ 笔。

溯源发现引擎存在 **`_entry_value` Bug**：

```python
# 修复前（错误）：
def _entry_value(legs, spx, sigma, dte_start):
    for action, is_call, strike, _, qty in legs:  # ← _ 丢弃了每条腿的 DTE
        price = call_price(spx, strike, dte_start, sigma)  # 所有腿用 short_dte=30

# 修复后（正确）：
def _entry_value(legs, spx, sigma):
    for action, is_call, strike, dte, qty in legs:  # ← 读取各腿自己的 DTE
        price = call_price(spx, strike, dte, sigma)
```

影响：对 BULL_CALL_DIAGONAL（long_dte=90, short_dte=30），long call 在 entry 时被错误地用 DTE=30 定价（而非 DTE=90），导致 `entry_value` 严重低估（约 65 vs 正确的 ~270）。但 `_current_value` 从 Day 1 起正确使用各腿自己的 DTE，造成 Day-1 pnl 虚高 ~56%，日日超越 50% 利润阈值。

`min_hold_days=10` **意外地掩盖了这个 Bug**——它阻止了提前触发，但所有 Diagonal 的绝对 PnL 数值都是基于错误 entry_value 计算的（过度杠杆化）。

**修复位置**：`backtest/engine.py` `_entry_value` 函数，2026-03-28 已修复。

### 修复后 SPEC-1B 验证

修复后，对 2023–2026 全部 14 笔 Diagonal 交易进行逐日 pnl_ratio 分析（前 7 个交易日）：

| 指标 | 结果 |
|------|------|
| 14 笔中触发 7 日快速退出的数量 | **0 笔** |
| 7 日内最高 pnl_ratio | +29.8%（2023-12-08，未到 50%） |
| 典型 7 日 pnl_ratio 范围 | -20% ~ +20% |

### 结论

**SPEC-1B 在正确定价下等效于死规则**：7 天内 Diagonal 价值增长无法达到 50% 阈值（需要 SPX 短期大幅上涨且 VIX 大幅下降，实际未发生）。规则添加与否对回测结果零影响。

**否决原因**：
1. 规则在正确定价下永不触发（2023–2026 零案例）
2. `min_hold_days=10` 的原始设计目的（防止运气性超短期套利）仍然合理
3. 添加规则增加代码复杂度，无实际收益

**实施建议**：维持现状（`days_held >= min_hold_days`），不实施 SPEC-1B。

---

## 14. Bear Call Diagonal — 入场过滤（≥5 连续 BULLISH 天）

**状态：❌ 否决（SPEC-005 REJECTED，2026-03-29）**

### 背景

Bear Call Diagonal（LOW_VOL + BULLISH）历史 WR 偏低（~67%），11 笔中 6 笔亏损，全部为 stop_loss 出场。假设：BULLISH 信号滞后——MA 信号确认时市场可能已接近阶段高点，若要求入场前已出现 ≥5 连续 BULLISH 天，则可过滤"信号刚出现"的高风险窗口。

### Prototype 数据（SPEC-005b）

- 连续 BULLISH 天数与入场 WR 呈**非单调**关系：
  - 0d：WR 41%（无信号历史）
  - 1–7d：WR 29–50%（最差区间）
  - ≥8d：WR 55%
- Sharpe proxy 峰值在 ≥7d（0.306），≥5d 给出 39 笔、WR 54%、Sharpe 0.300

### 顺序回测效应（Sequential Replacement Effect）

**实施后实际结果：**
- 预期：过滤掉 ~12 笔早期低胜率入场 → BCD n ≈ 39
- 实际：BCD n = 77（仅减少 12 笔），Total PnL = $58,299（低于 SPEC-004 基准 $70,017），Sharpe = 0.77

**根本原因：**
静态 prototype 分析假设"过滤 = 删除"。但在顺序回测中，过滤一个入场点并不会删除这笔交易，而是**延迟入场**——系统等待满足条件的下一个时间点，通常仍在同一个 BULLISH 连续段的第 5+ 天，此时 SPX 已上涨，BCD long deep-ITM call 成本更高（价内 call 随 SPX 上涨而升价），入场成本上升导致 PnL 更差。

| 指标 | 预期（静态） | 实际（顺序回测） |
|------|----------|--------------|
| BCD n | ~39 | 77 |
| Total PnL | ≥$60,000 | $58,299 |
| Sharpe | ≥1.10 | 0.77 |

### 结论

**连续天数过滤对顺序回测无效**：过滤不等于删除，等价于以更差价格延迟入场。任何"等待更多确认信号"的规则在连续制度期间都面临同样的替换效应——确认越晚，进入成本越高。

**通用教训**：静态相关分析（某特征 vs WR）无法预测顺序回测行为。特别是在趋势型信号（MA 类）中，制度内的后续入场点通常比第一个入场点价格更高。

---

## 15. BEARISH + HIGH_VOL 策略选择（SPEC-006，2026-03-29）

**状态：📋 SPEC-006 DRAFT，待 PM APPROVED**

### 背景

BEARISH 趋势占 26.1% 交易日，全部产生 REDUCE_WAIT（空仓）。其中 BEARISH + HIGH_VOL 占约 13%（868 天 / 26 年），是最大的空转时间段。

### 策略全扫描

在 BEARISH + HIGH_VOL（VIX 22–35）环境下，扫描 8 类策略（含借方方向性策略）：

| 策略类型 | 代表策略 | VIX FLAT+FALLING WR | Sharpe | 评分 |
|---------|---------|-------------------|--------|------|
| **信用——Bear Call Spread** | BCS δ0.20/δ0.10 DTE=45 | **86%** | **+0.577** | **0.247** |
| 信用——Iron Condor symmetric | IC sym DTE=45 | 67% | +0.307 | 0.103 |
| 信用——Bull Put Spread HV | BPS HV DTE=45 | 60% | +0.108 | 0.032 |
| 借方方向——Bear Put Spread | BPS dir DTE=45 | 30% | −0.xxx | 0.000 |
| 借方方向——Bear Put Diagonal | diag 90/45 | 33% | −0.xxx | 0.000 |
| 借方中性——Put Calendar | 45/21 DTE | 33% | −0.xxx | 0.000 |
| 借方方向——LEAP Put | δ0.70, 90d | 38% | −0.xxx | 0.000 |
| 借方方向——LEAP Put | δ0.70, 180d | 42% | −0.xxx | 0.000 |

评分公式：`(WR/100) × max(Sharpe, 0) / 腿数`（简洁性调整）

### 借方策略全面失效的原因

BEARISH 趋势由 MA50 信号确认，具有**滞后性**：
- BEARISH 信号出现时，SPX 已跌破 MA50，下跌行情通常已大部分完成
- MA 确认后市场常出现 V 型反弹（均值回归），方向性下跌赌注的 long put 被消耗
- Calendar spread 在 BEARISH+HIGH_VOL 的 VIX 倒挂（backwardation）期间失效

### BCS HV 为何有效

- **BEARISH 趋势** → SPX < MA50 → OTM call（δ0.20）到期价外概率高
- **HIGH_VOL** → call 权利金因恐慌被人为拉高 → 卖方收取超额信用
- **BCS 不依赖"继续下跌"**：只需市场不大幅反弹即可盈利，比方向性借方策略的 PoP 高得多
- backwardation 过滤不适用：backwardation 反映 put 侧短期恐慌，对 call 定价无负面影响

### 策略结构（SPEC-006 设计）

```
HIGH_VOL + BEARISH + VIX RISING   → REDUCE_WAIT（恐慌仍升级）
HIGH_VOL + BEARISH + VIX 非RISING → Bear Call Spread HV
    SELL CALL δ0.20, DTE=45
    BUY  CALL δ0.10, DTE=45
    size = 0.5×（与 BPS HV 一致）
HIGH_VOL + NEUTRAL                 → REDUCE_WAIT（无方向性支持）
HIGH_VOL + BULLISH                 → 原 BPS HV 逻辑（不变）
```

### 预期影响

- BCS HV n ≥ 20（26 年，约 51% BEARISH+HIGH_VOL 时间属于 VIX 非 RISING）
- WR ≥ 70%（prototype 基准 86%）
- Total PnL 新增 ≥ $8,000（从 $70,017 基准到 ≥ $78,000）
- Sharpe ≥ 1.20（从 $70,017 基准的 1.16）

---

## 16. 2nd Quant（ChatGPT）Review — research_notes 整体评估（2026-03-29）

**来源文件**：`task/research_notes_Review.md`
**Reviewer 结论**：REVISE
**Claude 评估结论**：**不采纳，维持现状**

### ChatGPT 提出的四项问题及评估

| 问题 | ChatGPT 结论 | Claude 评估 |
|------|------------|------------|
| 本质为 short vol，vol 不回落时系统性亏损 | REVISE | ✅ 描述正确，但已有 VIX RISING / backwardation / EXTREME_VOL 三层过滤，非新问题 |
| VIX 作为 IV proxy 导致 Sharpe 高估 | REVISE | ✅ 正确，已在 §12 文件化（回测折扣 × 0.7–0.8） |
| MA50 滞后 → 承担反转风险而非趋势收益 | REVISE | ❌ **建模错误**，见下方详述 |
| Regime clustering（多策略同向暴露） | 隐含风险 | ✅ 有效提醒，单仓设计下现况无即时影响 |

### MA50 批评为何不成立

ChatGPT 假设我们用 MA50 做趋势跟随（方向性），因此"信号滞后 = 错过主要行情"。但本系统的实际用途完全相反：

- **MA50 是信用策略方向过滤器，不是趋势入场信号**
  - BULLISH（SPX > MA50）→ 卖 OTM put（BPS）：只需市场不大幅下跌，与趋势方向无关
  - BEARISH（SPX < MA50）→ 卖 OTM call（BCS HV）：只需市场不大幅反弹，同样不依赖"继续下跌"

- **SPEC-006 prototype 实证**：MA 滞后正是 BCS HV 有效的根本原因
  - BEARISH 确认时下跌通常已完成，OTM call 到期价外概率更高
  - 借方方向性策略（LEAP Put、Bear Put Spread）反而因 MA 滞后失效（下跌已过、V 型反转）

MA50 的滞后性对信用策略是**结构性优势**，不是缺陷。

### 结论

**不执行 REVISE**。ChatGPT 的核心批评基于对 MA50 用途的错误假设，其余有效观点已在现有文件中覆盖。`research_notes.md` 维持现状。

**值得记录的通用教训**：外部 review 若未理解"信号用作方向过滤 vs 信号用作方向入场"的区别，会得出相反结论。在 code review 或策略评估中，需先核实 reviewer 对信号用途的建模是否与实际一致。

---

## 17. BEARISH + NORMAL — Iron Condor 入场研究（SPEC-007，2026-03-29）

**状态：✅ 已实施（IV HIGH + NEUTRAL 路径），❌ IV LOW 路径否决**

### 背景

BEARISH + NORMAL 占 8.3%（546 天 / 26 年），当前 100% REDUCE_WAIT。`SPEC-007_idle_scan.py` 扫描显示 IC symmetric δ0.16 在该环境 WR 83%、Sharpe 0.598、总 PnL $49,684。

### 实施结果（v1：IV HIGH + NEUTRAL 路径）

在 `iv_s == HIGH` 和 `iv_s == NEUTRAL` 的 BEARISH 分支新增 IC（带 VIX RISING + IVP 过滤）：

| 指标 | 结果 |
|------|------|
| IC 新增笔数 | +3（n: 21 → 24） |
| IC WR | 88% |
| Total PnL | $86,393（+$7,655） |
| Sharpe | 1.12（从 0.95） |

新增笔数远少于 Prototype 预期（53 笔），原因：**大多数 BEARISH+NORMAL 天落入 iv_s LOW（IVP < 40）**，v1 未覆盖该路径。

### IV LOW + BEARISH IC 尝试（v2）：否决

补充 iv_s LOW（IVP 15–40）+ BEARISH → IC 路径后：

| 指标 | v1 | v2 | 变化 |
|------|----|----|------|
| IC 新增笔数 | +3 | +18 | +15 笔 |
| Total PnL | $86,393 | $78,101 | **−$8,292** |
| Sharpe | 1.12 | 0.90 | **−0.22** |

15 笔新增 IC 均每笔亏损 **−$553**，净负贡献。**已回滚 v2，保留 v1 状态。**

### IV LOW + BEARISH IC 失效原因

- **IVP < 40 → 权利金极薄**：δ0.16 两腿合计信用不足以覆盖真实尾部风险
- **BEARISH 趋势 → put 实际突破概率 > 理论 PoP**：SPX 在 MA50 以下，继续下行动能存在，δ0.16 put 的安全边际被压缩
- Prototype 的 83% WR 是 IV HIGH/NEUTRAL/LOW 混合均值，IV HIGH/NEUTRAL 拉高了整体，掩盖了 IV LOW 子集的亏损

### 通用规则（新增）

**IC 禁区：iv_s LOW（IVP < 40）+ BEARISH 趋势。**

低保费 + 真实下行风险 = 负期望值，无论 IVP 下限设为 15 还是 20 均不能修复根本问题。后续所有 IC 类策略设计，BEARISH 趋势下必须要求 iv_s ≥ NEUTRAL（IVP ≥ 40）。

### 设计规则（强制）

> **IV LOW（IVP < 40）+ BEARISH 是 IC 禁区——低保费无法覆盖 BEARISH 趋势下的真实 put 突破风险。Prototype 的混合 WR 83% 对这个子集具有误导性。后续新 Spec 遇到 IC 类策略，IV LOW 路径直接排除。**

### Prototype 混合均值陷阱

本次研究揭示了一类常见的 prototype 分析偏差：**当 prototype 对某 regime 整体扫描时，若该 regime 内存在显著异质子集，聚合 WR/Sharpe 会掩盖坏子集。** 正确做法：按 iv_s 分层验证，不能只看整体均值。

---

## 18. 3 年回测 Sharpe 0.67 / WR < 50% — 根因分析（2026-03-29）

**背景**：26 年回测（2000–2026）Sharpe 1.24，但 3 年窗口（2022–2025）Sharpe 降至 0.67，WR < 50%。诊断目标：找出是哪个策略在哪个市场环境下造成系统性亏损。

### 确认：macro_warn 未阻断任何交易

`select_strategy()` 第 234 行：`macro_warn = not trend.above_200`

该标志被透传到每个 `Recommendation.macro_warning`，**但在整个 selector 逻辑中从未作为 guard 使用**——不存在"if macro_warn: return _reduce_wait(...)"的分支。SPX 在 200MA 以下时，所有 BPS、BPS_HV 依然正常开仓。

### H1（主因）：BPS/BPS_HV 在熊市宏观环境（SPX < 200MA）入场

**市场背景**：2022 年 1 月底 SPX 跌破 200MA，持续在 200MA 以下约 10 个月（2022-01 至 2022-10）。

**策略行为**：
- 2022 年期间多次短暂出现 HIGH_VOL + BULLISH（熊市反弹使 MA50 短暂穿越）或 NORMAL + BULLISH
- 这些"BULLISH"信号是 MA50 滞后产生的假信号：市场在短暂反弹后继续创新低
- BPS_HV short put（δ0.20）/ BPS short put（δ0.30）在随后的继续下跌中被打穿

**为什么 26 年回测不受影响**：26 年数据中大多数熊市是短暂的 V 型回调（持续 1–3 个月），SPX 未长期跌破 200MA。2022 年是持续 10 个月的结构性熊市，在 26 年数据中占比极低，被平均效应掩盖。

**潜在修复**：BPS / BPS_HV 增加 200MA 硬性封锁条件：
```
if not trend.above_200 → REDUCE_WAIT（不卖 put）
```
诊断 prototype（`SPEC-009_3yr_diagnosis.py`）将量化在 SPX < 200MA 时段的 BPS 亏损总额。

### H2（次因）：BCS_HV 被逆势反弹击穿

**市场背景**：2022 年有 4 次显著逆势反弹，幅度均在 10–15%：
- 3 月：+9.7%（Fed 加息预期短暂消化）
- 5–6 月：+7.0%（区间反弹）
- 7–8 月：+14.2%（通胀数据暂时降温）
- 10–11 月：+15.0%（熊市结束反弹）

**策略行为**：
- 反弹启动初期：VIX 从高位回落（5 日均线下降 >5%）→ 判断为 VIX 非 RISING
- selector 进入 HIGH_VOL + BEARISH + VIX 非 RISING → BCS_HV 开仓
- 随后反弹持续 3–4 周，short call（δ0.20 OTM）被快速推入价内
- 45 DTE 持仓还有大量 gamma 暴露 → 损失惨重

**潜在修复**：BCS_HV 增加短期动量过滤：
```
若 SPX 近 5 日涨幅 > +3%（逆势反弹正在进行中）→ REDUCE_WAIT
```
逻辑：如果市场已经快速反弹，说明 call 侧压力来临，此时卖 call 风险窗口已过。

### H3（小因）：IC 在制度过渡期被击穿

**市场背景**：HIGH_VOL→NORMAL 过渡期（VIX 从 25 降至 18–20）通常伴随市场剧烈波动。此时 IC δ0.16 两侧均脆弱。

**现有防护**：VIX RISING guard + IVP 20–50 过滤已覆盖大部分危险情形。这是三个假设中最小的因素。

### 诊断 Prototype

`backtest/prototype/SPEC-009_3yr_diagnosis.py`

五个分析模块：
1. 按年份 × 策略分解 WR / PnL → 定位亏损集中年份和策略
2. **H1 验证**：BPS/BPS_HV 在 SPX ≥ 200MA vs < 200MA 的 WR 对比
3. **H2 验证**：BCS_HV 按入场前 5 日 SPX 涨跌幅分层 WR 对比
4. 出场原因分布（stop_loss 比例是否在 3 年内异常高）
5. 26 年 vs 3 年汇总对比

### 诊断结果（SPEC-009_3yr_diagnosis.py 实测，2026-03-29）

```
3yr: 总交易 41 笔  Sharpe 0.14  WR 46.3%  Total PnL +$1,705
26yr: 总交易 230 笔  Sharpe 1.24  WR 68.7%  Total PnL +$90,410
```

**按年份 × 策略分解（关键行）：**

| 年份 | 策略 | n | WR | 均 PnL | 总 PnL |
|------|------|---|----|----|------|
| 2022 | BCS_HV | 10 | 70% | +$380 | +$3,801 |
| 2022 | Bull Call Diagonal | 3 | **0%** | -$904 | **-$2,713** |
| 2023 | Bull Call Diagonal | 5 | 40% | -$19 | -$95 |
| 2024 | Bull Call Diagonal | 5 | **20%** | +$63 | +$314 |
| 2025 | Bull Call Diagonal | 4 | 50% | +$93 | +$370 |

**出场原因分布（Bull Call Diagonal）：**
```
trend_flip: 13 笔 / 50pct_profit: 1 笔 / roll_21dte: 3 笔（共 17 笔）
```

### 真正根因：Bull Call Diagonal 在震荡市中的结构性弱点

**数据**：3 年 17 笔 Diagonal，WR = 5/17 = **29%**，占全部 41 笔的 **41%**。

**机制**：13/17 笔（76%）通过 `trend_flip` 出场——规则本身正确，问题在于 **2022–2025 市场结构**：
- **2022 年**：Diagonal 在 Jan/Feb BULLISH 环境入场，随即遭逢系统性熊市 → 0% WR
- **2023–2025 年**：牛市中频繁出现 3–7 天修正（银行危机、VIX 飙升、关税压力）→ trend_flip 触发 → 仓位被砍 → 市场快速恢复，但已在亏损中出场

**为何 26 年 WR 达 99%**：26 年大部分 Diagonal 入场在长期稳定上涨环境（2003–2007、2009–2019），trend_flip 触发后市场确实继续下行。2022–2025 是例外——trend_flip 反而变成了"在短期底部止损"的机制。

**H1（BPS < 200MA）：假设错误**。3 年内 SPX < 200MA 的 BPS 仅 1 笔且盈利，与预期相反。
**H2（BCS_HV 逆势反弹）：无法确认**。ret5d > 3% 子集只有 1 笔且盈利，样本过小。

### 改进方向：SPEC-009（待 prototype 验证）

Bull Call Diagonal 是主要问题（41% 交易量，29% WR），有三个候选方向：

| 方向 | 改动 | 逻辑 | 风险 |
|------|------|------|------|
| **A** | Diagonal 增加 `trend.above_200` 硬性前提 | 熊市宏观环境下 LOW_VOL + BULLISH 是假信号 | 减少 2023–2025 部分合理入场 |
| **B** | 移除 NORMAL + IV LOW + BULLISH → Diagonal，改 REDUCE_WAIT | IV LOW 环境 Diagonal 性价比差（long leg 贵、short leg 收入薄） | 减少 NORMAL 制度入场笔数 |
| **C** | trend_flip 观察期从 3 天延长到 5 天 | 过滤震荡市中的假翻转信号 | 延迟真实反转止损，可能扩大亏损 |

推荐：**方向 A + B 组合**，从入场两端收窄（macro 环境 + 制度），C 风险/收益比不明确，暂不动。

### Prototype 量化结果（SPEC-009_diagonal_filter.py，2026-03-29）

| 方向 | 3yr ΔSharpe | 3yr ΔWR | 3yr ΔPnL | 26yr ΔSharpe | 26yr ΔWR | 26yr ΔPnL |
|------|------------|---------|----------|--------------|---------|----------|
| A（200MA 前提） | +0.16 | +2.4pp | +$2,149 | +0.09 | +1.7pp | +$4,557 |
| **B（移除 NORMAL IV LOW）** | **+0.20** | **+3.7pp** | **+$2,186** | **+0.17** | **+4.0pp** | **-$3,357** |
| A+B | +0.20 | +3.7pp | +$2,186 | +0.17 | +3.8pp | -$3,567 |

**关键发现**：

1. **A+B ≈ B**（3yr 完全相同）：A 移除的 2 笔是 B 移除的 7 笔的子集，A 对 3yr 无增量贡献。

2. **方向 B 最优**（Sharpe 改善最大），但 26yr PnL 损失 $3,357——NORMAL+IV LOW Diagonal 在历史上是净正贡献，但在 2022–2025 年系统性失效（7 笔，WR=29%，avg=-$312）。

3. **Diagonal 26yr WR = 48.2%（旧数据勘误）**：§1 记录的 97%/99.3% WR 是 `_entry_value` Bug 修复前的错误数据（见 §13）。Diagonal 从来就不是高胜率策略，而是低 WR + 不对称收益（小量大赢覆盖多量小输）。趋势翻转止损规则限制了亏损幅度，保证期望值为正，但 WR 本质上偏低。

4. **即使执行 B，剩余 LOW_VOL Diagonal（n=10）WR 仍为 30%**。Diagonal 的低 WR 问题是结构性的，不能被单一入场过滤完全解决。

### 立项决策

**推荐立项 SPEC-009，方向 B**：

- 移除 NORMAL + IV LOW + BULLISH → Diagonal，改 REDUCE_WAIT
- 在 26yr 小幅让步 PnL（-$3,357）换取 Sharpe +0.17 和 WR +4pp
- 可选同时加入方向 A（200MA 前提），增量效果微小但无副作用

**不推荐进一步追求 WR > 50%**：剩余 Diagonal（LOW_VOL + BULLISH 路径）WR=30% 是结构性低 WR，正期望值来自不对称收益而非胜率。追求 WR > 50% 的目标对 Diagonal 类策略不适用，应改用 Sharpe 作为主要优化目标。

---

## 19. 零售 PM 账户 BP 利用率业界实践（网络调研，2026-03-29）

**状态：📋 参考资料，已用于 SPEC-013 / SPEC-014 参数 calibration**

### 研究背景

原引擎用 `risk_pct=2%`（premium 风险）定仓，与 PM 账户实际约束（BP 消耗）脱节。需要确认：
1. 真实零售 PM 账户的单笔 BP 占用标准是多少？
2. 总账户 BP 利用率应控制在什么范围？
3. 是否存在"同一时间只有 1 个仓位"的约束？（回答：**不存在**）
4. 增大单笔 size vs. 开多个仓位，哪种更优？

---

### 一、PM 账户机制（OCC TIMS 模型）

PM（Portfolio Margin）使用 OCC TIMS（Theoretical Intermarket Margin System）对组合整体进行压力测试，而非逐笔加总。核心特点：

- **Risk-based margin**：BPR = 最大压力场景下的潜在亏损（非固定公式）
- **BPR 非线性扩张**：VIX 从 20 升至 40 时，同一 delta 的 short put BPR 可涨 2–4×（gamma 和 vega 暴露同步扩大）
- **Cross-margin netting**：多个相关性低或相反方向的仓位之间，组合 BPR < 各仓位 BPR 之和。实践经验：同账户内 4–6 个 SPX defined-risk 仓位，总 BPR 约为独立加总的 60–80%（即 netting 节省 20–40%）
- **仓位数量无硬性上限**：PM 账户对并发仓位数量没有规则限制，唯一约束是总 BPR ≤ 账户净值（+ margin cushion）

---

### 二、单笔仓位 BP 标准（tastytrade 及社区实践）

**tastytrade 官方方法论**（来源：tastytrade 研究报告、Liz & Jenny 节目、TastyLive Research）：

| 仓位类型 | 建议单笔 BP 占用 | 说明 |
|---------|----------------|------|
| Defined-risk spread（BPS、BCS、IC） | **3–7% 账户净值** | 最常引用的标准 |
| Undefined-risk（naked short put/call） | 1–5%（视 delta） | 风险放大，通常更保守 |
| Diagonal / Calendar | 2–5% | Long leg 降低 BPR |

**社区实践（r/options、TastyTrade community、EliteTrader PM 版块）**：

- 多数全职/半全职零售交易者将**单笔 SPX defined-risk 仓位设为账户的 3–8%**
- 常见原则："never put more than 10% into any single trade"
- 非全职（每天 1 小时）交易者倾向更保守的 3–5%，因为无法盘中密切监控

**SPEC-013 calibration**：取 tastytrade 标准中间偏保守值：
- LOW_VOL / NORMAL：5%（单笔）
- HIGH_VOL：3.5%（VIX 升高时 BPR 非线性扩张，留出缓冲）

---

### 三、总 BP 利用率目标

**tastytrade 建议**（来源：Tom Sosnoff 访谈、tastytrade research "Portfolio Margin: The Basics"）：

| 市场环境 | 建议总利用率 | 说明 |
|---------|-----------|------|
| 低波动（VIX < 15） | 25–35% | 权利金薄，每笔 BPR 较小，但机会也少 |
| 正常（VIX 15–22） | 35–50% | 基准；大多数时间目标 |
| 高波动（VIX 22–35） | 40–60%（上限） | 权利金丰厚，但个别仓位 BPR 飙升 |
| 极端（VIX > 35） | 0–20% | 保留现金，等待 BPR 回落 |

**社区实践共识**：

- "Stay between 30–50% utilized during normal markets; go up to 60% in high IV but only if you're actively watching"
- "In PM, 25% is comfortable, 50% is fully deployed, anything over 60% is aggressive"
- 非全职交易者普遍**将目标设为 25–40%**，在高波动期适度提升但不超过 50%

**SPEC-014 calibration**：
- LOW_VOL ceiling = 25%（保守）
- NORMAL ceiling = 35%（基准）
- HIGH_VOL ceiling = 50%（权利金溢价丰厚补偿了每笔风险上升）

---

### 四、增大单笔 size vs. 开多个仓位

这是本次研究的核心问题，来自 PM"不存在1个仓位上限"的业务现实。

**Path X：增大单笔 size（原单仓架构下）**

| 优点 | 缺点 |
|------|------|
| 实现简单 | 集中风险：单笔仓位遭遇极端事件→账户受损更大 |
| 减少开/平仓次数（节省佣金、滑点） | BPR 线性增加，无 netting 效益 |
| 适合盘中无法监控的场景 | 无法同时利用不同 regime 下的机会 |

**Path Y：多个小仓位并行（SPEC-014 实现的架构）**

| 优点 | 缺点 |
|------|------|
| Cross-margin netting 降低总 BPR 20–40% | 开/平仓频率增加 |
| 风险分散（单笔极端亏损影响减小）| 需要更主动的仓位管理 |
| 可同时持有不同方向策略（BPS + BCS = 合成 IC，但 BPR 更低）| 回测引擎复杂度上升 |
| 信号利用率提高（持仓期不再 100% 屏蔽新信号）| |

**社区调研结论**（非全职 PM 交易者，r/options PM 版块，TastyTrade 社区）：

> "I run 5–8 positions at a time, each around 3–5% BP. Total is usually 25–40%. Having multiple positions is what makes PM worth it — the netting is free money compared to Reg-T."

> "Single large position is fine in Reg-T. In PM you're paying for the flexibility to run correlation — use it."

> "I never put more than 5% in any single SPX spread, but I have 4–6 of them running at once. If I concentrated into one big IC, my BPR would be higher, not lower."

**结论**：**多个小仓位（Path Y）在 PM 账户中在 BP 效率和风险分散上均优于单个大仓位（Path X）**。增大单笔 size 是在 PM 账户中放弃了 netting 优势，属于"Reg-T 思维套用到 PM"的常见误区。

---

### 五、对本系统的含义

| 维度 | 原实现 | SPEC-013+014 后 |
|------|-------|----------------|
| 单笔 BP 占用 | 2–3%（premium risk 2%，实测） | 5% / 3.5%（regime-aware） |
| 总 BP 利用率 | ≤5%（单仓） | 25–50%（多仓 + ceiling） |
| 架构 | 单仓（1-position-at-a-time） | 多仓并行（positions: list[Position]） |
| PM netting | 未体现 | 未显式建模，但多仓架构是前提 |

PM netting 建模（显式降低并行仓位总 BPR）是后续可扩展的改进方向，当前 SPEC-014 未实现，保守地以各仓位 bp_target 独立加总作为 ceiling 检查基准。

---

## 20. ROM（Return on Margin）指标实现（SPEC-012，2026-03-29）

**状态：✅ 已实施**

### 背景

原回测输出只有 P&L 绝对值（`exit_pnl`），无法比较不同 BP 占用的策略效率。PM 账户的实际绩效衡量标准是 **ROM（Return on Margin）**：

```
ROM（年化）= exit_pnl / total_bp × (365 / hold_days)
```

ROM 规范化了保证金占用，使得高 BP 策略（Iron Condor 宽价差）与低 BP 策略（Bull Put Spread）之间可横向比较。

### 实施内容

- **`Trade` dataclass**：新增 `rom_annualized` property（`backtest/engine.py`）
  - 分子：`exit_pnl`（USD）
  - 分母：`total_bp`（USD，= contracts × bp_per_contract）
  - 年化：`× 365 / hold_days`（`hold_days = max(dte_at_entry - dte_at_exit, 1)`）
  - 防护：`total_bp <= 0` 时返回 0.0
- **`compute_metrics`**：`by_strategy` 字典新增 `avg_rom` 和 `median_rom` 字段

### 设计决策

- ROM 使用 `total_bp`（实际 BP 消耗）而非 `account_size`，因此是**相对保证金效率**，不受账户大小影响
- `median_rom` 补充 `avg_rom`：ROM 分布常有偏斜（极端赢家拉高均值），中位数更稳健
- `hold_days` 下限 1 以防除零（DTE=0 强平情形）

---

## 21. BP 利用率驱动的仓位定量（SPEC-013，2026-03-29）

**状态：✅ 已实施**

### 问题：原 premium-risk 定量的系统性偏差

原实现：

```python
contracts = account_size * risk_pct / opt_prem   # risk_pct = 2%
```

这是以**权利金风险（2% 账户）**控制合约数。但对于 Iron Condor（信用 ~45pt，BP ~$5,000/contract）：
- 合约数 = 150,000 × 0.02 / (45×100) = 0.67 个合约
- 实际 BP 占用 = 0.67 × $5,000 = **$3,350 ≈ 2.2% 账户**

而 tastytrade PM 账户实际实践中，单笔 BPS/IC 通常消耗 **5–7% 账户 BP**——原引擎系统性低估了仓位规模约 2–3×。

### 新公式

```python
contracts = account_size * bp_target / bp_per_contract
```

bp_target 代表**该仓位应消耗的账户 BP 比例**，bp_per_contract 是 BS 定价+PM 规则算出的单合约保证金。

### 参数设定

| Regime | bp_target | 依据 |
|--------|-----------|------|
| LOW_VOL | 5% | 薄溢价环境，保守 |
| NORMAL | 5% | 基准 |
| HIGH_VOL | 3.5% | 个别仓位风险较高，保留缓冲 |

calibration 参考 tastytrade 零售 PM 标准：单笔 defined-risk 仓位 ≤ 5–7%。

### 新基线（SPEC-013 后，2026-03-29）

| 窗口 | Trades | WR | Sharpe | Total PnL | Max DD |
|------|-------|----|----|---------|--------|
| 3yr (2022-01-01) | 47 | 61.7% | 0.93 | +$16,094 | -$4,774 |
| 1yr (2024-01-01) | 23 | 60.9% | 1.48 | +$13,952 | -$4,213 |

BP 利用率验证：NORMAL 策略 bp%=5.0%，HIGH_VOL 策略 bp%=3.5%——与目标完全一致。

**3yr ROM by strategy**：

| 策略 | n | avg_rom |
|------|---|---------|
| Iron Condor HV | 6 | +2.98 |
| Bear Call Spread HV | 10 | +1.13 |
| Bull Call Diagonal | 17 | -0.147（2022–2023 熊市拖拽） |
| Bull Put Spread HV | 3 | -6.60（样本过小，不具代表性） |

**1yr（2024）Diagonal avg_rom = +1.36**：与 3yr 对比，2022–2023 熊市/加息周期是 Diagonal 亏损的宏观根因，2024 牛市下 Diagonal 恢复正常。

### 关于 size_mult 的地位变化

`size_mult`（HIGH_VOL 原为 0.5）被 `bp_target_high_vol=0.035` 取代：新公式直接用 bp_target 控制 BP 占用，不再需要乘以缩减系数。`size_mult` 字段保留在 `Position` dataclass 中但不再参与合约数计算。

---

## 22. 多仓并行引擎架构（SPEC-014，2026-03-29）

**状态：✅ 已实施**

### 背景

SPEC-013 将单笔仓位 BP 占用标准化（5%）后，账户总 BP 利用率在任意时刻只有 5%（即只有 1 个仓位）。真实 PM 账户的业界实践是：

- 同时持有 3–6 个仓位
- 总 BP 利用率 25–50%
- 多个小仓位比单个大仓位更高效：PM cross-margin netting 可降低总 BPR 20–40%
- 不存在"同一时间只能有 1 个交易"的约束

原单仓设计会在仓位持有期（30–45 天）内完全屏蔽所有新信号，导致大量高质量机会被丢弃。

### 架构变更

**核心变更**：`position: Optional[Position] = None` → `positions: list[Position] = []`

**入场条件**（替换 `position is None`）：

```python
_used_bp = sum(p.bp_target for p in positions)
_new_bp_target = params.bp_target_for_regime(regime)
_ceiling = params.bp_ceiling_for_regime(regime)
_already_open = any(p.strategy == rec.strategy for p in positions)

if (rec.strategy != REDUCE_WAIT
        and not _already_open
        and _used_bp + _new_bp_target <= _ceiling):
    # 开新仓
```

两个守护：
1. **总 BP ceiling**：防止整体风险暴露超限
2. **同策略 dedup**：相同 StrategyName 不重叠（防止信号连续发出时堆叠）

**BP Ceiling 参数**：

| Regime | bp_ceiling | 对应约几个并行仓 | 业界参考 |
|--------|-----------|----------------|---------|
| LOW_VOL | 25% | ~5 × 5% | 保守端 |
| NORMAL | 35% | ~7 × 5% | 中间值 |
| HIGH_VOL | 50% | ~14 × 3.5%（实际受 dedup 限制） | 高 IV 溢价丰厚 |

实践中受 dedup 约束，并发仓位一般 3–5 个。

### 验证结果

- 1yr (2024) trades：单仓 23 → 多仓 **30**（+30%），并行仓位使更多信号得以入场
- BP ceiling 守护：任意时点总 BP 未超过 ceiling（违规=0）
- dedup 守护：同 StrategyName 无重叠（违规=0）
- 回测结束未平仓仓位正确以 `end_of_backtest` 强平

### 对 Sharpe / compute_metrics 的影响

`compute_metrics` 无需修改。Sharpe 基于逐笔交易 P&L 计算（trade-level Sharpe），多仓并行下继续有效。已知近似：多个仓位同期开仓时，equity curve 是离散的交易序列叠加，非真实日收益率序列——这是 Precision B 引擎的已知近似，不影响策略比较的相对有效性。


---

## 23. Vol Persistence Risk Throttle（SPEC-015，2026-03-30）

### 研究问题

HIGH_VOL 入场过滤器覆盖的是**入场时点**的危险，但不建模 HIGH_VOL 会持续多久。多仓架构（SPEC-014）下，若 HIGH_VOL spell 持续 > 20 天（持仓窗口），会产生叠加 short-gamma 暴露。

### 数据来源（26yr，1990–2026，263 个 spell）

| 分位数 | 持续时长 |
|--------|---------|
| P50（中位数） | 4 天 |
| P75 | 10 天 |
| P90 | 29 天 |
| > 30 天（sticky） | 10%（25 笔） |
| > 60 天（极端） | 5%（13 笔） |

**90% 的 spell 在 30 天内结束**，大部分 HIGH_VOL 入场是短暂波动尖峰。

### 反直觉发现

VIX RISING（快速尖峰）型入场的 spell 反而**更短暂**；sticky spell 特征是 VIX 在中等水平（26–28）缓慢盘整，slope 接近 0。现有 VIX RISING 过滤器实际上阻止的是短暂 spell，而 sticky spell 在入场时信号上难以识别。

| 类型 | n | entry_vix 均 | slope 均 | peak_vix 均 |
|------|---|------------|---------|------------|
| Sticky（>30d） | 25 | 26.9 | −0.04 | 33.4 |
| Short（≤30d） | 238 | 24.8 | +0.45 | 27.0 |

### 解决方案：Spell Age Throttle

- `spell_age_cap = 30`：spell 超过 30 天（P90 分位）后，不再开新的 HIGH_VOL 策略
- `max_trades_per_spell = 2`：同一 spell 内最多开 2 笔 HIGH_VOL 仓位

### 验证结果

- 2022–2026 回测：throttle 阻断 6 笔（56 vs 62 trades），3yr Sharpe 从 0.90→0.97
- 2022 年的两段 sticky spell（99d + 88d）是 3yr vs 26yr Sharpe 差异（0.93 vs 1.54）的主因时段

---

## 24. Portfolio Exposure Aggregation — Greek-Aware Dedup（SPEC-017，2026-03-30）

### 研究问题

SPEC-014 的 StrategyName dedup 阻止同名重复，但 BPS_HV + BCS_HV 是不同名称、共享相同 Greek 签名的危险组合，合成了比 IC_HV 更高的 short-gamma 暴露。

### Greek 签名分类

| 策略 | ShortGamma | ShortVega | Delta |
|------|-----------|-----------|-------|
| Bull Put Spread (HV) | ✓ | ✓ | bull |
| Bear Call Spread HV | ✓ | ✓ | bear |
| Iron Condor (HV) | ✓ | ✓ | neut |
| Bull Call Diagonal | — | LONG | bull |

### 关键数据（26yr，177 对并发 short_gamma 组合）

| 组合 | n | avg_combined PnL | both_loss 率 |
|------|---|-----------------|-------------|
| BPS_HV + BCS_HV | 25 | +$28 | 40% |
| BCS_HV + BPS_HV | 19 | −$364 | 53% |
| IC_HV + BPS_HV | 22 | +$1,085 | 14% |
| IC_HV + BCS_HV | 30 | +$361 | 28% |

BPS_HV + BCS_HV 合计 44 对，双双亏损率 40–53%（合成 Iron Condor 但 short_gamma 量是 IC 的 2 倍）。IC + BPS_HV 组合相对安全（both_loss 14%）。

### 解决方案

- **Synthetic IC block**：已有 BPS_HV 时阻断 BCS_HV 入场（反之亦然）
- **`max_short_gamma_positions = 3`**：同时持有 short-gamma 仓位上限
- 当前 engine 时序（先平仓再开仓）下 BPS_HV+BCS_HV 不会真实并发，但规则将约束显式化，为未来更复杂的多仓逻辑保留保护网

---

## 25. Evaluation Metrics Reform — Tail Stats（SPEC-018，2026-03-30）

### 研究问题

现有 `compute_metrics` 仅输出 Sharpe / WR / TotalPnL，无法揭示 short-vol 系统的结构性风险特征（尾部分布、Regime 弱点、drawdown 调整收益）。

### 关键数据（Prototype，2000–2026 vs 2022–2026）

| 指标 | 26yr | 3yr | 解读 |
|------|------|-----|------|
| Calmar | **26.23** | **4.21** | 3yr 退化 6× |
| CVaR 5% | $−2,591 | $−2,564 | 尾部金额一致 |
| Skewness | −0.62 | −0.08 | 负偏；3yr 趋近对称 |
| Kurtosis | +2.85 | +0.32 | 厚尾；3yr 近正态 |
| Payoff ratio | 0.92 | 1.06 | avg_loss ≥ avg_win（短 vol 特征）|
| HIGH_VOL Sharpe | 1.83 | **0.60** | 3yr HV 策略断崖 |

### 策略级尾部对比（26yr）

| 策略 | Skewness | CVaR 5% | Payoff ratio | WR |
|------|---------|---------|-------------|----|
| Bull Call Diagonal | −0.02 | $−1,963 | **1.81** | 63% |
| Bull Put Spread HV | −2.09 | $−2,108 | 0.67 | 80% |
| Bear Call Spread HV | −2.70 | **$−1,639** | 0.67 | 80% |
| Iron Condor | **−2.66** | **$−5,045** | 0.43 | 84% |
| Iron Condor HV | −2.05 | $−2,151 | 0.64 | 84% |

**Iron Condor 是结构性最危险的策略**：负偏最严重（−2.66）、CVaR 5% 最大（$−5,045）、Payoff ratio 最低（0.43）。**Bull Call Diagonal 是分布最健康的策略**：近对称（−0.02），Payoff 1.81（赢多输少）。

### 结论

- 负偏 + payoff < 1 是所有 short-vol premium 系统的结构性特征，不是缺陷
- Calmar 比 Sharpe 更适合评估 short-vol 系统（直接衡量 drawdown 调整后收益）
- 3yr HIGH_VOL Sharpe 骤降（1.83→0.60）印证了 SPEC-015 spell throttle 的必要性

---

## 26. Trend Signal × Strategy Effectiveness — Lag & Gate Analysis（SPEC-019，2026-03-30）

### 研究问题

量化 MA50 趋势信号的实际贡献：作为 Entry Gate 和 Exit Trigger 哪个更有价值？MA50 vs MA20 的滞后代价是否显著？

### 关键数据（Prototype，26yr 386 笔）

**入场趋势分布**：BULLISH 55.2%，NEUTRAL 22.5%，BEARISH 22.3%；所有 386 笔均为 100% aligned（无反趋势入场）。

**BPS 家族 MA Gap 量级 vs 性能**：

| MA50 Gap 区间 | n | WR | AvgPnL |
|--------------|---|-----|--------|
| 1–3% | 44 | 75% | $+440 |
| 3–6% | 39 | **87%** | $+402 |
| ≥6%（过度延伸）| 19 | **68%** | **$+158** |

**MA50 vs MA20 滞后性**：MA50 翻多时 MA20 平均领先仅 **1.2 天**（中位数 0 天）。

**Diagonal 损失解剖**：41 笔亏损中，32 笔（**78%**）由 trend_flip EXIT 触发，仅 9 笔是 roll_21dte。

### 结论

1. **趋势信号是纯 Hard Gate**：全部入场已对齐，无反趋势基准；无法做 A/B 对比
2. **MA50 ≥6% 过度延伸时 BPS 表现退化**（WR 68%，最低分桶）——市场过热风险
3. **Diagonal 中 trend_flip EXIT 是趋势信号最重要的贡献**（78% 亏损由此捕获），EXIT trigger 价值远高于 ENTRY gate
4. **MA50 vs MA20 滞后性差异可忽略**（1.2 天均值）——不需要切换信号

---

## 27. P&L Attribution — Return Driver Decomposition（SPEC-020，2026-03-30）

### 研究问题

系统 P&L 的实际来源是 Theta / Vol premium 还是方向性 Alpha？验证 Warning A："不要把系统重新框架为方向性趋势跟随引擎"。

### Exit Reason 分布（26yr，386 笔，Total PnL $+192,234）

| Exit Reason | n | WR | TotalPnL | 贡献% |
|------------|---|-----|----------|-------|
| 50pct_profit | 159 | 100% | $+127,783 | **+66.5%** |
| roll_21dte | 172 | 69% | $+118,062 | **+61.4%** |
| roll_up | 12 | 100% | $+8,470 | +4.4% |
| stop_loss | 8 | 0% | $−24,293 | −12.6% |
| **trend_flip** | **34** | **6%** | **$−38,046** | **−19.8%** |

### PnL-SPX / PnL-VIX 相关系数

| 策略 | PnL-SPX | PnL-VIX | 主导驱动 |
|------|---------|---------|---------|
| Bull Call Diagonal | **+0.929** | −0.490 | 方向性 Delta |
| Bull Put Spread | **+0.973** | −0.897 | 双重驱动 |
| Iron Condor | +0.808 | **−0.914** | Vol compression |
| Iron Condor HV | +0.771 | **−0.861** | Vol compression |
| Bear Call Spread HV | −0.778 | +0.404 | 反向 Delta |

### 结论

1. **系统本质是 timed short-vol engine**：50pct_profit + roll_21dte = 86% 笔数，主要驱动是 Theta + vol premium
2. **trend_flip 是最大单一 PnL 拖累**（−19.8%，$−38,046）——是 Diagonal 结构的"保险成本"，不是 bug
3. **BCS_HV 是最"纯"的 Premium 策略**：SPX −5% 到 +3% 范围内 WR=100%，失败模式仅限于 SPX ≥+5% 急涨
4. **IC/IC_HV 的敌人是 VIX 上升，不是方向**：VIX-corr = −0.86 到 −0.91；VIX ≥+5pts 时 WR=23%
5. **Warning A 得到量化验证**：12.2% 的信用策略在逆向方向时仍然盈利（short-vol 结构缓冲）

---

## 28. Filter Complexity Penalty Protocol（SPEC-021，2026-03-30）

### 研究问题

落实 Warning B："不要假设更多 filter 总能改善结果"。量化 filter 叠加的边际价值，建立新 filter 评估框架。

### 关键实证

| 配置 | n | WR | AvgPnL |
|------|---|-----|--------|
| 全部 BPS 家族（无额外 filter） | 102 | **78%** | **$+373** |
| 理想组合（VIX 18–26 + MA gap 1–5%）| 46 | 76% | $+346 |

叠加两个额外 filter：WR −2pp，AvgPnL −$27，样本量减半。

### 现有 Active Filter 层（7 层）

1. VIX regime 分类（4 层）
2. IV signal（HIGH/NEUTRAL/LOW）
3. Trend signal（BULLISH/NEUTRAL/BEARISH）
4. VIX backwardation
5. EXTREME_VOL hard stop（VIX ≥ 35）
6. trend_flip EXIT（Diagonal 专属）
7. Vol spell age throttle（SPEC-015）

对于年均 15 笔的交易频率，7 层 filter 已达合理上限，进一步细分会使每个 bucket < 10 笔。

### Filter 复杂度管理协议

**Protocol 1（新 filter 最低门槛）**：过滤后 n ≥ 50，26yr/3yr 方向一致，有明确理论机制，不减少年均交易量 > 30%。

**Protocol 2（Ablation Study 必须）**：新 filter 需对比 Baseline vs With-filter；若 Sharpe 提升 < 5% 且年交易量减少 > 20% → 拒绝。

**Protocol 3（filter 清理标准）**：被过滤交易事后 WR > 70% 可考虑移除；边际贡献 < 2% 总 PnL 可移除。

**Protocol 4（禁止在同一数据上多次优化）**：建议 2000–2020 in-sample 设计，2021–2026 out-of-sample 验证。

### 结论

有理论机制的 filter（backwardation、EXTREME_VOL、trend_flip EXIT）历史上均有效。纯数据发现的组合 filter（VIX 18–26 + MA gap 1–5%）无改善。有效 filter 的标志：清晰的期权/市场结构机制。

---

## 29. Sharpe Robustness Test — Temporal Stability & CI（SPEC-022，2026-03-30）

### 研究问题

量化 Sharpe 的统计不确定性，落实 Warning C："不要过度解读 Sharpe"。

### 关键数据（Bootstrap 5,000 次，26yr 386 笔）

| 窗口 | Sharpe | Bootstrap 95% CI | CI 宽度 |
|------|--------|-----------------|---------|
| 26yr | 1.54 | [1.18, 1.95] | 0.76 |
| 3yr | 1.15 | [0.39, 1.96] | **1.56** |

3yr Sharpe 的 95% CI 宽度 1.56——几乎无法从点估计得出任何可靠结论。

### 年度 Sharpe 分布

| 统计量 | 值 |
|-------|---|
| 均值 | +2.13 |
| 最低（2004） | −0.92 |
| 最高（2021） | +7.13 |
| 负值年份 | 5/27（18.5%）|
| Sharpe < 0.5 年份 | 6/27（22%）|

### 策略级稳定性（26yr vs 3yr Sharpe）

| 策略 | 26yr | 3yr | 变化 | 稳定性 |
|------|------|-----|-----|-------|
| Bull Call Diagonal | 1.69 | 1.75 | +0.06 | 最稳 |
| Iron Condor | 1.08 | 3.42 | +2.34 | 极不稳（3yr n=10）|
| Bear Call Spread HV | 1.54 | 0.58 | −0.97 | 不稳 |
| Bull Put Spread | 2.50 | 0.57 | −1.93 | 严重退化 |
| Iron Condor HV | 2.22 | 0.55 | −1.67 | 严重退化 |

### Sharpe 的正确使用指南

**可以用**：策略间相对排名（同窗口）、系统健康检查（Sharpe 突然从 >1.5 降到 <0.5）、粗粒度决策。

**不应该用**：3yr 以下窗口的策略决策（CI 太宽）、比较差异 < 0.5 的两个策略（统计噪声范围内）。

**推荐补充指标**（优先级高于单独 Sharpe）：正值年份比例（22/27 = 81%）、Calmar ratio、最长连续亏损年数、负 Sharpe 的历史环境。

### 结论

- Bull Call Diagonal 是最稳健的策略（Sharpe 几乎不随窗口变化）
- BPS / IC_HV 的 26yr 高 Sharpe 是历史特定时期（低波动牛市）的产物，不是稳健的结构性优势
- 3yr Sharpe CI 极宽，基于 3yr 的比较在统计上几乎无意义

---

## 30. Realism Haircut & Strategy Re-ranking（SPEC-016，2026-03-30）

### 研究问题

量化 Precision B 回测的三类系统性乐观偏差，在调整后的 ROM 下重新为策略排名。

### 三类偏差

| 偏差类型 | 对 short-vega 策略 | 对 Diagonal |
|---------|-------------------|------------|
| IV Bias（VIX 同向联动）| 高估 10–12% | 低估 10%（反向）|
| Bid-Ask Slippage | 每腿 $40–75 | 每腿 $60 |
| 资金占用成本（5% p.a.）| 小（短持）| 较大（长持）|

### Raw vs Adjusted ROM

| 策略 | n | Raw ROM | Adj ROM | Haircut | Raw排名 | Adj排名 |
|------|---|---------|---------|---------|--------|--------|
| Bull Put Spread | 23 | +3.476 | +2.433 | 30% | #1 | **#1** |
| Iron Condor HV | 45 | +2.949 | +0.847 | 71% | #2 | **#2** |
| Bull Put Spread HV | 79 | +2.681 | +0.747 | 72% | #3 | **#3** |
| **Bull Call Diagonal** | **111** | **+0.770** | **+0.725** | **6%** | #6 | **#4 ↑+2** |
| Bear Call Spread HV | 79 | +1.206 | +0.313 | 74% | #4 | **#5 ↓** |
| Iron Condor | 49 | +1.020 | +0.269 | 74% | #5 | **#6 ↓** |

### 关键发现

1. **Bull Put Spread（Normal）是最稳健的策略**：Haircut 仅 30%，Adj ROM=+2.433 仍为最高
2. **Bull Call Diagonal 是回测可信度最高的策略**：Haircut 仅 6%（两个效应相反相消），Raw ROM ≈ Adj ROM
3. **HV 信用策略 haircut 达 70–74%**：主因是 bid-ask 摩擦（IC_HV: 4腿×$60=$240/trade）
4. **IC（Normal）的 adj_rom 几乎为零**（$130/trade 净收益），战略价值主要是"占用 regime 空隙"

### 决策影响

| 决策领域 | 原判断 | 调整后 |
|---------|-------|-------|
| 研究重点 | IC_HV >> Diagonal | IC_HV ≈ Diagonal（Diagonal 值得更多研究）|
| 参数优化 | 倾向 HV 策略 | BPS Normal 是最值得细化的策略 |
| 多仓优先级 | 多开 IC_HV | 限制 IC 类仓位，优先 BPS/BCS |
| 止损阈值 | 基于 raw ROM | 应 ≥ 一次开平仓的双边 bid-ask |

---

## 31. Concentrated Exposure & Stress Period Analysis（SPEC-023，2026-03-30）

### 研究问题

量化系统在历史极端事件中的实际表现，评估集中风险暴露，综合 SPEC-015/016/017 的风险缓解效果。

### 历史压力事件 P&L

| 事件 | n | TotalPnL | WR | MaxSingleLoss |
|------|---|---------|-----|--------------|
| 2000-03 dot-com 顶部 | 19 | $+8,402 | 89% | $−997 |
| 2008-09 雷曼崩盘 | 1 | **$−5,069** | 0% | $−5,069 |
| 2015-08 中国崩盘 | 5 | $−3,378 | 60% | $−4,852 |
| 2020-02 COVID 崩盘 | 4 | **$+1,767** | 75% | $−511 |
| 2022 Fed 加息熊市 | 29 | $−424 | 66% | $−2,461 |

### 集中暴露分析

| 并发 SG 仓位数 | 历史天数 | 占比 |
|-------------|------|------|
| 1 | 3,267 | 45.5% |
| 2 | 931 | 13.0% |
| 3 | 376 | 5.2% |
| **4（超过 SPEC-017 上限）** | **30** | **0.4%** |

### Realism 调整综合结果

| 指标 | Raw | Adjusted |
|-----|-----|---------|
| 26yr Total PnL | $+192,234 | **$+94,070** |
| 加权平均 haircut | — | 51.1% |
| Sharpe（估算）| 1.54 | **~0.99** |

**Sharpe ~1.0 是"有意义的正期望"**——系统不是靠 Precision B 乐观假设支撑，而是有真实 alpha。

### 最恶劣连续亏损序列（2015 年）

| 日期 | 策略 | PnL |
|------|------|-----|
| 2015-07-16 | Bull Call Diagonal | $−1,359 |
| 2015-08-13 | Iron Condor | $−4,852 |
| 合计 | — | **$−6,210** |

背景：中国股市崩盘 + VIX 急升，同时触发 Diagonal trend_flip + IC put side 击穿。

### 风险画像与保护缺口

| 风险类型 | 严重程度 | 已有保护 | 缺口 |
|---------|---------|---------|-----|
| VIX=80 灾难级事件 | 极高 | extreme_vix hard stop ✅ | 无 |
| VIX 25→50 快速中程急升 | **高（实际已发生）** | backwardation（部分）| 已有仓位退出速度 |
| Sticky spell 重复入场 | 中 | SPEC-015 ✅ | 已解决 |
| BPS_HV + BCS_HV 合成 IC | 中 | SPEC-017 ✅ | 已解决 |
| Realism haircut（50%）| 结构性 | SPEC-016（研究）| 无法消除，定期更新估算 |

### 结论

1. **2008 年是唯一有单笔灾难性损失的事件（$−5,069）**，但占 26yr 总 PnL 的 2.6%，extreme_vix 保护有效
2. **COVID 2020 = 正 PnL**（$+1,767）：hard stop + 已有仓位的提前 exit 验证了保护规则有效性
3. **最大实际尾部风险是 VIX 25→50 的中程急升**，而非 VIX=80 的极端事件（后者已被 hard stop 阻挡）
4. **历史上确实出现 4 个并发 SG 仓位**（30 天），支持 SPEC-017 设置 max=3 的必要性
5. **50% haircut 后 Sharpe ~0.99**：系统有真实 alpha，不依赖回测假设

---

## 32. Daily Portfolio Metrics — 从 Trade-Level 到 Daily Portfolio View（SPEC-024, 2026-04-01）

**Status：已实施**

### 研究问题

Sharpe 和 Calmar 之前基于 trade-level 计算：每笔交易作为独立观测单元，用其 PnL 构建收益序列。在单仓串行运行时，这是合理近似；但在多仓并行时，trade-level metrics 会系统性低估相关性、高估多样化效果。

具体后果：

- 两笔重叠持仓同时在 VIX spike 期间亏损，trade-level 会把它计算为"两次独立事件"；但实际它们是同一个市场日、同一次冲击。
- 用 trade-level Sharpe 作为下一轮 signal 设计的驱动指标，会产生系统性误判。
- 优化目标与真实组合风险脱节。

### 核心发现

1. 多仓并行时，真实组合波动来自**每日净值变化**，而不是每笔交易独立结算。重叠仓位期间的相关性决定真实 drawdown 深度。
2. 所有组合层风险控制（shock budget、overlay、资金利用率）都需要 **daily book view**。入场守护链（SPEC-025/026）不能基于 trade-level 序列做实时判断——系统需要知道"今天的 portfolio 在各场景下会损失多少"。
3. Trade-level Sharpe 作为下一轮设计的驱动指标会产生系统性误判。**Daily portfolio Sharpe**（基于实际净值日度变化）才是与真实资本消耗对齐的度量。

### 实现方案

`PortfolioTracker`（`backtest/portfolio.py`）：

#### `DailyPortfolioRow`（17 个字段）

| 字段 | 说明 |
|---|---|
| `date` | 日期 |
| `start_equity` | 日初净值 |
| `end_equity` | 日末净值 |
| `daily_return_gross` | 毛收益率（不含 haircut） |
| `daily_return_net` | 净收益率（含 haircut） |
| `realized_pnl` | 当日结算的已实现 PnL |
| `unrealized_pnl_delta` | unrealized PnL 较前一日变化 |
| `total_pnl` | `realized + unrealized delta` |
| `bp_used` | 当日使用的 Buying Power |
| `bp_headroom` | BP 剩余（占 NAV 比例） |
| `short_gamma_count` | short-gamma 仓位数 |
| `open_positions` | 开仓数量 |
| `regime` | 当日 VIX Regime |
| `vix` | 当日 VIX |
| `cumulative_equity` | 累计净值 |
| `drawdown` | 当日 drawdown（vs 历史高点） |
| `experiment_id` | 所属实验 ID |

`_prev_marks: dict`：追踪每个 `position_id` 的前一日 mark，用于计算日度 unrealized delta。每日收盘后更新；持仓到期/平仓时清除。

#### `compute_portfolio_metrics()`（`backtest/metrics_portfolio.py`）

公式：

```python
daily_sharpe = mean(daily_return_net) / std(daily_return_net) * sqrt(252)
daily_sortino = mean(daily_return_net) / std(daily_return_net[daily_return_net < 0]) * sqrt(252)
daily_calmar = ann_return / abs(max_drawdown)
cvar_95 = mean(bottom_5pct_daily_returns)
worst_5d_drawdown = min(rolling_5d_drawdown)
positive_months_pct = months_positive / total_months
```

### 与 Trade-Level 指标的关系

- 保留 `compute_metrics()`（trade-level）用于向后兼容及策略族横向对比（如 ROM 排名等）。
- 新增 **daily portfolio 指标** 作为主要决策依据；所有 SPEC-025/026 的风险控制均基于 daily portfolio view。
- 两套指标数字差异主要来自：haircut 应用方式不同；daily metrics 使用 net return 序列，而非 trade PnL 聚合。

### Experiment Registry

引入 `generate_experiment_id()`，格式：`EXP-YYYYMMDD-HHMMSS-XXXX`（`XXXX` 为 4 位随机字符）

- `config_hash = sha256(params JSON)[:12]`
- 参数完全确定时产生相同哈希，支持去重和结果回放。
- 所有回测输出强制关联 `experiment_id`，保证实验可复现、可对比、可审计。

实现文件：`backtest/registry.py`

---

## 33. Portfolio Shock-Risk Engine — 基于场景的组合风险预算（SPEC-025, 2026-04-01）

**Status：已实施**

### 研究问题

现有系统的入场控制依赖 count-based rule（`max_short_gamma_positions = 3`）：只要 short-gamma 仓位数不超过 3，就允许入场。这个规则无法区分同样是"3 个 short-gamma 仓位"但风险截然不同的情况：

- 场景 A：3 个窄翼 BPS，各自最大亏损约 $500，组合极端损失约 $1,500
- 场景 B：3 个宽翼 IC + 高 DTE，各自最大亏损约 $3,000，组合极端损失可达 $9,000

Count-based rule 对两者一视同仁。需要真正的组合层 tail risk 度量，并用 NAV 百分比表达。

### 设计决策：8 个标准场景

| 场景 | 名称 | Spot_pct | vix_shock_pt | 分类 |
|---|---|---:|---:|---|
| S1 | 下行轻冲击 | -2% | +5pt | Core |
| S2 | 下行中冲击 | -3% | +8pt | Core |
| S3 | 下行重冲击 | -5% | +15pt | Core |
| S4 | 纯波动率冲击 | 0% | +10pt | Core |
| S5 | 上行轻冲击 | +2% | -3pt | Tail |
| S6 | 上行重冲击 | +5% | -8pt | Tail |
| S7 | 反弹 + Vol 正常化 | +3% | -5pt | Tail |
| S8 | 下行 + 期限结构反转 | -2% | +5pt | 独立记录 |

- S1–S4（Core Scenarios）用于计算 `max_core_loss_pct_nav`，作为主预算门槛。
- S5–S7（Tail Scenarios）独立记录，首版不纳入预算控制（v2 扩展）。
- S8 与 S1 数值相同但独立记录：后续可调整参数以专门捕捉期限结构反转效应。

### 关键实现细节

#### Sigma 使用当日 `VIX / 100`，而不是 `pos.entry_sigma`

```python
sigma = current_vix / 100.0
sigma = max(0.05, min(2.00, sigma))
```

设计原因：shock engine 的目标是"在**当前 sigma 水平**下，如果 spot 进一步移动，仓位会损失多少"。若使用历史入场 sigma，会系统性低估当前期权敏感度。

#### 增量风险贡献

```python
incremental_shock_pct = post_max_core - pre_max_core
```

只衡量加入候选仓位后的**边际风险贡献**，允许在组合已有低风险仓位时接受边际贡献较小的新仓位。

#### 运行模式

- **shadow 模式（默认）**：始终 `approved = True`，仅记录审计日志。不阻断任何交易，用于观察历史样本中 shock 分布。
- **active 模式**：若 `abs(post_max_core) > budget`，则 `approved = False`，阻断入场，并记录 `reject_reason`。

### 风险预算（默认值）

| 参数 | Normal Regime | HIGH_VOL Regime |
|---|---:|---:|
| `shock_budget_core_normal` | 1.25% NAV | — |
| `shock_budget_core_hv` | — | 1.00% NAV |
| `shock_budget_incremental` | 0.40% NAV | — |
| `shock_budget_incremental_hv` | — | 0.30% NAV |
| `shock_budget_bp_headroom` | 15% NAV | 15% NAV |

HIGH_VOL regime 使用更严格预算：高 VIX 时仓位间相关性趋近于 1，原本分散的仓位在压力下丧失分散效果。

实现文件：`backtest/shock_engine.py`

---

## 34. VIX Acceleration Overlay — 组合层加速度防御状态机（SPEC-026, 2026-04-01）

**Status：已实施**

### 研究问题

Senior quant review（§8.24–§8.25）指出：**单笔 panic stop 无效**（已有实证）≠ 组合层 overlay 无价值。

| 维度 | 单笔 panic stop | 组合层 overlay |
|---|---|---|
| 触发时机 | 单笔仓位已大幅亏损后平仓 | 市场加速阶段，先于大亏损触发 |
| 执行成本 | 最差价差时点机械全平，成本最高 | 分级响应，先冻结新风险，再评估 trim |
| 信号质量 | 单仓 PnL（滞后指标） | `vix_accel × book_shock`（前瞻组合指标） |
| 历史实证 | 2015 / 2020 panic stop 期望为负 | L2 trim 在 2015 VIX spike 显著有效（§35） |

结论：**废除单笔 panic stop，在组合层引入 VIX 加速度驱动的分级状态机。**

### 关键设计决定：`book_core_shock` 信号路径修复

**初始实现的缺陷**：`book_core_shock` 从 `ShockReport` 取值，而 `ShockReport` 只在有候选入场时生成。后果：L1 freeze 触发 + 当日无入场候选 → 无 ShockReport → `book_core_shock = 0` → L2 AND 条件永远不满足。

**修复方案**：在主循环中独立计算每日 existing portfolio shock，不依赖入场路径（Step 0，engine.py）。

### 行动分级（状态机）

| Level | 触发条件 | 逻辑 | 行动 |
|---|---|---|---|
| L0 Normal | — | — | 正常运行，无限制 |
| L1 Freeze | `accel_3d > 15%` OR `vix >= 30` | OR | 禁止新开 short-vol 仓位 |
| L2 Freeze + Trim | `accel_3d > 25%` AND `book_core_shock >= 1%` | AND | Freeze + 强制平当前全部仓位 |
| L3 Freeze + Trim + Hedge | `accel_3d > 35%` AND `book_core_shock >= 1.5%` | AND | v1：同 L2；v2：额外开 long put spread hedge |
| L4 Emergency | `vix >= 40` OR `book_core_shock >= 2.5%` OR `bp_headroom < 10%` | OR | 强制退出所有仓位 |

- **L2/L3 使用 AND 条件**：防止 VIX 正常上升但组合风险可控时误触。
- **L4 使用 OR 条件**：任何极端信号立即强制保护，不等待其他条件同时满足。

实现文件：`signals/overlay.py`

---

## 35. Overlay 5-Version 对照回测（2026-04-01）

**Status：实验完成**

### 全历史指标（2000-01-03 至 2026-03-31）

| 配置 | Ann.Ret | Sharpe | Calmar | MaxDD | CVaR95 | 交易数 |
|---|---:|---:|---:|---:|---:|---:|
| EXP-baseline | 3.73% | 0.70 | 0.24 | -15.35% | -0.837% | 354 |
| EXP-freeze | 3.77% | 0.70 | 0.30 | -12.63% | -0.835% | 331 |
| EXP-freeze_trim | 4.25% | 0.85 | 0.34 | -12.38% | -0.747% | 348 |
| EXP-freeze_hedge | 3.90% | 0.74 | 0.31 | -12.59% | -0.808% | 333 |
| **EXP-full** | **4.26%** | **0.86** | **0.35** | **-12.22%** | **-0.736%** | **348** |

注：上述数字基于 daily portfolio metrics（SPEC-024）。与 trade-level Sharpe（~1.5）使用不同计量基础，两者方向一致但不可直接比较。

### 压力窗口 Max Drawdown 对比

| 配置 | 2011 EU债务危机 | 2015 VIX spike | 2020 COVID | 2022 熊市 |
|---|---:|---:|---:|---:|
| EXP-baseline | -2.78% | -2.13% | -4.45% | -5.59% |
| EXP-freeze | -2.78% | -2.13% | -4.45% | -5.59% |
| EXP-freeze_trim | -0.10% | -0.46% | -4.13% | -5.20% |
| **EXP-full** | **-0.10%** | **-0.46%** | **-4.13%** | **-5.20%** |

`EXP-freeze` 在 2011/2015 无改善——纯 freeze 无法保护已开仓位；L2 trim 触发后才有显著改善。

### 验收标准 VS EXP-baseline

| 验收项 | 门限 | EXP-full 实测 | 通过 |
|---|---:|---:|---|
| MaxDD 改善 | ≥10% | 20.4%（15.35% → 12.22%） | ✓ |
| CVaR95 改善 | ≥10% | 12.1%（0.837% → 0.736%） | ✓ |
| 年化收益不降 | ≥92% of baseline | +14%（3.73% → 4.26%） | ✓ |
| 交易数降幅 | ≤10% | -1.7%（354 → 348） | ✓ |

### 未解决问题

1. L3 hedge 实盘实现（v2）：当前 v1 中 L3 与 L2 行为相同。
2. `vix_accel_1d` 用于 L4 fast-path：提升对 COVID 类极速崩溃的响应能力。
3. 多仓引擎下的 trim 精细化：当前 L2/L4 为"全平"；可改为"优先关闭 shock 贡献最高的仓位"。

---

## 36. Shock Engine Active Mode 校准与 A/B 验证（SPEC-027, 2026-04-02）

**Status：已实施**

### 研究问题

验证：在 shadow mode 下，如果 shock gate 是 active 的，拦截率是多少？分布如何？只有当 hit rate 落在合理区间，active mode 才适合上线。

### Phase A：Shadow 模式下的 ShockReport 分析

核心分析维度：

1. **Hit rate（年度分布）**：哪些年份 shock gate 会频繁拦截？高 VIX 年是否显著更高？
2. **Breach type 分布**：`post_max_core_loss_pct` 超预算、`incremental_shock_pct` 超预算、`bp_headroom_pct < 15%` 三类 breach 各占多少？
3. **Percentile 分布**：shock 数值的中位数、P95、P99，为 budget 校准提供依据。

### 关键实现问题：`compute_hit_rates()` bug 修复

shadow mode 中 `approved` 永远为 `True`，导致原实现的 would-be rejection rate 恒为 0%。

**修复方案**：改用预算列直接比较（不依赖 `approved` 字段），使 Phase A 分析有意义。

### Phase B：Active vs Shadow A/B Acceptance Criteria

| AC | 指标 | 阈值 |
|---|---|---|
| B1 | Trade count 下降 | ≤10% |
| B2 | PnL 变化 | 下降 ≤8% |
| B3 | MaxDD | 不劣于 shadow |
| B4 | CVaR（5%） | 不劣于 shadow |

实现文件：`backtest/run_shock_analysis.py`

---

## 37. 资本效率指标与 PnL 归因（SPEC-028, 2026-04-02）

**Status：已实施**

### 核心新增指标

#### `pnl_per_bp_day`（资本利用率调整后收益）

```python
pnl_per_bp_day = total_net_pnl / sum(daily_used_bp)
```

单位：每占用 1 美元保证金 1 天获得的净 PnL（美元）。该指标同时把持仓时间和资金占用纳入分母，消除"长时间持有低效仓位"对胜率的扭曲。

#### `compute_strategy_attribution(trades)` → 11 列

按策略类型汇总：trade_count、win_rate、net_pnl、mean_pnl_per_trade、pnl_per_bp_day 等。

#### `compute_regime_attribution(rows, account_size)` → 8 列

按 VIX regime 汇总：day_count、pct_of_trading_days、mean_daily_return_net、regime_sharpe、mean_bp_utilization、total_net_pnl_contribution 等。

### 研究意义

`pnl_per_bp_day` 是衡量策略**资本效率**的关键指标。若 Diagonal 的 `pnl_per_bp_day` 显著低于 BPS，说明其长期占用 BP 但回报偏低，可为 trend signal 改进（§40）提供明确数值目标。

实现文件：`backtest/attribution.py`

---

## 38. 出样本（OOS）验证：IS=2000-2019 / OOS=2020-2026（SPEC-029, 2026-04-02）

**Status：已实施**

### 研究设计

采用**单次全历史回测 + 日期过滤**，而不是两次独立回测，以避免 OOS 回测缺少 IS 期仓位状态所带来的 cold-start artifact。

拆分点：IS = 2000-01-03 至 2019-12-31；OOS = 2020-01-01 至 2026-03-31。

### 5 张对比报表

| 报表 | 内容 |
|---|---|
| R1 | Full / IS / OOS 的 Ann.Ret、Sharpe、Calmar、MaxDD、CVaR、Trades |
| R2 | `EXP-full` vs `EXP-baseline` 的 delta，按三个窗口分列 |
| R3 | OOS Acceptance Criteria（4 项） |
| R4 | OOS 期策略归因：`pnl_per_bp_day by strategy` |
| R5 | OOS 期 8 个 Regime 视角：Sharpe / BP utilization by VIX regime |

### OOS 验证结果（2026-04-04）

| AC | 指标 | 阈值 | 结果 |
|---|---|---|---|
| OOS-1 | EXP-full OOS Sharpe > 0 | > 0 | **PASS**（1.58） |
| OOS-2 | MaxDD improvement（OOS, full vs baseline） | ≥ 5pp | **FAIL**（1.49pp；-5.01% → -3.52%） |
| OOS-3 | PnL retention（OOS vs IS，按日标准化） | ≥ 85% | **PASS**（94.4%） |
| OOS-4 | Trade drop（OOS vs IS） | ≤ 15% | **PASS**（OOS 频率比 IS 高 +12%） |

**OOS-2 分析**：OOS 期（2020-2026）本身市场环境已较温和（baseline MaxDD 仅 -5.01%），overlay 保护空间有限。overlay 在 IS 压力期（2008-2009、2011）作用更显著。OOS-2 FAIL 不代表 overlay 无效，而是 OOS 期 baseline 风险本来就低。

实现文件：`backtest/run_oos_validation.py`

---

## 39. SPX 趋势信号深度研究：Alternative Signal 评估（2026-04-02）

**Status：研究完成，立项建议已写入 SPEC-020**

### 两类核心问题

1. **Entry Gate 假 BULLISH**：熊市反弹导致 SPX 短暂站上 MA50 + 1%，系统开 BPS / Diagonal 后回撤亏损。
2. **Exit Trigger 误触发 trend_flip**：3–7 天正常修正触发单日 BEARISH，系统卖在局部底部。

### 评分矩阵

| 方向 | 减少假信号 | 及时性 | 实现复杂度 | 数据需求 | 总分 |
|---|---:|---:|---:|---:|---:|
| ATR Gap（Entry） | 4 | 4 | 4 | 3 | 20/25 |
| Persistence Filter（Exit） | 5 | 3 | 4 | 5 | 22/25 |
| Regime-Conditional（增强） | 5 | 4 | 3 | 3 | 19/25 |
| ADX 确认（Exit 辅助） | 4 | 3 | 3 | 3 | 17/25 |
| ROC / MACD | 1 | 5 | 4 | 5 | 8/25 |
| Swing Structure | 3 | 2 | 2 | 5 | 14/25 |

不推荐 ROC / MACD 的原因：信号逻辑（动量越差越 bearish）与 short-vol 策略"修正是机会"的框架方向不一致。Swing Structure 往往在市场下跌 10–15% 后才确认，无时效性，过拟合风险高。

---

## 40. ATR-Normalized Entry Gate + Persistence Exit Filter：研究设计（SPEC-020, 2026-04-02）

**Status：RS-020-1 完成（前置研究），RS-020-2 Ablation 待运行**

### 问题根因

固定 1% band 在不同波动环境下含义不一致：

- VIX = 12 时，等效门槛过宽，不易触发
- VIX = 30 时，等效门槛过窄，过于容易触发

ATR 标准化后，阈值在不同 VIX 环境下具有更一致的语义：

```python
gap_sigma = (SPX - MA50) / ATR(14)
```

Persistence filter 方案：用 `bearish_streak >= N` 触发 `trend_flip`，代替"单日 BEARISH 即翻转"。

### §7 前置研究结果（RS-020-1）

| 参数 | 初始假设 | 实证修正 |
|---|---|---|
| `ATR_THRESHOLD` | 1.0 | 1.0（确认；gap_sigma 分布与原 +1% band 最接近） |
| `BEARISH_PERSISTENCE_DAYS` | 5 | **3**（`streak = 3` 为条件概率拐点；相比 5，额外延迟不值得） |

---

## 41. ATR-Normalized Entry Gate：Ablation 结果与生产决策（SPEC-020 RS-020-2, 2026-04-04）

**Status：实验完成，已部署**

### 4-way Ablation 实验

| 配置 | use_atr_trend | bearish_persistence_days | 说明 |
|---|---|---|---|
| EXP-baseline | False | 1 | 原始系统（legacy 1% band，无 persistence） |
| EXP-atr | True | 1 | 仅 ATR normalization，无 persistence |
| EXP-persist | False | 3 | 仅 persistence filter（streak >= 3），无 ATR |
| EXP-full | True | 3 | ATR + persistence（两者合并） |

### 全量指标对比（2000-2026）

| 配置 | Full Sharpe | Full MaxDD | OOS Sharpe | OOS MaxDD | Full Trades |
|---|---:|---:|---:|---:|---:|
| EXP-baseline | 1.44 | -13.94% | 1.62 | -5.01% | 354 |
| EXP-atr | 1.43 | -11.21% | 1.68 | -4.94% | 309 |
| EXP-persist | 1.43 | -17.78% | 1.57 | -8.85% | 354 |
| EXP-full | 1.43 | -17.47% | 1.62 | -8.48% | 309 |

注：上述 Sharpe 为 trade-level Sharpe（激进口径），与 §35 的 daily portfolio Sharpe（保守口径）使用不同计量基础。

### 结论与生产决策

**ATR-only 采纳（Fast Path 已实施）**：

- OOS Sharpe 1.68 vs baseline 1.62（+6bp）
- Full MaxDD -11.21% vs baseline -13.94%（改善 2.73pp）
- 交易数 309 vs 354（减少 12.7%；质量更高的入场筛选）
- `use_atr_trend: bool = True`（`strategy/selector.py` 默认值）

**Persistence Filter 拒绝**：

- OOS Sharpe 1.57 vs baseline 1.62（−5bp）
- Full MaxDD -17.78% vs baseline -13.94%（恶化 3.84pp）
- EXP-full（ATR+persist）也未超过 baseline
- 根本原因：`bearish_streak >= 3` 使出场延迟，导致在真实熊市中承受更大损失；short-vol 策略需要快速响应趋势反转，持久性过滤与框架逻辑冲突
- `bearish_persistence_days: int = 1`（维持默认，等价于"单日即翻转"）

### 现行生产基准（2026-04-04）

| 指标 | 数值 |
|---|---:|
| Full Sharpe（trade-level） | 1.43 |
| Full MaxDD | -11.21% |
| IS Sharpe | 1.48 |
| IS MaxDD | -11.21% |
| OOS Sharpe | 1.68 |
| OOS MaxDD | -4.94% |
| Full Trades | 309 |

---

## 42. Delta 单调性与插值扫描设计（SPEC-045/047，2026-04-07）

**Status：设计决策，已实施**

### 问题背景

SPEC-040 的 centered scan（围绕理论 strike 邻域取 ±10 档）可能返回 live delta 远偏离目标（delta gap > 0.08）的候选。SPEC-043 草案提出迭代扩窗（类 binary search），但需要多次 API 请求且未利用期权链的结构性信息。

### 关键洞察：Delta 单调性

期权链 delta 对 strike 严格单调：

- **PUT**：|delta| 随 strike 升高而增大（越 ITM delta 越大）
- **CALL**：delta 随 strike 升高而减小（越 OTM delta 越小）

单调性意味着：
1. 目标 delta 在期权链中**有且只有一个穿越点**（或落在端点之外）
2. 可以扫描相邻行对找穿越点，线性插值估算最优 strike
3. **无需 binary search，也无需多次 API 请求**（O(n) 单次扫描）

### SPEC-045 设计：单次宽窗 + 插值

```
1. 一次拉取宽窗链（默认 80 档）
2. 对 chain 按 strike 排序
3. 扫描相邻对，找到 delta 穿越点
4. 线性插值：sought = K_i + t × (K_{i+1} − K_i)
   其中 t = (target − δ_i) / (δ_{i+1} − δ_i)
5. best_center = round(sought / 5.0) × 5.0
6. 围绕 best_center 取 ±10 档评分
```

**效果**：单次 API 请求，精准定位目标 delta strike，消除"推荐合约 delta 远偏"问题。

### SPEC-047 补充：边界命中检测 + 自适应扩窗

插值后若 sought_strike 等于链的 min 或 max strike，说明真实穿越点在当前窗口之外（boundary hit，非真实边界）。此时扩大窗口重试，最多 3 轮（80 → 140 → 220）。

```
_DELTA_SCAN_WINDOWS = (80, 140, 220)

for window in windows:
    chain = get_option_chain(... strike_window=window)
    sought = _seek_target_delta_strike(chain)
    if not _is_boundary_hit(chain, sought): break  # 内部穿越，停止
    # 否则继续扩窗
```

**设计权衡**：
- 正常情况（内部穿越）：1 次 API 请求
- 极端高波动（VIX > 40，delta curve 扁平）：最多 3 次
- 无限递归：不存在，窗口数量固定

### 与 SPEC-043 的对比

| 方案 | API 请求数 | delta gap 改善 | 利用单调性 |
|------|----------|--------------|----------|
| SPEC-043（迭代扩窗）| 多次（无上限）| 是 | 否 |
| SPEC-045（插值）| 1 次（正常）| 是，更精准 | ✅ 是 |
| SPEC-047（插值+边界检测）| 1–3 次（有上限）| 是，处理边界 | ✅ 是 |

**结论**：delta 单调性是期权链的结构性事实，利用它可以将扫描问题从"搜索"变为"插值"，显著减少 API 请求并提升精度。SPEC-043 已取消实施。

