"""Q042 — MA filter comparison grid.

For each dd threshold (5/8/10/12/15/20) × each MA filter, compute:
  - n_filt (after no-overlap rule)
  - Win rate
  - 19y total account at 10% sizing
  - Max DD
  - Median winner % account

MA filters tested:
  - none (naive — first day SPX prints below dd threshold)
  - ma10_reclaim (first day within 30 trading days where close > MA10)
  - ma20_reclaim (close > MA20)
  - ma50_reclaim (close > MA50)
  - ma10_cross_ma50 (first day MA10 crosses above MA50 — "golden cross")

Structure: ATM/+5% spread DTE 90, T+1 open execution, 10% sizing, no-overlap rule.
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


def find_entries_with_filter(df: pd.DataFrame, dd_thr: float, filter_kind: str, window_days: int = 30) -> pd.DatetimeIndex:
    """For each first-trigger of dd60 ≤ -dd_thr, apply MA filter to delay entry.

    filter_kind:
      'none'             - first dd trigger date itself
      'ma10_reclaim'     - first day in next window_days where close > MA10
      'ma20_reclaim'     - first day where close > MA20
      'ma50_reclaim'     - first day where close > MA50
      'ma10_cross_ma50'  - first day where MA10 > MA50 (and was ≤ on previous day)
    """
    triggers = first_triggers(df["dd60"] <= -dd_thr)
    if filter_kind == "none":
        return triggers

    entries = []
    for td in triggers:
        window = df.loc[td:].iloc[:window_days]
        if window.empty:
            continue

        if filter_kind == "ma10_reclaim":
            ok = window[window["close"] > window["ma10"]]
        elif filter_kind == "ma20_reclaim":
            ok = window[window["close"] > window["ma20"]]
        elif filter_kind == "ma50_reclaim":
            ok = window[window["close"] > window["ma50"]]
        elif filter_kind == "ma10_cross_ma50":
            # MA10 > MA50 today, and was ≤ MA50 yesterday (true cross from below)
            cross = (window["ma10"] > window["ma50"]) & (window["ma10"].shift(1) <= window["ma50"].shift(1))
            ok = window[cross.fillna(False)]
        else:
            raise ValueError(filter_kind)

        if not ok.empty:
            entries.append(ok.index[0])

    return pd.DatetimeIndex(entries).unique()


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


def evaluate_spread(df: pd.DataFrame, entries: pd.DatetimeIndex, dte: int = 90, otm: float = 0.05) -> pd.DataFrame:
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
        K_short = S_signal * (1 + otm)
        vix = float(df.loc[entry_day, "vix"])
        if np.isnan(vix):
            continue
        T = dte / 365
        p_long = price_with_skew(S_entry, K_long, T, vix, dte)
        p_short = price_with_skew(S_entry, K_short, T, vix, dte)
        net_debit = p_long - p_short
        if net_debit <= 0:
            continue
        target = entry_day + pd.Timedelta(days=dte)
        future = df.loc[entry_day:].loc[target:]
        if future.empty:
            continue
        S_expiry = float(future["close"].iloc[0])
        long_payoff = max(0.0, S_expiry - K_long)
        short_payoff = max(0.0, S_expiry - K_short)
        spread_payoff = (long_payoff - short_payoff) - net_debit
        rows.append({
            "entry": entry_day,
            "pnl_pct_bp": spread_payoff / net_debit * 100,
        })
    return pd.DataFrame(rows).sort_values("entry").reset_index(drop=True)


def metrics(trades: pd.DataFrame, sizing_pct: float, years: float) -> dict:
    if trades.empty:
        return {"n": 0, "win_rate": 0, "median_winner_account_pct": 0,
                "max_consec_losses": 0, "total_19y_pct": 0, "annualized_pct": 0, "max_dd_pct": 0}
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
    account_pct_per_trade = (pnl / 100) * sizing_pct * 100
    cum = np.cumsum(account_pct_per_trade)
    max_dd = float(np.min(cum - np.maximum.accumulate(cum)))

    return {
        "n": len(trades),
        "win_rate": float((pnl > 0).mean()),
        "median_winner_account_pct": float(np.median(winners)) * sizing_pct if len(winners) > 0 else 0,
        "max_consec_losses": max_consec,
        "total_19y_pct": float(cum[-1]),
        "annualized_pct": float(cum[-1] / years),
        "max_dd_pct": max_dd,
    }


def main() -> None:
    spx, vix = load()
    df = pd.DataFrame(index=spx.index)
    df["close"] = spx["Close"]
    df["open"] = spx["Open"]
    df["high60"] = df["close"].rolling(60).max()
    df["dd60"] = df["close"] / df["high60"] - 1
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma50"] = df["close"].rolling(50).mean()
    df["vix"] = vix.reindex(df.index).ffill()

    years = (df.index.max() - df.index.min()).days / 365
    SIZING = 0.10
    print(f"Span: {df.index.min().date()} → {df.index.max().date()} ({years:.1f}y), sizing 10%/entry, ATM/+5% spread DTE 90, no-overlap")

    rows = []
    for dd_thr in [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]:
        for filt in ["none", "ma10_reclaim", "ma20_reclaim", "ma50_reclaim", "ma10_cross_ma50"]:
            entries = find_entries_with_filter(df, dd_thr, filt)
            entries_filt = apply_no_overlap(entries, 90)
            trades = evaluate_spread(df, entries_filt)
            m = metrics(trades, SIZING, years)
            m["dd_thr"] = dd_thr
            m["filter"] = filt
            rows.append(m)

    out = pd.DataFrame(rows)
    out_path = Path(__file__).resolve().parent / "ma_filter_grid.csv"
    out.to_csv(out_path, index=False)

    # Print compact view per dd threshold
    print()
    for dd_thr in [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]:
        sub = out[out["dd_thr"] == dd_thr]
        print(f"\n=== dd60 ≥ {dd_thr*100:.0f}% ===")
        print(f"{'filter':<20} | {'n':>4} | {'/yr':>4} | {'Win%':>5} | {'Med winner':>10} | "
              f"{'19y total':>10} | {'Ann':>7} | {'Max DD':>8} | {'MaxConsec':>9}")
        print("-" * 110)
        for _, r in sub.iterrows():
            tpy = r["n"] / years if r["n"] > 0 else 0
            print(f"{r['filter']:<20} | {int(r['n']):>4d} | {tpy:>4.2f} | "
                  f"{r['win_rate']*100:>4.0f}% | {r['median_winner_account_pct']:>+9.2f}% | "
                  f"{r['total_19y_pct']:>+9.1f}% | {r['annualized_pct']:>+6.2f}% | "
                  f"{r['max_dd_pct']:>+7.1f}% | {int(r['max_consec_losses']):>9d}")

    # Headline: best filter per dd threshold (by annualized, with max DD ≤ 25%)
    print("\n" + "=" * 110)
    print("Headline: best filter per dd threshold (highest annualized, max DD ≤ 25%, n ≥ 5)")
    print("=" * 110)
    eligible = out[(out["max_dd_pct"] >= -25) & (out["n"] >= 5)]
    for dd_thr in [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]:
        sub = eligible[eligible["dd_thr"] == dd_thr]
        if sub.empty:
            print(f"  dd{dd_thr*100:.0f}%: none qualifies")
            continue
        winner = sub.sort_values("annualized_pct", ascending=False).iloc[0]
        print(f"  dd{int(dd_thr*100):>2}% + {winner['filter']:<18} | n={int(winner['n']):>3d} | win={winner['win_rate']*100:>3.0f}% | "
              f"19y={winner['total_19y_pct']:>+6.1f}% | ann={winner['annualized_pct']:>+5.2f}% | "
              f"DD={winner['max_dd_pct']:>+6.1f}%")

    # Top-10 globally by annualized (any dd, any filter, max DD ≤ 25%, n ≥ 5)
    print("\n=== Top-10 globally by annualized (max DD ≤ 25%, n ≥ 5) ===")
    print(f"{'dd_thr':>6} | {'filter':<20} | {'n':>4} | {'Win%':>5} | {'19y':>8} | {'Ann':>7} | {'DD':>7}")
    top = eligible.sort_values("annualized_pct", ascending=False).head(10)
    for _, r in top.iterrows():
        print(f"{r['dd_thr']*100:>5.0f}% | {r['filter']:<20} | {int(r['n']):>4d} | {r['win_rate']*100:>4.0f}% | "
              f"{r['total_19y_pct']:>+7.1f}% | {r['annualized_pct']:>+6.2f}% | {r['max_dd_pct']:>+6.1f}%")


if __name__ == "__main__":
    main()
