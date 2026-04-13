# Codex 实施指令 — SPEC-057

**Spec 文件**：`task/SPEC-057.md`（Status: APPROVED）

---

## 概览

| 步骤 | 文件 | 类型 |
|------|------|------|
| F5 | `backtest/engine.py` | 修改：signal_history 补充 iv_signal 字段 |
| F1 | `strategy/selector.py` | 修改：StrategyParams 新增 force_strategy |
| F2 | `strategy/selector.py` | 修改：select_strategy() 头部插入早返回 |
| F3 | `strategy/selector.py` | 修改：新增 _build_forced_recommendation() 函数 |
| F4 | `backtest/run_matrix_audit.py` | 新建 |

**必须先完成 F1/F2/F3/F5，再实现 F4。**

---

## F5 — `backtest/engine.py`

### 变更：signal_history 追加 iv_signal 字段

定位：约第 806 行，`"local_spike": _local_spike,` 这一行之后。

在 signal_history dict 末尾，紧接 `local_spike` 之后追加：

```python
            "iv_signal":      iv_eff.value,
```

`iv_eff` 是约第 737 行计算的 `IVSig.HIGH / IVSig.LOW / IVSig.NEUTRAL`，在插入点之前已存在。

---

## F1 — `strategy/selector.py`：StrategyParams 新增字段

定位：`disable_entry_gates: bool = False` 这一行（约第 119 行）之后插入：

```python
    # Research mode: force a specific strategy regardless of signal routing.
    # When set, select_strategy() returns a recommendation for this strategy
    # using its standard legs, bypassing all regime/IV/trend routing logic.
    # NEVER set in production.
    force_strategy: str | None = None
```

---

## F2 — `strategy/selector.py`：select_strategy() 早返回

定位：`select_strategy()` 函数体的第一行有效代码（约第 390 行附近，在任何 regime 判断之前）。

找到 `select_strategy` 函数定义后，在函数体开头插入：

```python
    if params.force_strategy:
        return _build_forced_recommendation(params.force_strategy, vix, iv, trend, params)
```

具体定位方法：搜索 `def select_strategy(`，找到函数体第一行（通常是 `r = vix.regime` 或类似），在它之前插入。

---

## F3 — `strategy/selector.py`：新增 _build_forced_recommendation()

将此函数放在 `_compute_size_tier()` 之后、`_build_recommendation()` 之前（约第 297 行附近）。

```python
def _build_forced_recommendation(
    strategy_key: str,
    vix: VixSnapshot,
    iv: IVSnapshot,
    trend: TrendSnapshot,
    params: StrategyParams,
) -> "Recommendation":
    """
    Build a valid Recommendation for the specified strategy using its standard legs,
    regardless of current regime/IV/trend. Used only for matrix audit research (SPEC-057).
    """
    _FORCED_LEGS: dict[str, list] = {
        "bull_call_diagonal": [
            Leg("BUY",  "CALL", 90, 0.70, "Long leg — deep ITM, high delta"),
            Leg("SELL", "CALL", 45, 0.30, "Short leg — OTM, collects theta"),
        ],
        "iron_condor": [
            Leg("SELL", "CALL", 45, 0.16, "Short call wing"),
            Leg("BUY",  "CALL", 45, 0.08, "Long call wing"),
            Leg("SELL", "PUT",  45, 0.16, "Short put wing"),
            Leg("BUY",  "PUT",  45, 0.08, "Long put wing"),
        ],
        "bull_put_spread": [
            Leg("SELL", "PUT", 30, 0.30, "Short put"),
            Leg("BUY",  "PUT", 30, 0.15, "Long put"),
        ],
        "bull_put_spread_hv": [
            Leg("SELL", "PUT", 35, 0.20, "Short put — HV params"),
            Leg("BUY",  "PUT", 35, 0.10, "Long put — HV params"),
        ],
        "bear_call_spread_hv": [
            Leg("SELL", "CALL", 45, 0.20, "Short call — HV params"),
            Leg("BUY",  "CALL", 45, 0.10, "Long call — HV params"),
        ],
        "iron_condor_hv": [
            Leg("SELL", "CALL", 45, 0.16, "Short call wing — HV"),
            Leg("BUY",  "CALL", 45, 0.08, "Long call wing — HV"),
            Leg("SELL", "PUT",  45, 0.16, "Short put wing — HV"),
            Leg("BUY",  "PUT",  45, 0.08, "Long put wing — HV"),
        ],
    }
    legs = _FORCED_LEGS.get(strategy_key)
    if legs is None:
        raise ValueError(f"_build_forced_recommendation: unknown strategy_key {strategy_key!r}")

    strategy_enum = next(
        (s for s in StrategyName if catalog_strategy_key(s.value) == strategy_key),
        None,
    )
    if strategy_enum is None:
        raise ValueError(f"_build_forced_recommendation: cannot map {strategy_key!r} to StrategyName")

    t = trend.signal
    iv_s = _effective_iv_signal(iv)
    size = _compute_size_tier(strategy_key, iv, vix, iv_s, t)
    local_spike = (iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN and iv.ivp252 < LOCAL_SPIKE_IVP252_MAX)

    return _build_recommendation(
        strategy_enum,
        vix=vix,
        iv=iv,
        trend=trend,
        legs=legs,
        size_rule=size,
        rationale=f"[FORCED] matrix audit — standard {strategy_key} legs",
        local_spike=local_spike,
    )
```

**导入确认**：`catalog_strategy_key` 在 `selector.py` 中已以 `from strategy.catalog import strategy_key as catalog_strategy_key` 导入，可直接使用。如果该 import 名称不同，找到 `strategy.catalog` 相关 import 并确认别名。

---

## F4 — `backtest/run_matrix_audit.py`（新建）

完整内容见 SPEC-057.md 的 F4 小节。直接复制 spec 中的代码即可。

**需要确认的一点**：`signal_history` 中的 `iv_signal` 字段在 F5 实现后才存在。`run_matrix_audit.py` 中读取 `sig.get("iv_signal", "UNKNOWN")` 即可，不需要 fallback 计算。

---

## 测试用例

文件：`tests/test_spec_057.py`

```python
"""Tests for SPEC-057: Force-entry matrix audit."""
from __future__ import annotations
from dataclasses import replace
import unittest


class Spec057Tests(unittest.TestCase):

    def _make_snaps(self, ivp63=40.0, ivp252=25.0):
        from strategy.selector import VixSnapshot, IVSnapshot, TrendSnapshot
        from signals.vix_regime import Regime, Trend
        from signals.trend import TrendSignal
        from signals.iv_rank import IVSignal
        v = VixSnapshot(date="2024-01-01", vix=28.0, regime=Regime.HIGH_VOL,
            trend=Trend.FLAT, vix_5d_avg=27.0, vix_5d_ago=26.0,
            transition_warning=False, vix3m=27.0, backwardation=False)
        i = IVSnapshot(date="2024-01-01", vix=28.0,
            iv_rank=70.0, iv_percentile=float(ivp252), iv_signal=IVSignal.HIGH,
            iv_52w_high=40.0, iv_52w_low=15.0,
            ivp63=float(ivp63), ivp252=float(ivp252), regime_decay=False)
        t = TrendSnapshot(date="2024-01-01", spx=4200.0,
            ma20=4300.0, ma50=4400.0, ma_gap_pct=-0.05, signal=TrendSignal.BEARISH,
            above_200=False, atr14=None, gap_sigma=None)
        return v, i, t

    # ── AC1: force_strategy=None 是默认值 ────────────────────────────────────
    def test_ac1_default_force_strategy_none(self):
        from strategy.selector import DEFAULT_PARAMS
        self.assertIsNone(DEFAULT_PARAMS.force_strategy)

    # ── AC2: force_strategy 强制返回目标策略，即使在错误 regime ──────────────
    def test_ac2_force_strategy_overrides_routing(self):
        from strategy.selector import select_strategy, StrategyParams, StrategyName
        # HIGH_VOL + BEARISH 通常 → BCS_HV；强制 → DIAGONAL
        params = StrategyParams(force_strategy="bull_call_diagonal")
        v, i, t = self._make_snaps()
        rec = select_strategy(v, i, t, params)
        self.assertEqual(rec.strategy, StrategyName.BULL_CALL_DIAGONAL)

    # ── AC2b: force_strategy 不返回 REDUCE_WAIT ───────────────────────────────
    def test_ac2b_force_strategy_never_reduce_wait(self):
        from strategy.selector import select_strategy, StrategyParams, StrategyName
        from signals.vix_regime import Regime, Trend
        from strategy.selector import VixSnapshot, IVSnapshot, TrendSnapshot
        from signals.trend import TrendSignal
        from signals.iv_rank import IVSignal
        # EXTREME_VOL 下通常 → REDUCE_WAIT；强制后仍返回目标策略
        v = VixSnapshot(date="2024-01-01", vix=40.0, regime=Regime.HIGH_VOL,
            trend=Trend.RISING, vix_5d_avg=38.0, vix_5d_ago=32.0,
            transition_warning=False, vix3m=38.0, backwardation=False)
        i = IVSnapshot(date="2024-01-01", vix=40.0,
            iv_rank=90.0, iv_percentile=30.0, iv_signal=IVSignal.NEUTRAL,
            iv_52w_high=45.0, iv_52w_low=15.0,
            ivp63=90.0, ivp252=30.0, regime_decay=False)
        t = TrendSnapshot(date="2024-01-01", spx=4000.0,
            ma20=4200.0, ma50=4300.0, ma_gap_pct=-0.07, signal=TrendSignal.BEARISH,
            above_200=False, atr14=None, gap_sigma=None)
        params = StrategyParams(force_strategy="iron_condor")
        rec = select_strategy(v, i, t, params)
        self.assertEqual(rec.strategy, StrategyName.IRON_CONDOR)

    # ── AC3: _build_forced_recommendation 对所有 6 个策略均返回有效 Recommendation
    def test_ac3_all_strategies_build_valid_recommendation(self):
        from strategy.selector import _build_forced_recommendation, StrategyParams
        from strategy.catalog import STRATEGIES_BY_KEY
        params = StrategyParams()
        v, i, t = self._make_snaps()
        keys = [k for k in STRATEGIES_BY_KEY if k != "reduce_wait"]
        for key in keys:
            rec = _build_forced_recommendation(key, v, i, t, params)
            self.assertIsNotNone(rec, f"None recommendation for {key}")
            self.assertIsNotNone(rec.strategy, f"No strategy for {key}")
            self.assertTrue(len(rec.legs) > 0, f"No legs for {key}")

    # ── AC4: run_matrix_audit DIAGONAL 强制跑后 strategy_key 全为 diagonal ──
    def test_ac4_matrix_audit_strategy_key_consistent(self):
        from backtest.run_matrix_audit import run_matrix_audit
        df = run_matrix_audit(
            strategy_keys=["bull_call_diagonal"],
            start_date="2018-01-01",
            end_date="2020-12-31",
            save_csv=False,
        )
        if df.empty:
            self.skipTest("No trades in window")
        self.assertTrue(
            (df["strategy_key"] == "bull_call_diagonal").all(),
            "Expected all rows to be bull_call_diagonal"
        )

    # ── AC5: signal_history 含 iv_signal 字段 ────────────────────────────────
    def test_ac5_signal_history_has_iv_signal(self):
        from backtest.engine import run_backtest
        result = run_backtest(start_date="2020-01-01", end_date="2020-06-30", verbose=False)
        self.assertTrue(result.signals)
        row = result.signals[0]
        self.assertIn("iv_signal", row, "iv_signal missing from signal_history")
        self.assertIn(row["iv_signal"], ("HIGH", "NEUTRAL", "LOW"),
                      f"Unexpected iv_signal value: {row['iv_signal']}")

    # ── AC6: matrix_audit CSV 写出 ────────────────────────────────────────────
    def test_ac6_matrix_audit_saves_csv(self):
        import os
        from backtest.run_matrix_audit import run_matrix_audit
        path = "backtest/output/matrix_audit.csv"
        # Remove if exists
        if os.path.exists(path):
            os.remove(path)
        df = run_matrix_audit(
            strategy_keys=["bull_put_spread"],
            start_date="2018-01-01",
            end_date="2021-12-31",
            save_csv=True,
        )
        if df.empty:
            self.skipTest("No trades to save")
        self.assertTrue(os.path.exists(path), f"CSV not found at {path}")


if __name__ == "__main__":
    unittest.main()
```

期望：**6/6 通过**（AC4/AC6 可能因数据 skip，但不得 FAIL）。

---

## 注意事项

1. **`_build_forced_recommendation` 的位置**：必须放在 `_compute_size_tier()` 之后（因为它调用 `_compute_size_tier`），且在 `_build_recommendation()` 之后（因为它调用 `_build_recommendation`）。检查 `_build_recommendation` 的定义位置，确保 `_build_forced_recommendation` 在其之后。

2. **`select_strategy()` 中的早返回位置**：在函数体最开头，`r = vix.regime`（或第一行有效逻辑）之前插入。不要插入在 docstring 之后、局部变量初始化之前以外的位置。

3. **extreme_vix 行为**：SPEC-057 的 force_strategy 覆盖包括 extreme_vix 检查（VIX ≥ 35）——这是有意为之，研究目的是测试策略在所有条件下的表现。AC2b 测试验证了这一点。

4. **overlay 和 BP ceiling**：`run_matrix_audit` 使用完整 engine（含 overlay 和 BP ceiling）。overlay.block_new_entries 在极端波动期会阻止入场，这会减少 HIGH_VOL 期间某些策略的实际交易数。这是真实约束，不需要绕过。

5. **iv_signal 字段名**：`iv_eff` 是 `IVSig`（engine.py 中 `IVSignal` 的别名），其 `.value` 是字符串 "HIGH"/"NEUTRAL"/"LOW"。

---

## 交接文件

实施完成后，请创建 `task/SPEC-057_handoff.md`，包含：
- 修改文件列表与行号
- 新建文件列表
- 测试运行结果（通过数 / 总数）
- 任何偏离 Spec 的说明
