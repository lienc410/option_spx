"""Q100 P2 — 执行时点分析（2026-07-30 near-miss 复盘 + GPT quant 提案的终局回答）。

背景：07-29 盘中穿越 −4% 线、收盘 −3.86% 未触发；次日 +1.5%。外部 quant 提案
"Execution Timing" 研究线（gap 分层 / T+1 open vs close / gap filter）。
本脚本 = 全部可测格子的一次性回答；结论：效应量不支持立项。

三个发现（37 触发，5%/30，CALIB，等预算）：
  1. T+1 开盘 gap 分布：median +0.03% / max +0.67% —— ">1% gap" 触发史零次
     （提案的 Group C 为空集；真触发收在低位区，暴力高开只发生在非信号日后）。
  2. gap 分层单调向好（≤0%: WR47% / 0-0.5%: 78% / 0.5-1%: 100%）——
     高开=动量确认；gap filter 会删掉最好 cohort（E2 家族 + 提案者自己的
     selection-bias 警告，双重反对）。
  3. 执行时点杠杆宽度 2.4%：T+1-close 锚定（晚一天）Σ1311k vs 现行 1343k。
     【口径（外审要求写明）】锚定变体 = T+1 收盘重定 ATM/+5%、同 30DTE、
     锚定日 close/VIX CALIB 定价、T+2 入场——完全重锚非沿用原 strikes；
     n=12 子集同口径。此口径亦为"漏一天"的 recovery rule 依据。
     场景类比：T+1 日涨 ≥1% 后 T+2 进场 n=12，Σ+352k WR67%（对照跳过 $0）
     —— 真触发后晚一天+涨过 1% 仍应进。
  未测且不测：VWAP/日内分批（需日内数据；SPEC-030 已证日内层提前率 0%，
  为 2.4% 宽的杠杆采购日内数据 = 负 ROI）。
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "research" / "q100")):
    if p not in sys.path:
        sys.path.insert(0, p)

from pricing.calibration import load_offsets            # noqa: E402
from q100_p1_replay import build_trades, load_data, replay_a  # noqa: E402


def main() -> int:
    spx, vix = load_data()
    close = spx["Close"]
    off = load_offsets()
    evs = replay_a(close, dte=30)
    tr = build_trades(evs, spx, vix, 0.05, 30, off)
    g = tr.gap_t1_pct * 100
    print(f"gap: median {g.median():+.2f}% p90 {g.quantile(.9):+.2f}% max {g.max():+.2f}%")
    for lo, hi, lbl in [(-99, 0, '≤0%'), (0, .5, '0-0.5%'), (.5, 1, '0.5-1%'), (1, 99, '>1%')]:
        s = tr[(g > lo) & (g <= hi)] if lo != -99 else tr[g <= hi]
        print(f"  {lbl:8s} n={len(s):2d} Σ{s.pnl_calib.sum()/1000:+8.1f}k "
              f"WR {(s.pnl_calib > 0).mean()*100 if len(s) else 0:3.0f}%")
    evs_t1c = [{**e, "sig_i": e["sig_i"] + 1, "ent_i": e["ent_i"] + 1,
                "expiry_date": close.index[e["sig_i"] + 1] + pd.Timedelta(days=31)}
               for e in evs if e["sig_i"] + 1 < len(close)]
    tr2 = build_trades(evs_t1c, spx, vix, 0.05, 30, off)
    print(f"T+1-close 锚: Σ{tr2.pnl_calib.sum()/1000:+.1f}k vs 现行 Σ{tr.pnl_calib.sum()/1000:+.1f}k")
    rows = []
    for e in evs:
        si, ei = e["sig_i"], e["ent_i"]
        if ei + 1 >= len(close):
            continue
        if close.iloc[ei] / close.iloc[si] - 1 < 0.01:
            continue
        t = build_trades([{"sig_i": ei, "ent_i": ei + 1,
                           "expiry_date": close.index[ei] + pd.Timedelta(days=31)}],
                         spx, vix, 0.05, 30, off)
        if len(t):
            rows.append({"signal": str(close.index[si].date()),
                         "pnl_k": round(t.iloc[0].pnl_calib / 1000, 1)})
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "research" / "q100" / "q100_p2_day1pop_t2.csv", index=False)
    print(f"day1≥+1% → T+2 进: n={len(df)} Σ{df.pnl_k.sum():+.1f}k WR {(df.pnl_k > 0).mean()*100:.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
