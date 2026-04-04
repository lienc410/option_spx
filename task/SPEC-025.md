# SPEC-025: Portfolio Shock-Risk Engine

## 目标

在入场守护链中加入基于场景的组合 tail-risk 预算控制，替代纯 count-based rule（`max_short_gamma_positions`）。用 NAV 百分比表达极端损失上限，并提供 shadow/active 双模式支持分阶段上线。

## 策略/信号逻辑

### 8 个标准场景

| 场景 | 类型 | Spot_pct | VIX_shock_pt | 用途 |
|---|---|---:|---:|---|
| S1 mild_down | Core | -2% | +5pt | 预算控制（S1–S4） |
| S2 mod_down | Core | -3% | +8pt | 预算控制 |
| S3 severe_down | Core | -5% | +15pt | 预算控制 |
| S4 vol_spike | Core | 0% | +10pt | 预算控制 |
| S5 mild_up | Tail | +2% | -3pt | 仅记录，v1 不纳入预算 |
| S6 rally | Tail | +5% | -8pt | 仅记录 |
| S7 vol_normalize | Tail | +3% | -5pt | 仅记录 |
| S8 term_inversion | 独立 | -2% | +5pt | 与 S1 数值相同，独立记录（为后续 term structure 分析保留） |

- **Core（S1–S4）**：用于计算 `pre_max_core_loss_pct` 和 `post_max_core_loss_pct`，驱动预算判断。
- **Tail（S5–S7）**：写入报告，首版不纳入 budget gate。
- **S8**：独立记录，不参与 budget。

### Sigma 规则

```python
sigma = max(0.05, min(2.00, current_vix / 100))
```

**必须使用当日 VIX**，不得使用 `pos.entry_sigma`。理由：shock engine 目标是"当前 sigma 水平下 spot 再移动的损失"，用历史入场 sigma 会系统性低估当前 vega 敏感度。

### 增量风险计算

```python
incremental_shock_pct = post_max_core_loss_pct - pre_max_core_loss_pct
```

衡量候选仓位的边际 core-scenario 贡献。

### 运行模式

- `shock_mode = "shadow"`（默认）：始终 `approved = True`，ShockReport 写入审计日志。
- `shock_mode = "active"`：若 `abs(post_max_core_loss_pct) > budget_core` 或 `abs(incremental_shock_pct) > budget_incremental`，则 `approved = False`，记录 `reject_reason`。

## 接口定义

### 新建文件：`backtest/shock_engine.py`

参考 prototype：`backtest/prototype/SPEC025_shock_engine_prototype.py`

#### `ShockScenario(frozen dataclass)`
```python
name: str
spot_shock: float   # fractional SPX move
vix_shock: float    # additive VIX points
is_core: bool       # True → S1-S4, included in budget
```

#### `LegSnapshot(dataclass)`
```python
option_type: str    # "put" | "call"
strike: float
dte: int
contracts: float    # negative = short
current_spx: float
```

#### `PositionSnapshot(dataclass)`
```python
strategy_key: str
is_short_gamma: bool
legs: list[LegSnapshot]
```

#### `ShockReport(dataclass)`
```python
date: str
nav: float
mode: str                      # "shadow" | "active"
pre_scenarios: dict[str, float]   # scenario_name → portfolio P&L ($)
pre_max_core_loss_pct: float      # min(S1-S4 pnl) / nav  (≤ 0)
post_scenarios: dict[str, float]  # after adding candidate
post_max_core_loss_pct: float
incremental_shock_pct: float      # post - pre
budget_core: float
budget_incremental: float
approved: bool
reject_reason: str | None
sigma_used: float
```

#### `run_shock_check()`
```python
def run_shock_check(
    *,
    positions: list[PositionSnapshot],
    current_spx: float,
    current_vix: float,
    date: str,
    params: StrategyParams,
    candidate_position: PositionSnapshot | None = None,
    account_size: float = 100_000,
    is_high_vol: bool = False,
) -> ShockReport
```

### 修改文件：`strategy/selector.py` — `StrategyParams` 新增 6 个字段

```python
shock_mode:                  str   = "shadow"
shock_budget_core_normal:    float = 0.0125
shock_budget_core_hv:        float = 0.0100
shock_budget_incremental:    float = 0.0040
shock_budget_incremental_hv: float = 0.0030
shock_budget_bp_headroom:    float = 0.15
```

### 修改文件：`backtest/engine.py` — 入场守护链新增 Step 7

在 SPEC-017 guards 之后（Steps 1–6 之后）插入：

```
Step 7: Shock gate check (active mode only)
  - Build PositionSnapshot list from open_positions
  - Build candidate PositionSnapshot from proposed trade
  - Call run_shock_check(positions, candidate, params, is_high_vol)
  - If shock_mode == "active" and not report.approved: skip entry, log reject_reason
  - Always record ShockReport to shock_log (for Phase A analysis)
```

**注意**：Step 7 仅在有候选入场时运行。每日独立 book shock 计算在 Step 0（见 SPEC-026）。

## 边界条件与约束

- Precision B：repricing 用 BS，无 bid-ask spread（乐观估计）
- `dte = 0` 时 clamp 至 1（避免 BS 退化）
- `candidate_position = None` 时，`post_* = pre_*`（纯 book-only 查询）
- bp_headroom 超限由 engine 在 BP 检查后设置，不在 `run_shock_check` 内部处理
- shadow mode 下 `approved` 恒为 `True`（Phase A 分析用预算列直接比较，不读 `approved`）

## 不在范围内

- S5–S7 Tail scenarios 纳入 budget 控制（v2）
- 希腊字母（delta/vega）aggr limits（独立 SPEC）
- BP headroom breach 内部判断（由 engine 负责）

## Prototype

路径：`backtest/prototype/SPEC025_shock_engine_prototype.py`

## Review

- 结论：PASS
- 实现文件：`backtest/shock_engine.py`、`strategy/selector.py`（6 个字段）、`backtest/engine.py`（Step 0 + Step 7）
- 核查要点：
  - 8 个场景：S1-S4（is_core=True），S5-S7（Tail），S8（独立），完全符合 SPEC ✓
  - `sigma = max(0.05, min(2.0, current_vix/100))`，使用当日 VIX 而非 entry_sigma ✓
  - `ShockReport` 含 `pre_scenarios`、`post_scenarios`、`pre/post_max_core_loss_pct`、`incremental_shock_pct`、`budget_core`、`budget_incremental`、`nav`、`mode`、`approved`、`reject_reason`、`sigma_used` ✓
  - shadow 模式恒 `approved=True`；active 模式超预算时 `approved=False` + `reject_reason` ✓
  - engine Step 0：`run_shock_check(candidate_position=None)` 在入场决策之前独立运行 ✓
  - engine Step 7：候选入场时再次调用 `run_shock_check`（含 candidate） ✓
  - `collect_shock_reports=True` 时 ShockReport 携带 `regime`、`bp_headroom_pct`、`bp_headroom_budget` ✓
  - `to_dict()` 方法存在，供 `shock_reports` 序列化 ✓

## 验收标准

1. `run_shock_check(positions=[], ...)` 返回 `pre_max_core_loss_pct == 0.0`
2. `sigma_used == max(0.05, min(2.00, current_vix / 100))`，VIX=20 时 sigma=0.20
3. 单个 short put 仓位在 S1–S4 下 `pre_max_core_loss_pct < 0`（损失）
4. `shock_mode="active"` + 超预算时 `approved=False` 且 `reject_reason` 非空
5. `shock_mode="shadow"` 时 `approved` 恒为 `True`
6. `len(pre_scenarios) == 8`（8 个场景均计算）
7. engine 集成后，`run_backtest()` 运行不报错（shadow mode 下结果与无 shock engine 版本相同）

---
Status: DONE
