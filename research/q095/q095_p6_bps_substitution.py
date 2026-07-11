"""Q095 P6 — Q042 触发日的表达替换:BPS(吃 BP) vs D30 call spread(吃现金)。

PM 假设(2026-07-12):①现金弹药不足时可用 BPS 替代 debit 结构表达同一 bullish
观点;②DD 触发时 vol 高,卖权(BPS)拿更肥 credit,比买权(call spread 付高 vol)
更顺风。Q062 结构网格只测过 call 侧(vertical/naked/ITM),BPS 表达从未测过。

预注册(单变体,不网格):
  BPS = 主策略惯例(short put Δ0.30 / long put Δ0.15,即 normal_delta 与其半值),
        与 call spread 同 entry(T+1)、同 expiry(entry+30cal)、同 hold-to-expiry
  Sizing = 等资源预算 $78.6k(today-scale):call spread 张数 = 预算/debit;
           BPS 张数 = 预算/max_loss(width−credit,PM 口径 BP)——同预算不同资源类型
  定价 bracket(research_bs_flat_vix_pricing_bias:FLAT 高估卖权 credit):
        FLAT + 入场 short put credit 按 sigma−2vp 重估的 haircut 变体
  分层:episode 内/破位后≤7d(31 次) vs 无前导突发型(4 次)——PM 第 3 点
  杀标(方向判定,非 ratify 门):BPS 若在突发型分层的 worst 显著劣于 call spread
        的 capped debit,则"无条件替代"死,只留"条件化(episode 型)替代"讨论

输出:q095_p6_bps_sub.csv + 摘要。口径:BS FLAT(与引擎一致,T=dte_td/252);
结论 research-grade,任何 adoption 须过 CALIB+成本(memory 强制)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "research" / "q095"

from research.q095.q095_p1_delta_attribution import load_daily  # noqa: E402
from backtest.pricer import (  # noqa: E402
    call_price, put_price, put_delta, find_strike_for_delta,
)

BUDGET = 78_600.0
HAIRCUT_VP = 0.02


def trading_days(daily, d0, d1) -> int:
    return max(len(daily.loc[d0:d1]) - 1, 1)


def main() -> int:
    daily = load_daily()
    eps = pd.read_csv(OUT / "q095_p2b_episodes.csv", parse_dates=["start", "end"])
    q = pd.read_csv(ROOT / "data" / "q042_backtest_trades.csv",
                    parse_dates=["signal_date", "entry_date", "exit_date"])
    q = q[q.sleeve_id == "A"].copy()

    rows = []
    for _, t in q.iterrows():
        d_sig, d_ent = t.signal_date, t.entry_date
        d_exp = d_ent + pd.Timedelta(days=30)
        # 对齐到交易日
        idx = daily.index
        if d_ent not in idx:
            d_ent = idx[idx.searchsorted(d_ent)]
        d_exp_eff = idx[min(idx.searchsorted(d_exp), len(idx) - 1)]
        s0, v0 = float(daily.loc[d_ent, "spx"]), float(daily.loc[d_ent, "vix"])
        s1 = float(daily.loc[d_exp_eff, "spx"])
        sigma0 = v0 / 100.0
        dte_td = trading_days(daily, d_ent, d_exp_eff)

        # 分层
        inside = ((eps.start <= d_sig) & (d_sig <= eps.end)).any()
        brk = ((eps.end < d_sig) & ((d_sig - eps.end).dt.days <= 7)).any()
        stratum = "episode" if (inside or brk) else "sudden"

        # ── Call spread(Q042 D30/2.5% 实际结构)────────────────────────────
        kL = round(s0 / 5) * 5
        kS = round(s0 * 1.025 / 5) * 5
        debit = (call_price(s0, kL, dte_td, sigma0) - call_price(s0, kS, dte_td, sigma0)) * 100
        n_cs = int(BUDGET // debit) if debit > 0 else 0
        pay_cs = (max(s1 - kL, 0) - max(s1 - kS, 0)) * 100
        pnl_cs = (pay_cs - debit) * n_cs

        # ── BPS(主策略惯例 Δ0.30/Δ0.15,同 expiry)──────────────────────────
        kSp = find_strike_for_delta(s0, dte_td, sigma0, 0.30, is_call=False)
        kLp = find_strike_for_delta(s0, dte_td, sigma0, 0.15, is_call=False)
        cr_flat = (put_price(s0, kSp, dte_td, sigma0) - put_price(s0, kLp, dte_td, sigma0)) * 100
        cr_hair = (put_price(s0, kSp, dte_td, max(sigma0 - HAIRCUT_VP, 0.01))
                   - put_price(s0, kLp, dte_td, sigma0)) * 100   # 只砍 short 腿 credit,方向保守
        width = (kSp - kLp) * 100
        for label, cr in (("FLAT", cr_flat), ("HAIRCUT", cr_hair)):
            max_loss = width - cr
            n_b = int(BUDGET // max_loss) if max_loss > 0 else 0
            pay_b = -(max(kSp - s1, 0) - max(kLp - s1, 0)) * 100   # 卖方视角
            pnl_b = (cr + pay_b) * n_b
            rows.append(dict(signal=d_sig.date(), stratum=stratum, vix=v0,
                             pricing=label,
                             cs_pnl=round(pnl_cs, 0), cs_n=n_cs, cs_debit=round(debit, 0),
                             bps_pnl=round(pnl_b, 0), bps_n=n_b,
                             bps_credit=round(cr, 0), bps_maxloss=round(max_loss, 0),
                             hold_td=dte_td))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "q095_p6_bps_sub.csv", index=False)

    for pricing in ("FLAT", "HAIRCUT"):
        sub = df[df.pricing == pricing]
        print(f"\n=== {pricing}(n={len(sub)} 触发,预算 ${BUDGET:,.0f}/次)===")
        for strat in ("all", "episode", "sudden"):
            s = sub if strat == "all" else sub[sub.stratum == strat]
            if not len(s):
                continue
            wr_cs = (s.cs_pnl > 0).mean() * 100
            wr_b = (s.bps_pnl > 0).mean() * 100
            print(f"[{strat:>7s} n={len(s):>2d}] CallSpread Σ${s.cs_pnl.sum():>9,.0f} "
                  f"WR {wr_cs:3.0f}% worst ${s.cs_pnl.min():>8,.0f} | "
                  f"BPS Σ${s.bps_pnl.sum():>9,.0f} WR {wr_b:3.0f}% worst ${s.bps_pnl.min():>8,.0f}")
        # 资源效率(metrics pack): $/资源-day,资源=预算(同额)
        days = sub.hold_td.sum()
        print(f"  $/资源-day: CallSpread(吃现金) {sub.cs_pnl.sum()/(BUDGET*days/21):,.2f} "
              f"| BPS(吃BP) {sub.bps_pnl.sum()/(BUDGET*days/21):,.2f}  (per $预算·月)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
