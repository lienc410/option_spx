"""Q042 — dd5 naive worst-trades inspection.

For dd5 naive + no-overlap + ATM/+5% spread DTE 90 + T+1 open + 10% sizing:
  - List all 43 trades sorted by PnL (worst first)
  - Show entry date, S_entry, VIX, S_expiry, fwd return %, PnL/$debit, account % contribution
  - Plot cumulative account curve (text-based)
  - Identify which periods drove the -31% max DD
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

REPO = Path(__file__).resolve().parents[2]
SPX_PKL = REPO / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
VIX_PKL = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"


def load() -> tuple[pd.DataFrame, pd.Series]:
    spx = pickle.loads(SPX_PKL.read_bytes())
    vix = pickle.loads(VIX_PKL.read_bytes())
    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    vix.index = pd.to_datetime(vix.index).tz_localize(None)
    return spx.loc["2007-01-01":"2026-05-08"].copy(), vix.loc["2007-01-01":"2026-05-08"]["Close"].copy()


def first_triggers(condition: pd.Series) -> pd.DatetimeIndex:
    fired = condition & ~condition.shift(1).fillna(False)
    return condition.index[fired]


def apply_no_overlap(entries: pd.DatetimeIndex, dte: int) -> pd.DatetimeIndex:
    if len(entries) == 0:
        return entries
    kept = [entries[0]]
    last_close = entries[0] + pd.Timedelta(days=dte)
    for e in entries[1:]:
        if e >= last_close:
            kept.append(e)
            last_close = e + pd.Timedelta(days=dte)
    return pd.DatetimeIndex(kept)


def term_multiplier(dte: int) -> float:
    if dte <= 45:
        return 1.10
    if dte <= 120:
        return 1.00
    return 0.95


def skew_multiplier(moneyness: float) -> float:
    if moneyness >= 1.0:
        delta = min(moneyness - 1.0, 0.10)
        return 1.0 - 1.5 * delta
    delta = min(1.0 - moneyness, 0.10)
    return 1.0 + 1.5 * delta


def bs_call(S: float, K: float, T: float, sigma: float, r: float = 0.04) -> float:
    if T <= 0:
        return max(0.0, S - K)
    if sigma <= 0:
        return max(0.0, S - K * np.exp(-r * T))
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def price_with_skew(S: float, K: float, T: float, vix: float, dte: int) -> float:
    sigma_atm = max(vix / 100.0, 0.10) * term_multiplier(dte)
    sigma_k = sigma_atm * skew_multiplier(K / S)
    return bs_call(S, K, T, sigma_k)


def evaluate(df: pd.DataFrame, entries: pd.DatetimeIndex) -> pd.DataFrame:
    DTE = 90
    OTM = 0.05
    rows = []
    for sig in entries:
        if sig not in df.index:
            continue
        future = df.loc[sig:].iloc[1:2]
        if future.empty:
            continue
        entry_day = future.index[0]
        S_entry = float(future["open"].iloc[0])
        S_signal = float(df.loc[sig, "close"])
        K_long = S_signal
        K_short = S_signal * (1 + OTM)
        vix = float(df.loc[entry_day, "vix"])
        if np.isnan(vix):
            continue
        T = DTE / 365
        p_long = price_with_skew(S_entry, K_long, T, vix, DTE)
        p_short = price_with_skew(S_entry, K_short, T, vix, DTE)
        net_debit = p_long - p_short
        if net_debit <= 0:
            continue
        target = entry_day + pd.Timedelta(days=DTE)
        future = df.loc[entry_day:].loc[target:]
        if future.empty:
            continue
        S_expiry = float(future["close"].iloc[0])
        long_payoff = max(0.0, S_expiry - K_long)
        short_payoff = max(0.0, S_expiry - K_short)
        spread_payoff = (long_payoff - short_payoff) - net_debit
        rows.append({
            "signal_date": sig,
            "entry_date": entry_day,
            "exit_date": future.index[0],
            "S_entry": S_entry,
            "S_expiry": S_expiry,
            "vix_at_entry": vix,
            "dd60_at_signal": float(df.loc[sig, "dd60"]) * 100,
            "fwd_ret_pct": (S_expiry / S_entry - 1) * 100,
            "K_long": K_long,
            "K_short": K_short,
            "net_debit": net_debit,
            "pnl_pct_debit": spread_payoff / net_debit * 100,
            "account_pct_at_10pct_sizing": (spread_payoff / net_debit) * 10,
        })
    return pd.DataFrame(rows).sort_values("entry_date").reset_index(drop=True)


def main() -> None:
    spx, vix = load()
    df = pd.DataFrame(index=spx.index)
    df["close"] = spx["Close"]
    df["open"] = spx["Open"]
    df["high60"] = df["close"].rolling(60).max()
    df["dd60"] = df["close"] / df["high60"] - 1
    df["vix"] = vix.reindex(df.index).ffill()

    entries_raw = first_triggers(df["dd60"] <= -0.05)
    entries = apply_no_overlap(entries_raw, 90)
    trades = evaluate(df, entries)

    # Add cumulative account
    trades["cum_account_pct"] = trades["account_pct_at_10pct_sizing"].cumsum()
    trades["running_max"] = trades["cum_account_pct"].cummax()
    trades["drawdown_pct"] = trades["cum_account_pct"] - trades["running_max"]

    print("=" * 130)
    print(f"dd5 naive + no-overlap + ATM/+5% spread DTE 90 + T+1 open + 10% sizing — all {len(trades)} trades over 19.4 years")
    print("=" * 130)

    # ── Top-10 worst trades by PnL ──
    print("\n=== TOP-10 worst single trades (sorted by PnL/$debit) ===")
    worst = trades.sort_values("pnl_pct_debit").head(10)
    print(f"{'#':>3} | {'entry':>10} | {'exit':>10} | {'dd60_sig':>8} | {'VIX':>5} | "
          f"{'S_entry':>7} | {'S_expiry':>8} | {'fwd_ret':>7} | {'PnL/dbt':>8} | {'acct%':>6}")
    print("-" * 110)
    for i, (_, r) in enumerate(worst.iterrows(), 1):
        print(f"{i:>3} | {r['entry_date'].date()!s:>10} | {r['exit_date'].date()!s:>10} | "
              f"{r['dd60_at_signal']:>+7.1f}% | {r['vix_at_entry']:>5.1f} | "
              f"{r['S_entry']:>7.0f} | {r['S_expiry']:>8.0f} | "
              f"{r['fwd_ret_pct']:>+6.1f}% | {r['pnl_pct_debit']:>+7.0f}% | {r['account_pct_at_10pct_sizing']:>+5.1f}%")

    # ── Top-10 best trades for context ──
    print("\n=== TOP-10 best single trades (sorted by PnL/$debit) ===")
    best = trades.sort_values("pnl_pct_debit", ascending=False).head(10)
    print(f"{'#':>3} | {'entry':>10} | {'exit':>10} | {'dd60_sig':>8} | {'VIX':>5} | "
          f"{'S_entry':>7} | {'S_expiry':>8} | {'fwd_ret':>7} | {'PnL/dbt':>8} | {'acct%':>6}")
    print("-" * 110)
    for i, (_, r) in enumerate(best.iterrows(), 1):
        print(f"{i:>3} | {r['entry_date'].date()!s:>10} | {r['exit_date'].date()!s:>10} | "
              f"{r['dd60_at_signal']:>+7.1f}% | {r['vix_at_entry']:>5.1f} | "
              f"{r['S_entry']:>7.0f} | {r['S_expiry']:>8.0f} | "
              f"{r['fwd_ret_pct']:>+6.1f}% | {r['pnl_pct_debit']:>+7.0f}% | {r['account_pct_at_10pct_sizing']:>+5.1f}%")

    # ── Drawdown periods ──
    print("\n=== Drawdown timeline (showing 10 worst running-DD points) ===")
    dd_worst = trades.sort_values("drawdown_pct").head(10)
    print(f"{'after trade':>12} | {'entry':>10} | {'cum_acct':>9} | {'running_max':>11} | {'drawdown':>9}")
    print("-" * 70)
    for _, r in dd_worst.iterrows():
        idx = trades.index[trades["entry_date"] == r["entry_date"]][0]
        print(f"#{idx+1:>11d} | {r['entry_date'].date()!s:>10} | {r['cum_account_pct']:>+8.1f}% | "
              f"{r['running_max']:>+10.1f}% | {r['drawdown_pct']:>+8.1f}%")

    # ── Loser concentration by year ──
    trades["year"] = trades["entry_date"].dt.year
    print("\n=== Per-year breakdown ===")
    by_year = trades.groupby("year").agg(
        n_trades=("pnl_pct_debit", "size"),
        n_losses=("pnl_pct_debit", lambda s: (s < 0).sum()),
        net_pnl_debit_pct=("pnl_pct_debit", "sum"),
        net_account_pct=("account_pct_at_10pct_sizing", "sum"),
        worst_trade_pct=("pnl_pct_debit", "min"),
    )
    print(by_year.to_string(float_format=lambda x: f"{x:+.1f}"))

    # ── Save full trade list ──
    out = Path(__file__).resolve().parent / "dd5_naive_all_trades.csv"
    trades.to_csv(out, index=False)
    print(f"\nwrote {out}")

    # ── Cumulative curve text plot ──
    print("\n=== Account curve (cumulative %, after each trade) ===")
    print(f"{'#':>3} | {'entry':>10} | {'pnl':>7} | {'cum':>8} | curve")
    print("-" * 100)
    for i, (_, r) in enumerate(trades.iterrows(), 1):
        bar_len = int(abs(r["cum_account_pct"]) / 5)
        bar = ("+" * bar_len) if r["cum_account_pct"] >= 0 else ("-" * bar_len)
        marker = " ★ DD" if r["drawdown_pct"] < -20 else ""
        print(f"{i:>3} | {r['entry_date'].date()!s:>10} | {r['pnl_pct_debit']:>+6.0f}% | "
              f"{r['cum_account_pct']:>+7.1f}% | {bar}{marker}")


if __name__ == "__main__":
    main()
