"""
Q065 P1 — Inventory of aftermath candidate days blocked by VIX ≥ 40 threshold
2026-05-12

Identify all historical days that would have been is_aftermath=True except for
the `vix < EXTREME_VIX (40)` guard. Tag these days with proximity to existing
raw aftermath windows, and characterize the events.

Reuses VIX data and 10-day peak logic from q064/q064_p1_aftermath_windows.py.
"""

import os
import sys
import pandas as pd
import numpy as np
import yfinance as yf

# ── Parameters (mirror selector.py) ────────────────────────────────────────
AFTERMATH_PEAK_VIX_10D_MIN = 28.0
AFTERMATH_OFF_PEAK_PCT     = 0.10
EXTREME_VIX                = 40.0
LOOKBACK_DAYS              = 10

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 1. Load VIX ─────────────────────────────────────────────────────────────
print("Downloading VIX history...")
raw = yf.download("^VIX", start="2006-01-01", end="2026-05-13",
                  auto_adjust=False, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
vix_series = raw["Close"].dropna().sort_index()
vix_series.index = pd.to_datetime(vix_series.index).tz_localize(None)
vix_series = vix_series[vix_series.index >= "2007-01-01"]
print(f"  VIX range: {vix_series.index[0].date()} → {vix_series.index[-1].date()}"
      f"  ({len(vix_series)} trading days)")

vix_arr = vix_series.values
dates   = vix_series.index.to_list()
n       = len(vix_arr)

# ── 2. Per-day classification ──────────────────────────────────────────────
# We classify each day as one of:
#   raw_aftermath          : passes all three rules (current production)
#   blocked_by_extreme     : passes peak/off-peak rules BUT vix >= 40
#   else                   : not aftermath
rows = []
for i in range(n):
    lo = max(0, i - LOOKBACK_DAYS + 1)
    peak = float(np.max(vix_arr[lo : i + 1]))
    v    = float(vix_arr[i])
    peak_ok    = peak >= AFTERMATH_PEAK_VIX_10D_MIN
    offpeak_ok = v <= peak * (1.0 - AFTERMATH_OFF_PEAK_PCT)
    extreme    = v >= EXTREME_VIX

    if peak_ok and offpeak_ok and not extreme:
        status = "raw_aftermath"
    elif peak_ok and offpeak_ok and extreme:
        status = "blocked_by_extreme"
    else:
        status = "none"

    off_peak_pct = (1.0 - v / peak) * 100 if peak > 0 else 0.0
    rows.append({
        "date": dates[i], "vix": v, "peak_10d": peak,
        "off_peak_%": off_peak_pct, "status": status,
    })

df = pd.DataFrame(rows)

n_raw    = (df["status"] == "raw_aftermath").sum()
n_block  = (df["status"] == "blocked_by_extreme").sum()
print(f"\n  raw_aftermath days       : {n_raw}")
print(f"  blocked_by_extreme days  : {n_block}")
print(f"  total candidate days     : {n_raw + n_block}")
print(f"  block rate (of cands)    : {n_block / (n_raw + n_block) * 100:.1f}%")

# ── 3. For each blocked day, find distance to nearest raw_aftermath day ────
raw_dates = df.loc[df["status"] == "raw_aftermath", "date"].to_list()
raw_set   = set(raw_dates)

def nearest_raw_gap(d):
    """Trading-day distance to nearest raw_aftermath day (signed)."""
    # Use index positions instead of calendar days
    idx_d = df.index[df["date"] == d][0]
    raw_idx = df.index[df["status"] == "raw_aftermath"].to_numpy()
    if len(raw_idx) == 0:
        return None, None
    diffs = raw_idx - idx_d
    nearest = diffs[np.argmin(np.abs(diffs))]
    nearest_raw_idx = idx_d + nearest
    return int(nearest), df.iloc[nearest_raw_idx]["date"]

blocked = df[df["status"] == "blocked_by_extreme"].copy()
gaps, neighbor_dates = [], []
for d in blocked["date"]:
    g, nd = nearest_raw_gap(d)
    gaps.append(g); neighbor_dates.append(nd)
blocked["gap_to_nearest_raw_TD"] = gaps
blocked["nearest_raw_date"] = neighbor_dates

# ── 4. Event clustering (group consecutive blocked days + close to raw) ───
# A "blocked cluster" = contiguous blocked days OR blocked days within 3 TD
# of a raw_aftermath day (i.e., the cases the user flagged as noise)
blocked_sorted = blocked.sort_values("date").reset_index(drop=True)
blocked_sorted["abs_gap"] = blocked_sorted["gap_to_nearest_raw_TD"].abs()
blocked_sorted["close_to_raw"] = blocked_sorted["abs_gap"] <= 3

# ── 5. Print summary tables ─────────────────────────────────────────────────
print(f"\n  ── Blocked days within 3 TD of a raw_aftermath day (noise candidates) ──")
noise = blocked_sorted[blocked_sorted["close_to_raw"]].copy()
print(f"  Count: {len(noise)} / {len(blocked_sorted)} blocked days")
if len(noise) > 0:
    print(noise[["date", "vix", "peak_10d", "off_peak_%",
                 "gap_to_nearest_raw_TD", "nearest_raw_date"]].to_string(index=False))

print(f"\n  ── All blocked days by year ──")
blocked_sorted["year"] = pd.to_datetime(blocked_sorted["date"]).dt.year
year_summary = blocked_sorted.groupby("year").agg(
    blocked_days=("date", "count"),
    vix_max=("vix", "max"),
    vix_median=("vix", "median"),
    avg_off_peak_pct=("off_peak_%", "mean"),
    n_close_to_raw=("close_to_raw", "sum"),
)
print(year_summary.to_string())

# ── 6. Save outputs ─────────────────────────────────────────────────────────
out_blocked = os.path.join(OUT_DIR, "q065_p1_blocked_days.csv")
blocked_out = blocked_sorted.copy()
blocked_out["date"] = pd.to_datetime(blocked_out["date"]).dt.strftime("%Y-%m-%d")
blocked_out["nearest_raw_date"] = pd.to_datetime(blocked_out["nearest_raw_date"]).dt.strftime("%Y-%m-%d")
blocked_out.to_csv(out_blocked, index=False)
print(f"\n  Saved: {out_blocked}")

out_daily = os.path.join(OUT_DIR, "q065_p1_classified_daily.csv")
df_out = df.copy()
df_out["date"] = pd.to_datetime(df_out["date"]).dt.strftime("%Y-%m-%d")
df_out.to_csv(out_daily, index=False)
print(f"  Saved: {out_daily}")

print("\n[P1 done]")
