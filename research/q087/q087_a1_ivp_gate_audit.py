"""Q087 Track-A #1 — IVP dual-gate audit (general 40-70, NNB 43-55).

Question: in cell-approved BPS lanes (NORMAL x BULLISH x iv_signal HIGH/
NEUTRAL), do the IVP bands select trade QUALITY, or only throttle FREQUENCY?

Pre-registered design (no cutpoint scanning):
  Strata  : per lane, below-band / in-band (incumbent) / above-band at the
            EXISTING boundaries only.
  Endpoint: trade-level BPS counterfactual (30 DTE d.30/.15, 21 DTE exit,
            3x stop, CALIB chain-calibrated sigma, $130 RT costs) — the
            Q085 P3 machinery, new-protocol native.
  Inference: Welch-studentized stratum-vs-in-band comparison.
  Eras    : full / worst-7y / 2020+ / 2024+ (adaptive-posture presentation).
  Reforms (3 discrete candidates, pre-registered):
    R1 harmonize: NNB 43-55 -> general 40-70 (kill the special case)
    R2 drop upper bound (keep lower 40/43)
    R3 cell-routing only (drop both IVP bounds)
Forward note: IVP-blocked oversold days overlap SPEC-116 S2 sleeve universe;
any reform SPEC must re-state that sleeve's universe.
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
dates, close, vix = df.index, C.to_numpy(), df["vix"].to_numpy()
base = (df.index >= "2000-01-01") & B.default_valid & df["vix"].notna() & df["ivp"].notna()

# lanes and strata at EXISTING boundaries
lane_high = base & (df.regime == "NORMAL") & (df.trend == "BULLISH") & (df.iv_signal == "HIGH")
lane_neut = base & (df.regime == "NORMAL") & (df.trend == "BULLISH") & (df.iv_signal == "NEUTRAL")
ivp = df["ivp"]
STRATA = {
    "HIGH  below(<=40)":  lane_high & (ivp <= 40),
    "HIGH  in(40-70]":    lane_high & (ivp > 40) & (ivp <= 70),
    "HIGH  above(>70)":   lane_high & (ivp > 70),
    "NEUT  below(<43)":   lane_neut & (ivp < 43),
    "NEUT  in[43-55]":    lane_neut & (ivp >= 43) & (ivp <= 55),
    "NEUT  mid(55-70]":   lane_neut & (ivp > 55) & (ivp <= 70),   # NNB-blocked, general-band-OK
    "NEUT  above(>70)":   lane_neut & (ivp > 70),
}

def run_bps(mask):
    mv = mask.to_numpy()
    tr, i = [], 0
    while i < len(dates) - 15:
        if not mv[i]:
            i += 1; continue
        S0, v0 = close[i], vix[i]
        ks, kl = kfor(S0, DTE, v0/100, 0.30), kfor(S0, DTE, v0/100, 0.15)
        credit = pput(S0, ks, DTE, v0/100 - 0.02) - pput(S0, kl, DTE, v0/100 + 0.01)
        if credit <= 0 or ks <= kl:
            i += 1; continue
        j = i
        while j < len(dates) - 1:
            j += 1
            dr = max(DTE - (dates[j] - dates[i]).days, 1)
            cost = pput(close[j], ks, dr, vix[j]/100 - 0.02) - pput(close[j], kl, dr, vix[j]/100 + 0.01)
            if cost >= STOP_X * credit or dr <= EXIT_DTE:
                break
        tr.append((dates[i], S0, (credit - cost) * 100 - COST, close[j] < ks))
        i = j + 1
    return pd.DataFrame(tr, columns=["date", "spx", "pnl", "breach"])

spx_ref, yrs = close[-1], 26.5

def welch_p(a, b, rngseed=20260706, n_perm=0):
    # plain Welch t + normal approx p (trade PnLs, non-overlapping -> serial corr minimal)
    se = math.sqrt(a.var(ddof=1)/len(a) + b.var(ddof=1)/len(b))
    t = (a.mean() - b.mean()) / se if se > 0 else 0.0
    from math import erf, sqrt
    p = 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))
    return t, p

def era_mean(t, lo, hi=None):
    w = t[(t.date >= lo) & ((t.date < hi) if hi else True)]
    return (len(w), w.pnl.mean() if len(w) else float("nan"))

print(f"{'stratum':<18} {'days':>5} {'n_tr':>5} {'tr/yr':>5} {'win%':>5} {'mean$':>7} "
      f"{'brch%':>6} {'net$/yr':>8} {'worst7y':>8} {'2020+':>7} {'2024+':>7} {'t_vs_in':>7} {'p':>7}")
results = {}
for lane, in_key in (("HIGH", "HIGH  in(40-70]"), ("NEUT", "NEUT  in[43-55]")):
    t_in = run_bps(STRATA[in_key]); results[in_key] = t_in
    for name, mask in STRATA.items():
        if not name.startswith(lane):
            continue
        t = results[name] if name in results else run_bps(mask)
        results[name] = t
        if not len(t):
            print(f"{name:<18} {int(mask.sum()):>5}     0"); continue
        w7 = min((era_mean(t, st, st + pd.DateOffset(years=7))[1]
                  for st in pd.date_range("2000-01-01", "2019-07-01", freq="6MS")
                  if era_mean(t, st, st + pd.DateOffset(years=7))[0] >= 8), default=float("nan"))
        n20, m20 = era_mean(t, pd.Timestamp("2020-01-01"))
        n24, m24 = era_mean(t, pd.Timestamp("2024-01-01"))
        netyr = (t.pnl * spx_ref / t.spx).sum() / yrs
        if name == in_key:
            tt, pp_ = 0.0, 1.0
        else:
            tt, pp_ = welch_p(t.pnl, t_in.pnl) if len(t) >= 8 and len(t_in) >= 8 else (float("nan"),)*2
        print(f"{name:<18} {int(mask.sum()):>5} {len(t):>5} {len(t)/yrs:>5.1f} "
              f"{100*(t.pnl>0).mean():>4.0f}% {t.pnl.mean():>7.0f} {100*t.breach.mean():>5.1f}% "
              f"{netyr:>8,.0f} {w7:>8.0f} {m20:>7.0f} {m24:>7.0f} {tt:>7.2f} {pp_:>7.3f}")

# Reforms: R1 harmonize NNB->40-70; R2 drop upper; R3 cell-only
print("\nreform packages (added days vs incumbent, CALIB+costs, today-scale):")
inc_mask = STRATA["HIGH  in(40-70]"] | STRATA["NEUT  in[43-55]"]
R1 = inc_mask | (lane_neut & (ivp > 40) & (ivp <= 70))
R2 = (lane_high & (ivp > 40)) | (lane_neut & (ivp >= 43))
R3 = lane_high | lane_neut
t_inc = run_bps(inc_mask)
for name, m in (("R1 harmonize", R1), ("R2 drop-upper", R2), ("R3 cell-only", R3)):
    t = run_bps(m)
    add_days = int(m.sum() - inc_mask.sum())
    netyr = (t.pnl * spx_ref / t.spx).sum() / yrs
    inc_netyr = (t_inc.pnl * spx_ref / t_inc.spx).sum() / yrs
    n24, m24 = era_mean(t, pd.Timestamp("2024-01-01"))
    w7 = min((era_mean(t, st, st + pd.DateOffset(years=7))[1]
              for st in pd.date_range("2000-01-01", "2019-07-01", freq="6MS")
              if era_mean(t, st, st + pd.DateOffset(years=7))[0] >= 8), default=float("nan"))
    print(f"  {name:<14} +{add_days:>4} days  n_tr {len(t):>4} ({len(t)/yrs:.1f}/yr vs {len(t_inc)/yrs:.1f})  "
          f"net ${netyr:,.0f}/yr (vs ${inc_netyr:,.0f})  worst7y ${w7:,.0f}  2024+ ${m24:,.0f}x{n24}")
