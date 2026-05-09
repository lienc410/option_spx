"""
Q052 — H1: Technical Exit Overlay
==================================
PM hypothesis: 利用技术分析判断进入下跌区间，主动 exit，而不是被动等待
3x/4x credit stop。如果有效，可以避免 stop loss 的尾部，且不依赖
"3x mark" 这个对 deep OTM 失真的 stop 语义。

Three exit variants tested on baseline Δ=0.20 DTE=45 (and best H3 config):

V_baseline:     credit stop only (mark ≥ 3× entry)
V_trend_only:   trend exit only (close when trend NOT BULLISH); no credit stop
V_trend_credit: trend exit + soft credit stop (mark ≥ 5× entry, less restrictive)

Trend exit signal: when ATR-normalized trend changes from BULLISH to anything
non-BULLISH (NEUTRAL/BEARISH/INSUFFICIENT_DATA), close position next day.
"""
from __future__ import annotations

import sys, math
from pathlib import Path
from collections import defaultdict
from typing import Literal

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from research.strategies.ES_puts.backtest import (
    _load_data, _trend, _make_row, _bp_per_contract,
    put_price, find_strike_for_delta,
    BacktestResult, PutTrade, PutPosition,
    PROFIT_TARGET, GAMMA_DTE, SPX_MULTIPLIER,
    WARMUP_DAYS, P1_INITIAL_EQUITY, TrendSignal,
)
from backtest.metrics_portfolio import compute_portfolio_metrics
from backtest.portfolio import DailyPortfolioRow
from backtest.run_bootstrap_ci import bootstrap_ci

START = "2000-01-01"
STRESS_WINDOWS = [
    ("2008 GFC",   "2008-01-01", "2009-06-30"),
    ("2020 COVID", "2020-01-01", "2020-09-30"),
    ("2022 Bear",  "2022-01-01", "2022-12-31"),
]

ExitMode = Literal["credit_only", "trend_only", "trend_credit_soft"]


def run_with_exit(
    target_delta: float,
    entry_dte:    int,
    exit_mode:    ExitMode,
    stop_mult:    float = 3.0,
    soft_stop:    float = 5.0,
    n_contracts:  int   = 1,
) -> BacktestResult:
    """Phase 1 single-slot, parametrised delta/DTE/exit_mode."""
    data, full_spx = _load_data()
    sim = data[data.index >= pd.Timestamp(START)]

    result    = BacktestResult(phase=f"h1_{exit_mode}_d{target_delta}_dte{entry_dte}",
                                mode="filtered")
    equity    = P1_INITIAL_EQUITY
    peak_eq   = P1_INITIAL_EQUITY
    daily_rows: list[DailyPortfolioRow] = []
    trades:     list[PutTrade]          = []
    positions:  dict[int, PutPosition]  = {}

    gamma_dte = max(GAMMA_DTE, entry_dte // 9)

    for date, row in sim.iterrows():
        spx = float(row["spx"])
        vix = float(row["vix"])
        sig = vix / 100.0
        dstr = date.strftime("%Y-%m-%d")
        daily_pnl = 0.0

        window = full_spx[full_spx.index <= date].iloc[-200:]
        warmed = len(window) >= WARMUP_DAYS
        cur_trend = _trend(window, spx) if warmed else TrendSignal.NEUTRAL
        bullish = (cur_trend == TrendSignal.BULLISH)

        # Manage open position
        pos = positions.get(entry_dte)
        if pos:
            pos.expiry_dte -= 1
            cur = put_price(spx, pos.strike, max(pos.expiry_dte, 0), sig)
            daily_pnl += (pos.prev_val - cur) * pos.contracts * SPX_MULTIPLIER

            reason = None

            # Standard exit checks (always active)
            if   pos.expiry_dte <= gamma_dte:           reason = "gamma_risk"
            elif cur <= pos.profit_premium:              reason = "profit_target"
            elif pos.expiry_dte <= 0:                   reason = "expiry"

            # Mode-specific exit logic
            if not reason:
                if exit_mode == "credit_only":
                    if cur >= pos.entry_premium * stop_mult:
                        reason = "stop_loss"
                elif exit_mode == "trend_only":
                    # Pure trend exit: close immediately when trend not BULLISH
                    if not bullish:
                        reason = "trend_exit"
                elif exit_mode == "trend_credit_soft":
                    # Trend exit primary, soft credit stop as fallback
                    if not bullish:
                        reason = "trend_exit"
                    elif cur >= pos.entry_premium * soft_stop:
                        reason = "stop_loss_soft"

            if reason:
                pnl = (pos.entry_premium - cur) * pos.contracts * SPX_MULTIPLIER
                trades.append(PutTrade(
                    slot=entry_dte, entry_date=pos.entry_date, exit_date=dstr,
                    entry_spx=pos.entry_spx, exit_spx=spx,
                    entry_vix=pos.entry_vix,
                    entry_premium=pos.entry_premium, exit_premium=cur,
                    dte_at_entry=entry_dte, dte_at_exit=pos.expiry_dte,
                    exit_reason=reason, contracts=pos.contracts, pnl=pnl,
                ))
                del positions[entry_dte]
            else:
                pos.prev_val = cur

        # Open new position when bullish, position empty
        if entry_dte not in positions and warmed and bullish:
            try:
                k = find_strike_for_delta(spx, entry_dte, sig, target_delta, False)
                prem = put_price(spx, k, entry_dte, sig)
            except Exception:
                k, prem = None, 0
            if prem > 0.30:
                stop_p = prem * stop_mult if exit_mode == "credit_only" else prem * soft_stop
                positions[entry_dte] = PutPosition(
                    slot=entry_dte, entry_date=dstr, expiry_dte=entry_dte,
                    strike=k, entry_premium=prem, entry_spx=spx, entry_vix=vix,
                    contracts=float(n_contracts),
                    bp_used=n_contracts * _bp_per_contract(spx, k, prem),
                    stop_premium=stop_p,
                    profit_premium=prem * PROFIT_TARGET,
                    prev_val=prem,
                )

        dr, equity, peak_eq = _make_row(dstr, equity, daily_pnl, peak_eq, positions, vix,
                                         result.phase)
        daily_rows.append(dr)

    result.trades            = trades
    result.portfolio_metrics = compute_portfolio_metrics(daily_rows).to_dict()
    result.daily_rows        = daily_rows
    if len(trades) >= 10:
        result.bootstrap = bootstrap_ci([t.pnl for t in trades])
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def stress_pnl(trades):
    out = {}
    for label, start, end in STRESS_WINDOWS:
        ts, te = pd.Timestamp(start), pd.Timestamp(end)
        out[label] = round(sum(t.pnl for t in trades
                                if ts <= pd.Timestamp(t.entry_date) <= te), 0)
    return out


def worst_year(trades):
    by_year = defaultdict(float)
    for t in trades:
        y = int(t.exit_date[:4]) if t.exit_date else int(t.entry_date[:4])
        by_year[y] += t.pnl
    if not by_year: return "—", 0
    wy = min(by_year, key=by_year.get)
    return str(wy), by_year[wy]


def exit_breakdown(trades):
    by_reason = defaultdict(int)
    pnl_by_reason = defaultdict(float)
    for t in trades:
        by_reason[t.exit_reason] += 1
        pnl_by_reason[t.exit_reason] += t.pnl
    return dict(by_reason), dict(pnl_by_reason)


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    print("=" * 84)
    print("Q052 / H1 — /ES Technical Exit Overlay")
    print("  Trend-based exit replaces or augments credit stop")
    print("=" * 84)

    # Test grid: focus on (Δ=0.20, 0.10) × (DTE=45, 90) × 3 exit modes
    deltas = [0.20, 0.10]
    dtes   = [45, 90]
    modes  = ["credit_only", "trend_only", "trend_credit_soft"]

    results = {}
    for d in deltas:
        for dte in dtes:
            for m in modes:
                tag = f"d{d}_dte{dte}_{m}"
                print(f"\n  Running Δ={d:.2f} DTE={dte} exit={m} …", flush=True)
                r = run_with_exit(d, dte, m, stop_mult=3.0, soft_stop=5.0)
                results[tag] = (d, dte, m, r)
                bs = r.bootstrap or {}
                m_ann = r.portfolio_metrics.get('ann_return', 0) * 100
                print(f"    → {len(r.trades)} trades  AnnROE {m_ann:+.2f}%  "
                      f"CI [{bs.get('ci_lo',0):+,.0f}, {bs.get('ci_hi',0):+,.0f}]  "
                      f"{'✅' if bs.get('significant') else '❌'}")

    # ── Detail per config ─────────────────────────────────────────────────────
    print("\n\n" + "=" * 84)
    print("DETAIL")
    print("=" * 84)
    for tag, (d, dte, mode, r) in results.items():
        t = r.trades
        if not t:
            print(f"\n  Δ={d}  DTE={dte}  {mode}: no trades")
            continue
        ws = [x for x in t if x.pnl > 0]
        m  = r.portfolio_metrics
        bs = r.bootstrap or {}
        eb_ct, eb_pnl = exit_breakdown(t)
        wy, wp = worst_year(t)
        sp = stress_pnl(t)

        sig = bs.get("significant", False)
        marker = "✅ SIGNIFICANT" if sig else "❌"
        print(f"\n  Δ={d:.2f}  DTE={dte}  exit={mode}  {marker}")
        print(f"    Trades: {len(t)}   WR: {len(ws)/len(t)*100:.1f}%")
        print(f"    Avg P&L: ${bs.get('mean',0):,.0f}/trade   Total: ${sum(x.pnl for x in t):,.0f}")
        print(f"    AnnROE: {m.get('ann_return',0)*100:+.2f}%   "
              f"Sharpe: {m.get('daily_sharpe',0):.3f}")
        print(f"    Worst trade: ${min(x.pnl for x in t):,.0f}   "
              f"Worst year: {wy} ${wp:,.0f}")
        print(f"    CI: [{bs.get('ci_lo',0):+,.0f}, {bs.get('ci_hi',0):+,.0f}]")
        print(f"    Exit breakdown:")
        for reason in sorted(eb_ct, key=lambda r: -eb_ct[r]):
            ct  = eb_ct[reason]
            pnl = eb_pnl[reason]
            print(f"      {reason:18s}  n={ct:>3}  total=${pnl:+,.0f}  avg=${pnl/ct:+,.0f}")
        print(f"    Stress: 2008=${sp['2008 GFC']:+,.0f}  "
              f"2020=${sp['2020 COVID']:+,.0f}  2022=${sp['2022 Bear']:+,.0f}")

    # ── Summary table ─────────────────────────────────────────────────────────
    print("\n\n" + "=" * 84)
    print("H1 SUMMARY: Exit-Mode Comparison")
    print("=" * 84)
    print(f"  {'Δ':>5} {'DTE':>4}  {'Mode':>20}  {'n':>5}  {'WR%':>5}  "
          f"{'AvgPnL':>8}  {'AnnROE%':>8}  {'CI_lo':>8}  {'CI_hi':>8}  Sig")
    for tag, (d, dte, mode, r) in results.items():
        t = r.trades
        if not t: continue
        ws = [x for x in t if x.pnl > 0]
        m = r.portfolio_metrics
        bs = r.bootstrap or {}
        sig = "✅" if bs.get("significant") else "❌"
        print(f"  {d:>5.2f} {dte:>4}  {mode:>20}  {len(t):>5}  "
              f"{len(ws)/len(t)*100:>5.1f}  ${bs.get('mean',0):>7,.0f}  "
              f"{m.get('ann_return',0)*100:>+8.2f}  "
              f"{bs.get('ci_lo',0):>+8,.0f}  {bs.get('ci_hi',0):>+8,.0f}  {sig}")

    # ── Verdict ──────────────────────────────────────────────────────────────
    print("\n\n" + "=" * 84)
    print("H1 VERDICT")
    print("=" * 84)
    sig = [(d, dte, m, r) for tag, (d, dte, m, r) in results.items()
           if r.bootstrap and r.bootstrap.get("significant", False)]
    if sig:
        print(f"\n  ✅ {len(sig)} configurations achieved significance:")
        for d, dte, m, r in sig:
            ann = r.portfolio_metrics.get('ann_return',0)*100
            print(f"     Δ={d:.2f} DTE={dte} exit={m}  AnnROE={ann:+.2f}%")

        # Compare credit_only vs trend variants
        print("\n  Direct comparison (Δ=0.20 DTE=45):")
        for mode_label in modes:
            tag = f"d0.2_dte45_{mode_label}"
            if tag in results:
                _, _, _, r = results[tag]
                ann = r.portfolio_metrics.get('ann_return',0)*100
                bs = r.bootstrap or {}
                print(f"    {mode_label:>20}  AnnROE {ann:+.2f}%  "
                      f"CI [{bs.get('ci_lo',0):+,.0f}, {bs.get('ci_hi',0):+,.0f}]")
    else:
        print("\n  ❌ No configuration achieved significance.")
        print("\n  Best AnnROE:")
        best = max(
            [(tag, d, dte, m, r) for tag, (d, dte, m, r) in results.items() if r.trades],
            key=lambda x: x[4].portfolio_metrics.get('ann_return', -999)
        )
        ann = best[4].portfolio_metrics.get('ann_return',0)*100
        bs  = best[4].bootstrap or {}
        print(f"    Δ={best[1]:.2f} DTE={best[2]} exit={best[3]}  "
              f"AnnROE {ann:+.2f}%  CI [{bs.get('ci_lo',0):+,.0f}, {bs.get('ci_hi',0):+,.0f}]")


if __name__ == "__main__":
    run()
