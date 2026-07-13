"""Q101 E1b — 摩擦入模 + 配对推断（framing 判定标准的执行件）。

摩擦：按腿半价差实测（2026-07-06 链，35-55DTE，δ 桶中位）× aftermath 倍数 F∈{1,2}；
入场+出场各收一次。配对：C2/C3/C4 vs C1 按共同入场日配对，paired t；
C1 vs cash 在最悲观角落（SKEW2×F2）做单样本检验 + MDE。
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "q101"))
import q101_e1_structures as m  # noqa: E402

# 实测半价差（$/腿，kind→[(δ, hs)]，线性插值；出处见本文件 docstring）
HS = {"C": [(0.04, 0.20), (0.08, 0.22), (0.12, 0.27), (0.16, 0.25), (0.20, 0.25)],
      "P": [(0.04, 0.20), (0.08, 0.35), (0.12, 0.45), (0.16, 0.40), (0.20, 0.45)]}

def leg_hs(kind, delta):
    pts = HS[kind]
    return float(np.interp(delta, [p[0] for p in pts], [p[1] for p in pts]))

def friction(legs, F):
    """入场+出场各一次半价差，$/share。"""
    return 2.0 * F * sum(leg_hs(k, dl) for _, k, _, dl in legs)

def main():
    spx, vix_h = m.load_spx_history(), m.load_vix_history()
    dates = sorted(set(spx) & set(vix_h))
    dates = [d for d in dates if d >= "2000-01-01"]
    darr = np.array(dates)
    vixs = pd.Series([vix_h[d] for d in dates], index=dates)
    peak10 = vixs.rolling(10, min_periods=10).max()
    from types import SimpleNamespace
    flags = pd.Series([bool(m.is_aftermath(SimpleNamespace(
        vix=vix_h[d], vix_peak_10d=(None if pd.isna(peak10[d]) else float(peak10[d]))),
        m.DEFAULT_PARAMS)) for d in dates], index=dates)
    curves = m.load_skew_curves()

    def run(cname, scale):
        legs = m.CANDS[cname]
        trades, busy = [], ""
        for i, d in enumerate(dates):
            if not flags[d] or d <= busy:
                continue
            t = m.simulate(d, spx, vix_h, legs, curves, scale, darr)
            if t:
                t["fric100"] = friction(legs, 1.0) * 100
                trades.append(t)
                busy = t["exit"]
        return pd.DataFrame(trades).set_index("entry")

    ARMS = {"FLAT": 0.0, "SKEW1": 1.0, "SKEW2": 2.0}
    rows = []
    store = {}
    for arm, scale in ARMS.items():
        for c in m.CANDS:
            store[(arm, c)] = run(c, scale)

    print("=== 配对 vs C1（共同入场日；净=扣摩擦后；F=aftermath 摩擦倍数） ===")
    for arm in ARMS:
        base = store[(arm, "C1_V3A_broken")]
        for ch in ("C2_IC_HV_sym", "C3_BPS_HV", "C4_BCS_HV"):
            t = store[(arm, ch)]
            common = base.index.intersection(t.index)
            if len(common) < 10:
                continue
            for F in (1.0, 2.0):
                d = ((t.loc[common, "pnl"] - F * t.loc[common, "fric100"])
                     - (base.loc[common, "pnl"] - F * base.loc[common, "fric100"]))
                tstat = d.mean() / (d.std(ddof=1) / np.sqrt(len(d))) if d.std(ddof=1) > 0 else 0
                rows.append({"arm": arm, "challenger": ch, "F": F, "n_pair": len(d),
                             "mean_diff$": round(d.mean()), "t": round(tstat, 2),
                             "win_share%": round(100 * (d > 0).mean())})
    pr = pd.DataFrame(rows)
    print(pr.to_string(index=False))
    pr.to_csv(ROOT / "research/q101/q101_e1b_paired.csv", index=False)

    print("\n=== C1 vs cash：净期望（扣摩擦）各制度 ===")
    for arm in ARMS:
        base = store[(arm, "C1_V3A_broken")]
        for F in (1.0, 2.0):
            net = base["pnl"] - F * base["fric100"]
            tstat = net.mean() / (net.std(ddof=1) / np.sqrt(len(net)))
            mde = 2.8 * net.std(ddof=1) / np.sqrt(len(net))   # 80%功效近似
            print(f"{arm} F{F:.0f}: n={len(net)} 净均值 ${net.mean():,.0f} t={tstat:.2f} "
                  f"MDE≈${mde:,.0f} 总净 ${net.sum():,.0f}")

    print("\n=== 各候选净均值一览（SKEW1×F2 = 现实主义中枢） ===")
    for c in m.CANDS:
        b = store[("SKEW1", c)]
        net = b["pnl"] - 2.0 * b["fric100"]
        print(f"{c}: n={len(net)} 净均值 ${net.mean():,.0f} 净总 ${net.sum():,.0f} "
              f"净CVaR10 ${net.nsmallest(max(1, int(0.1*len(net)))).mean():,.0f}")

if __name__ == "__main__":
    main()
