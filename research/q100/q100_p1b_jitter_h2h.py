"""Q100 P1b — 补充稳健性：Sleeve B settle-date jitter + Sleeve A 宽度风险轴同尺复核。

P1 主脚本（q100_p1_replay.py）之外的两个 robustness 问题：
  1. B n=5 的 100% WR 是否 settle 日期运气 → DTE 75/90/105 jitter，
     reclaim 与 immediate 两变体都跑；
  2. Q062 当年选 2.5% 的理由是风险指标（WR/MaxDD/Sharpe/consecL）→
     同一事件流、同预算、exit-day 记账下把风险轴摆到同一把尺上
     （worst-21td/63td 窗口、maxConsecL、paired per-event Δ）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "research" / "q100")):
    if p not in sys.path:
        sys.path.insert(0, p)

from pricing.calibration import load_offsets                     # noqa: E402
from q100_p1_replay import build_trades, load_data, replay_a, replay_b  # noqa: E402

OUT = ROOT / "research" / "q100"


def worst_window(tr, close_index, tag="calib", td=21):
    led = tr.groupby("settle_date")[f"pnl_{tag}"].sum()
    led.index = pd.to_datetime(led.index)
    daily = led.reindex(close_index).fillna(0.0)
    return float(daily.rolling(td).sum().min())


def max_consec_loss(tr, tag="calib"):
    best = cur = 0
    for v in (tr.sort_values("signal_date")[f"pnl_{tag}"] < 0).astype(int):
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def main() -> int:
    spx, vix = load_data()
    close = spx["Close"]
    ma10 = close.rolling(10).mean()
    off = load_offsets()

    rows = []
    print("═ Sleeve B settle jitter (CALIB) ═")
    for lbl, imm in (("reclaim", False), ("immediate", True)):
        for dte in (75, 90, 105):
            evs = replay_b(close, ma10, dte=dte, immediate=imm)
            tr = build_trades(evs, spx, vix, 0.05, dte, off)
            rec = {"variant": lbl, "dte": dte,
                   "total_k": round(tr.pnl_calib.sum() / 1000, 1),
                   "wr_pct": round((tr.pnl_calib > 0).mean() * 100),
                   "per_trade_k": [round(p / 1000) for p in tr.pnl_calib]}
            rows.append(rec)
            print(f"  B {lbl:9s} D{dte}: {rec['total_k']:+.1f}k wr {rec['wr_pct']}% {rec['per_trade_k']}")
    pd.DataFrame(rows).to_csv(OUT / "q100_p1b_b_jitter.csv", index=False)

    evs30 = replay_a(close, dte=30)
    t25 = build_trades(evs30, spx, vix, 0.025, 30, off)
    t50 = build_trades(evs30, spx, vix, 0.05, 30, off)
    print("\n═ A width risk axes (same stream/budget, exit-day) ═")
    for lbl, t in (("2.5%/30", t25), ("5%/30", t50)):
        print(f"  {lbl}: worst21td {worst_window(t, close.index)/1000:.1f}k "
              f"worst63td {worst_window(t, close.index, td=63)/1000:.1f}k "
              f"maxConsecL {max_consec_loss(t)} WR {(t.pnl_calib>0).mean()*100:.0f}%")
    d = t50.pnl_calib - t25.pnl_calib
    print(f"  paired Δ(5−2.5): mean {d.mean()/1000:+.2f}k median {d.median()/1000:+.2f}k "
          f"Δ>0 {(d>0).mean()*100:.0f}% worst {d.min()/1000:+.1f}k")
    pair = t25[["signal_date", "ST", "KL", "KS", "pnl_calib"]].rename(
        columns={"KS": "KS_25", "pnl_calib": "pnl_25"}).copy()
    pair[["KS_50", "pnl_50"]] = t50[["KS", "pnl_calib"]].values
    pair["delta"] = pair.pnl_50 - pair.pnl_25
    pair.to_csv(OUT / "q100_p1b_width_paired.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
