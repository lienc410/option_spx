"""Q062 Tier 2 — Structure × Width × DTE Full Grid Scan.

Tier 1 verdict was FAIL (baseline Pareto), but PM elected to run Tier 2 for
final confirmation given small Sleeve B sample and naked-call pricing caveat.

Grid:
  Structures: S1 vertical (ATM/+X%), S2 naked ATM call, S3 ITM-5% naked call
  Widths (S1 only): 2.5% / 5% / 7.5% / 10% / 15%
  DTEs: 30 / 45 / 60 / 90 / 120 / 180

  S1 cells = 5 widths × 6 DTEs = 30
  S2 cells = 6 DTEs
  S3 cells = 6 DTEs
  Total per sleeve = 42 cells × 2 sleeves = 84 cells

Same trigger logic (dd4 lenient for A, dd15 + MA10 reclaim for B).
Same 10% sizing per sleeve. Same BS+skew+term pricing.
Each cell uses DTE-specific no-overlap (apples-to-apples within cell).

Pass bar (consistent with Tier 1):
  Variant beats baseline on ≥ 2/3:
    - ann ROE ≥ +1.0pp
    - worst trade ≥ +5pp
    - max DD ≥ +3pp

Outputs:
  data/q062_tier2_grid.csv  — full grid metrics
  Console: top-5 by ann ROE per sleeve, top-5 by Sharpe per sleeve,
           Pareto candidates passing bar, heatmap printout for vertical.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from research.q062.q062_tier1_structure_scan import (
    Variant, _build_signals, _compute_metrics, _load_data, _run_variant, _print_table,
)

REPO = Path(__file__).resolve().parents[2]
GRID_CSV = REPO / "data" / "q062_tier2_grid.csv"

WIDTHS = [0.025, 0.05, 0.075, 0.10, 0.15]
DTES = [30, 45, 60, 90, 120, 180]
ITM_OFFSET = -0.05  # S3: ITM 5%


def _build_grid_for_sleeve(sleeve: str) -> list[Variant]:
    grid = []
    for dte in DTES:
        for w in WIDTHS:
            grid.append(Variant(f"S1_{int(w*1000)/10}pct_D{dte}", "vertical", 0.00, w, dte))
        grid.append(Variant(f"S2_nakedATM_D{dte}", "naked_call", 0.00, None, dte))
        grid.append(Variant(f"S3_ITM5pct_D{dte}", "naked_call", ITM_OFFSET, None, dte))
    return grid


def _run_sleeve(df: pd.DataFrame, grid: list[Variant], years: float, sleeve_id: str):
    results = []
    for v in grid:
        sig_a, sig_b = _build_signals(df, v.dte)
        sig = sig_a if sleeve_id == "A" else sig_b
        trades = _run_variant(df, sig, v)
        m = _compute_metrics(trades, years)
        results.append((v, m))
    return results


def _check_pass_bar(baseline_m, m, pass_bar_ann=1.0, pass_bar_worst=5.0, pass_bar_dd=3.0):
    wins, notes = 0, []
    if m.ann_ROE_pct - baseline_m.ann_ROE_pct >= pass_bar_ann:
        wins += 1; notes.append(f"ann +{m.ann_ROE_pct - baseline_m.ann_ROE_pct:.2f}pp")
    if m.worst_trade_pct - baseline_m.worst_trade_pct >= pass_bar_worst:
        wins += 1; notes.append(f"worst +{m.worst_trade_pct - baseline_m.worst_trade_pct:.1f}pp")
    if m.max_dd_pct - baseline_m.max_dd_pct >= pass_bar_dd:
        wins += 1; notes.append(f"DD +{m.max_dd_pct - baseline_m.max_dd_pct:.1f}pp")
    return wins, notes


def _print_top_n(name, results, key, n=5, reverse=True):
    sorted_r = sorted(results, key=lambda x: getattr(x[1], key), reverse=reverse)
    print(f"\n  Top {n} Sleeve {name} by {key}:")
    print(f"  {'rank':<5} {'variant':<26} {'AnnROE%':>8} {'Sharpe':>7} {'MaxDD%':>7} {'Worst%':>7} {'WR%':>5} {'n':>3}")
    for i, (v, m) in enumerate(sorted_r[:n], 1):
        print(f"  {i:<5} {v.name:<26} {m.ann_ROE_pct:>+7.2f}% {m.sharpe:>+6.2f} "
              f"{m.max_dd_pct:>+6.1f}% {m.worst_trade_pct:>+6.1f}% {m.win_rate_pct:>4.0f}% {m.n:>3d}")


def _print_heatmap(name, results):
    """Print vertical (S1) AnnROE heatmap: rows = DTE, cols = width."""
    print(f"\n  Sleeve {name} S1 vertical AnnROE% heatmap (rows=DTE, cols=width):")
    print(f"    {'DTE':<5}", " ".join(f"{int(w*100*10)/10:>6.1f}%" for w in WIDTHS))
    for dte in DTES:
        row = []
        for w in WIDTHS:
            cell = next(((v, m) for v, m in results
                         if v.structure == "vertical" and v.dte == dte and abs(v.short_offset_pct - w) < 1e-6), None)
            if cell:
                row.append(f"{cell[1].ann_ROE_pct:>+6.2f}")
            else:
                row.append("    -- ")
        print(f"    {dte:<5}", " ".join(row))


def _baseline(results):
    return next(m for v, m in results if v.name == "S1_5.0pct_D90")


def main():
    print("Q062 Tier 2 — Full Grid Scan")
    print("=" * 70)
    df = _load_data()
    years = (df.index.max() - df.index.min()).days / 365.25

    grid_a = _build_grid_for_sleeve("A")
    grid_b = _build_grid_for_sleeve("B")
    print(f"Grid size per sleeve: {len(grid_a)} cells")
    print(f"Total cells: {len(grid_a) + len(grid_b)}")
    print(f"Sample years: {years:.1f}")

    print("\nRunning Sleeve A grid …")
    results_a = _run_sleeve(df, grid_a, years, "A")
    print("Running Sleeve B grid …")
    results_b = _run_sleeve(df, grid_b, years, "B")

    # ── Top-N tables ──
    print("\n" + "=" * 70)
    print("Top-5 by AnnROE")
    print("=" * 70)
    _print_top_n("A", results_a, "ann_ROE_pct")
    _print_top_n("B", results_b, "ann_ROE_pct")

    print("\n" + "=" * 70)
    print("Top-5 by Sharpe")
    print("=" * 70)
    _print_top_n("A", results_a, "sharpe")
    _print_top_n("B", results_b, "sharpe")

    # ── Pass-bar analysis ──
    print("\n" + "=" * 70)
    print("Pass-bar candidates (≥ 2/3 of {ann +1.0pp, worst +5pp, dd +3pp})")
    print("=" * 70)
    bl_a = _baseline(results_a)
    bl_b = _baseline(results_b)
    print(f"\n  Baseline Sleeve A: ann={bl_a.ann_ROE_pct:.2f}% / worst={bl_a.worst_trade_pct:.1f}% / "
          f"dd={bl_a.max_dd_pct:.1f}% / Sharpe={bl_a.sharpe:.2f} / n={bl_a.n}")
    print(f"  Baseline Sleeve B: ann={bl_b.ann_ROE_pct:.2f}% / worst={bl_b.worst_trade_pct:.1f}% / "
          f"dd={bl_b.max_dd_pct:.1f}% / Sharpe={bl_b.sharpe:.2f} / n={bl_b.n}")

    pass_a = []
    for v, m in results_a:
        if v.name == "S1_5.0pct_D90": continue
        wins, notes = _check_pass_bar(bl_a, m)
        if wins >= 2:
            pass_a.append((v, m, wins, notes))
    pass_b = []
    for v, m in results_b:
        if v.name == "S1_5.0pct_D90": continue
        wins, notes = _check_pass_bar(bl_b, m)
        if wins >= 2:
            pass_b.append((v, m, wins, notes))

    print(f"\n  Sleeve A passing variants: {len(pass_a)}")
    for v, m, w, n in pass_a[:10]:
        print(f"    {v.name:<26} → {w}/3 [{', '.join(n)}] ann={m.ann_ROE_pct:+.2f}%")
    print(f"\n  Sleeve B passing variants: {len(pass_b)}")
    for v, m, w, n in pass_b[:10]:
        print(f"    {v.name:<26} → {w}/3 [{', '.join(n)}] ann={m.ann_ROE_pct:+.2f}%")

    # ── Heatmap ──
    print("\n" + "=" * 70)
    print("S1 vertical AnnROE% heatmap")
    print("=" * 70)
    _print_heatmap("A", results_a)
    _print_heatmap("B", results_b)

    # ── CSV dump ──
    GRID_CSV.parent.mkdir(parents=True, exist_ok=True)
    with GRID_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "sleeve", "variant", "structure", "long_offset", "short_offset", "dte",
            "n", "win_rate_pct", "ann_ROE_pct", "max_dd_pct", "worst_trade_pct",
            "median_winner_pct", "median_loser_pct", "sharpe",
            "marginal_dollar_per_bp_day", "cvar_5pct",
            "disaster_2008", "disaster_2020", "disaster_2022",
        ])
        for sleeve_id, results in [("A", results_a), ("B", results_b)]:
            for v, m in results:
                w.writerow([
                    sleeve_id, v.name, v.structure, v.long_offset_pct,
                    v.short_offset_pct if v.short_offset_pct is not None else "",
                    v.dte,
                    m.n, round(m.win_rate_pct, 1), round(m.ann_ROE_pct, 3),
                    round(m.max_dd_pct, 2), round(m.worst_trade_pct, 2),
                    round(m.median_winner_pct, 3), round(m.median_loser_pct, 3),
                    round(m.sharpe, 3), round(m.marginal_dollar_per_bp_day, 6),
                    round(m.cvar_5pct, 2),
                    round(m.disaster_2008, 2), round(m.disaster_2020, 2), round(m.disaster_2022, 2),
                ])
    print(f"\nwrote {GRID_CSV}")

    # ── Verdict ──
    print("\n" + "=" * 70)
    print("Tier 2 Verdict")
    print("=" * 70)
    print(f"  Sleeve A: {'PASS' if pass_a else 'FAIL'} ({len(pass_a)} candidates beat baseline ≥ 2/3)")
    print(f"  Sleeve B: {'PASS' if pass_b else 'FAIL'} ({len(pass_b)} candidates beat baseline ≥ 2/3)")
    if pass_a or pass_b:
        print("\n→ Tier 3 robustness check warranted on top candidates.")
    else:
        print("\n→ Baseline Pareto confirmed across full grid. Q062 closure.")


if __name__ == "__main__":
    main()
