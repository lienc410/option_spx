"""Q064 Phase 9 — Spell Reset Mechanism Sensitivity Study.

Tests three independent dimensions of HV spell logic:
  9a — VIX_low_reset hysteresis (consecutive-days requirement for spell reset)
  9b — VIX_high_reset (35+ → spell reset; is this redundant given EXTREME_VOL gate?)
  9c — spell_age_cap (30d → other values; per 2022 P8 forensic, likely binding)

Method: monkey-patch backtest.engine functions:
  - _update_hv_spell_state (controls when spell starts/ends/resets)
  - _block_hv_spell_entry  (controls age_cap check; max_trades_per_spell unchanged)

Then run engine.run_backtest, capture V3-A trades via selector wrapper, compute
per-variant metrics on the same 2009-2025 window as P6/P7/P8.

Reference baseline (V0 = production current state):
  - VIX_low_reset_hysteresis_days = 1  (single-day VIX < 22 resets spell)
  - high_reset_enabled = True          (VIX >= 35 resets spell)
  - spell_age_cap = 30                 (block entry after 30d in spell)
  - max_trades_per_spell = 2           (unchanged across all Q9 variants)

For comparability with P6: same 33 V3-A trades expected under V0.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import backtest.engine as eng
import strategy.selector as sel
from signals.iv_rank import IVSignal
from signals.trend import TrendSignal
from signals.vix_regime import Regime
from backtest.engine import HIGH_VOL_STRATEGY_KEYS

OUT_SUMMARY = REPO / "research" / "q064" / "q064_p9_summary.csv"
OUT_DETAIL = REPO / "research" / "q064" / "q064_p9_trade_detail.csv"

START = "2009-01-01"
END = "2025-06-30"
ACCOUNT = 150_000.0


# ── Original function references (cached before any patching) ─────────────────
_ORIG_UPDATE = eng._update_hv_spell_state
_ORIG_BLOCK = eng._block_hv_spell_entry


def make_patched_funcs(low_reset_hysteresis_days: int = 1,
                       high_reset_enabled: bool = True,
                       age_cap: int = 30):
    """Build patched spell-state functions for a given Q9 variant.

    low_reset_hysteresis_days:
      VIX must be < 22 (out of HIGH_VOL) for this many consecutive days
      before spell resets. Default 1 = current production behavior.

    high_reset_enabled:
      If True, VIX >= 35 also triggers spell reset. If False, spell maintained
      across VIX spikes (only low reset matters).

    age_cap:
      Override params.spell_age_cap. Block entry when spell_age > age_cap.
    """
    # Module-level state to track consecutive low days
    state = {"consecutive_below": 0}

    def patched_update(regime, vix, date, hv_spell_start, hv_spell_trade_count, extreme_vix):
        # Determine "currently in HV spell" per variant
        if high_reset_enabled:
            in_hv = (regime == Regime.HIGH_VOL) and (vix < extreme_vix)
        else:
            in_hv = regime == Regime.HIGH_VOL
        if in_hv:
            state["consecutive_below"] = 0
            if hv_spell_start is None:
                hv_spell_start = date
            return hv_spell_start, hv_spell_trade_count
        # Not in HV: count consecutive days
        state["consecutive_below"] += 1
        if state["consecutive_below"] >= low_reset_hysteresis_days:
            state["consecutive_below"] = 0
            return None, {}
        # Hysteresis: maintain spell state
        return hv_spell_start, hv_spell_trade_count

    def patched_block(regime, vix, new_key, hv_spell_start, hv_spell_trade_count, params, date):
        if regime != Regime.HIGH_VOL or vix >= params.extreme_vix:
            return False
        if new_key not in HIGH_VOL_STRATEGY_KEYS:
            return False
        spell_age = (date - hv_spell_start).days if hv_spell_start is not None else 0
        if spell_age > age_cap:
            return True
        if hv_spell_trade_count.get(new_key, 0) >= params.max_trades_per_spell:
            return True
        return False

    return patched_update, patched_block, state


def capture_v3a_trades(bt):
    """Get V3-A IC_HV trades from a backtest result.
    Re-walks signal_history to identify which entry_dates were V3-A path.
    """
    sig_df = pd.DataFrame(bt.signals)
    # V3-A path: regime=HIGH_VOL, iv_signal=HIGH, trend in (BEARISH, NEUTRAL),
    #            recommendation = Iron Condor (High Vol).
    # (is_aftermath check is done by selector internally so already filtered)
    v3a_signal_dates = set()
    for _, r in sig_df.iterrows():
        if (r.get("regime") == "HIGH_VOL"
            and r.get("iv_signal") == "HIGH"
            and r.get("trend") in ("BEARISH", "NEUTRAL")
            and r.get("strategy") == "Iron Condor (High Vol)"):
            v3a_signal_dates.add(r["date"])
    return [t for t in bt.trades
            if t.entry_date in v3a_signal_dates and "Iron Condor" in t.strategy.value]


def run_variant(label: str, low_reset_days: int, high_reset: bool, age_cap: int) -> dict:
    """Patch engine, run backtest, compute V3-A trade metrics."""
    patched_update, patched_block, _state = make_patched_funcs(
        low_reset_hysteresis_days=low_reset_days,
        high_reset_enabled=high_reset,
        age_cap=age_cap,
    )
    eng._update_hv_spell_state = patched_update
    eng._block_hv_spell_entry = patched_block
    try:
        bt = eng.run_backtest(start_date=START, end_date=END,
                              account_size=ACCOUNT, verbose=False)
        v3a = capture_v3a_trades(bt)
    finally:
        eng._update_hv_spell_state = _ORIG_UPDATE
        eng._block_hv_spell_entry = _ORIG_BLOCK

    pnls = [t.exit_pnl for t in v3a]
    if not pnls:
        return {
            "label": label, "n": 0, "wr_pct": 0.0, "avg_pnl": 0.0,
            "total_pnl": 0.0, "worst": 0.0, "best": 0.0,
            "avg_bp": 0.0, "trades": v3a,
        }
    wins = sum(1 for p in pnls if p > 0)
    bps = [t.total_bp for t in v3a if t.total_bp > 0]
    return {
        "label": label,
        "n": len(v3a),
        "wr_pct": round(wins / len(pnls) * 100, 1),
        "avg_pnl": round(sum(pnls) / len(pnls), 2),
        "total_pnl": round(sum(pnls), 2),
        "worst": round(min(pnls), 2),
        "best": round(max(pnls), 2),
        "avg_bp": round(sum(bps) / len(bps), 2) if bps else 0.0,
        "trades": v3a,
    }


def main():
    print("=" * 100)
    print("Q064 Phase 9 — Spell Reset Mechanism Sensitivity Study")
    print("=" * 100)

    variants = [
        # label,                                hysteresis, high_reset, age_cap
        ("9a/V0_baseline (1d / high_reset / 30d)",    1, True,  30),
        # ── 9a: VIX_low_reset hysteresis ─────────────────────────────────────
        ("9a/V1_hyst_3d",                              3, True,  30),
        ("9a/V2_hyst_5d",                              5, True,  30),
        ("9a/V3_threshold_drop_20",                    1, True,  30),  # alt: rely on baseline regime (sel:22) — no change in our code; placeholder
        ("9a/V4_no_op",                                1, True,  30),  # control duplicate of V0 (sanity)
        # ── 9b: VIX_high_reset ────────────────────────────────────────────────
        ("9b/V1_no_high_reset",                        1, False, 30),
        # ── 9c: spell_age_cap ─────────────────────────────────────────────────
        ("9c/V1_age_15d",                              1, True,  15),
        ("9c/V2_age_60d",                              1, True,  60),
        ("9c/V3_age_90d",                              1, True,  90),
        ("9c/V4_age_180d",                             1, True,  180),
        ("9c/V5_age_inf",                              1, True,  9999),
        # ── 9d: combined top candidates ───────────────────────────────────────
        ("9d/combo_hyst3+age60",                       3, True,  60),
        ("9d/combo_hyst3+age90+no_high",               3, False, 90),
    ]

    results = []
    for spec in variants:
        label = spec[0]
        print(f"\nRunning {label} ...")
        r = run_variant(*spec)
        print(f"  n={r['n']:>3}  WR={r['wr_pct']:>5}%  total=${r['total_pnl']:>+9,.0f}  "
              f"avg=${r['avg_pnl']:>+6,.0f}  worst=${r['worst']:>+8,.0f}  avg_bp=${r['avg_bp']:>+7,.0f}")
        results.append(r)

    # ── Save summary ──
    print("\n" + "=" * 100)
    print("Summary table")
    print("=" * 100)
    print(f"{'variant':<42} {'n':>3} {'WR%':>5} {'total':>10} {'avg':>8} {'worst':>9} {'avg_bp':>8}")
    print("-" * 100)
    for r in results:
        print(f"{r['label']:<42} {r['n']:>3} {r['wr_pct']:>5}% ${r['total_pnl']:>+8,.0f} "
              f"${r['avg_pnl']:>+6,.0f} ${r['worst']:>+7,.0f} ${r['avg_bp']:>+6,.0f}")

    # Δ vs baseline
    baseline = results[0]
    print("\n" + "=" * 100)
    print(f"Δ vs baseline V0 (n={baseline['n']}, WR={baseline['wr_pct']}%, total=${baseline['total_pnl']:+,.0f}, worst=${baseline['worst']:+,.0f})")
    print("=" * 100)
    print(f"{'variant':<42} {'Δn':>4} {'ΔWR':>7} {'Δtotal':>11} {'Δworst':>11} {'pareto?':<10}")
    print("-" * 100)
    for r in results[1:]:
        dn = r['n'] - baseline['n']
        dwr = r['wr_pct'] - baseline['wr_pct']
        dtotal = r['total_pnl'] - baseline['total_pnl']
        dworst = r['worst'] - baseline['worst']
        # Pareto check: total > 0 + worst >= baseline.worst
        pareto = "PASS" if (dtotal > 0 and dworst >= -100) else "FAIL"
        print(f"{r['label']:<42} {dn:>+4} {dwr:>+5.1f}pp ${dtotal:>+9,.0f} ${dworst:>+9,.0f} {pareto:<10}")

    # ── Write CSVs ──
    summary_df = pd.DataFrame([
        {k: v for k, v in r.items() if k != "trades"} for r in results
    ])
    summary_df.to_csv(OUT_SUMMARY, index=False)
    print(f"\nWrote {OUT_SUMMARY}")

    # Trade detail (variant × trade)
    detail_rows = []
    for r in results:
        for t in r["trades"]:
            detail_rows.append({
                "variant": r["label"],
                "entry_date": t.entry_date,
                "exit_date": t.exit_date,
                "exit_reason": t.exit_reason,
                "pnl": t.exit_pnl,
                "bp": t.total_bp,
            })
    detail_df = pd.DataFrame(detail_rows)
    detail_df.to_csv(OUT_DETAIL, index=False)
    print(f"Wrote {OUT_DETAIL}")


if __name__ == "__main__":
    main()
