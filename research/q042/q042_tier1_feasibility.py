"""Q042 Tier 1 — Directional Drawdown / Reversal Overlay feasibility scan.

Three questions, single-script answer:

Q1. After SPX drawdown of 5/10/15/20% from 60d/90d high, what does forward
    3/6/12-mo SPX return distribution look like? Does technical reclaim
    (close > 50dma / 200dma) filter materially shift the distribution?

Q2. Among LEAP call (DTE 365, ATM and Δ≈0.35), call spread (DTE 90 ATM/+5%),
    which gives better PnL per BP-day vs the main-strategy baseline ~$4-5/BP-day?
    Simplification: BS pricing with VIX_at_entry as σ, r=0.04, hold to expiry,
    payoff = max(0, S_T - K) − premium. BP = premium (long premium account).

Q3. At drawdown trigger dates, what's the VIX distribution? How often do we
    enter when VIX>22 (HIGH_VOL — main strategy in BPS_HV / reduced posture)?
    Does Q042 stack BP exactly when main strategy is stressed?

Output: one-line conclusion + supporting numbers per question.
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

START = "2007-01-01"
END = "2026-05-08"


def load() -> tuple[pd.DataFrame, pd.Series]:
    spx = pickle.loads(SPX_PKL.read_bytes())
    vix = pickle.loads(VIX_PKL.read_bytes())
    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    vix.index = pd.to_datetime(vix.index).tz_localize(None)
    spx = spx.loc[START:END].copy()
    vix = vix.loc[START:END]["Close"].copy()
    return spx, vix


def first_triggers(condition: pd.Series) -> pd.DatetimeIndex:
    """Return only the first day each contiguous True window starts."""
    fired = condition & ~condition.shift(1).fillna(False)
    return condition.index[fired]


def q1_drawdown_forward(spx: pd.DataFrame) -> str:
    df = pd.DataFrame(index=spx.index)
    df["close"] = spx["Close"]
    df["high60"] = df["close"].rolling(60).max()
    df["high90"] = df["close"].rolling(90).max()
    df["dd60"] = df["close"] / df["high60"] - 1
    df["dd90"] = df["close"] / df["high90"] - 1
    df["ma50"] = df["close"].rolling(50).mean()
    df["ma200"] = df["close"].rolling(200).mean()
    for h, label in [(63, "fwd_3m"), (126, "fwd_6m"), (252, "fwd_12m")]:
        df[label] = df["close"].shift(-h) / df["close"] - 1

    lines = []
    lines.append("=" * 78)
    lines.append("Q1. Drawdown depth → forward SPX return (2007-2026, 60d high lookback)")
    lines.append("=" * 78)
    lines.append(
        f"{'thr':>5} | {'n':>4} | "
        f"{'3m_med':>7} {'3m_avg':>7} {'3m_pos%':>7} | "
        f"{'6m_med':>7} {'6m_avg':>7} {'6m_pos%':>7} | "
        f"{'12m_med':>7} {'12m_avg':>7} {'12m_pos%':>7}"
    )
    lines.append("-" * 78)
    summaries = {}
    for thr in [0.05, 0.10, 0.15, 0.20]:
        dates = first_triggers(df["dd60"] <= -thr)
        sub = df.loc[dates]
        s3 = sub["fwd_3m"].dropna()
        s6 = sub["fwd_6m"].dropna()
        s12 = sub["fwd_12m"].dropna()
        summaries[thr] = (s3, s6, s12)
        lines.append(
            f"{thr:>5.2f} | {len(dates):>4} | "
            f"{s3.median()*100:>6.1f}% {s3.mean()*100:>6.1f}% {(s3>0).mean()*100:>6.1f}% | "
            f"{s6.median()*100:>6.1f}% {s6.mean()*100:>6.1f}% {(s6>0).mean()*100:>6.1f}% | "
            f"{s12.median()*100:>6.1f}% {s12.mean()*100:>6.1f}% {(s12>0).mean()*100:>6.1f}%"
        )

    lines.append("")
    lines.append("With MA50 reclaim filter: enter only when, after trigger, close > ma50")
    lines.append("within next 30 trading days. Skips 'falling knife' entries.")
    lines.append("-" * 78)
    lines.append(
        f"{'thr':>5} | {'n':>4} | "
        f"{'3m_med':>7} {'3m_avg':>7} {'3m_pos%':>7} | "
        f"{'6m_med':>7} {'6m_avg':>7} {'6m_pos%':>7} | "
        f"{'12m_med':>7} {'12m_avg':>7} {'12m_pos%':>7}"
    )
    lines.append("-" * 78)
    for thr in [0.05, 0.10, 0.15, 0.20]:
        trigger_dates = first_triggers(df["dd60"] <= -thr)
        # For each trigger, find first day within next 30 trading days where close > ma50
        entry_dates = []
        for td in trigger_dates:
            window = df.loc[td:].iloc[:30]
            reclaimed = window[window["close"] > window["ma50"]]
            if not reclaimed.empty:
                entry_dates.append(reclaimed.index[0])
        entry_dates = pd.DatetimeIndex(entry_dates).unique()
        sub = df.loc[entry_dates]
        s3 = sub["fwd_3m"].dropna()
        s6 = sub["fwd_6m"].dropna()
        s12 = sub["fwd_12m"].dropna()
        lines.append(
            f"{thr:>5.2f} | {len(entry_dates):>4} | "
            f"{s3.median()*100:>6.1f}% {s3.mean()*100:>6.1f}% {(s3>0).mean()*100:>6.1f}% | "
            f"{s6.median()*100:>6.1f}% {s6.mean()*100:>6.1f}% {(s6>0).mean()*100:>6.1f}% | "
            f"{s12.median()*100:>6.1f}% {s12.mean()*100:>6.1f}% {(s12>0).mean()*100:>6.1f}%"
        )

    # Compare with unconditional baseline (any random trading day)
    s3 = df["fwd_3m"].dropna()
    s6 = df["fwd_6m"].dropna()
    s12 = df["fwd_12m"].dropna()
    lines.append("")
    lines.append("UNCONDITIONAL baseline (any trading day 2007-2026):")
    lines.append(
        f"      | {len(s12):>4} | "
        f"{s3.median()*100:>6.1f}% {s3.mean()*100:>6.1f}% {(s3>0).mean()*100:>6.1f}% | "
        f"{s6.median()*100:>6.1f}% {s6.mean()*100:>6.1f}% {(s6>0).mean()*100:>6.1f}% | "
        f"{s12.median()*100:>6.1f}% {s12.mean()*100:>6.1f}% {(s12>0).mean()*100:>6.1f}%"
    )

    return "\n".join(lines), summaries


def bs_call(S: float, K: float, T: float, sigma: float, r: float = 0.04) -> float:
    if T <= 0:
        return max(0.0, S - K)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def strike_for_delta(S: float, T: float, sigma: float, target_delta: float, r: float = 0.04) -> float:
    """Solve for K such that BS call delta = target_delta."""
    d1 = norm.ppf(target_delta)
    # d1 = [ln(S/K) + (r+0.5σ²)T] / (σ√T)  →  ln(S/K) = d1σ√T − (r+0.5σ²)T
    log_ratio = d1 * sigma * np.sqrt(T) - (r + 0.5 * sigma**2) * T
    return S / np.exp(log_ratio)


def q2_option_structure(spx: pd.DataFrame, vix: pd.Series) -> str:
    """Compare LEAP ATM call, LEAP Δ0.35 call, ATM/+5% call spread.

    For each 10% drawdown trigger from 60d high, price option at trigger close,
    use VIX as σ, hold to expiry, payoff vs S_T.

    Use 6-mo forward S as expiry for 90-day spread? No — to keep apples-to-apples,
    each structure has its own DTE: LEAPs use 252-day forward, spread uses 63-day.
    """
    df = pd.DataFrame(index=spx.index)
    df["close"] = spx["Close"]
    df["high60"] = df["close"].rolling(60).max()
    df["dd60"] = df["close"] / df["high60"] - 1
    df["fwd_63"] = df["close"].shift(-63)
    df["fwd_126"] = df["close"].shift(-126)
    df["fwd_252"] = df["close"].shift(-252)
    df["vix"] = vix.reindex(df.index).ffill()

    triggers = first_triggers(df["dd60"] <= -0.10)
    sub = df.loc[triggers].dropna(subset=["fwd_252", "fwd_63", "vix"])

    rows = []
    for dt, row in sub.iterrows():
        S = float(row["close"])
        sigma = max(0.10, float(row["vix"]) / 100.0)  # floor at 10%

        # LEAP ATM, DTE 365, K=S
        T = 1.0
        K = S
        prem = bs_call(S, K, T, sigma)
        S_T = float(row["fwd_252"])
        payoff = max(0.0, S_T - K) - prem
        roe_leap_atm = payoff / prem  # full-period ROE
        bp_day_leap_atm = payoff / (prem * 365 / 100)  # $ per $100 BP per day

        # LEAP Δ=0.35, DTE 365
        K35 = strike_for_delta(S, T, sigma, 0.35)
        prem35 = bs_call(S, K35, T, sigma)
        payoff35 = max(0.0, S_T - K35) - prem35
        roe_leap_35 = payoff35 / prem35
        bp_day_leap_35 = payoff35 / (prem35 * 365 / 100)

        # Call spread DTE 90: long ATM, short K=S*1.05
        T_sp = 90 / 365
        Kshort = S * 1.05
        prem_long = bs_call(S, S, T_sp, sigma)
        prem_short = bs_call(S, Kshort, T_sp, sigma)
        net_debit = prem_long - prem_short
        S_T_sp = float(row["fwd_63"])  # ~63 trading days ≈ 90 calendar days
        long_payoff = max(0.0, S_T_sp - S)
        short_payoff = max(0.0, S_T_sp - Kshort)
        spread_payoff = (long_payoff - short_payoff) - net_debit
        roe_spread = spread_payoff / net_debit
        bp_day_spread = spread_payoff / (net_debit * 90 / 100)

        rows.append({
            "date": dt,
            "S": S,
            "vix": float(row["vix"]),
            "S_T_252": S_T,
            "S_T_63": S_T_sp,
            "leap_atm_prem%": prem / S * 100,
            "leap_atm_pnl$_per_$100BP": payoff / prem * 100,
            "leap_35_pnl$_per_$100BP": payoff35 / prem35 * 100,
            "spread_net_debit%": net_debit / S * 100,
            "spread_pnl$_per_$100BP": spread_payoff / net_debit * 100,
            "leap_atm_$bp_day": bp_day_leap_atm,
            "leap_35_$bp_day": bp_day_leap_35,
            "spread_$bp_day": bp_day_spread,
        })

    res = pd.DataFrame(rows)

    lines = []
    lines.append("=" * 78)
    lines.append("Q2. Option structure economics (10% dd60 triggers, hold to expiry)")
    lines.append("=" * 78)
    lines.append(f"trigger sample n={len(res)}")
    lines.append("")
    lines.append("$ PnL per $100 of BP, full-period (held to expiry):")
    for col in ["leap_atm_pnl$_per_$100BP", "leap_35_pnl$_per_$100BP", "spread_pnl$_per_$100BP"]:
        s = res[col]
        lines.append(
            f"  {col:<32}  median={s.median():>+7.1f}  avg={s.mean():>+7.1f}  "
            f"win%={(s>0).mean()*100:>5.1f}%  worst={s.min():>+7.1f}  best={s.max():>+7.1f}"
        )
    lines.append("")
    lines.append("$ PnL per $100 BP per DAY (apples-to-apples normalized):")
    for col in ["leap_atm_$bp_day", "leap_35_$bp_day", "spread_$bp_day"]:
        s = res[col]
        lines.append(
            f"  {col:<32}  median={s.median():>+6.3f}  avg={s.mean():>+6.3f}  "
            f"win%={(s>0).mean()*100:>5.1f}%"
        )
    lines.append("")
    lines.append("Baseline (main short-premium strategy): ~$4-5 per $100 BP per day")
    lines.append("                                         (i.e. ~4-5% annualized basis)")
    return "\n".join(lines), res


def q3_regime_overlap(spx: pd.DataFrame, vix: pd.Series) -> str:
    df = pd.DataFrame(index=spx.index)
    df["close"] = spx["Close"]
    df["high60"] = df["close"].rolling(60).max()
    df["high90"] = df["close"].rolling(90).max()
    df["dd60"] = df["close"] / df["high60"] - 1
    df["dd90"] = df["close"] / df["high90"] - 1
    df["vix"] = vix.reindex(df.index).ffill()

    lines = []
    lines.append("=" * 78)
    lines.append("Q3. Regime overlap with main strategy (HIGH_VOL = VIX>22)")
    lines.append("=" * 78)

    base_hv_rate = (df["vix"] > 22).mean()
    lines.append(f"baseline HIGH_VOL frequency on any trading day: {base_hv_rate*100:.1f}%")
    lines.append("")
    lines.append(f"{'thr':>5} | {'n':>4} | {'vix_med':>7} {'vix_avg':>7} {'vix_p75':>7} | {'HV_rate':>7}")
    lines.append("-" * 60)
    for thr in [0.05, 0.10, 0.15, 0.20]:
        dates = first_triggers(df["dd60"] <= -thr)
        sub = df.loc[dates]
        v = sub["vix"].dropna()
        hv_rate = (v > 22).mean()
        lines.append(
            f"{thr:>5.2f} | {len(v):>4} | "
            f"{v.median():>7.1f} {v.mean():>7.1f} {v.quantile(0.75):>7.1f} | "
            f"{hv_rate*100:>6.1f}%"
        )

    return "\n".join(lines)


def main() -> None:
    spx, vix = load()
    print(f"loaded SPX 1d {len(spx)} rows {spx.index.min().date()} → {spx.index.max().date()}")
    print(f"loaded VIX 1d {len(vix)} rows {vix.index.min().date()} → {vix.index.max().date()}")
    print()

    q1_text, _ = q1_drawdown_forward(spx)
    print(q1_text)
    print()

    q2_text, _ = q2_option_structure(spx, vix)
    print(q2_text)
    print()

    print(q3_regime_overlap(spx, vix))


if __name__ == "__main__":
    main()
