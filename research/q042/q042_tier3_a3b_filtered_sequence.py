"""Q042 Tier 3 — A3b: sequence metrics after applying re-trigger spacing rule.

Apply "no overlap" rule: skip any trigger that fires while a previous Q042
position is still open (within DTE days of previous entry). Then re-compute
sequence-loss metrics.

This produces honest production numbers for the candidate winner config.
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
    return (
        spx.loc["2007-01-01":"2026-05-08"].copy(),
        vix.loc["2007-01-01":"2026-05-08"]["Close"].copy(),
    )


def first_triggers(condition: pd.Series) -> pd.DatetimeIndex:
    fired = condition & ~condition.shift(1).fillna(False)
    return condition.index[fired]


def find_entries(df: pd.DataFrame, dd_thr: float, confirmation: str) -> pd.DatetimeIndex:
    triggers = first_triggers(df["dd60"] <= -dd_thr)
    if confirmation == "none":
        return triggers
    entries = []
    for td in triggers:
        window = df.loc[td:].iloc[:30]
        if window.empty:
            continue
        ok = window[window["close"] > window["ma50"]] if confirmation == "ma50_reclaim" else pd.DataFrame()
        if not ok.empty:
            entries.append(ok.index[0])
    return pd.DatetimeIndex(entries).unique()


def apply_no_overlap_filter(entries: pd.DatetimeIndex, dte: int) -> pd.DatetimeIndex:
    """Keep only entries that occur AFTER the previous entry's DTE has passed."""
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


def evaluate_t1_open_trades(df: pd.DataFrame, signal_dates: pd.DatetimeIndex, dte: int, otm_pct: float = 0.05) -> pd.DataFrame:
    rows = []
    for sig in signal_dates:
        if sig not in df.index:
            continue
        future = df.loc[sig:].iloc[1:2]
        if future.empty:
            continue
        entry_day = future.index[0]
        S_entry = float(future["open"].iloc[0])
        S_signal = float(df.loc[sig, "close"])
        K_long = S_signal
        K_short = S_signal * (1 + otm_pct)
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
            "entry_date": entry_day,
            "exit_date": future.index[0],
            "pnl_pct_bp": spread_payoff / net_debit * 100,
            "account_pct": (spread_payoff / net_debit) * 1.0,
        })
    return pd.DataFrame(rows).sort_values("entry_date").reset_index(drop=True)


def sequence_metrics(trades: pd.DataFrame, label: str) -> dict:
    if trades.empty:
        return {}
    pnl = trades["pnl_pct_bp"].values
    is_loss = (pnl < 0).astype(int)
    max_consec_losses = 0
    cur = 0
    for x in is_loss:
        if x:
            cur += 1
            max_consec_losses = max(max_consec_losses, cur)
        else:
            cur = 0
    is_win = (pnl > 0).astype(int)
    max_consec_wins = 0
    cur = 0
    for x in is_win:
        if x:
            cur += 1
            max_consec_wins = max(max_consec_wins, cur)
        else:
            cur = 0

    cum_account = trades["account_pct"].cumsum()
    series = trades.set_index("entry_date")["account_pct"]

    def worst_rolling(series: pd.Series, days: int) -> tuple[float, str, str]:
        worst = 0.0
        worst_start = None
        worst_end = None
        for dt in series.index:
            window_end = dt + pd.Timedelta(days=days)
            sub = series.loc[dt:window_end]
            window_sum = sub.sum()
            if window_sum < worst:
                worst = window_sum
                worst_start = dt
                worst_end = sub.index[-1]
        return float(worst), str(worst_start.date()) if worst_start else "n/a", str(worst_end.date()) if worst_end else "n/a"

    w12, s12, e12 = worst_rolling(series, 365)
    w24, s24, e24 = worst_rolling(series, 730)

    return {
        "label": label,
        "n": int(len(trades)),
        "win_rate": float((trades["pnl_pct_bp"] > 0).mean()),
        "median_pnl_pct_bp": float(trades["pnl_pct_bp"].median()),
        "max_consec_losses": max_consec_losses,
        "max_consec_wins": max_consec_wins,
        "total_account_pct": float(cum_account.iloc[-1]),
        "max_drawdown_account_pct": float((cum_account - cum_account.cummax()).min()),
        "worst_12m_pct": w12,
        "worst_12m_window": f"{s12} → {e12}",
        "worst_24m_pct": w24,
        "trades_per_year": float(len(trades) / max(((trades["entry_date"].max() - trades["entry_date"].min()).days / 365), 0.1)),
    }


def main() -> None:
    spx, vix = load()
    df = pd.DataFrame(index=spx.index)
    df["close"] = spx["Close"]
    df["open"] = spx["Open"]
    df["high60"] = df["close"].rolling(60).max()
    df["dd60"] = df["close"] / df["high60"] - 1
    df["ma50"] = df["close"].rolling(50).mean()
    df["vix"] = vix.reindex(df.index).ffill()

    print("=" * 100)
    print("A3b — Sequence metrics WITH no-overlap re-trigger spacing rule applied")
    print("=" * 100)

    triggers = {
        "dd12_ma50_reclaim": find_entries(df, 0.12, "ma50_reclaim"),
        "dd15_naive": find_entries(df, 0.15, "none"),
    }

    rows = []
    for trig_name, signal_dates in triggers.items():
        for dte in [30, 60, 90, 120]:
            # Without filter
            unfilt = evaluate_t1_open_trades(df, signal_dates, dte, 0.05)
            m_unfilt = sequence_metrics(unfilt, f"{trig_name} DTE{dte} unfiltered")
            m_unfilt["filter"] = "unfiltered"
            m_unfilt["trigger"] = trig_name
            m_unfilt["dte"] = dte
            rows.append(m_unfilt)

            # With no-overlap filter (using DTE as spacing)
            filtered_dates = apply_no_overlap_filter(signal_dates, dte)
            filt = evaluate_t1_open_trades(df, filtered_dates, dte, 0.05)
            m_filt = sequence_metrics(filt, f"{trig_name} DTE{dte} no-overlap")
            m_filt["filter"] = "no_overlap"
            m_filt["trigger"] = trig_name
            m_filt["dte"] = dte
            rows.append(m_filt)

    out = pd.DataFrame(rows)
    cols = ["trigger", "dte", "filter", "n", "trades_per_year", "win_rate",
            "median_pnl_pct_bp", "max_consec_losses", "max_consec_wins",
            "total_account_pct", "max_drawdown_account_pct",
            "worst_12m_pct", "worst_12m_window", "worst_24m_pct"]
    print(out[cols].to_string(index=False, float_format=lambda x: f"{x:.2f}" if isinstance(x, float) else str(x)))

    out_path = Path(__file__).resolve().parent / "a3b_filtered_sequence.csv"
    out.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
