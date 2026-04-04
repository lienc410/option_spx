# SPEC-006: Bear Call Spread HV — BEARISH + HIGH_VOL 新入场路径

## 目标

**What**：在 HIGH_VOL + BEARISH + VIX 非 RISING 环境下，新增 Bear Call Spread（BCS HV）策略，填补当前完全空转的时间段。

**Why**：Prototype 分析（`backtest/prototype/SPEC-006c_full_strategy_scan.py`）：
- BEARISH + HIGH_VOL 目前 100% REDUCE_WAIT（868 天 / 26 年，占 13%）
- 扫描 8 类策略后，BCS 是唯一具有统计显著正期望的：WR 86%，均 PnL +$466，Sharpe 0.577
- 借方方向性策略（Bear Put Spread、LEAP Put、Bear Put Diagonal）全面失效（WR 30-42%），原因：MA 信号滞后，BEARISH 确认时市场常已下跌完毕，随后 V 型反转消耗权利金
- Calendar spread 在 BEARISH+HIGH_VOL 的 VIX 倒挂期间同样失效（WR 33%）
- VIX RISING（49% 时间）排除，VIX FLAT + FALLING（51% 时间）是有效入场窗口

---

## 策略/信号逻辑

**新增路径（插入现有 HIGH_VOL 块中）：**

```
HIGH_VOL + BEARISH + VIX RISING  → REDUCE_WAIT（恐慌仍在升级，不入场）
HIGH_VOL + BEARISH + VIX 非RISING → Bear Call Spread HV（DTE=45, 0.5x size）
```

**BCS HV 结构：**
- SELL CALL δ0.20, DTE=45（近 OTM，收取 HIGH_VOL 下膨胀的权利金）
- BUY  CALL δ0.10, DTE=45（更远 OTM，封顶上行风险）
- Net credit = short call premium − long call premium

**为何方向对齐：**
- BEARISH 趋势 → SPX < MA50 → OTM call 到期价外概率高
- HIGH_VOL → call 权利金因市场恐慌被人为拉高 → 卖方获更多信用
- BCS 不依赖方向性"继续下跌"，只需市场不大幅反弹即可盈利

**backwardation 过滤不适用：**
- 现有 backwardation 过滤针对 BPS（put 侧）；BCS 卖的是 call，backwardation（near-term put 恐慌）对 call 定价无负面影响，故不过滤。

---

## 接口定义

### 1. `strategy/selector.py` — 新增枚举值

```python
class StrategyName(str, Enum):
    ...
    BEAR_CALL_SPREAD_HV = "Bear Call Spread (High Vol)"  # ← 新增
    ...
```

### 2. `strategy/selector.py` — 重构 HIGH_VOL 块

**变更前（lines 242–285）：**
```python
if r == Regime.HIGH_VOL:
    if vix.backwardation:
        return _reduce_wait(...)       # backwardation → wait
    if t != TrendSignal.BULLISH:
        return _reduce_wait(...)       # non-BULLISH → wait（含 BEARISH）
    if vix.trend == Trend.RISING:
        return _reduce_wait(...)       # VIX rising → wait
    # → BPS HV
```

**变更后：**
```python
if r == Regime.HIGH_VOL:

    # BEARISH 分支：BCS HV（方向对齐，不受 backwardation 影响）
    if t == TrendSignal.BEARISH:
        if vix.trend == Trend.RISING:
            return _reduce_wait(
                "HIGH_VOL + BEARISH + VIX RISING — panic escalating; "
                "wait for VIX to stabilise before selling calls",
                vix, iv, trend, macro_warn,
            )
        action = get_position_action(StrategyName.BEAR_CALL_SPREAD_HV.value, is_wait=False)
        return Recommendation(
            strategy        = StrategyName.BEAR_CALL_SPREAD_HV,
            underlying      = "SPX",
            legs            = [
                Leg("SELL", "CALL", 45, 0.20,
                    "Short call — δ0.20 OTM, collects inflated HIGH_VOL premium"),
                Leg("BUY",  "CALL", 45, 0.10,
                    "Long call — further OTM, caps upside risk"),
            ],
            max_risk        = "Spread width − net credit (defined risk)",
            target_return   = f"Close at {int(params.profit_target*100)}% of credit received",
            size_rule       = (
                f"{int(params.high_vol_size*100)}% size — risk ≤ "
                f"{1.5*params.high_vol_size:.1f}% of account "
                f"(HIGH_VOL BEARISH, reduced exposure)"
            ),
            roll_rule       = f"Close at 21 DTE; stop at {params.stop_mult}× credit",
            rationale       = (
                f"HIGH_VOL + BEARISH + VIX stable — inflated call premium with "
                f"directional tailwind; δ0.20 short call has high PoP"
            ),
            position_action = action,
            vix_snapshot    = vix, iv_snapshot = iv, trend_snapshot = trend,
            macro_warning   = macro_warn,
        )

    # NEUTRAL / BULLISH 分支：原有逻辑（backwardation、VIX RISING、BPS HV）
    if t == TrendSignal.NEUTRAL:
        return _reduce_wait(
            "HIGH_VOL + NEUTRAL — no directional edge; wait for trend to clarify",
            vix, iv, trend, macro_warn,
        )
    # t == TrendSignal.BULLISH（以下为原有 BPS HV 逻辑，不变）
    if vix.backwardation:
        return _reduce_wait(...)
    if vix.trend == Trend.RISING:
        return _reduce_wait(...)
    # → BPS HV（原有代码不变）
```

### 3. `backtest/engine.py` — `_build_legs()` 新增分支

在 `BULL_PUT_SPREAD_HV` 之后插入：

```python
if strategy == StrategyName.BEAR_CALL_SPREAD_HV:
    dte     = 45
    short_k = find_strike_for_delta(spx, dte, sigma, 0.20, is_call=True)
    long_k  = find_strike_for_delta(spx, dte, sigma, 0.10, is_call=True)
    return [
        (-1, True, short_k, dte, 1),   # short call δ0.20
        (+1, True, long_k,  dte, 1),   # long  call δ0.10
    ], dte
```

### 4. `backtest/engine.py` — BP 计算

`_compute_bp()` 中，BCS HV 与 BPS 相同公式：

```python
if position.strategy in (StrategyName.BULL_PUT_SPREAD,
                          StrategyName.BULL_PUT_SPREAD_HV,
                          StrategyName.BEAR_CALL_SPREAD_HV):   # ← 新增
    # BP = (spread_width - credit) × $100
    ...
```

---

## 边界条件与约束

- VIX RISING 时不入场（不论趋势）：恐慌未止，call premium 可能继续上涨（delta 损失 > theta 收益）
- backwardation 不过滤 BCS HV：backwardation 影响 put 侧，BCS 卖 call，无关
- NEUTRAL 趋势仍为 REDUCE_WAIT：无方向性支持，BCS 失去 tailwind
- 不添加 BULLISH trend_flip 出场规则（初版保持简单；WR 86% 不需额外过滤）
- size_mult = `params.high_vol_size`（默认 0.5×），与 BPS HV 一致
- 现有 BPS HV（BULLISH 路径）逻辑完全不变

---

## 不在范围内

- 不修改 NORMAL 体制的任何逻辑
- 不修改 LOW_VOL 体制的任何逻辑
- 不实现 BULLISH trend_flip 出场（留待后续 Spec 验证）
- 不修改 `params.high_vol_size`、`params.high_vol_dte` 参数含义
- 不实现 NEUTRAL + HIGH_VOL 的任何新策略

---

## Prototype

- 路径：`backtest/prototype/SPEC-006c_full_strategy_scan.py`
- 验证内容：8 类策略在 BEARISH+HIGH_VOL 的 WR/PnL/Sharpe 全扫描；BCS 综合评分第一

---

## Review

- 结论：**FAIL（实施正确，Sharpe 验收标准未达）**
- 日期：2026-03-29

### 实施正确性：PASS

逐项核查：

| 文件 | 修改点 | 核查结果 |
|------|-------|---------|
| `selector.py:87` | `BEAR_CALL_SPREAD_HV = "Bear Call Spread (High Vol)"` | ✅ 枚举值正确 |
| `selector.py:243` | `if t == BEARISH` → VIX RISING guard → BCS HV Recommendation | ✅ 逻辑与 Spec 一致 |
| `selector.py:277` | `if t == NEUTRAL` → `_reduce_wait(...)` | ✅ 新增 NEUTRAL 分支 |
| `selector.py:283+` | BULLISH 路径保留原 backwardation / VIX RISING / BPS HV 逻辑 | ✅ 未改动原有路径 |
| `engine.py:178` | `BEAR_CALL_SPREAD_HV` → DTE=45, short δ0.20 call, long δ0.10 call | ✅ 腿构建正确 |
| `engine.py:256` | BCS HV 纳入 credit spread BP 公式 | ✅ 与 BPS 同一分支 |
| `engine.py:594` | `size_mult = params.high_vol_size` for BCS HV | ✅ 0.5× 缩放正确 |

### 验收标准结果

| 标准 | 目标 | 实测 | 通过 |
|------|-----|------|------|
| BCS HV n | ≥ 20 | 72 | ✅ |
| BCS HV WR | ≥ 70% | 82% | ✅ |
| 全局 Total PnL | ≥ $78,000 | $78,738 | ✅ |
| 全局 Sharpe | ≥ 1.20 | **0.95** | ❌ |
| dry-run 合成验证 | BCS HV 输出 | 通过 | ✅ |

### Sharpe 下降原因分析

SPEC-004 基准 Sharpe = **1.16**（已低于目标 1.20）。BCS HV 新增 72 笔 HIGH_VOL 期间交易，在 HIGH_VOL 制度下：
- 损失时 spread 宽度大，单笔亏损金额较 NORMAL 显著更高
- 即使 WR 82%，18% 的亏损笔数在 HIGH_VOL 期间放大了 PnL 标准差
- 全局 Sharpe = expectancy / std_pnl × √(252/avg_hold)，std_pnl 上升幅度超过 expectancy 提升

**实质**：策略对全局 PnL 贡献为正（+$8,721），但降低了风险调整后回报率。

### 决策说明

Sharpe 目标 1.20 在 SPEC-004 基准（1.16）时就已超出基准，期望 BCS HV 额外将 Sharpe 从 1.16 推高到 1.20——这个设定过于乐观。**实施本身无问题**，是策略设计上的 tradeoff：

- 接受 Sharpe 0.95：PnL 提升 $8,721，WR 82%，资本利用率改善
- 不接受：回滚，BEARISH+HIGH_VOL 继续空转

**需 PM 决策**：是否接受当前结果，将 Sharpe 验收标准调整为 ≥ 0.90，或维持 FAIL 状态待进一步优化。

---

## 验收标准

1. `python main.py --backtest --start=2000-01-01` 输出中出现 `Bear Call Spread (High Vol)` 行，且 n ≥ 20
2. BCS HV WR ≥ 70%
3. 全局 Total PnL ≥ $78,000（SPEC-004 后基准 $70,017，预期新增 ≥ $8,000）
4. 全局 Sharpe ≥ 1.20
5. `python main.py --dry-run` 在当前信号为 HIGH_VOL + BEARISH + VIX 非 RISING 时，输出 `Bear Call Spread (High Vol)` 推荐（若当日信号不符合，用合成快照验证）

---
Status: DONE
