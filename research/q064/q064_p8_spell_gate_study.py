"""Q064 P8 — Spell gate sensitivity: is max_trades_per_spell=2 over-gating?

Tests max_trades_per_spell ∈ {2 (baseline), 3, 4, unlimited} on the full
2009-01-01 → 2025-06-30 backtest. For each configuration:
  - Reports IC_HV (V3-A path) trade count, win rate, avg P&L, $/BP-day
  - Shows incremental trades added vs baseline and their standalone metrics
  - Checks for degradation: do later-spell trades underperform early-spell trades?

Output:
  q064_p8_summary.csv    — per-config aggregate metrics
  q064_p8_incremental.csv — incremental trades (not in baseline) per config
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import strategy.selector as sel
from backtest import engine as engine_mod
from backtest.engine import run_backtest, StrategyParams, DEFAULT_PARAMS
from signals.vix_regime import Regime
from signals.iv_rank import IVSignal
from signals.trend import TrendSignal

OUT_SUMMARY     = REPO / "research" / "q064" / "q064_p8_summary.csv"
OUT_INCREMENTAL = REPO / "research" / "q064" / "q064_p8_incremental.csv"

START = "2009-01-01"
END   = "2025-06-30"
ACCT  = 150_000.0

SPELL_CONFIGS = [2, 3, 4, 999]   # 999 = unlimited


def _is_v3a(vix_snap, iv, trend) -> bool:
    return (
        vix_snap.regime == Regime.HIGH_VOL
        and iv.iv_signal == IVSignal.HIGH
        and trend.signal in (TrendSignal.BEARISH, TrendSignal.NEUTRAL)
        and sel.is_aftermath(vix_snap)
    )


def run_config(spell_max: int) -> list[dict]:
    """Run backtest with given max_trades_per_spell; return V3-A IC_HV trades."""
    v3a_dates: set = set()

    orig = sel.select_strategy

    def wrapped(vix_snap, iv, trend, params=sel.DEFAULT_PARAMS):
        rec = orig(vix_snap, iv, trend, params)
        if _is_v3a(vix_snap, iv, trend) and "Iron Condor" in rec.strategy.value:
            v3a_dates.add(vix_snap.date)
        return rec

    sel.select_strategy        = wrapped
    engine_mod.select_strategy = wrapped

    params = copy.copy(DEFAULT_PARAMS)
    params.max_trades_per_spell = spell_max

    try:
        bt = run_backtest(start_date=START, end_date=END,
                          account_size=ACCT, params=params, verbose=False)
    finally:
        sel.select_strategy        = orig
        engine_mod.select_strategy = orig

    trades = []
    for t in bt.trades:
        if t.entry_date in v3a_dates and "Iron Condor" in t.strategy.value:
            hold = (pd.Timestamp(t.exit_date) - pd.Timestamp(t.entry_date)).days
            trades.append({
                "entry_date":  t.entry_date,
                "exit_date":   t.exit_date,
                "exit_reason": t.exit_reason,
                "hold_days":   hold,
                "pnl":         round(t.exit_pnl, 2),
                "bp":          round(t.total_bp, 2),
                "bp_day":      round((t.exit_pnl / t.total_bp) * (365 / max(hold, 1)), 4)
                               if t.total_bp > 0 else 0.0,
                "spell_max":   spell_max,
            })
    return trades


def agg_metrics(trades: list[dict], label: str) -> dict:
    if not trades:
        return {"config": label, "n": 0}
    pnls = [t["pnl"]    for t in trades]
    bps  = [t["bp"]     for t in trades]
    hds  = [t["hold_days"] for t in trades]
    bp_days = sum(b * h for b, h in zip(bps, hds))
    wins = sum(1 for p in pnls if p > 0)
    return {
        "config":          label,
        "n_trades":        len(trades),
        "win_rate_pct":    round(wins / len(trades) * 100, 1),
        "avg_pnl":         round(sum(pnls) / len(pnls), 2),
        "median_pnl":      round(sorted(pnls)[len(pnls) // 2], 2),
        "total_pnl":       round(sum(pnls), 2),
        "worst_trade":     round(min(pnls), 2),
        "best_trade":      round(max(pnls), 2),
        "avg_bp":          round(sum(bps) / len(bps), 2),
        "dollar_per_bp_day": round(sum(pnls) / bp_days * 1e6, 2) if bp_days > 0 else 0.0,
        "avg_hold_days":   round(sum(hds) / len(hds), 1),
    }


def main() -> None:
    print("=" * 90)
    print("Q064 P8 — Spell gate sensitivity: max_trades_per_spell ∈ {2, 3, 4, ∞}")
    print("=" * 90)

    all_trades: dict[int, list[dict]] = {}
    for sp in SPELL_CONFIGS:
        label = str(sp) if sp < 999 else "∞"
        print(f"\nRunning spell_max={label} …", end=" ", flush=True)
        trades = run_config(sp)
        all_trades[sp] = trades
        print(f"{len(trades)} V3-A trades")

    # ── Summary table ──────────────────────────────────────────────────────────
    baseline_dates = {t["entry_date"] for t in all_trades[2]}

    summary_rows = []
    for sp in SPELL_CONFIGS:
        label = str(sp) if sp < 999 else "∞"
        summary_rows.append(agg_metrics(all_trades[sp], f"spell_max={label}"))

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(OUT_SUMMARY, index=False)

    print("\n\n" + "=" * 90)
    print("AGGREGATE METRICS")
    print("=" * 90)
    print(summary_df.to_string(index=False))

    # ── Incremental trades (not in baseline) ──────────────────────────────────
    incr_rows = []
    for sp in SPELL_CONFIGS[1:]:   # skip baseline (sp=2)
        label = str(sp) if sp < 999 else "∞"
        new_trades = [t for t in all_trades[sp] if t["entry_date"] not in baseline_dates]
        for t in new_trades:
            row = dict(t)
            row["config"] = f"spell_max={label}"
            incr_rows.append(row)

    incr_df = pd.DataFrame(incr_rows)
    incr_df.to_csv(OUT_INCREMENTAL, index=False)

    print("\n\n" + "=" * 90)
    print("INCREMENTAL TRADES vs BASELINE (spell_max=2)")
    print("=" * 90)
    for sp in SPELL_CONFIGS[1:]:
        label = str(sp) if sp < 999 else "∞"
        new_trades = [t for t in all_trades[sp] if t["entry_date"] not in baseline_dates]
        if not new_trades:
            print(f"\nspell_max={label}: no incremental trades")
            continue
        m = agg_metrics(new_trades, f"incremental (spell_max={label})")
        print(f"\nspell_max={label}  →  +{m['n_trades']} incremental trades")
        print(f"  Win rate:        {m['win_rate_pct']}%")
        print(f"  Avg P&L:         ${m['avg_pnl']:,.2f}")
        print(f"  Worst trade:     ${m['worst_trade']:,.2f}")
        print(f"  $/BP-day (×1M):  {m['dollar_per_bp_day']:.2f}")
        for t in sorted(new_trades, key=lambda x: x["entry_date"]):
            pnl_sign = "+" if t["pnl"] >= 0 else ""
            print(f"    {t['entry_date']} → {t['exit_date']}  "
                  f"hold={t['hold_days']:2d}d  "
                  f"P&L={pnl_sign}${t['pnl']:,.0f}  "
                  f"exit={t['exit_reason']}")

    # ── Spell-position analysis: early vs late spell trades ────────────────────
    print("\n\n" + "=" * 90)
    print("SPELL-POSITION ANALYSIS: does trade quality degrade within a spell?")
    print("(baseline spell_max=2, trades ranked by position within their spell)")
    print("=" * 90)

    # For baseline trades, determine their position within the spell
    # We use the actual engine spell tracking indirectly: sort trades by date,
    # then find consecutive clusters (same HV regime episode) using 90d gap heuristic
    baseline = sorted(all_trades[2], key=lambda t: t["entry_date"])
    spell_groups: list[list[dict]] = []
    for t in baseline:
        placed = False
        for g in spell_groups:
            last = g[-1]
            if (pd.Timestamp(t["entry_date"]) - pd.Timestamp(last["exit_date"])).days <= 90:
                g.append(t)
                placed = True
                break
        if not placed:
            spell_groups.append([t])

    for pos in [1, 2]:
        pos_trades = [g[pos - 1] for g in spell_groups if len(g) >= pos]
        if not pos_trades:
            continue
        m = agg_metrics(pos_trades, f"spell position #{pos}")
        print(f"\nSpell trade #{pos}  (n={m['n_trades']})")
        print(f"  Win rate:    {m['win_rate_pct']}%   Avg P&L: ${m['avg_pnl']:,.2f}   "
              f"$/BP-day: {m['dollar_per_bp_day']:.2f}")

    print(f"\nWrote {OUT_SUMMARY}")
    print(f"Wrote {OUT_INCREMENTAL}")


if __name__ == "__main__":
    main()
