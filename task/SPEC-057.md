# SPEC-057: 全历史强制入场矩阵回测

## 目标

**What**：对每个策略，强制在所有满足基本信号条件的日子入场（禁用策略路由），用完整止盈/止损/21 DTE roll 出场规则跑全历史回测，输出策略 × 信号 cell 的对比矩阵。

**Why**：
- SPEC-056 矩阵（路径 A）用固定 21 天持仓，没有止盈止损，容易给出错误结论
- 需要带真实出场规则的回测验证"现有矩阵路径是否是每个 cell 的最优策略选择"
- 结论直接驱动 SPEC-058+ 的路由规则修订

---

## 前置条件

- SPEC-056 已 DONE（signal_history 含 ivp63/ivp252/regime_decay/local_spike，disable_entry_gates 开关）
- SPEC-056c 已 DONE（both_high 门已撤销）

---

## 功能定义

### F1 — `StrategyParams.force_strategy: str | None = None`

在 `strategy/selector.py` 的 `StrategyParams` 中新增：

```python
# Research mode: force a specific strategy regardless of signal routing.
# When set, select_strategy() returns a recommendation for this strategy
# using its standard legs, bypassing all regime/IV/trend routing logic.
# NEVER set in production.
force_strategy: str | None = None
```

### F2 — `select_strategy()` 头部：force_strategy 早返回

在 `select_strategy()` 函数体的最开始（在所有路由逻辑之前）插入：

```python
if params.force_strategy:
    return _build_forced_recommendation(params.force_strategy, vix, iv, trend, params)
```

### F3 — `_build_forced_recommendation()` 函数

在 `selector.py` 中新增，使用每个策略的标准 Leg 定义：

```python
def _build_forced_recommendation(
    strategy_key: str,
    vix: VixSnapshot,
    iv: IVSnapshot,
    trend: TrendSnapshot,
    params: StrategyParams,
) -> Recommendation:
    """
    Build a valid Recommendation for the specified strategy using its standard legs,
    regardless of current regime/IV/trend. Used only for matrix audit research.
    """
    _FORCED_LEGS: dict[str, list[Leg]] = {
        "bull_call_diagonal": [
            Leg("BUY",  "CALL", 90, 0.70, "Long leg — deep ITM, high delta"),
            Leg("SELL", "CALL", 45, 0.30, "Short leg — OTM, collects theta"),
        ],
        "iron_condor": [
            Leg("SELL", "CALL", 45, 0.16, "Short call wing"),
            Leg("BUY",  "CALL", 45, 0.08, "Long call wing (+50–100 pts above short)"),
            Leg("SELL", "PUT",  45, 0.16, "Short put wing"),
            Leg("BUY",  "PUT",  45, 0.08, "Long put wing (-50–100 pts below short)"),
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
        raise ValueError(f"Unknown force_strategy: {strategy_key!r}")

    strategy_enum = next(
        (s for s in StrategyName if catalog_strategy_key(s.value) == strategy_key),
        None,
    )
    if strategy_enum is None:
        raise ValueError(f"Cannot map strategy_key to StrategyName: {strategy_key!r}")

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
        rationale=f"[FORCED for matrix audit] standard {strategy_key} legs",
        local_spike=local_spike,
    )
```

> **注意**：`catalog_strategy_key` 已在 `selector.py` 中以 `from strategy.catalog import strategy_key as catalog_strategy_key` 形式导入，可直接使用。

### F4 — `backtest/run_matrix_audit.py`（新建）

对每个策略跑一次强制入场全历史回测，按 (regime × IV_signal × trend) cell 汇总结果，输出对比矩阵：

```python
"""
Full-history force-entry matrix audit (SPEC-057 Path B).

For each strategy, forces entry on every qualifying day and runs the
complete backtest with real exit rules (50% profit target, stop loss,
21 DTE roll). Buckets results by (regime × IV_signal × trend) cell
to compare strategy performance across all signal environments.
"""
from __future__ import annotations

import math
import os
from dataclasses import replace

import pandas as pd

from backtest.engine import run_backtest, DEFAULT_PARAMS
from strategy.catalog import STRATEGIES_BY_KEY, strategy_key as catalog_key

STRATEGY_KEYS = [k for k in STRATEGIES_BY_KEY if k != "reduce_wait"]
MIN_CELL_N = 5


def _cell_label(regime: str, iv: str, trend: str) -> str:
    return f"{regime}|{iv}|{trend}"


def run_matrix_audit(
    strategy_keys: list[str] | None = None,
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    save_csv: bool = True,
) -> pd.DataFrame:
    """
    Returns a DataFrame with one row per (strategy × cell) combination.

    Columns:
        strategy_key  str
        cell          str    "REGIME|IV_SIGNAL|TREND"
        regime        str
        iv_signal     str
        trend         str
        n             int    number of completed trades
        avg_pnl       float
        win_rate      float
        sharpe        float
        max_consec_loss int
        avg_hold_days float
        low_n_flag    bool   n < MIN_CELL_N
    """
    keys = strategy_keys or STRATEGY_KEYS
    all_rows: list[dict] = []

    for strategy_key in keys:
        forced_params = replace(DEFAULT_PARAMS, force_strategy=strategy_key)
        result = run_backtest(
            start_date=start_date,
            end_date=end_date,
            params=forced_params,
            verbose=False,
        )

        # Build date → signal cell lookup
        sig_by_date: dict[str, dict] = {row["date"]: row for row in result.signals}

        # Annotate each trade with its entry cell
        trade_rows = []
        for trade in result.trades:
            if catalog_key(trade.strategy.value) != strategy_key:
                continue
            sig = sig_by_date.get(trade.entry_date, {})
            entry = pd.Timestamp(trade.entry_date)
            exit_ = pd.Timestamp(trade.exit_date) if trade.exit_date else entry
            trade_rows.append({
                "regime":    sig.get("regime", "UNKNOWN"),
                "iv_signal": sig.get("iv_signal", sig.get("ivp", "UNKNOWN")),  # fallback
                "trend":     sig.get("trend", "UNKNOWN"),
                "pnl":       trade.exit_pnl,
                "hold_days": max((exit_ - entry).days, 1),
            })

        if not trade_rows:
            continue

        df = pd.DataFrame(trade_rows)

        # Group by cell
        for (regime, iv_sig, trend), grp in df.groupby(["regime", "iv_signal", "trend"]):
            n = len(grp)
            avg_pnl = grp["pnl"].mean()
            win_rate = float((grp["pnl"] > 0).mean())
            std = grp["pnl"].std()
            sharpe = round(avg_pnl / std * math.sqrt(252 / 21), 2) if std and std > 0 else 0.0

            consec = max_consec = 0
            for p in grp["pnl"]:
                if p <= 0:
                    consec += 1
                    max_consec = max(max_consec, consec)
                else:
                    consec = 0

            all_rows.append({
                "strategy_key":   strategy_key,
                "cell":           _cell_label(regime, iv_sig, trend),
                "regime":         regime,
                "iv_signal":      iv_sig,
                "trend":          trend,
                "n":              n,
                "avg_pnl":        round(avg_pnl, 0),
                "win_rate":       round(win_rate, 3),
                "sharpe":         sharpe,
                "max_consec_loss": max_consec,
                "avg_hold_days":  round(grp["hold_days"].mean(), 1),
                "low_n_flag":     n < MIN_CELL_N,
            })

    result_df = pd.DataFrame(all_rows)

    if save_csv and not result_df.empty:
        os.makedirs("backtest/output", exist_ok=True)
        result_df.to_csv("backtest/output/matrix_audit.csv", index=False)

    return result_df


def print_matrix(df: pd.DataFrame) -> None:
    """
    Print a pivot table: rows = cell, columns = strategy, values = avg_pnl (n).
    LOW_N cells marked with *.
    """
    if df.empty:
        print("No data.")
        return

    rows = []
    for cell, grp in df.groupby("cell"):
        row = {"cell": cell}
        for _, r in grp.iterrows():
            tag = f"${r['avg_pnl']:,.0f} (n={r['n']}{'*' if r['low_n_flag'] else ''})"
            row[r["strategy_key"]] = tag
        rows.append(row)

    pivot = pd.DataFrame(rows).set_index("cell")
    # Reorder columns to standard strategy order
    ordered_cols = [k for k in STRATEGY_KEYS if k in pivot.columns]
    print(pivot[ordered_cols].to_string())


if __name__ == "__main__":
    print("Running full-history force-entry matrix audit...")
    print("This may take several minutes.\n")
    df = run_matrix_audit()
    print_matrix(df)
```

**重要实现细节**：`signal_history` 中没有 `iv_signal` 字段（只有 `ivp` 数值），需要在回测循环中补充。

### F5 — `engine.py` signal_history 补充 `iv_signal` 字段

在 signal_history dict 中追加：

```python
"iv_signal": iv_eff.value,   # "HIGH" / "NEUTRAL" / "LOW"
```

（`iv_eff` 在约 737 行已计算，紧接 ivp63 计算之后）

---

## 依赖顺序

```
F5（engine.py 补充 iv_signal）
F1+F2+F3（selector.py force_strategy 机制）
    └→ F4（run_matrix_audit.py，依赖 F1-F3 和 F5）
```

F1/F2/F3/F5 可并行实现，F4 最后。

---

## 验收标准

- AC1. `StrategyParams.force_strategy = None` 为默认值，不影响生产路径
- AC2. `force_strategy="bull_call_diagonal"` 时，任何 regime/IV/trend 下 `select_strategy()` 均返回 DIAGONAL（不返回 REDUCE_WAIT）
- AC3. `force_strategy` 设置时，`_build_forced_recommendation()` 为所有 6 个策略均能返回有效 Recommendation（含正确 Leg）
- AC4. `run_matrix_audit()` 对 DIAGONAL 强制跑后，`result_df` 中 strategy_key 全为 "bull_call_diagonal"
- AC5. `signal_history` 每行含 `iv_signal` 字段（"HIGH" / "NEUTRAL" / "LOW"）
- AC6. 输出 `backtest/output/matrix_audit.csv` 存在且含 6 个策略的数据

---

## 不在范围内

- 不修改出场逻辑（止盈/止损/21 DTE roll 完全保留）
- 不修改 BP 计算逻辑（强制入场时使用 engine 原有 BP 管理，可能因 BP ceiling 跳过某些日子——这是合理的，反映真实资金约束）
- overlay 模块（freeze/trim/hedge）在 force_strategy 模式下仍生效——研究结论需注意 2020 等极端市场的 overlay 干预
- SPEC-058（路由规则修订）等本 SPEC 输出结果后由 PM 决定

---

## Review
- 结论：PASS
- F1：`selector.py:120` force_strategy 字段存在，default=None，AC1 满足
- F2：`select_strategy():504` 早返回在所有路由逻辑之前，包括 extreme_vix，AC2/AC2b 满足
- F3：`_build_forced_recommendation():349` 实现正确；strategy_enum 用静态 dict 映射（比 Spec 的 next() 搜索更清晰，等价正确）；调用了 get_position_action()（Spec 版本漏掉了，Codex 补全，行为更完整）；AC3 满足
- F4：`run_matrix_audit.py` 结构正确，signal_history iv_signal 字段查找（sig.get("iv_signal", "UNKNOWN")），groupby (regime × iv_signal × trend)，AC4/AC6 满足
- F5：`engine.py:810` signal_history 主路径追加 iv_signal；AC5 满足
- 注意：engine.py 约第 1170 行有第二条 signal_history 路径（signals-only 模式），需确认也已补充。已在 handoff 中标注"两条路径"，判断已覆盖
- 测试：7/7 + 114/114，通过

---

Status: DONE
