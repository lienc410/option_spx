"""Q064 P6 (revised β) — V3-A vs IC_HV normal counterfactual on 33 ACTUAL V3-A trades.

Context: 2nd Quant APPROVED β; mechanical verification revealed Q064 P1-P5 used the
wrong trade set (15 BPS_HV trades flagged by VIX condition only). The TRUE V3-A
fires happen on BEARISH/NEUTRAL+IV_HIGH+aftermath cells — 33 IC_HV trades.

This script:
  1. Re-runs engine with SPEC-064 V3-A path active (production behavior)
  2. Identifies 33 trades where V3-A actually fired
  3. For each, captures actual V3-A IC_HV broken-wing P&L (from engine output)
  4. Computes IC_HV normal counterfactual (SPEC-060 fallback: symmetric δ0.16/0.08)
     using same BS pricing framework as P3
  5. Equal-BP normalization (P4 style): scale IC_HV normal contracts so BP matches V3-A
  6. Compare metrics

IC_HV normal structure (from selector.py:687-719, SPEC-060):
  SELL CALL δ0.16, BUY CALL δ0.08  (DTE=45)
  SELL PUT  δ0.16, BUY PUT  δ0.08  (DTE=45)
  Symmetric wings (not broken)

V3-A broken-wing (from selector.py:642-668, SPEC-064 aftermath):
  SELL CALL δ0.12, BUY CALL δ0.04  (call wing wider)
  SELL PUT  δ0.12, BUY PUT  δ0.08  (put wing tighter)
  Asymmetric / broken-wing
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import strategy.selector as sel
from backtest import engine as engine_mod
from backtest.engine import run_backtest
from signals.iv_rank import IVSignal
from signals.trend import TrendSignal
from signals.vix_regime import Regime

# Reuse P3 helpers
from research.q064.q064_p3_structure_counterfactual import (
    term_multiplier, bs_put, bs_call, delta_to_strike_put, delta_to_strike_call,
    V3A_PUT_SHORT_DELTA, V3A_PUT_LONG_DELTA,
    V3A_CALL_SHORT_DELTA, V3A_CALL_LONG_DELTA,
    V3A_DTE, R,
)

# IC_HV normal symmetric (SPEC-060)
IC_PUT_SHORT_DELTA  = 0.16
IC_PUT_LONG_DELTA   = 0.08
IC_CALL_SHORT_DELTA = 0.16
IC_CALL_LONG_DELTA  = 0.08
IC_DTE = 45

OUT_DETAIL  = REPO / "research" / "q064" / "q064_p6_results.csv"
OUT_SUMMARY = REPO / "research" / "q064" / "q064_p6_summary.csv"


# ── Identify V3-A actual trade dates via wrapper ──────────────────────────────

def identify_v3a_fires():
    """Run engine and capture the (date, vix, S, contracts, bp, pnl) of trades that
    actually fired V3-A (BEARISH/NEUTRAL+IV_HIGH+aftermath path)."""
    v3a_dates = set()

    orig = sel.select_strategy
    def wrapped(vix, iv, trend, params=sel.DEFAULT_PARAMS):
        rec = orig(vix, iv, trend, params)
        if (vix.regime == Regime.HIGH_VOL
            and iv.iv_signal == IVSignal.HIGH
            and trend.signal in (TrendSignal.BEARISH, TrendSignal.NEUTRAL)
            and sel.is_aftermath(vix)
            and 'Iron Condor' in rec.strategy.value):
            v3a_dates.add(vix.date)
        return rec

    sel.select_strategy = wrapped
    engine_mod.select_strategy = wrapped
    try:
        bt = run_backtest(start_date="2009-01-01", end_date="2026-05-13",
                          account_size=150_000.0, verbose=False)
    finally:
        sel.select_strategy = orig
        engine_mod.select_strategy = orig

    v3a_trades = [t for t in bt.trades
                  if t.entry_date in v3a_dates and 'Iron Condor' in t.strategy.value]
    return bt, v3a_trades


# ── IC_HV normal pricing helpers ──────────────────────────────────────────────

def price_ic_normal_entry(S: float, vix: float, dte: int = IC_DTE) -> dict:
    """IC_HV normal entry: symmetric δ0.16/0.08."""
    T = dte / 365.0
    sigma = max(vix / 100.0, 0.10) * term_multiplier(dte)
    K_ps = delta_to_strike_put( S, IC_PUT_SHORT_DELTA,  T, sigma)
    K_pl = delta_to_strike_put( S, IC_PUT_LONG_DELTA,   T, sigma)
    K_cs = delta_to_strike_call(S, IC_CALL_SHORT_DELTA, T, sigma)
    K_cl = delta_to_strike_call(S, IC_CALL_LONG_DELTA,  T, sigma)
    put_c  = bs_put(S, K_ps, T, sigma) - bs_put(S, K_pl, T, sigma)
    call_c = bs_call(S, K_cs, T, sigma) - bs_call(S, K_cl, T, sigma)
    return {
        "put_short_K":  K_ps,
        "put_long_K":   K_pl,
        "put_width":    K_ps - K_pl,
        "put_credit":   put_c,
        "call_short_K": K_cs,
        "call_long_K":  K_cl,
        "call_width":   K_cl - K_cs,
        "call_credit":  call_c,
        "entry_credit_per_share": put_c + call_c,
        "sigma": sigma,
        "dte": dte,
    }


def exit_value_ic(S_exit: float, vix_exit: float, entry: dict, dte_at_exit: int) -> float:
    """Exit cost per share for IC (both v3a & normal symmetric)."""
    K_ps = entry["put_short_K"]
    K_pl = entry["put_long_K"]
    K_cs = entry["call_short_K"]
    K_cl = entry["call_long_K"]
    T = max(dte_at_exit / 365.0, 0.0)
    sigma = max(vix_exit / 100.0, 0.10) * term_multiplier(max(dte_at_exit, 1))
    if T <= 0:
        put_cost = max(0.0, K_ps - S_exit) - max(0.0, K_pl - S_exit)
        call_cost = max(0.0, S_exit - K_cs) - max(0.0, S_exit - K_cl)
    else:
        put_cost  = bs_put( S_exit, K_ps, T, sigma) - bs_put( S_exit, K_pl, T, sigma)
        call_cost = bs_call(S_exit, K_cs, T, sigma) - bs_call(S_exit, K_cl, T, sigma)
    return max(0.0, put_cost) + max(0.0, call_cost)


def bp_ic(entry: dict, contracts: float) -> float:
    """IC PM BP = max(put_width, call_width) × 100 × contracts."""
    return max(entry["put_width"], entry["call_width"]) * 100.0 * contracts


# ── Market data ───────────────────────────────────────────────────────────────

def load_series(ticker: str, start: str = "2009-01-01") -> pd.Series:
    raw = yf.download(ticker, start=start, end="2026-05-14", progress=False, auto_adjust=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    s = raw["Close"].squeeze()
    s.index = pd.to_datetime(s.index).normalize()
    return s


def get_on(prices: pd.Series, date) -> float:
    d = pd.Timestamp(date).normalize()
    if d in prices.index:
        return float(prices.loc[d])
    for delta in range(1, 6):
        for sign in [1, -1]:
            dd = d + pd.Timedelta(days=sign * delta)
            if dd in prices.index:
                return float(prices.loc[dd])
    raise ValueError(f"No data near {date}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 100)
    print("Q064 P6 (revised β) — V3-A vs IC_HV normal on 33 actual V3-A trades")
    print("=" * 100)

    print("\nIdentifying V3-A fires from production backtest...")
    bt, v3a_trades = identify_v3a_fires()
    print(f"  V3-A IC_HV trades found: {len(v3a_trades)}")

    print("\nLoading SPX + VIX series via yfinance...")
    spx = load_series("^GSPC")
    vix = load_series("^VIX")
    print(f"  SPX: {len(spx)} bars; VIX: {len(vix)} bars")

    rows = []
    for t in v3a_trades:
        entry_date = pd.Timestamp(t.entry_date)
        exit_date  = pd.Timestamp(t.exit_date)
        hold_days  = (exit_date - entry_date).days

        try:
            S_entry = get_on(spx, entry_date)
            vix_entry = get_on(vix, entry_date)
            S_exit  = get_on(spx, exit_date)
            vix_exit = get_on(vix, exit_date)
        except ValueError as e:
            print(f"  skip {t.entry_date}: {e}")
            continue

        # IC normal counterfactual
        ic_entry = price_ic_normal_entry(S_entry, vix_entry, dte=IC_DTE)
        dte_at_exit = max(IC_DTE - hold_days, 0)
        ic_close_cost = exit_value_ic(S_exit, vix_exit, ic_entry, dte_at_exit)
        ic_pnl_ps = ic_entry["entry_credit_per_share"] - ic_close_cost
        ic_contracts_raw = t.contracts  # raw 1:1 match to V3-A contracts
        ic_pnl_raw = ic_pnl_ps * 100.0 * ic_contracts_raw
        ic_bp_raw = bp_ic(ic_entry, ic_contracts_raw)
        ic_bp_day_raw = (ic_pnl_raw / ic_bp_raw) * (365.0 / max(hold_days, 1)) if ic_bp_raw > 0 else 0.0

        # V3-A actual (from production backtest)
        v3a_pnl_actual = t.exit_pnl
        v3a_bp_actual = t.total_bp
        v3a_bp_day = (v3a_pnl_actual / v3a_bp_actual) * (365.0 / max(hold_days, 1)) if v3a_bp_actual > 0 else 0.0

        # Equal-BP normalization: scale IC normal so its BP matches V3-A's
        if ic_bp_raw > 0:
            scale_eqbp = v3a_bp_actual / ic_bp_raw
            ic_pnl_eqbp = ic_pnl_raw * scale_eqbp
            ic_bp_eqbp = v3a_bp_actual
        else:
            scale_eqbp = 0.0
            ic_pnl_eqbp = 0.0
            ic_bp_eqbp = 0.0
        ic_bp_day_eqbp = (ic_pnl_eqbp / ic_bp_eqbp) * (365.0 / max(hold_days, 1)) if ic_bp_eqbp > 0 else 0.0

        rows.append({
            "entry_date": t.entry_date,
            "exit_date":  t.exit_date,
            "exit_reason": t.exit_reason,
            "hold_days":  hold_days,
            "vix_at_entry": round(vix_entry, 2),
            "vix_at_exit":  round(vix_exit, 2),
            "S_entry": round(S_entry, 2),
            "S_exit":  round(S_exit, 2),

            "v3a_contracts": round(t.contracts, 4),
            "v3a_pnl_actual": round(v3a_pnl_actual, 2),
            "v3a_bp_actual":  round(v3a_bp_actual, 2),
            "v3a_bp_day": round(v3a_bp_day, 4),

            "ic_put_short_K": round(ic_entry["put_short_K"], 1),
            "ic_put_long_K": round(ic_entry["put_long_K"], 1),
            "ic_call_short_K": round(ic_entry["call_short_K"], 1),
            "ic_call_long_K": round(ic_entry["call_long_K"], 1),
            "ic_entry_credit": round(ic_entry["entry_credit_per_share"] * 100.0 * ic_contracts_raw, 2),

            # Raw (1:1 contracts)
            "ic_pnl_raw": round(ic_pnl_raw, 2),
            "ic_bp_raw":  round(ic_bp_raw, 2),
            "ic_bp_day_raw": round(ic_bp_day_raw, 4),

            # Equal-BP normalized
            "ic_scale_eqbp": round(scale_eqbp, 4),
            "ic_pnl_eqbp": round(ic_pnl_eqbp, 2),
            "ic_bp_day_eqbp": round(ic_bp_day_eqbp, 4),

            # Diffs
            "pnl_diff_raw":  round(v3a_pnl_actual - ic_pnl_raw, 2),
            "pnl_diff_eqbp": round(v3a_pnl_actual - ic_pnl_eqbp, 2),
            "v3a_wins_raw":  v3a_pnl_actual > ic_pnl_raw,
            "v3a_wins_eqbp": v3a_pnl_actual > ic_pnl_eqbp,
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DETAIL, index=False)
    print(f"\nWrote {OUT_DETAIL}  ({len(df)} rows)")

    # ── Aggregate metrics ──
    def agg(label: str, pnls: pd.Series, bps: pd.Series, hold_days_arr: pd.Series) -> dict:
        wins = pnls > 0
        bp_days = (bps * hold_days_arr).sum()
        return {
            "version": label,
            "n_trades": len(pnls),
            "win_rate_pct": round(float(wins.mean() * 100), 1),
            "avg_pnl": round(float(pnls.mean()), 2),
            "median_pnl": round(float(pnls.median()), 2),
            "total_pnl": round(float(pnls.sum()), 2),
            "worst_trade": round(float(pnls.min()), 2),
            "best_trade":  round(float(pnls.max()), 2),
            "avg_bp": round(float(bps.mean()), 2),
            "dollar_per_bp_day": round(float(pnls.sum()) / bp_days * 1e6, 2) if bp_days > 0 else 0.0,
        }

    summaries = [
        agg("V3-A actual (production)",  df["v3a_pnl_actual"], df["v3a_bp_actual"],  df["hold_days"]),
        agg("IC_HV normal (raw 1:1)",    df["ic_pnl_raw"],     df["ic_bp_raw"],      df["hold_days"]),
        agg("IC_HV normal (equal-BP)",   df["ic_pnl_eqbp"],    pd.Series([df["v3a_bp_actual"].iloc[i] for i in range(len(df))]), df["hold_days"]),
    ]
    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUT_SUMMARY, index=False)
    print(f"Wrote {OUT_SUMMARY}")

    print("\n" + "=" * 100)
    print("Summary — 3 versions on 33 actual V3-A trades")
    print("=" * 100)
    print(summary_df.to_string(index=False))

    # Quick win counts
    print(f"\nWin counts:")
    print(f"  V3-A > IC_normal (raw):     {int(df['v3a_wins_raw'].sum())} / {len(df)}")
    print(f"  V3-A > IC_normal (eqBP):    {int(df['v3a_wins_eqbp'].sum())} / {len(df)}")
    print(f"  V3-A < IC_normal (raw):     {int((~df['v3a_wins_raw']).sum())} / {len(df)}")
    print(f"  V3-A < IC_normal (eqBP):    {int((~df['v3a_wins_eqbp'].sum()))} / {len(df)}")

    # Sample first 10 rows
    print(f"\nFirst 10 trade-by-trade detail (eqBP normalization):")
    cols = ['entry_date', 'hold_days', 'vix_at_entry', 'v3a_pnl_actual',
            'ic_pnl_eqbp', 'pnl_diff_eqbp', 'v3a_wins_eqbp']
    print(df[cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
