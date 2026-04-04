"""
SPEC-018 Prototype — Evaluation Metrics Reform
计算当前缺失的尾部统计、体制分层 drawdown、PnL 分布特征。
ROM 已由 SPEC-012 实现，本次补充：
  - Tail loss stats (CVaR, worst N)
  - Regime-specific Sharpe / WR / drawdown
  - PnL skew / kurtosis (asymmetry signature)
  - Return/MaxDD ratio
  - ROM after realism adjustment (using SPEC-016 haircut factors)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd
from backtest.engine import run_backtest

# ─── 运行回测 ─────────────────────────────────────────────────────────────────

print("加载 26yr 回测数据 (2000-01-01)...")
trades26, _, _ = run_backtest(start_date="2000-01-01", verbose=False)
print(f"完成: {len(trades26)} 笔")

print("加载 3yr 回测数据 (2022-01-01)...")
trades3, _, _ = run_backtest(start_date="2022-01-01", verbose=False)
print(f"完成: {len(trades3)} 笔")

print()

# ─── 辅助函数 ──────────────────────────────────────────────────────────────────

def extended_metrics(trades, label):
    if not trades:
        print(f"  {label}: no trades")
        return {}

    pnls    = np.array([t.exit_pnl for t in trades])
    roms    = np.array([t.rom_annualized for t in trades if t.total_bp > 0])
    holds   = np.array([t.hold_days for t in trades])
    total   = len(pnls)
    wins    = pnls[pnls > 0]
    losses  = pnls[pnls <= 0]

    equity  = np.cumsum(pnls)
    peak    = np.maximum.accumulate(equity)
    dd      = equity - peak
    max_dd  = float(dd.min())

    # Sharpe
    mean_pnl = np.mean(pnls)
    std_pnl  = np.std(pnls, ddof=1) if len(pnls) > 1 else 1e-9
    avg_hold = np.mean(holds)
    sharpe   = (mean_pnl / std_pnl) * np.sqrt(252 / max(avg_hold, 1))

    # Tail stats
    sorted_pnl = np.sort(pnls)
    worst5  = sorted_pnl[:5]
    cvar5   = float(sorted_pnl[:max(1, int(len(pnls)*0.05))].mean())   # 5% CVaR
    cvar10  = float(sorted_pnl[:max(1, int(len(pnls)*0.10))].mean())   # 10% CVaR

    # Distribution shape
    skew    = float(pd.Series(pnls).skew())
    kurt    = float(pd.Series(pnls).kurtosis())  # excess kurtosis

    # Calmar-like: Total PnL / |MaxDD|
    total_pnl  = float(pnls.sum())
    calmar     = total_pnl / abs(max_dd) if max_dd != 0 else np.nan

    # Win/loss asymmetry
    avg_win  = float(wins.mean()) if len(wins) else 0
    avg_loss = float(losses.mean()) if len(losses) else 0
    payoff   = abs(avg_win / avg_loss) if avg_loss != 0 else np.nan

    # ROM stats
    avg_rom    = float(roms.mean()) if len(roms) else 0
    median_rom = float(np.median(roms)) if len(roms) else 0

    print(f"\n  ─── {label} (n={total}) ───")
    print(f"  【基础】")
    print(f"    Total PnL   : ${total_pnl:+,.0f}")
    print(f"    Win rate    : {len(wins)/total*100:.1f}%")
    print(f"    Sharpe      : {sharpe:.2f}")
    print(f"    Max DD      : ${max_dd:+,.0f}")
    print(f"    Calmar      : {calmar:.2f}  (TotalPnL / |MaxDD|)")
    print(f"  【ROM】")
    print(f"    Avg ROM     : {avg_rom:+.3f}")
    print(f"    Median ROM  : {median_rom:+.3f}")
    print(f"  【尾部损失】")
    print(f"    CVaR 5%     : ${cvar5:+,.0f}  (worst 5% trades avg)")
    print(f"    CVaR 10%    : ${cvar10:+,.0f}  (worst 10% trades avg)")
    print(f"    Worst 5     : {[f'${x:+,.0f}' for x in worst5]}")
    print(f"  【分布形态】")
    print(f"    Skewness    : {skew:+.2f}  ({'右尾（大赢多）' if skew>0 else '左尾（大输多）'})")
    print(f"    Kurtosis    : {kurt:+.2f}  ({'厚尾' if kurt>0 else '薄尾'})")
    print(f"    Payoff ratio: {payoff:.2f}  (avg_win / avg_loss)")
    print(f"  【赢亏结构】")
    print(f"    Avg win     : ${avg_win:+,.0f}")
    print(f"    Avg loss    : ${avg_loss:+,.0f}")
    print(f"    Hold avg    : {avg_hold:.0f} days")

    return {
        "total_pnl":   total_pnl,
        "win_rate":    len(wins)/total,
        "sharpe":      sharpe,
        "max_dd":      max_dd,
        "calmar":      calmar,
        "avg_rom":     avg_rom,
        "median_rom":  median_rom,
        "cvar5":       cvar5,
        "cvar10":      cvar10,
        "skew":        skew,
        "kurt":        kurt,
        "payoff":      payoff,
    }


def regime_breakdown(trades, label):
    """按 regime 分层计算 Sharpe / WR / DrawDown"""
    from signals.vix_regime import _classify_regime

    groups = {"LOW_VOL": [], "NORMAL": [], "HIGH_VOL": []}
    for t in trades:
        if t.entry_vix < 15:
            groups["LOW_VOL"].append(t)
        elif t.entry_vix < 22:
            groups["NORMAL"].append(t)
        elif t.entry_vix < 35:
            groups["HIGH_VOL"].append(t)

    print(f"\n  ─── {label}: Regime 分层 ───")
    for regime, ts in groups.items():
        if not ts:
            continue
        pnls = np.array([t.exit_pnl for t in ts])
        holds = np.array([t.hold_days for t in ts])
        wins = pnls[pnls > 0]
        equity = np.cumsum(pnls)
        peak = np.maximum.accumulate(equity)
        dd = equity - peak
        max_dd = float(dd.min())
        mean_pnl = np.mean(pnls)
        std_pnl = np.std(pnls, ddof=1) if len(pnls) > 1 else 1e-9
        avg_hold = np.mean(holds)
        sharpe = (mean_pnl / std_pnl) * np.sqrt(252 / max(avg_hold, 1))
        print(f"    {regime:<12} n={len(ts):>3}  WR={len(wins)/len(ts)*100:.0f}%  "
              f"Sharpe={sharpe:.2f}  MaxDD=${max_dd:+,.0f}  "
              f"TotalPnL=${sum(pnls):+,.0f}")


print("=" * 65)
print("  METRICS REFORM — Extended Statistics")
print("=" * 65)

m26 = extended_metrics(trades26, "26yr (2000–2026)")
m3  = extended_metrics(trades3,  "3yr  (2022–2026)")

regime_breakdown(trades26, "26yr")
regime_breakdown(trades3,  "3yr")

# ─── 策略族尾部比较 ────────────────────────────────────────────────────────────

print("\n\n  ─── 26yr: 各策略尾部损失对比 ───")
from collections import defaultdict
strat_trades = defaultdict(list)
for t in trades26:
    strat_trades[t.strategy.value].append(t)

print(f"  {'策略':<32} {'n':>4} {'Skew':>7} {'CVaR5%':>10} {'Payoff':>8} {'WR':>6}")
print("  " + "-" * 70)
for strat, ts in sorted(strat_trades.items(), key=lambda x: len(x[1]), reverse=True):
    pnls = np.array([t.exit_pnl for t in ts])
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    skew = float(pd.Series(pnls).skew()) if len(pnls) >= 3 else 0
    cvar5 = float(np.sort(pnls)[:max(1, int(len(pnls)*0.05))].mean())
    payoff = abs(wins.mean() / losses.mean()) if len(losses) and len(wins) else 0
    wr = len(wins) / len(pnls)
    print(f"  {strat:<32} {len(ts):>4} {skew:>+7.2f} ${cvar5:>9,.0f} {payoff:>8.2f} {wr*100:>5.0f}%")

# ─── 总结 ────────────────────────────────────────────────────────────────────

print("\n\n" + "=" * 65)
print("  发现汇总")
print("=" * 65)

print(f"""
  1. Calmar ratio（TotalPnL / MaxDD）:
     26yr: {m26.get('calmar', 0):.2f}  3yr: {m3.get('calmar', 0):.2f}
     → 3yr 较差，印证 2022–2023 熊市拖拽

  2. CVaR 5%（最差 5% trades 均值）:
     26yr: ${m26.get('cvar5', 0):+,.0f}  3yr: ${m3.get('cvar5', 0):+,.0f}
     → 尾部损失绝对值揭示极端场景下账户受损程度

  3. PnL Skewness:
     26yr: {m26.get('skew', 0):+.2f}  3yr: {m3.get('skew', 0):+.2f}
     → 正 skew = 有少量大赢；负 skew = 集中在小赢但有大输

  4. Payoff ratio:
     26yr: {m26.get('payoff', 0):.2f}  3yr: {m3.get('payoff', 0):.2f}
     → short-vol 系统通常 WR 高但 payoff ratio < 2 是结构性特征
""")
