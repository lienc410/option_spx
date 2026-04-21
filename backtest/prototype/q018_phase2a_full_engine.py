"""
Q018 Phase 2-A — Full-engine multi-slot IC_HV aftermath (BP + shock + overlay).

Phase 1b's +$47,735 was computed with three gaps:
  - No BP ceiling check
  - No shock engine interaction
  - No overlay (block_new_entries / force_trim)

This prototype closes all three by runtime-patching engine.run_backtest to
allow up to 2 concurrent IC_HV positions (only IC_HV — everything else
keeps the existing single-slot rule). All other engine logic is preserved.

Method:
  1. inspect.getsource on engine.run_backtest
  2. Replace the single `_already_open` line with a conditional that
     allows IC_HV up to 2 concurrent:
       if IC_HV: _already_open = (count_IC_HV >= 2)
       else:     _already_open = any(p.strategy == rec.strategy)
  3. exec the modified source in engine module namespace → patched function
  4. Run baseline + patched end-to-end, diff

What this captures that Phase 1b missed:
  - BP ceiling rejections (second IC_HV blocked when bp_used + bp_target > 50%)
  - Shock engine rejections (candidate would breach book_core_shock limit)
  - Overlay block_new_entries / force_trim scenarios
  - Regime shifts during 2nd position hold → engine re-prices / exits correctly
  - Downstream effects: the 2nd position's BP may prevent a LATER trade

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.q018_phase2a_full_engine
"""

from __future__ import annotations

import inspect

import numpy as np

import backtest.engine as engine_mod
from backtest.engine import run_backtest, Trade
from strategy.selector import StrategyName

START = "2000-01-01"


# ──────────────────────────────────────────────────────────────────
# Runtime-patched run_backtest
# ──────────────────────────────────────────────────────────────────

_ORIG_LINE = "_already_open = any(p.strategy == rec.strategy for p in positions)"
_PATCHED_LINE = (
    "_already_open = ("
    "(sum(1 for p in positions if p.strategy == rec.strategy) >= 2) "
    "if rec.strategy == StrategyName.IRON_CONDOR_HV "
    "else any(p.strategy == rec.strategy for p in positions)"
    ")"
)


def _build_patched_run_backtest():
    src = inspect.getsource(engine_mod.run_backtest)
    if _ORIG_LINE not in src:
        raise RuntimeError(f"Expected line not found in run_backtest source:\n  {_ORIG_LINE}")
    patched_src = src.replace(_ORIG_LINE, _PATCHED_LINE)
    if patched_src == src:
        raise RuntimeError("String replacement produced no change")
    # Exec in a copy of engine module's namespace so default param bindings resolve.
    ns = dict(engine_mod.__dict__)
    exec(patched_src, ns)
    return ns["run_backtest"]


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _closed(trades: list[Trade]) -> list[Trade]:
    return [t for t in trades if t.exit_reason != "end_of_backtest"]


def _stats(trades: list[Trade]) -> dict:
    if not trades:
        return {"n": 0, "mean": 0, "total": 0, "win%": 0.0, "sharpe": 0.0}
    p = np.array([t.exit_pnl for t in trades])
    n = len(p)
    mu = float(p.mean())
    sd = float(p.std(ddof=1)) if n > 1 else 0.0
    return {
        "n": n,
        "mean": round(mu),
        "total": int(p.sum()),
        "win%": round((p > 0).mean() * 100, 1),
        "sharpe": round(mu / sd, 2) if sd > 0 else 0.0,
    }


def _fmt(tag: str, s: dict) -> str:
    return (f"    {tag:<22} n={s['n']:>4}  total=${s['total']:>+10,}  "
            f"avg=${s['mean']:>+6,}  win={s['win%']:>5.1f}%  sharpe={s['sharpe']:>+5.2f}")


def _max_dd(trades: list[Trade]) -> float:
    if not trades:
        return 0.0
    ts = sorted(trades, key=lambda t: t.exit_date)
    cum = np.cumsum([t.exit_pnl for t in ts])
    peak = np.maximum.accumulate(cum)
    return float((cum - peak).min())


def _trade_id(t: Trade) -> tuple:
    return (t.entry_date, t.strategy.value, round(t.entry_spx, 2), round(t.entry_vix, 2), t.exit_date)


def _is_ic_hv(t: Trade) -> bool:
    return t.strategy.value == StrategyName.IRON_CONDOR_HV.value


# Clusters of interest from Phase 1 (for traceability)
PHASE1_CLUSTER_STARTS = {
    "2008-09-19": "2008 GFC",
    "2020-03-03": "2020 COVID",
    "2025-04-11": "2025 Tariff #1",
    "2025-04-25": "2025 Tariff #2",
    "2026-03-10": "2026-03 double-spike (trigger case)",
}


def run_study() -> None:
    print("Q018 Phase 2-A — Full-engine multi-slot IC_HV aftermath")
    print()
    print("  Building patched run_backtest (allows IC_HV up to 2 concurrent) ...")
    patched_run_backtest = _build_patched_run_backtest()

    print("  Running baseline ...")
    bt_base = run_backtest(start_date=START, verbose=False)
    base_closed = _closed(bt_base.trades)
    print("  Running patched (multi-slot IC_HV) ...")
    bt_patched = patched_run_backtest(start_date=START, verbose=False)
    patched_closed = _closed(bt_patched.trades)

    # ── System-level delta ─────────────────────────────────────────
    print()
    print("=" * 100)
    print("  SYSTEM-LEVEL")
    print("=" * 100)
    s_base = _stats(base_closed)
    s_p = _stats(patched_closed)
    print(_fmt("baseline", s_base))
    print(_fmt("patched (multi-slot)", s_p))
    print(f"\n  Delta: n {s_p['n'] - s_base['n']:+d}, "
          f"total ${s_p['total'] - s_base['total']:+,}, "
          f"avg ${s_p['mean'] - s_base['mean']:+,}, "
          f"sharpe {s_p['sharpe'] - s_base['sharpe']:+.2f}")
    print(f"  MaxDD: baseline ${_max_dd(base_closed):+,.0f}  "
          f"patched ${_max_dd(patched_closed):+,.0f}  "
          f"delta ${_max_dd(patched_closed) - _max_dd(base_closed):+,.0f}")

    # ── IC_HV subset ───────────────────────────────────────────────
    print()
    print("=" * 100)
    print("  IC_HV SUBSET")
    print("=" * 100)
    ic_base = [t for t in base_closed if _is_ic_hv(t)]
    ic_p = [t for t in patched_closed if _is_ic_hv(t)]
    print(_fmt("baseline IC_HV", _stats(ic_base)))
    print(_fmt("patched IC_HV", _stats(ic_p)))
    print(f"\n  IC_HV delta: n {len(ic_p) - len(ic_base):+d}")

    # ── Identify "extra" trades (entry_date not in baseline IC_HV) ────
    base_ic_ids = {_trade_id(t) for t in ic_base}
    extra_trades = [t for t in ic_p if _trade_id(t) not in base_ic_ids]
    # Also find baseline IC_HV that disappeared (should be 0 — we only added permission, never removed)
    missing_trades = [t for t in ic_base if _trade_id(t) not in {_trade_id(x) for x in ic_p}]

    print()
    print(f"  Extra IC_HV (not in baseline): {len(extra_trades)}")
    print(f"  Missing IC_HV (in baseline but not patched): {len(missing_trades)}")
    if missing_trades:
        print("  (unexpected — investigating):")
        for t in missing_trades[:10]:
            print(f"    {t.entry_date} → {t.exit_date}  pnl=${t.exit_pnl:+,.0f}")

    # ── Extra trade detail ─────────────────────────────────────────
    print()
    print("=" * 100)
    print("  EXTRA IC_HV TRADES (the multi-slot second-slot entries the engine allowed)")
    print("=" * 100)
    if not extra_trades:
        print("  (none — BP/shock/overlay blocked every candidate)")
    else:
        for t in sorted(extra_trades, key=lambda x: x.entry_date):
            yr = t.entry_date[:4]
            phase1_tag = PHASE1_CLUSTER_STARTS.get(t.entry_date, "")
            tag = f"  [{phase1_tag}]" if phase1_tag else ""
            print(f"  {t.entry_date} → {t.exit_date}  "
                  f"SPX {t.entry_spx:>7.1f}→{t.exit_spx:>7.1f}  "
                  f"VIX {t.entry_vix:>5.1f}  "
                  f"days={t.dte_at_entry - t.dte_at_exit:>3}  "
                  f"pnl=${t.exit_pnl:>+9,.0f}  ({t.exit_reason}){tag}")

        extra_total = sum(t.exit_pnl for t in extra_trades)
        extra_wins = sum(1 for t in extra_trades if t.exit_pnl > 0)
        extra_losses = sum(t.exit_pnl for t in extra_trades if t.exit_pnl < 0)
        extra_profits = sum(t.exit_pnl for t in extra_trades if t.exit_pnl > 0)
        print()
        print(f"  Extra trades summary:")
        print(f"    count:        {len(extra_trades)}")
        print(f"    win rate:     {extra_wins}/{len(extra_trades)} = "
              f"{extra_wins/len(extra_trades)*100:.1f}%")
        print(f"    profits sum:  ${extra_profits:+,.0f}")
        print(f"    losses sum:   ${extra_losses:+,.0f}")
        print(f"    NET:          ${extra_total:+,.0f}")

    # ── Phase 1 cluster traceability ───────────────────────────────
    print()
    print("=" * 100)
    print("  PHASE 1 CLUSTER TRACEABILITY (36 clusters → how many actually opened?)")
    print("=" * 100)
    extra_entry_dates = {t.entry_date for t in extra_trades}

    from backtest.prototype.q018_phase1_multi_slot import _find_blocked_clusters
    clusters, _ = _find_blocked_clusters(bt_base.signals, ic_base)
    opened_count = 0
    disaster_opened_count = 0
    print(f"  {'Cluster start':<14} {'Opened?':<8}  Disaster")
    for c in clusters:
        # Engine may open on first day of cluster OR a later day within the window.
        # Check if any extra trade's entry_date falls inside cluster window [first_day, last_day].
        opened_dates = [d for d in extra_entry_dates
                        if c.first_day <= d <= c.last_day]
        status = f"YES ({opened_dates[0]})" if opened_dates else "no"
        if opened_dates:
            opened_count += 1
            if c.disaster:
                disaster_opened_count += 1
        disaster = c.disaster or ""
        flag = "  [traced]" if c.first_day in PHASE1_CLUSTER_STARTS else ""
        print(f"  {c.first_day:<14} {status:<16}  {disaster}{flag}")

    print()
    print(f"  Summary: {opened_count}/{len(clusters)} Phase 1 clusters actually opened in full engine")
    print(f"  Disaster clusters opened: {disaster_opened_count}/"
          f"{sum(1 for c in clusters if c.disaster)}")

    # ── Comparison vs Phase 1b approximation ───────────────────────
    print()
    print("=" * 100)
    print("  PHASE 1b vs PHASE 2-A RECONCILIATION")
    print("=" * 100)
    print(f"  Phase 1b ex-post replay:     36/36 opened,  NET = $+47,735  (no BP/shock/overlay)")
    extra_net = sum(t.exit_pnl for t in extra_trades)
    print(f"  Phase 2-A full engine:       {opened_count}/36 opened,  NET = ${extra_net:+,.0f}")
    print(f"  Gap explained by BP + shock + overlay: "
          f"{36 - opened_count} cluster(s) blocked, "
          f"${47_735 - extra_net:+,.0f} PnL difference")


if __name__ == "__main__":
    run_study()
