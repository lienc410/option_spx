"""Q042 — ddATH_lenient × MA reclaim filter for dd4 and dd15.

Compare the new ddATH_lenient baseline (dd4 / dd15) with MA filter overlays:
  - none (baseline)
  - ma10_reclaim
  - ma20_reclaim
  - ma50_reclaim
  - ma10_cross_ma50

Logic:
  1. ddATH_lenient first-cross fires the trigger (re-arms when ddATH ≥ -2%)
  2. After trigger, enter "watching" 30 trading days for MA filter to fire
  3. MA fire day = entry day (T+1 open execution)
  4. No-overlap rule applied on actual entry days
  5. Structure: ATM/+5% spread DTE 90, 10% sizing
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


def find_ddath_triggers(df: pd.DataFrame, thr: float, rearm_at: float = -0.02) -> pd.DatetimeIndex:
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


def apply_ma_filter(df: pd.DataFrame, ddath_triggers: pd.DatetimeIndex, filter_kind: str, window_days: int = 30) -> pd.DatetimeIndex:
    """For each ddATH trigger, find first day in next window_days satisfying MA filter.

    filter_kind: 'none' / 'ma10_reclaim' / 'ma20_reclaim' / 'ma50_reclaim' / 'ma10_cross_ma50'
    """
    if filter_kind == "none":
        return ddath_triggers

    entries = []
    for td in ddath_triggers:
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
            cross = (window["ma10"] > window["ma50"]) & (window["ma10"].shift(1) <= window["ma50"].shift(1))
            ok = window[cross.fillna(False)]
        else:
            raise ValueError(filter_kind)

        if not ok.empty:
            entries.append(ok.index[0])
    return pd.DatetimeIndex(entries).unique()


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
        return {"n": 0, "win_rate": 0, "median_winner_account_pct": 0, "total_19y": 0,
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
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma50"] = df["close"].rolling(50).mean()
    df["vix"] = vix.reindex(df.index).ffill()
    years = (df.index.max() - df.index.min()).days / 365

    print(f"Span: {df.index.min().date()} → {df.index.max().date()} ({years:.1f}y)")
    print(f"Structure: ATM/+5% spread DTE 90, T+1 open, no-overlap, 10% sizing")

    SIZING = 0.10
    rows = []
    for thr in [0.04, 0.15]:
        ddath_trigs = find_ddath_triggers(df, thr, rearm_at=-0.02)
        for filt in ["none", "ma10_reclaim", "ma20_reclaim", "ma50_reclaim", "ma10_cross_ma50"]:
            entries_pre = apply_ma_filter(df, ddath_trigs, filt)
            entries_filt = apply_no_overlap(entries_pre, 90)
            trades = evaluate(df, entries_filt)
            m = metrics(trades, SIZING, years)
            m["thr"] = thr
            m["filter"] = filt
            m["raw_ddath_triggers"] = len(ddath_trigs)
            m["after_ma_filter"] = len(entries_pre)
            rows.append(m)

    out = pd.DataFrame(rows)

    for thr in [0.04, 0.15]:
        sub = out[out["thr"] == thr]
        print(f"\n=== ddATH_lenient {int(thr*100)}% × MA filter ===")
        print(f"{'filter':<20} | {'raw':>4} | {'post-MA':>7} | {'n_filt':>6} | {'/yr':>4} | "
              f"{'Win%':>5} | {'MedWin':>7} | {'19y':>8} | {'Ann':>7} | {'Max DD':>8} | {'MaxCon':>6}")
        print("-" * 120)
        for _, r in sub.iterrows():
            tpy = r["n"] / years if r["n"] > 0 else 0
            print(f"{r['filter']:<20} | {int(r['raw_ddath_triggers']):>4} | {int(r['after_ma_filter']):>7} | "
                  f"{int(r['n']):>6} | {tpy:>4.2f} | {r['win_rate']*100:>4.0f}% | "
                  f"{r['median_winner_account_pct']:>+6.2f}% | "
                  f"{r['total_19y']:>+7.1f}% | {r['annualized']:>+6.2f}% | "
                  f"{r['max_dd']:>+7.1f}% | {int(r['max_consec_l']):>6d}")

    out_path = Path(__file__).resolve().parent / "ddath_ma_filter_grid.csv"
    out.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
