"""Q102 P2 — Confirmatory：候选门槛判定（P1 预注册 §5 的执行）。

P1 自审（ruler audit 四问）发现三处尺子问题，本 phase 先修再判：
  A1 指数基准漏股息 → 基准加 1.8%/yr 总回报修正（SPX 长期股息率，常数近似；
     方向不利于期权候选 = 保守）。
  A2 LEAP 候选②限定深档（≤−25%）但 P1 T4 是全 rung 汇总 → 深档子集单独 vs 基准。
  A3 spread 候选未做 settle jitter（Q100 揭示 B 类 n 小对结算日敏感）→ D75/90/105。

预注册门槛（P1 §5.2 原文，不动）：
  G1 候选必须在 CALIB 与 STRESS（spread）/两括号端（LEAP）**同时** ≥ 指数基准
     （同入场日、同预算、同持有期、含股息）。
  G2 阈值零拟合复查（rungs 10pp 结构步长 / stop=rung 线 / K=0.85S 股票替代惯例 /
     re-arm −2% 继承）——本文件只消费 P1 已申明的值。
  G3 现金叠栈规则先于 promote 写死（→ findings §落地设计）。

候选（P1 §5.1）：
  C1 ladder-immediate × 持有 × 5%/90 spread（全 rung）
  C1s ladder-immediate × rung-stop × 5%/90（全 rung）——P1 已见 STRESS 弱，正式判
  C2 深档（≤−25%）ITM85 LEAP 365d（XSP 落地），无 stop
  附验：LEAP 730d（P1 局限项）；浅档（−15 单档）immediate spread 子集单判
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "research" / "q100"), str(ROOT / "research" / "q102")):
    if p not in sys.path:
        sys.path.insert(0, p)

from pricing import core as pcore                      # noqa: E402
from pricing.calibration import load_offsets           # noqa: E402
from q100_p1_replay import load_data                   # noqa: E402
from q102_p1_b_redesign import (                       # noqa: E402
    BUDGET, COMM, Q_DIV, R, RUNGS, SLIP, ladder_entries, run_spread,
)

OUT = ROOT / "research" / "q102"
DIV_YR = 0.018          # A1: 指数总回报修正（常数近似，findings 披露）


def run_index_tr(ev, close, dte):
    """指数基准（含股息 1.8%/yr 线性加成）。"""
    dates = close.index
    ei = ev["ent_i"]
    sp = dates.searchsorted(dates[ev["sig_i"]] + pd.Timedelta(days=1 + dte))
    if sp >= len(close):
        return None
    S0, ST = float(close.iloc[ei]), float(close.iloc[sp])
    yrs = (dates[sp] - dates[ei]).days / 365.25
    pnl = BUDGET * (ST / S0 - 1 + DIV_YR * yrs)
    return {"rung": ev["rung"], "signal": str(dates[ev["sig_i"]].date()),
            "pnl": round(pnl, 0)}


def run_leap(ev, close, vix_s, dte, vol_mult, k_ratio=0.85):
    dates = close.index
    si, ei = ev["sig_i"], ev["ent_i"]
    sp = dates.searchsorted(dates[si] + pd.Timedelta(days=1 + dte))
    if sp >= len(close):
        return None
    S = float(close.iloc[si])
    vx = float(vix_s.iloc[si]) * vol_mult
    K = round(S * k_ratio / 5) * 5
    deb = pcore.call_price(S, K, dte / 365.0, max(vx / 100.0, 0.01), R, q=Q_DIV)
    fill = deb * (1 + SLIP)
    cts = BUDGET / (fill * 100.0)
    ST = float(close.iloc[sp])
    pnl = (max(ST - K, 0.0) - fill) * 100.0 * cts - COMM * cts
    return {"rung": ev["rung"], "signal": str(dates[si].date()),
            "pnl": round(pnl, 0), "debit": round(deb, 1)}


def gate_line(label, cand_vals, bench, n):
    ok = all(v >= bench for v in cand_vals)
    vals = " / ".join(f"{v/1000:+.1f}k" for v in cand_vals)
    print(f"  {label:38s} [{vals}] vs 基准 {bench/1000:+.1f}k  n={n}  "
          f"→ {'✅ PASS' if ok else '❌ FAIL'}")
    return ok


def main() -> int:
    spx, vix_s = load_data()
    close = spx["Close"]
    ma10 = close.rolling(10).mean()
    dd = close / close.cummax() - 1.0
    off = load_offsets()
    ev_im = ladder_entries(close, ma10, mode="immediate")
    deep = [e for e in ev_im if e["rung"] <= -0.25]
    shallow = [e for e in ev_im if e["rung"] == -0.15]

    def spread_totals(evs, exit_rule, dte=90):
        rows = [run_spread(e, close, vix_s, ma10, dd, off, dte=dte,
                           exit_rule=exit_rule, mode="immediate") for e in evs]
        rows = [r for r in rows if r]
        df = pd.DataFrame(rows)
        return df.pnl_calib.sum(), df.pnl_stress.sum(), len(df), df

    def index_total(evs, dte):
        rows = [run_index_tr(e, close, dte) for e in evs]
        return sum(r["pnl"] for r in rows if r), sum(1 for r in rows if r)

    def leap_totals(evs, dte):
        out = {}
        for vm in (0.75, 1.0):
            rows = [run_leap(e, close, vix_s, dte, vm) for e in evs]
            out[vm] = sum(r["pnl"] for r in rows if r)
        return out, sum(1 for r in (run_leap(e, close, vix_s, dte, 1.0) for e in evs) if r)

    print("═ G1 门槛判定（基准含股息） ═")
    results = {}

    bench90_all, n90 = index_total(ev_im, 90)
    c1 = spread_totals(ev_im, "X0")
    results["C1 全rung spread×持有"] = gate_line(
        "C1 ladder×持有×5%/90（全 rung）", c1[:2], bench90_all, c1[2])
    c1s = spread_totals(ev_im, "X1")
    results["C1s 全rung spread×rung-stop"] = gate_line(
        "C1s ladder×rung-stop×5%/90（全 rung）", c1s[:2], bench90_all, c1s[2])

    bench90_sh, _ = index_total(shallow, 90)
    csh = spread_totals(shallow, "X0")
    results["C1a 浅档 spread×持有"] = gate_line(
        "C1a 浅档(−15)×持有×5%/90", csh[:2], bench90_sh, csh[2])
    cshs = spread_totals(shallow, "X1")
    results["C1as 浅档 spread×stop"] = gate_line(
        "C1as 浅档(−15)×rung-stop×5%/90", cshs[:2], bench90_sh, cshs[2])

    bench90_dp, _ = index_total(deep, 90)
    cdp = spread_totals(deep, "X0")
    results["C1b 深档 spread×持有"] = gate_line(
        "C1b 深档(≤−25)×持有×5%/90", cdp[:2], bench90_dp, cdp[2])

    bench365_dp, nl = index_total(deep, 365)
    l365, _ = leap_totals(deep, 365)
    results["C2 深档 LEAP ITM85 365d"] = gate_line(
        "C2 深档 ITM85 LEAP 365d（两括号端）", [l365[0.75], l365[1.0]], bench365_dp, nl)
    l730, n730 = leap_totals(deep, 730)
    bench730_dp, _ = index_total(deep, 730)
    results["C2b 深档 LEAP ITM85 730d"] = gate_line(
        "C2b 深档 ITM85 LEAP 730d（两括号端）", [l730[0.75], l730[1.0]], bench730_dp, n730)

    # 浅档 LEAP 反证（PM thesis 限定深跌；确认浅档不冤枉）
    bench365_sh, _ = index_total(shallow, 365)
    lsh, _ = leap_totals(shallow, 365)
    gate_line("（参考）浅档 ITM85 LEAP 365d", [lsh[0.75], lsh[1.0]], bench365_sh, len(shallow))

    # ═ A3 settle jitter：通过 G1 的 spread 候选做 D75/90/105 ═
    print("\n═ A3 settle jitter（immediate×持有, 全 rung） ═")
    for dte in (75, 90, 105):
        t = spread_totals(ev_im, "X0", dte=dte)
        b, _ = index_total(ev_im, dte)
        print(f"  D{dte}: calib {t[0]/1000:+.1f}k stress {t[1]/1000:+.1f}k vs 基准 {b/1000:+.1f}k "
              f"→ {'✅' if t[0] >= b and t[1] >= b else '❌'}")

    # ═ 深档 LEAP per-event（落地视角：XSP 换算 + 最坏情形） ═
    print("\n═ C2 深档 LEAP ITM85 365d per-event（×0.75 | ×1.0） ═")
    for e in deep:
        r75 = run_leap(e, close, vix_s, 365, 0.75)
        r10 = run_leap(e, close, vix_s, 365, 1.0)
        b = run_index_tr(e, close, 365)
        if r75:
            print(f"  rung {e['rung']*100:+.0f}% {r75['signal']}: LEAP {r75['pnl']/1000:+6.1f}k | "
                  f"{r10['pnl']/1000:+6.1f}k  vs 指数 {b['pnl']/1000:+6.1f}k  "
                  f"(debit@0.75 {r75['debit']}/sh)")
    pd.DataFrame([{"cand": k, "pass": v} for k, v in results.items()]).to_csv(
        OUT / "q102_p2_gates.csv", index=False)
    print("\n═ 门槛判定汇总 ═")
    for k, v in results.items():
        print(f"  {'✅' if v else '❌'} {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
