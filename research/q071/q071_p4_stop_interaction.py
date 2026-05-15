"""Q071 P4 — STOP interaction proof.

Under the best P2 gate (G6, VIX ≥ 22, hard-skip), test 4 stop variants to
verify the prompt's claim: "STOP=15 解决 Q041 T1 尾部问题".

Key question: does no_stop produce a Q041-T1-style worst trade (~-18%)?
Does stop_15 successfully clip it to V1 PASS (≥ -15% NLV)?

Output: q071_p4_results.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from research.q071.q071_engine import run_v2f_with_gate, run_bootstrap  # noqa: E402
from research.q071.q071_p2_gate_sweep import _g6, _g8_exclude_p1_worst, _g1, _g3  # noqa: E402
from research.q071.q071_p3_cadence import worst_cluster_3m_nlv  # noqa: E402

OUT = REPO / "research" / "q071"


STOP_VARIANTS = [
    ("no_stop",  9999.0),  # effectively disable
    ("stop_10",  10.0),
    ("stop_15",  15.0),     # V2f baseline
    ("stop_20",  20.0),
]

# Test on P2 promising gates + baseline (no gate, for completeness)
TEST_GATES = [
    ("V2f_base", None,                       "no gate"),
    ("G6",       _g6,                        "VIX ≥ 22"),
    ("G8",       _g8_exclude_p1_worst,       "exclude IVP 55-70"),
    ("G1",       _g1,                        "IVP_252 ≤ 55"),
]


def main() -> None:
    print("=" * 100)
    print("Q071 P4 — STOP Interaction Test (2000-01-01 → present)")
    print("=" * 100)

    rows = []
    for gate_label, gate_fn, gate_desc in TEST_GATES:
        print(f"\n── Gate {gate_label}: {gate_desc} ──────────────────────────────")
        kwargs = {} if gate_fn is None else {"gate_fn": gate_fn}
        for stop_label, stop_mult in STOP_VARIANTS:
            r = run_v2f_with_gate(
                stop_mult=stop_mult,
                cadence_mode="hard_skip",
                label=f"{gate_label}_{stop_label}",
                **kwargs,
            )
            boot = run_bootstrap(r, seeds=20, block_size=250)
            cluster_3m = worst_cluster_3m_nlv(r["daily_rows"])
            # stop hit rate
            stops = sum(1 for t in r["trades"] if t["exit_reason"] == "stop_loss")
            stop_rate = stops / r["n_trades"] if r["n_trades"] > 0 else 0.0
            print(f"  [{stop_label:8}]  n={r['n_trades']:>4}  "
                  f"ann_roe={r['ann_roe_geo']*100:+.2f}%  "
                  f"worst_nlv={r['worst_pnl_nlv']*100:+.1f}%  "
                  f"worst3m={cluster_3m*100:+.1f}%  "
                  f"stop_hit={stop_rate*100:.1f}%  "
                  f"V1={'PASS' if r['v1_pass'] else 'FAIL'}  "
                  f"sig={boot['sig_rate']*100:.0f}%")
            rows.append({
                "gate":              gate_label,
                "gate_desc":         gate_desc,
                "stop_variant":      stop_label,
                "stop_mult":         stop_mult,
                "n_trades":          r["n_trades"],
                "ann_roe":           round(r["ann_roe_geo"] * 100, 3),
                "sharpe":            round(r["sharpe"], 3),
                "max_dd":            round(r["max_drawdown"] * 100, 2),
                "worst_pnl_nlv":     round(r["worst_pnl_nlv"] * 100, 2),
                "worst_cluster_3m_nlv": round(cluster_3m * 100, 2),
                "stop_hit_rate_pct": round(stop_rate * 100, 2),
                "v1_pass":           bool(r["v1_pass"]),
                "sig_rate_pct":      round(boot["sig_rate"] * 100, 1),
            })

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "q071_p4_results.csv", index=False)
    print(f"\nWrote {OUT / 'q071_p4_results.csv'}")

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    print("\n" + "=" * 100)
    print("Summary table")
    print("=" * 100)
    print(df.to_string(index=False))

    # ── Interpretation ─────────────────────────────────────────
    print("\n" + "=" * 100)
    print("Q041-T1 tail comparison (V2f_base no_stop)")
    print("=" * 100)
    base_no_stop = df[(df["gate"] == "V2f_base") & (df["stop_variant"] == "no_stop")].iloc[0]
    base_stop_15 = df[(df["gate"] == "V2f_base") & (df["stop_variant"] == "stop_15")].iloc[0]
    print(f"V2f_base no_stop  worst trade NLV: {base_no_stop['worst_pnl_nlv']:+.1f}%")
    print(f"V2f_base stop_15  worst trade NLV: {base_stop_15['worst_pnl_nlv']:+.1f}%")
    print(f"Δ from STOP=15 protection: {base_stop_15['worst_pnl_nlv'] - base_no_stop['worst_pnl_nlv']:+.1f}pp")
    print(f"Q041 T1 reference worst: -17.99%")
    if base_no_stop['worst_pnl_nlv'] <= -15:
        print(f"→ V2f no_stop has Q041-T1-style tail. STOP=15 brings it to {base_stop_15['worst_pnl_nlv']:+.1f}% "
              f"(V1 {'PASS' if base_stop_15['v1_pass'] else 'FAIL'}).")
    else:
        print(f"→ V2f no_stop worst ({base_no_stop['worst_pnl_nlv']:+.1f}%) is NOT close to Q041 T1 (-17.99%).")
        print(f"   V2f's structural exits (ladder_exit ≤21 DTE) already bound the tail.")
        print(f"   STOP=15 vs no_stop change: {base_stop_15['worst_pnl_nlv'] - base_no_stop['worst_pnl_nlv']:+.1f}pp")
        print(f"   Interpretation: STOP=15 integration provides little additional V2f-specific tail edge.")


if __name__ == "__main__":
    main()
