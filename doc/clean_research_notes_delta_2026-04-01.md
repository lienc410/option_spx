# Research Notes Delta - 2026-04-01

**说明**：本文件为增量文档，仅记录 2026-04-01 新增的研究发现。不重复已有章节（§1–§31）的内容。如需参考已有章节，请见 `doc/research_notes.md`。

**承接章节**：§31 “Concentrated Exposure & Stress Period Analysis” (2026-03-30)

## §32 Daily Portfolio Metrics - 从 Trade-Level 到 Daily Portfolio View（SPEC-024, 2026-04-01）

**Status：已实施**

### 研究问题

Sharpe 和 Calmar 之前基于 trade-level 计算：每笔交易作为独立观测单元，用其 PnL 构建收益序列。在单仓串行运行时，这是合理近似；但在多仓并行时，trade-level metrics 会系统性低估相关性、高估多样化效果。

具体后果：

- 两笔重叠持仓同时在 VIX spike 期间亏损，trade-level 会把它计算为“两次独立事件”；但实际它们是同一个市场日、同一次冲击。
- 用 trade-level Sharpe 作为下一轮 signal 设计的驱动指标，会产生系统性误判。
- 优化目标与真实组合风险脱节。

### 核心发现

1. 多仓并行时，真实组合波动来自**每日净值变化**，而不是每笔交易独立结算。重叠仓位期间的相关性决定真实 drawdown 深度。
2. 所有组合层风险控制（shock budget、overlay、资金利用率）都需要 **daily book view**。入场守护链（SPEC-025/026）不能基于 trade-level 序列做实时判断——系统需要知道“今天的 portfolio 在各场景下会损失多少”。
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

- `daily_sharpe`
- `daily_sortino`
- `daily_calmar`
- `cvar_95`
- `worst_5d_drawdown`
- `positive_months_pct`

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
- 两套指标数字差异主要来自：
  1. haircut 应用方式不同；
  2. daily metrics 使用 net return 序列，而非 trade PnL 聚合。

### Experiment Registry

引入 `generate_experiment_id()`，格式：

`EXP-YYYYMMDD-HHMMSS-XXXX`（`XXXX` 为 4 位随机字符）

- `config_hash = sha256(params JSON)[:12]`
- 参数完全确定时产生相同哈希，支持去重和结果回放。

**所有回测输出强制关联 `experiment_id`**，保证：

- 每次实验可精确复现（通过 `config_hash` 定位参数）
- 多版本结果可对比（`EXP-baseline` vs `EXP-full` 等）
- 审计日志不丢失（shock report、overlay log 均携带 `experiment_id`）

实现文件：`backtest/registry.py`

---

## §33 Portfolio Shock-Risk Engine - 基于场景的组合风险预算（SPEC-025, 2026-04-01）

**Status：已实施**

### 研究问题

现有系统的入场控制依赖 count-based rule（`max_short_gamma_positions = 3`）：只要 short-gamma 仓位数不超过 3，就允许入场。这个规则无法区分同样是“3 个 short-gamma 仓位”但风险截然不同的情况：

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
- S8 与 S1 数值相同但独立记录：SPEC 明确要求分离，后续可调整 spot/vol 参数以专门捕捉期限结构反转效应。

### 关键实现细节

#### Sigma 使用当日 `VIX / 100`，而不是 `pos.entry_sigma`

设计原因：shock engine 的目标是“在**当前 sigma 水平**下，如果 spot 进一步移动，仓位会损失多少”。若使用历史入场 sigma，会系统性低估当前的期权敏感度。

```python
sigma = current_vix / 100.0
sigma = max(0.05, min(2.00, sigma))
```

- clamp 用于防止 BS 公式数值退化。
- 例：入场时 VIX = 15，今日 VIX = 25，若仍用 15% sigma 重估，会明显低估当前 vega 损失。

#### 增量风险贡献

```python
incremental_shock_pct = post_max_core - pre_max_core
```

只衡量加入候选仓位后的**边际风险贡献**，而不是 portfolio 绝对风险。这允许在组合已有低风险仓位时，接受边际贡献较小的新仓位。

#### 运行模式

- **shadow 模式（默认）**：始终 `approved = True`，仅记录审计日志（`ShockReport` 写入 CSV）。不阻断任何交易，用于观察历史样本中 shock 分布。
- **active 模式**：若 `abs(post_max_core) > budget`，则 `approved = False`，阻断入场，并记录 `reject_reason`。

### 风险预算（默认值）

| 参数 | Normal Regime | HIGH_VOL Regime |
|---|---:|---:|
| `shock_budget_core_normal` | 1.25% NAV | - |
| `shock_budget_core_hv` | - | 1.00% NAV |
| `shock_budget_incremental` | 0.40% NAV | - |
| `shock_budget_incremental_hv` | - | 0.30% NAV |
| `shock_budget_bp_headroom` | 15% NAV | 15% NAV |

HIGH_VOL regime 使用更严格预算，原因是 HIGH_VOL 时实际相关性上升（共同对 VIX 敏感），原本分散的仓位在压力下相关性趋近于 1。

### `ShockReport` 数据结构

```python
@dataclass
class ShockReport:
    date: str
    nav: float
    pre_scenarios: dict[str, float]
    pre_max_core_loss_pct: float
    post_scenarios: dict[str, float]
    post_max_core_loss_pct: float
    incremental_shock_pct: float
    budget_core: float
    budget_incremental: float
    approved: bool
    reject_reason: str | None
    mode: str
```

说明：

- `pre_scenarios`：8 个场景的 pre-entry 损失（$）
- `pre_max_core_loss_pct`：S1–S4 最差损失，占 NAV
- `post_scenarios`：加入候选仓位后的 8 场景损失
- `mode`：`"shadow"` 或 `"active"`

实现文件：`backtest/shock_engine.py`

---

## §34 VIX Acceleration Overlay - 组合层加速度防御状态机（SPEC-026, 2026-04-01）

**Status：已实施**

### 研究问题

Senior quant review（§8.24–§8.25）指出：**单笔 panic stop 无效**（已有实证）≠ 组合层 overlay 无价值。二者核心区别如下：

| 维度 | 单笔 panic stop | 组合层 overlay |
|---|---|---|
| 触发时机 | 单笔仓位已大幅亏损后平仓 | 市场加速阶段，先于大亏损触发 |
| 执行成本 | 最差价差时点机械全平，成本最高 | 分级响应，先冻结新风险，再评估 trim |
| 信号质量 | 单仓 PnL（滞后指标） | `vix_accel × book_shock`（前瞻组合指标） |
| 历史实证 | 2015 / 2020 panic stop 期望为负 | L2 trim 在 2015 VIX spike 显著有效（§35） |

结论：**废除单笔 panic stop，在组合层引入 VIX 加速度驱动的分级状态机。**

### 信号选择

放弃 `term_inversion`（VIX3M 无完整历史数据），使用以下 4 个信号：

1. `vix_accel_3d = (VIX_t / VIX_{t-3}) - 1`：市场加速度。3 日窗口平衡了噪声和响应速度。
2. `book_core_shock`：当日已有仓位在 8 个场景下的最差 core loss（来自 shock engine，每日独立计算），衡量“当前 portfolio 有多脆弱”。
3. `vix`：绝对水位（Level 4 emergency 保护）。
4. `bp_headroom`：资金紧急状态（Level 4 兜底）。

### 关键设计决定：`book_core_shock` 信号路径修复

**初始实现的缺陷**：`book_core_shock` 从 `ShockReport` 取值，而 `ShockReport` 只在有候选入场时生成。缺陷后果：

- Level 1 freeze 触发
- 当日无入场候选
- 无 `ShockReport` 生成
- `book_core_shock = 0`（默认值）
- L2 的 AND 条件永远不满足
- L2 永远不触发

**修复方案**：在主循环中独立计算每日 existing portfolio shock，不依赖入场路径：

```python
# 每日收盘后，无论有无候选入场，都计算现有仓位的 shock
if positions:
    sc_results = compute_portfolio_shock(
        positions, spx, sigma, SCENARIOS, nav
    )
    _daily_book_shock = max_core_loss_pct(sc_results)
else:
    _daily_book_shock = 0.0

overlay_result = compute_overlay_signals(
    vix=vix,
    vix_3d_ago=vix_3d_ago,
    book_core_shock=_daily_book_shock,
    bp_headroom=bp_headroom,
    params=params,
)
```

该修复使 L2 在 2015 VIX spike 等真实压力事件中可以正常触发（§35 实验验证）。

### 行动分级（状态机）

| Level | 触发条件 | 逻辑 | 行动 |
|---|---|---|---|
| L0 Normal | - | - | 正常运行，无限制 |
| L1 Freeze | `accel_3d > 15%` OR `vix >= 30` | OR | 禁止新开 short-vol 仓位 |
| L2 Freeze + Trim | `accel_3d > 25%` AND `book_core_shock >= 1%` | AND | Freeze + 强制平当前全部仓位 |
| L3 Freeze + Trim + Hedge | `accel_3d > 35%` AND `book_core_shock >= 1.5%` | AND | v1：同 L2；v2：额外开 long put spread hedge |
| L4 Emergency | `vix >= 40` OR `book_core_shock >= 2.5%` OR `bp_headroom < 10%` | OR | 强制退出所有仓位 |

#### 设计逻辑

- **L2/L3 使用 AND 条件**：防止 VIX 正常上升但组合风险可控时误触。例如完全由 long-vega 策略构成时，VIX 上升可能反而有利。
- **L4 使用 OR 条件**：任何一个极端信号出现时，立即强制保护，不等待其他条件同时满足。

### `StrategyParams` 中的 Overlay 参数（10 个）

| 参数 | 默认值 | Level |
|---|---:|---|
| `overlay_mode` | `"disabled"` | - |
| `overlay_freeze_accel` | 0.15 | L1 |
| `overlay_freeze_vix` | 30.0 | L1 |
| `overlay_trim_accel` | 0.25 | L2 |
| `overlay_trim_shock` | 0.01 | L2 |
| `overlay_hedge_accel` | 0.35 | L3 |
| `overlay_hedge_shock` | 0.015 | L3 |
| `overlay_emergency_vix` | 40.0 | L4 |
| `overlay_emergency_shock` | 0.025 | L4 |
| `overlay_emergency_bp` | 0.10 | L4 |

实现文件：`signals/overlay.py`

---

## §35 Overlay 5-Version 对照回测（2026-04-01）

**Status：实验完成**

### 实验设计

按 senior quant review §8.24–§8.25 的要求，对比 5 个 overlay 配置在 2000–2026 全历史 + 4 个压力窗口的表现。实验均使用 daily portfolio metrics（SPEC-024），每次运行关联独立 `experiment_id`。

### 5 组实验配置

| 实验名 | overlay_mode | 说明 |
|---|---|---|
| `EXP-baseline` | `disabled` | 原始系统，无任何 overlay |
| `EXP-freeze` | `active`, 仅 L1 | 只冻结，不 trim |
| `EXP-freeze_trim` | `active`, L1 + L2 | 冻结 + trim |
| `EXP-freeze_hedge` | `active`, L1 + L3 | 冻结 + trim + hedge（v1 实际同 trim） |
| `EXP-full` | `active`, L1 + L2 + L3 + L4 | 全层级开启 |

所有实验使用相同信号参数（SPEC-015 spell throttle、SPEC-017 synthetic IC block、SPEC-025 shock engine shadow mode），仅 overlay 层不同。

### 全历史指标（2000-01-03 至 2026-03-31）

| 配置 | Ann.Ret | Sharpe | Calmar | MaxDD | CVaR95 | 交易数 |
|---|---:|---:|---:|---:|---:|---:|
| EXP-baseline | 3.73% | 0.70 | 0.24 | -15.35% | -0.837% | 354 |
| EXP-freeze | 3.77% | 0.70 | 0.30 | -12.63% | -0.835% | 331 |
| EXP-freeze_trim | 4.25% | 0.85 | 0.34 | -12.38% | -0.747% | 348 |
| EXP-freeze_hedge | 3.90% | 0.74 | 0.31 | -12.59% | -0.808% | 333 |
| **EXP-full** | **4.26%** | **0.86** | **0.35** | **-12.22%** | **-0.736%** | **348** |

注：`EXP-baseline` 与 `strategy_status_2026-03-30.md` 中的历史基准（26yr Sharpe 1.54）使用不同计量基础：前者是 daily portfolio metrics，后者是 trade-level metrics。两者不可直接比较，但方向一致（均显示系统有正期望）。

### 压力窗口 Max Drawdown 对比

| 配置 | 2011 EU债务危机 | 2015 VIX spike | 2020 COVID | 2022 熊市 |
|---|---:|---:|---:|---:|
| EXP-baseline | -2.78% | -2.13% | -4.45% | -5.59% |
| EXP-freeze | -2.78% | -2.13% | -4.45% | -5.59% |
| EXP-freeze_trim | -0.10% | -0.46% | -4.13% | -5.20% |
| EXP-freeze_hedge | -0.15% | -0.52% | -4.18% | -5.25% |
| **EXP-full** | **-0.10%** | **-0.46%** | **-4.13%** | **-5.20%** |

注：`EXP-freeze` 在 2011/2015 无改善——这两个事件的 VIX 加速度超过 L2 阈值但未触发实际 trim，纯 freeze 无法保护已开仓位；L2 trim 触发后才有显著改善。

### 验收标准（VS EXP-baseline，EXP-full）

| 验收项 | 门限 | EXP-full 实测 | 通过 |
|---|---:|---:|---|
| MaxDD 改善 | ≥10% | 20.4%（15.35% → 12.22%） | 是 |
| CVaR95 改善 | ≥10% | 12.1%（0.837% → 0.736%） | 是 |
| 压力窗口 drawdown 改善 | 明显改善 | 2011 / 2015 均显著改善 | 是 |
| 年化收益不降 | ≥92% of baseline | +14%（3.73% → 4.26%） | 是 |
| 交易数降幅 | ≤10% | -1.7%（354 → 348） | 是 |

### 为什么 Freeze + Trim 优于纯 Freeze（L2 的价值）

1. **BP 释放与再入场**：Trim 后 BP 释放，VIX 回落后可再次入场。`EXP-freeze_trim` 交易数 348 > `EXP-freeze` 的 331，说明 trim 实际增加了优质入场机会，而不是简单减少交易。
2. **已开仓位期望值转负**：L2 条件为 `accel_3d > 25% AND shock >= 1%`。此时 VIX 正在加速上升，且当前仓位在 core scenarios 下已承受较大潜在损失，继续持有的期望损失高于及时 trim 的执行成本。
3. **触发时机并非最差点**：L2 的 3 日加速度阈值通常早于 VIX 绝对高位极值，trim 时 bid-ask 往往仍可接受。

### 2020 COVID 效果有限的原因

COVID 期间 VIX 上升速度异常：最剧烈阶段集中在约 5 个交易日内，3 日窗口仍有一定滞后；L4 emergency 触发时，部分损失已不可避免。

改进方向（待 v2）：

- 增加 `vix_accel_1d` 快速响应路径，专门处理 COVID 类极速崩溃事件。

### 推荐生产配置

**`EXP-full`**（`overlay_mode = "active"`，所有阈值使用 SPEC-026 默认值）

理由：

- `EXP-full` 与 `EXP-freeze_trim` 的全历史指标几乎相同（Sharpe 0.86 vs 0.85，MaxDD 12.22% vs 12.38%），但 L4 emergency 提供了额外的极端事件保护，且对长期表现几乎无成本。
- L3 hedge（v2 实现后）将进一步拉开 `EXP-full` 与 `EXP-freeze_trim` 的差异。

### 未解决问题

1. **L3 hedge 实盘实现（v2）**：当前 v1 中 L3 实际执行与 L2 相同，真正的 long put spread hedge 仍待实现并验证。
2. **`vix_accel_1d` 用于 L4 fast-path**：提升对 COVID 类极速崩溃的响应能力，需要额外 backtest 验证以避免日内噪声误触发。
3. **多仓引擎下的 trim 精细化**：当前 L2/L4 触发时为“全平所有仓位”；多仓扩展后可改为“优先关闭 shock 贡献最高的仓位”，提高资本效率。

---

## §36 Shock Engine Active Mode 校准与 A/B 验证（SPEC-027, 2026-04-02）

**Status：已实施**

### 研究问题

SPEC-025 实现的 Shock Engine 目前默认运行于 shadow mode：所有风险报告都会计算并输出，但不阻止入场或强制退出。要切换为 active mode，需要先验证：

> 在 shadow mode 下，如果 shock gate 是 active 的，拦截率是多少？分布如何？

只有当 hit rate 落在合理区间（过高则系统入场过少，过低则守护无意义），active mode 才适合上线。

### Phase A：Shadow 模式下的 ShockReport 分析

核心分析维度：

1. **Hit rate（年度分布）**：哪些年份 shock gate 会频繁拦截？高 VIX 年（2002、2008–09、2020、2022）是否显著更高？
2. **Breach type 分布**：`post_max_core_loss_pct` 超预算、`incremental_shock_pct` 超预算、`bp_headroom_pct < 15%` 三类 breach 各占多少？
3. **Percentile 分布**：shock 数值的中位数、P95、P99，为 budget 校准提供依据。

### 关键实现问题（Fast Path 修复）

`compute_hit_rates()` 中原有 bug：

```python
any_breach_rate = (~shock_df["approved"]).sum()
```

但 shadow mode 中 `approved` 永远为 `True`，导致 would-be rejection rate 恒为 0%，完全失去 Phase A 的意义。

**修复方案**：改用预算列直接比较：

```python
any_core_b = shock_df["post_max_core_loss_pct"].abs() > shock_df["budget_max_core"]
any_inc_b = shock_df["incremental_shock_pct"].abs() > shock_df["budget_incremental"]
any_bp_b = shock_df["bp_headroom_pct"] < 0.15
any_breach = (any_core_b | any_inc_b | any_bp_b).sum()
```

### Phase B：Active vs Shadow A/B

#### Acceptance Criteria（active mode）

| AC | 指标 | 阈值 |
|---|---|---|
| B1 | Trade count 下降 | ≤10%（active 不过度收窄入场） |
| B2 | PnL 变化 | 下降 ≤8%（守护成本可接受） |
| B3 | MaxDD | 不劣于 shadow |
| B4 | CVaR（5%） | 不劣于 shadow |

---

## §37 资本效率指标与 PnL 归因（SPEC-028, 2026-04-02）

**Status：已实施**

### 研究问题

仅有 daily portfolio metrics（Sharpe、MaxDD 等）仍然只回答结果问题，无法回答：

- 哪个策略类型贡献了 PnL？
- 哪个 regime 下系统最赚钱？
- 资本是否被高效利用？

### 核心新增指标

#### `pnl_per_bp_day`（资本利用率调整后收益）

```python
pnl_per_bp_day = total_net_pnl / sum(daily_used_bp)
```

单位：每占用 1 美元保证金 1 天获得的净 PnL（美元）。该指标同时把持仓时间和资金占用纳入分母，消除“长时间持有低效仓位”对胜率的扭曲。

#### `compute_strategy_attribution()`

按策略类型汇总（11 列），包括：

- trade_count
- win_rate
- net_pnl
- mean_pnl_per_trade
- pnl_per_bp_day
- 等

#### `compute_regime_attribution()`

按 VIX regime 汇总（8 列），包括：

- day_count
- pct_of_trading_days
- mean_daily_return_net
- regime_sharpe
- mean_bp_utilization
- total_net_pnl_contribution
- 等

### 研究意义

`pnl_per_bp_day` 是衡量策略**资本效率**的关键指标。若 Diagonal 的 `pnl_per_bp_day` 显著低于 BPS，说明其长期占用 BP 但回报偏低。结合 §38 的 OOS 验证，可量化 Diagonal 在 OOS 期的资本效率劣化，并为 trend signal 改进（§40）提供明确数值目标。

---

## §38 出样本（OOS）验证：IS=2000-2019 / OOS=2020-2026（SPEC-029, 2026-04-02）

**Status：已实施**

### 研究设计

采用**单次全历史回测 + 日期过滤**，而不是两次独立回测，以避免 OOS 回测缺少 IS 期仓位状态所带来的 cold-start artifact。

### 5 张对比报表

| 报表 | 内容 |
|---|---|
| R1 | Full / IS / OOS 的 Ann.Ret、Sharpe、Calmar、MaxDD、CVaR、Trades |
| R2 | `EXP-full` vs `EXP-baseline` 的 delta，按三个窗口分列 |
| R3 | OOS Acceptance Criteria：Sharpe > 0 / MaxDD improvement ≥5% / PnL retention ≥85% / Trade drop ≤15% |
| R4 | OOS 期（2020–2026）策略归因：`pnl_per_bp_day by strategy` |
| R5 | OOS 期 8 个 Regime 视角：Sharpe / BP utilization by VIX regime |

---

## §39 SPX 趋势信号深度研究：Alternative Signal 评估（2026-04-02）

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

不推荐方向的根本原因：

- ROC / MACD 的信号逻辑（动量越差越 bearish）与 short-vol 策略“修正是机会”的框架方向不一致。
- Swing Structure 往往在市场已经下跌 10–15% 后才确认，无时效性，且需要更多 lookback 参数，过拟合风险高。

---

## §40 ATR-Normalized Entry Gate + Persistence Exit Filter（SPEC-020, 2026-04-02）

**Status：实施中（RS-020-1 FAIL，待 RS-020-2）**

### 问题根因

固定 1% band 在不同波动环境下含义不一致：

- VIX = 12 时，等效门槛过宽，不易触发
- VIX = 30 时，等效门槛过窄，过于容易触发

ATR 标准化后：

```python
gap_sigma = (SPX - MA50) / ATR(14)
```

阈值在不同 VIX 环境下具有更一致的语义。

Persistence filter 方案：

- 用 `bearish_streak >= 3` 触发 `trend_flip`
- 代替“单日 BEARISH 即翻转”
- `streak` 在日循环顶层维护

### §7 前置研究结果

| 参数 | 初始假设 | 实证修正 |
|---|---|---|
| `ATR_THRESHOLD` | 1.0 | 1.0（确认；gap_sigma 分布与原 +1% band 最接近） |
| `BEARISH_PERSISTENCE_DAYS` | 5 | **3**（`streak = 3` 为条件概率拐点；相比 5，额外延迟不值得） |

### ChatGPT Review 关键决策

**采纳：**

- 强制做 4-way ablation（`EXP-baseline / EXP-atr / EXP-persist / EXP-full`）
- 按 regime 分层报告
- 做 3×3 稳健性参数网格

**驳回：**

- “信号语义改变是缺陷”这一说法不成立。ATR normalization 将信号变为“状态依赖过滤器”是**设计意图**，且已在研究设计中明确说明。

### 当前状态

Ablation 尚未完成（AC7–AC10 尚无法验证）。

**待 AMP 提交 `RS-020-2`。**
