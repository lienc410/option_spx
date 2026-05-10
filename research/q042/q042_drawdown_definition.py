"""Q042 — Drawdown definition comparison.

PM question: should "5% drop" be measured against rolling 60d max (which
steps down in bear markets, creating false re-triggers) or running ATH
(which only resets when SPX makes a new high)?

Variants:
  A. dd60_rolling (current): first day where SPX/max(60d) - 1 ≤ thr;
     natural re-arm when 60d max steps up
  B. dd252_rolling: same with 1-year window
  C. ddATH_strict: from running ATH; re-arm only when SPX makes new ATH
  D. ddATH_lenient: from running ATH; re-arm when ddATH ≤ -2%

Test for each: dd5, dd10, dd15.
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


def find_triggers_dd60_rolling(df: pd.DataFrame, thr: float) -> pd.DatetimeIndex:
    cond = df["dd60"] <= -thr
    fired = cond & ~cond.shift(1).fillna(False)
    return df.index[fired]


def find_triggers_dd252_rolling(df: pd.DataFrame, thr: float) -> pd.DatetimeIndex:
    high252 = df["close"].rolling(252).max()
    dd252 = df["close"] / high252 - 1
    cond = dd252 <= -thr
    fired = cond & ~cond.shift(1).fillna(False)
    return df.index[fired]


def find_triggers_ddath(df: pd.DataFrame, thr: float, rearm_at: float) -> pd.DatetimeIndex:
    """Trigger when ddATH crosses below -thr, after a previous re-arm.

    rearm_at: ddATH level at which we re-arm (e.g., -0.02 = within 2% of ATH).
              Use 0.0 for strict (must reach new ATH).
    """
    ath = df["close"].cummax()
    ddath = df["close"] / ath - 1

    triggers = []
    armed = True  # start armed
    for i, (dt, dd) in enumerate(ddath.items()):
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
            "signal_date": sig,
            "vix": vix,
            "S_entry": S_entry,
            "S_expiry": S_expiry,
            "fwd_ret_pct": (S_expiry / S_entry - 1) * 100,
            "pnl_pct_debit": spread_payoff / net_debit * 100,
            "account_pct_at_10": (spread_payoff / net_debit) * 10,
        })
    return pd.DataFrame(rows).sort_values("entry_date").reset_index(drop=True)


def metrics(trades: pd.DataFrame, sizing_pct: float, years: float) -> dict:
    if trades.empty:
        return {"n": 0, "win_rate": 0, "total_19y_pct": 0, "annualized_pct": 0,
                "max_dd_pct": 0, "max_consec_losses": 0}
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
    account_pct = (pnl / 100) * sizing_pct * 100
    cum = np.cumsum(account_pct)
    max_dd = float(np.min(cum - np.maximum.accumulate(cum)))
    return {
        "n": len(trades),
        "win_rate": float((pnl > 0).mean()),
        "total_19y_pct": float(cum[-1]),
        "annualized_pct": float(cum[-1] / years),
        "max_dd_pct": max_dd,
        "max_consec_losses": max_consec,
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

    print(f"Span: {df.index.min().date()} → {df.index.max().date()} ({years:.1f}y), 10% sizing, ATM/+5% spread DTE 90, no-overlap")

    SIZING = 0.10
    rows = []

    for thr in [0.05, 0.10, 0.15]:
        for variant_name, get_triggers in [
            ("A. dd60_rolling (current)", lambda t: find_triggers_dd60_rolling(df, t)),
            ("B. dd252_rolling", lambda t: find_triggers_dd252_rolling(df, t)),
            ("C. ddATH_strict", lambda t: find_triggers_ddath(df, t, rearm_at=0.0)),
            ("D. ddATH_lenient", lambda t: find_triggers_ddath(df, t, rearm_at=-0.02)),
        ]:
            entries_raw = get_triggers(thr)
            entries_filt = apply_no_overlap(entries_raw, 90)
            trades = evaluate(df, entries_filt)
            m = metrics(trades, SIZING, years)
            m["variant"] = variant_name
            m["thr"] = thr
            m["raw_triggers"] = len(entries_raw)
            rows.append(m)

    out = pd.DataFrame(rows)

    for thr in [0.05, 0.10, 0.15]:
        sub = out[out["thr"] == thr]
        print(f"\n=== Threshold {thr*100:.0f}% ===")
        print(f"{'variant':<28} | {'n_raw':>5} | {'n_filt':>6} | {'/yr':>4} | {'Win%':>5} | "
              f"{'19y':>8} | {'Ann':>7} | {'Max DD':>8} | {'MaxCon':>6}")
        print("-" * 105)
        for _, r in sub.iterrows():
            tpy = r["n"] / years if r["n"] > 0 else 0
            print(f"{r['variant']:<28} | {int(r['raw_triggers']):>5} | {int(r['n']):>6} | "
                  f"{tpy:>4.2f} | {r['win_rate']*100:>4.0f}% | "
                  f"{r['total_19y_pct']:>+7.1f}% | {r['annualized_pct']:>+6.2f}% | "
                  f"{r['max_dd_pct']:>+7.1f}% | {int(r['max_consec_losses']):>6d}")

    out_path = Path(__file__).resolve().parent / "drawdown_definition_grid.csv"
    out.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}")

    # ── Show what 2008 triggers each variant produces (for transparency) ──
    print("\n\n=== 2008-2009 GFC: which triggers fire under each variant (dd5%) ===")
    for variant_name, get_triggers in [
        ("A. dd60_rolling", lambda: find_triggers_dd60_rolling(df, 0.05)),
        ("B. dd252_rolling", lambda: find_triggers_dd252_rolling(df, 0.05)),
        ("C. ddATH_strict", lambda: find_triggers_ddath(df, 0.05, rearm_at=0.0)),
        ("D. ddATH_lenient", lambda: find_triggers_ddath(df, 0.05, rearm_at=-0.02)),
    ]:
        triggers_raw = get_triggers()
        triggers_filt = apply_no_overlap(triggers_raw, 90)
        gfc_triggers = [t for t in triggers_filt if pd.Timestamp("2007-10-01") <= t <= pd.Timestamp("2009-12-31")]
        print(f"\n{variant_name}: {len(gfc_triggers)} GFC-era triggers")
        for t in gfc_triggers:
            spx_close = float(df.loc[t, "close"])
            ath = float(df["close"].loc[:t].max())
            ddath = (spx_close / ath - 1) * 100
            dd60 = float(df.loc[t, "dd60"]) * 100
            print(f"  {t.date()}: SPX={spx_close:.0f}, ATH={ath:.0f}, ddATH={ddath:+.1f}%, dd60={dd60:+.1f}%")


if __name__ == "__main__":
    main()
