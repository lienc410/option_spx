# Codex 实施指令 — SPEC-056

**Spec 文件**：`task/SPEC-056.md`（Status: APPROVED）
**实施顺序**：F1 → F2 → F5 → F3 → F4（F3/F4 依赖 F1+F2，F5 仅依赖 F1）

---

## 概览

| 步骤 | 文件 | 类型 | 描述 |
|------|------|------|------|
| F1 | `backtest/engine.py` | 修改 | 回测循环加入 ivp63 计算 + signal_history + IVSnapshot |
| F2 | `strategy/selector.py` | 修改 | StrategyParams 新增 disable_entry_gates 开关，包裹四道门 |
| F5 | `backtest/run_event_study.py` | 修改 | 返回 DataFrame 追加信号列 |
| F3 | `backtest/run_strategy_audit.py` | 新建 | Matrix 层：全历史信号桶矩阵 |
| F4 | `backtest/run_conditional_pnl.py` | 新建 | Risk 层：条件累计 P&L 时间序列 |

---

## F1 — `backtest/engine.py`

### 变更 1：ivp63 计算（在 ivp 计算之后插入）

定位：`ivp = compute_iv_percentile(iv_window)` 这一行之后（约第 724 行）。

在该行之后紧接插入：

```python
        # SPEC-056 F1: ivp63 for IVP four-quadrant tagging
        _w63 = (vix_window.iloc[-63:] if len(vix_window) >= 63 else vix_window).copy()
        _w63.iloc[-1] = vix
        if len(_w63) < 63:
            ivp63_val: float = float(ivp)
        else:
            ivp63_val = round(
                float((_w63.iloc[:-1] < float(_w63.iloc[-1])).mean()) * 100.0, 1
            )
        _regime_decay = (float(ivp) >= 50.0) and (ivp63_val < 50.0)
        _local_spike  = (ivp63_val >= 50.0) and (float(ivp) < 50.0)
```

### 变更 2：IVSnapshot 构造（约第 761–765 行）

**现有代码**：
```python
        iv_snap    = IVSnapshot(
            date=str(date.date()), vix=vix,
            iv_rank=ivr, iv_percentile=ivp, iv_signal=iv_eff,
            iv_52w_high=float(iv_window.max()), iv_52w_low=float(iv_window.min()),
        )
```

**替换为**：
```python
        iv_snap    = IVSnapshot(
            date=str(date.date()), vix=vix,
            iv_rank=ivr, iv_percentile=ivp, iv_signal=iv_eff,
            iv_52w_high=float(iv_window.max()), iv_52w_low=float(iv_window.min()),
            ivp63=ivp63_val,
            ivp252=float(ivp),
            regime_decay=_regime_decay,
        )
```

（`local_spike` 不需要放入 IVSnapshot，由 selector.py 内部计算。`ivp63` 和 `regime_decay` 已是 SPEC-048 定义的 IVSnapshot 字段。）

### 变更 3：signal_history 追加字段（约第 778–792 行的 dict）

在 `signal_history.append({...})` 的 dict 末尾，在 `"bearish_streak": bearish_streak,` 之后添加：

```python
            "ivp63":          round(ivp63_val, 1),
            "ivp252":         round(float(ivp), 1),
            "regime_decay":   _regime_decay,
            "local_spike":    _local_spike,
```

---

## F2 — `strategy/selector.py`

### 变更 1：StrategyParams 新增字段

定位：`bearish_persistence_days: int = 1` 这一行（约第 116 行）之后插入：

```python
    # Research mode: bypass IVP entry gates for full-history matrix analysis.
    # NEVER set to True in production. See SPEC-056.
    disable_entry_gates: bool = False
```

### 变更 2：包裹 DIAGONAL 三道门（LOW_VOL + BULLISH 分支，约第 611–639 行）

**现有代码**（三道门独立）：
```python
        if t == TrendSignal.BULLISH:
            # ── Gate 1 (SPEC-049): ivp252 marginal zone ──────────────────
            if DIAGONAL_IVP252_GATE_LO <= iv.ivp252 <= DIAGONAL_IVP252_GATE_HI:
                return _reduce_wait(
                    f"LOW_VOL + BULLISH but ivp252={iv.ivp252:.0f} in {DIAGONAL_IVP252_GATE_LO}–{DIAGONAL_IVP252_GATE_HI} "
                    "marginal zone — long-term vol environment transitional; DIAGONAL edge reduced",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
                    params=params,
                )

            # ── Gate 2 (SPEC-051): IV=HIGH in LOW_VOL ────────────────────
            if iv_s == IVSignal.HIGH:
                return _reduce_wait(
                    f"LOW_VOL + BULLISH but IV=HIGH (IVP={iv.iv_percentile:.0f}) — "
                    "vol expansion signal in low-vol regime; DIAGONAL short leg exposed",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
                    params=params,
                )

            # ── Gate 3 (SPEC-054): both-high ─────────────────────────────
            if iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN and iv.ivp252 >= REGIME_DECAY_IVP252_MIN:
                return _reduce_wait(
                    f"LOW_VOL + BULLISH but ivp63={iv.ivp63:.0f} >= 50 AND ivp252={iv.ivp252:.0f} >= 50 "
                    "(both-high) — near-term AND long-term vol stressed; DIAGONAL tail risk too high",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
                    params=params,
                )
```

**替换为**（用 `if not params.disable_entry_gates:` 包裹全部三道门）：
```python
        if t == TrendSignal.BULLISH:
            if not params.disable_entry_gates:
                # ── Gate 1 (SPEC-049): ivp252 marginal zone ──────────────────
                if DIAGONAL_IVP252_GATE_LO <= iv.ivp252 <= DIAGONAL_IVP252_GATE_HI:
                    return _reduce_wait(
                        f"LOW_VOL + BULLISH but ivp252={iv.ivp252:.0f} in {DIAGONAL_IVP252_GATE_LO}–{DIAGONAL_IVP252_GATE_HI} "
                        "marginal zone — long-term vol environment transitional; DIAGONAL edge reduced",
                        vix, iv, trend, macro_warn,
                        canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
                        params=params,
                    )

                # ── Gate 2 (SPEC-051): IV=HIGH in LOW_VOL ────────────────────
                if iv_s == IVSignal.HIGH:
                    return _reduce_wait(
                        f"LOW_VOL + BULLISH but IV=HIGH (IVP={iv.iv_percentile:.0f}) — "
                        "vol expansion signal in low-vol regime; DIAGONAL short leg exposed",
                        vix, iv, trend, macro_warn,
                        canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
                        params=params,
                    )

                # ── Gate 3 (SPEC-054): both-high ─────────────────────────────
                if iv.ivp63 >= LOCAL_SPIKE_IVP63_MIN and iv.ivp252 >= REGIME_DECAY_IVP252_MIN:
                    return _reduce_wait(
                        f"LOW_VOL + BULLISH but ivp63={iv.ivp63:.0f} >= 50 AND ivp252={iv.ivp252:.0f} >= 50 "
                        "(both-high) — near-term AND long-term vol stressed; DIAGONAL tail risk too high",
                        vix, iv, trend, macro_warn,
                        canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
                        params=params,
                    )
```

### 变更 3：包裹 BCS_HV ivp63 门（HIGH_VOL + BEARISH，约第 440–447 行）

**现有代码**：
```python
            if iv.ivp63 >= IVP63_BCS_BLOCK:
                return _reduce_wait(
                    f"HIGH_VOL + BEARISH but ivp63={iv.ivp63:.0f} >= {IVP63_BCS_BLOCK} — "
                    "VIX at 63-day high; mean reversion risk too elevated for BCS_HV short call",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.BEAR_CALL_SPREAD_HV.value,
                    params=params,
                )
```

**替换为**：
```python
            if not params.disable_entry_gates and iv.ivp63 >= IVP63_BCS_BLOCK:
                return _reduce_wait(
                    f"HIGH_VOL + BEARISH but ivp63={iv.ivp63:.0f} >= {IVP63_BCS_BLOCK} — "
                    "VIX at 63-day high; mean reversion risk too elevated for BCS_HV short call",
                    vix, iv, trend, macro_warn,
                    canonical_strategy=StrategyName.BEAR_CALL_SPREAD_HV.value,
                    params=params,
                )
```

> **注意**：VIX_RISING 检查（`if vix.trend == Trend.RISING:`）以及 `extreme_vix` 检查不包裹，始终生效。

---

## F5 — `backtest/run_event_study.py`（扩展信号列）

**现有返回 dict**（`rows.append({...})`）：
```python
        rows.append({
            "entry_date": entry,
            "exit_date": exit_date,
            "pnl": trade.exit_pnl,
            "hit_target": trade.exit_reason == "50pct_profit",
            "strategy_key": strategy_key,
        })
```

**步骤**：

1. 在 `result = run_backtest(...)` 之后，构建 date→signal 查找表：
```python
    sig_by_date: dict[str, dict] = {row["date"]: row for row in result.signals}
```

2. 将 `rows.append` 扩展为：
```python
        sig = sig_by_date.get(str(entry.date()), {})
        rows.append({
            "entry_date":    entry,
            "exit_date":     exit_date,
            "pnl":           trade.exit_pnl,
            "hit_target":    trade.exit_reason == "50pct_profit",
            "strategy_key":  strategy_key,
            # signal columns (SPEC-056 F5)
            "regime":        sig.get("regime", ""),
            "trend":         sig.get("trend", ""),
            "ivp252":        sig.get("ivp252", float("nan")),
            "ivp63":         sig.get("ivp63", float("nan")),
            "regime_decay":  sig.get("regime_decay", False),
            "local_spike":   sig.get("local_spike", False),
        })
```

---

## F3 — `backtest/run_strategy_audit.py`（新建）

```python
"""
Strategy Environment Audit — Matrix Layer (SPEC-056 F3)

Runs each strategy with entry gates disabled over the full history.
Buckets trades by signal environment and reports key statistics per bucket.
"""
from __future__ import annotations

import math
import os
from dataclasses import replace

import pandas as pd

from backtest.engine import run_backtest, DEFAULT_PARAMS
from strategy.catalog import STRATEGIES_BY_KEY, strategy_key as catalog_key

MIN_BUCKET_N = 5

# Signal environment bucket definitions
# Each bucket is checked independently (not exclusive / exhaustive across dimensions)
BUCKETS: list[tuple[str, str]] = [
    # IVP four-quadrant
    ("ivp_double_low",    "ivp252 < 50 AND ivp63 < 50"),
    ("ivp_regime_decay",  "ivp252 >= 50 AND ivp63 < 50"),
    ("ivp_local_spike",   "ivp63 >= 50 AND ivp252 < 50"),
    ("ivp_both_high",     "ivp63 >= 50 AND ivp252 >= 50"),
    # VIX Regime
    ("regime_low_vol",    "regime == LOW_VOL"),
    ("regime_normal",     "regime == NORMAL"),
    ("regime_high_vol",   "regime == HIGH_VOL"),
    # Trend
    ("trend_bullish",     "trend == BULLISH"),
    ("trend_neutral",     "trend == NEUTRAL"),
    ("trend_bearish",     "trend == BEARISH"),
]


def _bucket_mask(df: pd.DataFrame, bucket: str) -> pd.Series:
    """Return boolean mask for the given bucket name."""
    if bucket == "ivp_double_low":
        return (df["ivp252"] < 50) & (df["ivp63"] < 50)
    if bucket == "ivp_regime_decay":
        return (df["ivp252"] >= 50) & (df["ivp63"] < 50)
    if bucket == "ivp_local_spike":
        return (df["ivp63"] >= 50) & (df["ivp252"] < 50)
    if bucket == "ivp_both_high":
        return (df["ivp63"] >= 50) & (df["ivp252"] >= 50)
    if bucket == "regime_low_vol":
        return df["regime"] == "LOW_VOL"
    if bucket == "regime_normal":
        return df["regime"] == "NORMAL"
    if bucket == "regime_high_vol":
        return df["regime"] == "HIGH_VOL"
    if bucket == "trend_bullish":
        return df["trend"] == "BULLISH"
    if bucket == "trend_neutral":
        return df["trend"] == "NEUTRAL"
    if bucket == "trend_bearish":
        return df["trend"] == "BEARISH"
    raise ValueError(f"Unknown bucket: {bucket!r}")


def _bucket_stats(sub: pd.DataFrame, bucket: str, description: str) -> dict:
    n = len(sub)
    if n == 0:
        return {
            "bucket": bucket, "description": description,
            "n": 0, "avg_pnl": float("nan"), "win_rate": float("nan"),
            "sharpe": float("nan"), "max_consec_loss": 0,
            "avg_hold_days": float("nan"), "low_n_flag": True,
        }
    avg_pnl = sub["pnl"].mean()
    win_rate = float((sub["pnl"] > 0).mean())
    std = sub["pnl"].std()
    sharpe = round((avg_pnl / std * math.sqrt(252 / 21)), 2) if std and std > 0 else 0.0

    # Max consecutive losses
    consec = max_consec = 0
    for p in sub["pnl"]:
        if p <= 0:
            consec += 1
            max_consec = max(max_consec, consec)
        else:
            consec = 0

    avg_hold = sub["hold_days"].mean() if "hold_days" in sub.columns else float("nan")

    return {
        "bucket":        bucket,
        "description":   description,
        "n":             n,
        "avg_pnl":       round(avg_pnl, 0),
        "win_rate":      round(win_rate, 3),
        "sharpe":        sharpe,
        "max_consec_loss": max_consec,
        "avg_hold_days": round(avg_hold, 1) if not math.isnan(avg_hold) else float("nan"),
        "low_n_flag":    n < MIN_BUCKET_N,
    }


def run_strategy_audit(
    strategy_keys: list[str] | None = None,
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    save_csv: bool = True,
) -> dict[str, pd.DataFrame]:
    """
    For each strategy, run the full backtest with entry gates disabled,
    then bucket all trades by signal environment.

    Returns: dict[strategy_key → audit DataFrame]
    """
    keys = strategy_keys or [
        k for k in STRATEGIES_BY_KEY if k != "reduce_wait"
    ]

    audit_params = replace(DEFAULT_PARAMS, disable_entry_gates=True)
    result = run_backtest(
        start_date=start_date,
        end_date=end_date,
        params=audit_params,
        verbose=False,
    )

    # Build date→signal lookup
    sig_by_date: dict[str, dict] = {row["date"]: row for row in result.signals}

    # Attach signal data to each trade
    trade_rows = []
    for trade in result.trades:
        sig = sig_by_date.get(trade.entry_date, {})
        key = catalog_key(trade.strategy.value)
        entry_dt = pd.Timestamp(trade.entry_date)
        exit_dt  = pd.Timestamp(trade.exit_date) if trade.exit_date else entry_dt
        trade_rows.append({
            "strategy_key": key,
            "entry_date":   entry_dt,
            "exit_date":    exit_dt,
            "hold_days":    (exit_dt - entry_dt).days,
            "pnl":          trade.exit_pnl,
            "regime":       sig.get("regime", ""),
            "trend":        sig.get("trend", ""),
            "ivp252":       sig.get("ivp252", float("nan")),
            "ivp63":        sig.get("ivp63", float("nan")),
            "regime_decay": sig.get("regime_decay", False),
            "local_spike":  sig.get("local_spike", False),
        })

    all_trades = pd.DataFrame(trade_rows)

    results: dict[str, pd.DataFrame] = {}
    os.makedirs("backtest/output", exist_ok=True)

    for key in keys:
        sub_all = all_trades[all_trades["strategy_key"] == key]

        rows = [
            _bucket_stats(sub_all[_bucket_mask(sub_all, b)], b, desc)
            for b, desc in BUCKETS
        ]
        df = pd.DataFrame(rows)
        results[key] = df

        if save_csv:
            path = f"backtest/output/audit_{key}.csv"
            df.to_csv(path, index=False)

    return results


if __name__ == "__main__":
    audit = run_strategy_audit()
    for key, df in audit.items():
        print(f"\n=== {key} ===")
        print(df.to_string(index=False))
```

---

## F4 — `backtest/run_conditional_pnl.py`（新建）

```python
"""
Conditional Cumulative P&L — Risk Layer (SPEC-056 F4)

Splits the P&L time-series by a signal state and shows how cumulative P&L
evolves within each signal environment. No independence assumption required.
"""
from __future__ import annotations

import os

import pandas as pd

from backtest.engine import run_backtest
from strategy.catalog import strategy_key as catalog_key


def run_conditional_pnl(
    strategy_key: str,
    signal_col: str,
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    save_csv: bool = True,
) -> pd.DataFrame:
    """
    For a given strategy and signal column, return a DataFrame showing
    daily P&L and cumulative P&L split by signal state.

    signal_col: any column in signal_history —
        e.g. "regime_decay" (bool), "local_spike" (bool), "regime" (str), "trend" (str)

    Returns DataFrame columns:
        date, signal_state, pnl, cum_pnl_by_state, cum_pnl_global, in_position
    """
    result = run_backtest(start_date=start_date, end_date=end_date, verbose=False)

    # Build date→signal lookup
    sig_df = pd.DataFrame(result.signals)
    sig_df["date"] = pd.to_datetime(sig_df["date"])
    sig_df = sig_df.set_index("date")

    # Build date→daily P&L lookup from trades
    pnl_by_date: dict[str, float] = {}
    in_pos_by_date: dict[str, bool] = {}
    for trade in result.trades:
        if catalog_key(trade.strategy.value) != strategy_key:
            continue
        entry = pd.Timestamp(trade.entry_date)
        exit_ = pd.Timestamp(trade.exit_date) if trade.exit_date else entry
        hold_days = max((exit_ - entry).days, 1)
        daily_pnl = trade.exit_pnl / hold_days
        # Distribute P&L evenly across holding period (approximation)
        for d in pd.date_range(entry, exit_, freq="B"):
            ds = str(d.date())
            pnl_by_date[ds] = pnl_by_date.get(ds, 0.0) + daily_pnl
            in_pos_by_date[ds] = True

    # Build output rows
    rows = []
    cum_global = 0.0
    cum_by_state: dict = {}

    for date, sig_row in sig_df.iterrows():
        if signal_col not in sig_row.index:
            raise ValueError(
                f"signal_col={signal_col!r} not found in signal_history. "
                f"Available: {list(sig_row.index)}"
            )
        state = sig_row[signal_col]
        ds = str(date.date())
        pnl = pnl_by_date.get(ds, 0.0)
        in_pos = in_pos_by_date.get(ds, False)

        cum_global += pnl
        cum_by_state[state] = cum_by_state.get(state, 0.0) + pnl

        rows.append({
            "date":             date,
            "signal_state":     state,
            "pnl":              round(pnl, 2),
            "cum_pnl_by_state": round(cum_by_state[state], 2),
            "cum_pnl_global":   round(cum_global, 2),
            "in_position":      in_pos,
        })

    df = pd.DataFrame(rows)

    if save_csv:
        os.makedirs("backtest/output", exist_ok=True)
        path = f"backtest/output/conditional_pnl_{strategy_key}_{signal_col}.csv"
        df.to_csv(path, index=False)

    return df


if __name__ == "__main__":
    for col in ["regime_decay", "local_spike", "regime"]:
        df = run_conditional_pnl("bull_call_diagonal", col)
        print(f"\n=== bull_call_diagonal × {col} ===")
        states = df["signal_state"].unique()
        for s in states:
            sub = df[df["signal_state"] == s]
            final_cum = sub["cum_pnl_by_state"].iloc[-1]
            in_pos_days = sub["in_position"].sum()
            print(f"  state={s}: final_cum_pnl=${final_cum:,.0f}, in_position_days={in_pos_days}")
```

---

## 测试用例

文件：`tests/test_spec_056.py`

```python
"""
Tests for SPEC-056: Data-driven strategy environment analysis tools
"""
from __future__ import annotations
import math
from dataclasses import replace
from unittest.mock import patch
import pandas as pd
import pytest

# ─── T1: signal_history 含 ivp63 / ivp252 / regime_decay / local_spike ────────
def test_t1_signal_history_has_ivp63_fields():
    """AC1: signal_history rows contain ivp63, ivp252, regime_decay, local_spike."""
    from backtest.engine import run_backtest
    result = run_backtest(start_date="2020-01-01", end_date="2020-06-30", verbose=False)
    assert result.signals, "signal_history should not be empty"
    row = result.signals[0]
    assert "ivp63" in row, "ivp63 missing from signal_history"
    assert "ivp252" in row, "ivp252 missing from signal_history"
    assert "regime_decay" in row, "regime_decay missing from signal_history"
    assert "local_spike" in row, "local_spike missing from signal_history"
    assert isinstance(row["ivp63"], float), "ivp63 should be float"
    assert isinstance(row["regime_decay"], bool), "regime_decay should be bool"


# ─── T2: regime_decay / local_spike 互斥 ──────────────────────────────────────
def test_t2_regime_decay_local_spike_mutually_exclusive():
    """regime_decay and local_spike cannot both be True on the same day."""
    from backtest.engine import run_backtest
    result = run_backtest(start_date="2010-01-01", end_date="2020-12-31", verbose=False)
    for row in result.signals:
        assert not (row["regime_decay"] and row["local_spike"]), (
            f"Both regime_decay and local_spike True on {row['date']}"
        )


# ─── T3: IVSnapshot has ivp63 field ───────────────────────────────────────────
def test_t3_iv_snapshot_ivp63_field():
    """IVSnapshot constructed in engine loop should have ivp63 field populated."""
    from backtest.engine import run_backtest
    result = run_backtest(start_date="2020-01-01", end_date="2020-03-31", verbose=False)
    # Indirect check via signal_history
    assert all(0 <= row["ivp63"] <= 100 for row in result.signals), (
        "ivp63 values should be in [0, 100]"
    )


# ─── T4: disable_entry_gates=False is the default ─────────────────────────────
def test_t4_default_disable_entry_gates_false():
    """AC7: DEFAULT_PARAMS.disable_entry_gates is False."""
    from strategy.selector import DEFAULT_PARAMS
    assert DEFAULT_PARAMS.disable_entry_gates is False


# ─── T5: disable_entry_gates=True bypasses DIAGONAL Gate 1 ───────────────────
def test_t5_disable_gates_bypasses_diagonal_gate1():
    """AC2: With disable_entry_gates=True, ivp252 in [30,50] does NOT trigger REDUCE_WAIT."""
    from strategy.selector import (
        select_strategy, StrategyParams,
        VixSnapshot, IVSnapshot, TrendSnapshot, StrategyName,
    )
    from signals.vix_regime import Regime, Trend
    from signals.trend import TrendSignal
    from signals.iv_rank import IVSignal

    params = StrategyParams(disable_entry_gates=True)
    vix_snap = VixSnapshot(
        date="2024-01-01", vix=14.0, regime=Regime.LOW_VOL,
        trend=Trend.FLAT, vix_5d_avg=14.0, vix_5d_ago=14.0,
        transition_warning=False, vix3m=15.0, backwardation=False,
    )
    iv_snap = IVSnapshot(
        date="2024-01-01", vix=14.0,
        iv_rank=25.0, iv_percentile=40.0, iv_signal=IVSignal.NEUTRAL,
        iv_52w_high=35.0, iv_52w_low=10.0,
        ivp63=45.0, ivp252=40.0, regime_decay=False,  # ivp252=40 is in Gate 1 zone [30,50]
    )
    trend_snap = TrendSnapshot(
        date="2024-01-01", spx=4800.0,
        ma20=4750.0, ma50=4700.0, ma_gap_pct=0.02, signal=TrendSignal.BULLISH,
        above_200=True, atr14=None, gap_sigma=None,
    )
    rec = select_strategy(vix_snap, iv_snap, trend_snap, params)
    assert rec.strategy == StrategyName.BULL_CALL_DIAGONAL, (
        f"Expected DIAGONAL when gates disabled, got {rec.strategy}"
    )


# ─── T6: disable_entry_gates=True bypasses DIAGONAL Gate 2 ───────────────────
def test_t6_disable_gates_bypasses_diagonal_gate2():
    """disable_entry_gates=True: IV=HIGH does NOT trigger REDUCE_WAIT for LOW_VOL+BULLISH."""
    from strategy.selector import (
        select_strategy, StrategyParams,
        VixSnapshot, IVSnapshot, TrendSnapshot, StrategyName,
    )
    from signals.vix_regime import Regime, Trend
    from signals.trend import TrendSignal
    from signals.iv_rank import IVSignal

    params = StrategyParams(disable_entry_gates=True)
    vix_snap = VixSnapshot(
        date="2024-01-01", vix=14.0, regime=Regime.LOW_VOL,
        trend=Trend.FLAT, vix_5d_avg=14.0, vix_5d_ago=14.0,
        transition_warning=False, vix3m=15.0, backwardation=False,
    )
    iv_snap = IVSnapshot(
        date="2024-01-01", vix=14.0,
        iv_rank=70.0, iv_percentile=25.0, iv_signal=IVSignal.HIGH,  # IV=HIGH
        iv_52w_high=35.0, iv_52w_low=10.0,
        ivp63=25.0, ivp252=25.0, regime_decay=False,
    )
    trend_snap = TrendSnapshot(
        date="2024-01-01", spx=4800.0,
        ma20=4750.0, ma50=4700.0, ma_gap_pct=0.02, signal=TrendSignal.BULLISH,
        above_200=True, atr14=None, gap_sigma=None,
    )
    rec = select_strategy(vix_snap, iv_snap, trend_snap, params)
    assert rec.strategy == StrategyName.BULL_CALL_DIAGONAL


# ─── T7: disable_entry_gates=True bypasses DIAGONAL Gate 3 ───────────────────
def test_t7_disable_gates_bypasses_diagonal_gate3():
    """disable_entry_gates=True: ivp63≥50 AND ivp252≥50 does NOT trigger REDUCE_WAIT."""
    from strategy.selector import (
        select_strategy, StrategyParams,
        VixSnapshot, IVSnapshot, TrendSnapshot, StrategyName,
    )
    from signals.vix_regime import Regime, Trend
    from signals.trend import TrendSignal
    from signals.iv_rank import IVSignal

    params = StrategyParams(disable_entry_gates=True)
    vix_snap = VixSnapshot(
        date="2024-01-01", vix=14.0, regime=Regime.LOW_VOL,
        trend=Trend.FLAT, vix_5d_avg=14.0, vix_5d_ago=14.0,
        transition_warning=False, vix3m=15.0, backwardation=False,
    )
    iv_snap = IVSnapshot(
        date="2024-01-01", vix=14.0,
        iv_rank=60.0, iv_percentile=25.0, iv_signal=IVSignal.NEUTRAL,
        iv_52w_high=35.0, iv_52w_low=10.0,
        ivp63=60.0, ivp252=60.0, regime_decay=False,  # both-high
    )
    trend_snap = TrendSnapshot(
        date="2024-01-01", spx=4800.0,
        ma20=4750.0, ma50=4700.0, ma_gap_pct=0.02, signal=TrendSignal.BULLISH,
        above_200=True, atr14=None, gap_sigma=None,
    )
    rec = select_strategy(vix_snap, iv_snap, trend_snap, params)
    assert rec.strategy == StrategyName.BULL_CALL_DIAGONAL


# ─── T8: disable_entry_gates=True bypasses BCS_HV Gate ───────────────────────
def test_t8_disable_gates_bypasses_bcs_hv_gate():
    """disable_entry_gates=True: ivp63≥70 in HIGH_VOL+BEARISH does NOT block BCS_HV."""
    from strategy.selector import (
        select_strategy, StrategyParams,
        VixSnapshot, IVSnapshot, TrendSnapshot, StrategyName,
    )
    from signals.vix_regime import Regime, Trend
    from signals.trend import TrendSignal
    from signals.iv_rank import IVSignal

    params = StrategyParams(disable_entry_gates=True)
    vix_snap = VixSnapshot(
        date="2024-01-01", vix=28.0, regime=Regime.HIGH_VOL,
        trend=Trend.FLAT, vix_5d_avg=27.0, vix_5d_ago=26.0,  # NOT RISING
        transition_warning=False, vix3m=27.0, backwardation=False,
    )
    iv_snap = IVSnapshot(
        date="2024-01-01", vix=28.0,
        iv_rank=80.0, iv_percentile=25.0, iv_signal=IVSignal.HIGH,
        iv_52w_high=40.0, iv_52w_low=15.0,
        ivp63=75.0, ivp252=25.0, regime_decay=False,  # ivp63 >= 70
    )
    trend_snap = TrendSnapshot(
        date="2024-01-01", spx=4200.0,
        ma20=4300.0, ma50=4400.0, ma_gap_pct=-0.05, signal=TrendSignal.BEARISH,
        above_200=False, atr14=None, gap_sigma=None,
    )
    rec = select_strategy(vix_snap, iv_snap, trend_snap, params)
    assert rec.strategy == StrategyName.BEAR_CALL_SPREAD_HV


# ─── T9: gates still work when disable_entry_gates=False ─────────────────────
def test_t9_gates_still_active_when_not_disabled():
    """disable_entry_gates=False (default): Gate 1 still fires for ivp252=40."""
    from strategy.selector import (
        select_strategy, DEFAULT_PARAMS,
        VixSnapshot, IVSnapshot, TrendSnapshot, StrategyName,
    )
    from signals.vix_regime import Regime, Trend
    from signals.trend import TrendSignal
    from signals.iv_rank import IVSignal

    vix_snap = VixSnapshot(
        date="2024-01-01", vix=14.0, regime=Regime.LOW_VOL,
        trend=Trend.FLAT, vix_5d_avg=14.0, vix_5d_ago=14.0,
        transition_warning=False, vix3m=15.0, backwardation=False,
    )
    iv_snap = IVSnapshot(
        date="2024-01-01", vix=14.0,
        iv_rank=25.0, iv_percentile=40.0, iv_signal=IVSignal.NEUTRAL,
        iv_52w_high=35.0, iv_52w_low=10.0,
        ivp63=45.0, ivp252=40.0, regime_decay=False,
    )
    trend_snap = TrendSnapshot(
        date="2024-01-01", spx=4800.0,
        ma20=4750.0, ma50=4700.0, ma_gap_pct=0.02, signal=TrendSignal.BULLISH,
        above_200=True, atr14=None, gap_sigma=None,
    )
    rec = select_strategy(vix_snap, iv_snap, trend_snap, DEFAULT_PARAMS)
    assert rec.strategy == StrategyName.REDUCE_WAIT, (
        "Gate 1 should fire and return REDUCE_WAIT when gates enabled"
    )


# ─── T10: run_event_study returns signal columns ──────────────────────────────
def test_t10_event_study_has_signal_cols():
    """AC5: run_event_study DataFrame contains ivp63, regime_decay, local_spike columns."""
    from backtest.run_event_study import run_event_study
    df = run_event_study("bull_call_diagonal", fixed_hold_days=21,
                         start_date="2015-01-01", end_date="2020-12-31")
    if df.empty:
        pytest.skip("No DIAGONAL trades in test window")
    for col in ["regime", "trend", "ivp252", "ivp63", "regime_decay", "local_spike"]:
        assert col in df.columns, f"Column {col!r} missing from event study DataFrame"


# ─── T11: run_conditional_pnl returns correct structure ──────────────────────
def test_t11_conditional_pnl_structure():
    """AC4: run_conditional_pnl returns date, signal_state, pnl, cum_pnl_by_state cols."""
    from backtest.run_conditional_pnl import run_conditional_pnl
    df = run_conditional_pnl(
        "bull_call_diagonal", "regime_decay",
        start_date="2018-01-01", end_date="2020-12-31",
        save_csv=False,
    )
    assert not df.empty
    for col in ["date", "signal_state", "pnl", "cum_pnl_by_state", "cum_pnl_global", "in_position"]:
        assert col in df.columns, f"Column {col!r} missing"
    # Should have both True and False states
    states = set(df["signal_state"].unique())
    assert True in states or False in states


# ─── T12: run_strategy_audit returns 10-bucket DataFrame per strategy ─────────
def test_t12_strategy_audit_bucket_count():
    """AC3: run_strategy_audit returns DataFrame with all 10 buckets."""
    from backtest.run_strategy_audit import run_strategy_audit, BUCKETS
    audit = run_strategy_audit(
        strategy_keys=["bull_call_diagonal"],
        start_date="2010-01-01", end_date="2023-12-31",
        save_csv=False,
    )
    assert "bull_call_diagonal" in audit
    df = audit["bull_call_diagonal"]
    assert len(df) == len(BUCKETS), f"Expected {len(BUCKETS)} buckets, got {len(df)}"


# ─── T13: run_strategy_audit with disable_entry_gates has >= standard trade count ─
def test_t13_audit_gates_disabled_more_trades():
    """Gates-disabled run should have >= same or more DIAGONAL trades than standard run."""
    from backtest.engine import run_backtest, DEFAULT_PARAMS
    from dataclasses import replace
    from strategy.catalog import strategy_key as catalog_key
    from strategy.selector import StrategyName

    std_result = run_backtest(start_date="2015-01-01", end_date="2023-12-31", verbose=False)
    std_diag = sum(
        1 for t in std_result.trades
        if catalog_key(t.strategy.value) == "bull_call_diagonal"
    )

    audit_params = replace(DEFAULT_PARAMS, disable_entry_gates=True)
    audit_result = run_backtest(start_date="2015-01-01", end_date="2023-12-31",
                                params=audit_params, verbose=False)
    audit_diag = sum(
        1 for t in audit_result.trades
        if catalog_key(t.strategy.value) == "bull_call_diagonal"
    )

    assert audit_diag >= std_diag, (
        f"Gates-disabled should have >= trades: audit={audit_diag}, std={std_diag}"
    )


# ─── T14: ivp252 == ivp in signal_history ─────────────────────────────────────
def test_t14_ivp252_equals_ivp():
    """ivp252 in signal_history should equal the existing ivp field (both 252-day)."""
    from backtest.engine import run_backtest
    result = run_backtest(start_date="2020-01-01", end_date="2020-12-31", verbose=False)
    for row in result.signals:
        assert abs(row["ivp252"] - row["ivp"]) < 0.01, (
            f"ivp252={row['ivp252']} != ivp={row['ivp']} on {row['date']}"
        )
```

---

## 验收清单

完成所有变更后，运行：

```bash
python -m pytest tests/test_spec_056.py -v
```

期望：**14/14 通过**。

---

## 注意事项

1. **run_strategy_audit 中的 `replace(DEFAULT_PARAMS, ...)`**：需要从 `dataclasses` 导入 `replace`，同时 `DEFAULT_PARAMS` 须从 `strategy.selector` 导入（已经在 engine.py 的现有 import 中存在）。

2. **ivp252 vs ivp**：engine.py 中已有 `ivp`（252 日百分位）。新增的 `ivp252` 字段值等于 `ivp`，存在于 signal_history 以明确语义（供研究工具使用）。不删除原 `ivp` 字段（向后兼容）。

3. **output 目录**：`backtest/output/` 若不存在，F3/F4 工具在 `save_csv=True`（默认）时自动创建。测试用 `save_csv=False` 跳过文件写入。

4. **F5 的 `run_backtest()` 调用**：`run_event_study.py` 已有 `result = run_backtest(...)` 调用，只需在此之后构建 `sig_by_date` 查找表，无需额外 import。

5. **`_w63` 临时变量命名**：使用带前缀 `_` 的名称避免与外层循环变量冲突。

---

## 交接文件

实施完成后，请创建 `task/SPEC-056_handoff.md`，格式参照 `task/SPEC-048-055_handoff.md`，包含：
- 修改的文件列表与行号
- 新建的文件列表
- 测试运行结果（通过数 / 总数）
- 任何偏离 Spec 的说明
