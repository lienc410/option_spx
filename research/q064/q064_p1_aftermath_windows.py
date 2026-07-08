"""
Q064 P1 — Aftermath Window Extraction
2026-05-11

完全复现 strategy/selector.py 的 is_aftermath() 逻辑，扫描 2007-2026 VIX 日线数据，
识别所有 aftermath 窗口，输出统计和 CSV。

参数（与 selector.py 一致）：
  AFTERMATH_PEAK_VIX_10D_MIN = 28.0
  AFTERMATH_OFF_PEAK_PCT     = 0.10
  EXTREME_VIX                = 40.0
  LOOKBACK_DAYS              = 10   (trading days, 含当日)
"""

import os
import sys
import pandas as pd
import numpy as np
import yfinance as yf

# ── 参数 ─────────────────────────────────────────────────────────────────────
AFTERMATH_PEAK_VIX_10D_MIN = 28.0
AFTERMATH_OFF_PEAK_PCT     = 0.10
EXTREME_VIX                = 40.0
LOOKBACK_DAYS              = 10

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 1. 下载 VIX 全历史 ────────────────────────────────────────────────────────
# End date was hard-coded "2026-05-12" (the original one-shot research run) —
# that froze the whole q064→q072 flags chain at 5/11 and the Gov BT page
# missed the June VIX-22 episode. Rolling end since the chain went on a
# weekly cron (scripts/refresh_regime_flags.py, PM 2026-07-07 option B).
from datetime import date as _date, timedelta as _td
_END = (_date.today() + _td(days=1)).isoformat()
print(f"Downloading VIX history (max, → {_END})...")
raw = yf.download("^VIX", start="2006-01-01", end=_END, auto_adjust=False, progress=False)

# flatten multi-index if present
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)

vix = raw["Close"].dropna().sort_index()
vix.index = pd.to_datetime(vix.index).tz_localize(None)

# 截取 2007-01-01 起（策略 backtest 起点）；end 随 cron 滚动
vix = vix[vix.index >= "2007-01-01"]
print(f"VIX range: {vix.index[0].date()} → {vix.index[-1].date()}  ({len(vix)} trading days)")

# ── 2. 逐日计算 is_aftermath ───────────────────────────────────────────────
vix_arr  = vix.values
dates    = vix.index.to_list()
n        = len(vix_arr)

is_aftermath_list = []
peak_10d_list     = []

for i in range(n):
    lo = max(0, i - LOOKBACK_DAYS + 1)
    peak = float(np.max(vix_arr[lo : i + 1]))
    v    = float(vix_arr[i])
    flag = (
        peak >= AFTERMATH_PEAK_VIX_10D_MIN
        and v <= peak * (1.0 - AFTERMATH_OFF_PEAK_PCT)
        and v < EXTREME_VIX
    )
    is_aftermath_list.append(flag)
    peak_10d_list.append(peak)

df_daily = pd.DataFrame({
    "date":          dates,
    "vix":           vix_arr,
    "vix_peak_10d":  peak_10d_list,
    "is_aftermath":  is_aftermath_list,
})

total_days       = len(df_daily)
aftermath_days   = df_daily["is_aftermath"].sum()
pct_of_all       = aftermath_days / total_days * 100

print(f"\nTotal trading days:   {total_days}")
print(f"Aftermath days:       {aftermath_days}  ({pct_of_all:.1f}%)")

# ── 3. 识别独立 window（连续 aftermath 天数为一个 window）────────────────────
windows = []
in_window   = False
win_start   = None
win_peak    = None
win_entry   = None   # VIX at first day of window

for _, row in df_daily.iterrows():
    if row["is_aftermath"] and not in_window:
        in_window  = True
        win_start  = row["date"]
        win_peak   = row["vix_peak_10d"]
        win_entry  = row["vix"]
    elif row["is_aftermath"] and in_window:
        win_peak = max(win_peak, row["vix_peak_10d"])
    elif not row["is_aftermath"] and in_window:
        windows.append({
            "start_date": win_start,
            "end_date":   last_date,
            "peak_vix":   win_peak,
            "entry_vix":  win_entry,
            "duration_days": (last_date - win_start).days + 1,
        })
        in_window = False

    if row["is_aftermath"]:
        last_date = row["date"]

# close final window if still open
if in_window:
    windows.append({
        "start_date": win_start,
        "end_date":   last_date,
        "peak_vix":   win_peak,
        "entry_vix":  win_entry,
        "duration_days": (last_date - win_start).days + 1,
    })

df_windows = pd.DataFrame(windows)
print(f"\nIndependent aftermath windows: {len(df_windows)}")

# ── 4. VIX 分布统计（aftermath 期间）──────────────────────────────────────────
af_vix = df_daily.loc[df_daily["is_aftermath"], "vix"]
print(f"\nVIX distribution during aftermath windows:")
print(f"  Median : {af_vix.median():.2f}")
print(f"  P25    : {af_vix.quantile(0.25):.2f}")
print(f"  P75    : {af_vix.quantile(0.75):.2f}")
print(f"  Min    : {af_vix.min():.2f}")
print(f"  Max    : {af_vix.max():.2f}")

# ── 5. Window 列表打印 ─────────────────────────────────────────────────────────
print(f"\n{'#':>3}  {'Start':12} {'End':12} {'Peak VIX':>9} {'Entry VIX':>10} {'Days':>5}")
print("-" * 58)
for i, w in df_windows.iterrows():
    print(f"{i+1:>3}  {str(w['start_date'].date()):12} {str(w['end_date'].date()):12} "
          f"{w['peak_vix']:>9.2f} {w['entry_vix']:>10.2f} {w['duration_days']:>5}")

# ── 6. 输出 CSV ───────────────────────────────────────────────────────────────
out_windows = os.path.join(OUT_DIR, "q064_p1_windows.csv")
df_windows_out = df_windows.copy()
df_windows_out["start_date"] = df_windows_out["start_date"].dt.strftime("%Y-%m-%d")
df_windows_out["end_date"]   = df_windows_out["end_date"].dt.strftime("%Y-%m-%d")
df_windows_out.to_csv(out_windows, index=False)
print(f"\nSaved: {out_windows}")

# also save daily flags (used by P2)
out_daily = os.path.join(OUT_DIR, "q064_p1_daily_flags.csv")
df_daily_out = df_daily.copy()
df_daily_out["date"] = df_daily_out["date"].dt.strftime("%Y-%m-%d")
df_daily_out.to_csv(out_daily, index=False)
print(f"Saved: {out_daily}")

print("\n[P1 done]")
