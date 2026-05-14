"""
Q070 P2 — BPS HV Trade Attribution by Threshold
2026-05-13

从 baseline_19y_trades.csv 取 Bull Put Spread (High Vol) 28 笔，
对每个 threshold 重新打 is_aftermath 标签，识别新增 aftermath trades，
并报告其 P&L 质量指标。

对比基准：Q064 P2 threshold=28 组的 aftermath trades（n=15，avg $2,140，WR 86.7%）

数据来源：
  - research/q042/baseline_19y_trades.csv
  - research/q064/q064_p1_daily_flags.csv（含 vix / vix_peak_10d）
"""

import os
import pandas as pd
import numpy as np

# ── 路径 ─────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRADES_CSV  = os.path.join(BASE_DIR, "q042", "baseline_19y_trades.csv")
DAILY_CSV   = os.path.join(BASE_DIR, "q064", "q064_p1_daily_flags.csv")
OUT_DIR     = os.path.dirname(os.path.abspath(__file__))

AFTERMATH_OFF_PEAK_PCT = 0.10
EXTREME_VIX            = 40.0
BASELINE_THRESHOLD     = 28.0
THRESHOLDS             = [22, 24, 25, 26, 27, 28]

HOLD_DAYS_ASSUMPTION   = 21   # 用于 $/BP-day 估算（BPS HV 典型持仓 ~21d）

# ── 1. 读取数据 ────────────────────────────────────────────────────────────────
print("Loading data...")
df_trades = pd.read_csv(TRADES_CSV, parse_dates=["entry_date", "exit_date"])
df_daily  = pd.read_csv(DAILY_CSV, parse_dates=["date"])
df_daily  = df_daily.sort_values("date").reset_index(drop=True)

# 只保留 BPS HV
bps_hv = df_trades[df_trades["strategy"] == "Bull Put Spread (High Vol)"].copy()
bps_hv = bps_hv.sort_values("entry_date").reset_index(drop=True)
print(f"  BPS HV trades total: {len(bps_hv)}")

# ── 2. 为日线数据计算每个 threshold 的 is_aftermath ──────────────────────────
def compute_aftermath_series(df: pd.DataFrame, min_peak: float) -> pd.Series:
    peak = df["vix_peak_10d"].values
    vix  = df["vix"].values
    flag = (
        (peak >= min_peak) &
        (vix <= peak * (1.0 - AFTERMATH_OFF_PEAK_PCT)) &
        (vix < EXTREME_VIX)
    )
    return pd.Series(flag, index=df.index)


# 建立 date → is_aftermath dict 方便 lookup
af_lookup = {}
for thr in THRESHOLDS:
    s = compute_aftermath_series(df_daily, float(thr))
    af_lookup[thr] = dict(zip(df_daily["date"].dt.strftime("%Y-%m-%d"), s.values))

# ── 3. 对每笔 BPS HV trade 打 is_aftermath 标签（用 entry_date 查） ──────────
for thr in THRESHOLDS:
    col = f"is_af_{thr}"
    bps_hv[col] = bps_hv["entry_date"].dt.strftime("%Y-%m-%d").map(af_lookup[thr]).fillna(False)

# ── 4. 基准组（threshold=28）的 aftermath trades ──────────────────────────────
def trade_stats(trades: pd.DataFrame, label: str) -> dict:
    n       = len(trades)
    if n == 0:
        return {"label": label, "n": 0, "win_rate": None, "avg_pnl": None,
                "median_pnl": None, "worst_pnl": None, "dollar_bp_day": None}
    wins    = (trades["exit_pnl"] > 0).sum()
    avg_pnl = trades["exit_pnl"].mean()
    med_pnl = trades["exit_pnl"].median()
    worst   = trades["exit_pnl"].min()
    # $/BP-day：avg_pnl / (total_bp * hold_days / 100)
    # total_bp is in $, hold_days ~ dte_at_exit (actual)
    if "dte_at_exit" in trades.columns and "total_bp" in trades.columns:
        hold_days = trades["dte_at_exit"].mean()
        avg_bp    = trades["total_bp"].mean()
        dbd       = avg_pnl / (avg_bp * hold_days / 100) if avg_bp > 0 and hold_days > 0 else None
    else:
        dbd = avg_pnl / (21000 * HOLD_DAYS_ASSUMPTION / 100)
    return {
        "label":        label,
        "n":            n,
        "win_rate":     round(wins / n * 100, 1),
        "avg_pnl":      round(avg_pnl, 0),
        "median_pnl":   round(med_pnl, 0),
        "worst_pnl":    round(worst, 0),
        "dollar_bp_day": round(dbd, 4) if dbd else None,
    }

# ── 5. 对每个 threshold 输出统计 ─────────────────────────────────────────────
results = []
tagged_rows = []

# 基准组（threshold=28）统计
af28_trades    = bps_hv[bps_hv["is_af_28"] == True]
non_af28_trades = bps_hv[bps_hv["is_af_28"] == False]

print(f"\nBaseline (threshold=28):")
print(f"  Aftermath trades: {len(af28_trades)}  |  Non-aftermath: {len(non_af28_trades)}")
s = trade_stats(af28_trades, "threshold=28 aftermath")
print(f"  WR={s['win_rate']}%  avg=${s['avg_pnl']}  worst=${s['worst_pnl']}  $/BP-day={s['dollar_bp_day']}")

for thr in THRESHOLDS:
    col         = f"is_af_{thr}"
    af_trades   = bps_hv[bps_hv[col] == True]
    non_af      = bps_hv[bps_hv[col] == False]

    # 新增 = 在此 threshold 标为 aftermath 但在 threshold=28 不是
    new_trades  = bps_hv[(bps_hv[col] == True) & (bps_hv["is_af_28"] == False)]
    # 原有 aftermath = 两者都标为 aftermath
    orig_trades = bps_hv[(bps_hv[col] == True) & (bps_hv["is_af_28"] == True)]

    s_all    = trade_stats(af_trades, f"threshold={thr} all aftermath")
    s_new    = trade_stats(new_trades, f"threshold={thr} new-only")
    s_orig   = trade_stats(orig_trades, f"threshold={thr} original aftermath")

    row = {
        "threshold":              thr,
        "af_trades_n":            s_all["n"],
        "orig_aftermath_n":       s_orig["n"],
        "new_trades_n":           s_new["n"],
        "new_wr":                 s_new["win_rate"],
        "new_avg_pnl":            s_new["avg_pnl"],
        "new_median_pnl":         s_new["median_pnl"],
        "new_worst_pnl":          s_new["worst_pnl"],
        "new_dollar_bp_day":      s_new["dollar_bp_day"],
        "all_af_wr":              s_all["win_rate"],
        "all_af_avg_pnl":         s_all["avg_pnl"],
        "all_af_worst_pnl":       s_all["worst_pnl"],
    }
    results.append(row)

    print(f"\nThreshold = {thr}:")
    print(f"  All aftermath trades : {s_all['n']}  (orig={s_orig['n']}, new={s_new['n']})")
    if s_new["n"] > 0:
        print(f"  New trades WR        : {s_new['win_rate']}%")
        print(f"  New trades avg P&L   : ${s_new['avg_pnl']}")
        print(f"  New trades median P&L: ${s_new['median_pnl']}")
        print(f"  New trades worst     : ${s_new['worst_pnl']}")
        print(f"  New $/BP-day         : {s_new['dollar_bp_day']}")
    else:
        print(f"  New trades           : none")

    # 收集带标签的 trades 用于输出
    for _, t in bps_hv.iterrows():
        orig_af   = bool(t["is_af_28"])
        this_af   = bool(t[col])
        is_new    = this_af and not orig_af
        tagged_rows.append({
            "entry_date":     t["entry_date"].strftime("%Y-%m-%d"),
            "exit_date":      t["exit_date"].strftime("%Y-%m-%d"),
            "exit_pnl":       t["exit_pnl"],
            "total_bp":       t.get("total_bp", ""),
            "dte_at_exit":    t.get("dte_at_exit", ""),
            "threshold":      thr,
            "is_aftermath":   this_af,
            "is_new_vs_28":   is_new,
        })

# ── 6. 输出 CSV ───────────────────────────────────────────────────────────────
df_results = pd.DataFrame(results)
out_r = os.path.join(OUT_DIR, "q070_p2_results.csv")
df_results.to_csv(out_r, index=False)
print(f"\nSaved: {out_r}")

df_tagged = pd.DataFrame(tagged_rows)
out_t = os.path.join(OUT_DIR, "q070_p2_tagged_trades.csv")
df_tagged.to_csv(out_t, index=False)
print(f"Saved: {out_t}  ({len(df_tagged)} rows)")

print("\n[P2 done]")
