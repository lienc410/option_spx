"""Q063 Phase 5 — Test 2nd Quant's multi-factor gate proposal.

2nd Quant proposed (2026-05-11) replacing current IVR > 55 single-condition
gate with a 3-factor AND composite:

  BLOCK if:
    IVR > 55
    AND VIX_RISING:  VIX_5d_MA > VIX_10d_MA AND VIX_today > VIX_5d_MA
    AND (
      SPX_NOT_BULLISH: SPX < MA50 OR (SPX < MA20 AND SPX_20d_return < 0)
      OR
      SPX_DRAWDOWN_EXPANDING: SPX_60d_dd <= -3% AND dd_today < dd_5d_ago - 1%
    )

Phase 5 evaluates this gate empirically:
  - Full 19y backtest vs baseline
  - OOS split (07-17 train / 18-26 test)
  - Recent windows (last 5y/3y/2y)
  - Per-year attribution
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from collections import defaultdict

import strategy.selector as sel
from backtest import engine as engine_mod
from backtest.engine import run_backtest
from strategy.selector import IVSignal, Regime, StrategyName

REPO = Path(__file__).resolve().parents[2]
SPX_PKL = REPO / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
VIX_PKL = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"

START = "2007-01-01"
END = "2026-05-10"
ACCOUNT = 150_000.0


def _load_features() -> pd.DataFrame:
    """Precompute VIX/SPX features needed for 2nd Quant gate evaluation."""
    spx = pickle.loads(SPX_PKL.read_bytes())
    vix = pickle.loads(VIX_PKL.read_bytes())
    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    vix.index = pd.to_datetime(vix.index).tz_localize(None)
    df = pd.DataFrame(index=spx.index)
    df["spx"] = spx["Close"]
    df["vix"] = vix["Close"].reindex(df.index).ffill()
    df["spx_ma20"] = df["spx"].rolling(20).mean()
    df["spx_ma50"] = df["spx"].rolling(50).mean()
    df["spx_20d_return"] = df["spx"].pct_change(20)
    df["spx_60d_high"] = df["spx"].rolling(60).max()
    df["spx_drawdown_60d"] = df["spx"] / df["spx_60d_high"] - 1
    df["spx_dd_5d_ago"] = df["spx_drawdown_60d"].shift(5)
    df["vix_5d_ma"] = df["vix"].rolling(5).mean()
    df["vix_10d_ma"] = df["vix"].rolling(10).mean()
    return df


# Global feature df (computed once)
_FEATURES_DF: pd.DataFrame | None = None


def _2nd_quant_gate(vix_value: float, ivp: float, date_str: str) -> bool:
    """Return True if 2nd Quant gate would BLOCK this entry."""
    global _FEATURES_DF
    if _FEATURES_DF is None:
        _FEATURES_DF = _load_features()
    if ivp <= 55:
        return False  # not in gated range
    if date_str not in _FEATURES_DF.index.strftime("%Y-%m-%d").tolist():
        # fallback: search nearest date <= date_str
        idx = _FEATURES_DF.index[_FEATURES_DF.index <= pd.Timestamp(date_str)]
        if len(idx) == 0:
            return ivp >= 55  # fallback to baseline-equivalent
        row = _FEATURES_DF.loc[idx[-1]]
    else:
        row = _FEATURES_DF.loc[date_str]

    # VIX_RISING
    if pd.isna(row.vix_5d_ma) or pd.isna(row.vix_10d_ma):
        return False
    vix_rising = (row.vix_5d_ma > row.vix_10d_ma) and (row.vix > row.vix_5d_ma)
    if not vix_rising:
        return False

    # SPX_NOT_BULLISH
    if pd.isna(row.spx_ma50) or pd.isna(row.spx_ma20) or pd.isna(row.spx_20d_return):
        spx_not_bullish = False
    else:
        spx_not_bullish = (row.spx < row.spx_ma50) or (
            row.spx < row.spx_ma20 and row.spx_20d_return < 0
        )

    # SPX_DRAWDOWN_EXPANDING
    if pd.isna(row.spx_drawdown_60d) or pd.isna(row.spx_dd_5d_ago):
        dd_expanding = False
    else:
        dd_expanding = (row.spx_drawdown_60d <= -0.03) and (
            row.spx_drawdown_60d < row.spx_dd_5d_ago - 0.01
        )

    return spx_not_bullish or dd_expanding


def _make_patcher(gate_fn, base_select, use_date=False):
    BPS = StrategyName.BULL_PUT_SPREAD
    def patched(vix, iv, trend, params=sel.DEFAULT_PARAMS):
        rec = base_select(vix, iv, trend, params)
        if rec.strategy != BPS:
            return rec
        from strategy.selector import _effective_iv_signal, _reduce_wait
        if not (vix.regime == Regime.NORMAL
                and _effective_iv_signal(iv) == IVSignal.NEUTRAL
                and trend.signal.value == "BULLISH"):
            return rec
        block = gate_fn(vix.vix, iv.iv_percentile, vix.date) if use_date \
                else gate_fn(vix.vix, iv.iv_percentile)
        if block:
            return _reduce_wait(
                f"blocked", vix, iv, trend, macro_warn=not trend.above_200,
                canonical_strategy=BPS.value, params=params,
            )
        return rec
    return patched


def _run_with_gate(gate_fn, base_select, orig_engine_select, use_date=False):
    sel.select_strategy = _make_patcher(gate_fn, base_select, use_date)
    engine_mod.select_strategy = sel.select_strategy
    try:
        return run_backtest(start_date=START, end_date=END, account_size=ACCOUNT, verbose=False)
    finally:
        sel.select_strategy = base_select
        engine_mod.select_strategy = orig_engine_select


def main():
    print("=" * 100)
    print("Q063 Phase 5 — 2nd Quant Multi-Factor Gate Backtest")
    print("=" * 100)
    orig_select = sel.select_strategy
    orig_engine_select = engine_mod.select_strategy
    orig_upper = sel.BPS_NNB_IVP_UPPER
    sel.BPS_NNB_IVP_UPPER = 999

    full_years = (pd.Timestamp(END) - pd.Timestamp(START)).days / 365.25

    print("\nRunning baseline (IVR > 55)...")
    bt_bl = _run_with_gate(lambda v, ivp: ivp >= 55, orig_select, orig_engine_select)
    print("Running 2nd Quant (multi-factor)...")
    bt_2q = _run_with_gate(_2nd_quant_gate, orig_select, orig_engine_select, use_date=True)

    bps_bl = [t for t in bt_bl.trades if t.strategy.value == "Bull Put Spread"]
    bps_2q = [t for t in bt_2q.trades if t.strategy.value == "Bull Put Spread"]
    pnls_bl = [t.exit_pnl for t in bps_bl]
    pnls_2q = [t.exit_pnl for t in bps_2q]
    all_bl = [t.exit_pnl for t in bt_bl.trades]
    all_2q = [t.exit_pnl for t in bt_2q.trades]

    print(f"\n{'='*100}")
    print(f"Test 1 — Full sample 19y comparison")
    print(f"{'='*100}")
    def _stats(bps, all_trades):
        return {
            "bps_n": len(bps),
            "wr": sum(1 for p in [t.exit_pnl for t in bps] if p > 0)/len(bps)*100 if bps else 0,
            "total": sum(t.exit_pnl for t in bps),
            "avg": sum(t.exit_pnl for t in bps)/len(bps) if bps else 0,
            "worst": min((t.exit_pnl for t in bps), default=0),
            "all_total": sum(t.exit_pnl for t in all_trades),
            "all_ann": sum(t.exit_pnl for t in all_trades)/full_years,
        }
    sbl = _stats(bps_bl, bt_bl.trades)
    s2q = _stats(bps_2q, bt_2q.trades)
    print(f"{'gate':<22} {'bps_n':>6} {'WR%':>6} {'total':>11} {'avg':>9} {'worst':>11} {'all_ann':>11}")
    print(f"{'baseline (IVR>55)':<22} {sbl['bps_n']:>6} {sbl['wr']:>5.1f}% "
          f"${sbl['total']:>+9,.0f} ${sbl['avg']:>+7,.0f} ${sbl['worst']:>+9,.0f} ${sbl['all_ann']:>+9,.0f}")
    print(f"{'2nd Quant (3-factor)':<22} {s2q['bps_n']:>6} {s2q['wr']:>5.1f}% "
          f"${s2q['total']:>+9,.0f} ${s2q['avg']:>+7,.0f} ${s2q['worst']:>+9,.0f} ${s2q['all_ann']:>+9,.0f}")
    print(f"Δ 2Q - BL:           "
          f"{s2q['bps_n']-sbl['bps_n']:>+6d} "
          f"{s2q['wr']-sbl['wr']:>+5.1f}pp "
          f"${s2q['total']-sbl['total']:>+9,.0f} "
          f"${s2q['avg']-sbl['avg']:>+7,.0f} "
          f"${s2q['worst']-sbl['worst']:>+9,.0f} "
          f"${s2q['all_ann']-sbl['all_ann']:>+9,.0f}")

    # OOS
    print(f"\n{'='*100}")
    print(f"Test 2 — OOS split")
    print(f"{'='*100}")
    def _filter(trades, s, e):
        return [t for t in trades if s <= t.entry_date <= e]
    for label, s, e, yrs in [("Train (07-17)", "2007-01-01", "2017-12-31", 11.0),
                             ("Test (18-26)", "2018-01-01", "2026-05-10", 8.4)]:
        bbl = _filter(bps_bl, s, e)
        b2q = _filter(bps_2q, s, e)
        all_b = _filter(bt_bl.trades, s, e)
        all_q = _filter(bt_2q.trades, s, e)
        print(f"{label}:")
        print(f"  BL: bps_n={len(bbl)}, ann={sum(t.exit_pnl for t in all_b)/yrs:>+9,.0f}, bps_avg=${sum(t.exit_pnl for t in bbl)/len(bbl) if bbl else 0:>+7,.0f}")
        print(f"  2Q: bps_n={len(b2q)}, ann={sum(t.exit_pnl for t in all_q)/yrs:>+9,.0f}, bps_avg=${sum(t.exit_pnl for t in b2q)/len(b2q) if b2q else 0:>+7,.0f}")
        diff = sum(t.exit_pnl for t in all_q)/yrs - sum(t.exit_pnl for t in all_b)/yrs
        print(f"  Δ (2Q-BL) ann: ${diff:>+9,.0f}/yr {'PASS' if diff > 0 else 'FAIL'}")

    # Recent
    print(f"\n{'='*100}")
    print(f"Test 3 — Recent windows (BPS only)")
    print(f"{'='*100}")
    print(f"{'window':<18} | {'BL n':>4} {'BL sum':>10} | {'2Q n':>4} {'2Q sum':>10} | Δ")
    for wn, ws in [("last 5y", "2021-01-01"),
                   ("last 3y", "2023-01-01"),
                   ("last 2y", "2024-01-01"),
                   ("last 1y", "2025-05-11")]:
        bbl = _filter(bps_bl, ws, END)
        b2q = _filter(bps_2q, ws, END)
        bpl = sum(t.exit_pnl for t in bbl)
        qpl = sum(t.exit_pnl for t in b2q)
        diff = qpl - bpl
        print(f"{wn:<18} | {len(bbl):>4} ${bpl:>+8,.0f} | {len(b2q):>4} ${qpl:>+8,.0f} | "
              f"${diff:>+8,.0f} {'PASS' if diff > 0 else 'FAIL'}")

    # Per-year
    print(f"\n{'='*100}")
    print(f"Test 4 — Per-year P&L comparison (years 2018+)")
    print(f"{'='*100}")
    by_year_bl = defaultdict(lambda: [0, 0.0])
    by_year_2q = defaultdict(lambda: [0, 0.0])
    for t in bps_bl:
        y = t.entry_date[:4]
        by_year_bl[y][0] += 1
        by_year_bl[y][1] += t.exit_pnl
    for t in bps_2q:
        y = t.entry_date[:4]
        by_year_2q[y][0] += 1
        by_year_2q[y][1] += t.exit_pnl
    print(f"{'year':<6} | {'BL n':>4} {'BL pnl':>10} | {'2Q n':>4} {'2Q pnl':>10} | Δ_n  Δ_pnl")
    for y in sorted(set(list(by_year_bl.keys()) + list(by_year_2q.keys()))):
        if int(y) < 2018: continue
        bn, bp = by_year_bl[y]
        an, ap = by_year_2q[y]
        marker = "  ✓" if ap-bp > 0 else "  ✗" if ap-bp < 0 else ""
        print(f"{y:<6} | {bn:>4d} ${bp:>+8,.0f} | {an:>4d} ${ap:>+8,.0f} | "
              f"{an-bn:>+3d}  ${ap-bp:>+8,.0f}{marker}")

    # Specifically check 2026-02-25
    print(f"\n{'='*100}")
    print(f"Test 5 — Did 2nd Quant gate block the 2026-02-25 trade?")
    print(f"{'='*100}")
    has_0225 = any(t.entry_date == "2026-02-25" for t in bps_2q)
    print(f"  2nd Quant gate {'ALLOWED' if has_0225 else 'BLOCKED'} the 2026-02-25 entry")
    if has_0225:
        t = next(t for t in bps_2q if t.entry_date == "2026-02-25")
        print(f"  → trade pnl: ${t.exit_pnl:+,.0f}")

    sel.BPS_NNB_IVP_UPPER = orig_upper


if __name__ == "__main__":
    main()
