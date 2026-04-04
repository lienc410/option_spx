"""
SPEC-016 Prototype — Realism Haircut & Strategy Re-ranking
对每个策略族分别估算 Precision B 乐观偏差，应用 haircut 后重新排名。

偏差来源：
1. IV Bias: sigma = 当日 VIX（非锁定 IV）。
   SPX 上涨时 VIX 下降，short put 自动获 vega 收益 → BPS 偏乐观。
   SPX 下跌时 VIX 上升，short call 自动获 vega 收益 → BCS 偏乐观。
   Diagonal（long vega）：SPX 上涨 → VIX 下降 → long call vega 损失 → 偏悲观。

2. Bid-Ask / Slippage: SPX 期权宽幅约 $0.5–1.5/leg。
   每笔交易额外成本 = 腿数 × bid/ask_half × 100。

3. 资金成本（PM margin）：持仓期 BP 占用的机会成本。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd
from backtest.engine import run_backtest, compute_metrics

# ─── 1. 运行 26yr 回测获取各策略基础数据 ─────────────────────────────────────

print("加载 26yr 回测数据...")
trades, metrics, _ = run_backtest(start_date="2000-01-01", verbose=False)
print(f"完成: {len(trades)} 笔交易")
print()

# ─── 2. 按策略族分组 ──────────────────────────────────────────────────────────

from collections import defaultdict

strat_trades = defaultdict(list)
for t in trades:
    strat_trades[t.strategy.value].append(t)

# 策略族映射到偏差参数
STRAT_CONFIG = {
    "Bull Put Spread (High Vol)": {
        "legs": 2,
        "vega_bias": "short_vega_bullish",  # SPX 涨 → VIX 跌 → short put 自动盈利（过乐观）
        "vega_haircut": 0.12,               # estimated: 12% of avg PnL overstatement
        "ba_per_leg": 75,                   # $75/leg bid-ask slippage (SPX wide in HV)
        "description": "SHORT PUT SPREAD — HV: VIX 下跌时 short put vega 自动盈利",
    },
    "Bull Put Spread": {
        "legs": 2,
        "vega_bias": "short_vega_bullish",
        "vega_haircut": 0.10,
        "ba_per_leg": 50,
        "description": "SHORT PUT SPREAD — Normal: 同上，VIX 正常水平幅度较小",
    },
    "Bear Call Spread (High Vol)": {
        "legs": 2,
        "vega_bias": "short_vega_bearish",  # SPX 跌 → VIX 涨 → short call vega 自动盈利（过乐观）
        "vega_haircut": 0.12,
        "ba_per_leg": 75,
        "description": "SHORT CALL SPREAD — HV: VIX 上涨时 short call vega 自动盈利",
    },
    "Iron Condor": {
        "legs": 4,
        "vega_bias": "short_vega_symmetric",  # 双边 short，VIX 变化部分抵消
        "vega_haircut": 0.08,
        "ba_per_leg": 40,
        "description": "SHORT IRON CONDOR: 双边 short vega，部分抵消，偏差较小",
    },
    "Iron Condor (High Vol)": {
        "legs": 4,
        "vega_bias": "short_vega_symmetric",
        "vega_haircut": 0.08,
        "ba_per_leg": 60,
        "description": "SHORT IC HV: 同 IC，HV 期 spread 更宽",
    },
    "Bull Call Diagonal": {
        "legs": 2,
        "vega_bias": "long_vega_bullish",  # long vega：SPX 上涨 → VIX 下跌 → HURT（偏悲观）
        "vega_haircut": -0.10,             # 负值 = 回测比实际更悲观（实际可能更好）
        "ba_per_leg": 60,                  # diagonal: bid-ask on both back and front month
        "description": "LONG DIAGONAL: NET LONG VEGA，回测因 VIX 联动偏悲观",
    },
    "Bear Call Diagonal": {
        "legs": 2,
        "vega_bias": "long_vega_bearish",
        "vega_haircut": -0.10,
        "ba_per_leg": 60,
        "description": "LONG DIAGONAL (bear): 同上，回测偏悲观",
    },
}

# PM 资金成本（年化 5%，按持仓天数计算）
MARGIN_RATE = 0.05  # 5% annual opportunity cost on BP used

print("=" * 65)
print("  REALISM HAIRCUT — 各策略偏差估算")
print("=" * 65)

results = {}
for strat, ts in strat_trades.items():
    if strat not in STRAT_CONFIG:
        continue
    cfg = STRAT_CONFIG[strat]

    raw_pnl      = sum(t.exit_pnl for t in ts)
    raw_rom_list = [t.rom_annualized for t in ts if t.total_bp > 0]
    avg_raw_rom  = np.mean(raw_rom_list) if raw_rom_list else 0
    avg_hold     = np.mean([t.hold_days for t in ts]) if ts else 14

    # IV vega bias haircut（正 = 乐观，负 = 悲观）
    vega_adjust  = -cfg["vega_haircut"] * raw_pnl   # 正 haircut = 减少收益

    # Bid-Ask slippage：腿数 × 每腿成本 × 合约数
    ba_per_trade = cfg["legs"] * cfg["ba_per_leg"]
    avg_contracts = np.mean([t.contracts for t in ts]) if ts else 1.0
    ba_total     = ba_per_trade * avg_contracts * len(ts)

    # 资金成本：total_bp × 年化率 × hold_days/365
    margin_cost  = sum(
        t.total_bp * MARGIN_RATE * t.hold_days / 365
        for t in ts if t.total_bp > 0
    )

    adj_pnl      = raw_pnl + vega_adjust - ba_total - margin_cost

    # 调整后 ROM（用 adj_pnl / raw_pnl 的比例缩放）
    scale        = adj_pnl / raw_pnl if raw_pnl != 0 else 1.0
    adj_rom_avg  = avg_raw_rom * scale

    results[strat] = {
        "n":             len(ts),
        "raw_pnl":       raw_pnl,
        "vega_adjust":   vega_adjust,
        "ba_cost":       -ba_total,
        "margin_cost":   -margin_cost,
        "adj_pnl":       adj_pnl,
        "haircut_pct":   (1 - scale) * 100,
        "avg_raw_rom":   avg_raw_rom,
        "adj_rom_avg":   adj_rom_avg,
        "avg_hold":      avg_hold,
        "vega_bias":     cfg["vega_bias"],
    }

    print(f"\n  {strat}")
    print(f"    n={len(ts)}  raw_pnl=${raw_pnl:+,.0f}  avg_raw_rom={avg_raw_rom:+.3f}")
    print(f"    vega adjust : ${vega_adjust:+,.0f}  ({cfg['vega_haircut']*100:+.0f}% haircut)")
    print(f"    bid-ask cost: ${-ba_total:+,.0f}  ({cfg['legs']} legs × ${cfg['ba_per_leg']}/leg)")
    print(f"    margin cost : ${-margin_cost:+,.0f}")
    print(f"    adj_pnl     : ${adj_pnl:+,.0f}  (haircut {(1-scale)*100:.0f}%)")
    print(f"    adj_rom_avg : {adj_rom_avg:+.3f}")

# ─── 3. 排名对比 ──────────────────────────────────────────────────────────────

print("\n\n" + "=" * 65)
print("  排名对比：Raw ROM vs Adjusted ROM")
print("=" * 65)

sorted_raw = sorted(results.items(), key=lambda x: -x[1]["avg_raw_rom"])
sorted_adj = sorted(results.items(), key=lambda x: -x[1]["adj_rom_avg"])

print(f"\n  {'策略':<30} {'Raw ROM':>10} {'Adj ROM':>10} {'Raw排名':>8} {'Adj排名':>8}")
print("  " + "-" * 70)

raw_rank = {s: i+1 for i, (s, _) in enumerate(sorted_raw)}
adj_rank = {s: i+1 for i, (s, _) in enumerate(sorted_adj)}

for strat, v in sorted_adj:
    shift = raw_rank[strat] - adj_rank[strat]
    arrow = f"↑{shift}" if shift > 0 else (f"↓{-shift}" if shift < 0 else "—")
    print(f"  {strat:<30} {v['avg_raw_rom']:>+10.3f} {v['adj_rom_avg']:>+10.3f} "
          f"#{raw_rank[strat]:>3}→#{adj_rank[strat]:<3} {arrow}")

# ─── 4. 关键发现 ──────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("  关键发现")
print("=" * 65)

# Diagonal 方向
diag_keys = [k for k in results if "Diagonal" in k]
credit_keys = [k for k in results if "Diagonal" not in k]

print(f"\n  Diagonal 策略（long vega）:")
for k in diag_keys:
    v = results[k]
    print(f"    {k}: raw_rom={v['avg_raw_rom']:+.3f} → adj_rom={v['adj_rom_avg']:+.3f}")
    print(f"      → 回测偏悲观（VIX 联动导致 vega 损失被高估）")

print(f"\n  Credit 策略（short vega）:")
for k in credit_keys:
    if k in results:
        v = results[k]
        print(f"    {k}: raw_rom={v['avg_raw_rom']:+.3f} → adj_rom={v['adj_rom_avg']:+.3f}")

print("\n  排名关键变化:")
for strat in adj_rank:
    shift = raw_rank[strat] - adj_rank[strat]
    if abs(shift) >= 2:
        print(f"    {strat}: 排名 #{raw_rank[strat]} → #{adj_rank[strat]}（{'+' if shift>0 else ''}{shift}）")
