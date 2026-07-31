"""Q100 P3 — Sleeve A 触发阈值细网格 sweep + near-miss 队列（PM 挑战触发，2026-07-30）。

挑战：−4% 系 1pp 网格选出，从未测 −3.85/−3.9——"硬线"实为大致范围。
预注册：本 sweep 仅刻画敏感带（高原 vs 悬崖），**禁用于移线**（切点过拟合禁令）。

结论（findings §9）：[−3.5, −4.5] 全域高原（Σ $1,103-1,531k，$/cash-kday 24-32），
相邻 0.05pp 格点差 = 1-2 笔/26y 事件噪音；near-miss（armed 下收盘 [−4, −3.7]
未破线）26 年 4+1 次、21TD 结果 3:1 混合。−4% 官方身份 = 高原上的治理常数
（governance consistency, not statistical optimality——与 SPEC-094.8 同句式）。
年度复检并入 DEFERRED #23（新样本并入重跑）。
"""
import sys
from pathlib import Path

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
    rows = []
    for trig in [-0.035, -0.0375, -0.0385, -0.039, -0.0395, -0.04,
                 -0.0405, -0.041, -0.0425, -0.045]:
        evs = replay_a(close, trig=trig, dte=30)
        tr = build_trades(evs, spx, vix, 0.05, 30, off)
        p20 = tr[tr.year >= 2020]
        rows.append({"trig_pct": trig * 100, "n": len(tr),
                     "total_k": round(tr.pnl_calib.sum() / 1000, 1),
                     "wr_pct": round((tr.pnl_calib > 0).mean() * 100),
                     "per_cash_kday": round(tr.pnl_calib.sum() / (tr.cash_days.sum() / 1000), 2),
                     "post2020_k": round(p20.pnl_calib.sum() / 1000, 1)})
        print(rows[-1])
    import pandas as pd
    pd.DataFrame(rows).to_csv(ROOT / "research" / "q100" / "q100_p3_sweep.csv", index=False)

    # near-miss 队列（armed 下收盘 (−4, −3.7]、spell 未破线、以回 −2% 结束）
    dd = close / close.cummax() - 1
    armed, in_spell, s0, mn = True, False, None, 0.0
    misses = []
    for i in range(len(close)):
        d = dd.iloc[i]
        if not armed and d >= -0.02:
            armed = True
        if armed and d <= -0.04:
            armed, in_spell = False, False
            continue
        if armed and -0.04 < d <= -0.037:
            if not in_spell:
                in_spell, s0, mn = True, i, d
            mn = min(mn, d)
        elif in_spell and d > -0.02:
            misses.append({"date": str(close.index[s0].date()),
                           "spell_min_pct": round(mn * 100, 2),
                           "fwd21_pct": round((close.iloc[min(s0 + 22, len(close) - 1)]
                                               / close.iloc[s0] - 1) * 100, 1)})
            in_spell = False
    for m in misses:
        print("near-miss:", m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
