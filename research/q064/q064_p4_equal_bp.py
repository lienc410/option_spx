"""
Q064 P4: 等 BP 条件下 V3-A vs BPS_HV 对比

方法：
- 以 BPS_HV 的 BP 占用为基准（每笔 trade 各自的 bps_bp）
- V3-A 按比例缩减合约数：v3a_contracts_adj = bps_bp / v3a_bp（每笔独立计算）
- V3-A P&L 按调整后合约数等比缩放
- BPS_HV 合约数保持不变（baseline=1.0 contract unit）
- 所有 $/BP-day 均以 bps_bp 为分母（两组 BP 相同）
"""

import pandas as pd
import numpy as np

# ── 读取 P3 结果 ──────────────────────────────────────────────────────────────
df = pd.read_csv("research/q064/q064_p3_results.csv")

# ── 每笔 trade 各自的 per-contract 基准 ──────────────────────────────────────
# P3 中 contracts 列是 BPS_HV 实际用的合约数（固定为 BP_target / spread_width / 100）
# bps_bp 和 v3a_bp 已经是 per-trade 的实际 BP（包含合约数）
# 我们需要 per-contract BP：
#   bps_bp_per_contract = bps_bp / contracts
#   v3a_bp_per_contract = v3a_bp / contracts
#
# 然后标准化到"同一 BP 预算"：
#   target_bp = bps_bp（每笔 BPS_HV 的实际 BP，作为共同预算）
#   bps_contracts_adj = 1.0（不变）
#   v3a_contracts_adj = bps_bp / v3a_bp（=bps_bp_per_contract / v3a_bp_per_contract，等价）

df["bps_bp_per_contract"] = df["bps_bp"] / df["contracts"]
df["v3a_bp_per_contract"] = df["v3a_bp"] / df["contracts"]
df["bps_pnl_per_contract"] = df["bps_pnl"] / df["contracts"]
df["v3a_pnl_per_contract"] = df["v3a_pnl"] / df["contracts"]

# 等 BP 调整系数（V3-A 缩减合约数使 BP = bps_bp）
df["v3a_contracts_adj"] = df["bps_bp"] / df["v3a_bp"]

# BP 标准化后的 P&L
df["bps_pnl_adj"] = df["bps_pnl"]          # BPS_HV 不变
df["v3a_pnl_adj"] = df["v3a_pnl"] * df["v3a_contracts_adj"]

# 等 BP 预算（两组相同）
df["equal_bp"] = df["bps_bp"]

# $/BP-day（等 BP 条件下，用共同 BP 预算作分母）
# 单位与 P3 一致：pnl / (bp * hold_days) * 10000
# P3 CSV 中 bps_bp_day 约为 81，对应 pnl/(bp*days) * 10000
# 例：2792.96 / (22921.47 * 15) * 10000 = 81.23
df["bps_dollar_bp_day"] = df["bps_pnl_adj"] / (df["equal_bp"] * df["hold_days"]) * 10000
df["v3a_dollar_bp_day"] = df["v3a_pnl_adj"] / (df["equal_bp"] * df["hold_days"]) * 10000

# V3-A > BPS 标记
df["v3a_wins"] = df["v3a_pnl_adj"] > df["bps_pnl_adj"]
df["pnl_diff_v3a_minus_bps"] = df["v3a_pnl_adj"] - df["bps_pnl_adj"]

# ── 逐笔对比表 ────────────────────────────────────────────────────────────────
detail_cols = [
    "entry_date", "exit_date", "hold_days",
    "vix_at_entry", "vix_at_exit",
    "equal_bp",
    "v3a_contracts_adj",
    "bps_pnl_adj", "v3a_pnl_adj",
    "bps_dollar_bp_day", "v3a_dollar_bp_day",
    "pnl_diff_v3a_minus_bps", "v3a_wins",
]
detail_df = df[detail_cols].copy()
detail_df.to_csv("research/q064/q064_p4_results.csv", index=False, float_format="%.4f")
print("=== q064_p4_results.csv saved ===\n")

# ── 汇总统计 ──────────────────────────────────────────────────────────────────
n = len(df)
print(f"{'指标':<30} {'BPS_HV（baseline）':>22} {'V3-A BP-adjusted':>22}")
print("-" * 78)

def fmt_pct(x): return f"{x*100:.1f}%"
def fmt_dollar(x): return f"${x:,.0f}"
def fmt_float(x): return f"{x:.4f}"

# avg contracts adjusted
bps_avg_contracts = 1.0
v3a_avg_contracts = df["v3a_contracts_adj"].mean()
print(f"{'n':<30} {n:>22} {n:>22}")
print(f"{'avg contracts (adjusted)':<30} {bps_avg_contracts:>22.4f} {v3a_avg_contracts:>22.4f}")

# win_rate（P&L > 0）
bps_win = (df["bps_pnl_adj"] > 0).mean()
v3a_win = (df["v3a_pnl_adj"] > 0).mean()
print(f"{'win_rate':<30} {fmt_pct(bps_win):>22} {fmt_pct(v3a_win):>22}")

# avg P&L
bps_avg_pnl = df["bps_pnl_adj"].mean()
v3a_avg_pnl = df["v3a_pnl_adj"].mean()
print(f"{'avg P&L (BP-adjusted)':<30} {fmt_dollar(bps_avg_pnl):>22} {fmt_dollar(v3a_avg_pnl):>22}")

# median P&L
bps_med_pnl = df["bps_pnl_adj"].median()
v3a_med_pnl = df["v3a_pnl_adj"].median()
print(f"{'median P&L (BP-adjusted)':<30} {fmt_dollar(bps_med_pnl):>22} {fmt_dollar(v3a_med_pnl):>22}")

# $/BP-day（用各笔 bps_dollar_bp_day 的 mean）
bps_dbpd = df["bps_dollar_bp_day"].mean()
v3a_dbpd = df["v3a_dollar_bp_day"].mean()
print(f"{'avg $/BP-day':<30} {bps_dbpd:>22.2f} {v3a_dbpd:>22.2f}")

# worst trade
bps_worst = df["bps_pnl_adj"].min()
v3a_worst = df["v3a_pnl_adj"].min()
print(f"{'worst trade (BP-adjusted)':<30} {fmt_dollar(bps_worst):>22} {fmt_dollar(v3a_worst):>22}")

# total P&L
bps_total = df["bps_pnl_adj"].sum()
v3a_total = df["v3a_pnl_adj"].sum()
print(f"{'total P&L (BP-adjusted)':<30} {fmt_dollar(bps_total):>22} {fmt_dollar(v3a_total):>22}")

print("-" * 78)
v3a_win_count = df["v3a_wins"].sum()
print(f"\nV3-A 胜出笔数（V3-A > BPS）: {v3a_win_count} / {n}")
print(f"V3-A 平均 contracts 调整系数: {v3a_avg_contracts:.4f}（= {1/v3a_avg_contracts:.2f}× 原 V3-A 合约数的倒数）")

# ── 逐笔详情打印 ──────────────────────────────────────────────────────────────
print("\n=== 逐笔对比（等 BP 条件下）===")
print(f"{'日期':<14} {'Hold':>5} {'VIX':>6} {'BP':>8} "
      f"{'V3A_Cts':>8} {'BPS_PNL':>9} {'V3A_PNL':>9} {'Diff':>9} {'V3A>BPS':>8}")
print("-" * 82)
for _, r in df.iterrows():
    diff = r["pnl_diff_v3a_minus_bps"]
    win_mark = "YES" if r["v3a_wins"] else "no"
    print(f"{r['entry_date']:<14} {r['hold_days']:>5.0f} {r['vix_at_entry']:>6.2f} "
          f"{r['equal_bp']:>8,.0f} {r['v3a_contracts_adj']:>8.4f} "
          f"{r['bps_pnl_adj']:>9,.0f} {r['v3a_pnl_adj']:>9,.0f} "
          f"{diff:>9,.0f} {win_mark:>8}")

# ── 关键对比总结 ──────────────────────────────────────────────────────────────
pnl_edge = v3a_avg_pnl - bps_avg_pnl
pct_edge = pnl_edge / abs(bps_avg_pnl) * 100
dbpd_edge = v3a_dbpd - bps_dbpd
print(f"\n=== P4 核心结论 ===")
print(f"等 BP 后 V3-A avg P&L: {fmt_dollar(v3a_avg_pnl)}  BPS avg P&L: {fmt_dollar(bps_avg_pnl)}")
print(f"P&L 差异（V3-A - BPS）: {fmt_dollar(pnl_edge)}（{pct_edge:+.1f}%）")
print(f"$/BP-day 差异（V3-A - BPS）: {dbpd_edge:+.2f}")
print(f"V3-A 胜出笔数: {v3a_win_count}/{n}（{v3a_win_count/n*100:.1f}%）")
print(f"V3-A worst trade: {fmt_dollar(v3a_worst)}  BPS worst trade: {fmt_dollar(bps_worst)}")
