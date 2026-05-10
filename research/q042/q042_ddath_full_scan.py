"""Q042 — Full ddATH scan dd3% through dd15%.

Re-scan all drawdown thresholds using ddATH definition (running max from
2007-01-01 baseline). Compare strict (re-arm only at new ATH) vs lenient
(re-arm when ddATH ≤ -2%).

Structure: ATM/+5% spread DTE 90, T+1 open, no-overlap, 10% sizing.
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


def find_triggers_ddath(df: pd.DataFrame, thr: float, rearm_at: float) -> pd.DatetimeIndex:
    ath = df["close"].cummax()
    ddath = df["close"] / ath - 1
    triggers = []
    armed = True
    for dt, dd in ddath.items():
        if armed and dd <= -thr:
            triggers.append(dt)
            armed = False
        elif (not armed) and dd >= rearm_at:
            armed = True
    return pd.DatetimeIndex(triggers)


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
            "entry_date": entry_day,
            "vix": vix,
            "pnl_pct_debit": spread_payoff / net_debit * 100,
        })
    return pd.DataFrame(rows).sort_values("entry_date").reset_index(drop=True)


def metrics(trades: pd.DataFrame, sizing_pct: float, years: float) -> dict:
    if trades.empty:
        return {"n": 0, "win_rate": 0, "median_winner": 0, "total_19y": 0,
                "annualized": 0, "max_dd": 0, "max_consec_l": 0}
    pnl = trades["pnl_pct_debit"].values
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
    account_pct = (pnl / 100) * sizing_pct * 100
    cum = np.cumsum(account_pct)
    max_dd = float(np.min(cum - np.maximum.accumulate(cum)))
    return {
        "n": len(trades),
        "win_rate": float((pnl > 0).mean()),
        "median_winner": float(np.median(winners)) if len(winners) > 0 else 0,
        "median_winner_account_pct": float(np.median(winners)) * sizing_pct if len(winners) > 0 else 0,
        "total_19y": float(cum[-1]),
        "annualized": float(cum[-1] / years),
        "max_dd": max_dd,
        "max_consec_l": max_consec,
    }


def main() -> None:
    spx, vix = load()
    df = pd.DataFrame(index=spx.index)
    df["close"] = spx["Close"]
    df["open"] = spx["Open"]
    df["vix"] = vix.reindex(df.index).ffill()
    years = (df.index.max() - df.index.min()).days / 365

    print(f"Span: {df.index.min().date()} → {df.index.max().date()} ({years:.1f}y)")
    print(f"Structure: ATM/+5% spread DTE 90, T+1 open, no-overlap, 10% sizing")

    SIZING = 0.10
    thresholds = [0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.13, 0.14, 0.15]

    rows = []
    for variant_label, rearm in [("ddATH_strict", 0.0), ("ddATH_lenient", -0.02)]:
        for thr in thresholds:
            entries_raw = find_triggers_ddath(df, thr, rearm_at=rearm)
            entries_filt = apply_no_overlap(entries_raw, 90)
            trades = evaluate(df, entries_filt)
            m = metrics(trades, SIZING, years)
            m["variant"] = variant_label
            m["thr"] = thr
            m["raw_triggers"] = len(entries_raw)
            rows.append(m)

    out = pd.DataFrame(rows)

    for variant in ["ddATH_strict", "ddATH_lenient"]:
        sub = out[out["variant"] == variant]
        print(f"\n=== {variant} ===")
        print(f"{'thr':>4} | {'n_raw':>5} | {'n_filt':>6} | {'/yr':>4} | {'Win%':>5} | "
              f"{'MedWin':>7} | {'19y':>8} | {'Ann':>7} | {'Max DD':>8} | {'MaxCon':>6}")
        print("-" * 100)
        for _, r in sub.iterrows():
            tpy = r["n"] / years if r["n"] > 0 else 0
            print(f"{r['thr']*100:>3.0f}%  | {int(r['raw_triggers']):>5} | {int(r['n']):>6} | "
                  f"{tpy:>4.2f} | {r['win_rate']*100:>4.0f}% | "
                  f"{r['median_winner_account_pct']:>+6.2f}% | "
                  f"{r['total_19y']:>+7.1f}% | {r['annualized']:>+6.2f}% | "
                  f"{r['max_dd']:>+7.1f}% | {int(r['max_consec_l']):>6d}")

    # Headline: best annualized (n>=5, max DD ≤ 25%)
    print("\n" + "=" * 100)
    print("Headline: top configs (n ≥ 5, max DD ≤ 25%, sorted by annualized)")
    print("=" * 100)
    eligible = out[(out["max_dd"] >= -25) & (out["n"] >= 5)]
    print(f"{'rank':>4} | {'variant':<14} | {'thr':>4} | {'n':>4} | {'Win%':>5} | "
          f"{'19y':>8} | {'Ann':>7} | {'Max DD':>8}")
    print("-" * 80)
    for i, (_, r) in enumerate(eligible.sort_values("annualized", ascending=False).head(10).iterrows(), 1):
        print(f"{i:>4} | {r['variant']:<14} | {r['thr']*100:>3.0f}%  | "
              f"{int(r['n']):>4} | {r['win_rate']*100:>4.0f}% | "
              f"{r['total_19y']:>+7.1f}% | {r['annualized']:>+6.2f}% | {r['max_dd']:>+7.1f}%")

    out_path = Path(__file__).resolve().parent / "ddath_full_scan.csv"
    out.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
