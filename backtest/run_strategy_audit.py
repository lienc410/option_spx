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

from backtest.engine import run_backtest
from strategy.catalog import STRATEGIES_BY_KEY, strategy_key as catalog_key
from strategy.selector import DEFAULT_PARAMS

MIN_BUCKET_N = 5

BUCKETS: list[tuple[str, str]] = [
    ("ivp_double_low", "ivp252 < 50 AND ivp63 < 50"),
    ("ivp_regime_decay", "ivp252 >= 50 AND ivp63 < 50"),
    ("ivp_local_spike", "ivp63 >= 50 AND ivp252 < 50"),
    ("ivp_both_high", "ivp63 >= 50 AND ivp252 >= 50"),
    ("regime_low_vol", "regime == LOW_VOL"),
    ("regime_normal", "regime == NORMAL"),
    ("regime_high_vol", "regime == HIGH_VOL"),
    ("trend_bullish", "trend == BULLISH"),
    ("trend_neutral", "trend == NEUTRAL"),
    ("trend_bearish", "trend == BEARISH"),
]


def _bucket_mask(df: pd.DataFrame, bucket: str) -> pd.Series:
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


def _bucket_stats(sub: pd.DataFrame, bucket: str, description: str, min_bucket_n: int) -> dict:
    n = len(sub)
    if n == 0:
        return {
            "bucket": bucket,
            "description": description,
            "n": 0,
            "avg_pnl": float("nan"),
            "win_rate": float("nan"),
            "sharpe": float("nan"),
            "max_consec_loss": 0,
            "avg_hold_days": float("nan"),
            "low_n_flag": True,
        }
    avg_pnl = sub["pnl"].mean()
    win_rate = float((sub["pnl"] > 0).mean())
    std = sub["pnl"].std()
    sharpe = round((avg_pnl / std * math.sqrt(252 / 21)), 2) if std and std > 0 else 0.0

    consec = max_consec = 0
    for pnl in sub["pnl"]:
        if pnl <= 0:
            consec += 1
            max_consec = max(max_consec, consec)
        else:
            consec = 0

    avg_hold = sub["hold_days"].mean() if "hold_days" in sub.columns else float("nan")
    return {
        "bucket": bucket,
        "description": description,
        "n": n,
        "avg_pnl": round(avg_pnl, 0),
        "win_rate": round(win_rate, 3),
        "sharpe": sharpe,
        "max_consec_loss": max_consec,
        "avg_hold_days": round(avg_hold, 1) if not math.isnan(avg_hold) else float("nan"),
        "low_n_flag": n < min_bucket_n,
    }


def run_strategy_audit(
    strategy_keys: list[str] | None = None,
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    min_bucket_n: int = MIN_BUCKET_N,
    save_csv: bool = True,
) -> dict[str, pd.DataFrame]:
    keys = strategy_keys or [k for k in STRATEGIES_BY_KEY if k != "reduce_wait"]
    audit_params = replace(DEFAULT_PARAMS, disable_entry_gates=True)
    result = run_backtest(
        start_date=start_date,
        end_date=end_date,
        params=audit_params,
        verbose=False,
    )

    sig_by_date: dict[str, dict] = {row["date"]: row for row in result.signals}

    trade_rows: list[dict] = []
    for trade in result.trades:
        sig = sig_by_date.get(trade.entry_date, {})
        key = catalog_key(trade.strategy.value)
        entry_dt = pd.Timestamp(trade.entry_date)
        exit_dt = pd.Timestamp(trade.exit_date) if trade.exit_date else entry_dt
        trade_rows.append({
            "strategy_key": key,
            "entry_date": entry_dt,
            "exit_date": exit_dt,
            "hold_days": max((exit_dt - entry_dt).days, 0),
            "pnl": trade.exit_pnl,
            "regime": sig.get("regime", ""),
            "trend": sig.get("trend", ""),
            "ivp252": sig.get("ivp252", float("nan")),
            "ivp63": sig.get("ivp63", float("nan")),
            "regime_decay": sig.get("regime_decay", False),
            "local_spike": sig.get("local_spike", False),
        })

    all_trades = pd.DataFrame(trade_rows)
    if all_trades.empty:
        all_trades = pd.DataFrame(columns=[
            "strategy_key", "entry_date", "exit_date", "hold_days", "pnl",
            "regime", "trend", "ivp252", "ivp63", "regime_decay", "local_spike",
        ])

    results: dict[str, pd.DataFrame] = {}
    if save_csv:
        os.makedirs("backtest/output", exist_ok=True)

    for key in keys:
        sub_all = all_trades[all_trades["strategy_key"] == key]
        rows = [
            _bucket_stats(sub_all[_bucket_mask(sub_all, bucket)], bucket, description, min_bucket_n)
            for bucket, description in BUCKETS
        ]
        df = pd.DataFrame(rows)
        results[key] = df
        if save_csv:
            df.to_csv(f"backtest/output/audit_{key}.csv", index=False)

    return results


if __name__ == "__main__":
    audit = run_strategy_audit()
    for key, df in audit.items():
        print(f"\n=== {key} ===")
        print(df.to_string(index=False))
