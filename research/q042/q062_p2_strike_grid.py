"""Q062 — P2: Short strike distance grid, per-sleeve independent.

Sleeve A: dd4 (n=25/26 from q042_backtest_trades.csv)
Sleeve B: dd15 + MA10 reclaim (n=5)

Fixed DTE = 90 (current SPEC-094 parameter).
Scan short strike multiplier ∈ {1.03, 1.05, 1.07, 1.10}.

Pricing: BS + linear skew haircut (inherits Tier 2/3 framework exactly).
No-overlap rule: max 1 active position per sleeve.

Additional metrics: max_gain_cap_pct, debit_as_pct_of_width.

Output: research/q042/q062_p2_strike_grid.csv
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
OUT_CSV = Path(__file__).resolve().parent / "q062_p2_strike_grid.csv"

DTE = 90  # fixed
SHORT_MULTIPLIERS = [1.03, 1.05, 1.07, 1.10]
R = 0.04


# ─── Data loading ─────────────────────────────────────────────────────────────

def load_market() -> tuple[pd.DataFrame, pd.Series]:
    spx = pickle.loads(SPX_PKL.read_bytes())
    vix = pickle.loads(VIX_PKL.read_bytes())
    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    vix.index = pd.to_datetime(vix.index).tz_localize(None)
    spx_df = spx.loc["2007-01-01":"2026-05-10"].copy()
    vix_s = vix.loc["2007-01-01":"2026-05-10"]["Close"].copy()
    return spx_df, vix_s


def load_signal_dates() -> dict[str, list[pd.Timestamp]]:
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
    table = {1.00: 1.00, 1.03: 0.96, 1.05: 0.93, 1.07: 0.90, 1.10: 0.85}
    keys = sorted(table.keys())
    if moneyness <= keys[0]:
        return table[keys[0]]
    if moneyness >= keys[-1]:
        slope = (table[keys[-1]] - table[keys[-2]]) / (keys[-1] - keys[-2])
        return table[keys[-1]] + slope * (moneyness - keys[-1])
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


def price_spread(S: float, vix: float, dte: int, short_mult: float) -> tuple[float, float, float, float, float]:
    """Returns (debit_per_share, K_long, K_short, spread_width, spread_width_pct_atm)."""
    K_long = S
    K_short = S * short_mult
    T = dte / 365.0
    p_long = bs_call(S, K_long, T, sigma_for(K_long, S, vix, dte))
    p_short = bs_call(S, K_short, T, sigma_for(K_short, S, vix, dte))
    debit = max(p_long - p_short, 0.01)
    spread_width = K_short - K_long  # = S * (short_mult - 1)
    spread_width_pct = (short_mult - 1) * 100  # e.g. 5.0 for +5%
    return debit, K_long, K_short, spread_width, spread_width_pct


# ─── Exit price ───────────────────────────────────────────────────────────────

def exit_close(spx_df: pd.DataFrame, signal_date: pd.Timestamp, dte: int) -> tuple[float | None, str]:
    target = signal_date + pd.Timedelta(days=dte)
    future = spx_df.loc[signal_date:].loc[target:]
    if future.empty:
        return None, "OPEN"
    return float(future["Close"].iloc[0]), "CLOSED"


# ─── No-overlap filter ────────────────────────────────────────────────────────

def apply_no_overlap(signal_dates: list[pd.Timestamp], dte: int) -> list[pd.Timestamp]:
    result = []
    last_exit = pd.Timestamp("1900-01-01")
    for sd in signal_dates:
        if sd >= last_exit:
            result.append(sd)
            last_exit = sd + pd.Timedelta(days=dte)
    return result


# ─── Worst 12-month drawdown ─────────────────────────────────────────────────

def worst_12m_drawdown(trades: pd.DataFrame, sizing: float = 0.10) -> float:
    """Worst cumulative account % in any 12-month window (10% sizing)."""
    closed = trades[trades["status"] == "CLOSED"].copy()
    if closed.empty:
        return 0.0
    closed = closed.sort_values("signal_date")
    dates = list(closed["signal_date"])
    pnls_acct = [p * sizing for p in closed["pnl_pct"]]
    worst = 0.0
    for i in range(len(dates)):
        window_end = dates[i] + pd.DateOffset(months=12)
        window_pnl = sum(p for j, p in enumerate(pnls_acct) if i <= j and dates[j] <= window_end)
        worst = min(worst, window_pnl)
    return round(worst, 2)


# ─── Compute metrics ──────────────────────────────────────────────────────────

def compute_metrics(
    signal_dates_raw: list[pd.Timestamp],
    spx_df: pd.DataFrame,
    vix_s: pd.Series,
    dte: int,
    short_mult: float,
    sleeve_name: str,
) -> dict:
    filtered = apply_no_overlap(signal_dates_raw, dte)

    trades = []
    debits_list = []
    for sd in filtered:
        if sd not in spx_df.index:
            idx = spx_df.index.searchsorted(sd)
            if idx >= len(spx_df):
                continue
            sd_actual = spx_df.index[idx]
        else:
            sd_actual = sd

        S = float(spx_df.loc[sd_actual, "Close"])

        if sd_actual in vix_s.index:
            vix_val = float(vix_s.loc[sd_actual])
        else:
            idx = vix_s.index.searchsorted(sd_actual)
            if idx >= len(vix_s):
                continue
            vix_val = float(vix_s.iloc[idx])

        if np.isnan(vix_val) or vix_val <= 0:
            continue

        debit, K_long, K_short, spread_width, spread_width_pct = price_spread(S, vix_val, dte, short_mult)
        debits_list.append(debit)

        S_T, status = exit_close(spx_df, sd_actual, dte)

        short_strike_hit = None
        if status == "OPEN":
            latest_S = float(spx_df["Close"].iloc[-1])
            long_payoff = max(0.0, latest_S - K_long)
            short_payoff = max(0.0, latest_S - K_short)
            payoff = long_payoff - short_payoff
        else:
            long_payoff = max(0.0, S_T - K_long)
            short_payoff = max(0.0, S_T - K_short)
            payoff = long_payoff - short_payoff
            short_strike_hit = (S_T >= K_short)

        pnl = payoff - debit
        pnl_pct = pnl / debit * 100  # % of debit (BP)
        max_gain = spread_width - debit  # max possible gain per share
        max_gain_cap_pct = (spread_width / S) * 100  # spread width as % of ATM price

        trades.append({
            "sleeve": sleeve_name,
            "signal_date": sd_actual,
            "short_mult": short_mult,
            "S": S,
            "vix": vix_val,
            "K_long": K_long,
            "K_short": K_short,
            "debit": debit,
            "spread_width": spread_width,
            "spread_width_pct": spread_width_pct,
            "max_gain_cap_pct": max_gain_cap_pct,
            "debit_as_pct_of_width": debit / spread_width * 100,
            "S_T": S_T,
            "payoff": payoff,
            "pnl_pct": pnl_pct,
            "status": status,
            "short_strike_hit": short_strike_hit,
        })

    df = pd.DataFrame(trades)
    if df.empty:
        return {
            "sleeve": sleeve_name,
            "dte": dte,
            "short_mult": short_mult,
            "short_strike_label": f"+{int((short_mult-1)*100)}%",
            "n_raw": len(signal_dates_raw),
            "n_filtered": 0,
        }

    closed = df[df["status"] == "CLOSED"].copy()
    n_closed = len(closed)

    win_rate = float((closed["pnl_pct"] > 0).mean()) * 100 if n_closed > 0 else None
    median_pnl_pct = float(closed["pnl_pct"].median()) if n_closed > 0 else None
    dollar_per_bp_day = (median_pnl_pct / dte) if median_pnl_pct is not None else None

    max_consec = 0
    cur_consec = 0
    for _, row in closed.iterrows():
        if row["pnl_pct"] < 0:
            cur_consec += 1
            max_consec = max(max_consec, cur_consec)
        else:
            cur_consec = 0

    worst_12m = worst_12m_drawdown(df)

    ssh = closed["short_strike_hit"].dropna()
    short_strike_hit_rate = float(ssh.mean()) * 100 if len(ssh) > 0 else None

    if n_closed > 0 and median_pnl_pct is not None:
        date_range_years = (closed["signal_date"].max() - closed["signal_date"].min()).days / 365.25
        trades_per_year = n_closed / date_range_years if date_range_years > 0 else n_closed
        annualized_account_pct = trades_per_year * (median_pnl_pct / 100) * 0.10 * 100
    else:
        annualized_account_pct = None

    # Structural metrics (use medians across trades)
    med_max_gain_cap_pct = float(closed["max_gain_cap_pct"].median()) if n_closed > 0 else None
    med_debit_as_pct_of_width = float(closed["debit_as_pct_of_width"].median()) if n_closed > 0 else None

    return {
        "sleeve": sleeve_name,
        "dte": dte,
        "short_mult": short_mult,
        "short_strike_label": f"+{int((short_mult-1)*100)}%",
        "n_raw": len(signal_dates_raw),
        "n_filtered": n_closed,
        "win_rate": round(win_rate, 1) if win_rate is not None else None,
        "median_pnl_pct": round(median_pnl_pct, 2) if median_pnl_pct is not None else None,
        "dollar_per_bp_day": round(dollar_per_bp_day, 4) if dollar_per_bp_day is not None else None,
        "max_consec_losses": max_consec,
        "worst_12m_drawdown_pct": worst_12m,
        "short_strike_hit_rate_pct": round(short_strike_hit_rate, 1) if short_strike_hit_rate is not None else None,
        "annualized_account_pct": round(annualized_account_pct, 2) if annualized_account_pct is not None else None,
        "max_gain_cap_pct": round(med_max_gain_cap_pct, 2) if med_max_gain_cap_pct is not None else None,
        "debit_as_pct_of_width": round(med_debit_as_pct_of_width, 2) if med_debit_as_pct_of_width is not None else None,
        "max_loss_per_bp_pct": 100.0,  # always 100% of debit for debit spreads
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    spx_df, vix_s = load_market()
    signal_dates = load_signal_dates()

    rows = []
    for sleeve, dates in signal_dates.items():
        for short_mult in SHORT_MULTIPLIERS:
            metrics = compute_metrics(dates, spx_df, vix_s, DTE, short_mult, sleeve)
            rows.append(metrics)
            label = f"+{int((short_mult-1)*100)}%"
            print(f"Sleeve {sleeve} {label}: n_filtered={metrics['n_filtered']}, "
                  f"win_rate={metrics['win_rate']}%, "
                  f"median_pnl={metrics['median_pnl_pct']}%, "
                  f"debit/width={metrics['debit_as_pct_of_width']}%, "
                  f"short_hit={metrics['short_strike_hit_rate_pct']}%")

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)
    print(f"\nWrote {OUT_CSV}")

    print("\n=== P2 Summary ===")
    for sleeve in ["A", "B"]:
        sub = out[out["sleeve"] == sleeve].copy()
        print(f"\nSleeve {sleeve} (DTE={DTE}):")
        print(sub[[
            "short_strike_label", "n_filtered", "win_rate", "median_pnl_pct",
            "dollar_per_bp_day", "max_consec_losses", "worst_12m_drawdown_pct",
            "short_strike_hit_rate_pct", "annualized_account_pct",
            "max_gain_cap_pct", "debit_as_pct_of_width"
        ]].to_string(index=False))


if __name__ == "__main__":
    main()
