"""Q071 P3 — Cadence-aware modes for promising gates.

For each gate that passed P2 stopping condition (ann_roe ≥ base AND V1 PASS),
test three ladder implementations:

  Mode A — Hard skip      : gate fail → wait next 5-TD window (P2 default)
  Mode B — Delay retry    : gate fail → re-check daily up to 5 TD, then give up
  Mode C — Size scale     : gate fail → enter at 0.5 unit (half-size)

Reports ann_roe / avg_active_slots / slot_occupancy_pct / worst_cluster_3m_NLV.

Output:
  q071_p3_results.csv   (gate × mode × metrics)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from research.q071.q071_engine import (  # noqa: E402
    run_v2f_with_gate, run_bootstrap, EntryCtx, gate_pass_all,
)

OUT = REPO / "research" / "q071"

# Reuse P2 gate functions
from research.q071.q071_p2_gate_sweep import (  # noqa: E402
    _g1, _g3, _g6, _g8_exclude_p1_worst, _g9_exclude_disaster_pocket,
)

# Gates to test (from P2 promising + comparison set)
GATES_P3 = [
    ("G6", _g6,                       "VIX ≥ 22"),
    ("G8", _g8_exclude_p1_worst,      "exclude IVP 55-70"),
    ("G1", _g1,                       "IVP_252 ≤ 55"),
    ("G3", _g3,                       "IVP ∈ [43,55] (Q041 literal)"),
]

MODES = [
    ("A_hard_skip",   "hard_skip"),
    ("B_delay_retry", "delay_retry"),
    ("C_size_scale",  "size_scale"),
]


def worst_cluster_3m_nlv(daily_rows, initial_equity: float = 500_000.0) -> float:
    """Worst rolling 63-TD (3-month) drawdown in pnl, normalised to NLV."""
    if not daily_rows:
        return 0.0
    pnls = np.array([dr.total_pnl for dr in daily_rows])
    if len(pnls) < 63:
        return float(pnls.sum() / initial_equity)
    rolling = pd.Series(pnls).rolling(63).sum()
    return float(rolling.min() / initial_equity)


def slot_occupancy_pct(daily_rows) -> float:
    """% of trading days with ≥1 active slot."""
    if not daily_rows:
        return 0.0
    occupied = sum(1 for dr in daily_rows if dr.open_positions > 0)
    return occupied / len(daily_rows) * 100.0


def main() -> None:
    print("=" * 100)
    print("Q071 P3 — Cadence Modes for Promising Gates (2000-01-01 → present)")
    print("=" * 100)

    rows = []
    for gate_label, gate_fn, desc in GATES_P3:
        print(f"\n── Gate {gate_label}: {desc} ────────────────────────────")
        for mode_label, mode_arg in MODES:
            r = run_v2f_with_gate(
                gate_fn=gate_fn,
                cadence_mode=mode_arg,
                label=f"{gate_label}_{mode_label}",
            )
            boot = run_bootstrap(r, seeds=20, block_size=250)
            cluster_3m = worst_cluster_3m_nlv(r["daily_rows"])
            occ = slot_occupancy_pct(r["daily_rows"])
            print(f"  [{mode_label:14}] n={r['n_trades']:>4}  "
                  f"ann_roe={r['ann_roe_geo']*100:+.2f}%  "
                  f"avg_slots={r['avg_slots']:.2f}  occ={occ:.0f}%  "
                  f"worst3m_NLV={cluster_3m*100:+.1f}%  "
                  f"sig={boot['sig_rate']*100:.0f}%")
            rows.append({
                "gate":              gate_label,
                "mode":              mode_label,
                "desc":              desc,
                "n_trades":          r["n_trades"],
                "ann_roe":           round(r["ann_roe_geo"] * 100, 3),
                "sharpe":            round(r["sharpe"], 3),
                "max_dd":            round(r["max_drawdown"] * 100, 2),
                "worst_pnl_nlv":     round(r["worst_pnl_nlv"] * 100, 2),
                "worst_cluster_3m_nlv": round(cluster_3m * 100, 2),
                "avg_slots":         round(r["avg_slots"], 2),
                "peak_slots":        r["peak_slots"],
                "slot_occupancy_pct": round(occ, 1),
                "peak_bp_pct_nlv":   round(r["peak_bp_pct_nlv"] * 100, 1),
                "v1_pass":           bool(r["v1_pass"]),
                "sig_rate_pct":      round(boot["sig_rate"] * 100, 1),
                "boot_ci_lo_ann":    round(boot["ci_lo"] * 100, 3),
            })

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "q071_p3_results.csv", index=False)
    print(f"\nWrote {OUT / 'q071_p3_results.csv'}")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    print("\n" + "=" * 100)
    print("Summary table")
    print("=" * 100)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
