"""Q102 P1 — Sleeve B 深跌抄底重设计：多发 re-arm × 离场规则 × 结构（PM 2026-07-12 立项）。

PM 三问（原话要点）：
  1. 多发后"半山腰"入场大概率亏 → 但我不会机械持有 90D，确认假突破可提前割肉
     —— 离场规则能否把多发的亏单救小？
  2. 替代结构：LEAP call 深跌抄底（美股长期总上涨 thesis，长线交易）；
  3. 短线宽度：5% 装不下暴跌后的反弹（Q100 §5 补充已证封顶率 80%）
     —— 深入场点的宽度阶梯。

预注册（先于跑数写定）：
  R1 本 phase 为 EXPLORATORY，facts-only，不产生 promote/kill verdict
     （每 cell n=1..10）；交付物 = 设计地图 + 后续 confirmatory phase 该预注册什么。
  R2 离场阈值只允许结构性数值（入场 rung 线本身 / 下一级 rung / MA10——
     与入场同一均线），禁止拟合出来的 buffer（Q083 切点过拟合教训，n 这么小
     任何拟合切点都是伪发现）。
  R3 LEAP 定价括号 [0.75, 1.0]×VIX 先行申明（危机期 1y IV 深度贴水 VIX；
     VIX3M/VIX 比值当日实测值一并报告作括号内证）；q=1.6%（SPX 股息，
     q=0 会系统性高估 1-2y call）；结论必须在两端都读。
  R4 同 friction（debit×1.005+$2.6/ct 入场；提前离场再付 0.5%+$2.6）、
     同预算 $62.5k/笔 fractional、exit-day 记账、CALIB+STRESS 双报。

结构性 rung 阶梯：{-15%, -25%, -35%, -45%}（自然 10pp 步长，非拟合）。
多仓并行允许（研究口径独立评估）；现金叠栈约束（4 rung × $62.5k = $250k >
今日池 $152k）属 production sizing 议题，登记不建模。
离场规则：
  X0 hold-to-expiry（现任）
  X1 假突破止损：reclaim 入场 → close 跌回入场 rung 线；immediate 入场 →
     close 触及下一级 rung（结构性下界）
  X2 MA10 止损：入场后首次 close < MA10（与 reclaim 入场信号同一均线）
提前离场估值 = CALIB 剩余期限重定价（模型依赖，findings 披露）。
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

from pricing import core as pcore                      # noqa: E402
from pricing.calibration import load_offsets           # noqa: E402
from pricing.sigma import SigmaMode, sigma_for         # noqa: E402
from q100_p1_replay import load_data                   # noqa: E402

OUT = ROOT / "research" / "q102"
BUDGET = 62_500.0
SLIP = 0.005
COMM = 2.6
R = 0.045
Q_DIV = 0.016
RUNGS = (-0.15, -0.25, -0.35, -0.45)
STOP_FLOOR = -0.55          # immediate 模式最深一级的结构性下界


# ── 定价 ─────────────────────────────────────────────────────────────────────

def leg_sigma(S, K, T, vix, dte, off, stress_vp=0.0, sgn=+1):
    d = pcore.call_delta(S, K, T, max(vix / 100.0, 0.01), R)
    sig = sigma_for(SigmaMode.CALIB, vix=vix, option_type="CALL",
                    abs_delta=abs(d), dte=dte, offsets=off)
    return max(sig + sgn * stress_vp / 100.0, 0.01)


def spread_px(S, KL, KS, dte_rem, vix, off, stress_vp=0.0):
    """CALIB spread 价（stress>0 = 买方不利：long 抬 short 压）。dte_rem<=0 → 内在。"""
    if dte_rem <= 0:
        return max(S - KL, 0.0) - max(S - KS, 0.0)
    T = dte_rem / 365.0
    pl = pcore.call_price(S, KL, T, leg_sigma(S, KL, T, vix, dte_rem, off, stress_vp, +1), R)
    ps = pcore.call_price(S, KS, T, leg_sigma(S, KS, T, vix, dte_rem, off, stress_vp, -1), R)
    return max(pl - ps, 0.0)


# ── 阶梯入场流 ────────────────────────────────────────────────────────────────

def ladder_entries(close, ma10, mode="reclaim", watch=30, rearm=-0.02):
    """每 rung 独立 armed；全体 rung 在 dd ≥ rearm 时重新装弹（同现任语义）。
    多仓并行允许（每 rung 一仓位语义归 confirmatory phase，本 phase 独立评估）。"""
    dates = close.index
    dd = close / close.cummax() - 1.0
    armed = {r: True for r in RUNGS}
    watching = {}                                    # rung -> touch_i
    events = []
    for i in range(len(close)):
        if dd.iloc[i] >= rearm:
            for r in RUNGS:
                armed[r] = True
            watching.clear()
        for r in RUNGS:
            if armed[r] and dd.iloc[i] <= r:
                armed[r] = False
                if mode == "immediate":
                    if i + 1 < len(close):
                        events.append(dict(rung=r, sig_i=i, ent_i=i + 1,
                                           dd_entry=float(dd.iloc[i])))
                else:
                    watching[r] = i
        fired = []
        for r, t0 in watching.items():
            if i > t0 and i - t0 > watch:
                fired.append(r)                       # watch 过期，本轮丢弃
            elif i > t0 and close.iloc[i] > ma10.iloc[i]:
                if i + 1 < len(close):
                    events.append(dict(rung=r, sig_i=i, ent_i=i + 1,
                                       dd_entry=float(dd.iloc[i])))
                fired.append(r)
        for r in fired:
            watching.pop(r, None)
    return events


# ── spread 交易（含离场规则） ─────────────────────────────────────────────────

def run_spread(ev, close, vix_s, ma10, dd, off, w=0.05, dte=90,
               exit_rule="X0", mode="reclaim"):
    dates = close.index
    si, ei = ev["sig_i"], ev["ent_i"]
    S = float(close.iloc[si])
    vx = float(vix_s.iloc[si])
    KL = round(S / 5) * 5
    KS = round(S * (1 + w) / 5) * 5
    expiry = dates[si] + pd.Timedelta(days=1 + dte)
    sp = dates.searchsorted(expiry)
    if sp >= len(close):
        return None
    out = {"rung": ev["rung"], "signal": str(dates[si].date()),
           "dd_entry": round(ev["dd_entry"] * 100, 1), "w_pct": w * 100,
           "exit_rule": exit_rule}
    if exit_rule == "X1":
        stop_dd = ev["rung"] if mode == "reclaim" else (
            RUNGS[RUNGS.index(ev["rung"]) + 1] if RUNGS.index(ev["rung"]) + 1 < len(RUNGS)
            else STOP_FLOOR)
    for tag, stress in (("calib", 0.0), ("stress", 2.0)):
        deb = spread_px(S, KL, KS, dte, vx, off, stress)
        fill = deb * (1 + SLIP)
        cts = BUDGET / (fill * 100.0)
        exit_i, reason = sp, "expiry"
        for j in range(ei + 1, sp):
            if exit_rule == "X1" and float(dd.iloc[j]) <= stop_dd:
                exit_i, reason = j, "stop_rung"
                break
            if exit_rule == "X2" and float(close.iloc[j]) < float(ma10.iloc[j]):
                exit_i, reason = j, "stop_ma10"
                break
        St = float(close.iloc[exit_i])
        rem = max((expiry - dates[exit_i]).days, 0) if exit_i < sp else 0
        val = spread_px(St, KL, KS, rem, float(vix_s.iloc[exit_i]), off, -stress if rem > 0 else 0.0)
        if rem > 0:
            val = val * (1 - SLIP)
            pnl = (val - fill) * 100.0 * cts - COMM * cts * 2
        else:
            pnl = (val - fill) * 100.0 * cts - COMM * cts
        out[f"pnl_{tag}"] = round(pnl, 0)
    out.update(exit=str(dates[exit_i].date()), reason=reason,
               hold_td=int(exit_i - ei),
               capped=bool(float(close.iloc[exit_i]) >= KS))
    out["cash_days"] = BUDGET * out["hold_td"]
    return out


# ── LEAP / 指数基准 ───────────────────────────────────────────────────────────

def run_leap(ev, close, vix_s, kind="atm", dte=365, vol_mult=1.0):
    dates = close.index
    si, ei = ev["sig_i"], ev["ent_i"]
    S = float(close.iloc[si])
    vx = float(vix_s.iloc[si]) * vol_mult
    K = round(S / 5) * 5 if kind == "atm" else round(S * 0.85 / 5) * 5
    expiry = dates[si] + pd.Timedelta(days=1 + dte)
    sp = dates.searchsorted(expiry)
    if sp >= len(close):
        return None
    T = dte / 365.0
    deb = pcore.call_price(S, K, T, max(vx / 100.0, 0.01), R, q=Q_DIV)
    fill = deb * (1 + SLIP)
    cts = BUDGET / (fill * 100.0)
    ST = float(close.iloc[sp])
    pnl = (max(ST - K, 0.0) - fill) * 100.0 * cts - COMM * cts
    return {"rung": ev["rung"], "signal": str(dates[si].date()),
            "kind": f"LEAP_{kind}_x{vol_mult}", "K": K, "debit": round(deb, 1),
            "settle": str(dates[sp].date()), "ST": round(ST, 0),
            "pnl": round(pnl, 0), "hold_td": int(sp - ei),
            "ret_on_cash_pct": round(pnl / BUDGET * 100, 1)}


def run_index(ev, close, dte=365):
    dates = close.index
    si, ei = ev["sig_i"], ev["ent_i"]
    sp = dates.searchsorted(dates[si] + pd.Timedelta(days=1 + dte))
    if sp >= len(close):
        return None
    S0, ST = float(close.iloc[ei]), float(close.iloc[sp])
    pnl = BUDGET * (ST / S0 - 1)
    return {"rung": ev["rung"], "signal": str(dates[si].date()), "kind": f"INDEX_{dte}d",
            "pnl": round(pnl, 0), "ret_on_cash_pct": round((ST / S0 - 1) * 100, 1)}


def main() -> int:
    spx, vix_s = load_data()
    close = spx["Close"]
    ma10 = close.rolling(10).mean()
    dd = close / close.cummax() - 1.0
    off = load_offsets()
    try:
        v3 = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__VIX3M__max__1d.pkl")["Close"]
        vi = pd.to_datetime(v3.index)
        v3.index = (vi.tz_localize(None) if vi.tz is not None else vi).normalize()
        v3 = v3.reindex(close.index)
    except Exception:
        v3 = pd.Series(index=close.index, dtype=float)

    ev_re = ladder_entries(close, ma10, mode="reclaim")
    ev_im = ladder_entries(close, ma10, mode="immediate")

    print("═ T1 阶梯入场流 ═")
    for lbl, evs in (("reclaim", ev_re), ("immediate", ev_im)):
        print(f"[{lbl}] n={len(evs)}")
        for e in evs:
            t3 = v3.iloc[e["sig_i"]] / vix_s.iloc[e["sig_i"]] if not pd.isna(v3.iloc[e["sig_i"]]) else np.nan
            print(f"  rung {e['rung']*100:+.0f}%  sig {close.index[e['sig_i']].date()}  "
                  f"dd@sig {e['dd_entry']*100:+.1f}%  VIX {vix_s.iloc[e['sig_i']]:.1f}  "
                  f"VIX3M/VIX {t3:.2f}" if not pd.isna(t3) else
                  f"  rung {e['rung']*100:+.0f}%  sig {close.index[e['sig_i']].date()}  "
                  f"dd@sig {e['dd_entry']*100:+.1f}%  VIX {vix_s.iloc[e['sig_i']]:.1f}  VIX3M n/a")
    pd.DataFrame(ev_re).assign(mode="reclaim").pipe(
        lambda a: pd.concat([a, pd.DataFrame(ev_im).assign(mode="immediate")])
    ).to_csv(OUT / "q102_p1_entries.csv", index=False)

    # ═ T2 多发 × 离场规则（S1 = 5%/90 现任结构） ═
    print("\n═ T2 多发 × 离场（5%/90, 等预算, CALIB|STRESS） ═")
    grid_rows = []
    for mlbl, evs in (("reclaim", ev_re), ("immediate", ev_im)):
        for xr in ("X0", "X1", "X2"):
            rows = [run_spread(e, close, vix_s, ma10, dd, off, exit_rule=xr, mode=mlbl)
                    for e in evs]
            rows = [r for r in rows if r]
            df = pd.DataFrame(rows).assign(mode=mlbl)
            grid_rows.append(df)
            tot, tots = df.pnl_calib.sum() / 1000, df.pnl_stress.sum() / 1000
            wr = (df.pnl_calib > 0).mean() * 100
            deep = df[df.rung <= -0.25]
            print(f"  {mlbl:9s} {xr}: n={len(df)} total {tot:+7.1f}k (stress {tots:+7.1f}k) "
                  f"wr {wr:3.0f}% worst {df.pnl_calib.min()/1000:+6.1f}k | "
                  f"deep(≤-25%) n={len(deep)} sub {deep.pnl_calib.sum()/1000:+6.1f}k")
    gdf = pd.concat(grid_rows)
    gdf.to_csv(OUT / "q102_p1_exits_grid.csv", index=False)
    print("\n  [per-event] immediate × X1 明细（PM 问题 1 的直接证据）：")
    d = gdf[(gdf["mode"] == "immediate") & (gdf.exit_rule == "X1")]
    print(d[["rung", "signal", "dd_entry", "exit", "reason", "hold_td",
             "pnl_calib", "pnl_stress"]].to_string(index=False))

    # ═ T3 深入场点宽度阶梯（immediate 流 rung ≤ -25%, X0） ═
    print("\n═ T3 深 rung 宽度阶梯（immediate ≤-25%, hold-to-expiry） ═")
    deep_ev = [e for e in ev_im if e["rung"] <= -0.25]
    wrows = []
    for w in (0.05, 0.10, 0.15, 0.20):
        rows = [run_spread(e, close, vix_s, ma10, dd, off, w=w) for e in deep_ev]
        rows = [r for r in rows if r]
        df = pd.DataFrame(rows)
        wrows.append(df.assign(width=w))
        print(f"  +{w*100:4.1f}%: total {df.pnl_calib.sum()/1000:+7.1f}k "
              f"(stress {df.pnl_stress.sum()/1000:+7.1f}k) wr {(df.pnl_calib>0).mean()*100:3.0f}% "
              f"capped {df.capped.mean()*100:3.0f}% "
              f"$/cash-kday {df.pnl_calib.sum()/(df.cash_days.sum()/1000):5.2f}")
    pd.concat(wrows).to_csv(OUT / "q102_p1_width_deep.csv", index=False)

    # ═ T4 LEAP vs spread vs 指数（immediate 全 rung） ═
    print("\n═ T4 LEAP(365d) / 指数基准 / 现任 spread — immediate 流 ═")
    lrows = []
    for e in ev_im:
        for kind in ("atm", "itm85"):
            for vm in (0.75, 1.0):
                r = run_leap(e, close, vix_s, kind="atm" if kind == "atm" else "itm", vol_mult=vm)
                if r:
                    r["kind"] = f"LEAP_{kind}_x{vm}"
                    lrows.append(r)
        for r in (run_index(e, close, 365), run_index(e, close, 90)):
            if r:
                lrows.append(r)
    ldf = pd.DataFrame(lrows)
    ldf.to_csv(OUT / "q102_p1_leap.csv", index=False)
    agg = (ldf.groupby("kind")
           .agg(n=("pnl", "size"), total_k=("pnl", lambda s: round(s.sum() / 1000, 1)),
                wr=("pnl", lambda s: round((s > 0).mean() * 100)),
                worst_k=("pnl", lambda s: round(s.min() / 1000, 1)),
                med_ret_pct=("ret_on_cash_pct", "median"))
           .reset_index())
    print(agg.to_string(index=False))
    print("\n  [per-event] LEAP_atm_x1.0 vs INDEX_365d（deep rung ≤-25%）：")
    for k in ("LEAP_atm_x1.0", "INDEX_365d"):
        sub = ldf[(ldf.kind == k)].merge(pd.DataFrame(ev_im)[["sig_i"]], how="cross").head(0)
    sub = ldf[ldf.kind.isin(["LEAP_atm_x1.0", "LEAP_atm_x0.75", "INDEX_365d"])]
    deep = sub[sub.rung <= -0.25].sort_values(["signal", "kind"])
    print(deep[["rung", "signal", "kind", "pnl", "ret_on_cash_pct"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
