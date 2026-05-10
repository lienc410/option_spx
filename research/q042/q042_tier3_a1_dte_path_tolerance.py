"""Q042 Tier 3 — A1 DTE path-tolerance multi-metric comparison.

Reviewer's challenge (Q2): $/BP-day over-favors short DTE for a directional
recovery overlay. Path tolerance matters more than capital-time efficiency.

This analysis compares DTE 30 / 60 / 90 / 120 ATM/+5% call spreads on:
  - $/BP-day (efficiency)
  - total PnL (economic value)
  - median / mean PnL per trade
  - win rate
  - max consecutive losses
  - account-level ROE (assuming 1% account/entry)
  - worst 5 trades
  - 30d / 60d / 90d forward SPX return alignment with structure window
  - "sideways tolerance": % of trades where SPX recovered to +5% within DTE
  - "delayed-recovery survival": for trades that lost money, what would
    a longer DTE have produced?

Triggers tested:
  - dd12 + ma50_reclaim (Tier 2 lead winner)
  - dd15 naive (reviewer's required benchmark)
  - dd10 + ma50_reclaim (secondary benchmark)

Pricing: same BS + skew haircut + term-structure multiplier as Tier 2 P2.
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


# Pricing (same as Tier 2 P2)


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


def forward_close(df: pd.DataFrame, entry_date: pd.Timestamp, dte: int) -> float | None:
    target = entry_date + pd.Timedelta(days=dte)
    future = df.loc[entry_date:].loc[target:]
    if future.empty:
        return None
    return float(future["close"].iloc[0])


# Analysis


def evaluate_trades(df: pd.DataFrame, entries: pd.DatetimeIndex, dte: int, otm_pct: float = 0.05) -> pd.DataFrame:
    rows = []
    for entry in entries:
        if entry not in df.index:
            continue
        S = float(df.loc[entry, "close"])
        vix = float(df.loc[entry, "vix"])
        if np.isnan(vix):
            continue
        S_T = forward_close(df, entry, dte)
        if S_T is None:
            continue

        K_long = S
        K_short = S * (1 + otm_pct)
        T = dte / 365
        p_long = price_with_skew(S, K_long, T, vix, dte)
        p_short = price_with_skew(S, K_short, T, vix, dte)
        net_debit = p_long - p_short
        if net_debit <= 0:
            continue
        long_payoff = max(0.0, S_T - K_long)
        short_payoff = max(0.0, S_T - K_short)
        spread_payoff = (long_payoff - short_payoff) - net_debit
        max_gain = (K_short - K_long) - net_debit  # capped upside
        ret_pct = S_T / S - 1

        rows.append({
            "entry": entry,
            "S": S,
            "S_T": S_T,
            "vix": vix,
            "fwd_ret_pct": ret_pct,
            "net_debit": net_debit,
            "max_gain": max_gain,
            "pnl_pct_bp": spread_payoff / net_debit * 100,  # PnL per $100 BP
            "pnl_usd_per_S": spread_payoff,                 # raw $ per share
            "is_max_loss": spread_payoff <= -net_debit * 0.99,
            "is_max_gain": spread_payoff >= max_gain * 0.99,
            "fwd_ret_in_window": (ret_pct >= otm_pct),     # SPX hit short strike
        })
    return pd.DataFrame(rows)


def trade_metrics(trades: pd.DataFrame, dte: int) -> dict:
    if trades.empty:
        return {"n": 0}
    pnl = trades["pnl_pct_bp"]
    sorted_pnl = pnl.sort_values()

    # Max consecutive losses
    is_loss = (pnl < 0).astype(int).values
    max_consec = 0
    cur = 0
    for x in is_loss:
        if x:
            cur += 1
            max_consec = max(max_consec, cur)
        else:
            cur = 0

    # Account-level ROE assuming 1% account / entry, full debit at risk
    # If 1% per entry and pnl = X% of debit, then account contribution = 0.01 × X
    account_pct_per_trade = pnl / 100 * 1.0  # 1% per entry
    annualized_pct = account_pct_per_trade.sum() / (
        (trades["entry"].max() - trades["entry"].min()).days / 365
    )

    return {
        "n": len(trades),
        "median_pnl_pct_bp": float(pnl.median()),
        "mean_pnl_pct_bp": float(pnl.mean()),
        "win_rate": float((pnl > 0).mean()),
        "median_$bp_day": float(pnl.median() / dte),
        "max_consecutive_losses": int(max_consec),
        "worst_5_avg": float(sorted_pnl.head(5).mean()),
        "best_5_avg": float(sorted_pnl.tail(5).mean()),
        "fwd_ret_at_short_strike_pct": float(trades["fwd_ret_in_window"].mean()) * 100,
        "max_loss_pct_trades": float(trades["is_max_loss"].mean()) * 100,
        "max_gain_pct_trades": float(trades["is_max_gain"].mean()) * 100,
        "annualized_account_pct": float(annualized_pct) * 100,  # in % account / yr
        "total_account_pct": float(account_pct_per_trade.sum()) * 100,
    }


def main() -> None:
    spx, vix = load()
    df = build_features(spx, vix)

    triggers = {
        "dd12_ma50_reclaim": find_entries(df, 0.12, "ma50_reclaim"),
        "dd15_naive": find_entries(df, 0.15, "none"),
        "dd10_ma50_reclaim": find_entries(df, 0.10, "ma50_reclaim"),
    }

    print("=" * 100)
    print("A1 — DTE path-tolerance multi-metric (ATM/+5% call spread)")
    print("=" * 100)

    rows = []
    for trig_name, entries in triggers.items():
        for dte in [30, 60, 90, 120]:
            trades = evaluate_trades(df, entries, dte, otm_pct=0.05)
            metrics = trade_metrics(trades, dte)
            metrics["trigger"] = trig_name
            metrics["dte"] = dte
            rows.append(metrics)

    out = pd.DataFrame(rows)
    out_path = Path(__file__).resolve().parent / "a1_dte_path_tolerance.csv"
    out.to_csv(out_path, index=False)

    # Pretty print
    cols = ["trigger", "dte", "n", "win_rate", "median_pnl_pct_bp", "mean_pnl_pct_bp",
            "median_$bp_day", "max_consecutive_losses", "worst_5_avg",
            "fwd_ret_at_short_strike_pct", "max_loss_pct_trades", "max_gain_pct_trades",
            "annualized_account_pct"]
    print(out[cols].to_string(index=False, float_format=lambda x: f"{x:.2f}" if isinstance(x, float) else str(x)))

    print(f"\nwrote {out_path}")

    # Highlight the trade-off: efficiency winner vs production winner
    print("\n=== Efficiency winner (highest median $/$100BP/day) ===")
    eff_winner = out.sort_values("median_$bp_day", ascending=False).iloc[0]
    print(f"  {eff_winner['trigger']} DTE{eff_winner['dte']}: ${eff_winner['median_$bp_day']:.3f}/$100BP/day, "
          f"{eff_winner['win_rate']*100:.0f}% win, {eff_winner['max_consecutive_losses']} max consecutive losses, "
          f"{eff_winner['annualized_account_pct']:.2f}%/yr account")

    print("\n=== Production winner (highest annualized account % at 1% account/entry) ===")
    prod_winner = out.sort_values("annualized_account_pct", ascending=False).iloc[0]
    print(f"  {prod_winner['trigger']} DTE{prod_winner['dte']}: ${prod_winner['median_$bp_day']:.3f}/$100BP/day, "
          f"{prod_winner['win_rate']*100:.0f}% win, {prod_winner['max_consecutive_losses']} max consecutive losses, "
          f"{prod_winner['annualized_account_pct']:.2f}%/yr account")

    print("\n=== Robustness winner (lowest max consecutive losses, n>=20) ===")
    robust = out[out["n"] >= 20].sort_values("max_consecutive_losses").iloc[0]
    print(f"  {robust['trigger']} DTE{robust['dte']}: ${robust['median_$bp_day']:.3f}/$100BP/day, "
          f"{robust['win_rate']*100:.0f}% win, {robust['max_consecutive_losses']} max consecutive losses, "
          f"{robust['annualized_account_pct']:.2f}%/yr account")

    # Hidden delayed-recovery analysis: at dd12+ma50_reclaim, for trades that lost in DTE30,
    # what would DTE60/90/120 have done?
    print("\n=== Delayed-recovery rescue: DTE30 losers, what DTE60/90/120 would have done? ===")
    entries = triggers["dd12_ma50_reclaim"]
    t30 = evaluate_trades(df, entries, 30, 0.05).set_index("entry")
    losers30 = t30[t30["pnl_pct_bp"] < 0].index
    print(f"DTE30 losers in dd12+reclaim: {len(losers30)} of {len(t30)}")

    for dte_alt in [60, 90, 120]:
        t_alt = evaluate_trades(df, entries, dte_alt, 0.05).set_index("entry")
        rescued = t_alt.loc[losers30.intersection(t_alt.index)]
        if rescued.empty:
            continue
        n_pos = (rescued["pnl_pct_bp"] > 0).sum()
        median_pnl = rescued["pnl_pct_bp"].median()
        print(f"  DTE{dte_alt}: {n_pos}/{len(rescued)} positive ({n_pos/len(rescued)*100:.0f}%), median PnL = {median_pnl:+.1f}/$100 BP")


if __name__ == "__main__":
    main()
