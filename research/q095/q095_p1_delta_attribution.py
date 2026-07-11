"""Q095 P1 — Delta PnL Attribution(账本本质有多少是 20 天 delta?)。

Question: 26y 引擎流 + 实盘的逐笔 PnL 中,delta 贡献占比多大?
residual(theta/vega/gamma 交叉 + 模型/摩擦)占多大?——PM 实盘感受②
"BCD/BPS 本质都是 ~20 天杠杆看多"的定量化,也是两段式架构(P4)的地基。

Method:
  1. 逐笔重建 legs:直接调 backtest.engine._build_legs(与引擎完全同源,
     FLAT sigma = entry_vix/100),消除重建漂移。aftermath IC 无法还原
     V3-A 变体 legs(Trade 不带 Recommendation),用标准 legs 近似
     (0.16Δ vs 0.12Δ short,二阶影响,披露)。
  2. 保真度门槛:重建 entry_value(per-share) vs trade.entry_credit,
     |误差|/|entry_credit| > 25% 的笔剔除路径分解(单独计数披露)。
  3. 日度路径分解:entry→exit 沿 SPX/VIX 日收盘,BS 重定价
     (sigma_t = VIX_t/100),delta_pnl = Σ Δ_{t-1}·(S_t−S_{t-1})·100·ct;
     residual = exit_pnl − delta_pnl(含 theta/vega/gamma 交叉+模型误差)。
  4. 聚合(避免单笔除零):
     - 美元份额:Σdelta_pnl / Σexit_pnl(按 family/regime/era 分层)
     - 跨笔方差:corr²(delta_pnl, exit_pnl)(delta 分量解释的截面方差)
     - 幅度占比:Σ|delta| / (Σ|delta|+Σ|residual|)
  5. 实盘案例:BPS 7200/6950(5-15→5-29)同法分解(strikes 实际值)。

口径:engine $500k canonical,FLAT sigma(与引擎默认一致;CALIB 差异计入
residual,attribution 结论对 sigma 口径二阶敏感,披露)。

Output: q095_p1_attribution.csv + 终端摘要。
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
ACCOUNT = 500_000.0
FIDELITY_MAX_ERR = 0.25


def _series(pkl: Path) -> pd.Series:
    df = pd.read_pickle(pkl)
    s = df["Close"] if "Close" in df else df["close"]
    idx = pd.to_datetime(s.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    s.index = idx.normalize()
    return s[~s.index.duplicated(keep="last")]


def load_daily() -> pd.DataFrame:
    spx = _series(ROOT / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl")
    vix = _series(ROOT / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl")
    df = pd.DataFrame({"spx": spx, "vix": vix}).dropna()
    if df.empty:
        raise RuntimeError("daily SPX/VIX join empty — index alignment failed")
    return df


def leg_value_and_delta(legs, spx: float, sigma: float, days_elapsed: int):
    """Per-share value (signed, debit>0) and net delta of the structure.

    口径与引擎完全一致:backtest.pricer(T = dte/252 交易日,r = 4.5%);
    days_elapsed 按交易日 bar 计数(引擎 days_held 同义)。
    """
    from backtest.pricer import call_delta, call_price, put_delta, put_price
    val = 0.0
    delta = 0.0
    for action, is_call, strike, dte0, qty in legs:
        dte = int(dte0) - int(days_elapsed)
        if is_call:
            v = call_price(spx, strike, dte, sigma)
            d = call_delta(spx, strike, dte, sigma)
        else:
            v = put_price(spx, strike, dte, sigma)
            d = put_delta(spx, strike, dte, sigma)
        val += action * qty * v
        delta += action * qty * d
    return val, delta


def decompose(trade, legs, daily: pd.DataFrame):
    """Path delta PnL from entry to exit along daily closes."""
    e0 = pd.Timestamp(str(trade.entry_date))
    e1 = pd.Timestamp(str(trade.exit_date))
    path = daily.loc[e0:e1]
    if len(path) < 2:
        return None
    ct = float(trade.contracts)
    delta_pnl = 0.0
    # delta at t-1 × price move t-1→t;elapsed 按交易日 bar 计数(引擎同义)
    prev_spx = float(path["spx"].iloc[0])
    for i in range(1, len(path)):
        sigma = float(path["vix"].iloc[i - 1]) / 100.0
        _, d = leg_value_and_delta(legs, prev_spx, max(sigma, 1e-4), i - 1)
        cur_spx = float(path["spx"].iloc[i])
        delta_pnl += d * (cur_spx - prev_spx) * 100.0 * ct
        prev_spx = cur_spx
    return delta_pnl


def main() -> int:
    import backtest.engine as eng
    OUT.mkdir(parents=True, exist_ok=True)
    daily = load_daily()

    # ── Spy on _build_legs:捕获引擎真实 legs(含 Recommendation 变体 legs,
    #    如 aftermath V3-A / BCS_HV 0.20Δ),消除重建漂移 ────────────────────
    captured: dict[tuple, list] = {}
    orig_build = eng._build_legs

    def spy(rec_or_strategy, spx, sigma, params=None, sigma_fn=None):
        if params is None:
            legs, dte = orig_build(rec_or_strategy, spx, sigma, sigma_fn=sigma_fn)
        else:
            legs, dte = orig_build(rec_or_strategy, spx, sigma, params, sigma_fn)
        strat = (rec_or_strategy.strategy if hasattr(rec_or_strategy, "strategy")
                 else rec_or_strategy)
        key = (str(strat), round(float(spx), 2))
        captured.setdefault(key, []).append(legs)
        return legs, dte

    eng._build_legs = spy
    try:
        trades, _, _ = eng.run_backtest(start_date="2000-01-01", verbose=False,
                                        account_size=ACCOUNT)
    finally:
        eng._build_legs = orig_build

    rows = []
    excl: dict[str, int] = {}

    def _skip(t, reason: str):
        sname = t.strategy.value if hasattr(t.strategy, "value") else str(t.strategy)
        excl[f"{sname}|{reason}"] = excl.get(f"{sname}|{reason}", 0) + 1

    for t in trades:
        if getattr(t, "open_at_end", False) or not t.exit_date:
            continue
        sname = t.strategy.value if hasattr(t.strategy, "value") else str(t.strategy)
        sigma0 = max(float(t.entry_vix), 1.0) / 100.0
        key = (str(t.strategy), round(float(t.entry_spx), 2))
        bucket = captured.get(key) or []
        if not bucket:
            _skip(t, "no_leg_match")
            continue
        legs = bucket.pop(0)
        # fidelity: rebuilt entry value vs recorded entry_credit (per-share signed)
        v0, d0 = leg_value_and_delta(legs, float(t.entry_spx), sigma0, 0)
        rec = float(t.entry_credit)
        err = abs(v0 - rec) / max(abs(rec), 1e-9)
        if err > FIDELITY_MAX_ERR:
            _skip(t, "fidelity")
            continue
        dp = decompose(t, legs, daily)
        if dp is None:
            _skip(t, "path_data")
            continue
        era = "post2020" if str(t.entry_date) >= "2020-01-01" else "pre2020"
        fam = ("BCD" if "Diagonal" in sname
               else "IC" if "Iron Condor" in sname
               else "BCS" if "Bear Call" in sname
               else "BPS")
        hv = "HV" if "High Vol" in sname else "nonHV"
        rows.append({
            "entry_date": str(t.entry_date), "exit_date": str(t.exit_date),
            "strategy": sname, "family": fam, "hv": hv, "era": era,
            "entry_delta_pershare": round(d0, 4),
            "contracts": round(float(t.contracts), 4),
            "exit_pnl": round(float(t.exit_pnl), 2),
            "delta_pnl": round(dp, 2),
            "residual": round(float(t.exit_pnl) - dp, 2),
            "fidelity_err": round(err, 4),
        })
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "q095_p1_attribution.csv", index=False)
    print(f"trades decomposed n={len(df)} | excluded={sum(excl.values())}")
    for k in sorted(excl):
        print(f"  excl {k}: {excl[k]}")

    def report(sub: pd.DataFrame, label: str):
        if len(sub) < 5:
            print(f"[{label}] n={len(sub)} <5 — 只记不算")
            return
        tot, dlt, res = sub["exit_pnl"].sum(), sub["delta_pnl"].sum(), sub["residual"].sum()
        share = dlt / tot if abs(tot) > 1 else float("nan")
        mag = sub["delta_pnl"].abs().sum() / (sub["delta_pnl"].abs().sum() + sub["residual"].abs().sum())
        r2 = np.corrcoef(sub["delta_pnl"], sub["exit_pnl"])[0, 1] ** 2 if len(sub) > 2 else float("nan")
        print(f"[{label}] n={len(sub)} | Σpnl ${tot:,.0f} = Σdelta ${dlt:,.0f} + Σresid ${res:,.0f}"
              f" | $份额 {share*100:.0f}% | 幅度占比 {mag*100:.0f}% | 截面R² {r2:.2f}")

    print("\n=== 总体 ===")
    report(df, "all")
    print("\n=== by family ===")
    for f in sorted(df["family"].unique()):
        report(df[df["family"] == f], f)
    print("\n=== by era ===")
    for e in ("pre2020", "post2020"):
        report(df[df["era"] == e], e)
    print("\n=== HV vs nonHV ===")
    for h in ("nonHV", "HV"):
        report(df[df["hv"] == h], h)

    # ── 实盘案例:BPS 7200/6950 (2026-05-15 → 05-29, credit 34.5, 1ct) ────────
    print("\n=== 实盘 BPS 案例(strikes 实际值)===")
    # expiry 2026-06-18:5-15 起 ≈ 24 个交易日(引擎 dte 口径 = 交易日)
    legs_live = [(-1, False, 7200.0, 24, 1), (+1, False, 6950.0, 24, 1)]

    class _T:
        entry_date, exit_date, contracts = "2026-05-15", "2026-05-29", 1.0
    dp = decompose(_T, legs_live, daily)
    # 实际 PnL:credit 34.5 收 → 平仓成本未知,用 BS 路径重建近似披露
    e0, e1 = pd.Timestamp("2026-05-15"), pd.Timestamp("2026-05-29")
    s1 = float(daily.loc[:e1, "spx"].iloc[-1]); v1 = float(daily.loc[:e1, "vix"].iloc[-1])
    bars = len(daily.loc[e0:e1]) - 1
    vend, _ = leg_value_and_delta(legs_live, s1, v1 / 100.0, bars)
    # credit 结构:entry_value = -34.5(收权利金);PnL/share = val_exit − val_entry
    pnl_est = (vend - (-34.5)) * 100
    print(f"delta_pnl ≈ ${dp:,.0f} | BS 估算全程 PnL ≈ ${pnl_est:,.0f} "
          f"| delta 份额 ≈ {dp/pnl_est*100 if abs(pnl_est)>1 else float('nan'):.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
