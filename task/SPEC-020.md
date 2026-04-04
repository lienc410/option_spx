# SPEC-020: P&L Attribution Analysis — Return Driver Decomposition

## 目标

**What**：分解系统 P&L 的实际来源，验证或否定 Warning A："不要把系统重新框架为方向性趋势跟随引擎"。

**Why**（Prototype 实证，`SPEC-020_pnl_attribution.py`，2026-03-30，26yr 386 笔）：

在 SPEC-014（多仓）、SPEC-015（vol throttle）等改进后，系统收益来源是否发生了结构性变化？趋势信号是主要 RETURN DRIVER 还是 RISK REDUCER？

---

## 核心数据（Prototype 结果，2000–2026）

### Exit Reason 分布（P&L 来源分类）

| Exit Reason | n | WR | AvgPnL | TotalPnL | 贡献% |
|------------|---|-----|--------|----------|-------|
| 50pct_profit | 159 | 100% | $+804 | $+127,783 | **+66.5%** |
| roll_21dte | 172 | 69% | $+686 | $+118,062 | **+61.4%** |
| roll_up | 12 | 100% | $+706 | $+8,470 | +4.4% |
| stop_loss | 8 | 0% | $−3,037 | $−24,293 | **−12.6%** |
| **trend_flip** | **34** | **6%** | **$−1,119** | **$−38,046** | **−19.8%** |

**总 PnL: $+192,234**

### Credit 策略盈利来源分解（213 笔盈利交易）

| 驱动场景 | 占盈利笔数 | AvgPnL |
|---------|-----------|--------|
| 有利方向 only | 59.2% | $+1,220 |
| 有利方向 + vol压缩 | 18.3% | $+1,211 |
| vol压缩 only | 12.7% | $+349 |
| 逆向方向仍赢（short-vol 缓冲） | 12.2% | $+311 |
| 静止（无大移动） | 4.2% | $+347 |

### VIX 持仓期移动 vs WR

| VIX 变化 | n | WR | AvgPnL |
|---------|---|-----|--------|
| -5~-2 pts | 90 | **91%** | $+803 |
| -2~0 pts（最优区间） | 108 | **94%** | $+1,099 |
| 0~2 pts | 68 | 74% | $+652 |
| 2~5 pts | 43 | 53% | $−216 |
| 5~10 pts | 33 | 30% | $−812 |
| ≥10 pts | 13 | 23% | $−1,556 |

### PnL-SPX 和 PnL-VIX 相关系数

| 策略 | PnL-SPX corr | PnL-VIX corr | 主导驱动 |
|------|------------|-------------|---------|
| Bull Call Diagonal | **+0.929** | −0.490 | **方向性 Delta** |
| Bull Put Spread | **+0.973** | −0.897 | **双重驱动** |
| Bull Put Spread HV | +0.942 | −0.803 | 双重驱动 |
| Bear Call Spread HV | −0.778 | +0.404 | 反向 Delta |
| Iron Condor | +0.808 | **−0.914** | **Vol compression** |
| Iron Condor HV | +0.771 | **−0.861** | Vol compression |

---

## 关键发现

### 发现 1：系统收益的最大来源是 Theta + 时间价值，而非方向性 Alpha

Exit Reason 中：
- `50pct_profit`（159 笔，贡献 66.5%）：持仓到达 50% 利润目标，核心来源是时间价值衰减和/或 vol 收缩
- `roll_21dte`（172 笔，WR=69%，贡献 61.4%）：持满时间窗口，theta 自然衰减为主

这两类合计 331 笔（86%），是绝大部分 PnL 的来源。

### 发现 2：trend_flip 是最大的单一 PnL 拖累（−19.8%），远超 stop_loss（−12.6%）

`trend_flip` 34 笔，WR=6%，TotalPnL=−$38,046，是系统最大的拖累项。

**来源分析**：这 34 笔几乎全部是 Bull Call Diagonal 的 trend flip 出场（SPEC-019 中已确认：32/41 Diagonal 亏损由 trend_flip 触发）。

**解读**：
- trend_flip 规则本身是正确的（防止 Diagonal 持续亏损）
- 但 Diagonal 策略的结构性缺陷（long option + 方向性依赖）导致这些退出付出了较大代价
- 这 $38k 的损失是为了保护更大潜在损失而付出的"保险成本"

### 发现 3：BPS 系列有高 SPX 相关性（corr≈0.94–0.97），但这是双重驱动，不是纯方向性 Alpha

BPS 系列 SPX-corr=+0.94–0.97，看似高度方向性，但有两个解释：

1. **选择效应**：trend filter = BULLISH 才入场，所以 entry 时 SPX 已在上升趋势，自然相关
2. **Premium 缓冲**：逆向方向仍赢比例 12.2%（26 笔，AvgPnL=+$311），说明即使 SPX 反向，short put 的 premium 足以覆盖部分损失

与此同时 VIX-corr=−0.80–0.90：**VIX 下降是同等重要的驱动**（regime 选择 + IV 环境正确）。

结论：BPS 是方向 + vol 的双重驱动，而非纯方向性。Warning A 仍然成立。

### 发现 4：BCS_HV 是最"纯"的 Premium 策略

BCS_HV SPX 移动 vs WR 数据：
- SPX 从 ≤-5% 到 +3%，WR 均为 100%
- 只有 SPX ≥+5% 时 WR 骤降至 16%（19 笔）

这意味着 BCS_HV 在宽广的价格区间内都能盈利，它的失败模式几乎仅限于"SPX 急涨 >5%"。这是最接近"纯 Theta / Premium 收割"的策略，方向性风险最低。

### 发现 5：IC / IC_HV 是 vol compression 驱动，不是方向性

IC/IC_HV 的 VIX-corr = −0.86 至 −0.91（所有策略中最强）。VIX-2~0 区间 WR=94%，AvgPnL=$1,099。IC 盈利的核心是"进场时 VIX 偏高，持仓期间 VIX 自然回归"。这是经典 short-vol premium 收割，与趋势方向无关。

### 发现 6：Warning A 得到量化验证

| 系统框架 | 证据 |
|---------|------|
| "timed short-vol engine" | Exit reason 主导：50pct_profit + roll_21dte = 86% 笔数 |
| "regime filters as risk reducer" | VIX 移动 vs WR 显示 vol expansion 是主要失败模式 |
| NOT "directional alpha engine" | 12.2% 的信用策略赢在逆向移动时；BCS_HV 无视 SPX 方向 100% 盈利 |
| Diagonal 是唯一例外 | SPX-corr=0.929，方向性最强；但它靠 trend_flip EXIT 管理风险 |

---

## 策略含义

| 决策方向 | 含义 |
|---------|------|
| 不要把 MA50 filter 当核心 Alpha | 它是 risk reducer，降低 adverse direction 概率 |
| BCS_HV 是最鲁棒的策略 | 宽广 SPX 缓冲区，方向依赖最低 |
| trend_flip 损失是结构成本，不是 bug | 它防止了更大的 Diagonal 亏损 |
| IC/IC_HV 的敌人是 VIX 上升，不是 SPX 方向 | VIX ≥+5pts 时 WR=23% — 这是 IC 最大风险 |
| 增加方向性过滤不会显著提升 Credit 策略收益 | 已有 trend filter 已经是最优的方向性保护 |

---

## 不在范围内

- 精确 Black-Scholes 归因（需锁定 IV）
- 实时 Greeks 跟踪
- 修改 selector 或 engine

---

## Prototype

路径：`backtest/prototype/SPEC-020_pnl_attribution.py`

关键数字：
- trend_flip 拖累 = $−38,046（−19.8%），最大单一损失来源
- BCS_HV: SPX −5% to +3% 范围内 WR=100%
- IC/IC_HV: VIX-corr = −0.86 to −0.91（最强 vol sensitivity）
- 逆向方向仍赢比例：12.2%（short-vol 结构缓冲验证）

---

## Review

- 结论：N/A（研究性 SPEC，无 Codex 实现）

---

## 验收标准

1. PM 了解：系统主要驱动是 Theta + Vol premium，不是方向性 Alpha
2. PM 了解：trend_flip 是最大 PnL 拖累，但它是 Diagonal 结构的保险成本
3. PM 了解：BCS_HV 的风险模式是 SPX ≥+5% 急涨；IC 的风险是 VIX ≥+5pts 扩张
4. PM 了解：trend filter 是 RISK REDUCER，不是 RETURN DRIVER

---

## 追加实现范围（2026-04-02，ATR-Normalized Entry Gate + Persistence Exit）

基于 §7 前置研究（`backtest/research/SPEC020_prereq_findings.md`），对趋势信号实施两项改进。

### §7 前置研究参数

| 参数 | 初始假设 | 实证修正 |
|---|---|---|
| `ATR_THRESHOLD` | 1.0 | 1.0（确认；gap_sigma 分布与原 +1% band 最接近） |
| `BEARISH_PERSISTENCE_DAYS` | 5 | **3**（streak=3 为条件概率拐点，额外延迟代价不值得） |

### 改动 1：ATR-Normalized Entry Gate

**问题**：固定 1% band 在不同 VIX 环境下语义不一致（VIX=12 时过宽；VIX=30 时过窄）。

**实现**（`signals/trend.py`）：

```python
ATR_PERIOD    = 14      # 新增常量
ATR_THRESHOLD = 1.0    # 新增常量（gap_sigma 阈值）

def _compute_atr14_close(close_series: pd.Series) -> pd.Series:
    """v1: 用收盘价差分近似 ATR（|close[t] - close[t-1]| 的 14 日均值）。"""
    return close_series.diff().abs().rolling(ATR_PERIOD).mean()

def _classify_trend_atr(gap_sigma: float) -> TrendSignal:
    """BULLISH if gap_sigma >= +1.0; BEARISH if <= -1.0."""
    if gap_sigma >= ATR_THRESHOLD: return TrendSignal.BULLISH
    if gap_sigma <= -ATR_THRESHOLD: return TrendSignal.BEARISH
    return TrendSignal.NEUTRAL
```

`TrendSnapshot` 新增可选字段：
```python
atr14: float | None = None
gap_sigma: float | None = None
```

`get_trend_history()` 新增可选参数 `use_atr: bool = True`，当 True 时额外输出列：`atr14, gap_sigma, signal_atr`。

### 改动 2：Persistence Exit Filter

**问题**：单日 BEARISH 触发 `trend_flip`，导致正常修正被错误识别为趋势转换。

**实现**（`backtest/engine.py`）：

```python
BEARISH_PERSISTENCE_DAYS = 3   # 新增常量（或从 StrategyParams 读取）

# 在日循环顶层维护 streak 计数器（不在 signals/trend.py 内，在 engine 主循环）
if trend_signal == TrendSignal.BEARISH:
    bearish_streak += 1
else:
    bearish_streak = 0

# 出场条件修改
# Before: hold_days >= min_hold_days and trend_signal == BEARISH
# After:  hold_days >= min_hold_days and bearish_streak >= BEARISH_PERSISTENCE_DAYS
```

**注意**：streak 计数器在 engine 主循环顶层维护，而不是在 `signals/trend.py` 内，因为它是跨日状态。

### 4-way Ablation（SPEC-020 验证要求）

需要在 `backtest/run_trend_ablation.py` 中完成 4 组对比：

| 实验名 | Entry Gate | Exit Filter |
|---|---|---|
| `EXP-baseline` | 固定 1% band | 单日 BEARISH |
| `EXP-atr` | ATR-normalized | 单日 BEARISH |
| `EXP-persist` | 固定 1% band | streak >= 3 |
| `EXP-full` | ATR-normalized | streak >= 3 |

报告：全历史 + OOS（2020-2026）× 策略归因（pnl_per_bp_day by strategy）。

**当前状态**：RS-020-1 FAIL（ablation 未完成），待 RS-020-2。

### 新建文件：`backtest/run_trend_ablation.py`

```python
def run_trend_ablation(start_date="2000-01-01", end_date="2026-03-31") -> None:
    """运行 4-way ablation，打印全历史 + OOS 对比表。"""
```

参数构造：
- `EXP-atr`：在 params 中设置 `use_atr_entry=True`，或直接切换 engine entry gate 逻辑（由 Codex 决定最优方式）
- `EXP-persist`：`bearish_persistence_days=3`（StrategyParams 新增字段，见下）

**建议**：`StrategyParams` 新增两个字段供 ablation 控制：
```python
use_atr_trend: bool = False         # True → ATR-normalized entry; False → legacy 1% band
bearish_persistence_days: int = 1   # 1 = legacy（单日）; 3 = SPEC-020 推荐
```

### Review（追加实现部分）

- 结论：PASS（代码实现）；AC#7 全历史 OOS 方向性验证待完成
- 实现文件：`signals/trend.py`、`strategy/selector.py`（`use_atr_trend`、`bearish_persistence_days`）、`backtest/engine.py`
- 核查要点：
  - `_compute_atr14_close()`: `close.diff().abs().rolling(14).mean()`，前 14 行 NaN，第 15 行起有值（单测 ✓）
  - `gap_sigma = (spx - ma50) / max(atr14, 1.0)`，防止 atr14=0 除零 ✓
  - `_classify_trend_atr(1.0) == BULLISH`，`(0.99) == NEUTRAL`（单测 ✓）
  - `use_atr_trend=True` 时 engine 用 `_classify_trend_atr(gap_sigma)`，否则用 legacy 1% band ✓
  - `bearish_streak` 计数器在日循环顶层：BEARISH 日 +1，否则重置为 0 ✓
  - `bearish_persistence_days=1`（默认），等价于原单日触发行为 ✓；=3 时需连续 3 天才触发 trend_flip ✓
  - trend flip 条件：`bearish_streak >= max(params.bearish_persistence_days, 1)`（用 max 防止 0 的边界情况）✓
  - `bearish_streak` 写入 `signal_history`，可供 ablation 分析 ✓
- 全历史 Ablation 验证结果（2026-04-04）：

| 配置 | Full Sharpe | OOS Sharpe | Full MaxDD |
|---|---:|---:|---:|
| EXP-baseline | 1.44 | 1.62 | -13.94% |
| EXP-atr | 1.43 | **1.68** | -11.21% |
| EXP-persist | 1.38 | 1.57 | -17.78% |
| EXP-full（atr+persist） | 1.37 | 1.62 | -17.41% |

AC#7 结果：EXP-full OOS Sharpe（1.62）= EXP-baseline OOS Sharpe（1.62），**未超越**。

分项分析：
- **ATR 单独**（EXP-atr）：OOS Sharpe 1.68 > baseline 1.62，有效，Full MaxDD 也改善 ✓
- **Persistence 单独**（EXP-persist）：OOS Sharpe 1.57 < baseline，独立使用略差，Full MaxDD 反而更差（-17.78%）
- **两者组合**（EXP-full）：OOS 与 baseline 持平，但 Full MaxDD 劣化至 -17.41%

结论：ATR-normalized entry gate 有价值（OOS +6bp Sharpe / MaxDD 改善 2.73pp）；Persistence exit 单独或组合使用有副作用（Full MaxDD 劣化约 4pp），**Persistence filter 被 RS-020-2 否决**。

RS-020-2 决策（2026-04-04，PM 批准）：
- **采纳**：`use_atr_trend = True`（ATR-normalized entry gate，新默认值）
- **否决**：`bearish_persistence_days = 3`，维持 `bearish_persistence_days = 1`（单日触发，legacy 行为）

Fast Path 实施：`strategy/selector.py` L115，`use_atr_trend: bool = False → True`

### 验收标准（追加部分）

1. `_compute_atr14_close(pd.Series(...))` 前 14 行为 NaN，第 15 行起有值
2. `gap_sigma = (spx - ma50) / atr14`，atr14=0 时不产生除零错误（clamp atr14 >= 1.0）
3. `_classify_trend_atr(1.0) == BULLISH`；`_classify_trend_atr(0.99) == NEUTRAL`
4. Engine 中 `bearish_streak` 在 BEARISH 日递增，非 BEARISH 日重置为 0
5. `EXP-persist` vs `EXP-baseline`：streak=3 不会早于 3 日触发 trend_flip
6. `run_trend_ablation()` 输出 4 行对比表，不报错
7. RS-020-2 完成后：`EXP-full` OOS Sharpe > `EXP-baseline` OOS Sharpe（方向性验证）

---
Status: DONE
