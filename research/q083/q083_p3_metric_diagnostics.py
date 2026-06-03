"""Q083 P3 — Direct metric diagnostics (per G1 §4.A demand).

Replaces the model-driven P3 with FACT-DRIVEN measurements:

A1. IVP252 lag after spike: how many trading days does IVP252 take to
    "recover" (reflect current VIX state) after a spike event? Compare
    against IVP63 and IVP126 same-event response.

A2. Gate pass rate by VIX bucket: in each VIX bucket [<13/13-15/15-17/...],
    what fraction of historical NORMAL × BULLISH days passed the IVP gate?
    Tests PM's claim that "normal VIX (15-22) days almost never pass".

These are pure observations on historical data, no counterfactual PnL
needed. Independent of any IVP-derived stratification (avoids circular
validation, per memory feedback_circular_metric_validation).
"""
from __future__ import annotations
import csv
import math
from datetime import date, timedelta
from pathlib import Path
from collections import defaultdict
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"
LAG_OUT = ROOT / "research" / "q083" / "q083_p3a1_lag_per_spike.csv"
PASS_OUT = ROOT / "research" / "q083" / "q083_p3a2_pass_rate_by_vix.csv"


def load_signal_rows() -> list[dict]:
    rows = []
    with open(SIGNAL) as f:
        for r in csv.DictReader(f):
            try:
                vix = float(r["vix"])
                ivp = float(r["ivp"]) if r["ivp"] else None
                ivp63 = float(r["ivp63"]) if r["ivp63"] else None
                rows.append({
                    "date":      r["date"],
                    "vix":       vix,
                    "ivp":       ivp,
                    "ivp63":     ivp63,
                    "ivr":       float(r["ivr"]) if r["ivr"] else None,
                    "iv_signal": r["iv_signal"],
                    "regime":    r["regime"],
                    "trend":     r["trend"],
                    "strategy":  r["strategy_key"],
                })
            except (ValueError, TypeError):
                continue
    return rows


# ===========================================================================
# A1 — IVP252 lag after VIX spikes
# ===========================================================================

def identify_spikes(rows: list[dict], peak_threshold: float = 25.0,
                    min_separation_days: int = 60) -> list[int]:
    """Identify VIX spike events (local peaks above threshold).

    A "spike" is a day where VIX peaks (> all neighbors within ±5 trading days)
    AND VIX > peak_threshold AND no prior spike within min_separation_days.
    Returns list of row indices.
    """
    spike_indices = []
    n = len(rows)
    last_spike = -10000
    for i in range(5, n - 5):
        v = rows[i]["vix"]
        if v < peak_threshold:
            continue
        if i - last_spike < min_separation_days:
            continue
        # Check local peak
        window = [rows[i+offset]["vix"] for offset in range(-5, 6)]
        if v == max(window) and v == window[5]:  # center of window is max
            spike_indices.append(i)
            last_spike = i
    return spike_indices


def measure_lag(rows: list[dict], spike_indices: list[int],
                lookahead_days: int = 252) -> list[dict]:
    """For each spike, measure IVP252 vs IVP63 trajectories post-peak."""
    out = []
    for sp_idx in spike_indices:
        spike_date = rows[sp_idx]["date"]
        spike_vix = rows[sp_idx]["vix"]
        # Recovery proxy: define current VIX state as 30d trailing avg
        # IVP252 "recovers" when its reading approaches IVP63's reading
        # (i.e., when the stale spike data no longer dominates 252d window)
        # Operationally: find first day post-peak where |IVP252 - IVP63| < 10
        recovery_day_252 = None
        recovery_day_126 = None
        for offset in range(20, min(lookahead_days, len(rows) - sp_idx - 1)):
            r = rows[sp_idx + offset]
            if r["ivp"] is None or r["ivp63"] is None:
                continue
            diff = r["ivp"] - r["ivp63"]
            if recovery_day_252 is None and abs(diff) < 10:
                recovery_day_252 = offset
            # Also track when IVP252 itself drops to "normal" (<50)
            if r["ivp"] < 50 and recovery_day_126 is None:
                recovery_day_126 = offset
        out.append({
            "spike_date":   spike_date,
            "spike_vix":    round(spike_vix, 2),
            "recovery_day_ivp252_vs_ivp63": recovery_day_252,
            "recovery_day_ivp_below_50":   recovery_day_126,
        })
    return out


# ===========================================================================
# A2 — Gate pass rate by VIX bucket
# ===========================================================================

# IVP gate thresholds
def passes_gate(iv_signal: str, ivp: float) -> bool:
    """Current selector gate logic for NORMAL × BULL routing."""
    if iv_signal not in ("HIGH", "NEUTRAL"):
        return False
    if iv_signal == "NEUTRAL":
        return 43 <= ivp <= 55
    return 40 < ivp <= 70  # HIGH


def compute_pass_rate_by_vix(rows: list[dict]) -> list[dict]:
    """Per-VIX-bucket pass rate over NORMAL × BULLISH days."""
    # VIX buckets covering NORMAL regime
    buckets = [(13, 14), (14, 15), (15, 16), (16, 17), (17, 18),
               (18, 19), (19, 20), (20, 21), (21, 22)]
    out = []
    for lo, hi in buckets:
        sub = [r for r in rows if r["regime"] == "NORMAL"
               and r["trend"] == "BULLISH"
               and lo <= r["vix"] < hi
               and r["ivp"] is not None]
        n = len(sub)
        if n == 0:
            continue
        passes = sum(1 for r in sub if passes_gate(r["iv_signal"], r["ivp"]))
        actual = sum(1 for r in sub if r["strategy"] in ("bull_put_spread",))
        out.append({
            "vix_bucket":   f"[{lo}, {hi})",
            "n_days":       n,
            "gate_pass":    passes,
            "gate_pass_pct": round(100 * passes / n, 1),
            "actual_bps_open": actual,
            "actual_pct":   round(100 * actual / n, 1),
        })
    return out


# ===========================================================================
# A3 — Spike-day proximity vs IVP252 reading (heatmap-style)
# ===========================================================================

def days_since_last_high_vix(rows: list[dict], high_threshold: float = 25.0) -> list[dict]:
    """For each NORMAL × BULL day, count days since last VIX > threshold.
    Cross-tab with IVP252 reading to show how spike contamination propagates.
    """
    out = []
    last_high_idx = None
    for i, r in enumerate(rows):
        if r["vix"] >= high_threshold:
            last_high_idx = i
        if r["regime"] == "NORMAL" and r["trend"] == "BULLISH" and r["ivp"] is not None:
            days_since = (i - last_high_idx) if last_high_idx is not None else 9999
            out.append({
                "date":         r["date"],
                "vix":          r["vix"],
                "ivp252":       r["ivp"],
                "ivp63":        r["ivp63"],
                "days_since_high": days_since,
            })
    return out


def main():
    print("Loading signal history...")
    rows = load_signal_rows()
    print(f"  rows: {len(rows)} ({rows[0]['date']} → {rows[-1]['date']})")

    # ---------- A1: lag measurement ----------
    print()
    print("=" * 80)
    print("A1 — IVP252 lag after VIX spikes (peak threshold VIX > 25)")
    print("=" * 80)
    spikes = identify_spikes(rows, peak_threshold=25.0, min_separation_days=60)
    print(f"  Identified {len(spikes)} spike events with peak VIX > 25")
    lag_data = measure_lag(rows, spikes)
    with open(LAG_OUT, "w", newline="") as f:
        if lag_data:
            w = csv.DictWriter(f, fieldnames=list(lag_data[0].keys()))
            w.writeheader()
            w.writerows(lag_data)
    print(f"  wrote {LAG_OUT}")
    print()
    print("Top 20 spikes by VIX peak:")
    print(f"{'spike_date':<12} {'peak_vix':>8} {'IVP252→IVP63 align':>22} {'IVP252→<50':>13}")
    for d in sorted(lag_data, key=lambda x: -x["spike_vix"])[:20]:
        rec1 = d["recovery_day_ivp252_vs_ivp63"]
        rec2 = d["recovery_day_ivp_below_50"]
        rec1_s = f"{rec1} days" if rec1 is not None else "not reached"
        rec2_s = f"{rec2} days" if rec2 is not None else "not reached"
        print(f"{d['spike_date']:<12} {d['spike_vix']:>8.2f} {rec1_s:>22} {rec2_s:>13}")
    print()
    # Summary
    valid = [d["recovery_day_ivp252_vs_ivp63"] for d in lag_data
             if d["recovery_day_ivp252_vs_ivp63"] is not None]
    if valid:
        print(f"Median lag (IVP252 → IVP63 alignment): {int(median(valid))} trading days "
              f"= ~{median(valid)/21:.1f} months")
        print(f"Mean lag:   {mean(valid):.0f} trading days = ~{mean(valid)/21:.1f} months")
        print(f"Max lag:    {max(valid)} trading days = ~{max(valid)/21:.1f} months")
        print(f"  (n={len(valid)} spikes had measurable recovery; "
              f"{len(lag_data)-len(valid)} didn't recover in 252d lookahead)")

    # ---------- A2: pass rate by VIX bucket ----------
    print()
    print("=" * 80)
    print("A2 — Gate pass rate by VIX bucket (NORMAL × BULLISH days)")
    print("=" * 80)
    pass_data = compute_pass_rate_by_vix(rows)
    with open(PASS_OUT, "w", newline="") as f:
        if pass_data:
            w = csv.DictWriter(f, fieldnames=list(pass_data[0].keys()))
            w.writeheader()
            w.writerows(pass_data)
    print(f"  wrote {PASS_OUT}")
    print()
    print(f"{'VIX bucket':<12} {'n':>5} {'gate pass':>11} {'pass %':>8} {'actual BPS':>11} {'actual %':>9}")
    print("-" * 70)
    for d in pass_data:
        print(f"{d['vix_bucket']:<12} {d['n_days']:>5} {d['gate_pass']:>11} "
              f"{d['gate_pass_pct']:>7.1f}% {d['actual_bps_open']:>11} {d['actual_pct']:>8.1f}%")

    # ---------- A3: spike contamination proximity ----------
    print()
    print("=" * 80)
    print("A3 — IVP252 vs days-since-last-VIX-high (contamination decay)")
    print("=" * 80)
    proximity_data = days_since_last_high_vix(rows, high_threshold=25.0)
    # Bucket by days_since
    buckets = [(0, 30), (30, 60), (60, 90), (90, 126), (126, 180),
               (180, 252), (252, 365), (365, 9999)]
    for lo, hi in buckets:
        sub = [r for r in proximity_data if lo <= r["days_since_high"] < hi]
        if not sub:
            continue
        ivp252_med = median(r["ivp252"] for r in sub)
        ivp63_vals = [r["ivp63"] for r in sub if r["ivp63"] is not None]
        ivp63_med = median(ivp63_vals) if ivp63_vals else None
        gate_pass = sum(1 for r in sub if r["ivp252"] is not None
                        and 43 <= r["ivp252"] <= 70)
        gate_pct = 100 * gate_pass / len(sub)
        diff = (ivp252_med - ivp63_med) if ivp63_med is not None else None
        diff_s = f"{diff:+.1f}" if diff is not None else "n/a"
        print(f"  Days since last VIX≥25: [{lo:>4},{hi:>5}) "
              f"n={len(sub):>4} IVP252_med={ivp252_med:>5.1f} "
              f"IVP63_med={ivp63_med or 0:>5.1f} "
              f"Δ(252-63)={diff_s:>6} pass_rate={gate_pct:>5.1f}%")


if __name__ == "__main__":
    main()
