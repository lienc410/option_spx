"""Q098 — Episode 子类型 × 结构选择:真震荡 vs 慢涨的路由价值(PM 2026-07-13 立项)。

A. 真信号分离度复核:Q097 addendum 的 crosstab 用了 close>MA50 粗代理——
   本部分用生产真信号(SPEC-020, MA20/50 gap ATR 标准化三态)重跑,
   先澄清"trend 轴粗糙"的批评对象到底是谁。
B. 头对头(主事件):episode 内固定步长采样日,同日合成定价 IC 与 BPS 两种
   结构(消除 selector 路由选择效应),按子类型分组比较。

预注册:
  子类型 = Q097 addendum 度量(drift 占比 ±0.5 切点 + crossings,hindsight
           episode 级——事实层;causal 版留 P2)
  结构惯例 = 引擎现值:IC 45DTE 0.16Δ 短双翼/0.08Δ 长翼;BPS 30DTE 0.30/0.15Δ
  定价 = BS FLAT(backtest.pricer 同引擎口径)+ 短腿 −2vp HAIRCUT bracket
  采样 = episode 内每 5 TD(描述统计)+ 每 45 TD 非重叠子样本(推断统计,
         防持有期重叠的序列相关虚胖)
  主检验(唯一) = oscillation 型内 IC vs BPS 每合约 PnL 差(Welch t,
         非重叠子样本);行动门槛 p<0.05 且 melt-up 型内不反向恶化
  → 过门槛才谈路由/标签;不过 = 只考虑显示不改操作
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "research" / "q098"

from backtest.pricer import (  # noqa: E402
    call_price, put_price, find_strike_for_delta,
)


def load_px():
    df = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl")
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    vix = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl")
    vi = pd.to_datetime(vix.index)
    if vi.tz is not None:
        vi = vi.tz_localize(None)
    v = pd.Series(vix["Close"].values, index=vi.normalize())
    out = pd.DataFrame({"close": df["Close"], "vix": v}).dropna()
    return out.loc["1999-01-01":]


def sim_structs(spx, vix_val, dte_ic=45, dte_bps=30, haircut=0.0):
    """同日合成:返回 (ic_legs, bps_legs) 各为 [(action,is_call,K,dte)]。"""
    s = vix_val / 100.0
    ic = [(-1, True, find_strike_for_delta(spx, dte_ic, s, 0.16, is_call=True), dte_ic),
          (+1, True, find_strike_for_delta(spx, dte_ic, s, 0.08, is_call=True), dte_ic),
          (-1, False, find_strike_for_delta(spx, dte_ic, s, 0.16, is_call=False), dte_ic),
          (+1, False, find_strike_for_delta(spx, dte_ic, s, 0.08, is_call=False), dte_ic)]
    bps = [(-1, False, find_strike_for_delta(spx, dte_bps, s, 0.30, is_call=False), dte_bps),
           (+1, False, find_strike_for_delta(spx, dte_bps, s, 0.15, is_call=False), dte_bps)]
    return ic, bps


def entry_value(legs, spx, sigma, haircut_vp=0.0):
    tot = 0.0
    for a, is_c, k, dte in legs:
        s_leg = max(sigma - haircut_vp, 0.01) if (a < 0 and haircut_vp) else sigma
        p = call_price(spx, k, dte, s_leg) if is_c else put_price(spx, k, dte, s_leg)
        tot += a * p
    return tot


def expiry_pnl(legs, entry_val, spx_exp):
    payoff = 0.0
    for a, is_c, k, _ in legs:
        intr = max(spx_exp - k, 0.0) if is_c else max(k - spx_exp, 0.0)
        payoff += a * intr
    return (payoff - entry_val) * 100.0   # per contract USD


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    px = load_px()
    subs = pd.read_csv(ROOT / "research" / "q097" / "q097_p2d_episode_subtypes.csv",
                       parse_dates=["start"])
    eps = pd.read_csv(ROOT / "research" / "q095" / "q095_p2b_episodes.csv",
                      parse_dates=["start", "end"])
    eps = eps.merge(subs[["start", "kind", "drift", "crossings"]], on="start", how="left")

    # ── A. 真信号分离度(SPEC-020 ATR 标准化三态) ──────────────────────────
    from signals.trend import get_trend_history
    spx_df = pd.DataFrame({"close": px["close"]})
    th = get_trend_history(spx_df, use_atr=True)
    sig = th["signal"].astype(str)
    mids = []
    for _, r in eps.iterrows():
        c = px.loc[r.start:r.end]
        if len(c) < 10 or pd.isna(r.kind):
            continue
        mid = c.index[len(c) // 2]
        if mid in sig.index:
            mids.append((r.kind, sig.loc[mid]))
    ct = pd.crosstab(pd.Series([m[0] for m in mids], name="kind"),
                     pd.Series([m[1] for m in mids], name="trend_real"))
    print("=== A. 真信号(SPEC-020 ATR 三态)× 子类型 ===")
    print(ct.to_string())
    neutral_share = {k: round(ct.loc[k].get("neutral", 0) / ct.loc[k].sum() * 100)
                     for k in ct.index}
    print("NEUTRAL 占比 by 子类型:", neutral_share)

    # ── B. 同日配对头对头 ─────────────────────────────────────────────────
    rows = []
    for _, r in eps.iterrows():
        if pd.isna(r.kind):
            continue
        days = px.loc[r.start:r.end].index
        for i in range(0, len(days), 5):
            d = days[i]
            spx, vv = float(px.loc[d, "close"]), float(px.loc[d, "vix"])
            for label, dte in (("IC", 45), ("BPS", 30)):
                exp_d = d + pd.Timedelta(days=dte)
                fut = px.loc[:exp_d]
                if fut.index[-1] < exp_d - pd.Timedelta(days=5):
                    continue                       # 数据尾部不足
                spx_exp = float(fut["close"].iloc[-1])
                dte_td = max(len(px.loc[d:exp_d]) - 1, 1)
                ic, bps = sim_structs(spx, vv, dte_ic=dte_td if label == "IC" else 45,
                                      dte_bps=dte_td if label == "BPS" else 30)
                legs = ic if label == "IC" else bps
                for pr_label, hc in (("FLAT", 0.0), ("HAIRCUT", 0.02)):
                    ev = entry_value(legs, spx, vv / 100.0, haircut_vp=hc)
                    rows.append(dict(date=d.date(), kind=r.kind, struct=label,
                                     pricing=pr_label,
                                     pnl=round(expiry_pnl(legs, ev, spx_exp), 0),
                                     stride45=(i % 45 == 0)))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "q098_headtohead.csv", index=False)

    print("\n=== B. 同日配对头对头(每合约 PnL, USD)===")
    for pricing in ("FLAT", "HAIRCUT"):
        print(f"\n-- {pricing} --")
        for kind in ("oscillation", "melt_up", "melt_down"):
            line = f"[{kind:>11s}]"
            for st in ("IC", "BPS"):
                s = df[(df.pricing == pricing) & (df.kind == kind) & (df.struct == st)]
                line += f"  {st}: n={len(s):>4d} avg ${s.pnl.mean():>7,.0f} WR {(s.pnl>0).mean()*100:3.0f}% worst ${s.pnl.min():>8,.0f}"
            print(line)

    print("\n=== 主检验(唯一): oscillation 内 IC vs BPS, 非重叠 stride-45 子样本, FLAT ===")
    o = df[(df.pricing == "FLAT") & (df.kind == "oscillation") & df.stride45]
    ic45, bps45 = o[o.struct == "IC"].pnl, o[o.struct == "BPS"].pnl
    t, p = stats.ttest_ind(ic45, bps45, equal_var=False)
    print(f"IC n={len(ic45)} avg ${ic45.mean():,.0f} | BPS n={len(bps45)} avg ${bps45.mean():,.0f} "
          f"| diff ${ic45.mean()-bps45.mean():,.0f} | t={float(t):+.2f} p={float(p):.4f}")
    m = df[(df.pricing == "FLAT") & (df.kind == "melt_up") & df.stride45]
    ic_m, bps_m = m[m.struct == "IC"].pnl, m[m.struct == "BPS"].pnl
    print(f"[melt_up 对照] IC avg ${ic_m.mean():,.0f} vs BPS ${bps_m.mean():,.0f} (diff ${ic_m.mean()-bps_m.mean():,.0f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
