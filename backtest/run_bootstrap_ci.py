"""
Block Bootstrap confidence interval for mean P&L (SPEC-059 F1).

Non-parametric resampling that preserves return autocorrelation and
vol clustering — no GBM or distributional assumptions.
"""
from __future__ import annotations

import math

import numpy as np

DEFAULT_N_BOOT = 2000
MIN_N_BOOTSTRAP = 10
DEFAULT_CI_LEVEL = 0.95


def bootstrap_ci(
    pnl_series: list[float] | np.ndarray,
    n_boot: int = DEFAULT_N_BOOT,
    ci: float = DEFAULT_CI_LEVEL,
    block_size: int | None = None,
) -> dict:
    """
    Block bootstrap confidence interval for the mean of pnl_series.
    """
    arr = np.asarray(pnl_series, dtype=float)
    n = len(arr)

    if n < MIN_N_BOOTSTRAP:
        return {
            "n": n,
            "mean": float(np.mean(arr)) if n > 0 else float("nan"),
            "ci_lo": float("nan"),
            "ci_hi": float("nan"),
            "ci_level": ci,
            "significant": False,
            "block_size": 0,
            "n_boot": 0,
        }

    bs = block_size if block_size is not None else max(5, n // 4)
    alpha = 1.0 - ci
    rng = np.random.default_rng(seed=42)

    boot_means = np.empty(n_boot)
    max_start = max(1, n - bs + 1)
    for idx in range(n_boot):
        n_blocks = math.ceil(n / bs)
        starts = rng.integers(0, max_start, size=n_blocks)
        sample = np.concatenate([arr[s : s + bs] for s in starts])[:n]
        boot_means[idx] = sample.mean()

    lo = float(np.percentile(boot_means, 100 * alpha / 2))
    hi = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    significant = lo > 0

    return {
        "n": n,
        "mean": round(float(arr.mean()), 2),
        "ci_lo": round(lo, 2),
        "ci_hi": round(hi, 2),
        "ci_level": ci,
        "significant": significant,
        "block_size": bs,
        "n_boot": n_boot,
    }
