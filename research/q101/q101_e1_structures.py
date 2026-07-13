"""Q101 E1 — aftermath 结构独立复审（预注册 q101_framing.md）。

窗口真值 = 生产 is_aftermath 直调（构造 snapshot；探针校准 vs q064_p1 flags）。
候选腿 = 产码/catalog 逐字。双定价臂：FLAT（逐字复现 Q064 口径）与
SKEW(S∈{1,2})（实测 calm skew 外推 + aftermath 陡化 bracket）。
出场统一 60%/DTE21。指标包含等 BP $/BP-day 与时代切片。
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "q082"))
from q082_p6_bcd_synth_reconstruction import load_spx_history, load_vix_history  # noqa: E402
from strategy.selector import is_aftermath, DEFAULT_PARAMS  # noqa: E402

R = 0.04
POLLUTED = {"2026-07-06"}   # H-1（宪法：污染日隔离）

# ── 定价基元（Q064 同款约定：T=dte/365, term_mult, σ 下限） ────────────────────
def term_multiplier(dte: int) -> float:
    if dte <= 45:
        return 1.10
    if dte <= 120:
        return 1.00
    return 0.95

def bs_price(S, K, T, sigma, kind):
    if T <= 0:
        return max(S - K, 0.0) if kind == "C" else max(K - S, 0.0)
    d1 = (math.log(S / K) + (R + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if kind == "C":
        return S * norm.cdf(d1) - K * math.exp(-R * T) * norm.cdf(d2)
    return K * math.exp(-R * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def strike_for_delta(S, T, sigma, delta, kind):
    """N(d1)=delta (call) / N(d1)=1-|delta| (put)，解 K（Q064 同式）。"""
    nd1 = delta if kind == "C" else 1.0 - delta
    d1 = norm.ppf(nd1)
    return S * math.exp((R + 0.5 * sigma**2) * T - d1 * sigma * math.sqrt(T))

# ── 实测 skew 曲线（monitor 中位，δ 分段线性 + 末段斜率外推） ───────────────────
def load_skew_curves() -> dict:
    rows = []
    for src in (ROOT / "data" / "q085_skew_monitor.jsonl",
                ROOT / "research" / "q087" / "q087_moff_backfill.jsonl"):
        if src.exists():
            for l in src.read_text().splitlines():
                if not l.strip():
                    continue
                r = json.loads(l)
                if str(r.get("date")) not in POLLUTED:
                    rows.append(r)
    df = pd.DataFrame(rows)
    med = lambda c: float(df[c].dropna().median()) if c in df else None
    # put 侧：atm(δ.50) → d30(δ.30) → d15(δ.15)；call 侧：atm → c30 → c16 → c08
    put_pts = [(0.50, med("atm_moff")), (0.30, med("d30_moff")), (0.15, med("d15_moff"))]
    call_pts = [(0.50, med("atm_moff")), (0.30, med("c30_moff")),
                (0.16, med("c16_moff")), (0.08, med("c08_moff"))]
    put_pts = [(d, o) for d, o in put_pts if o is not None]
    call_pts = [(d, o) for d, o in call_pts if o is not None]
    assert len(put_pts) >= 3 and len(call_pts) >= 3, "skew 数据不足"
    return {"P": sorted(put_pts), "C": sorted(call_pts)}

def off_at(curves, kind, delta):
    pts = curves["P" if kind == "P" else "C"]
    ds = [p[0] for p in pts]; os_ = [p[1] for p in pts]
    if delta <= ds[0]:   # 比最远测点更远 → 沿末段斜率外推
        slope = (os_[1] - os_[0]) / (ds[1] - ds[0])
        return os_[0] + slope * (delta - ds[0])
    return float(np.interp(delta, ds, os_))

def sigma_leg(vix, dte, kind, delta, curves, slope_scale):
    base = max(vix, 10.0)
    off = off_at(curves, kind, delta) * slope_scale if slope_scale > 0 else 0.0
    return max((base + off) / 100.0, 0.05) * term_multiplier(dte)

# ── 候选结构（腿 = 产码/catalog 逐字；(side, kind, dte, delta)） ───────────────
CANDS = {
    "C1_V3A_broken":  [("S","C",45,0.12), ("B","C",45,0.04), ("S","P",45,0.12), ("B","P",45,0.08)],
    "C2_IC_HV_sym":   [("S","C",45,0.16), ("B","C",45,0.08), ("S","P",45,0.16), ("B","P",45,0.08)],
    "C3_BPS_HV":      [("S","P",35,0.20), ("B","P",35,0.10)],
    "C4_BCS_HV":      [("S","C",45,0.20), ("B","C",45,0.10)],
}

def simulate(entry_iso, spx, vix_h, legs, curves, slope_scale, dates_arr):
    """一笔：入场定 strikes+credit → 逐日重定价 → 60%/DTE21 出场。"""
    S0, v0 = spx[entry_iso], vix_h[entry_iso]
    dte0 = max(l[2] for l in legs)
    solved = []
    credit = 0.0
    for side, kind, dte, delta in legs:
        sg = sigma_leg(v0, dte, kind, delta, curves, slope_scale)
        K = round(strike_for_delta(S0, dte / 365.0, sg, delta, kind) / 5) * 5
        px = bs_price(S0, K, dte / 365.0, sg, kind)
        solved.append((side, kind, dte, delta, K))
        credit += px if side == "S" else -px
    if credit <= 0:
        return None
    # BP：IC=max 翼宽，单 spread=宽度
    puts = sorted([K for s, k, d, dl, K in solved if k == "P"])
    calls = sorted([K for s, k, d, dl, K in solved if k == "C"])
    pw = (puts[-1] - puts[0]) if len(puts) == 2 else 0.0
    cw = (calls[-1] - calls[0]) if len(calls) == 2 else 0.0
    bp = max(pw, cw) * 100.0
    if bp <= 0:
        return None
    i0 = int(np.searchsorted(dates_arr, entry_iso))
    for i in range(i0 + 1, min(i0 + 40, len(dates_arr))):
        d = dates_arr[i]
        if d not in spx or d not in vix_h:
            continue
        held = i - i0                      # 交易日；DTE 按日历近似 = held*7/5
        cal_held = int(round(held * 7 / 5))
        rem = dte0 - cal_held
        S, v = spx[d], vix_h[d]
        cost = 0.0
        for side, kind, dte, delta, K in solved:
            rem_leg = max(dte - cal_held, 0)
            sg = sigma_leg(v, max(rem_leg, 1), kind, delta, curves, slope_scale)
            px = bs_price(S, K, rem_leg / 365.0, sg, kind)
            cost += px if side == "S" else -px
        captured = (credit - cost) / credit
        if captured >= 0.60 or rem <= 21:
            return {"entry": entry_iso, "exit": d, "hold_td": held,
                    "credit": credit * 100, "pnl": (credit - cost) * 100,
                    "bp": bp, "dpbd": (credit - cost) * 100 / bp / max(held, 1)}
    return None

def main():
    spx, vix_h = load_spx_history(), load_vix_history()
    dates = sorted(set(spx) & set(vix_h))
    dates = [d for d in dates if d >= "2000-01-01"]
    darr = np.array(dates)
    vixs = pd.Series([vix_h[d] for d in dates], index=dates)
    peak10 = vixs.rolling(10, min_periods=10).max()      # 含当日，同 Q064 P1
    flags = []
    for d in dates:
        snap = SimpleNamespace(vix=vix_h[d], vix_peak_10d=(None if pd.isna(peak10[d]) else float(peak10[d])))
        flags.append(bool(is_aftermath(snap, DEFAULT_PARAMS)))
    flags = pd.Series(flags, index=dates)

    # 探针校准：vs q064_p1 flags（v1.2 规则）
    q064 = pd.read_csv(ROOT / "research/q064/q064_p1_daily_flags.csv", parse_dates=["date"])
    q064["d"] = q064["date"].dt.date.astype(str)
    both = q064[q064["d"].isin(flags.index)]
    agree = (both.set_index("d")["is_aftermath"].astype(bool) == flags.loc[both["d"]].values).mean()
    print(f"探针校准 vs q064_p1: 一致率 {agree:.3%}（n={len(both)}）")
    assert agree > 0.98, "窗口旗标与 q064 P1 分歧过大——先查数据源"

    # 入场日：窗口首日 + 出场后窗口仍开则再入（按各候选独立 busy-lock）
    starts = [d for i, d in enumerate(dates)
              if flags[d] and (i == 0 or not flags[dates[i - 1]])]
    print(f"aftermath 窗口数（首日入场基）: {len(starts)}")

    curves = load_skew_curves()
    print("skew 曲线（中位）:", {k: [(round(d, 2), round(o, 2)) for d, o in v]
                              for k, v in curves.items()})

    ARMS = {"FLAT": 0.0, "SKEW1": 1.0, "SKEW2": 2.0}
    ERAS = [("full", "2000", "2100"), ("2008-09", "2008", "2010"), ("2011", "2011", "2012"),
            ("2020", "2020", "2021"), ("2022", "2022", "2023"), ("2020+", "2020", "2100")]
    out_rows = []
    for arm, scale in ARMS.items():
        for cname, legs in CANDS.items():
            trades = []
            busy = ""
            for i, d in enumerate(dates):
                if not flags[d] or d <= busy:
                    continue
                if d in starts or (busy and flags[d]):   # 首日或出场后窗口未闭
                    t = simulate(d, spx, vix_h, legs, curves, scale, darr)
                    if t:
                        trades.append(t)
                        busy = t["exit"]
            tdf = pd.DataFrame(trades)
            if tdf.empty:
                continue
            for era, lo, hi in ERAS:
                w = tdf[(tdf.entry >= lo) & (tdf.entry < hi)]
                if not len(w):
                    continue
                k = max(1, int(0.10 * len(w)))
                out_rows.append({
                    "arm": arm, "cand": cname, "era": era, "n": len(w),
                    "mean$": round(w.pnl.mean()), "total$": round(w.pnl.sum()),
                    "worst$": round(w.pnl.min()), "cvar10$": round(w.pnl.nsmallest(k).mean()),
                    "win%": round(100 * (w.pnl > 0).mean()),
                    "dpbd": round(w.dpbd.mean(), 4),
                    "med_credit$": round(w.credit.median()),
                })
    res = pd.DataFrame(out_rows)
    res.to_csv(ROOT / "research/q101/q101_e1_results.csv", index=False)
    pd.set_option("display.width", 220)
    for arm in ARMS:
        print(f"\n===== {arm} =====")
        print(res[(res.arm == arm) & (res.era == "full")]
              .drop(columns=["arm", "era"]).to_string(index=False))
    print("\n===== 时代切片（SKEW1，全候选） =====")
    print(res[(res.arm == "SKEW1") & (res.era != "full")]
          .drop(columns=["arm"]).to_string(index=False))

if __name__ == "__main__":
    main()
