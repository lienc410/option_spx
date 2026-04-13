# SPEC-059: Block Bootstrap 置信区间工具

## 目标

**What**：对 SPEC-057 矩阵中 n ≥ 10 的 cell，用 block bootstrap 对 P&L 序列重采样，生成 avg_pnl 的 95% 置信区间，判断统计显著性。

**Why**：
- SPEC-057 矩阵给出点估计（avg_pnl、Sharpe），但没有置信区间——无法区分"真实 alpha"和"运气"
- 标准 MC（GBM）不适合稀疏 cell（生成的是错误条件下的数据）
- Block Bootstrap 保留真实 return 分布、vol clustering 和路径依赖性，不引入参数假设
- 目标：对 n ≥ 10 的 cell 给出 95% CI，决策标准变为"CI 下界 > 0"而非"avg_pnl > 0"

---

## 方法论

### Block Bootstrap 原理

从同一 cell 内的 P&L 序列（按时间排序）中，以固定块长度 `block_size` 做有放回重采样，组合成与原序列等长的 bootstrap 样本，重复 `n_boot` 次，取 avg_pnl 的分布。

**块长度选择**：`block_size = max(5, n // 4)`——捕捉短期 return 自相关，同时保留足够的块数量。n < 10 时不做 bootstrap（LOW_N）。

**与标准 MC 的区别**：不假设正态分布，不用 GBM，直接用历史 P&L 做非参数重采样。

---

## 功能定义

### F1 — `backtest/run_bootstrap_ci.py`（新建）

```python
def bootstrap_ci(
    pnl_series: list[float] | np.ndarray,
    n_boot: int = 2000,
    ci: float = 0.95,
    block_size: int | None = None,
) -> dict:
    """
    Block bootstrap confidence interval for mean P&L.

    Returns:
        {
            "n":          int,
            "mean":       float,   # point estimate
            "ci_lo":      float,   # lower bound (e.g. 2.5th percentile)
            "ci_hi":      float,   # upper bound (e.g. 97.5th percentile)
            "ci_level":   float,   # e.g. 0.95
            "significant": bool,   # ci_lo > 0
            "block_size": int,
            "n_boot":     int,
        }
    """
```

### F2 — `backtest/run_matrix_bootstrap.py`（新建）

从 SPEC-057 的 `matrix_audit.csv` 读取结果，或直接调用 `run_matrix_audit()`，对每个 n ≥ 10 的 (strategy × cell) 运行 block bootstrap，输出扩展后的矩阵：

```python
def run_matrix_bootstrap(
    matrix_csv: str = "backtest/output/matrix_audit.csv",
    n_boot: int = 2000,
    min_n: int = 10,
    save_csv: bool = True,
) -> pd.DataFrame:
    """
    Returns DataFrame with all original matrix_audit columns plus:
        ci_lo         float   95% CI 下界
        ci_hi         float   95% CI 上界
        significant   bool    ci_lo > 0（avg_pnl 在 95% 置信水平下显著为正）
        block_size    int     实际使用的块长度
    """
```

输出保存至 `backtest/output/matrix_audit_bootstrap.csv`。

### F3 — `print_bootstrap_matrix()` 展示函数

输出格式（每 cell × strategy，显示均值 + CI + 显著性标记）：

```
cell                      | bull_call_diagonal        | iron_condor
NORMAL|HIGH|BEARISH       | $1,041 [-$234,$2,316]     | $2,043 [$891,$3,195] ✓
LOW_VOL|LOW|BULLISH       | $1,867 [$1,102,$2,632] ✓  | $657 [$389,$925] ✓
```

`✓` = significant（ci_lo > 0），空 = 不显著或 LOW_N。

---

## 常量

```python
DEFAULT_N_BOOT   = 2000   # bootstrap 次数，精度与速度的平衡
MIN_N_BOOTSTRAP  = 10     # 少于此数不做 bootstrap
DEFAULT_CI_LEVEL = 0.95   # 95% 置信区间
```

---

## 依赖

- SPEC-057 已 DONE（`run_matrix_audit()` 和 `matrix_audit.csv` 存在）
- 不依赖 engine.py 或 selector.py，纯统计工具

---

## 不在范围内

- 不做稀疏 cell（n < 10）的 bootstrap（bootstrap 本身需要足够样本才有效）
- 不修改任何路由规则（结论输出到 CSV，由 PM 决定后续 SPEC）
- 不做多策略联合显著性检验（Bonferroni 修正等，scope 太大）

---

## 验收标准

- AC1. `bootstrap_ci([100]*20)` 返回 mean=100，significant=True，ci_lo > 0
- AC2. `bootstrap_ci([-50]*20)` 返回 significant=False，ci_hi < 0
- AC3. `bootstrap_ci([100,-100]*10)` 返回 significant=False（均值≈0，CI 跨零）
- AC4. `run_matrix_bootstrap()` 对 n ≥ 10 的 cell 均有 ci_lo / ci_hi 字段
- AC5. `run_matrix_bootstrap()` 对 n < 10 的 cell，ci_lo = NaN，significant = False
- AC6. 输出 `backtest/output/matrix_audit_bootstrap.csv` 存在

---

## Review
- 结论：PASS
- `run_bootstrap_ci.py`：block_size=max(5,n//4)，seed=42，n<10 返回 NaN，significant=(ci_lo>0)，AC1–AC3 ✓
- `run_matrix_bootstrap.py`：透传 strategy_keys，trade-level P&L 重建正确，ci 字段对 n<10 为 NaN，AC4–AC6 ✓
- 120/120 通过

---

Status: DONE
