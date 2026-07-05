"""Q087 B3 — same-day re-statement of CALIB-based verdicts under pricing-grade
(*_moff) offsets backfilled in B2 (30 days, AC-3 cross-validated).

Re-runs with identical machinery, three sigma scenarios:
  FLAT        : VIX flat (historical convention)
  CALIB_VENDOR: old vendor-iv offsets (short -2.0 / long +1.0) — the basis of
                Q085 P3 withdrawal and Q087 A1 absolute levels
  CALIB_MOFF  : B2 medians (put d30 -0.79 / d15 +1.78) — pricing-grade
Affected verdicts: Q085 P3 (S2-BPS arms), Q087 A1 (IVP strata absolutes).
Relative conclusions (strata indistinguishable, reforms worsen) unaffected.
"""
from __future__ import annotations
import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q085"))
import q085_battery_lib as B

R, Q = 0.05, 0.013
DTE, EXIT_DTE, STOP_X, COST = 30, 21, 3.0, 130.0
SCEN = {"FLAT": (0.0, 0.0), "CALIB_VENDOR": (-2.0, +1.0), "CALIB_MOFF": (-0.79, +1.78)}

def _n(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
def pput(S, K, d, s):
    T = max(d, 0.01) / 365.0
    d1 = (math.log(S / K) + (R - Q + 0.5 * s * s) * T) / (s * math.sqrt(T))
    return K * math.exp(-R * T) * _n(-(d1 - s * math.sqrt(T))) - S * math.exp(-Q * T) * _n(-d1)
def pdelta(S, K, d, s):
    T = d / 365.0
    d1 = (math.log(S / K) + (R - Q + 0.5 * s * s) * T) / (s * math.sqrt(T))
    return math.exp(-Q * T) * (1 - _n(d1))
def kfor(S, d, s, t):
    lo, hi = S * 0.5, S * 1.2
    for _ in range(70):
        m = 0.5 * (lo + hi)
        if pdelta(S, m, d, s) > t: hi = m
        else: lo = m
    return round(m / 5) * 5

df, C = B.df, B.C
sig = pd.read_csv(B.ROOT / "research/q078/_signal_history_cache.csv",
                  parse_dates=["date"]).set_index("date")
for col in ("regime", "trend", "iv_signal", "ivp", "strategy_key"):
    df[col] = sig[col].reindex(df.index)
allowed = df["strategy_key"].fillna("") != ""
comp = (B.SIGNALS["F3_rsi2_os"] | B.SIGNALS["F3_down3"]).fillna(False)
base = (df.index >= "2000-01-01") & B.default_valid & df["vix"].notna()
dates, close, vix = df.index, C.to_numpy(), df["vix"].to_numpy()

MASKS = {
    "P3 INCUMBENT": (df["strategy_key"] == "bull_put_spread") & base,
    "P3 CHALLENGER": (~allowed) & (df.regime == "NORMAL") & comp & (df["vix"] < 35) & base,
    "A1 NEUT in[43-55]": base & (df.regime == "NORMAL") & (df.trend == "BULLISH")
                         & (df.iv_signal == "NEUTRAL") & (df.ivp >= 43) & (df.ivp <= 55),
    "A1 NEUT mid(55-70]": base & (df.regime == "NORMAL") & (df.trend == "BULLISH")
                          & (df.iv_signal == "NEUTRAL") & (df.ivp > 55) & (df.ivp <= 70),
}

def run(mask, so, lo):
    mv = mask.to_numpy()
    tr, i = [], 0
    while i < len(dates) - 15:
        if not mv[i]:
            i += 1; continue
        S0, v0 = close[i], vix[i]
        ks, kl = kfor(S0, DTE, v0/100, 0.30), kfor(S0, DTE, v0/100, 0.15)
        credit = pput(S0, ks, DTE, (v0+so)/100) - pput(S0, kl, DTE, (v0+lo)/100)
        if credit <= 0 or ks <= kl:
            i += 1; continue
        j = i
        while j < len(dates) - 1:
            j += 1
            dr = max(DTE - (dates[j] - dates[i]).days, 1)
            cost = pput(close[j], ks, dr, (vix[j]+so)/100) - pput(close[j], kl, dr, (vix[j]+lo)/100)
            if cost >= STOP_X * credit or dr <= EXIT_DTE:
                break
        tr.append((dates[i], S0, (credit - cost) * 100 - COST))
        i = j + 1
    return pd.DataFrame(tr, columns=["date", "spx", "pnl"])

spx_ref, yrs = close[-1], 26.5
print(f"{'arm':<20} {'scen':<13} {'n':>4} {'mean$':>7} {'net$/yr':>8} {'2024+':>10} {'2025+':>10}")
for arm, mask in MASKS.items():
    for scen, (so, lo) in SCEN.items():
        t = run(mask, so, lo)
        if not len(t):
            continue
        netyr = (t.pnl * spx_ref / t.spx).sum() / yrs
        w24 = t[t.date >= "2024-01-01"]; w25 = t[t.date >= "2025-01-01"]
        f24 = f"{w24.pnl.mean():>+6.0f}x{len(w24):<2}" if len(w24) else "   —"
        f25 = f"{w25.pnl.mean():>+6.0f}x{len(w25):<2}" if len(w25) else "   —"
        print(f"{arm:<20} {scen:<13} {len(t):>4} {t.pnl.mean():>7.0f} {netyr:>8,.0f} {f24:>10} {f25:>10}")
    print()
