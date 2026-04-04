# SPEC-013: BP-Based Position Sizing per Regime

## 目标

**What**：将 `run_backtest` 的仓位定仓逻辑从「premium 风险比例」替换为「BP 利用率目标」，同时在 `StrategyParams` 中加入 regime-aware BP target 参数。

**Why**：当前 `contracts = account_size * risk_pct / opt_prem` 的 sizing 基于 option premium 风险（2% of account），与 PM 账户的核心约束（buying power 消耗）脱节。不同策略的 BP/premium 比值差异大（Diagonal ≈ 1:1，Bear Call Spread ≈ 4:1），导致相同 `risk_pct` 下各策略实际 BP 占用量差异悬殊。用 BP target 定仓，使每笔交易的 BP 消耗在同一 regime 下一致，回测 P&L 绝对值更接近真实 PM 账户规模。

业界实践参考（tastytrade 方法论 + 零售 PM 账户实践）：
- 单笔仓位 BPR：3–7% of account（defined risk）
- 总 BP 利用率：25–50%（LOW_VOL 保守端，HIGH_VOL 激进端）
- 本 SPEC 为单仓架构（SPEC-014 将扩展为多仓并行）

---

## 策略/信号逻辑

无策略逻辑变更。纯 engine 定仓公式与参数扩展。

---

## 接口定义

### `strategy/selector.py` — `StrategyParams` 修改（约 line 65）

在 `min_hold_days` 之后，`DEFAULT_PARAMS` 之前，新增：

```python
    # BP utilization target per regime (fraction of account_size per trade)
    # Used by backtest engine to size contracts; supersedes risk_pct + size_mult sizing.
    # Calibrated to tastytrade retail PM standard: single position ≤ 5–7% of account.
    bp_target_low_vol:  float = 0.05   # LOW_VOL:  5% — thin premium, low risk
    bp_target_normal:   float = 0.05   # NORMAL:   5% — baseline
    bp_target_high_vol: float = 0.035  # HIGH_VOL: 3.5% — elevated risk, preserve buffer

    def bp_target_for_regime(self, regime: "Regime") -> float:
        """Return the per-trade BP utilization target for the given regime."""
        if regime == Regime.LOW_VOL:
            return self.bp_target_low_vol
        if regime == Regime.HIGH_VOL:
            return self.bp_target_high_vol
        return self.bp_target_normal
```

> 注：`Regime` 已在 `selector.py` line 73 import，方法体内可直接使用。`"Regime"` 写成字符串 forward reference 以避免 dataclass 字段与方法顺序问题（或直接用裸名，因 import 在 line 73 但 class 在 line 47——需 Codex 确认是否有 NameError；若有，可在方法内 import）。

---

### `backtest/engine.py` — 修改点 1：`Position` dataclass（约 line 113）

在 `bp_per_contract` 字段后新增：

```python
    bp_target:       float = 0.0  # BP utilization target captured at entry (from StrategyParams)
```

---

### `backtest/engine.py` — 修改点 2：开仓时记录 bp_target（约 line 626）

在 `Position(...)` 初始化中，`bp_per_contract = bp_per_c` 后新增：

```python
                    bp_target       = params.bp_target_for_regime(regime),
```

---

### `backtest/engine.py` — 修改点 3：平仓计算（约 line 583，第一处）

变更前：
```python
                _opt_prem = abs(position.entry_value) * 100     # USD per contract
                _conts    = (account_size * risk_pct * position.size_mult / _opt_prem
                             if _opt_prem else 0.0)
                _total_bp = _conts * position.bp_per_contract
                t = Trade(
                    ...
                    exit_pnl        = pnl * account_size * risk_pct * position.size_mult / abs(position.entry_value) if position.entry_value else 0,
```

变更后：
```python
                _opt_prem = abs(position.entry_value) * 100     # USD per contract
                _conts    = (account_size * position.bp_target / position.bp_per_contract
                             if position.bp_per_contract > 0 else 0.0)
                _total_bp = _conts * position.bp_per_contract
                t = Trade(
                    ...
                    exit_pnl        = pnl * _conts * 100,
```

---

### `backtest/engine.py` — 修改点 4：回测结束强平（约 line 650，第二处）

同 修改点 3，将相同的旧公式替换为：
```python
        _conts    = (account_size * position.bp_target / position.bp_per_contract
                     if position.bp_per_contract > 0 else 0.0)
        ...
        exit_pnl  = pnl * _conts * 100,
```

---

## 边界条件与约束

- `bp_per_contract == 0` 时（REDUCE_WAIT 或未识别策略）：`_conts = 0.0`，不抛异常
- `bp_target == 0.0` 时（Position 未正确赋值）：`_conts = 0.0`，Trade 记录 PnL = 0（不应发生，属防御）
- `size_mult` 字段保留在 `Position` 中（不删除），但不再参与 `_conts` 和 `exit_pnl` 计算；`HIGH_VOL` 的减仓效果由 `bp_target_high_vol < bp_target_normal` 体现
- `risk_pct` 参数保留在 `run_backtest` 签名中（不破坏 API），但不再参与 sizing
- 只修改 `strategy/selector.py` 和 `backtest/engine.py`
- 不修改 `signals/`、`web/`、`backtest/prototype/`

---

## 不在范围内

- 多仓并行（SPEC-014）
- 总 BP ceiling 守护（SPEC-014）
- PM cross-margin netting 模拟
- `risk_pct` 参数的弃用注释（可选，后续清理）

---

## Prototype

无，公式直接，不需要量化预验证。

---

## Review

- 结论：PASS
- AC 1：`bp_target_low_vol=0.05`、`bp_target_normal=0.05`、`bp_target_high_vol=0.035` 均在 `StrategyParams`（selector.py:73–75）✅
- AC 2：`bp_target_for_regime()` 正确实现（selector.py:77–85），方法内 `from signals.vix_regime import Regime` 解决了 forward reference 问题 ✅
- AC 3：`Position.bp_target: float = 0.0` 新增（engine.py:114）✅
- AC 4：Codex 自报 `run_backtest` 正常完成 ✅
- AC 5/6：sizing 公式已替换（engine.py:586–587, 652–653），两处均为 `account_size * position.bp_target / position.bp_per_contract`；`exit_pnl = pnl * _conts * 100`（line 598, 664）。NORMAL regime bp_target=0.05、HIGH_VOL bp_target=0.035，满足 AC 5/6 ✅
- 额外观察：Codex 在守护条件上比 Spec 更严格——加了 `position.bp_target > 0` 判断（line 587, 653），防止旧 Position 对象（bp_target=0 默认值）误除，是合理的防御性改进

---

## 验收标准

1. `StrategyParams` 具有 `bp_target_low_vol`、`bp_target_normal`、`bp_target_high_vol` 三个字段，默认值分别为 `0.05`、`0.05`、`0.035`
2. `StrategyParams` 具有 `bp_target_for_regime(regime)` 方法，LOW_VOL 返回 `bp_target_low_vol`，HIGH_VOL 返回 `bp_target_high_vol`，NORMAL/其他返回 `bp_target_normal`
3. `Position` dataclass 具有 `bp_target: float = 0.0` 字段
4. `run_backtest(start_date="2022-01-01")` 正常完成，无异常
5. 回测结果中，NORMAL regime 的交易 `total_bp / account_size` 约等于 `0.05`（±20% 容差，因 `bp_per_contract` 随入场价格变化）
6. HIGH_VOL 策略的 `total_bp / account_size` 约等于 `0.035`，低于 NORMAL 的 `0.05`

---
Status: DONE
