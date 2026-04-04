# PROTOTYPE — SPEC-005 前期研究
# 目标：分析 Bull Call Diagonal 的 trend_flip 退出规则是否在帮助或伤害策略
#
# 研究问题：
#   1. trend_flip 退出时，仓位处于盈利 or 亏损？（是否在切 winner）
#   2. trend_flip 在第几天触发？（是噪声 or 真实趋势）
#   3. 如果放宽 trend_flip 最低天数（3→5→7→10），ALL 历史如何变化？
#
# 方法：
#   - run_backtest 只能修改 StrategyParams，trend_flip min_days 硬编码在 engine.py
#   - 本 prototype 通过读取回测 trade 数据 + signal_history 还原 trend_flip 触发时的信号
#   - 对 "如果放宽" 的问题，用 days_held 分布做推断（非精确模拟）

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
from backtest.engine import run_backtest
from strategy.selector import DEFAULT_PARAMS, StrategyName

# ─── 1. 运行全量回测 ────────────────────────────────────────────────────────
print("运行全量回测 2000-01-01 → 今日（约 30 秒）...")
trades, metrics, signals = run_backtest(start_date="2000-01-01", verbose=False)

bcd = [t for t in trades if t.strategy == StrategyName.BULL_CALL_DIAGONAL]
print(f"\n全量 BCD 交易：{len(bcd)} 笔\n")

# ─── 2. 按 exit_reason 分组统计 ────────────────────────────────────────────
reasons = {}
for t in bcd:
    r = t.exit_reason
    if r not in reasons:
        reasons[r] = {"count": 0, "wins": 0, "total_pnl": 0.0, "pnl_list": [], "days_list": []}
    g = reasons[r]
    g["count"] += 1
    g["total_pnl"] += t.exit_pnl
    g["pnl_list"].append(t.exit_pnl)
    g["days_list"].append(t.dte_at_exit if hasattr(t, "dte_at_exit") else 0)
    if t.exit_pnl > 0:
        g["wins"] += 1

print("=" * 65)
print(f"{'退出原因':<20} {'笔数':>5} {'胜率':>7} {'总PnL':>10} {'均PnL':>9}")
print("-" * 65)
for reason, g in sorted(reasons.items(), key=lambda x: -x[1]["count"]):
    wr  = g["wins"] / g["count"] * 100 if g["count"] else 0
    avg = g["total_pnl"] / g["count"] if g["count"] else 0
    print(f"{reason:<20} {g['count']:>5} {wr:>6.0f}% {g['total_pnl']:>+10.0f} {avg:>+9.0f}")

# ─── 3. trend_flip 明细分析 ──────────────────────────────────────────────
tf_trades = [t for t in bcd if t.exit_reason == "trend_flip"]
if not tf_trades:
    print("\ntend_flip 退出：0 笔")
else:
    print(f"\n{'=' * 65}")
    print(f"trend_flip 退出明细（{len(tf_trades)} 笔）")
    print("-" * 65)

    # 用 signal_history 重建 days_held（回测 Trade 没有直接存 days_held）
    # 计算方法：entry_date 到 exit_date 的自然日差作为代理
    sig_df = pd.DataFrame(signals)
    sig_df["date"] = pd.to_datetime(sig_df["date"])
    sig_df = sig_df.set_index("date")

    rows = []
    for t in tf_trades:
        entry = pd.to_datetime(t.entry_date)
        exit_ = pd.to_datetime(t.exit_date)
        # 计算持仓交易日数（更准确）
        if entry in sig_df.index and exit_ in sig_df.index:
            trading_days = len(sig_df.loc[entry:exit_])
        else:
            trading_days = (exit_ - entry).days  # 日历日兜底
        rows.append({
            "entry":        t.entry_date,
            "exit":         t.exit_date,
            "days_held":    trading_days,
            "entry_spx":    t.entry_spx,
            "exit_spx":     t.exit_spx,
            "spx_chg%":     (t.exit_spx - t.entry_spx) / t.entry_spx * 100,
            "pnl":          t.exit_pnl,
            "pnl_pct":      t.pnl_pct,
        })

    df = pd.DataFrame(rows).sort_values("entry")
    pd.set_option("display.float_format", lambda x: f"{x:.1f}")
    print(df.to_string(index=False))

    # 关键统计
    print(f"\n--- trend_flip 退出时的仓位状态 ---")
    at_profit = sum(1 for r in rows if r["pnl"] > 0)
    at_loss   = sum(1 for r in rows if r["pnl"] <= 0)
    avg_pnl   = sum(r["pnl"] for r in rows) / len(rows)
    avg_days  = sum(r["days_held"] for r in rows) / len(rows)
    print(f"  退出时盈利（pnl > 0）：{at_profit} 笔 ({at_profit/len(rows)*100:.0f}%)")
    print(f"  退出时亏损（pnl ≤ 0）：{at_loss}  笔 ({at_loss/len(rows)*100:.0f}%)")
    print(f"  平均 PnL：${avg_pnl:+.0f}")
    print(f"  平均持仓天数：{avg_days:.1f}d")

    # days_held 分布
    print(f"\n--- days_held 分布（trend_flip 在第几天触发）---")
    buckets = {"≤5d": 0, "6-10d": 0, "11-20d": 0, "21-40d": 0, ">40d": 0}
    for r in rows:
        d = r["days_held"]
        if d <= 5:      buckets["≤5d"] += 1
        elif d <= 10:   buckets["6-10d"] += 1
        elif d <= 20:   buckets["11-20d"] += 1
        elif d <= 40:   buckets["21-40d"] += 1
        else:           buckets[">40d"] += 1
    for k, v in buckets.items():
        bar = "█" * v
        print(f"  {k:<10} {v:>3} 笔  {bar}")

# ─── 4. 对比：如果 trend_flip 要求 days_held ≥ N 才触发 ─────────────────────
# 这是一个近似推断：trend_flip 出场的 days_held < N 的笔数，
# 如果放宽到 N，这些笔就不会被 trend_flip 截断。
# 但我们不知道它们后来的真实走势，所以只能分析"被提前切出"的比例。
if tf_trades:
    print(f"\n{'=' * 65}")
    print("放宽 trend_flip 最低天数的影响推断")
    print("（注：这是对'被提前切出笔数'的静态分析，非精确重跑）")
    print("-" * 65)
    for threshold in [3, 5, 7, 10, 15]:
        early_exits = sum(1 for r in rows if r["days_held"] < threshold)
        pct = early_exits / len(rows) * 100
        print(f"  min_days ≥ {threshold:>2}d：{early_exits:>3} 笔 trend_flip 被抑制 ({pct:.0f}%)")

print("\n完成。")
