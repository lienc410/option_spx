"""Q085 P3b — era-conditional analysis, EXECUTABLE form (review C6 fix).

Includes the honest start-year ladder demanded by review C2: the "2024+"
window is a scanned start date; the full ladder shows calendar 2023 and
2024 are NEGATIVE for BPS-CALIB and the recent-era case is driven by
2025-26 trades. Primary era evidence is the model-free S6-MES event stream.

PM posture ratification (2026-07-04) and scope boundary recorded in
feedback_adaptive_posture_no_allweather_gate (memory) and the G-review packet.
"""
from __future__ import annotations
import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
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
df["strategy_key"] = sig["strategy_key"].reindex(df.index)
df["regime"] = sig["regime"].reindex(df.index)
allowed = df["strategy_key"].fillna("") != ""
comp = (B.SIGNALS["F3_rsi2_os"] | B.SIGNALS["F3_down3"]).fillna(False)
dates, close, vix = df.index, C.to_numpy(), df["vix"].to_numpy()

# --- S6-MES event stream (model-free primary evidence) ---
ibs = ((C - B.L) / (B.H - B.L)).to_numpy()
ok6 = (comp & (df["vix"] < 35) & (df.index >= "2000-01-01") & B.default_valid).to_numpy()
ev, i = [], 0
while i < len(dates) - 11:
    if not ok6[i]:
        i += 1; continue
    j = i + 10
    for k in range(i + 1, i + 11):
        if ibs[k] > 0.8:
            j = k; break
    ev.append((dates[i], (close[j] - close[i]) * 5 - 3.6))
    i = j + 1
mes = pd.DataFrame(ev, columns=["date", "pnl"])

# --- BPS challenger @ CALIB + costs ---
mask = ((~allowed) & (df.regime == "NORMAL") & comp & (df["vix"] < 35)
        & (df.index >= "2000-01-01") & B.default_valid).to_numpy()
tr, i = [], 0
while i < len(dates) - 15:
    if not mask[i]:
        i += 1; continue
    S0, v0 = close[i], vix[i]
    ks, kl = kfor(S0, DTE, v0 / 100, 0.30), kfor(S0, DTE, v0 / 100, 0.15)
    credit = pput(S0, ks, DTE, v0 / 100 - 0.02) - pput(S0, kl, DTE, v0 / 100 + 0.01)
    if credit <= 0 or ks <= kl:
        i += 1; continue
    j = i
    while j < len(dates) - 1:
        j += 1
        dr = max(DTE - (dates[j] - dates[i]).days, 1)
        cost = pput(close[j], ks, dr, vix[j] / 100 - 0.02) - pput(close[j], kl, dr, vix[j] / 100 + 0.01)
        if cost >= STOP_X * credit or dr <= EXIT_DTE:
            break
    tr.append((dates[i], (credit - cost) * 100 - COST))
    i = j + 1
bps = pd.DataFrame(tr, columns=["date", "pnl"])

def wstats(t, lo):
    w = t[t.date >= lo]
    return len(w), (w.pnl.mean() if len(w) else float("nan"))

print("=== primary evidence: S6-MES stream (no pricing model, per contract) ===")
for lo in ("2000-01-01", "2020-01-01", "2022-01-01", "2024-01-01", "2025-01-01"):
    n, m = wstats(mes, lo)
    print(f"  {lo[:4]}+ n={n:>3} mean ${m:>7,.0f}")

print("\n=== BPS-CALIB start-year ladder (review C2: full ladder, no cherry-pick) ===")
for y in range(2019, 2026):
    w = bps[bps.date >= f"{y}-01-01"]
    if len(w) >= 5:
        se = w.pnl.std(ddof=1) / math.sqrt(len(w))
        print(f"  {y}+ : n={len(w):>3} mean ${w.pnl.mean():>7,.0f}  t={w.pnl.mean()/se:+.2f}")
print("  calendar years:")
for y in range(2022, 2027):
    w = bps[(bps.date >= f"{y}-01-01") & (bps.date < f"{y+1}-01-01")]
    if len(w):
        print(f"  {y}  : n={len(w):>3} mean ${w.pnl.mean():>7,.0f}")

print("\n=== corrected risk numbers (review C1) ===")
worst7 = min(bps[(bps.date >= st) & (bps.date < st + pd.DateOffset(years=7))].pnl.mean()
             for st in pd.date_range("2000-01-01", "2019-07-01", freq="6MS")
             if len(bps[(bps.date >= st) & (bps.date < st + pd.DateOffset(years=7))]) >= 8)
print(f"  BPS-CALIB worst-7y era mean: ${worst7:,.0f}/trade")
worst_win = bps[(bps.date >= "2014-07-01") & (bps.date < "2021-07-01")].pnl.to_numpy()
rng = np.random.default_rng(20260704)
sims = np.array([rng.choice(worst_win, 10, replace=True).sum() for _ in range(4000)])
print(f"  degradation tuition (10 events @ worst era): mean ${sims.mean():,.0f}, "
      f"p5 ${np.percentile(sims, 5):,.0f}; detection lag ~{10 / (len(bps) / 26.5):.1f} yrs at avg frequency")
