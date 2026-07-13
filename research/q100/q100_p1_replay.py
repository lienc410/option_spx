"""Q100 P1 — DD Overlay 双 sleeve 独立重验（PM 2026-07-12 直接指令）。

任务：不默认既有研究可信，从原始行情独立重放触发流 + 重定价，评估当前
两 sleeve 配置（A: dd-4 T+1, ATM/+2.5%, DTE30, 12.5%→17.5%;
B: dd-15 + MA10 reclaim, ATM/+5%, DTE90, production 0% / paper 10%）
是否是设计空间内的合理点。

独立性措施：
  - 状态机自行实现（本文件），production `signals.q042_trigger.get_q042_history`
    仅作交叉验证对象，不作数据源；
  - `data/q042_backtest_trades.csv` 仅作 reproduction 校验对象；
  - 定价三路：INC = 生产公式 (strategy.q042_pricing, FLAT-VIX×term×skew,
    r=0.04)；CALIB = SPEC-119 (pricing.core r=0.045 ACT/365 + 实测 moff
    offset)；STRESS = CALIB 最大 debit 方向 (long +2vp / short −2vp)。
    结算 = 到期内在价值，model-free——定价模型只影响入场 debit。

预注册判定规则（先于跑数写定）：
  R1 结构/参数改动仅在以下全部成立时才建议：ΔPnL>0 在 INC 且 CALIB 且
     STRESS 三路成立；year-block bootstrap P(Δ>0) ≥ 0.90（CALIB）；
     post-2020 子样本符号一致；Δ($/cash-day) 不劣化（cash-bound 账户）。
  R2 Sleeve B 事件 n<8 → 只呈现事实，不给 promote/kill 建议
     （feedback_layer_n_replacement_outcome / 噪音门槛纪律）。
  R3 sizing 部分为确定性算术（今日 NLV/池），不做统计推断。
  R4 挑战者与现任同一把尺（同 friction、同预算、同结算规则）——
     status-quo-bias 防线。

口径：
  - canonical 预算 $62.5k/笔（= 12.5% × $500k，与 Q093 P1 同），fractional
    contracts = budget / (debit×100)；等现金预算使 width/DTE cell 可比。
  - friction：fill = est_debit×1.005（半价差 0.5%）+ $2.6/contract 佣金；
    到期现金结算免平仓费。全部 cell 同规则 (R4)。
  - PnL 记账 = exit-day（unsmoothed，feedback_sharpe_smoothing_artifact）。
  - 时代分层 full (2007+) / post-2020（feedback_adaptive_posture）。
  - ATH 种子 2007-01-01 cummax（与生产一致；2000 年 ATH 缺席只影响
    2007H1 触发深度，见 findings 局限节）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "research" / "q100"

from pricing import core as pcore                      # noqa: E402
from pricing.calibration import load_offsets           # noqa: E402
from pricing.sigma import SigmaMode, sigma_for         # noqa: E402
from strategy.q042_pricing import estimate_debit       # noqa: E402

BUDGET = 62_500.0          # canonical per-trade cash budget (USD)
SLIP = 0.005               # half-spread, fraction of debit
COMMISSION = 2.6           # USD per contract, entry (2 legs × $1.30)
R_CALIB = 0.045
START = "2007-01-01"


# ── data ─────────────────────────────────────────────────────────────────────

def load_data():
    spx = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl")
    idx = pd.to_datetime(spx.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    spx.index = idx.normalize()
    spx = spx.loc[START:]
    vix = pd.read_pickle(ROOT / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl")
    vi = pd.to_datetime(vix.index)
    if vi.tz is not None:
        vi = vi.tz_localize(None)
    vix.index = vi.normalize()
    vix_c = vix["Close"].reindex(spx.index).ffill()
    return spx[["Open", "Close"]].dropna(), vix_c


# ── independent state machines ───────────────────────────────────────────────

def replay_a(close: pd.Series, trig=-0.04, rearm=-0.02, dte=30,
             entry_mode="t1", ma10: pd.Series | None = None,
             confirm_days=30):
    """Sleeve A style: first-cross trigger → entry.
    entry_mode: 't1' (incumbent T+1) | 't5' (5 TD later) | 'reclaim'
    (first close > MA10 within confirm_days TD, then that day is signal-eq).
    Returns list of dicts {sig_i, ent_i, expiry_date}. Position blocks
    re-fire until first trading day >= expiry (production settle semantics).
    """
    dates = close.index
    ath = close.cummax()
    dd = close / ath - 1.0
    events = []
    armed = True
    pos_expiry = None            # pd.Timestamp | None
    pending = None               # for t5/reclaim: dict
    n = len(close)
    for i in range(n):
        d = dates[i]
        if pos_expiry is not None and d >= pos_expiry:
            pos_expiry = None
        # resolve pending confirmation entries first (no new trigger while pending)
        if pending is not None:
            if entry_mode == "t5":
                if i - pending["trig_i"] >= 5:
                    events.append(_mk_event(dates, i, dte))
                    pos_expiry = events[-1]["expiry_date"]
                    pending = None
            elif entry_mode == "reclaim":
                if i - pending["trig_i"] > confirm_days:
                    pending = None                      # confirmation expired
                elif close.iloc[i] > ma10.iloc[i]:
                    events.append(_mk_event(dates, i, dte))
                    pos_expiry = events[-1]["expiry_date"]
                    pending = None
        if not armed and dd.iloc[i] >= rearm:
            armed = True
        if armed and dd.iloc[i] <= trig and pos_expiry is None and pending is None:
            armed = False
            if entry_mode == "t1":
                events.append(_mk_event(dates, i, dte))
                pos_expiry = events[-1]["expiry_date"]
            else:
                pending = {"trig_i": i}
    return events


def _mk_event(dates, sig_i, dte):
    sig_d = dates[sig_i]
    return {"sig_i": sig_i, "ent_i": sig_i + 1,
            "expiry_date": sig_d + pd.Timedelta(days=1 + dte)}


def replay_b(close: pd.Series, ma10: pd.Series, outer=-0.15, rearm=-0.02,
             dte=90, watch_days=30, immediate=False):
    """Sleeve B style: outer trigger → watching → MA10 reclaim fire.
    immediate=True: fire at outer trigger day directly (challenger variant)."""
    dates = close.index
    ath = close.cummax()
    dd = close / ath - 1.0
    events = []
    armed = True
    watching = False
    watch_start_i = None
    pos_expiry = None
    for i in range(len(close)):
        d = dates[i]
        if pos_expiry is not None and d >= pos_expiry:
            pos_expiry = None
        if not armed and not watching and dd.iloc[i] >= rearm:
            armed = True
        if armed and not watching and dd.iloc[i] <= outer and pos_expiry is None:
            armed = False
            if immediate:
                events.append(_mk_event(dates, i, dte))
                pos_expiry = events[-1]["expiry_date"]
            else:
                watching = True
                watch_start_i = i
                continue                                 # no same-day reclaim
        if watching:
            days_in_watch = i - watch_start_i            # TD count after start
            if days_in_watch > watch_days:
                watching = False
                watch_start_i = None
            elif close.iloc[i] > ma10.iloc[i]:
                watching = False
                watch_start_i = None
                events.append(_mk_event(dates, i, dte))
                pos_expiry = events[-1]["expiry_date"]
    return events


# ── pricing ──────────────────────────────────────────────────────────────────

def debit_calib(S, KL, KS, dte, vix, offsets, stress_vp=0.0):
    """CALIB per-leg sigma; delta from FLAT first pass; stress widens debit."""
    T = dte / 365.0
    sig0 = max(vix / 100.0, 0.01)
    legs = []
    for K, sgn in ((KL, +1), (KS, -1)):
        delta = pcore.call_delta(S, K, T, sig0, R_CALIB)
        sig = sigma_for(SigmaMode.CALIB, vix=vix, option_type="CALL",
                        abs_delta=abs(delta), dte=dte, offsets=offsets)
        sig = max(sig + sgn * stress_vp / 100.0, 0.01)
        legs.append(pcore.call_price(S, K, T, sig, R_CALIB))
    return max(legs[0] - legs[1], 0.01)


def debit_inc(S, KL, KS, dte, vix):
    return max(estimate_debit(S=S, K_long=KL, K_short=KS, dte=dte, vix=vix), 0.01)


# ── trade construction ───────────────────────────────────────────────────────

def build_trades(events, spx, vix, w, dte, offsets):
    close, open_ = spx["Close"], spx["Open"]
    dates = close.index
    rows = []
    for ev in events:
        si, ei = ev["sig_i"], ev["ent_i"]
        if ei >= len(close):
            continue                                     # open / no entry bar
        settle_pos = dates.searchsorted(ev["expiry_date"])
        if settle_pos >= len(close):
            continue                                     # still open at data end
        S = float(close.iloc[si])
        vx = float(vix.iloc[si])
        KL = round(S / 5) * 5
        KS = round(S * (1 + w) / 5) * 5
        ST = float(close.iloc[settle_pos])
        intrinsic = max(ST - KL, 0.0) - max(ST - KS, 0.0)
        row = {
            "signal_date": str(dates[si].date()),
            "entry_date": str(dates[ei].date()),
            "settle_date": str(dates[settle_pos].date()),
            "year": dates[si].year,
            "S": S, "KL": KL, "KS": KS, "vix": vx,
            "hold_td": settle_pos - ei,
            "ST": ST,
            "gap_t1_pct": float(open_.iloc[ei]) / S - 1.0,
            "knife_pct": float(close.iloc[ei:settle_pos + 1].min()) / float(close.iloc[ei]) - 1.0,
            "capped": ST >= KS,
        }
        for tag, deb in (
            ("inc", debit_inc(S, KL, KS, dte, vx)),
            ("calib", debit_calib(S, KL, KS, dte, vx, offsets)),
            ("stress", debit_calib(S, KL, KS, dte, vx, offsets, stress_vp=2.0)),
        ):
            fill = deb * (1 + SLIP)
            per_ct = (intrinsic - fill) * 100.0 - COMMISSION
            cts = BUDGET / (fill * 100.0)
            row[f"debit_{tag}"] = round(deb, 3)
            row[f"pnl_{tag}"] = round(per_ct * cts, 0)   # budget-scaled USD
        row["cash_days"] = BUDGET * row["hold_td"]
        rows.append(row)
    return pd.DataFrame(rows)


# ── metrics pack ─────────────────────────────────────────────────────────────

def pack(tr: pd.DataFrame, tag="calib", era=None):
    t = tr if era is None else tr[tr.year >= 2020] if era == "post" else tr[tr.year < 2020]
    if len(t) == 0:
        return {"n": 0}
    p = t[f"pnl_{tag}"]
    k = max(1, int(np.ceil(len(p) * 0.10)))
    return {
        "n": len(t),
        "wr_pct": round((p > 0).mean() * 100),
        "total_k": round(p.sum() / 1000, 1),
        "avg_k": round(p.mean() / 1000, 2),
        "worst_k": round(p.min() / 1000, 1),
        "cvar10_k": round(p.nsmallest(k).mean() / 1000, 1),
        "per_cash_kday": round(p.sum() / (t.cash_days.sum() / 1000.0), 3),
        "med_hold": int(t.hold_td.median()),
        "capped_pct": round(t.capped.mean() * 100),
        "knife5_pct": round((t.knife_pct <= -0.05).mean() * 100),
    }


def year_bootstrap(a: pd.DataFrame, b: pd.DataFrame, tag="calib", n=4000, seed=7):
    """P(total_a > total_b) under year-block resampling (union of years)."""
    years = sorted(set(a.year) | set(b.year))
    ya = a.groupby("year")[f"pnl_{tag}"].sum().reindex(years).fillna(0.0).values
    yb = b.groupby("year")[f"pnl_{tag}"].sum().reindex(years).fillna(0.0).values
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(years), size=(n, len(years)))
    da = ya[idx].sum(axis=1)
    db = yb[idx].sum(axis=1)
    return float((da > db).mean())


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    spx, vix = load_data()
    close = spx["Close"]
    ma10 = close.rolling(10).mean()
    offsets = load_offsets()
    print(f"data: {close.index[0].date()} → {close.index[-1].date()}  n={len(close)}")

    # ═ 0. reproduction cross-check vs production walk-forward + CSV ═════════
    my_a = replay_a(close, dte=30)
    my_b = replay_b(close, ma10)
    from signals.q042_trigger import get_q042_history
    df_wf = spx.rename(columns={"Open": "open", "Close": "close"})
    ea, eb = get_q042_history(df_wf, start=START, end=str(close.index[-1].date()))
    my_a_dates = [str(close.index[e["sig_i"]].date()) for e in my_a]
    my_b_dates = [str(close.index[e["sig_i"]].date()) for e in my_b]
    pr_a_dates = [e["signal_date"] for e in ea]
    pr_b_dates = [e["signal_date"] for e in eb]
    print(f"\n[X-CHECK] A mine={len(my_a_dates)} prod={len(pr_a_dates)} "
          f"match={my_a_dates == pr_a_dates}")
    print(f"[X-CHECK] B mine={len(my_b_dates)} prod={len(pr_b_dates)} "
          f"match={my_b_dates == pr_b_dates}")
    if my_a_dates != pr_a_dates:
        print("  A diff mine-only:", sorted(set(my_a_dates) - set(pr_a_dates))[:6])
        print("  A diff prod-only:", sorted(set(pr_a_dates) - set(my_a_dates))[:6])
    if my_b_dates != pr_b_dates:
        print("  B diff mine-only:", sorted(set(my_b_dates) - set(pr_b_dates))[:6])
        print("  B diff prod-only:", sorted(set(pr_b_dates) - set(my_b_dates))[:6])
    csv = pd.read_csv(ROOT / "data" / "q042_backtest_trades.csv")
    csv_a = csv[csv.sleeve_id == "A"]
    csv_b = csv[csv.sleeve_id == "B"]
    print(f"[X-CHECK] CSV A n={len(csv_a)} B n={len(csv_b)}; "
          f"A dates ⊂ mine: {set(csv_a.signal_date) <= set(my_a_dates)}")

    # ═ 1. Sleeve A width × DTE grid (trigger/entry fixed at incumbent) ══════
    grid_rows = []
    trades_cache = {}
    for dte in (30, 60, 90):
        evs = replay_a(close, dte=dte)
        for w in (0.025, 0.05, 0.075):
            tr = build_trades(evs, spx, vix, w, dte, offsets)
            trades_cache[(w, dte)] = tr
            for tag in ("inc", "calib", "stress"):
                for era, lbl in ((None, "full"), ("post", "post2020")):
                    m = pack(tr, tag, era)
                    grid_rows.append({"w_pct": w * 100, "dte": dte,
                                      "pricing": tag, "era": lbl, **m})
    grid = pd.DataFrame(grid_rows)
    grid.to_csv(OUT / "q100_p1_a_grid.csv", index=False)
    inc_cell = trades_cache[(0.025, 30)]
    inc_cell.to_csv(OUT / "q100_p1_a_incumbent_trades.csv", index=False)
    print("\n═ Sleeve A grid (CALIB, full) ═")
    print(grid[(grid.pricing == "calib") & (grid.era == "full")]
          .drop(columns=["pricing", "era"]).to_string(index=False))
    print("\n═ Sleeve A grid (CALIB, post2020) ═")
    print(grid[(grid.pricing == "calib") & (grid.era == "post2020")]
          .drop(columns=["pricing", "era"]).to_string(index=False))
    print("\n═ Sleeve A grid (INC, full — reproduction ruler) ═")
    print(grid[(grid.pricing == "inc") & (grid.era == "full")]
          .drop(columns=["pricing", "era"]).to_string(index=False))
    print("\n═ Sleeve A grid (STRESS, full) ═")
    print(grid[(grid.pricing == "stress") & (grid.era == "full")]
          .drop(columns=["pricing", "era"]).to_string(index=False))

    # headline bootstraps (R1)
    for cand, lbl in (((0.05, 30), "5%/30 vs 2.5%/30"),
                      ((0.025, 60), "2.5%/60 vs 2.5%/30"),
                      ((0.05, 90), "5%/90(旧A) vs 2.5%/30(现A)"),
                      ((0.075, 30), "7.5%/30 vs 2.5%/30")):
        pboot = year_bootstrap(trades_cache[cand], inc_cell)
        print(f"[BOOT] P({lbl.split(' vs ')[0]} > incumbent) = {pboot:.3f}  ({lbl})")

    # ═ 2. Sleeve A entry timing (structure fixed 2.5/30) ════════════════════
    timing_rows = []
    timing_cache = {}
    for mode, lbl in (("t1", "T+1(现任)"), ("t5", "T+5"), ("reclaim", "MA10确认")):
        evs = replay_a(close, dte=30, entry_mode=mode, ma10=ma10)
        tr = build_trades(evs, spx, vix, 0.025, 30, offsets)
        timing_cache[mode] = tr
        for era, elbl in ((None, "full"), ("post", "post2020")):
            timing_rows.append({"mode": lbl, "era": elbl, **pack(tr, "calib", era)})
    tdf = pd.DataFrame(timing_rows)
    tdf.to_csv(OUT / "q100_p1_a_timing.csv", index=False)
    print("\n═ Sleeve A entry timing (CALIB) ═")
    print(tdf.to_string(index=False))
    for mode in ("t5", "reclaim"):
        print(f"[BOOT] P({mode} > t1) = {year_bootstrap(timing_cache[mode], timing_cache['t1']):.3f}")

    # ═ 3. Sleeve A trigger depth (structure fixed 2.5/30) ═══════════════════
    depth_rows = []
    depth_cache = {}
    for trig in (-0.03, -0.04, -0.05, -0.06):
        evs = replay_a(close, trig=trig, dte=30)
        tr = build_trades(evs, spx, vix, 0.025, 30, offsets)
        depth_cache[trig] = tr
        for era, elbl in ((None, "full"), ("post", "post2020")):
            depth_rows.append({"trig_pct": trig * 100, "era": elbl,
                               **pack(tr, "calib", era)})
    ddf = pd.DataFrame(depth_rows)
    ddf.to_csv(OUT / "q100_p1_a_depth.csv", index=False)
    print("\n═ Sleeve A trigger depth (CALIB) ═")
    print(ddf.to_string(index=False))
    for trig in (-0.03, -0.05, -0.06):
        print(f"[BOOT] P(dd{trig*100:.0f} > dd-4) = "
              f"{year_bootstrap(depth_cache[trig], depth_cache[-0.04]):.3f}")

    # ═ 4. Sleeve B variants (facts only, R2) ═════════════════════════════════
    b_rows = []
    for lbl, evs, w, dte in (
        ("B现任 reclaim 5%/90", replay_b(close, ma10), 0.05, 90),
        ("B即时 -15 T+1 5%/90", replay_b(close, ma10, immediate=True), 0.05, 90),
        ("B reclaim 5%/30", replay_b(close, ma10, dte=30), 0.05, 30),
        ("B reclaim 2.5%/90", replay_b(close, ma10), 0.025, 90),
    ):
        tr = build_trades(evs, spx, vix, w, dte, offsets)
        tr_l = tr.assign(variant=lbl)
        b_rows.append(tr_l)
        m = pack(tr, "calib")
        ms = pack(tr, "stress")
        print(f"\n[B] {lbl}: n={m['n']} wr={m.get('wr_pct')}% "
              f"total(calib)={m.get('total_k')}k stress={ms.get('total_k')}k "
              f"worst={m.get('worst_k')}k")
        if len(tr):
            print(tr[["signal_date", "entry_date", "settle_date", "vix",
                      "debit_calib", "pnl_calib", "pnl_stress", "knife_pct"]]
                  .to_string(index=False))
    pd.concat(b_rows).to_csv(OUT / "q100_p1_b_variants.csv", index=False)

    # ═ 5. execution realism: T+1 gap on incumbent A stream ══════════════════
    g = inc_cell.gap_t1_pct
    print("\n═ A 现任流 T+1 开盘 gap（signal close → entry open）═")
    print(f"median {g.median()*100:+.2f}%  p10 {g.quantile(.1)*100:+.2f}%  "
          f"worst {g.min()*100:+.2f}% @ {inc_cell.loc[g.idxmin(), 'signal_date']}")

    # ═ 6. sizing arithmetic (R3, deterministic) ══════════════════════════════
    nlv, pool, bcd = 629_000, 152_000, 38_300
    print("\n═ sizing 算术（今日 NLV $629k · liquid pool $152k · live BCD $38.3k/笔）═")
    for cap in (12.5, 17.5):
        a_usd = nlv * cap / 100
        for nb in (0, 1, 2):
            tot = a_usd + nb * bcd
            print(f"A@{cap}% = ${a_usd/1000:.1f}k + {nb}×BCD = ${tot/1000:.1f}k "
                  f"→ {tot/pool*100:.0f}% of pool {'⚠️ 抽穿' if tot > pool else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
