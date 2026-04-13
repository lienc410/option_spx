# Codex 实施指令 — SPEC-059

**Spec 文件**：`task/SPEC-059.md`（Status: APPROVED）
**前置条件**：SPEC-057 已 DONE，`backtest/output/matrix_audit.csv` 存在

---

## 概览

| 步骤 | 文件 | 类型 |
|------|------|------|
| F1 | `backtest/run_bootstrap_ci.py` | 新建：block bootstrap 核心函数 |
| F2 | `backtest/run_matrix_bootstrap.py` | 新建：矩阵级 bootstrap 汇总 |
| Tests | `tests/test_spec_059.py` | 新建：6 个验收测试 |

F1 先完成，F2 依赖 F1。

---

## F1 — `backtest/run_bootstrap_ci.py`（新建）

```python
"""
Block Bootstrap confidence interval for mean P&L (SPEC-059 F1).

Non-parametric resampling that preserves return autocorrelation and
vol clustering — no GBM or distributional assumptions.
"""
from __future__ import annotations

import math
import numpy as np

DEFAULT_N_BOOT   = 2000
MIN_N_BOOTSTRAP  = 10
DEFAULT_CI_LEVEL = 0.95


def bootstrap_ci(
    pnl_series: list[float] | np.ndarray,
    n_boot: int = DEFAULT_N_BOOT,
    ci: float = DEFAULT_CI_LEVEL,
    block_size: int | None = None,
) -> dict:
    """
    Block bootstrap confidence interval for the mean of pnl_series.

    Parameters
    ----------
    pnl_series : sequence of floats (P&L values in trade order)
    n_boot     : number of bootstrap samples
    ci         : confidence level (default 0.95)
    block_size : block length; if None, uses max(5, n // 4)

    Returns
    -------
    dict with keys:
        n, mean, ci_lo, ci_hi, ci_level, significant, block_size, n_boot
    For n < MIN_N_BOOTSTRAP, returns NaN ci values and significant=False.
    """
    arr = np.asarray(pnl_series, dtype=float)
    n = len(arr)

    if n < MIN_N_BOOTSTRAP:
        return {
            "n":          n,
            "mean":       float(np.mean(arr)) if n > 0 else float("nan"),
            "ci_lo":      float("nan"),
            "ci_hi":      float("nan"),
            "ci_level":   ci,
            "significant": False,
            "block_size": 0,
            "n_boot":     0,
        }

    bs = block_size if block_size is not None else max(5, n // 4)
    alpha = 1.0 - ci
    rng = np.random.default_rng(seed=42)

    boot_means = np.empty(n_boot)
    for b in range(n_boot):
        # Draw enough block start indices to cover n observations
        n_blocks = math.ceil(n / bs)
        starts = rng.integers(0, n - bs + 1, size=n_blocks)
        sample = np.concatenate([arr[s : s + bs] for s in starts])[:n]
        boot_means[b] = sample.mean()

    lo = float(np.percentile(boot_means, 100 * alpha / 2))
    hi = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))

    return {
        "n":           n,
        "mean":        round(float(arr.mean()), 2),
        "ci_lo":       round(lo, 2),
        "ci_hi":       round(hi, 2),
        "ci_level":    ci,
        "significant": lo > 0,
        "block_size":  bs,
        "n_boot":      n_boot,
    }
```

---

## F2 — `backtest/run_matrix_bootstrap.py`（新建）

```python
"""
Matrix-level block bootstrap (SPEC-059 F2).

Reads matrix_audit.csv (or re-runs the audit), applies block bootstrap
to every cell with n >= MIN_N_BOOTSTRAP, and outputs an extended CSV.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from dataclasses import replace

from backtest.run_bootstrap_ci import bootstrap_ci, MIN_N_BOOTSTRAP, DEFAULT_N_BOOT
from backtest.run_matrix_audit import run_matrix_audit, print_matrix, STRATEGY_KEYS
from backtest.engine import DEFAULT_PARAMS, run_backtest
from strategy.catalog import strategy_key as catalog_key


def run_matrix_bootstrap(
    matrix_csv: str = "backtest/output/matrix_audit.csv",
    n_boot: int = DEFAULT_N_BOOT,
    min_n: int = MIN_N_BOOTSTRAP,
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    save_csv: bool = True,
) -> pd.DataFrame:
    """
    For each (strategy × cell) with n >= min_n, compute block bootstrap CI.

    If matrix_csv exists, reads trade-level data by re-running force-entry
    backtest (needed to get individual P&L values per cell, not just aggregates).

    Returns DataFrame = matrix_audit columns + ci_lo, ci_hi, significant, block_size.
    """
    # Re-run force-entry backtest for each strategy to get trade-level P&L
    keys = STRATEGY_KEYS
    sig_lookup: dict[str, list[dict]] = {}

    for strategy_key in keys:
        forced_params = replace(DEFAULT_PARAMS, force_strategy=strategy_key)
        result = run_backtest(
            start_date=start_date,
            end_date=end_date,
            params=forced_params,
            verbose=False,
        )
        sig_by_date = {row["date"]: row for row in result.signals}

        trade_rows = []
        for trade in result.trades:
            if catalog_key(trade.strategy.value) != strategy_key:
                continue
            sig = sig_by_date.get(trade.entry_date, {})
            cell = f"{sig.get('regime','?')}|{sig.get('iv_signal','?')}|{sig.get('trend','?')}"
            trade_rows.append({"cell": cell, "pnl": trade.exit_pnl})

        sig_lookup[strategy_key] = trade_rows

    # Build matrix from audit (re-run to ensure consistency)
    audit_df = run_matrix_audit(
        strategy_keys=keys,
        start_date=start_date,
        end_date=end_date,
        save_csv=False,
    )

    ci_rows = []
    for _, row in audit_df.iterrows():
        sk   = row["strategy_key"]
        cell = row["cell"]
        n    = int(row["n"])

        # Extract P&L values for this (strategy × cell)
        pnls = [t["pnl"] for t in sig_lookup.get(sk, []) if t["cell"] == cell]

        if n < min_n or not pnls:
            ci = {
                "ci_lo":      float("nan"),
                "ci_hi":      float("nan"),
                "significant": False,
                "block_size": 0,
            }
        else:
            result_ci = bootstrap_ci(pnls, n_boot=n_boot)
            ci = {
                "ci_lo":      result_ci["ci_lo"],
                "ci_hi":      result_ci["ci_hi"],
                "significant": result_ci["significant"],
                "block_size": result_ci["block_size"],
            }

        ci_rows.append({**row.to_dict(), **ci})

    out_df = pd.DataFrame(ci_rows)

    if save_csv and not out_df.empty:
        os.makedirs("backtest/output", exist_ok=True)
        out_df.to_csv("backtest/output/matrix_audit_bootstrap.csv", index=False)

    return out_df


def print_bootstrap_matrix(df: pd.DataFrame) -> None:
    """
    Print pivot: rows = cell, columns = strategy.
    Format per cell: $mean [ci_lo, ci_hi] ✓/空
    Only shows n >= MIN_N_BOOTSTRAP rows.
    """
    if df.empty:
        print("No data.")
        return

    df_sig = df[df["n"] >= MIN_N_BOOTSTRAP].copy()
    rows = []
    for cell, grp in df_sig.groupby("cell"):
        row = {"cell": cell}
        for _, r in grp.iterrows():
            if pd.isna(r["ci_lo"]):
                tag = f"${r['avg_pnl']:,.0f} (n={r['n']})"
            else:
                marker = " ✓" if r["significant"] else ""
                tag = f"${r['avg_pnl']:,.0f} [${r['ci_lo']:,.0f},${r['ci_hi']:,.0f}]{marker}"
            row[r["strategy_key"]] = tag
        rows.append(row)

    pivot = pd.DataFrame(rows).set_index("cell")
    ordered = [k for k in STRATEGY_KEYS if k in pivot.columns]
    print(pivot[ordered].to_string())


if __name__ == "__main__":
    print("Running matrix bootstrap (this may take 10–15 minutes)...\n")
    df = run_matrix_bootstrap()
    print_bootstrap_matrix(df)
```

---

## Tests — `tests/test_spec_059.py`（新建）

```python
"""Tests for SPEC-059: Block Bootstrap CI."""
from __future__ import annotations
import math
import unittest
import numpy as np


class Spec059Tests(unittest.TestCase):

    # AC1: 全正序列 → significant=True, ci_lo > 0
    def test_ac1_all_positive_significant(self):
        from backtest.run_bootstrap_ci import bootstrap_ci
        result = bootstrap_ci([100.0] * 20)
        self.assertEqual(result["n"], 20)
        self.assertAlmostEqual(result["mean"], 100.0, places=1)
        self.assertTrue(result["significant"])
        self.assertGreater(result["ci_lo"], 0)

    # AC2: 全负序列 → significant=False, ci_hi < 0
    def test_ac2_all_negative_not_significant(self):
        from backtest.run_bootstrap_ci import bootstrap_ci
        result = bootstrap_ci([-50.0] * 20)
        self.assertFalse(result["significant"])
        self.assertLess(result["ci_hi"], 0)

    # AC3: 均值≈0 → significant=False（CI 跨零）
    def test_ac3_zero_mean_not_significant(self):
        from backtest.run_bootstrap_ci import bootstrap_ci
        result = bootstrap_ci([100.0, -100.0] * 10)
        self.assertFalse(result["significant"])
        self.assertLess(result["ci_lo"], 0)
        self.assertGreater(result["ci_hi"], 0)

    # AC4: run_matrix_bootstrap n ≥ 10 的 cell 有 ci_lo / ci_hi
    def test_ac4_bootstrap_fills_ci_for_sufficient_n(self):
        from backtest.run_matrix_bootstrap import run_matrix_bootstrap
        from backtest.run_bootstrap_ci import MIN_N_BOOTSTRAP
        df = run_matrix_bootstrap(
            start_date="2015-01-01",
            end_date="2023-12-31",
            n_boot=200,   # fast for test
            save_csv=False,
        )
        sufficient = df[df["n"] >= MIN_N_BOOTSTRAP]
        if sufficient.empty:
            self.skipTest("No cells with n >= MIN_N in test window")
        for _, row in sufficient.iterrows():
            self.assertFalse(
                math.isnan(row["ci_lo"]),
                f"ci_lo is NaN for n={row['n']} cell {row['cell']}"
            )

    # AC5: n < 10 的 cell 有 ci_lo = NaN, significant = False
    def test_ac5_low_n_cells_have_nan_ci(self):
        from backtest.run_matrix_bootstrap import run_matrix_bootstrap
        from backtest.run_bootstrap_ci import MIN_N_BOOTSTRAP
        df = run_matrix_bootstrap(
            start_date="2015-01-01",
            end_date="2023-12-31",
            n_boot=200,
            save_csv=False,
        )
        low_n = df[df["n"] < MIN_N_BOOTSTRAP]
        for _, row in low_n.iterrows():
            self.assertTrue(math.isnan(row["ci_lo"]),
                f"Expected NaN ci_lo for n={row['n']}")
            self.assertFalse(row["significant"])

    # AC6: CSV 写出
    def test_ac6_csv_saved(self):
        import os
        from backtest.run_matrix_bootstrap import run_matrix_bootstrap
        path = "backtest/output/matrix_audit_bootstrap.csv"
        if os.path.exists(path):
            os.remove(path)
        df = run_matrix_bootstrap(
            strategy_keys=["bull_call_diagonal"],
            start_date="2018-01-01",
            end_date="2022-12-31",
            n_boot=100,
            save_csv=True,
        )
        if df.empty:
            self.skipTest("No data")
        self.assertTrue(os.path.exists(path))
```

> **注意**：`run_matrix_bootstrap` 没有 `strategy_keys` 参数（它调用 `run_matrix_audit` 时不传 strategy_keys，默认全策略）。AC6 测试里如果要限制策略范围，需要在 `run_matrix_bootstrap` 中透传 `strategy_keys` 参数，或者在测试里接受全策略跑（慢）。**建议实现时给 `run_matrix_bootstrap` 加 `strategy_keys: list[str] | None = None` 参数，透传给内部调用**，这样测试可以只跑单策略加速。

---

## 注意事项

1. **`run_matrix_bootstrap` 的 `strategy_keys` 参数**：Spec 里没写，但测试 AC6 需要单策略跑，请加上并透传给 `run_backtest` 和 `run_matrix_audit` 的调用。

2. **seed 固定**：`bootstrap_ci` 使用 `np.random.default_rng(seed=42)` 确保结果可复现。

3. **block_size 上界**：当 n=10，block_size = max(5, 10//4) = max(5, 2) = 5，合理。当 n=100，block_size = 25，合理。

4. **运行时间**：全策略 × 全历史 × n_boot=2000 约需 10–15 分钟。测试使用 n_boot=100–200 加速。

5. **numpy 已在 venv 中可用**（engine.py 已使用 np）。

---

## 交接文件

完成后创建 `task/SPEC-059_handoff.md`，格式同前。
