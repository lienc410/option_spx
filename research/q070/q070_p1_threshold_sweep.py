"""
Q070 P1 — Aftermath Peak VIX Threshold Sensitivity Sweep
2026-05-13

对 threshold in {22, 24, 25, 26, 27, 28} 重新跑 is_aftermath() 逻辑，
统计每个 threshold 的 aftermath 天数、window 数、新增 window 及其 entry VIX 分布。

数据来源：research/q064/q064_p1_daily_flags.csv（已有 vix / vix_peak_10d 字段）
参数：
  AFTERMATH_OFF_PEAK_PCT = 0.10
  EXTREME_VIX            = 40.0
  LOW_VOL threshold      = 22.0  (entry_vix < 22 → LOW_VOL，aftermath 对 BPS HV 无效)
"""

import os
import sys
import pandas as pd
import numpy as np

# ── 路径 ─────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY_CSV  = os.path.join(BASE_DIR, "q064", "q064_p1_daily_flags.csv")
OUT_DIR    = os.path.dirname(os.path.abspath(__file__))

AFTERMATH_OFF_PEAK_PCT = 0.10
EXTREME_VIX            = 40.0
LOW_VOL_THRESHOLD      = 22.0
BASELINE_THRESHOLD     = 28.0

THRESHOLDS = [22, 24, 25, 26, 27, 28]

# ── 1. 读取日线数据 ────────────────────────────────────────────────────────────
print("Loading daily flags...")
df = pd.read_csv(DAILY_CSV, parse_dates=["date"])
df = df.sort_values("date").reset_index(drop=True)
print(f"  Rows: {len(df)}  ({df['date'].iloc[0].date()} → {df['date'].iloc[-1].date()})")

# ── 2. 定义 is_aftermath 函数（参数化 threshold）────────────────────────────
def compute_aftermath(df: pd.DataFrame, min_peak: float) -> pd.Series:
    """返回 is_aftermath bool 序列，只改 min_peak（其余参数固定）"""
    peak = df["vix_peak_10d"].values
    vix  = df["vix"].values
    flag = (
        (peak >= min_peak) &
        (vix <= peak * (1.0 - AFTERMATH_OFF_PEAK_PCT)) &
        (vix < EXTREME_VIX)
    )
    return pd.Series(flag, index=df.index)


def extract_windows(df: pd.DataFrame, flag_col: str) -> pd.DataFrame:
    """从 bool 列提取独立 aftermath window 列表"""
    windows = []
    in_window  = False
    win_start  = None
    win_peak   = None
    win_entry  = None
    last_idx   = None

    for idx, row in df.iterrows():
        is_af = row[flag_col]
        if is_af and not in_window:
            in_window  = True
            win_start  = row["date"]
            win_peak   = row["vix_peak_10d"]
            win_entry  = row["vix"]
            last_idx   = idx
        elif is_af and in_window:
            win_peak   = max(win_peak, row["vix_peak_10d"])
            last_idx   = idx
        elif not is_af and in_window:
            end_date   = df.loc[last_idx, "date"]
            windows.append({
                "start_date":     win_start,
                "end_date":       end_date,
                "peak_vix":       win_peak,
                "entry_vix":      win_entry,
                "duration_days":  (end_date - win_start).days + 1,
            })
            in_window  = False

    if in_window:
        end_date = df.loc[last_idx, "date"]
        windows.append({
            "start_date":     win_start,
            "end_date":       end_date,
            "peak_vix":       win_peak,
            "entry_vix":      win_entry,
            "duration_days":  (end_date - win_start).days + 1,
        })

    return pd.DataFrame(windows) if windows else pd.DataFrame(
        columns=["start_date", "end_date", "peak_vix", "entry_vix", "duration_days"]
    )


# ── 3. 基准 threshold=28 windows ─────────────────────────────────────────────
df["is_af_28"] = compute_aftermath(df, BASELINE_THRESHOLD)
baseline_windows = extract_windows(df, "is_af_28")
baseline_days    = df["is_af_28"].sum()

# baseline window 日期集合（用于识别"新增"）
baseline_start_set = set(baseline_windows["start_date"].dt.strftime("%Y-%m-%d"))

print(f"\nBaseline (threshold=28):")
print(f"  Aftermath days   : {baseline_days}  ({baseline_days/len(df)*100:.1f}%)")
print(f"  Independent windows: {len(baseline_windows)}")

# ── 4. 对每个 threshold 跑 sweep ──────────────────────────────────────────────
results = []
all_new_windows = []

for thr in THRESHOLDS:
    col = f"is_af_{thr}"
    df[col] = compute_aftermath(df, float(thr))
    af_days = df[col].sum()
    windows = extract_windows(df, col)

    # 新增 window（start_date 不在 baseline 中）
    if thr < BASELINE_THRESHOLD:
        new_wins = windows[
            ~windows["start_date"].dt.strftime("%Y-%m-%d").isin(baseline_start_set)
        ].copy()
    else:
        new_wins = pd.DataFrame(
            columns=["start_date", "end_date", "peak_vix", "entry_vix", "duration_days"]
        )

    n_new         = len(new_wins)
    n_total_wins  = len(windows)

    # 新增 window entry VIX 统计
    if n_new > 0:
        ev = new_wins["entry_vix"]
        low_vol_n   = (ev < LOW_VOL_THRESHOLD).sum()
        low_vol_pct = low_vol_n / n_new * 100
        ev_median   = ev.median()
        ev_p25      = ev.quantile(0.25)
        ev_p75      = ev.quantile(0.75)
        pv_median   = new_wins["peak_vix"].median()
        pv_p25      = new_wins["peak_vix"].quantile(0.25)
        pv_p75      = new_wins["peak_vix"].quantile(0.75)
    else:
        low_vol_n   = 0
        low_vol_pct = 0.0
        ev_median   = ev_p25 = ev_p75 = np.nan
        pv_median   = pv_p25 = pv_p75 = np.nan

    results.append({
        "threshold":          thr,
        "af_days":            int(af_days),
        "af_pct":             round(af_days / len(df) * 100, 2),
        "n_windows":          n_total_wins,
        "n_new_windows":      n_new,
        "new_win_peak_p25":   round(pv_p25, 2) if not np.isnan(pv_p25) else "",
        "new_win_peak_med":   round(pv_median, 2) if not np.isnan(pv_median) else "",
        "new_win_peak_p75":   round(pv_p75, 2) if not np.isnan(pv_p75) else "",
        "new_win_entry_p25":  round(ev_p25, 2) if not np.isnan(ev_p25) else "",
        "new_win_entry_med":  round(ev_median, 2) if not np.isnan(ev_median) else "",
        "new_win_entry_p75":  round(ev_p75, 2) if not np.isnan(ev_p75) else "",
        "low_vol_new_n":      int(low_vol_n),
        "low_vol_new_pct":    round(low_vol_pct, 1),
    })

    # 收集新增 window 详情（带 threshold 标签）
    if n_new > 0:
        new_wins = new_wins.copy()
        new_wins["threshold"] = thr
        all_new_windows.append(new_wins)

    # 打印
    print(f"\nThreshold = {thr}:")
    print(f"  Aftermath days   : {af_days}  ({af_days/len(df)*100:.1f}%)")
    print(f"  Total windows    : {n_total_wins}")
    print(f"  New windows vs 28: {n_new}")
    if n_new > 0:
        print(f"  New win entry VIX: med={ev_median:.2f}  p25={ev_p25:.2f}  p75={ev_p75:.2f}")
        print(f"  New win peak VIX : med={pv_median:.2f}  p25={pv_p25:.2f}  p75={pv_p75:.2f}")
        print(f"  LOW_VOL entry (<22): {low_vol_n}/{n_new}  ({low_vol_pct:.1f}%)")

# ── 5. 输出 CSV ───────────────────────────────────────────────────────────────
df_results = pd.DataFrame(results)
out_results = os.path.join(OUT_DIR, "q070_p1_results.csv")
df_results.to_csv(out_results, index=False)
print(f"\nSaved: {out_results}")

# 新增 window 合并列表
if all_new_windows:
    df_new_all = pd.concat(all_new_windows, ignore_index=True)
    for col in ["start_date", "end_date"]:
        df_new_all[col] = pd.to_datetime(df_new_all[col]).dt.strftime("%Y-%m-%d")
    df_new_all = df_new_all.sort_values(["threshold", "start_date"]).reset_index(drop=True)
    out_new = os.path.join(OUT_DIR, "q070_p1_new_windows.csv")
    df_new_all.to_csv(out_new, index=False)
    print(f"Saved: {out_new}  ({len(df_new_all)} rows)")
else:
    print("No new windows found across all thresholds.")

print("\n[P1 done]")
