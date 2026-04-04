# SPEC-024: Capital Efficiency Improvement — Position Sizing Scale + T-Bill Overlay

## 目标

**What**：通过两个独立杠杆提升 $150k PM 账户的资金使用效率：
1. **Position Sizing Scale**：将 `bp_target` 从 5% 提升至 7.5%（NORMAL/LOW）、5%（HIGH_VOL），使每笔仓位在相同信号质量下占用更多账户资本
2. **T-Bill Overlay**：将闲置 margin cash 系统性存入短期国债（SGOV/BIL/货币市场），获取无风险利率收益

**Why**（Prototype 实证，`SPEC-024_bp_utilization.py`，2026-03-30）：

---

## 核心数据（Prototype 结果）

### 根本原因：信号频率是 binding constraint，不是 BP ceiling

| 指标 | 值 |
|------|---|
| 5yr 平均 BP 利用率（含零值天）| **3.5%** |
| 有仓位天的平均 BP 利用率 | 5.5% |
| 每日有仓位天占比 | 63.3% |
| 每日无仓位天占比（闲置）| **36.7%** |
| 每日 REDUCE_WAIT 信号天占比 | **65.8%** |

**决定性证据：BP ceiling 不是约束**：将 ceiling 从 25/35/50% 提升到 90%，结果完全不变（同 67 笔交易，同 Sharpe）。闲置资金来自"信号根本没有触发入场"，而非"ceiling 阻止了入场"。

**信号频率分析**：
- 连续同策略信号平均持续 6.3 天（dedup 只取第 1 天入场，后续 5.3 天信号被丢弃）
- HIGH_VOL 区间：spell_age > 30 天的有 87 天（spell throttle 生效）
- 5yr 仅 34.2% 的交易日有可执行信号

### Position Sizing 的关键性质：Sharpe 不变，PnL 线性放大

| 场景 | bp_target | 5yr PnL | MaxDD | Sharpe |
|------|-----------|---------|-------|--------|
| 基准（5% / 3.5%）| 5% | $33,156 | −$8,174 | **1.34** |
| 1.5× 放大（7.5% / 5%）| 7.5% | $49,365 | −$11,766 | **1.34** |
| 2× 放大（10% / 7%）| 10% | $66,312 | −$16,348 | **1.34** |
| 2.5× 放大（12% / 8%）| 12% | $78,984 | −$18,826 | **1.34** |

26yr 结论一致：Sharpe 在 1.50–1.51 之间无显著变化，PnL 和 MaxDD 均线性放大。

**这是期望行为**：Sharpe = mean_pnl / std_pnl，当所有仓位等比例放大时，分子分母同步放大，比值不变。这意味着放大仓位不改变策略的风险调整收益结构，只改变绝对规模。

### T-Bill Overlay：无风险附加收益

| 计算基础 | 年化值 |
|---------|-------|
| 闲置资金比例 | ~96.5%（1 − 3.5% 平均利用率）|
| 账户规模 | $150,000 |
| 经纪商支付比例（Schwab PM）| ~80% of SOFR（4.5% × 0.8 = 3.6%）|
| **年化增量 PnL** | **$5,211 / 年** |
| 5yr 累计 | $27,307 |

相当于 5yr 基准总 PnL（$33,156）的 **82% 额外叠加**，零风险，零策略修改。

### 多标的（SPY/QQQ/IWM）压力期相关性：不建议

| 标的 | 平静期（VIX ≤ 25）corr | 压力期（VIX > 25）corr | Δ |
|------|----------------------|----------------------|---|
| SPY  | 0.739 | 0.816 | +0.077 |
| QQQ  | 0.847 | 0.921 | +0.074 |
| IWM  | 0.842 | 0.927 | +0.085 |

**结论**：需要分散化时（高波动期），相关性反而最高（0.92–0.93）。在 SPX 基础上叠加 QQQ/IWM 期权不提供真正的风险分散，只是加倍了相同的 short-vol 暴露。

---

## 策略决策

### 决策一：Position Sizing Scale（1.5×）— 推荐实施

**提升幅度**：`bp_target_normal` 5% → **7.5%**，`bp_target_high_vol` 3.5% → **5%**，`bp_target_low_vol` 5% → **7.5%**

**理由**：
- Sharpe 不变（1.34 / 1.51），风险调整结构完全相同
- 5yr 总 PnL：$33k → $49k（+49%）
- MaxDD：−$8,174 → −$11,766（+44%，比 PnL 增幅小）
- 平均 BP 利用率：3.5% → 5.2%（仍远低于零售 PM 目标 20%）
- 对账户的直觉含义：一笔 BPS 仓位从占账户 7,500 美元升至 11,250 美元（spread 仍 $5 宽，只是合约数更多）

**MaxDD 容忍度检查**：MaxDD = −$11,766 ≈ 7.8% 账户回撤，在合理零售 PM 范围内（业界参考：单策略最大 20% 账户回撤）。

### 决策二：T-Bill Overlay — 强烈推荐，立即可执行

**操作**：将 Schwab PM 账户中的非保证金现金（idle cash）移入：
- **SGOV**（iShares 0-3 Month Treasury Bond ETF）或
- **BIL**（SPDR Bloomberg 1-3 Month T-Bill ETF）或
- **Schwab Value Advantage Money Fund（SWVXX）**

**效果**：年化 $5,000–5,500 无风险附加收益。无需修改任何策略代码，无需 Codex 实施。

**注意**：PM 账户中的 T-bill ETF 通常可以直接计为 marginable securities，不影响 BP 计算。

### 决策三：不实施

以下方案在研究后**不推荐**：

| 方案 | 原因 |
|------|------|
| 提升 BP ceiling | 完全无效（ceiling 不是 binding constraint）|
| 多标的期权（QQQ/IWM）| 压力期相关性 0.92–0.93，不提供分散化，反而叠加风险 |
| 缩短 DTE（14 DTE 策略）| 需要独立研究，gamma 风险特征不同，不是本 SPEC 范围 |
| 允许 dedup 内重复入场 | 破坏同策略 dedup 保护，增加叠加风险（SPEC-014 的设计初衷）|

---

## 接口定义

### `strategy/selector.py` — `StrategyParams` 默认值修改

```python
    bp_target_low_vol:  float = 0.10   # 10%（从 0.05 提升，2× scale）
    bp_target_normal:   float = 0.10   # 10%（从 0.05 提升，2× scale）
    bp_target_high_vol: float = 0.07   # 7%（从 0.035 提升，2× scale）
```

**仅修改三个默认值，其余逻辑不变。PM 决策：选用 2× 方案（非 1.5×）。**

bp_ceiling 无需变动（当前已设置 25–50%，远高于实际利用率）。

---

## 边界条件与约束

- 这是**无结构性风险**的改动：不改变入场信号、出场逻辑、hedge 结构、dedup/spell 保护
- Sharpe 不变（已 prototype 验证）
- MaxDD 线性放大，1.5× 场景下 MaxDD ≈ $12k（8% 账户），在零售 PM 合理范围
- T-bill overlay 与 options 策略完全独立，两者互不影响
- 若 PM 账户风险承受度降低（例如账户规模扩大到 $500k），可随时通过参数回调 bp_target

---

## 不在范围内

- 多标的期权扩展（需独立 SPEC，底层信号重新设计）
- 短 DTE 策略（需独立研究，gamma/vega 特征不同）
- 动态 bp_target（根据 VIX 水平调整每笔仓位大小）
- PM netting 建模（显式降低并行仓位总 BPR）

---

## Prototype

路径：`backtest/prototype/SPEC-024_bp_utilization.py`

---

## Review（Fast Path 部分）

- 结论：PASS（Fast Path，PM 批准 2× 方案）
- 修改：`strategy/selector.py` L74–76，三行默认值
- 验证：5yr Trades=67，Sharpe=1.34（不变），PnL=$66,312（+100%），MaxDD=−$16,348

## Review（追加实现部分）

- 结论：PASS
- 实现文件：`backtest/registry.py`、`backtest/portfolio.py`、`backtest/metrics_portfolio.py`、`strategy/selector.py`（追加字段）
- 核查要点：
  - `DailyPortfolioRow` 17 字段齐全 ✓
  - `PortfolioTracker._prev_marks` 存在，unrealized delta 计算正确 ✓
  - `compute_portfolio_metrics()` 含 `pnl_per_bp_day`，`to_dict()` 可用 ✓
  - `generate_experiment_id()` 实际长度 24 字符（SPEC AC#1 原写 20 为笔误，已修正）✓
  - `config_hash()` 用 `asdict()` + sorted JSON + sha256[:12] ✓
  - engine 集成：`PortfolioTracker` 实例化，`update_day()` 每日调用，`portfolio_rows` 写入 `BacktestResult` ✓
- 次要备注：`DailyPortfolioRow.bp_headroom` 存储 USD（`account_size - used_bp_usd`），SPEC 描述为"占 NAV 比例"，二者不一致。不影响任何下游计算（overlay 用独立 `bp_headroom_pct` 变量，attribution 不读此字段），可在后续迭代修正描述或单位。

---

## 验收标准（若 PM 批准）

1. `StrategyParams` 默认值修改：bp_target_normal = 0.075，bp_target_high_vol = 0.05，bp_target_low_vol = 0.075
2. `run_backtest(start_date="2021-01-01")` 验证：total_pnl 约 $49,000（1.49× 基准），Sharpe ≈ 1.34（不变）
3. `run_backtest(start_date="2000-01-01")` 验证：Sharpe ≈ 1.50（不变），MaxDD ≈ −$11,766

---

## 追加实现范围（2026-04-01，Daily Portfolio Infrastructure）

BP utilization Fast Path（bp_target 参数修改）已完成（DONE）。以下为 SPEC-024 研究同步确定的 daily portfolio 基础设施，需 Codex 实施：

### 新建文件 1：`backtest/registry.py`

参考 prototype：`backtest/prototype/SPEC024_registry_prototype.py`

```python
def generate_experiment_id(timestamp: datetime | None = None) -> str
    # 格式：EXP-YYYYMMDD-HHMMSS-XXXX（XXXX 为 4 位随机大写字母+数字）

def config_hash(params: StrategyParams) -> str
    # sha256(sorted JSON of dataclass fields)[:12]
```

### 新建文件 2：`backtest/portfolio.py`

参考 prototype：`backtest/prototype/SPEC024_portfolio_prototype.py`

#### `DailyPortfolioRow`（17 字段 dataclass）

```
date, start_equity, end_equity, daily_return_gross, daily_return_net,
realized_pnl, unrealized_pnl_delta, total_pnl, bp_used, bp_headroom,
short_gamma_count, open_positions, regime, vix,
cumulative_equity, drawdown, experiment_id
```

#### `PortfolioTracker`

```python
class PortfolioTracker:
    def __init__(self, initial_equity: float, experiment_id: str, account_size: float | None = None)
    def update_day(self, *, date, realized_pnl, open_position_marks: dict[str, float],
                   bp_used, bp_ceiling_usd, short_gamma_count, open_positions,
                   regime, vix) -> DailyPortfolioRow
    def get_rows(self) -> list[DailyPortfolioRow]
    def reset(self) -> None
```

- `_prev_marks: dict[str, float]`：`position_id → mark`，每日更新
- `drawdown`：`(cumulative_equity - peak_equity) / peak_equity`，≤ 0

### 新建文件 3：`backtest/metrics_portfolio.py`

参考 prototype：`backtest/prototype/SPEC024_metrics_portfolio_prototype.py`

```python
@dataclass
class PortfolioMetrics:
    ann_return, daily_sharpe, daily_sortino, daily_calmar,
    max_drawdown, cvar_95, worst_5d_drawdown, positive_months_pct,
    pnl_per_bp_day,   # SPEC-028 追加
    total_days, experiment_id

def compute_portfolio_metrics(rows: Sequence[DailyPortfolioRow]) -> PortfolioMetrics
```

公式：
- `daily_sharpe = mean(daily_return_net) / std(daily_return_net) * sqrt(252)`
- `cvar_95 = mean(bottom 5% daily returns)`
- `worst_5d_drawdown = min(rolling 5-day cumulative return)`
- `pnl_per_bp_day = total_net_pnl / sum(bp_used per day)` — 若 sum=0 则返回 0.0

### 修改文件：`strategy/selector.py` — `StrategyParams` 新增 1 个字段

```python
initial_equity: float = 100_000   # 回测初始净值，DailyPortfolioRow 基准
```

位置：spell throttle 字段之后，shock 字段之前（由 SPEC-025 添加）。

### 验收标准（追加部分）

1. `generate_experiment_id()` 格式：`EXP-YYYYMMDD-HHMMSS-XXXX`，长度 = 24 字符
2. `config_hash(StrategyParams())` 返回 12 字符 hex 字符串；相同参数哈希相同
3. `PortfolioTracker.update_day()` 后 `drawdown ≤ 0`
4. `compute_portfolio_metrics([])` 抛出 ValueError
5. `pnl_per_bp_day = 0.0` 当所有 `bp_used = 0`
6. `daily_sharpe > 0` 对单调上升净值曲线
7. engine 集成后，`run_backtest()` 返回结果携带 `portfolio_rows`

---
Status: DONE
