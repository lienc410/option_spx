# PROTOTYPE — SPEC-009 Bull Call Diagonal 入场过滤
#
# 目标：量化两个改进方向对 26 年和 3 年 Sharpe / WR 的净影响
#
# 方向 A：Diagonal 增加 trend.above_200 前提
#   LOW_VOL + BULLISH + SPX < 200MA → REDUCE_WAIT（原为 Diagonal）
#   NORMAL + IV LOW + BULLISH + SPX < 200MA → REDUCE_WAIT（原为 Diagonal）
#
# 方向 B：移除 NORMAL + IV LOW + BULLISH → Diagonal，改 REDUCE_WAIT
#   无论 above_200 状态，NORMAL + IV LOW + BULLISH 一律 REDUCE_WAIT
#
# 方向 A+B：两者叠加

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
import numpy as np
from collections import defaultdict
from backtest.engine   import run_backtest, Trade
from strategy.selector import StrategyName, StrategyParams

DEFAULT_PARAMS = StrategyParams()


# ─── 辅助函数 ─────────────────────────────────────────────────────────────────

def summarise(label: str, trades: list[Trade], start_year: int) -> dict:
    """打印并返回汇总指标。"""
    if not trades:
        print(f"  {label:<35}  no trades")
        return {}

    pnls      = [t.exit_pnl for t in trades]
    wr        = sum(1 for p in pnls if p > 0) / len(pnls) * 100
    total     = sum(pnls)
    mean_pnl  = np.mean(pnls)
    std_pnl   = np.std(pnls) if len(pnls) > 1 else 1e-9
    avg_hold  = np.mean([
        (pd.Timestamp(t.exit_date) - pd.Timestamp(t.entry_date)).days for t in trades
    ])
    sharpe    = mean_pnl / std_pnl * np.sqrt(252 / avg_hold) if avg_hold > 0 else 0

    diag_n    = sum(1 for t in trades if t.strategy == StrategyName.BULL_CALL_DIAGONAL)
    diag_wr   = (sum(1 for t in trades
                     if t.strategy == StrategyName.BULL_CALL_DIAGONAL and t.exit_pnl > 0)
                 / diag_n * 100) if diag_n else float("nan")

    print(f"  {label:<35}  n={len(trades):>3}  WR={wr:>5.1f}%  "
          f"Sharpe={sharpe:>+5.2f}  PnL=${total:>+9,.0f}  "
          f"Diag({diag_n}笔 WR={diag_wr:.0f}%)" if diag_n else
          f"  {label:<35}  n={len(trades):>3}  WR={wr:>5.1f}%  "
          f"Sharpe={sharpe:>+5.2f}  PnL=${total:>+9,.0f}  "
          f"Diag=0")
    return {"n": len(trades), "wr": wr, "sharpe": sharpe, "total": total,
            "diag_n": diag_n, "diag_wr": diag_wr}


def delta_row(label: str, base: dict, variant: dict) -> None:
    """打印 baseline vs variant 的差值行。"""
    if not base or not variant:
        return
    dwr    = variant["wr"]    - base["wr"]
    dsharp = variant["sharpe"] - base["sharpe"]
    dpnl   = variant["total"]  - base["total"]
    dn     = variant["n"]      - base["n"]
    print(f"    Δ {label:<31}  Δn={dn:>+3}  ΔWR={dwr:>+5.1f}pp  "
          f"ΔSharpe={dsharp:>+5.2f}  ΔPnL=${dpnl:>+9,.0f}")


# ─── 加载基准回测（原始引擎，不修改） ────────────────────────────────────────
print("加载基准回测...")
trades_26_base, _, _ = run_backtest(start_date="2000-01-01", verbose=False)
trades_3_base,  _, _ = run_backtest(start_date="2022-01-01", verbose=False)

# 加载 SPX 历史（用于 above_200 判断）
from signals.trend import fetch_spx_history
spx_hist = fetch_spx_history(period="max")
spx_hist.index = pd.to_datetime(spx_hist.index.date)
spx_hist["ma200"] = spx_hist["close"].rolling(200).mean()


def above_200_on(entry_date: str) -> bool:
    ts = pd.Timestamp(entry_date)
    if ts not in spx_hist.index:
        return True          # 保守：找不到数据时不过滤
    row = spx_hist.loc[ts]
    if pd.isna(row["ma200"]):
        return True
    return bool(row["close"] >= row["ma200"])


# ─── 模拟过滤：对已有交易列表做后验过滤 ───────────────────────────────────────
#
# 注意：真正的实施会在 selector 入场时阻断，产生不同的随后入场序列。
# 但此处做后验过滤（把 Diagonal 视为 REDUCE_WAIT 即删除该笔）可以快速
# 量化上界：若这些 Diagonal 笔数全部变为不入场，WR / Sharpe 会怎样变化。
#
# 局限性：后验过滤高估改善幅度（因为实际上阻断后后续入场时机会偏移）。
# 但可以明确告诉我们"最好情况"的改善区间。

def filter_A(trades: list[Trade]) -> list[Trade]:
    """方向 A：删除 SPX < 200MA 时入场的 Diagonal。"""
    return [t for t in trades
            if not (t.strategy == StrategyName.BULL_CALL_DIAGONAL
                    and not above_200_on(t.entry_date))]


def filter_B(trades: list[Trade], signals: list[dict]) -> list[Trade]:
    """
    方向 B：删除来自 NORMAL + IV LOW + BULLISH 路径的 Diagonal。
    使用信号历史判断：若入场当日 regime=NORMAL 且 ivp < 40 → 删除。
    （signal history 无 iv_signal 字段，用 ivp < IVP_LOW_THRESHOLD=40 等效）
    """
    # 构建 date → sig 快查表
    sig_map: dict[str, dict] = {s["date"]: s for s in signals}

    def is_normal_iv_low(entry_date: str) -> bool:
        sig = sig_map.get(entry_date)
        if sig is None:
            return False
        return sig.get("regime") == "NORMAL" and (sig.get("ivp") or 100) < 40

    return [t for t in trades
            if not (t.strategy == StrategyName.BULL_CALL_DIAGONAL
                    and is_normal_iv_low(t.entry_date))]


def filter_AB(trades: list[Trade], signals: list[dict]) -> list[Trade]:
    """方向 A+B：两者叠加。"""
    after_a = filter_A(trades)
    return filter_B(after_a, signals)


# ─── 加载信号历史（用于 B 过滤）────────────────────────────────────────────────
print("加载信号历史（用于方向 B 判断）...")
_, _, signals_26 = run_backtest(start_date="2000-01-01", verbose=False)
_, _, signals_3  = run_backtest(start_date="2022-01-01", verbose=False)

trades_26_A  = filter_A(trades_26_base)
trades_26_B  = filter_B(trades_26_base, signals_26)
trades_26_AB = filter_AB(trades_26_base, signals_26)

trades_3_A   = filter_A(trades_3_base)
trades_3_B   = filter_B(trades_3_base, signals_3)
trades_3_AB  = filter_AB(trades_3_base, signals_3)


# ─── 打印结果 ─────────────────────────────────────────────────────────────────
print(f"\n{'='*80}")
print("26 年回测（2000–2026）")
print("-" * 80)
b26  = summarise("Baseline",   trades_26_base, 2000)
a26  = summarise("方向 A (above_200 前提)", trades_26_A,  2000)
bb26 = summarise("方向 B (移除 NORMAL IV LOW)", trades_26_B, 2000)
ab26 = summarise("方向 A+B",   trades_26_AB, 2000)
print()
delta_row("A vs Baseline", b26, a26)
delta_row("B vs Baseline", b26, bb26)
delta_row("A+B vs Baseline", b26, ab26)

print(f"\n{'='*80}")
print("3 年回测（2022–2026）")
print("-" * 80)
b3   = summarise("Baseline",   trades_3_base, 2022)
a3   = summarise("方向 A (above_200 前提)", trades_3_A,   2022)
bb3  = summarise("方向 B (移除 NORMAL IV LOW)", trades_3_B, 2022)
ab3  = summarise("方向 A+B",   trades_3_AB,  2022)
print()
delta_row("A vs Baseline", b3, a3)
delta_row("B vs Baseline", b3, bb3)
delta_row("A+B vs Baseline", b3, ab3)


# ─── Diagonal 专项分解 ────────────────────────────────────────────────────────
print(f"\n{'='*80}")
print("Diagonal 专项：3 年，按入场时 above_200 / regime 分层")
print("-" * 60)

diag_3 = [t for t in trades_3_base if t.strategy == StrategyName.BULL_CALL_DIAGONAL]
above_diag  = [t for t in diag_3 if above_200_on(t.entry_date)]
below_diag  = [t for t in diag_3 if not above_200_on(t.entry_date)]

def fmt(label, trades):
    if not trades:
        print(f"  {label:<35} n=0")
        return
    wr  = sum(1 for t in trades if t.exit_pnl > 0) / len(trades) * 100
    avg = np.mean([t.exit_pnl for t in trades])
    tot = sum(t.exit_pnl for t in trades)
    reasons = defaultdict(int)
    for t in trades:
        reasons[t.exit_reason] += 1
    r_str = " ".join(f"{k}:{v}" for k, v in sorted(reasons.items(), key=lambda x: -x[1]))
    print(f"  {label:<35} n={len(trades):>2}  WR={wr:>4.0f}%  均={avg:>+7.0f}  总={tot:>+9.0f}  [{r_str}]")

fmt("Diagonal SPX ≥ 200MA", above_diag)
fmt("Diagonal SPX < 200MA  ⚠", below_diag)

sig_map_3 = {s["date"]: s for s in signals_3}
normal_iv_low_diag = [
    t for t in diag_3
    if (lambda s: s is not None and s.get("regime") == "NORMAL" and (s.get("ivp") or 100) < 40)
       (sig_map_3.get(t.entry_date))
]
other_diag = [t for t in diag_3 if t not in normal_iv_low_diag]
fmt("Diagonal NORMAL + IV LOW", normal_iv_low_diag)
fmt("Diagonal 其他路径 (LOW_VOL)", other_diag)

print(f"\n{'='*80}")
print("结论摘要")
print("-" * 60)
# 找到最优方向
candidates = {"A": (a3, a26), "B": (bb3, bb26), "A+B": (ab3, ab26)}
for name, (r3, r26) in candidates.items():
    if r3 and r26:
        print(f"  方向 {name}: "
              f"3yr ΔSharpe={r3['sharpe']-b3['sharpe']:>+.2f}  ΔWR={r3['wr']-b3['wr']:>+.1f}pp  "
              f"| 26yr ΔSharpe={r26['sharpe']-b26['sharpe']:>+.2f}  ΔWR={r26['wr']-b26['wr']:>+.1f}pp")

print("\n完成。")
