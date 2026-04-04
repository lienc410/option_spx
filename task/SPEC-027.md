# SPEC-027: Shock Engine Active Mode 校准 — Phase A Shadow Analysis

## 目标

在切换到 `shock_mode="active"` 之前，通过全历史 shadow mode 分析验证：
1. Would-be rejection rate 是否在合理区间（过高 → 入场过少；过低 → 守护无意义）
2. Breach 类型分布（core / incremental / bp_headroom）
3. Core shock 的 percentile 分布（为 budget 校准提供依据）

同时定义 Phase B A/B 对比的 Acceptance Criteria，作为 active mode 上线决策依据。

## 策略/信号逻辑

### Phase A：Shadow mode ShockReport 分析

核心分析维度：
- 年度 hit rate：哪些年份拦截率高（预期：2002、2008-09、2020、2022 显著更高）
- Regime hit rate：按 VIX regime 分组
- Breach 类型分布：core / incremental / bp_headroom 各占多少
- Percentile 分布：P50 / P95 / P99 of `abs(post_max_core_loss_pct)`

### 关键 Bug 修复（必须实现）

**错误做法**：
```python
any_breach_rate = (~shock_df["approved"]).sum() / n
```
shadow mode 中 `approved` 恒为 `True`，导致 would-be rejection rate = 0%，Phase A 完全失效。

**正确做法**：直接比较预算列：
```python
any_core_b = shock_df["post_max_core_loss_pct"].abs() > shock_df["budget_core"]
any_inc_b  = shock_df["incremental_shock_pct"].abs() > shock_df["budget_incremental"]
any_bp_b   = shock_df["bp_headroom_pct"] < 0.15
any_breach = (any_core_b | any_inc_b | any_bp_b).sum()
```

### Phase B：Active vs Shadow A/B Acceptance Criteria

| AC | 指标 | 阈值 |
|---|---|---|
| B1 | Trade count 下降 | ≤ 10%（active 不过度收窄入场） |
| B2 | PnL 变化 | 下降 ≤ 8% |
| B3 | MaxDD | 不劣于 shadow |
| B4 | CVaR 95% | 不劣于 shadow |

## 接口定义

### 新建文件：`backtest/run_shock_analysis.py`

参考 prototype：`backtest/prototype/SPEC027_run_shock_analysis_prototype.py`

#### `ShockAnalysisResult(dataclass)`
```python
total_entry_checks:       int
any_breach_count:         int
any_breach_rate:          float
core_breach_count:        int
incremental_breach_count: int
bp_headroom_breach_count: int
annual_hit_rate:          dict[str, float]   # year → rate
regime_hit_rate:          dict[str, float]   # regime → rate
p50_core_shock:           float
p95_core_shock:           float
p99_core_shock:           float
```

#### `compute_hit_rates(shock_records: list[dict]) -> ShockAnalysisResult`

- 输入：ShockReport 序列（dict 格式，包含 date, regime, post_max_core_loss_pct, incremental_shock_pct, bp_headroom_pct, budget_core, budget_incremental）
- **不得读取 `approved` 字段**（shadow mode 恒为 True）

#### `run_phase_a_analysis(start_date, end_date) -> ShockAnalysisResult`

- 调用 `run_backtest(..., collect_shock_reports=True)`
- engine 需支持 `collect_shock_reports` 参数（ShockReport 附加到回测结果）

### 依赖：`backtest/engine.py`

需新增 `collect_shock_reports: bool = False` 参数，回测结果对象需附加 `shock_reports: list[dict]`。

## 边界条件与约束

- Phase A 必须运行 shadow mode（不能改变回测结果）
- `bp_headroom_pct` 由 engine 在每日 BP 计算后附加到 ShockReport
- Phase B 由数据驱动决策，不在本 SPEC 范围内（由 PM 根据 Phase A 结果决定）

## 不在范围内

- 自动切换 active mode（Phase B 后由 PM 手动决策）
- 参数自动优化

## Prototype

路径：`backtest/prototype/SPEC027_run_shock_analysis_prototype.py`

## Review

- 结论：PASS
- 实现文件：`backtest/run_shock_analysis.py`
- 核查要点：
  - `compute_hit_rates()` 直接比较 `post_max_core_loss_pct`/`budget_core`、`incremental_shock_pct`/`budget_incremental`、`bp_headroom_pct`/`bp_headroom_budget`，不读 `approved` 字段 ✓（关键 bug fix 正确实现）
  - 单测验证：`approved=True` 的记录但预算超限时 `any_breach_count=1` ✓
  - `p50/p95/p99` 使用线性插值 percentile ✓
  - `annual_hit_rate` 和 `regime_hit_rate` 分组计算 ✓
  - `run_phase_a_analysis()` 调用 `run_backtest(..., collect_shock_reports=True)` ✓
  - `ShockAnalysisResult(0,0,0.0,0,0,0)` 对空输入 ✓

## 验收标准

1. `compute_hit_rates([])` 返回全零 `ShockAnalysisResult`
2. 所有 hit rate 计算不读 `approved` 字段
3. `annual_hit_rate` 中高 VIX 年（2008、2020）hit rate > 低 VIX 年（2013、2014）
4. `p95_core_shock > p50_core_shock > 0`
5. `any_breach_rate = (core_b | inc_b | bp_b).sum() / n`（三类 OR）
6. 运行 `run_phase_a_analysis("2000-01-01", "2026-03-31")` 不报错，输出摘要

---
Status: DONE
