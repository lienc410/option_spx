"""Q042 — Drawdown threshold comparison at fixed structure / sizing.

Compare dd5 / dd8 / dd10 / dd12 / dd15 / dd20 with all other params held constant:
  - Structure: ATM/+5% spread DTE 90
  - Filter: no-overlap (no new entry while position held)
  - Sizing: 10% account / entry
  - Execution: T+1 open

For each threshold, output:
  - n triggers (filtered)
  - Win rate
  - Per-winner avg / median (% of debit)
  - Per-trade avg account contribution
  - Worst single trade account %
  - Max consecutive losses
  - 19y total account return
  - Annualized account return
  - Max drawdown
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


def evaluate_spread_dte90(df: pd.DataFrame, entries: pd.DatetimeIndex) -> pd.DataFrame:
    """ATM/+5% spread DTE 90, T+1 open execution."""
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
            "entry": entry_day,
            "S_entry": S_entry,
            "S_expiry": S_expiry,
            "vix": vix,
            "fwd_ret_pct": (S_expiry / S_entry - 1) * 100,
            "net_debit": net_debit,
            "pnl_pct_bp": spread_payoff / net_debit * 100,  # PnL as % of debit
        })
    return pd.DataFrame(rows).sort_values("entry").reset_index(drop=True)


def metrics(trades: pd.DataFrame, sizing_pct: float, years: float) -> dict:
    if trades.empty:
        return {"n": 0}
    pnl = trades["pnl_pct_bp"].values
    is_loss = (pnl < 0).astype(int)
    max_consec = 0
    cur = 0
    for x in is_loss:
        if x:
            cur += 1
            max_consec = max(max_consec, cur)
        else:
            cur = 0

    winners = pnl[pnl > 0]
    losers = pnl[pnl <= 0]

    # Account contribution per trade as % account
    account_pct_per_trade = (pnl / 100) * sizing_pct * 100  # in %

    cum = np.cumsum(account_pct_per_trade)
    max_dd = float(np.min(cum - np.maximum.accumulate(cum)))

    return {
        "n": int(len(trades)),
        "trades_per_year": float(len(trades) / years),
        "win_rate": float((pnl > 0).mean()),
        "median_winner_pct_debit": float(np.median(winners)) if len(winners) > 0 else 0.0,
        "avg_winner_pct_debit": float(np.mean(winners)) if len(winners) > 0 else 0.0,
        "best_winner_pct_debit": float(np.max(winners)) if len(winners) > 0 else 0.0,
        "worst_loser_pct_debit": float(np.min(losers)) if len(losers) > 0 else 0.0,
        "max_consec_losses": max_consec,
        # at sizing_pct sizing
        "median_winner_account_pct": float(np.median(winners)) * sizing_pct / 100 * 100 if len(winners) > 0 else 0.0,
        "avg_winner_account_pct": float(np.mean(winners)) * sizing_pct / 100 * 100 if len(winners) > 0 else 0.0,
        "worst_loser_account_pct": float(np.min(losers)) * sizing_pct / 100 * 100 if len(losers) > 0 else 0.0,
        "total_account_pct_19y": float(cum[-1]),
        "annualized_account_pct": float(cum[-1] / years),
        "max_dd_account_pct": max_dd,
    }


def main() -> None:
    spx, vix = load()
    df = pd.DataFrame(index=spx.index)
    df["close"] = spx["Close"]
    df["open"] = spx["Open"]
    df["high60"] = df["close"].rolling(60).max()
    df["dd60"] = df["close"] / df["high60"] - 1
    df["vix"] = vix.reindex(df.index).ffill()

    years = (df.index.max() - df.index.min()).days / 365

    print("=" * 110)
    print(f"Q042 dd-threshold comparison @ ATM/+5% spread DTE 90, no-overlap, 10% sizing/entry")
    print(f"Span: {df.index.min().date()} → {df.index.max().date()} ({years:.1f} years)")
    print("=" * 110)

    SIZING = 0.10  # 10% per entry

    rows = []
    for thr in [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]:
        entries_raw = first_triggers(df["dd60"] <= -thr)
        entries_filt = apply_no_overlap(entries_raw, 90)
        trades = evaluate_spread_dte90(df, entries_filt)
        m = metrics(trades, SIZING, years)
        m["dd_thr"] = thr
        m["raw_triggers"] = len(entries_raw)
        rows.append(m)

    out = pd.DataFrame(rows)

    # Per-trade view
    print("\n--- Per-trade ROE (sizing = 10% account / entry) ---")
    print(f"{'dd_thr':>6} | {'n_raw':>6} | {'n_filt':>6} | {'/yr':>4} | {'Win%':>5} | "
          f"{'Med winner':>10} | {'Avg winner':>10} | {'Best':>5} | {'Max consec L':>12}")
    print(f"{' (%)':>6} | {'':>6} | {'':>6} | {'':>4} | {'':>5} | "
          f"{'(% acct)':>10} | {'(% acct)':>10} | {'(%dbt)':>5} | {'':>12}")
    print("-" * 90)
    for _, r in out.iterrows():
        print(f"{r['dd_thr']*100:>5.0f}% | {int(r['raw_triggers']):>6d} | {int(r['n']):>6d} | "
              f"{r['trades_per_year']:>4.2f} | {r['win_rate']*100:>4.0f}% | "
              f"{r['median_winner_account_pct']:>+9.1f}% | {r['avg_winner_account_pct']:>+9.1f}% | "
              f"{r['best_winner_pct_debit']:>+4.0f}% | {int(r['max_consec_losses']):>12d}")

    # Account-level view
    print("\n--- Account-level totals ---")
    print(f"{'dd_thr':>6} | {'n_filt':>6} | {'19y total':>10} | {'Annualized':>10} | "
          f"{'Max DD':>8} | {'Worst single':>12}")
    print(f"{' (%)':>6} | {'':>6} | {'(% acct)':>10} | {'(% / yr)':>10} | "
          f"{'(% acct)':>8} | {'(% acct)':>12}")
    print("-" * 75)
    for _, r in out.iterrows():
        print(f"{r['dd_thr']*100:>5.0f}% | {int(r['n']):>6d} | "
              f"{r['total_account_pct_19y']:>+9.1f}% | {r['annualized_account_pct']:>+9.2f}% | "
              f"{r['max_dd_account_pct']:>+7.1f}% | {r['worst_loser_account_pct']:>+11.1f}%")

    out_path = Path(__file__).resolve().parent / "dd_threshold_comparison.csv"
    out.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
