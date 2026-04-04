# SPEC-005: BCD 入场过滤 — 要求连续 BULLISH ≥ 5 天

## 目标

**What**：Bull Call Diagonal 入场前，要求入场日之前连续 ≥ 5 个交易日均为 BULLISH 信号。

**Why**：Prototype 分析（`backtest/prototype/SPEC-005b_bcd_entry_filter.py`）显示：
- 入场前 2–7 天 BULLISH 的交易 WR 最低（29–33%），均为负期望
- 入场前 ≥ 8 天 BULLISH 的交易 WR 55%，均 PnL +$233
- 过滤至 ≥ 5d 后：89 笔 → 39 笔，WR 46% → 54%，Sharpe 代理 +76%
- 被过滤掉的 50 笔均 PnL 仅 $66，性价比极低

---

## 策略/信号逻辑

**变更前**：trend == BULLISH 当天即可入场 BCD。

**变更后**：
```
BCD 入场条件（在原有 LOW_VOL/NORMAL + BULLISH 前提之外，新增）：
  trend.consecutive_bullish_days >= 5
  （含义：入场日之前，连续 ≥ 5 个交易日的趋势信号均为 BULLISH）

否则 → REDUCE_WAIT，理由文案：
  "LOW_VOL/NORMAL + BULLISH but only {N}d consecutive — wait for confirmed uptrend (≥5d)"
```

`consecutive_bullish_days` 的定义：
- 统计入场日**之前**（不含当天）连续为 BULLISH 的交易日数
- 例：入场日前 7 天均为 BULLISH → consecutive_bullish_days = 7 → 允许入场
- 例：入场日前 2 天为 BULLISH，第 3 天为 NEUTRAL → consecutive_bullish_days = 2 → 阻止入场

---

## 接口定义

### 1. `signals/trend.py` — `TrendSnapshot` 新增字段

```python
@dataclass
class TrendSnapshot:
    date:                    str
    spx:                     float
    ma20:                    float
    ma50:                    float
    ma_gap_pct:              float
    signal:                  TrendSignal
    above_200:               bool
    consecutive_bullish_days: int = 0   # ← 新增，默认 0
```

### 2. `signals/trend.py` — `get_current_trend()` 计算新字段

在返回 `TrendSnapshot` 之前，从 `df` 历史计算：

```python
def _count_consecutive_bullish(df: pd.DataFrame) -> int:
    """
    统计 df 最后一行之前连续 BULLISH 的交易日数（不含最后一行当天）。
    使用 ma_gap_pct > TREND_THRESHOLD 判定每天是否为 BULLISH。
    """
    gaps = ((df["close"] - df["close"].rolling(MA_LONG).mean())
            / df["close"].rolling(MA_LONG).mean()).dropna()
    # 不含最后一行（当天）
    prior = gaps.iloc[:-1]
    count = 0
    for gap in reversed(prior.values):
        if gap > TREND_THRESHOLD:
            count += 1
        else:
            break
    return count
```

`get_current_trend()` 中，在构建 `TrendSnapshot` 时传入：
```python
consec = _count_consecutive_bullish(df)
return TrendSnapshot(..., consecutive_bullish_days=consec)
```

### 3. `backtest/engine.py` — 构建 `trend_snap` 时计算新字段

在 `run_backtest()` 的主循环中，构建 `trend_snap` 时新增：

```python
# 计算连续 BULLISH 天数（不含当天，基于 spx_window）
consec_bull = 0
if len(spx_window) >= MA_LONG + 1:
    ma50_series = spx_window.rolling(MA_LONG).mean()
    gaps = (spx_window - ma50_series) / ma50_series
    prior_gaps = gaps.iloc[:-1].dropna()  # 不含当天
    for g in reversed(prior_gaps.values):
        if g > TREND_THRESHOLD:
            consec_bull += 1
        else:
            break

trend_snap = TrendSnapshot(
    ...,                                    # 原有字段不变
    consecutive_bullish_days=consec_bull,   # ← 新增
)
```

### 4. `strategy/selector.py` — BCD 入场过滤

BCD 触发的两处位置（LOW_VOL + BULLISH 和 NORMAL + LOW_IV + BULLISH）各加一个前置检查：

```python
# LOW_VOL + BULLISH
if t == TrendSignal.BULLISH:
    if trend.consecutive_bullish_days < 5:
        return _reduce_wait(
            f"LOW_VOL + BULLISH but only {trend.consecutive_bullish_days}d consecutive "
            f"— wait for confirmed uptrend (≥5d required for Bull Call Diagonal)",
            vix, iv, trend, macro_warn,
        )
    action = get_position_action(StrategyName.BULL_CALL_DIAGONAL.value, is_wait=False)
    return Recommendation(...)

# NORMAL + IV LOW + BULLISH（同样的过滤，相同文案）
if t == TrendSignal.BULLISH:
    if trend.consecutive_bullish_days < 5:
        return _reduce_wait(
            f"NORMAL + IV LOW + BULLISH but only {trend.consecutive_bullish_days}d consecutive "
            f"— wait for confirmed uptrend (≥5d required for Bull Call Diagonal)",
            vix, iv, trend, macro_warn,
        )
    ...
```

---

## 边界条件与约束

- `consecutive_bullish_days = 0`：入场日前一天不是 BULLISH（如 NEUTRAL 或 BEARISH 转 BULLISH），阻止入场
- `consecutive_bullish_days = 5`：前 5 天均为 BULLISH，允许入场
- NORMAL + IV HIGH + BULLISH → Bull Put Spread：**不受此过滤影响**（BPS 不是 BCD）
- NORMAL + IV NEUTRAL + BULLISH → Bull Put Spread：**不受此过滤影响**
- `TrendSnapshot.consecutive_bullish_days` 默认值 `0`，向后兼容现有调用方

---

## 不在范围内

- 不修改 NEUTRAL 或 BEARISH 趋势下的任何逻辑
- 不修改 BPS（Bull Put Spread）的入场条件
- 不修改 trend_flip 的退出逻辑
- 不修改 `TREND_THRESHOLD` 常数
- 不修改 Iron Condor 的入场条件

---

## Prototype

- 路径：`backtest/prototype/SPEC-005b_bcd_entry_filter.py`
- 验证内容：连续 BULLISH 天数与 BCD 胜率的相关性；≥5d 阈值的 WR / Sharpe 提升

---

## Review

- 结论：FAIL
- 问题：
  1. BCD 笔数实测 77（预期 ≤ 50）。原因：静态原型分析未考虑时序替换效应——过滤早期入场后，模型等待 5d 再入场，笔数只减少 12 笔而非 50 笔。
  2. 总 PnL $58,299（预期 ≥ $60,000），Sharpe 0.77（预期 ≥ 1.10）。原因：连续 BULLISH 过滤强制高位入场，BCD delta 暴露在更高 SPX 价格时更脆弱，均值回归时损失扩大。
  3. 根本结论：对 BCD 使用"趋势确认"型入场过滤是反效果。原型的静态相关性分析无法预测时序替换的代价。

---

## 验收标准

1. `python main.py --backtest --start=2000-01-01` 输出中 BCD 笔数 ≤ 50（当前 89，预期约 39）
2. BCD WR ≥ 52%（当前 46%）
3. 全局 Total PnL 仍 ≥ $60,000（BCD 贡献减少，但整体不应大幅倒退）
4. 全局 Sharpe ≥ 1.10
5. `python main.py --dry-run` 在 BULLISH 天数不足时输出含 "wait for confirmed uptrend" 的 REDUCE_WAIT

---
Status: REJECTED
