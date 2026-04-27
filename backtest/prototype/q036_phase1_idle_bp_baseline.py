"""
Q036 Phase 1 — Idle BP baseline measurement (no overlay introduced).

Per `task/IDLE_BP_OVERLAY_RESEARCH_NOTE.md` and Quant framing 2026-04-26:

  Q036 is a CAPITAL-ALLOCATION question, not a rule-replacement question.
  Before evaluating any overlay, we must first measure: how much BP is
  actually idle under V_A SPEC-066 baseline, and is that idle BP available
  in the regime windows where an overlay would want to deploy it?

  Phase 1 deliberately introduces NO overlay; it only measures the
  baseline V_A capital-utilization profile, with regime + aftermath
  conditional slices.

Output sections:
  1. Daily idle BP statistics — full sample
  2. Idle BP distribution — percentiles
  3. Idle BP by regime (LOW_VOL / NORMAL / HIGH_VOL)
  4. Idle BP by aftermath state (cluster vs non-cluster)
  5. Idle BP by VIX bucket (vol stress test)
  6. Idle BP during disaster windows (forced-liquidation proxy)
  7. Aftermath-day deploy capacity — how often is idle BP ≥ {30,40,50}%
     when the system is sitting in an aftermath cluster?
  8. Short-gamma exposure overlap — how often does the system
     already carry short-gamma during aftermath windows?

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.q036_phase1_idle_bp_baseline
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

import strategy.selector as sel
from backtest.engine import run_backtest

START = "2000-01-01"
RECENT_SLICE_START = "2018-01-01"
OFF_PEAK_B = 0.10  # SPEC-066 production value


# ──────────────────────────────────────────────────────────────────────
# VIX cluster map (reused from Q021 Phase 4 — defines aftermath days)
# ──────────────────────────────────────────────────────────────────────

def _load_vix_close():
    pkl = Path("data/market_cache/yahoo__VIX__max__1d.pkl")
    df = pickle.loads(pkl.read_bytes())
    if hasattr(df, "Close"):
        s = df["Close"]
    else:
        s = df.iloc[:, 0]
    return {str(idx.date()): float(v) for idx, v in s.items() if v == v}


def build_cluster_map_and_vix() -> tuple[dict[str, str | None], dict[str, float]]:
    vix = _load_vix_close()
    dates = sorted(vix.keys())
    is_after: dict[str, bool] = {}
    for i, d in enumerate(dates):
        lo = max(0, i - 9)
        win = [vix[sd] for sd in dates[lo:i + 1]]
        peak = max(win)
        cur = vix[d]
        op = (peak - cur) / peak if peak > 0 else 0.0
        is_after[d] = (peak >= 28.0) and (op >= 0.10)

    cluster: dict[str, str | None] = {}
    cur_id: str | None = None
    for d in dates:
        if is_after[d]:
            if cur_id is None:
                cur_id = d
            cluster[d] = cur_id
        else:
            cur_id = None
            cluster[d] = None
    return cluster, vix


# ──────────────────────────────────────────────────────────────────────
# Distribution helpers
# ──────────────────────────────────────────────────────────────────────

def _percentiles(arr, qs=(0, 5, 25, 50, 75, 95, 100)):
    if len(arr) == 0:
        return {q: 0.0 for q in qs}
    a = np.asarray(arr, dtype=float)
    return {q: float(np.percentile(a, q)) for q in qs}


def _mean_std(arr):
    if len(arr) == 0:
        return 0.0, 0.0
    a = np.asarray(arr, dtype=float)
    return float(a.mean()), float(a.std(ddof=1)) if len(a) > 1 else (float(a.mean()), 0.0)


def _print_pcts(label, arr, account_size):
    """Print BP-pct percentiles (bp_used as fraction of account_size)."""
    if len(arr) == 0:
        print(f"  {label:<32} (no observations)")
        return
    pct_arr = [bp / account_size * 100 for bp in arr]
    p = _percentiles(pct_arr)
    mean, std = _mean_std(pct_arr)
    n = len(pct_arr)
    print(f"  {label:<32} n={n:>5}  mean={mean:>5.1f}%  std={std:>4.1f}%  "
          f"p5={p[5]:>5.1f}  p25={p[25]:>5.1f}  p50={p[50]:>5.1f}  "
          f"p75={p[75]:>5.1f}  p95={p[95]:>5.1f}  max={p[100]:>5.1f}")


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def run_study():
    print("Q036 Phase 1 — Idle BP baseline measurement (V_A SPEC-066, no overlay)")
    print()

    print("  Building VIX cluster map ...")
    cluster_map, vix_by_date = build_cluster_map_and_vix()
    n_after = sum(1 for v in cluster_map.values() if v is not None)
    n_clusters = len(set(v for v in cluster_map.values() if v is not None))
    print(f"    {n_after} aftermath days across {n_clusters} clusters")
    print()

    # Force SPEC-066 production OFF_PEAK
    orig_op = sel.AFTERMATH_OFF_PEAK_PCT
    sel.AFTERMATH_OFF_PEAK_PCT = OFF_PEAK_B
    try:
        print("  Running V_A SPEC-066 baseline (engine default account_size=$150,000) ...")
        result = run_backtest(start_date=START, verbose=False)
    finally:
        sel.AFTERMATH_OFF_PEAK_PCT = orig_op

    rows = result.portfolio_rows
    if not rows:
        print("ERROR: portfolio_rows empty — engine returned no daily snapshots")
        return

    # Engine constant
    account_size = 150_000.0

    # ── Section 1 — full-sample daily idle BP ─────────────────────────
    print()
    print("=" * 120)
    print("  1. DAILY IDLE BP — FULL SAMPLE")
    print("=" * 120)
    bp_used_all = [r.bp_used for r in rows]
    bp_idle_all = [account_size - r.bp_used for r in rows]
    pct_used = [b / account_size * 100 for b in bp_used_all]
    pct_idle = [b / account_size * 100 for b in bp_idle_all]
    print(f"    Total trading days observed: {len(rows):>6}")
    print(f"    Avg daily BP used:           {np.mean(pct_used):>6.2f}%   "
          f"(median {np.median(pct_used):.2f}%, max {np.max(pct_used):.2f}%)")
    print(f"    Avg daily BP idle:           {np.mean(pct_idle):>6.2f}%   "
          f"(median {np.median(pct_idle):.2f}%, min {np.min(pct_idle):.2f}%)")

    # ── Section 2 — idle BP distribution ──────────────────────────────
    print()
    print("=" * 120)
    print("  2. IDLE BP DISTRIBUTION (% of account_size)")
    print("=" * 120)
    _print_pcts("Full sample", bp_idle_all, account_size)
    bp_idle_recent = [account_size - r.bp_used for r in rows if r.date >= RECENT_SLICE_START]
    _print_pcts(f"Recent slice ({RECENT_SLICE_START}+)", bp_idle_recent, account_size)

    # ── Section 3 — idle BP by regime ─────────────────────────────────
    print()
    print("=" * 120)
    print("  3. IDLE BP BY REGIME")
    print("=" * 120)
    by_regime: dict[str, list[float]] = {}
    for r in rows:
        idle = account_size - r.bp_used
        by_regime.setdefault(r.regime, []).append(idle)
    for regime in sorted(by_regime.keys()):
        _print_pcts(f"regime={regime}", by_regime[regime], account_size)

    # ── Section 4 — idle BP by aftermath state ────────────────────────
    print()
    print("=" * 120)
    print("  4. IDLE BP BY AFTERMATH STATE")
    print("=" * 120)
    bp_after = [account_size - r.bp_used for r in rows if cluster_map.get(r.date) is not None]
    bp_non_after = [account_size - r.bp_used for r in rows if cluster_map.get(r.date) is None]
    _print_pcts("Aftermath day (in cluster)", bp_after, account_size)
    _print_pcts("Non-aftermath day", bp_non_after, account_size)

    # Recent slice cut
    bp_after_r = [account_size - r.bp_used for r in rows
                  if cluster_map.get(r.date) is not None and r.date >= RECENT_SLICE_START]
    bp_non_after_r = [account_size - r.bp_used for r in rows
                      if cluster_map.get(r.date) is None and r.date >= RECENT_SLICE_START]
    _print_pcts(f"Aftermath, {RECENT_SLICE_START}+", bp_after_r, account_size)
    _print_pcts(f"Non-aftermath, {RECENT_SLICE_START}+", bp_non_after_r, account_size)

    # ── Section 5 — idle BP by VIX bucket ─────────────────────────────
    print()
    print("=" * 120)
    print("  5. IDLE BP BY VIX BUCKET (vol-stress conditional)")
    print("=" * 120)
    buckets = [("VIX<15", lambda v: v < 15),
               ("15≤VIX<20", lambda v: 15 <= v < 20),
               ("20≤VIX<25", lambda v: 20 <= v < 25),
               ("25≤VIX<30", lambda v: 25 <= v < 30),
               ("30≤VIX<40", lambda v: 30 <= v < 40),
               ("VIX≥40 (EXTREME)", lambda v: v >= 40)]
    for label, pred in buckets:
        sel_rows = [r for r in rows if pred(r.vix)]
        idles = [account_size - r.bp_used for r in sel_rows]
        _print_pcts(label, idles, account_size)

    # ── Section 6 — disaster windows ──────────────────────────────────
    print()
    print("=" * 120)
    print("  6. IDLE BP DURING DISASTER WINDOWS (forced-liquidation proxy)")
    print("=" * 120)
    windows = [
        ("2008 GFC",    "2008-09-01", "2008-12-31"),
        ("2020 COVID",  "2020-02-20", "2020-04-30"),
        ("2025 Tariff", "2025-04-01", "2025-05-31"),
    ]
    for label, lo, hi in windows:
        sel_rows = [r for r in rows if lo <= r.date <= hi]
        if not sel_rows:
            print(f"  {label:<32} (no rows in window)")
            continue
        idles = [account_size - r.bp_used for r in sel_rows]
        _print_pcts(label, idles, account_size)
        # Worst day in window
        worst_idx = int(np.argmin(idles))
        wr = sel_rows[worst_idx]
        print(f"      worst-idle day in window: {wr.date}  bp_used={wr.bp_used/account_size*100:.1f}%  "
              f"vix={wr.vix:.1f}  regime={wr.regime}  drawdown={wr.drawdown*100:+.2f}%")

    # ── Section 7 — aftermath deploy capacity ─────────────────────────
    print()
    print("=" * 120)
    print("  7. AFTERMATH-DAY DEPLOY CAPACITY")
    print("=" * 120)
    print("    How often, ON AN AFTERMATH DAY, is system idle BP available at given thresholds?")
    print("    Reads as: 'if overlay rule fires today, can the account fund it?'")
    print()
    after_rows = [r for r in rows if cluster_map.get(r.date) is not None]
    after_recent = [r for r in after_rows if r.date >= RECENT_SLICE_START]
    n_after_total = len(after_rows)
    n_after_recent = len(after_recent)
    if n_after_total > 0:
        thresholds_pct = [10, 20, 30, 40, 50, 60, 70, 80]
        # IC_HV adds ~7% (1×) or 14% (2×) — relevant deploy-decision thresholds
        # Threshold := minimum required idle BP % to fund overlay
        print(f"    Full sample n_aftermath_days = {n_after_total}")
        print(f"    {'Threshold (idle BP ≥)':<25} {'days_meeting':>14} {'fraction':>10}")
        for tpct in thresholds_pct:
            t_dollars = account_size * tpct / 100
            n_meet = sum(1 for r in after_rows if (account_size - r.bp_used) >= t_dollars)
            frac = n_meet / n_after_total * 100
            print(f"    {f'≥ {tpct}%':<25} {n_meet:>14} {frac:>9.1f}%")
        print()
        print(f"    Recent slice n_aftermath_days = {n_after_recent}")
        print(f"    {'Threshold (idle BP ≥)':<25} {'days_meeting':>14} {'fraction':>10}")
        for tpct in thresholds_pct:
            t_dollars = account_size * tpct / 100
            n_meet = sum(1 for r in after_recent if (account_size - r.bp_used) >= t_dollars)
            frac = n_meet / n_after_recent * 100 if n_after_recent else 0
            print(f"    {f'≥ {tpct}%':<25} {n_meet:>14} {frac:>9.1f}%")

    # ── Section 8 — short-gamma overlap on aftermath days ─────────────
    print()
    print("=" * 120)
    print("  8. SHORT-GAMMA EXPOSURE ON AFTERMATH DAYS")
    print("=" * 120)
    print("    Quant framing: an aftermath overlay would add short-vega + short-gamma exposure.")
    print("    If the account is ALREADY carrying short-gamma when overlay would fire, the marginal")
    print("    risk is concentrated rather than diversified.")
    print()
    if after_rows:
        sg_counts_full = [r.short_gamma_count for r in after_rows]
        sg_counts_recent = [r.short_gamma_count for r in after_recent]
        for label, arr in (("Full sample aftermath", sg_counts_full),
                           (f"Recent {RECENT_SLICE_START}+ aftermath", sg_counts_recent)):
            if not arr:
                continue
            mean = np.mean(arr)
            n_zero = sum(1 for c in arr if c == 0)
            n_one = sum(1 for c in arr if c == 1)
            n_two_plus = sum(1 for c in arr if c >= 2)
            print(f"    {label:<32} n={len(arr):>5}  mean_short_gamma={mean:>4.2f}  "
                  f"#0={n_zero}({n_zero/len(arr)*100:.0f}%)  "
                  f"#1={n_one}({n_one/len(arr)*100:.0f}%)  "
                  f"#≥2={n_two_plus}({n_two_plus/len(arr)*100:.0f}%)")

    # ── 9. SUMMARY (decision-grade lines) ─────────────────────────────
    print()
    print("=" * 120)
    print("  9. PHASE 1 SUMMARY (read in this order)")
    print("=" * 120)
    print("    §1 avg daily BP used   — if << 50%, idle BP is structurally large")
    print("    §3 HIGH_VOL idle median — if HIGH_VOL idle ≪ NORMAL idle, overlay must skip vol-stress")
    print("    §4 aftermath idle      — if aftermath idle ≥ non-aftermath idle, overlay has room when it fires")
    print("    §6 disaster idle       — if disaster days drop near 0% idle, margin-stress proxy is HIGH")
    print("    §7 deploy capacity     — % of aftermath days that can fund a +14% (2×) overlay")
    print("    §8 short-gamma overlap — pre-existing short-vega risk on aftermath days")


if __name__ == "__main__":
    run_study()
