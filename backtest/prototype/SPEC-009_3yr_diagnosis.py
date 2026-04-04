# PROTOTYPE — 3 年回测诊断（2022-01-01 至今）
#
# 目标：
#   1. 找出 3 年 Sharpe 0.67、WR < 50% 的根因
#   2. 按年份 × 策略分解 WR / PnL
#   3. 验证两个主假设：
#      H1: BPS/BPS_HV 在 SPX < 200MA（熊市宏观）时 WR 低
#      H2: BCS_HV 在近期 SPX 强劲反弹时 WR 低（逆势反弹打穿 short call）
#   4. 估算"200MA 硬性封锁 BPS/BPS_HV"的潜在改善

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
import numpy as np
from backtest.engine import run_backtest
from signals.trend import fetch_spx_history
from signals.vix_regime import fetch_vix_history

# ─── 加载数据 ─────────────────────────────────────────────────────────────────
print("加载 3 年回测（2022-01-01）...")
trades_3yr, metrics_3yr, signals_3yr = run_backtest(
    start_date="2022-01-01", verbose=False
)

print("加载 26 年基准（2000-01-01）...")
trades_26yr, metrics_26yr, _ = run_backtest(
    start_date="2000-01-01", verbose=False
)

spx_hist = fetch_spx_history(period="max")
spx_hist.index = pd.to_datetime(spx_hist.index.date)
spx_hist["ma200"] = spx_hist["close"].rolling(200).mean()
spx_hist["ma50"]  = spx_hist["close"].rolling(50).mean()
spx_hist["ret5d"]  = spx_hist["close"].pct_change(5) * 100  # 5 日涨跌幅
spx_hist["ret10d"] = spx_hist["close"].pct_change(10) * 100

print(f"\n3yr 总交易数: {len(trades_3yr)}  |  26yr: {len(trades_26yr)}")
print(f"3yr Sharpe: {metrics_3yr['sharpe']:.2f}  |  WR: {metrics_3yr['win_rate']*100:.1f}%  |  "
      f"Total PnL: ${metrics_3yr['total_pnl']:+,.0f}")

# ─── 1. 按年份 × 策略分解 ──────────────────────────────────────────────────────
print(f"\n{'='*80}")
print("§1  按年份 × 策略分解 WR / PnL")
print(f"{'年份':<6} {'策略':<30} {'n':>4} {'WR':>6} {'均PnL':>8} {'总PnL':>10}")
print("-" * 65)

for trade in trades_3yr:
    trade._year = trade.entry_date[:4]

from collections import defaultdict
by_year_strat: dict[tuple[str, str], list] = defaultdict(list)
for t in trades_3yr:
    by_year_strat[(t._year, t.strategy.value)].append(t.exit_pnl)

for (yr, strat), pnls in sorted(by_year_strat.items()):
    wr  = sum(1 for p in pnls if p > 0) / len(pnls) * 100
    avg = np.mean(pnls)
    tot = sum(pnls)
    flag = "  ← ⚠" if wr < 50 else ""
    print(f"  {yr:<4} {strat:<30} {len(pnls):>4} {wr:>5.0f}% {avg:>+8.0f} {tot:>+10.0f}{flag}")

# ─── 2. H1 验证：BPS/BPS_HV 在 SPX < 200MA 的 WR ─────────────────────────────
print(f"\n{'='*80}")
print("§2  H1: BPS / BPS_HV — SPX < 200MA vs SPX ≥ 200MA")

bps_strats = {"Bull Put Spread", "Bull Put Spread (High Vol)"}
bps_above, bps_below = [], []

for t in trades_3yr:
    if t.strategy.value not in bps_strats:
        continue
    entry_ts = pd.Timestamp(t.entry_date)
    if entry_ts not in spx_hist.index:
        continue
    row = spx_hist.loc[entry_ts]
    if pd.isna(row["ma200"]):
        continue
    if row["close"] >= row["ma200"]:
        bps_above.append(t.exit_pnl)
    else:
        bps_below.append(t.exit_pnl)

def fmt_bucket(label, pnls):
    if not pnls:
        print(f"  {label:<38} n=0")
        return
    wr  = sum(1 for p in pnls if p > 0) / len(pnls) * 100
    avg = np.mean(pnls)
    tot = sum(pnls)
    print(f"  {label:<38} n={len(pnls):>3}  WR={wr:>4.0f}%  均={avg:>+7.0f}  总={tot:>+9.0f}")

fmt_bucket("BPS/BPS_HV  SPX ≥ 200MA", bps_above)
fmt_bucket("BPS/BPS_HV  SPX < 200MA  ⚠", bps_below)

saved_pnl = sum(p for p in bps_below if p < 0)  # 若全部改为 REDUCE_WAIT 能避免的损失
print(f"\n  → 若在 SPX < 200MA 时阻断 BPS/BPS_HV（改为 REDUCE_WAIT）：")
print(f"    避免损失: ${-saved_pnl:,.0f}  |  放弃盈利: ${sum(p for p in bps_below if p > 0):,.0f}")

# ─── 3. H2 验证：BCS_HV 在近期 SPX 反弹时的 WR ───────────────────────────────
print(f"\n{'='*80}")
print("§3  H2: BCS_HV — 按入场前 5 日 SPX 涨跌幅分层")

bcs_hv_trades = [t for t in trades_3yr if t.strategy.value == "Bear Call Spread (High Vol)"]
buckets: dict[str, list] = {"< -3%": [], "-3% ~ 0%": [], "0% ~ +3%": [], "> +3%  ⚠反弹": []}

for t in bcs_hv_trades:
    entry_ts = pd.Timestamp(t.entry_date)
    if entry_ts not in spx_hist.index:
        continue
    ret5 = spx_hist.loc[entry_ts, "ret5d"]
    if pd.isna(ret5):
        continue
    if ret5 < -3:
        buckets["< -3%"].append(t.exit_pnl)
    elif ret5 < 0:
        buckets["-3% ~ 0%"].append(t.exit_pnl)
    elif ret5 <= 3:
        buckets["0% ~ +3%"].append(t.exit_pnl)
    else:
        buckets["> +3%  ⚠反弹"].append(t.exit_pnl)

for label, pnls in buckets.items():
    fmt_bucket(f"BCS_HV  ret5d {label}", pnls)

# ─── 4. 出场原因分布 ──────────────────────────────────────────────────────────
print(f"\n{'='*80}")
print("§4  出场原因分布（3年）")
exit_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
for t in trades_3yr:
    exit_counts[t.strategy.value][t.exit_reason] += 1

for strat, reasons in sorted(exit_counts.items()):
    total = sum(reasons.values())
    parts = ", ".join(f"{r}:{n}" for r, n in sorted(reasons.items(), key=lambda x: -x[1]))
    print(f"  {strat:<30} total={total:>3}  [{parts}]")

# ─── 5. 26yr vs 3yr 对比总结 ─────────────────────────────────────────────────
print(f"\n{'='*80}")
print("§5  汇总对比")
print(f"  {'指标':<25} {'26年':>10} {'3年':>10}")
print("-" * 48)
print(f"  {'Total PnL':<25} ${metrics_26yr['total_pnl']:>+9,.0f} ${metrics_3yr['total_pnl']:>+9,.0f}")
print(f"  {'WR':<25} {metrics_26yr['win_rate']*100:>9.1f}% {metrics_3yr['win_rate']*100:>9.1f}%")
print(f"  {'Sharpe':<25} {metrics_26yr['sharpe']:>10.2f} {metrics_3yr['sharpe']:>10.2f}")
print(f"  {'总交易笔数':<25} {len(trades_26yr):>10} {len(trades_3yr):>10}")
avg_hold_26 = np.mean([
    (pd.Timestamp(t.exit_date) - pd.Timestamp(t.entry_date)).days for t in trades_26yr
]) if trades_26yr else 0
avg_hold_3  = np.mean([
    (pd.Timestamp(t.exit_date) - pd.Timestamp(t.entry_date)).days for t in trades_3yr
]) if trades_3yr else 0
print(f"  {'平均持仓天数':<25} {avg_hold_26:>10.1f} {avg_hold_3:>10.1f}")

print("\n完成。")
