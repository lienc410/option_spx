"""Q083 P0 — Baseline gate-state mapping across 26y.

For each NORMAL × BULLISH trading day in 2000-2026:
  Gate A: IVR cell-routing (iv_signal in {HIGH, NEUTRAL} = OPEN cell, LOW = reduce_wait cell)
  Gate B: IVP filter (40-70 general; 43-55 stricter NNB for NEUTRAL × BULL cell)

Classify into:
  (a) IVR-blocked AND IVP-would-block-too  (double-blocked, gate question moot)
  (b) IVR-blocked AND IVP-would-allow      (cell-routing-only blocks — IVR over-restrictive?)
  (c) IVR-allows  AND IVP-blocks           (gate-only blocks — IVP over-restrictive?)
  (d) IVR-allows  AND IVP-allows           (BPS opens in practice — baseline tradable)

Kill-gate: if state (b)+(c) < 10% of total NORMAL × BULLISH days, dual-gating
is rarely binding → likely H1, low ROI for further phases.

Inputs: research/q078/_signal_history_cache.csv
Outputs:
  q083_p0_state_counts.csv (per-year breakdown)
  q083_p0_state_assignments.csv (per-day classification for downstream P1)
  q083_p0_memo.md (separate)
"""
from __future__ import annotations
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"
COUNTS_OUT = ROOT / "research" / "q083" / "q083_p0_state_counts.csv"
ASSIGN_OUT = ROOT / "research" / "q083" / "q083_p0_state_assignments.csv"

# Gate thresholds (from strategy/selector.py lines 181-211)
IVP_LOW_THRESHOLD   = 40.0   # general; below = reduce_wait
IVP_HIGH_THRESHOLD  = 70.0   # general; above = reduce_wait
BPS_NNB_IVP_LOWER   = 43.0   # NEUTRAL × BULL cell specific
BPS_NNB_IVP_UPPER   = 55.0   # NEUTRAL × BULL cell specific


def gate_a_allows_open(iv_signal: str) -> bool:
    """Cell-routing gate (IVR-derived iv_signal). NORMAL × HIGH/NEUTRAL = BPS open."""
    return iv_signal in ("HIGH", "NEUTRAL")


def gate_b_allows_open(iv_signal: str, ivp: float) -> bool:
    """IVP-filter gate. Different threshold per cell.

    NORMAL × HIGH × BULL → BPS, gated by general IVP 40-70.
    NORMAL × NEUTRAL × BULL → BPS, gated by stricter NNB 43-55.
    NORMAL × LOW (cell-blocked already; gate-check is hypothetical).

    For state (b), we hypothetically ask: if we IGNORED cell-routing, would
    the IVP gate alone allow open? Use general 40-70 band since we don't
    know which cell the trade would target.
    """
    if iv_signal == "NEUTRAL":
        return BPS_NNB_IVP_LOWER <= ivp <= BPS_NNB_IVP_UPPER
    if iv_signal == "HIGH":
        return IVP_LOW_THRESHOLD < ivp <= IVP_HIGH_THRESHOLD
    # iv_signal LOW: hypothetical — assume general gate
    return IVP_LOW_THRESHOLD < ivp <= IVP_HIGH_THRESHOLD


def classify(iv_signal: str, ivp: float) -> str:
    a_ok = gate_a_allows_open(iv_signal)
    b_ok = gate_b_allows_open(iv_signal, ivp)
    if a_ok and b_ok:
        return "d_open"
    if a_ok and not b_ok:
        return "c_ivp_blocks"
    if not a_ok and b_ok:
        return "b_ivr_only_blocks"
    return "a_double_blocked"


def main():
    rows = []
    with open(SIGNAL) as f:
        for r in csv.DictReader(f):
            rows.append(r)

    # Restrict to NORMAL × BULLISH (Q083 scope per framing §5)
    universe = [r for r in rows
                if r["regime"] == "NORMAL"
                and r["trend"] == "BULLISH"]
    print(f"Total rows 2000-2026: {len(rows)}")
    print(f"NORMAL × BULLISH universe (Q083 scope): {len(universe)}")

    # Classify each day
    assignments = []
    state_totals = defaultdict(int)
    by_year = defaultdict(lambda: defaultdict(int))
    for r in universe:
        try:
            ivp = float(r["ivp"])
        except (TypeError, ValueError):
            continue
        iv_signal = r["iv_signal"]
        state = classify(iv_signal, ivp)
        assignments.append({
            "date":       r["date"],
            "year":       r["date"][:4],
            "vix":        r["vix"],
            "ivr":        r["ivr"],
            "ivp":        r["ivp"],
            "iv_signal":  iv_signal,
            "trend":      r["trend"],
            "regime":     r["regime"],
            "strategy_key_actual": r["strategy_key"],
            "state":      state,
        })
        state_totals[state] += 1
        by_year[r["date"][:4]][state] += 1

    # Write per-day assignments
    with open(ASSIGN_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(assignments[0].keys()))
        w.writeheader()
        w.writerows(assignments)
    print(f"\nwrote {ASSIGN_OUT}")

    # Summary
    total = sum(state_totals.values())
    print()
    print("=" * 78)
    print(f"State distribution across 26y NORMAL × BULLISH days (n={total})")
    print("=" * 78)
    state_labels = {
        "a_double_blocked":   "(a) IVR-blocks AND IVP-also-blocks  [double-blocked]",
        "b_ivr_only_blocks":  "(b) IVR-blocks but IVP-would-allow  [cell-routing alone]",
        "c_ivp_blocks":       "(c) IVR-allows but IVP-blocks       [** disputed zone **]",
        "d_open":             "(d) Both gates allow → BPS opens    [tradable baseline]",
    }
    for k in ("a_double_blocked", "b_ivr_only_blocks", "c_ivp_blocks", "d_open"):
        n = state_totals[k]
        pct = 100 * n / total if total else 0
        print(f"  {state_labels[k]:<55} n={n:>5}  {pct:>5.1f}%")
    print()

    # Per-year breakdown
    yearly_rows = []
    print("Per-year breakdown:")
    print(f"{'year':<6} {'(a) DB':>7} {'(b) IVR':>8} {'(c) IVP':>8} {'(d) OPEN':>9} {'total':>6}  {'(b)+(c) %':>10}")
    for yr in sorted(by_year):
        s = by_year[yr]
        t = sum(s.values())
        if t == 0:
            continue
        bc_pct = 100 * (s.get("b_ivr_only_blocks", 0) + s.get("c_ivp_blocks", 0)) / t
        yearly_rows.append({
            "year":       yr,
            "a_double":   s.get("a_double_blocked", 0),
            "b_ivr":      s.get("b_ivr_only_blocks", 0),
            "c_ivp":      s.get("c_ivp_blocks", 0),
            "d_open":     s.get("d_open", 0),
            "total":      t,
            "bc_share":   round(bc_pct, 1),
        })
        print(f"{yr:<6} {s.get('a_double_blocked',0):>7} {s.get('b_ivr_only_blocks',0):>8} "
              f"{s.get('c_ivp_blocks',0):>8} {s.get('d_open',0):>9} {t:>6}  {bc_pct:>9.1f}%")

    with open(COUNTS_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(yearly_rows[0].keys()))
        w.writeheader()
        w.writerows(yearly_rows)
    print(f"\nwrote {COUNTS_OUT}")

    # Kill-gate evaluation
    bc_total = state_totals["b_ivr_only_blocks"] + state_totals["c_ivp_blocks"]
    bc_share = 100 * bc_total / total if total else 0
    print()
    print("=" * 78)
    print("KILL-GATE EVALUATION")
    print("=" * 78)
    print(f"State (b)+(c) total: {bc_total}/{total} = {bc_share:.1f}%")
    print(f"Threshold for kill: < 10%")
    print()
    if bc_share < 10:
        print("→ KILL-GATE TRIGGERED: dual-gating rarely binds.")
        print("  Likely H1; further phases low ROI.")
        print("  Q083 verdict: matrix unchanged, document reduce_wait stretches as designed.")
    elif bc_share < 25:
        print("→ MARGINAL: (b)+(c) is 10-25% of NORMAL+BULLISH days.")
        print("  Continue to P1 but expect modest verdict.")
    else:
        print("→ MATERIAL: (b)+(c) ≥ 25% of NORMAL+BULLISH days.")
        print("  PM operational complaint quantified — strong case for P1 counterfactual.")

    # Also break down which gate fires more
    c_share = 100 * state_totals["c_ivp_blocks"] / total
    b_share = 100 * state_totals["b_ivr_only_blocks"] / total
    print()
    print(f"  State (b) IVR-only blocks: {b_share:.1f}% → IVR cell-routing alone responsible")
    print(f"  State (c) IVP-only blocks: {c_share:.1f}% → IVP gate alone responsible")
    print(f"  State (a) both block:      {100*state_totals['a_double_blocked']/total:.1f}% → can't separate")
    print(f"  State (d) both allow:      {100*state_totals['d_open']/total:.1f}% → BPS tradable")


if __name__ == "__main__":
    main()
