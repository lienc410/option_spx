"""Q107 P1 — BPS 持有窗口：min_hold vs DTE 延长（PM 2026-09-14 立项）。

**问题来源**：PM 发现策略卡矛盾——BPS 30 DTE 入场、短腿 21 DTE 平仓（=9 DTE 刻度
持有），而 profit_target 被 min_hold_days=10 gate → **60% 止盈对 NORMAL BPS 永不
可达**（26y 回测 0 次触发，14 笔全走 roll_21dte）。HIGH_VOL BPS 无此问题
（35−21=14>10，注释明写"enough window"——作者修了 HV 没回头修 NORMAL）。

**四个预注册变体**（禁网格搜索；min_hold=5 为"半个现任值"的结构性选择，
非拟合切点）：
  INC : normal_dte=30, min_hold_days=10  —— 现任（止盈死区）
  A   : normal_dte=30, min_hold_days=5   —— 止盈复活，窗口不变
  B   : normal_dte=45, min_hold_days=10  —— 窗口延长（45−21=24>10 自然复活）
  C   : normal_dte=45, min_hold_days=5   —— 两者都改

**预注册判定规则（先于跑数写定）**：
  R1 主指标 = marginal $/BP-day（账户 cash/BP-bound，feedback_strategy_metrics_pack
     强制）；总 PnL 为辅——只看总额会奖励"占用更久换更多 credit"的假胜。
  R2 强制指标包：worst trade / CVaR10 / worst-21TD / worst-63TD / WR / maxDD。
  R3 显著性：year-block bootstrap P(候选 > INC) ≥ 0.90（CALIB 主臂）。
  R4 时代分层 full / post-2020 符号一致。
  R5 **B/C 特有副作用必须量化**（45 DTE 撞 IC 的 45 DTE）：BP 占用天数、
     并发笔数、IC 被挤出笔数——延长窗口不是免费的。
  R6 噪音门槛 ROE Δ < 0.5pp = 噪音（已校准）。
  R7 本脚本只跑这 4 格；任何"再试试 min_hold=7/DTE=38"的冲动 = 切点过拟合，禁。

**全账本口径**：BPS 改动会挤占 IC/BCD 的资源与时间窗，故所有指标同时报
per-strategy（BPS）与 portfolio（全账本）两层——单策略赢而账本输 = 否决。
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.engine import run_backtest                    # noqa: E402
from strategy.selector import DEFAULT_PARAMS                # noqa: E402

OUT = ROOT / "research" / "q107"
START = "2007-01-01"

VARIANTS = {
    "INC": dict(normal_dte=30, min_hold_days=10),
    "A":   dict(normal_dte=30, min_hold_days=5),
    "B":   dict(normal_dte=45, min_hold_days=10),
    "C":   dict(normal_dte=45, min_hold_days=5),
}


def _trades_df(res) -> pd.DataFrame:
    rows = []
    for t in res.trades:
        rows.append({
            "strategy_key": str(getattr(t, "strategy", "")),   # enum → str
            "entry_date": str(getattr(t, "entry_date", "")),
            "exit_date": str(getattr(t, "exit_date", "")),
            "exit_reason": str(getattr(t, "exit_reason", "")),
            "pnl": float(getattr(t, "exit_pnl", 0.0) or 0.0),
            "hold_dte": int(getattr(t, "hold_days", 0) or 0),   # DTE 刻度（实测确认）
            "bp_used": float(getattr(t, "total_bp", 0.0) or 0.0),
        })
    return pd.DataFrame(rows)


def pack(df: pd.DataFrame, label: str) -> dict:
    """R2 强制指标包。bp_day = Σ(bp_used × hold_dte) 作占用分母。"""
    if len(df) == 0:
        return {"variant": label, "n": 0}
    p = df.pnl
    k = max(1, int(np.ceil(len(p) * 0.10)))
    bp_days = (df.bp_used * df.hold_dte).sum()
    return {
        "variant": label, "n": len(df),
        "total_k": round(p.sum() / 1000, 1),
        "wr_pct": round((p > 0).mean() * 100),
        "worst_k": round(p.min() / 1000, 1),
        "cvar10_k": round(p.nsmallest(k).mean() / 1000, 1),
        "per_bp_kday": round(p.sum() / (bp_days / 1000), 3) if bp_days else None,
        "med_hold_dte": int(df.hold_dte.median()),
        "bp_days_k": round(bp_days / 1000),
        "pt_fired": int((df.exit_reason.astype(str)
                         .str.contains("profit|50pct")).sum()),
    }


def worst_window(df: pd.DataFrame, td: int) -> float:
    if len(df) == 0:
        return 0.0
    s = df.groupby("exit_date").pnl.sum()
    s.index = pd.to_datetime(s.index)
    daily = s.resample("D").sum().fillna(0.0)
    return float(daily.rolling(td).sum().min())


def year_bootstrap(a: pd.DataFrame, b: pd.DataFrame, n=4000, seed=11) -> float:
    ya = a.assign(y=pd.to_datetime(a.exit_date).dt.year).groupby("y").pnl.sum()
    yb = b.assign(y=pd.to_datetime(b.exit_date).dt.year).groupby("y").pnl.sum()
    years = sorted(set(ya.index) | set(yb.index))
    va = ya.reindex(years).fillna(0).values
    vb = yb.reindex(years).fillna(0).values
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(years), size=(n, len(years)))
    return float((va[idx].sum(axis=1) > vb[idx].sum(axis=1)).mean())


def main() -> int:
    results = {}
    for label, over in VARIANTS.items():
        params = replace(DEFAULT_PARAMS, **over)
        print(f"── running {label}: {over} …", flush=True)
        res = run_backtest(start_date=START, params=params, verbose=False)
        df = _trades_df(res)
        results[label] = df
        df.to_csv(OUT / f"q107_trades_{label}.csv", index=False)

    rows_bps, rows_all = [], []
    for label, df in results.items():
        bps = df[df.strategy_key.astype(str).str.contains("BULL_PUT", case=False, na=False)]
        rows_bps.append({**pack(bps, label),
                         "worst21_k": round(worst_window(bps, 21) / 1000, 1),
                         "worst63_k": round(worst_window(bps, 63) / 1000, 1)})
        rows_all.append({**pack(df, label),
                         "worst21_k": round(worst_window(df, 21) / 1000, 1),
                         "worst63_k": round(worst_window(df, 63) / 1000, 1)})
    bps_tbl = pd.DataFrame(rows_bps)
    all_tbl = pd.DataFrame(rows_all)
    print("\n═ BPS only ═"); print(bps_tbl.to_string(index=False))
    print("\n═ Portfolio (全账本) ═"); print(all_tbl.to_string(index=False))
    bps_tbl.to_csv(OUT / "q107_p1_bps.csv", index=False)
    all_tbl.to_csv(OUT / "q107_p1_portfolio.csv", index=False)

    print("\n═ R3 bootstrap P(候选 > INC) ═")
    for label in ("A", "B", "C"):
        for scope, sel in (("BPS", lambda d: d[d.strategy_key.astype(str)
                                               .str.contains("BULL_PUT", case=False, na=False)]),
                           ("ALL", lambda d: d)):
            p = year_bootstrap(sel(results[label]), sel(results["INC"]))
            print(f"  {label} vs INC [{scope}]: {p:.3f}")

    # R5: 45 DTE 撞 IC 的并发副作用
    print("\n═ R5 副作用（IC 笔数 / 全账本占用）═")
    for label, df in results.items():
        ic = df[df.strategy_key.astype(str).str.contains("IRON_CONDOR", case=False, na=False)]
        print(f"  {label}: IC n={len(ic)} Σ${ic.pnl.sum()/1000:+.1f}k | "
              f"全账本 bp_days {int((df.bp_used*df.hold_dte).sum()/1000)}k")
    return 0


if __name__ == "__main__":
    sys.exit(main())
