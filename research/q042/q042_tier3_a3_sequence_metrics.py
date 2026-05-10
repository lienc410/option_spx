"""Q042 Tier 3 — A3 Sequence-loss metrics + re-trigger spacing.

Reviewer requested explicit output of:
  - max consecutive Q042 losses
  - worst rolling 12m sleeve loss
  - worst rolling 24m sleeve loss

Compute these for the finalist configs:
  - dd12 + ma50_reclaim × DTE 30, 60, 90
  - dd15 naive × DTE 30, 60, 90

Apply 1% account / entry sizing.
Use T+1 open execution variant (realistic) for honest production estimate.
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


def build_features(spx: pd.DataFrame, vix: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame(index=spx.index)
    df["close"] = spx["Close"]
    df["open"] = spx["Open"]
    df["high60"] = df["close"].rolling(60).max()
    df["dd60"] = df["close"] / df["high60"] - 1
    df["ma50"] = df["close"].rolling(50).mean()
    df["vix"] = vix.reindex(df.index).ffill()
    return df


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
    """T+1 open entry — the realistic execution baseline."""
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
            "account_pct": (spread_payoff / net_debit) * 1.0,  # 1% account / entry
        })
    return pd.DataFrame(rows).sort_values("entry_date").reset_index(drop=True)


def sequence_metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {}
    pnl = trades["pnl_pct_bp"].values
    is_loss = (pnl < 0).astype(int)

    # Max consecutive losses
    max_consec_losses = 0
    cur = 0
    for x in is_loss:
        if x:
            cur += 1
            max_consec_losses = max(max_consec_losses, cur)
        else:
            cur = 0

    # Max consecutive wins
    is_win = (pnl > 0).astype(int)
    max_consec_wins = 0
    cur = 0
    for x in is_win:
        if x:
            cur += 1
            max_consec_wins = max(max_consec_wins, cur)
        else:
            cur = 0

    # Cumulative account % series, sized at 1% per entry
    cum_account = trades["account_pct"].cumsum()

    # Rolling 12m / 24m worst window (using entry_date)
    trades_with_dt = trades.set_index("entry_date").copy()
    trades_with_dt["account_pct"] = trades["account_pct"].values
    series = trades_with_dt["account_pct"]

    def worst_rolling_window(series: pd.Series, days: int) -> tuple[float, str, str]:
        """Find worst contiguous N-day window sum."""
        worst = 0.0
        worst_start = None
        worst_end = None
        for i, dt in enumerate(series.index):
            window_end = dt + pd.Timedelta(days=days)
            window_sum = series.loc[dt:window_end].sum()
            if window_sum < worst:
                worst = window_sum
                worst_start = dt
                worst_end = series.loc[dt:window_end].index[-1]
        return float(worst), str(worst_start.date()) if worst_start else "n/a", str(worst_end.date()) if worst_end else "n/a"

    worst_12m, w12_start, w12_end = worst_rolling_window(series, 365)
    worst_24m, w24_start, w24_end = worst_rolling_window(series, 730)

    return {
        "n": int(len(trades)),
        "win_rate": float((trades["pnl_pct_bp"] > 0).mean()),
        "median_pnl_pct_bp": float(trades["pnl_pct_bp"].median()),
        "max_consecutive_losses": max_consec_losses,
        "max_consecutive_wins": max_consec_wins,
        "total_account_pct_19y": float(cum_account.iloc[-1]),
        "max_drawdown_account_pct": float((cum_account - cum_account.cummax()).min()),
        "worst_rolling_12m_pct": worst_12m,
        "worst_rolling_12m_window": f"{w12_start} → {w12_end}",
        "worst_rolling_24m_pct": worst_24m,
        "worst_rolling_24m_window": f"{w24_start} → {w24_end}",
        "trades_per_year": float(len(trades) / ((trades["entry_date"].max() - trades["entry_date"].min()).days / 365)),
    }


def main() -> None:
    spx, vix = load()
    df = build_features(spx, vix)

    triggers = {
        "dd12_ma50_reclaim": find_entries(df, 0.12, "ma50_reclaim"),
        "dd15_naive": find_entries(df, 0.15, "none"),
    }

    print("=" * 100)
    print("A3 — Sequence-loss metrics (T+1 open execution, 1% account/entry)")
    print("=" * 100)

    rows = []
    for trig_name, signal_dates in triggers.items():
        for dte in [30, 60, 90, 120]:
            trades = evaluate_t1_open_trades(df, signal_dates, dte, 0.05)
            m = sequence_metrics(trades)
            m.update({"trigger": trig_name, "dte": dte})
            rows.append(m)

    out = pd.DataFrame(rows)
    cols = ["trigger", "dte", "n", "trades_per_year", "win_rate",
            "median_pnl_pct_bp", "max_consecutive_losses", "max_consecutive_wins",
            "total_account_pct_19y", "max_drawdown_account_pct",
            "worst_rolling_12m_pct", "worst_rolling_12m_window",
            "worst_rolling_24m_pct", "worst_rolling_24m_window"]
    print(out[cols].to_string(index=False, float_format=lambda x: f"{x:.2f}" if isinstance(x, float) else str(x)))

    out_path = Path(__file__).resolve().parent / "a3_sequence_metrics.csv"
    out.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}")

    # Cap stress test: at 5% sleeve cap, what's the equivalent risk envelope?
    print("\n=== 5% sleeve cap stress: max_drawdown × 5 (since 1% sizing scales linearly) ===")
    print("If sleeve cap = 5% account = 5 concurrent positions, max sequence loss scales 5×")
    for _, r in out.iterrows():
        print(f"  {r['trigger']:<22s} DTE{int(r['dte']):>3d}: "
              f"5x worst_12m = {r['worst_rolling_12m_pct'] * 5:>+6.2f}% account / "
              f"5x worst_24m = {r['worst_rolling_24m_pct'] * 5:>+6.2f}% account / "
              f"max_consec_losses × 1% = {r['max_consecutive_losses'] * 1.0}%")


if __name__ == "__main__":
    main()
