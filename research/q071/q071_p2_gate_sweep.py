"""Q071 P2 — Gate sweep on V2f baseline.

Tests 7 prompt-specified gates + 2 data-driven gates derived from P1 findings:

  V2f_base                  — no extra gate (production baseline)
  G1  IVP_252 ≤ 55          — only block extreme high IV
  G2  IVP_252 ≥ 43          — only block extreme low IV
  G3  IVP_252 ∈ [43, 55]    — full Q041 window (rebuttal candidate)
  G4  IVP_252 ≤ 70          — loose upper cap
  G5  VIX < 30              — avoid extreme VIX (SPAN risk)
  G6  VIX ≥ 22              — HIGH_VOL only
  G7  VIX ∈ [15, 25]        — mid band
  G8  IVP_252 NOT in [55,70]    — data-driven: exclude P1's worst bucket
  G9  NOT (IVP_252 in [55,70] AND VIX in [15,20])  — exclude P1 disaster pocket

For each: hard-skip mode (gate fail → wait next cadence), full 26y backtest.

Output:
  q071_p2_results.csv   (one row per gate; metrics + bootstrap sig_rate)
  q071_p2_results.json  (full result blobs, for downstream P3/P4 reuse)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from research.q071.q071_engine import (  # noqa: E402
    run_v2f_with_gate, run_bootstrap, gate_pass_all, EntryCtx,
)

OUT = REPO / "research" / "q071"


# ── Gate definitions ───────────────────────────────────────────────────

def _g1(ctx: EntryCtx) -> bool:
    return (not pd.isna(ctx.ivp252)) and (ctx.ivp252 <= 55)

def _g2(ctx: EntryCtx) -> bool:
    return (not pd.isna(ctx.ivp252)) and (ctx.ivp252 >= 43)

def _g3(ctx: EntryCtx) -> bool:
    return (not pd.isna(ctx.ivp252)) and (43 <= ctx.ivp252 <= 55)

def _g4(ctx: EntryCtx) -> bool:
    return (not pd.isna(ctx.ivp252)) and (ctx.ivp252 <= 70)

def _g5(ctx: EntryCtx) -> bool:
    return ctx.vix < 30

def _g6(ctx: EntryCtx) -> bool:
    return ctx.vix >= 22

def _g7(ctx: EntryCtx) -> bool:
    return 15 <= ctx.vix <= 25

def _g8_exclude_p1_worst(ctx: EntryCtx) -> bool:
    """Exclude IVP 55-70 bucket only (P1's worst zone, -$68k total)."""
    if pd.isna(ctx.ivp252):
        return True
    return not (55 <= ctx.ivp252 < 70)

def _g9_exclude_disaster_pocket(ctx: EntryCtx) -> bool:
    """Exclude IVP 55-70 × VIX 15-20 disaster pocket only (P1 finding: -$113k, -119% avg pnl)."""
    if pd.isna(ctx.ivp252):
        return True
    in_ivp_zone = 55 <= ctx.ivp252 < 70
    in_vix_zone = 15 <= ctx.vix < 20
    return not (in_ivp_zone and in_vix_zone)


GATES = [
    ("V2f_base",  gate_pass_all,              "no gate (baseline)"),
    ("G1",        _g1,                        "IVP_252 ≤ 55"),
    ("G2",        _g2,                        "IVP_252 ≥ 43"),
    ("G3",        _g3,                        "IVP_252 ∈ [43, 55]"),
    ("G4",        _g4,                        "IVP_252 ≤ 70"),
    ("G5",        _g5,                        "VIX < 30"),
    ("G6",        _g6,                        "VIX ≥ 22"),
    ("G7",        _g7,                        "VIX ∈ [15, 25]"),
    ("G8",        _g8_exclude_p1_worst,       "exclude IVP 55-70 zone (P1 worst)"),
    ("G9",        _g9_exclude_disaster_pocket, "exclude IVP55-70 × VIX15-20 pocket"),
]


def main() -> None:
    print("=" * 100)
    print("Q071 P2 — Gate Sweep on V2f (hard_skip mode, 2000-01-01 → present)")
    print("=" * 100)

    results: list[dict] = []
    baseline = None
    for label, gate_fn, desc in GATES:
        print(f"\n[{label}] {desc}")
        r = run_v2f_with_gate(gate_fn=gate_fn, label=label, cadence_mode="hard_skip")
        boot = run_bootstrap(r, seeds=20, block_size=250)
        r["sig_rate"] = boot["sig_rate"]
        r["boot_ci_lo_ann"] = boot["ci_lo"]
        r["desc"] = desc
        results.append(r)
        if label == "V2f_base":
            baseline = r
        n = r["n_trades"]
        afreq = (n / baseline["n_trades"] * 100) if baseline else 100.0
        print(f"  n={n} ({afreq:.1f}% vs base)  ann_roe={r['ann_roe_geo']*100:+.2f}%  "
              f"sharpe={r['sharpe']:+.2f}  max_dd={r['max_drawdown']*100:+.1f}%  "
              f"worst_nlv={r['worst_pnl_nlv']*100:+.1f}%  V1={'P' if r['v1_pass'] else 'F'}  "
              f"sig={boot['sig_rate']*100:.0f}%")

    # ── Summary table ────────────────────────────────────────────
    rows = []
    base_n  = baseline["n_trades"]
    base_an = baseline["ann_roe_geo"]
    base_dd = baseline["max_drawdown"]
    base_worst = baseline["worst_pnl_nlv"]
    for r in results:
        rows.append({
            "label":             r["label"],
            "desc":              r["desc"],
            "n_entries":         r["n_trades"],
            "entry_freq_pct":    round(r["n_trades"] / base_n * 100, 1),
            "ann_roe":           round(r["ann_roe_geo"] * 100, 3),
            "delta_ann_roe_pp":  round((r["ann_roe_geo"] - base_an) * 100, 3),
            "sharpe":            round(r["sharpe"], 3),
            "sortino":           round(r["sortino"], 3),
            "max_dd":            round(r["max_drawdown"] * 100, 2),
            "delta_dd_pp":       round((r["max_drawdown"] - base_dd) * 100, 2),
            "worst_pnl_nlv":     round(r["worst_pnl_nlv"] * 100, 2),
            "delta_worst_pp":    round((r["worst_pnl_nlv"] - base_worst) * 100, 2),
            "v1_pass":           bool(r["v1_pass"]),
            "avg_slots":         round(r["avg_slots"], 2),
            "peak_slots":        r["peak_slots"],
            "peak_bp_pct_nlv":   round(r["peak_bp_pct_nlv"] * 100, 1),
            "sig_rate_pct":      round(r["sig_rate"] * 100, 1),
            "boot_ci_lo_ann":    round(r["boot_ci_lo_ann"] * 100, 3) if isinstance(r["boot_ci_lo_ann"], float) else r["boot_ci_lo_ann"],
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "q071_p2_results.csv", index=False)
    print(f"\nWrote {OUT / 'q071_p2_results.csv'}")

    print("\n" + "=" * 100)
    print("Summary (Δ vs V2f_base)")
    print("=" * 100)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    print(df.to_string(index=False))

    # ── Stopping condition ─────────────────────────────────────
    print("\n" + "=" * 100)
    print("Stopping condition (P2 → P3 gate)")
    print("=" * 100)
    promising = [r for r in results
                 if r["label"] != "V2f_base"
                 and r["ann_roe_geo"] >= base_an
                 and r["v1_pass"]]
    if not promising:
        print(f"NO gate matches ann_roe ≥ baseline ({base_an*100:+.2f}%) AND V1 PASS.")
        print("→ Stop P3-P5 per stopping rule.")
    else:
        print(f"Promising gates ({len(promising)}):")
        for r in promising:
            print(f"  {r['label']:8} ann_roe={r['ann_roe_geo']*100:+.2f}% "
                  f"(+{(r['ann_roe_geo']-base_an)*100:+.2f}pp) "
                  f"worst={r['worst_pnl_nlv']*100:+.1f}% sig={r['sig_rate']*100:.0f}%")

    # ── Save lite JSON (without daily_rows) ────────────────────
    lite = []
    for r in results:
        lite.append({
            **{k: v for k, v in r.items() if k not in {"trades", "daily_rows"}},
            "n_trades": r["n_trades"],
        })
    (OUT / "q071_p2_results.json").write_text(json.dumps(lite, indent=2, default=str))


if __name__ == "__main__":
    main()
