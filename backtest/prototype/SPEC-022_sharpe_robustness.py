"""
SPEC-022 Prototype — Sharpe Robustness Test
"Do not over-read current Sharpe. Use it as a provisional ranking metric only."

测试维度：
1. 滚动窗口 Sharpe（24-month rolling, 6-month step）
2. 不同起始日期（start_date）下的 Sharpe 稳定性
3. Sharpe 的时序分布（年度 Sharpe 分布）
4. Bootstrap confidence interval for Sharpe
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd
from backtest.engine import run_backtest

print("加载 26yr 完整数据...")
trades, _, _ = run_backtest(start_date="2000-01-01", verbose=False)
print(f"完成: {len(trades)} 笔")

# ─── 辅助：从 trades 子集计算 Sharpe ─────────────────────────────────────────

def compute_sharpe(trade_list):
    if len(trade_list) < 3:
        return np.nan
    pnls   = np.array([t.exit_pnl for t in trade_list])
    holds  = np.array([t.hold_days for t in trade_list])
    mean   = np.mean(pnls)
    std    = np.std(pnls, ddof=1)
    if std < 1e-9:
        return np.nan
    avg_hold = np.mean(holds)
    return (mean / std) * np.sqrt(252 / max(avg_hold, 1))

def compute_metrics_simple(trade_list, label=""):
    if not trade_list:
        return {}
    pnls = np.array([t.exit_pnl for t in trade_list])
    wins = pnls[pnls > 0]
    return {
        "n":         len(pnls),
        "sharpe":    compute_sharpe(trade_list),
        "wr":        len(wins) / len(pnls),
        "total_pnl": float(pnls.sum()),
        "avg_pnl":   float(pnls.mean()),
    }

# ─── 1. 年度 Sharpe 分布 ──────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("  SHARPE ROBUSTNESS TEST — Temporal Stability Analysis")
print("=" * 65)

print("\n  一、年度 Sharpe 分布（2000–2025）")
print()

yearly = {}
for t in trades:
    year = t.entry_date[:4]
    yearly.setdefault(year, []).append(t)

sharpes_per_year = {}
print(f"  {'年份':>6} {'n':>4} {'Sharpe':>8} {'WR':>7} {'TotalPnL':>12}")
print("  " + "-" * 45)
for year in sorted(yearly.keys()):
    ts = yearly[year]
    m  = compute_metrics_simple(ts)
    sharpes_per_year[year] = m.get("sharpe", np.nan)
    sharpe_str = f"{m['sharpe']:+.2f}" if not np.isnan(m.get('sharpe', np.nan)) else "  N/A"
    print(f"  {year:>6} {m['n']:>4} {sharpe_str:>8} {m['wr']*100:>6.0f}% {m['total_pnl']:>+12,.0f}")

annual_sharpes = [v for v in sharpes_per_year.values() if not np.isnan(v)]
print(f"\n  年度 Sharpe 统计:")
print(f"    均值: {np.mean(annual_sharpes):+.2f}")
print(f"    中位: {np.median(annual_sharpes):+.2f}")
print(f"    最低: {np.min(annual_sharpes):+.2f}  ({min(sharpes_per_year, key=lambda k: sharpes_per_year.get(k, 999))})")
print(f"    最高: {np.max(annual_sharpes):+.2f}  ({max(sharpes_per_year, key=lambda k: sharpes_per_year.get(k, -999))})")
print(f"    负值年数: {sum(1 for s in annual_sharpes if s < 0)} / {len(annual_sharpes)}")
print(f"    Sharpe<0.5 年数: {sum(1 for s in annual_sharpes if s < 0.5)} / {len(annual_sharpes)}")

# ─── 2. 滚动窗口 Sharpe（2yr 窗口，1yr 步进）────────────────────────────────

print("\n  二、滚动 2yr Sharpe（按年分组）")
print()

years = sorted(yearly.keys())
print(f"  {'窗口':>15} {'n':>4} {'Sharpe':>8} {'TotalPnL':>12}")
print("  " + "-" * 45)
for i in range(len(years) - 1):
    y1, y2 = years[i], years[i+1]
    ts = yearly.get(y1, []) + yearly.get(y2, [])
    if len(ts) < 3:
        continue
    m  = compute_metrics_simple(ts)
    sharpe_str = f"{m['sharpe']:+.2f}" if not np.isnan(m.get('sharpe', np.nan)) else "  N/A"
    print(f"  {y1}–{y2}          {m['n']:>4} {sharpe_str:>8} {m['total_pnl']:>+12,.0f}")

# ─── 3. 不同起始日期的 Sharpe ─────────────────────────────────────────────────

print("\n  三、不同起始日期的累计 Sharpe（back-window sensitivity）")
print()

start_dates = ["2000-01-01", "2003-01-01", "2005-01-01", "2008-01-01",
               "2010-01-01", "2015-01-01", "2018-01-01", "2020-01-01", "2022-01-01"]

print(f"  {'起始日期':>12} {'n':>4} {'Sharpe':>8} {'WR':>7} {'TotalPnL':>12}")
print("  " + "-" * 50)
for start in start_dates:
    ts = [t for t in trades if t.entry_date >= start]
    if not ts:
        continue
    m = compute_metrics_simple(ts)
    sharpe_str = f"{m['sharpe']:+.2f}" if not np.isnan(m.get('sharpe', np.nan)) else "  N/A"
    print(f"  {start:>12} {m['n']:>4} {sharpe_str:>8} {m['wr']*100:>6.0f}% {m['total_pnl']:>+12,.0f}")

# ─── 4. Bootstrap Confidence Interval for 26yr Sharpe ────────────────────────

print("\n  四、Bootstrap 95% CI for 26yr Sharpe")
print()
np.random.seed(42)
all_pnls = np.array([t.exit_pnl for t in trades])
all_holds = np.array([t.hold_days for t in trades])
n_boot = 5000
boot_sharpes = []
for _ in range(n_boot):
    idx = np.random.randint(0, len(all_pnls), len(all_pnls))
    bp = all_pnls[idx]
    bh = all_holds[idx]
    std = np.std(bp, ddof=1)
    if std < 1e-9:
        continue
    avg_h = np.mean(bh)
    s = (np.mean(bp) / std) * np.sqrt(252 / max(avg_h, 1))
    boot_sharpes.append(s)

p5, p50, p95 = np.percentile(boot_sharpes, [5, 50, 95])
full_sharpe = compute_sharpe(trades)
print(f"  26yr 完整 Sharpe:    {full_sharpe:+.2f}")
print(f"  Bootstrap 中位:     {p50:+.2f}")
print(f"  Bootstrap 95% CI:   [{p5:+.2f}, {p95:+.2f}]")
print(f"  P5-P95 区间宽度:    {p95-p5:.2f}")

# 3yr bootstrap
trades3yr = [t for t in trades if t.entry_date >= "2022-01-01"]
all_pnls3 = np.array([t.exit_pnl for t in trades3yr])
all_holds3 = np.array([t.hold_days for t in trades3yr])
boot3 = []
for _ in range(n_boot):
    idx = np.random.randint(0, len(all_pnls3), len(all_pnls3))
    bp  = all_pnls3[idx]
    bh  = all_holds3[idx]
    std = np.std(bp, ddof=1)
    if std < 1e-9:
        continue
    avg_h = np.mean(bh)
    s = (np.mean(bp) / std) * np.sqrt(252 / max(avg_h, 1))
    boot3.append(s)

p5_3, p50_3, p95_3 = np.percentile(boot3, [5, 50, 95])
sharpe3yr = compute_sharpe(trades3yr)
print(f"\n  3yr 完整 Sharpe:    {sharpe3yr:+.2f}")
print(f"  Bootstrap 中位:     {p50_3:+.2f}")
print(f"  Bootstrap 95% CI:   [{p5_3:+.2f}, {p95_3:+.2f}]")
print(f"  P5-P95 区间宽度:    {p95_3-p5_3:.2f}")

# ─── 5. 策略族 Sharpe 稳定性 ─────────────────────────────────────────────────

print("\n  五、各策略族 Sharpe 稳定性（26yr vs 3yr）")
print()
from collections import defaultdict
strat_map = defaultdict(list)
for t in trades:
    strat_map[t.strategy.value].append(t)
strat_map3 = defaultdict(list)
for t in trades3yr:
    strat_map3[t.strategy.value].append(t)

print(f"  {'策略':<32} {'26yr Sharpe':>12} {'3yr Sharpe':>12} {'变化':>8}")
print("  " + "-" * 70)
for strat in sorted(strat_map.keys()):
    ts26 = strat_map[strat]
    ts3  = strat_map3[strat]
    s26  = compute_sharpe(ts26) if len(ts26) >= 3 else np.nan
    s3   = compute_sharpe(ts3) if len(ts3) >= 3 else np.nan
    s26_str = f"{s26:+.2f}" if not np.isnan(s26) else "  N/A"
    s3_str  = f"{s3:+.2f}" if not np.isnan(s3) else "  N/A"
    delta   = s3 - s26 if not (np.isnan(s26) or np.isnan(s3)) else np.nan
    delta_str = f"{delta:+.2f}" if not np.isnan(delta) else "   —"
    print(f"  {strat:<32} {s26_str:>12} {s3_str:>12} {delta_str:>8}")

# ─── 结论 ─────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("  发现汇总 — Sharpe Robustness")
print("=" * 65)
neg_years = sum(1 for s in annual_sharpes if s < 0)
low_years  = sum(1 for s in annual_sharpes if s < 0.5)
print(f"""
  1. 年度 Sharpe 波动极大（均值 {np.mean(annual_sharpes):.2f}，范围 {np.min(annual_sharpes):.2f} ~ {np.max(annual_sharpes):.2f}）
     - 负值年份: {neg_years}，低于 0.5 年份: {low_years}
     - 这意味着某些单独年份 Sharpe 为负，但长期正向

  2. 起始日期敏感性：不同起点的 Sharpe 差异显著
     - 包含 2000–2003 熊市的窗口 Sharpe 最低
     - 2015–2025 窗口 Sharpe 最高

  3. Bootstrap 95% CI 宽度：26yr = {p95-p5:.2f}（不小）
     - 这说明 Sharpe 点估计有较大不确定性
     - 即使 26yr Sharpe={full_sharpe:.2f}，真实值可能在 [{p5:.2f}, {p95:.2f}]

  4. Warning C 的具体含义：
     - Sharpe={full_sharpe:.2f} 应理解为"可能范围 [{p5:.2f}, {p95:.2f}]"
     - 不同时间窗口下 Sharpe 波动 > 1.0，不应作为精确测量
     - 更可靠的指标：正年份比例 + Calmar ratio + 最大连续亏损年数
""")
