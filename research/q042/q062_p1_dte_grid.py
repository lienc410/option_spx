"""Q062 — P1: DTE Grid, per-sleeve independent.

Sleeve A: dd4 lenient first-cross (n=25 from q042_backtest_trades.csv)
Sleeve B: dd15 + MA10 reclaim lenient first-cross (n=5 from q042_backtest_trades.csv)

Fixed structure: ATM/+5% call spread.
Scan DTE ∈ {30, 45, 60, 90, 120}.

Pricing: BS + linear skew haircut (inherits Tier 2/3 framework exactly).
No-overlap rule: max 1 active position per sleeve; if new signal_date < prev exit_date,
skip.

Output: research/q042/q062_p1_dte_grid.csv
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
TRADES_CSV = REPO / "data" / "q042_backtest_trades.csv"
OUT_CSV = Path(__file__).resolve().parent / "q062_p1_dte_grid.csv"

OTM_PCT = 0.05  # fixed short strike at ATM × 1.05
DTE_LIST = [30, 45, 60, 90, 120]
R = 0.04


# ─── Data loading ────────────────────────────────────────────────────────────

def load_market() -> tuple[pd.DataFrame, pd.Series]:
    spx = pickle.loads(SPX_PKL.read_bytes())
    vix = pickle.loads(VIX_PKL.read_bytes())
    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    vix.index = pd.to_datetime(vix.index).tz_localize(None)
    spx_df = spx.loc["2007-01-01":"2026-05-10"].copy()
    vix_s = vix.loc["2007-01-01":"2026-05-10"]["Close"].copy()
    return spx_df, vix_s


def load_signal_dates() -> dict[str, list[pd.Timestamp]]:
    """Read signal_date per sleeve from backtest trades CSV."""
    df = pd.read_csv(TRADES_CSV, parse_dates=["signal_date"])
    result = {}
    for sleeve in ["A", "B"]:
        sub = df[df["sleeve_id"] == sleeve].copy()
        sub = sub.sort_values("signal_date")
        result[sleeve] = list(sub["signal_date"])
    return result


# ─── Pricing (Tier 2/3 framework) ────────────────────────────────────────────

def term_multiplier(dte: int) -> float:
    if dte <= 45:
        return 1.10
    if dte <= 120:
        return 1.00
    return 0.95


def skew_multiplier(moneyness: float) -> float:
    """Linear interpolation from skew_table:
    {1.00: 1.00, 1.03: 0.96, 1.05: 0.93, 1.07: 0.90, 1.10: 0.85}
    Extrapolate linearly beyond 1.10.
    """
    table = {1.00: 1.00, 1.03: 0.96, 1.05: 0.93, 1.07: 0.90, 1.10: 0.85}
    keys = sorted(table.keys())
    if moneyness <= keys[0]:
        return table[keys[0]]
    if moneyness >= keys[-1]:
        # extrapolate slope from last two points
        slope = (table[keys[-1]] - table[keys[-2]]) / (keys[-1] - keys[-2])
        return table[keys[-1]] + slope * (moneyness - keys[-1])
    # interpolate
    for i in range(len(keys) - 1):
        if keys[i] <= moneyness <= keys[i + 1]:
            frac = (moneyness - keys[i]) / (keys[i + 1] - keys[i])
            return table[keys[i]] + frac * (table[keys[i + 1]] - table[keys[i]])
    return 1.0


def sigma_for(K: float, S: float, vix: float, dte: int) -> float:
    sigma_base = max(vix / 100.0, 0.10)
    sigma_atm = sigma_base * term_multiplier(dte)
    return sigma_atm * skew_multiplier(K / S)


def bs_call(S: float, K: float, T: float, sigma: float, r: float = R) -> float:
    if T <= 0:
        return max(0.0, S - K)
    if sigma <= 0:
        return max(0.0, S - K * np.exp(-r * T))
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return float(S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2))


def price_spread(S: float, vix: float, dte: int, otm_pct: float = OTM_PCT) -> tuple[float, float, float]:
    """Returns (debit_per_share, K_long, K_short)."""
    K_long = S
    K_short = S * (1 + otm_pct)
    T = dte / 365.0
    p_long = bs_call(S, K_long, T, sigma_for(K_long, S, vix, dte))
    p_short = bs_call(S, K_short, T, sigma_for(K_short, S, vix, dte))
    debit = p_long - p_short
    return max(debit, 0.01), K_long, K_short


# ─── Exit price lookup ────────────────────────────────────────────────────────

def exit_close(spx_df: pd.DataFrame, signal_date: pd.Timestamp, dte: int) -> tuple[float | None, str]:
    """Return (S_T, status). status = 'CLOSED' or 'OPEN'."""
    target = signal_date + pd.Timedelta(days=dte)
    future = spx_df.loc[signal_date:].loc[target:]
    if future.empty:
        # Beyond data range
        return None, "OPEN"
    S_T = float(future["Close"].iloc[0])
    return S_T, "CLOSED"


# ─── No-overlap filter ────────────────────────────────────────────────────────

def apply_no_overlap(signal_dates: list[pd.Timestamp], dte: int) -> list[pd.Timestamp]:
    """Keep only signal_dates that don't overlap with previous position's hold window."""
    result = []
    last_exit = pd.Timestamp("1900-01-01")
    for sd in signal_dates:
        if sd >= last_exit:
            result.append(sd)
            last_exit = sd + pd.Timedelta(days=dte)
    return result


# ─── Worst 12-month drawdown ─────────────────────────────────────────────────

def worst_12m_drawdown(trades: pd.DataFrame, sizing: float = 0.10) -> float:
    """Over all rolling 12-month windows (by signal_date), find worst cumulative account %.

    Each trade's account impact = pnl_pct * sizing (e.g., 10% of account per trade).
    pnl_pct is already in % terms (e.g., -100 = full debit loss).
    Returns cumulative account % (e.g., -10.0 means -10% of account in worst 12m window).
    """
    closed = trades[trades["status"] == "CLOSED"].copy()
    if closed.empty:
        return 0.0
    closed = closed.sort_values("signal_date")
    dates = list(closed["signal_date"])
    # pnl_pct is in % (e.g., 78.15 or -100); account impact = pnl_pct * sizing
    pnls_acct = [p * sizing for p in closed["pnl_pct"]]
    worst = 0.0
    for i in range(len(dates)):
        window_end = dates[i] + pd.DateOffset(months=12)
        window_pnl = sum(p for j, p in enumerate(pnls_acct) if i <= j and dates[j] <= window_end)
        worst = min(worst, window_pnl)
    return round(worst, 2)


# ─── Metrics calculation ──────────────────────────────────────────────────────

def compute_metrics(
    signal_dates_raw: list[pd.Timestamp],
    spx_df: pd.DataFrame,
    vix_s: pd.Series,
    dte: int,
    sleeve_name: str,
) -> dict:
    # Apply no-overlap filter
    filtered = apply_no_overlap(signal_dates_raw, dte)

    trades = []
    for sd in filtered:
        # Get SPX close at signal_date (entry price)
        if sd not in spx_df.index:
            # find nearest
            idx = spx_df.index.searchsorted(sd)
            if idx >= len(spx_df):
                continue
            sd_actual = spx_df.index[idx]
        else:
            sd_actual = sd

        S = float(spx_df.loc[sd_actual, "Close"])
        # VIX at signal date
        if sd_actual in vix_s.index:
            vix_val = float(vix_s.loc[sd_actual])
        else:
            idx = vix_s.index.searchsorted(sd_actual)
            if idx >= len(vix_s):
                continue
            vix_val = float(vix_s.iloc[idx])

        if np.isnan(vix_val) or vix_val <= 0:
            continue

        debit_per_share, K_long, K_short = price_spread(S, vix_val, dte)

        S_T, status = exit_close(spx_df, sd_actual, dte)

        if status == "OPEN":
            # MTM: use latest available price
            latest_S = float(spx_df["Close"].iloc[-1])
            long_payoff = max(0.0, latest_S - K_long)
            short_payoff = max(0.0, latest_S - K_short)
            payoff = long_payoff - short_payoff
            pnl = payoff - debit_per_share
            pnl_pct = pnl / debit_per_share
        else:
            long_payoff = max(0.0, S_T - K_long)
            short_payoff = max(0.0, S_T - K_short)
            payoff = long_payoff - short_payoff
            pnl = payoff - debit_per_share
            pnl_pct = pnl / debit_per_share
            short_strike_hit = (S_T >= K_short)

        trades.append({
            "sleeve": sleeve_name,
            "signal_date": sd_actual,
            "dte": dte,
            "S": S,
            "vix": vix_val,
            "K_long": K_long,
            "K_short": K_short,
            "debit_per_share": debit_per_share,
            "debit_total": debit_per_share * 100,
            "S_T": S_T,
            "payoff": payoff,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "status": status,
            "short_strike_hit": short_strike_hit if status == "CLOSED" else None,
        })

    df = pd.DataFrame(trades)
    if df.empty:
        return {
            "sleeve": sleeve_name,
            "dte": dte,
            "n_raw": len(signal_dates_raw),
            "n_filtered": 0,
            "win_rate": None,
            "median_pnl_pct": None,
            "dollar_per_bp_day": None,
            "max_consec_losses": None,
            "worst_12m_drawdown_pct": None,
            "short_strike_hit_rate_pct": None,
            "annualized_account_pct": None,
            "vix_median_at_signal": None,
        }

    closed = df[df["status"] == "CLOSED"].copy()
    n_closed = len(closed)

    win_rate = float((closed["pnl_pct"] > 0).mean()) * 100 if n_closed > 0 else None
    median_pnl_pct = float(closed["pnl_pct"].median()) * 100 if n_closed > 0 else None

    # $/BP-day = median_pnl_pct (as %) / DTE  [in % terms]
    dollar_per_bp_day = (median_pnl_pct / dte) if median_pnl_pct is not None else None

    # Max consecutive losses (CLOSED only)
    max_consec = 0
    cur_consec = 0
    for _, row in closed.iterrows():
        if row["pnl_pct"] < 0:
            cur_consec += 1
            max_consec = max(max_consec, cur_consec)
        else:
            cur_consec = 0

    worst_12m = worst_12m_drawdown(df)

    # Short strike hit rate
    ssh = closed["short_strike_hit"].dropna()
    short_strike_hit_rate = float(ssh.mean()) * 100 if len(ssh) > 0 else None

    # Annualized account% (10% sizing, no-overlap)
    # trades/year × median_pnl_pct × 10%
    if n_closed > 0 and median_pnl_pct is not None:
        date_range_years = (closed["signal_date"].max() - closed["signal_date"].min()).days / 365.25
        if date_range_years > 0:
            trades_per_year = n_closed / date_range_years
        else:
            trades_per_year = n_closed
        annualized_account_pct = trades_per_year * (median_pnl_pct / 100) * 0.10 * 100
    else:
        annualized_account_pct = None

    vix_median = float(df["vix"].median())

    return {
        "sleeve": sleeve_name,
        "dte": dte,
        "n_raw": len(signal_dates_raw),
        "n_filtered": n_closed,
        "win_rate": round(win_rate, 1) if win_rate is not None else None,
        "median_pnl_pct": round(median_pnl_pct, 2) if median_pnl_pct is not None else None,
        "dollar_per_bp_day": round(dollar_per_bp_day, 4) if dollar_per_bp_day is not None else None,
        "max_consec_losses": max_consec,
        "worst_12m_drawdown_pct": worst_12m,
        "short_strike_hit_rate_pct": round(short_strike_hit_rate, 1) if short_strike_hit_rate is not None else None,
        "annualized_account_pct": round(annualized_account_pct, 2) if annualized_account_pct is not None else None,
        "vix_median_at_signal": round(vix_median, 1),
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    spx_df, vix_s = load_market()
    signal_dates = load_signal_dates()

    print(f"Sleeve A signal_dates: n={len(signal_dates['A'])}")
    print(f"  {[str(d.date()) for d in signal_dates['A']]}")
    print(f"Sleeve B signal_dates: n={len(signal_dates['B'])}")
    print(f"  {[str(d.date()) for d in signal_dates['B']]}")
    print()

    rows = []
    for sleeve, dates in signal_dates.items():
        for dte in DTE_LIST:
            metrics = compute_metrics(dates, spx_df, vix_s, dte, sleeve)
            rows.append(metrics)
            print(f"Sleeve {sleeve} DTE={dte}: n_filtered={metrics['n_filtered']}, "
                  f"win_rate={metrics['win_rate']}%, "
                  f"median_pnl={metrics['median_pnl_pct']}%, "
                  f"$/BP/day={metrics['dollar_per_bp_day']}, "
                  f"short_hit={metrics['short_strike_hit_rate_pct']}%")

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)
    print(f"\nWrote {OUT_CSV}")

    print("\n=== P1 Summary ===")
    for sleeve in ["A", "B"]:
        sub = out[out["sleeve"] == sleeve].copy()
        print(f"\nSleeve {sleeve}:")
        print(sub[[
            "dte", "n_filtered", "win_rate", "median_pnl_pct",
            "dollar_per_bp_day", "max_consec_losses",
            "worst_12m_drawdown_pct", "short_strike_hit_rate_pct",
            "annualized_account_pct"
        ]].to_string(index=False))


if __name__ == "__main__":
    main()
