# SPEC-028: 资本效率指标与 PnL 归因

## 目标

在 daily portfolio metrics 之上增加两个归因视角，回答"哪个策略、哪个 regime 在消耗多少 BP 的情况下贡献了多少 PnL"。引入 `pnl_per_bp_day` 作为资本效率的核心衡量指标。

## 策略/信号逻辑

### `pnl_per_bp_day`（资本效率）

```python
pnl_per_bp_day = total_net_pnl / sum(daily_used_bp)
```

- 分母 = 每日 BP 占用的累计和（$ × 天）
- 消除持仓时长对胜率的扭曲
- 若 Diagonal 的 `pnl_per_bp_day` 显著低于 BPS，说明其长期占用 BP 但回报偏低

### `compute_strategy_attribution()`（11 列）

按 `trade.strategy` 分组，每策略一行：

| 列 | 说明 |
|---|---|
| strategy | 策略名 |
| trade_count | 交易数 |
| win_rate | 盈利交易占比 |
| gross_pnl | exit_pnl 之和 |
| net_pnl | 同 gross（Precision B 无 commission） |
| mean_pnl_per_trade | 每笔平均 PnL |
| median_pnl_per_trade | 每笔中位 PnL |
| mean_hold_days | 平均持仓天数（dte_at_entry - dte_at_exit） |
| total_bp_days | sum(total_bp × hold_days)（$ × 天） |
| pnl_per_bp_day | net_pnl / total_bp_days |
| pct_of_total_pnl | 本策略占全部策略 net_pnl 的比例 |

### `compute_regime_attribution()`（8 列）

按 `DailyPortfolioRow.regime` 分组，每 regime 一行：

| 列 | 说明 |
|---|---|
| regime | VIX regime 标签 |
| day_count | 该 regime 的交易日数 |
| pct_of_trading_days | day_count / 总交易日 |
| mean_daily_return_net | 平均日度净收益率 |
| regime_sharpe | 该 regime 内的年化 Sharpe（√252 标准化） |
| mean_bp_utilization | 平均 bp_used / account_size |
| total_net_pnl_contribution | sum(daily_total_pnl) |
| pct_of_total_pnl | 该 regime 占全部日度 pnl 的比例 |

## 接口定义

### 新建文件：`backtest/attribution.py`

参考 prototype：`backtest/prototype/SPEC028_attribution_prototype.py`

```python
def compute_strategy_attribution(trades: Sequence[Trade]) -> list[StrategyAttributionRow]
def compute_regime_attribution(rows: Sequence[DailyPortfolioRow], account_size: float = 100_000) -> list[RegimeAttributionRow]
def print_strategy_attribution(rows: list[StrategyAttributionRow]) -> None
def print_regime_attribution(rows: list[RegimeAttributionRow]) -> None
```

### 修改文件：`backtest/metrics_portfolio.py`

在 `compute_portfolio_metrics()` 中新增：

```python
pnl_per_bp_day = total_net_pnl / sum(r.bp_used for r in rows)
# 若 sum(bp_used) == 0: pnl_per_bp_day = 0.0
```

`PortfolioMetrics` dataclass 新增字段 `pnl_per_bp_day: float`。

**注**：`backtest/metrics_portfolio.py` 为本次新建文件（SPEC-024），Codex 在实现时一并包含此字段。

## 边界条件与约束

- `total_bp_days = 0`（如全程无任何仓位）时 `pnl_per_bp_day = 0.0`
- `total_pnl = 0` 时 `pct_of_total_pnl` 各行均为 0.0
- 策略归因结果按 `net_pnl` 降序排列
- Regime 归因结果按 `total_net_pnl_contribution` 降序排列

## 不在范围内

- 按 expiry cycle 归因
- 日内 intraday 归因

## Prototype

路径：`backtest/prototype/SPEC028_attribution_prototype.py`

## Review

- 结论：PASS
- 实现文件：`backtest/attribution.py`、`backtest/metrics_portfolio.py`（`pnl_per_bp_day`）
- 核查要点：
  - `StrategyAttributionRow` 11 列齐全 ✓
  - `RegimeAttributionRow` 8 列齐全 ✓
  - `pnl_per_bp_day = total_net_pnl / sum(bp_days)`，`bp_days=0` 时返回 0.0 ✓
  - `compute_strategy_attribution([])` 返回空列表（无需处理 total=0 的除法）✓
  - `regime_sharpe` 用 `sqrt(252)` 标准化 ✓
  - `pct_of_trading_days` 各行之和 = 1.0（所有 regime 天数覆盖全样本）✓
  - `PortfolioMetrics` 含 `pnl_per_bp_day` 字段，`to_dict()` 可序列化 ✓

## 验收标准

1. `compute_strategy_attribution([])` 返回空列表
2. 单一策略所有交易：`pct_of_total_pnl == 1.0`
3. `pnl_per_bp_day = total_net_pnl / sum(trade.total_bp * hold_days for each trade)`
4. `compute_regime_attribution(rows)` 中各行 `pct_of_trading_days` 之和 == 1.0
5. `regime_sharpe` 计算用 `sqrt(252)` 标准化
6. `print_strategy_attribution` / `print_regime_attribution` 输出对齐表格，不报错

---
Status: DONE
