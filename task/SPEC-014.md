# SPEC-014: Multi-Position Parallel Engine Architecture

## 目标

**What**：将 `run_backtest` 的持仓模型从「最多 1 个并行仓位」改为「多仓并行，受总 BP ceiling 约束」。同时在 `StrategyParams` 加入 regime-aware BP ceiling 参数。

**Why**：真实 PM 账户不受「同一时间只有一个仓位」约束，而是受总 BP 利用率上限管理。当前单仓模型会在一个仓位持有期（30–45 天）内完全屏蔽新信号，导致：
- 高质量机会（信号连续发出 3–5 天）被全部丢弃
- Sharpe / total P&L 大幅低估
- 无法体现 PM 账户 cross-margin netting 对 BP 效率的提升

多仓架构是 SPEC-013（BP sizing）的自然延伸：既然每笔仓位的 BP 占用已标准化，只需用总 BP ceiling 守护整体风险暴露，即可安全并行。

业界实践参考（tastytrade 零售 PM 账户）：
- 同时持仓：3–6 个
- 总 BP 利用率：25–50%（LOW_VOL 25%、NORMAL 35%、HIGH_VOL 50%）
- 不重复持有相同策略（dedup 规则）

---

## 策略/信号逻辑

无信号变更。纯 engine 并发模型扩展：

- `select_strategy()` 每天仍返回一个推荐，不变
- 新入场规则（见下）判断是否允许开新仓

---

## 接口定义

### `strategy/selector.py` — `StrategyParams` 修改（约 line 75 后）

在 `bp_target_high_vol` 字段之后，`bp_target_for_regime` 方法之前，新增：

```python
    # Total BP ceiling per regime (fraction of account_size, all concurrent positions combined)
    # Governs maximum aggregate portfolio margin utilization at any point in time.
    # Reference: tastytrade retail PM practice — 25–50% total utilization.
    bp_ceiling_low_vol:  float = 0.25  # LOW_VOL:  conservative — thin premium environment
    bp_ceiling_normal:   float = 0.35  # NORMAL:   baseline
    bp_ceiling_high_vol: float = 0.50  # HIGH_VOL: elevated premium offsets higher per-trade risk

    def bp_ceiling_for_regime(self, regime: "Regime") -> float:
        """Return the total-portfolio BP ceiling for the given regime."""
        from signals.vix_regime import Regime
        if regime == Regime.LOW_VOL:
            return self.bp_ceiling_low_vol
        if regime == Regime.HIGH_VOL:
            return self.bp_ceiling_high_vol
        return self.bp_ceiling_normal
```

> 注：`from signals.vix_regime import Regime` 仍在方法体内 import，与 `bp_target_for_regime` 保持一致。

---

### `backtest/engine.py` — 修改点 1：持仓变量初始化（约 line 459）

变更前：
```python
    position: Optional[Position] = None
```

变更后：
```python
    positions: list[Position] = []
```

---

### `backtest/engine.py` — 修改点 2：持仓管理循环（约 line 532–613）

**变更前**（单仓逻辑）：
```python
        # ── Manage open position ─────────────────────────────────────
        if position is not None:
            position.days_held += 1
            current_val  = _current_value(...)
            pnl          = current_val - position.entry_value
            ...
            if exit_reason:
                ...
                trades.append(t)
                position = None
```

**变更后**（多仓迭代，对 `positions` 列表的副本迭代以安全删除）：
```python
        # ── Manage open positions ────────────────────────────────────
        for position in list(positions):
            position.days_held += 1
            current_val  = _current_value(position.legs, spx, sigma, position.days_held)
            pnl          = current_val - position.entry_value

            short_leg    = _short_leg(position.legs)
            short_dte    = max(short_leg[3] - position.days_held, 0)

            # Exit conditions（逐仓独立评估，与原逻辑相同）
            exit_reason  = None
            is_credit    = position.entry_value < 0
            if abs(position.entry_value) > 0:
                pnl_ratio = pnl / abs(position.entry_value)
                if pnl_ratio >= params.profit_target and position.days_held >= params.min_hold_days:
                    exit_reason = "50pct_profit"
                elif is_credit and pnl_ratio <= -params.stop_mult:
                    exit_reason = "stop_loss"
                elif not is_credit and pnl_ratio <= -0.50:
                    exit_reason = "stop_loss"

            if short_dte <= 21 and exit_reason is None:
                exit_reason = "roll_21dte"

            if (exit_reason is None
                    and short_dte > 14
                    and position.strategy in (StrategyName.BULL_PUT_SPREAD,
                                              StrategyName.BULL_PUT_SPREAD_HV)):
                spx_gain = (spx - position.entry_spx) / position.entry_spx
                if (spx_gain >= 0.03
                        and regime != Regime.LOW_VOL
                        and ivp >= 30):
                    exit_reason = "roll_up"

            if (exit_reason is None
                    and position.days_held >= 3
                    and position.strategy == StrategyName.BULL_CALL_DIAGONAL
                    and trend == TrendSignal.BEARISH):
                exit_reason = "trend_flip"

            if exit_reason:
                _opt_prem = abs(position.entry_value) * 100
                _conts    = (account_size * position.bp_target / position.bp_per_contract
                             if position.bp_per_contract > 0 and position.bp_target > 0 else 0.0)
                _total_bp = _conts * position.bp_per_contract
                t = Trade(
                    strategy        = position.strategy,
                    underlying      = position.underlying,
                    entry_date      = position.entry_date,
                    exit_date       = str(date.date()),
                    entry_spx       = position.entry_spx,
                    exit_spx        = spx,
                    entry_vix       = position.entry_vix,
                    entry_credit    = position.entry_value,
                    exit_pnl        = pnl * _conts * 100,
                    exit_reason     = exit_reason,
                    dte_at_entry    = short_leg[3],
                    dte_at_exit     = short_dte,
                    spread_width    = position.spread_width,
                    option_premium  = _opt_prem,
                    bp_per_contract = position.bp_per_contract,
                    contracts       = round(_conts, 4),
                    total_bp        = round(_total_bp, 2),
                    bp_pct_account  = round(_total_bp / account_size * 100, 2) if account_size else 0.0,
                )
                trades.append(t)
                positions.remove(position)
                if verbose:
                    print(f"  EXIT  {t.exit_date}  {t.strategy.value:<25}  "
                          f"PnL: {t.exit_pnl:+.0f}  ({exit_reason})")
```

> 注：exit 逻辑与原逻辑完全相同，只是将 `if position is not None:` 改为 `for position in list(positions):`，并将 `position = None` 改为 `positions.remove(position)`。

---

### `backtest/engine.py` — 修改点 3：开仓逻辑（约 line 615–645）

**变更前**：
```python
        # ── Open new position (only if none open) ────────────────────────────
        if position is None and rec.strategy != StrategyName.REDUCE_WAIT:
```

**变更后**：
```python
        # ── Open new position (if BP ceiling and dedup allow) ────────────────
        _used_bp      = sum(p.bp_target for p in positions)
        _new_bp_target = params.bp_target_for_regime(regime)
        _ceiling      = params.bp_ceiling_for_regime(regime)
        _already_open = any(p.strategy == rec.strategy for p in positions)

        if (rec.strategy != StrategyName.REDUCE_WAIT
                and not _already_open
                and _used_bp + _new_bp_target <= _ceiling):
```

> 后续 `_build_legs` / `Position(...)` 初始化代码不变，只替换入场条件判断。

---

### `backtest/engine.py` — 修改点 4：回测结束强平（约 line 647–674）

**变更前**：
```python
    # Close any still-open position at last price
    if position is not None:
        ...
        trades.append(Trade(...))
```

**变更后**：
```python
    # Close all still-open positions at last price
    for position in positions:
        current_val = _current_value(position.legs, spx, sigma, position.days_held)
        pnl = current_val - position.entry_value
        _opt_prem = abs(position.entry_value) * 100
        _conts    = (account_size * position.bp_target / position.bp_per_contract
                     if position.bp_per_contract > 0 and position.bp_target > 0 else 0.0)
        _total_bp = _conts * position.bp_per_contract
        trades.append(Trade(
            strategy        = position.strategy,
            underlying      = position.underlying,
            entry_date      = position.entry_date,
            exit_date       = str(df.index[-1].date()),
            entry_spx       = position.entry_spx,
            exit_spx        = float(df["spx"].iloc[-1]),
            entry_vix       = position.entry_vix,
            entry_credit    = position.entry_value,
            exit_pnl        = pnl * _conts * 100,
            exit_reason     = "end_of_backtest",
            dte_at_entry    = _short_leg(position.legs)[3],
            dte_at_exit     = 0,
            spread_width    = position.spread_width,
            option_premium  = _opt_prem,
            bp_per_contract = position.bp_per_contract,
            contracts       = round(_conts, 4),
            total_bp        = round(_total_bp, 2),
            bp_pct_account  = round(_total_bp / account_size * 100, 2) if account_size else 0.0,
        ))
```

---

## 边界条件与约束

- `positions` 为空时，`_used_bp = 0.0`，入场判断退化为只检查 `_new_bp_target <= _ceiling`（必然满足，因单仓 5% << 25%），与原行为一致
- 同一策略 dedup：同一 `StrategyName` 在 `positions` 中已存在时不重复开仓（防止信号连续发出时堆叠同类型仓位）
- `bp_ceiling_for_regime` 使用**当天**的 regime（与 `bp_target_for_regime` 保持一致）；regime 在持仓存续期间可能变化，但 ceiling 检查只在入场时生效
- `compute_metrics` / `_summarize_trades` 无需修改（已支持任意数量 Trade 对象）
- Sharpe 计算基于逐笔交易 P&L，多仓并行下为 trade-level Sharpe（非日收益率 Sharpe），是已知近似，不变
- `Optional[Position]` import 仍保留（`typing.Optional` 用于 `Position` 的 forward reference；`positions: list[Position]` 不需要 Optional）
- 只修改 `strategy/selector.py` 和 `backtest/engine.py`
- 不修改 `signals/`、`web/`、`backtest/prototype/`、`run_backtest` 函数签名

---

## 不在范围内

- 仓位间相关性分析（例如同时持有 Bull Put + Bear Call = 合成 Iron Condor 的 BP netting）
- PM cross-margin netting 模拟（实际 BPR 因组合而降低 20–40%）
- 每日总 BP 快照记录（可后续加入 signal_history）
- 动态 ceiling：持仓期间 regime 变化时自动平仓以降低总 BP
- 前端多仓展示

---

## Prototype

无，逻辑直接。入场条件是简单的 BP 求和比较，无需量化预验证。

---

## Review

- 结论：PASS
- AC 1：`bp_ceiling_low_vol=0.25`、`bp_ceiling_normal=0.35`、`bp_ceiling_high_vol=0.50` 均在 `StrategyParams`（selector.py:79–81）✅
- AC 2：`bp_ceiling_for_regime()` 正确实现（selector.py:83–91），方法内 `from signals.vix_regime import Regime`，与 `bp_target_for_regime` 同模式 ✅
- AC 3：`run_backtest(start_date="2024-01-01")` 正常完成，无异常 ✅
- AC 4：1yr trades 从单仓基线 23 增至 30（+30%），并行仓位使更多信号得以入场 ✅
- AC 5：instrumented replay 显示任意时点总 BP 未超过 ceiling，违规数 0 ✅
- AC 6：instrumented replay 显示无相同 StrategyName 同时在 positions 中，违规数 0 ✅
- AC 7：回测结束时 1 个未平仓仓位正确记录 `exit_reason="end_of_backtest"` ✅
- 代码实现：四处修改与 Spec 完全一致——`positions: list[Position] = []`（engine.py:459）、`for position in list(positions):`（engine.py:533）、BP ceiling + dedup 入场条件（engine.py:615–623）、`for position in positions:` 强平（engine.py:654–655）；`position = None` 已全面替换为 `positions.remove(position)`（engine.py:613）和 `positions.append()`（engine.py:634）

---

## 验收标准

1. `StrategyParams` 具有 `bp_ceiling_low_vol=0.25`、`bp_ceiling_normal=0.35`、`bp_ceiling_high_vol=0.50` 三个字段
2. `StrategyParams` 具有 `bp_ceiling_for_regime(regime)` 方法，LOW_VOL 返回 `0.25`，HIGH_VOL 返回 `0.50`，NORMAL 返回 `0.35`
3. `run_backtest(start_date="2024-01-01")` 正常完成，无异常
4. 回测 1yr 总 trades 数量 ≥ 单仓版本（并行仓位使更多信号得以入场）
5. 任意时间点 `sum(p.bp_target for p in positions)` ≤ `bp_ceiling_for_regime(regime)`（BP ceiling 守护不被突破）
6. 相同 `StrategyName` 不会在 `positions` 中同时出现两次（dedup 有效）
7. 回测结束时所有未平仓仓位均被强平并记录 `exit_reason="end_of_backtest"`

---
Status: DONE
