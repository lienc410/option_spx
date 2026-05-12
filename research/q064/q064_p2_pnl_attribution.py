"""
Q064 P2 — P&L Attribution: Aftermath vs Non-Aftermath HIGH_VOL BPS
2026-05-11

对 baseline_19y_trades.csv 中 28 笔 Bull Put Spread (High Vol)，
根据 entry_date 打 is_aftermath 标签，输出两组对比指标。

依赖：P1 脚本已生成 q064_p1_daily_flags.csv
"""

import os
import pandas as pd
import numpy as np

OUT_DIR  = os.path.dirname(os.path.abspath(__file__))
TRADES_PATH = os.path.join(
    os.path.dirname(OUT_DIR),  # research/
    "q042", "baseline_19y_trades.csv"
)
DAILY_FLAGS = os.path.join(OUT_DIR, "q064_p1_daily_flags.csv")

# ── 1. 读取数据 ───────────────────────────────────────────────────────────────
df_trades = pd.read_csv(TRADES_PATH, parse_dates=["entry_date", "exit_date"])
df_flags  = pd.read_csv(DAILY_FLAGS, parse_dates=["date"])

# 仅保留 BPS HV
bps_hv = df_trades[df_trades["strategy"] == "Bull Put Spread (High Vol)"].copy()
print(f"BPS High Vol trades: {len(bps_hv)}")

# 构建日期→标签 lookup
flags_map = df_flags.set_index("date")[["vix", "vix_peak_10d", "is_aftermath"]]

# ── 2. 打标签 ────────────────────────────────────────────────────────────────
def lookup_flag(row):
    ed = pd.Timestamp(row["entry_date"]).normalize()
    if ed in flags_map.index:
        r = flags_map.loc[ed]
        return r["vix"], r["vix_peak_10d"], bool(r["is_aftermath"])
    # 找最近交易日（±2日）
    for delta in [1, -1, 2, -2]:
        ed2 = ed + pd.Timedelta(days=delta)
        if ed2 in flags_map.index:
            r = flags_map.loc[ed2]
            return r["vix"], r["vix_peak_10d"], bool(r["is_aftermath"])
    return np.nan, np.nan, False

results = bps_hv.apply(lookup_flag, axis=1, result_type="expand")
results.columns = ["vix_at_entry", "vix_peak_10d", "is_aftermath"]
bps_hv = pd.concat([bps_hv, results], axis=1)

# 打印标签详情
print("\nTagged trades:")
cols_show = ["entry_date","exit_date","exit_pnl","total_bp","dte_at_entry","dte_at_exit",
             "vix_at_entry","vix_peak_10d","is_aftermath"]
print(bps_hv[cols_show].to_string(index=False))

# ── 3. 分组统计 ───────────────────────────────────────────────────────────────
def group_stats(grp):
    n        = len(grp)
    win_rate = (grp["exit_pnl"] > 0).mean() * 100
    avg_pnl  = grp["exit_pnl"].mean()
    med_pnl  = grp["exit_pnl"].median()
    avg_bp   = grp["total_bp"].mean()
    avg_dte  = ((grp["dte_at_entry"] + grp["dte_at_exit"]) / 2).mean()
    # $/BP-day = median_pnl / avg_bp * 10000 / avg_dte  (BP in $)
    bp_day   = med_pnl / avg_bp / avg_dte * 10_000 if avg_bp > 0 and avg_dte > 0 else np.nan
    worst    = grp["exit_pnl"].min()
    total    = grp["exit_pnl"].sum()
    avg_bp_pct = grp["bp_pct_account"].mean()

    # VIX stats
    vix_med  = grp["vix_at_entry"].median()
    vix_p25  = grp["vix_at_entry"].quantile(0.25)
    vix_p75  = grp["vix_at_entry"].quantile(0.75)

    return pd.Series({
        "n":               n,
        "win_rate_%":      round(win_rate, 1),
        "avg_exit_pnl_$":  round(avg_pnl, 2),
        "med_exit_pnl_$":  round(med_pnl, 2),
        "avg_bp_pct_acct_%": round(avg_bp_pct, 2),
        "$/BP-day":        round(bp_day, 4),
        "worst_trade_$":   round(worst, 2),
        "total_pnl_$":     round(total, 2),
        "vix_entry_med":   round(vix_med, 2),
        "vix_entry_p25":   round(vix_p25, 2),
        "vix_entry_p75":   round(vix_p75, 2),
    })

stats = bps_hv.groupby("is_aftermath").apply(group_stats).T
stats.columns = ["aftermath=False", "aftermath=True"]
stats = stats[["aftermath=True", "aftermath=False"]]  # True first

print("\n" + "=" * 60)
print("P2 Summary — BPS High Vol: Aftermath vs Non-Aftermath")
print("=" * 60)
print(stats.to_string())

# ── 4. 输出 CSV ───────────────────────────────────────────────────────────────
# tagged trades
out_tagged = os.path.join(OUT_DIR, "q064_p2_tagged_trades.csv")
bps_hv_out = bps_hv.copy()
bps_hv_out["entry_date"] = bps_hv_out["entry_date"].dt.strftime("%Y-%m-%d")
bps_hv_out["exit_date"]  = bps_hv_out["exit_date"].dt.strftime("%Y-%m-%d")
bps_hv_out.to_csv(out_tagged, index=False)
print(f"\nSaved: {out_tagged}")

# summary
out_summary = os.path.join(OUT_DIR, "q064_p2_summary.csv")
stats.to_csv(out_summary)
print(f"Saved: {out_summary}")

# ── 5. VIX 分布对比 ──────────────────────────────────────────────────────────
print("\nVIX at entry distribution:")
for af_val, label in [(True, "aftermath=True"), (False, "aftermath=False")]:
    sub = bps_hv[bps_hv["is_aftermath"] == af_val]["vix_at_entry"]
    if len(sub) == 0:
        print(f"  {label}: (no data)")
        continue
    print(f"  {label}  n={len(sub)}  "
          f"med={sub.median():.2f}  p25={sub.quantile(.25):.2f}  p75={sub.quantile(.75):.2f}")

print("\n[P2 done]")
