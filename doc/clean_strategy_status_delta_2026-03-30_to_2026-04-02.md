# Strategy Status Delta - 2026-03-30 to 2026-04-02

- **适用场景**：快速了解本次迭代变更内容，无需重读完整文档。
- **完整文档**：`doc/strategy_status_2026-04-01.md`

## 新增模块（2026-04-01 首批 5 个文件）

| 文件 | 模块内容 | 对应 SPEC |
|---|---|---|
| `backtest/portfolio.py` | `PortfolioTracker`、`DailyPortfolioRow`、`_prev_marks: dict`、每日 unrealized delta 追踪 | SPEC-024 |
| `backtest/metrics_portfolio.py` | `compute_portfolio_metrics()`：daily Sharpe / Sortino / Calmar / CVaR95 / worst_5d_drawdown / positive_months_pct | SPEC-024 |
| `backtest/registry.py` | `generate_experiment_id()`：`EXP-YYYYMMDD-HHMMSS-XXXX`；`config_hash = sha256(params)[:12]`；实验结果强制关联 ID | SPEC-024 |
| `backtest/shock_engine.py` | 8 个标准场景、`run_shock_check()`、`ShockReport` dataclass、shadow / active 双模式、sigma 使用当日 `VIX/100` | SPEC-025 |
| `signals/overlay.py` | `OverlayLevel (0-4)`、`compute_overlay_signals()`、4 级响应（Freeze / Trim / Hedge / Emergency）、`book_core_shock` 修复 | SPEC-026 |

## §1 实证基线变更

### Before（2026-03-30，trade-level only）

| 指标 | 值 |
|---|---|
| Sharpe | 1.54（Bootstrap 95% CI: [1.18, 1.95]） |
| Calmar | 26.23 |
| WR | 75.6% |
| Total PnL | +192,234 Raw / +94,070 Adj |

### After（2026-04-01，两套指标并行）

Trade-level（Legacy，保留不变）：同上。

Daily portfolio（SPEC-024）：

| 配置 | Ann.Ret | Sharpe | Calmar | MaxDD |
|---|---:|---:|---:|---:|
| `EXP-baseline`（无 overlay） | 3.73% | 0.70 | 0.24 | -15.35% |
| **`EXP-full`（推荐生产配置）** | **4.26%** | **0.86** | **0.35** | **-12.22%** |

> 计量基础不同，不可直接对比。trade-level 用于策略族 ROM 排名；daily portfolio 用于风险控制决策和多版本实验对比。

## §5 StrategyParams 新增字段

### Before（2026-03-30）

9 个参数：

- `extreme_vix`
- `high_vol_delta`
- `high_vol_dte`
- `high_vol_size`
- `normal_delta`
- `normal_dte`
- `profit_target`
- `stop_mult`
- `min_hold_days`

### After（2026-04-01）

共 25 个参数（新增 16 个）。

### 新增字段明细

#### SPEC-024（1 个）

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `initial_equity` | 100000 | 回测初始净值，`DailyPortfolioRow` 基准 |

#### SPEC-025 Shock-Risk Engine（6 个）

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `shock_mode` | `"shadow"` | `shadow` = 只记录；`active` = 超预算时拦截 |
| `shock_budget_core_normal` | 0.0125 | Normal：core shock 上限 1.25% NAV |
| `shock_budget_core_hv` | 0.0100 | HIGH_VOL：core shock 上限 1.00% NAV |
| `shock_budget_incremental` | 0.0040 | Normal：边际 shock 上限 0.40% NAV |
| `shock_budget_incremental_hv` | 0.0030 | HIGH_VOL：边际 shock 上限 0.30% NAV |
| `shock_budget_bp_headroom` | 0.15 | 任意 regime：BP 最低剩余 15% NAV |

#### SPEC-026 Acceleration Overlay（10 个）

| 参数 | 默认值 | Level |
|---|---:|---|
| `overlay_mode` | `"disabled"` | - |
| `overlay_freeze_accel` | 0.15 | L1（OR） |
| `overlay_freeze_vix` | 30.0 | L1（OR） |
| `overlay_trim_accel` | 0.25 | L2（AND） |
| `overlay_trim_shock` | 0.01 | L2（AND） |
| `overlay_hedge_accel` | 0.35 | L3（AND） |
| `overlay_hedge_shock` | 0.015 | L3（AND） |
| `overlay_emergency_vix` | 40.0 | L4（OR） |
| `overlay_emergency_shock` | 0.025 | L4（OR） |
| `overlay_emergency_bp` | 0.10 | L4（OR） |

> 参数数量变化：9 → 25（+16）

## §7 入场守护链更新

### Before（2026-03-30）

6 步检查（Steps 1–6），全部与策略 / 仓位 / BP 相关。

### After（2026-04-01）

新增 4 个检查点：

| 新增步骤 | 时机 | 内容 | SPEC |
|---|---|---|---|
| Step 0 | 每日开始（独立于入场路径） | 计算现有仓位 `_daily_book_shock`；修复 L1 freeze 后 `book_core_shock = 0` 的缺陷 | SPEC-026 |
| Step pre-entry | 候选入场前 | Overlay freeze check：`overlay_level >= 1` 时禁止新开 short-vol | SPEC-026 |
| Step 7 | SPEC-017 guards 之后 | Shock gate check（active mode）：`post_max_core > budget` then 阻断入场
 SPEC-025 |
| Step post-entry | 仓位建立后（每日收盘） | 若 `overlay_level >= 2` 强制 trim；若 `overlay_level = 4` 执行 emergency exit | SPEC-026 |

原 Steps 1–6 不变；新增检查插入到其前后。

## §8 历史性能基准更新

新增内容：Overlay 5-version 对照表（基于 daily portfolio metrics）。

### 全历史（2000-01-03 至 2026-03-31）

| 配置 | Ann.Ret | Sharpe | Calmar | MaxDD | CVaR95 | 交易数 |
|---|---:|---:|---:|---:|---:|---:|
| `EXP-baseline` | 3.73% | 0.70 | 0.24 | -15.35% | -0.837% | 354 |
| `EXP-freeze` | 3.77% | 0.70 | 0.30 | -12.63% | -0.835% | 331 |
| `EXP-freeze_trim` | 4.25% | 0.85 | 0.34 | -12.38% | -0.747% | 348 |
| `EXP-freeze_hedge` | 3.90% | 0.74 | 0.31 | -12.59% | -0.808% | 333 |
| **`EXP-full`** | **4.26%** | **0.86** | **0.35** | **-12.22%** | **-0.736%** | **348** |

### 压力窗口 MaxDD

| 配置 | 2011 | 2015 | 2020 | 2022 |
|---|---:|---:|---:|---:|
| Baseline | -2.78% | -2.13% | -4.45% | -5.59% |
| `EXP-full` | **-0.10%** | **-0.46%** | **-4.13%** | **-5.20%** |

变化说明：旧版 §8 仅有 trade-level 指标（26yr Sharpe 1.54）；新版新增 daily portfolio 对照表，两套指标并列展示。

## §9 风险画像更新

### 更新项：VIX 25 → 50 的中速急升保护状态

| 风险类型 | Before（2026-03-30） | After（2026-04-01） |
|---|---|---|
| VIX 25→50 中速急升 | backwardation 提供部分保护；已开仓位退出速度缺失 | SPEC-025 shock engine（预算门槛）+ SPEC-026 overlay L2 trim（2015 场景改善 78%） |

### 新增项：极速崩溃（3–5 日 VIX 翻倍）

| 风险类型 | 状态 |
|---|---|
| 极速崩溃（COVID 型） | 部分保护：3 日窗口存在滞后；v2 计划加入 `vix_accel_1d` fast-path |

### 新增分类：已实施保护机制完整性

- 入场前
- 持仓中
- 每日监控

详见完整文档 §9。

## 未变更项目

以下内容在 2026-03-30 至 2026-04-01 迭代中**未发生改动**：

| 章节 | 内容 |
|---|---|
| §2 | 信号体系（三维过滤）：VIX regime、IVR / IVP、趋势信号逻辑和阈值均不变 |
| §3 | 决策矩阵：`CANONICAL_MATRIX` 不变 |
| §4 | 六大策略参数：delta、DTE、haircut、主动出场规则均不变 |
| §5.1 | 基础参数：原 9 个参数值不变 |
| §5.2 | BP 利用率：`bp_target / bp_ceiling` 不变 |
| §5.4 | Vol Spell Throttle：`spell_age_cap = 30`、`max_trades_per_spell = 2` 不变 |
| §5.3 | Portfolio Greek 限制：`max_short_gamma_positions = 3`、synthetic IC block 逻辑不变 |
| SPEC-022 | Sharpe 使用指南：统计不确定性分析和建议不变（仅新增 daily Sharpe 作为补充） |
| SPEC-021 | Filter 复杂度协议：准入门槛和实证结论不变 |

## 下一步（截至 2026-04-01）

### 短期（v2，待 PM 审批）

1. L3 hedge 的实际实现（Long put spread），需新 SPEC；ChatGPT review 建议优先推进。
2. `vix_accel_1d` L4 fast-path：优化 COVID 类极速崩溃场景。
3. 将 `overlay_mode` 从 `"disabled"` 切换至 `"active"`：`EXP-full` 已验证，可作为推荐生产配置。

### 中期（下一波研究优先级）

- Vol Persistence Model（senior quant review §5.2）
- 多仓引擎：按 shock 贡献排序进行 trim 精细化

---

# 追加 Delta：2026-04-01 至 2026-04-02

## 新增模块（第二批 5 个文件）

| 文件 | 模块内容 | 对应 SPEC |
|---|---|---|
| `backtest/attribution.py` | `compute_strategy_attribution()`（11 列）、`compute_regime_attribution()`（8 列） | SPEC-028 |
| `backtest/run_shock_analysis.py` | Phase A shadow analysis：年度 / regime hit rate、breach type 分布、percentile 分布 | SPEC-027 |
| `backtest/run_oos_validation.py` | `_split()`、`_run_config()`、5 组报表（window metrics / overlay advantage / OOS AC / OOS strategy attribution / OOS regime attribution） | SPEC-029 |
| `backtest/run_trend_ablation.py` | 趋势 ablation：`EXP-baseline / EXP-atr / EXP-persist / EXP-full`；RS-020-1 FAIL，待 RS-020-2 | SPEC-020 |
| `backtest/research/SPEC020_prereq_findings.md` | §7 前置研究结果：gap_sigma 分布、BEARISH streak 条件概率 | SPEC-020 §7 |

## §2.3 趋势信号更新

### Before（2026-04-01）

固定 `+1% band`，单日 `BEARISH` 触发 `trend_flip`。

### After（2026-04-02，SPEC-020，实施中）

| 改动 | 内容 |
|---|---|
| Entry Gate | ATR-Normalized：`gap_sigma = (SPX - MA50) / ATR_close(14)`；BULLISH if `> +1.0 sigma` |
| Exit Filter | Persistence：`bearish_streak >= 3` 天才触发 `trend_flip` |
| 参数依据 | §7 实证：`ATR_THRESHOLD = 1.0`；`PERSISTENCE = 3`（条件概率拐点） |

**ATR 实现**：v1 先用收盘价差分近似（无需 Bloomberg H/L）；v2 待数据就绪后升级。

## §5 新增指标（SPEC-028）

### `pnl_per_bp_day`

位置：`backtest/metrics_portfolio.py`

```python
pnl_per_bp_day = total_net_pnl / sum(daily_used_bp)
```

衡量每占用 1 美元保证金 1 天所获得的净收益，消除持仓时长对胜率的扭曲。

### `BEARISH_PERSISTENCE_DAYS = 3`

位置：`signals/trend.py`（SPEC-020）

## §6 出场规则更新

| 规则 | Before（2026-04-01） | After（2026-04-02） |
|---|---|---|
| `trend_flip` | 持仓 ≥ 3 天，当日 `trend = BEARISH` | 持仓 ≥ 3 天，且 **连续 `bearish_streak >= 3` 天** |

## §8 新增：OOS 验证结果（SPEC-029）

| 报表 | 内容 |
|---|---|
| R3 | OOS Acceptance Criteria：Sharpe > 0 / MaxDD improvement ≥5% / PnL retention ≥85% / Trade drop ≤15%，PASS / FAIL |

## SPEC 变更历史新增

| SPEC | 内容 | 状态 |
|---|---|---|
| SPEC-027 | Shock Engine Active Mode：Phase A shadow analysis + A/B AC；`any_breach_rate` bug fix | DONE |
| SPEC-028 | Capital efficiency（`pnl_per_bp_day`）+ strategy / regime PnL attribution | DONE |
| SPEC-029 | OOS Validation：IS = 2000–2019 / OOS = 2020–2026；5 reports；9/9 tests | DONE |
| SPEC-020（更新） | ATR-Normalized Entry Gate + Persistence Exit；§7 前置研究完成；RS-020-1 FAIL（ablation 未完成），待 RS-020-2 | 进行中 |

## 研究优先级更新

### 已完成

- SPEC-027（Shock active mode 校准）
- SPEC-028（Capital attribution）
- SPEC-029（OOS validation）
- SPX 趋势信号深度研究（§39）

### 当前阻塞

- SPEC-020 / RS-020-2（AMP 修复 `run_backtest` toggle + 完成 ablation）

### 下一波研究

| 优先级 | 任务 |
|---|---|
| P3 | Vol Persistence Model（senior quant review §5.2） |
| P4 | Shock Active Mode 生产切换（基于 SPEC-027 Phase B 数据驱动决策） |
| P5 | ATR v2：Bloomberg H/L 版 ATR |
| P6 | ADX 辅助确认（若 SPEC-020 OOS 仍有 >20% 误触发） |
