"""Q042 PM pushback — LEAP at dd15 + concentrated sizing comparison.

PM challenge:
  1. "dd15 这种大回调应该大幅买入 LEAP，考虑满仓一年后到期"
  2. "19y 个位数 % 营收忽略不计"

Test:
  - Trigger: dd15 naive + no-overlap (Tier 3 winner trigger)
  - Structure variants:
      A. ATM/+5% spread DTE 90 (Tier 3 SPEC-094 baseline)
      B. ATM long call only DTE 90 (no short, full upside)
      C. ATM long call only DTE 365 (LEAP, no short)
      D. ATM/+10% spread DTE 365 (LEAP wide spread)
      E. ATM long call DTE 540 (extra long LEAP)
  - Sizing: 1%, 3%, 5%, 10% account / entry
  - Compare: total 19y account return, max consec losses, max DD, worst 12m

Honest cost-benefit comparison.
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


def find_dd15_entries(df: pd.DataFrame) -> pd.DatetimeIndex:
    return first_triggers(df["dd60"] <= -0.15)


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
    if dte <= 270:
        return 0.95
    return 0.90  # very long-dated even calmer


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


def evaluate_structure(df: pd.DataFrame, entries: pd.DatetimeIndex, structure: str, dte: int) -> pd.DataFrame:
    """Evaluate trades for given structure at given DTE.

    Structures:
      'spread_5pct': long ATM, short +5% (Tier 3 baseline)
      'long_atm':    long ATM only (no short, full upside)
      'spread_10pct': long ATM, short +10% (wider, more upside)
    """
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
        vix = float(df.loc[entry_day, "vix"])
        if np.isnan(vix):
            continue

        K_long = S_signal
        T = dte / 365
        p_long = price_with_skew(S_entry, K_long, T, vix, dte)

        if structure == "long_atm":
            net_debit = p_long
            K_short = None
        elif structure == "spread_5pct":
            K_short = S_signal * 1.05
            p_short = price_with_skew(S_entry, K_short, T, vix, dte)
            net_debit = p_long - p_short
        elif structure == "spread_10pct":
            K_short = S_signal * 1.10
            p_short = price_with_skew(S_entry, K_short, T, vix, dte)
            net_debit = p_long - p_short
        else:
            raise ValueError(structure)

        if net_debit <= 0:
            continue

        target = entry_day + pd.Timedelta(days=dte)
        future = df.loc[entry_day:].loc[target:]
        if future.empty:
            continue
        S_expiry = float(future["close"].iloc[0])

        long_payoff = max(0.0, S_expiry - K_long)
        if K_short is None:
            payoff = long_payoff - net_debit
        else:
            short_payoff = max(0.0, S_expiry - K_short)
            payoff = (long_payoff - short_payoff) - net_debit

        rows.append({
            "entry": entry_day,
            "S_entry": S_entry,
            "S_expiry": S_expiry,
            "fwd_ret_pct": (S_expiry / S_entry - 1) * 100,
            "net_debit": net_debit,
            "pnl_pct_bp": payoff / net_debit * 100,  # PnL as % of debit
        })
    return pd.DataFrame(rows).sort_values("entry").reset_index(drop=True)


def metrics_at_sizing(trades: pd.DataFrame, sizing_pct: float) -> dict:
    """Compute account-level metrics at given % account / entry sizing."""
    if trades.empty:
        return {"n": 0}
    pnl = trades["pnl_pct_bp"].values  # PnL as % of debit
    is_loss = (pnl < 0).astype(int)
    max_consec = 0
    cur = 0
    for x in is_loss:
        if x:
            cur += 1
            max_consec = max(max_consec, cur)
        else:
            cur = 0

    # Account contribution per trade = sizing_pct × (pnl_pct_bp / 100)
    account_pct = (pnl / 100) * sizing_pct
    cum = np.cumsum(account_pct)
    max_dd = float(np.min(cum - np.maximum.accumulate(cum)))
    return {
        "n": len(trades),
        "win_rate": float((pnl > 0).mean()),
        "median_pnl_pct_bp": float(np.median(pnl)),
        "mean_pnl_pct_bp": float(np.mean(pnl)),
        "best_pnl_pct_bp": float(np.max(pnl)),
        "worst_pnl_pct_bp": float(np.min(pnl)),
        "max_consec_losses": max_consec,
        # Convert from fraction to percent for display
        "max_dd_account_pct": max_dd * 100,
        "total_account_pct_19y": float(cum[-1]) * 100,
        "annualized_account_pct": float(cum[-1] / 19) * 100,
    }


def main() -> None:
    spx, vix = load()
    df = pd.DataFrame(index=spx.index)
    df["close"] = spx["Close"]
    df["open"] = spx["Open"]
    df["high60"] = df["close"].rolling(60).max()
    df["dd60"] = df["close"] / df["high60"] - 1
    df["vix"] = vix.reindex(df.index).ffill()

    entries_raw = find_dd15_entries(df)

    print("=" * 110)
    print("PM pushback — LEAP / large-sizing comparison at dd15 naive + no-overlap")
    print("=" * 110)

    # 5 structure variants
    variants = [
        ("A. spread ATM/+5% DTE 90 (Tier 3 baseline)", "spread_5pct", 90),
        ("B. long ATM call DTE 90", "long_atm", 90),
        ("C. long ATM call DTE 365 (LEAP)", "long_atm", 365),
        ("D. spread ATM/+10% DTE 365 (LEAP wide)", "spread_10pct", 365),
        ("E. long ATM call DTE 540 (extra LEAP)", "long_atm", 540),
    ]

    sizings = [0.01, 0.03, 0.05, 0.10]  # 1%, 3%, 5%, 10% account / entry

    all_results = []
    for label, structure, dte in variants:
        # Apply no-overlap rule with this DTE
        entries = apply_no_overlap(entries_raw, dte)
        trades = evaluate_structure(df, entries, structure, dte)
        if trades.empty:
            continue

        print(f"\n=== {label} ===")
        print(f"trigger n_filtered: {len(trades)} (out of {len(entries_raw)} raw dd15 first-triggers)")
        print(f"trade-level: win_rate={metrics_at_sizing(trades, 1.0)['win_rate']*100:.0f}%, "
              f"median PnL/$debit={metrics_at_sizing(trades, 1.0)['median_pnl_pct_bp']:+.0f}%, "
              f"best={metrics_at_sizing(trades, 1.0)['best_pnl_pct_bp']:+.0f}%, "
              f"worst={metrics_at_sizing(trades, 1.0)['worst_pnl_pct_bp']:+.0f}%, "
              f"max consec losses={metrics_at_sizing(trades, 1.0)['max_consec_losses']}")

        print(f"\nSizing comparison:")
        print(f"{'Sizing':>8} | {'Total 19y':>10} | {'Ann %':>8} | {'Max DD':>8} | {'Worst single trade':>20}")
        print("-" * 75)
        for sz in sizings:
            m = metrics_at_sizing(trades, sz)
            worst_single = m['worst_pnl_pct_bp'] * sz  # %_pnl × sizing_fraction = % account
            print(f"{sz*100:>6.0f}%  | {m['total_account_pct_19y']:>+9.1f}% | "
                  f"{m['annualized_account_pct']:>+7.2f}% | {m['max_dd_account_pct']:>+7.1f}% | {worst_single:>+19.1f}%")
            all_results.append({
                "structure": label,
                "sizing_pct": sz,
                "n": m["n"],
                **m,
                "worst_single_account_pct": worst_single,
            })

    # Save full grid
    out = pd.DataFrame(all_results)
    out_path = Path(__file__).resolve().parent / "pm_pushback_leap_grid.csv"
    out.to_csv(out_path, index=False)

    # Headline comparison
    print("\n" + "=" * 110)
    print("Headline: best variant per sizing level (highest 19y total subject to max DD ≤ 20%)")
    print("=" * 110)
    print(f"{'Sizing':>8} | {'Variant':<50} | {'19y total':>10} | {'Ann':>7} | {'Max DD':>8}")
    print("-" * 100)
    for sz in sizings:
        candidates = out[(out["sizing_pct"] == sz) & (out["max_dd_account_pct"] >= -20)]
        if candidates.empty:
            print(f"{sz*100:>6.0f}%  | (none satisfies max DD ≤ 20%)")
            continue
        winner = candidates.sort_values("total_account_pct_19y", ascending=False).iloc[0]
        print(f"{sz*100:>6.0f}%  | {winner['structure']:<50} | {winner['total_account_pct_19y']:>+9.1f}% | "
              f"{winner['annualized_account_pct']:>+6.2f}% | {winner['max_dd_account_pct']:>+7.1f}%")


if __name__ == "__main__":
    main()
