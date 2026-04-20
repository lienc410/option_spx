"""
VIX Peak Aftermath Study

Research question:
  After VIX peaks (e.g. 2025-04, 2026-04), but before SPX trend turns BULLISH,
  does the system systematically miss opportunities while sitting in WAIT?

Focus window definition:
  - peak_vix_10d = max(VIX) in trailing 10 trading days
  - current VIX has fallen below peak (at least 5% off the peak)
  - peak_vix_10d >= 28 (meaningful spike — covers 2020, 2022, 2025-04, 2026-04)

Within those windows, focus on wait days where trend is NOT YET BULLISH
(BEARISH or NEUTRAL). These are exactly the cells Q015/Q016 did not touch.

Outputs:
  1. Count of aftermath windows in history
  2. Classification of wait-reason:
       - HIGH_VOL route (VIX_RISING / backwardation / ivp63>=70 / other HIGH_VOL WAIT)
       - NORMAL+HIGH+BEARISH + VIX_RISING
       - NORMAL+HIGH+NEUTRAL + VIX_RISING
  3. Forward SPX returns (5d, 10d, 20d) from each wait day
  4. Compare against wait days OUTSIDE aftermath windows (baseline)
  5. Per-event summary for 2020-03, 2022-06, 2025-04, 2026-04

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.vix_peak_aftermath_study
"""

from __future__ import annotations

import numpy as np

from backtest.engine import run_signals_only
from backtest.run_bootstrap_ci import bootstrap_ci

START = "2000-01-01"
PEAK_VIX_MIN = 28.0       # only count meaningful spikes
PEAK_LOOKBACK = 10        # trading days
OFF_PEAK_MIN_PCT = 0.05   # VIX must be at least 5% below the 10d peak
FORWARD_DAYS = [5, 10, 20]


def _is_aftermath(signals: list[dict], idx: int) -> tuple[bool, float]:
    """Return (is_aftermath, peak_vix) for day at index `idx`."""
    lo = max(0, idx - PEAK_LOOKBACK)
    window = signals[lo:idx + 1]
    if not window:
        return False, 0.0
    peak = max(s["vix"] for s in window)
    if peak < PEAK_VIX_MIN:
        return False, peak
    cur = signals[idx]["vix"]
    if cur >= peak * (1 - OFF_PEAK_MIN_PCT):
        return False, peak
    return True, peak


def _is_vix_rising(signals: list[dict], idx: int) -> bool:
    """Replicate _classify_trend: today's 5d avg vs 5-days-ago 5d avg, band 5%."""
    today = signals[idx].get("vix_5d_avg")
    if today is None or idx < 5:
        return False
    prior = signals[idx - 5].get("vix_5d_avg")
    if prior is None or prior == 0:
        return False
    change = (today - prior) / prior
    return change > 0.05


def _classify_wait(s: dict, rising: bool) -> str:
    """Classify why a wait day is in WAIT."""
    regime = s["regime"]
    trend = s["trend"]
    ivs = s["iv_signal"]
    ivp63 = s.get("ivp63", 0) or 0

    if regime == "HIGH_VOL":
        if rising:
            return "HIGH_VOL+VIX_RISING"
        if trend == "BEARISH" and ivp63 >= 70:
            return "HIGH_VOL+BEARISH+IVP63>=70"
        return "HIGH_VOL+other"
    if regime == "NORMAL" and ivs == "HIGH":
        if trend == "BEARISH":
            return "NORMAL+HIGH+BEARISH+VIX_RISING" if rising else "NORMAL+HIGH+BEARISH+other"
        if trend == "NEUTRAL":
            return "NORMAL+HIGH+NEUTRAL+VIX_RISING" if rising else "NORMAL+HIGH+NEUTRAL+other"
        if trend == "BULLISH":
            return "NORMAL+HIGH+BULLISH (Q016 cell — out of scope)"
    return f"other ({regime}/{ivs}/{trend})"


def _forward_return(signals: list[dict], idx: int, days: int) -> float | None:
    j = idx + days
    if j >= len(signals):
        return None
    spx_now = signals[idx]["spx"]
    spx_fwd = signals[j]["spx"]
    if spx_now <= 0:
        return None
    return (spx_fwd - spx_now) / spx_now * 100


def _fmt_stats(arr: list[float]) -> str:
    if not arr:
        return "n=0"
    a = np.array(arr)
    n = len(a)
    mu = a.mean()
    med = np.median(a)
    pos = (a > 0).sum() / n * 100
    sd = a.std(ddof=1) if n > 1 else 0
    return f"n={n:>4}  mean={mu:+.2f}%  median={med:+.2f}%  pos={pos:>5.1f}%  sd={sd:.2f}"


def run_study():
    print("  Loading signal history 2000-01-01 ...")
    signals = run_signals_only(start_date=START)
    n_days = len(signals)
    print(f"  Total signal days: {n_days}")

    # ── Identify aftermath windows ────────────────────────────────────
    aftermath_idx: list[int] = []
    peak_by_idx: dict[int, float] = {}
    for i in range(len(signals)):
        ok, peak = _is_aftermath(signals, i)
        if ok:
            aftermath_idx.append(i)
            peak_by_idx[i] = peak

    print(f"\n  Aftermath days (VIX peak ≥ {PEAK_VIX_MIN}, now ≥5% off peak within {PEAK_LOOKBACK}d): "
          f"{len(aftermath_idx)}")

    # ── Segment into discrete windows (gap > 3 days = new window) ─────
    windows: list[list[int]] = []
    cur: list[int] = []
    last_i = -10
    for i in aftermath_idx:
        if i - last_i > 3:
            if cur:
                windows.append(cur)
            cur = [i]
        else:
            cur.append(i)
        last_i = i
    if cur:
        windows.append(cur)
    print(f"  Distinct aftermath windows: {len(windows)}")

    # ── Filter aftermath wait days where trend NOT YET BULLISH ────────
    wait_days: list[dict] = []
    for i in aftermath_idx:
        s = signals[i]
        if "Reduce" not in s["strategy"]:
            continue
        if s["trend"] == "BULLISH":
            continue  # out of scope per PM (Q015/Q016 already cover this)
        rising = _is_vix_rising(signals, i)
        wait_days.append({
            "idx": i,
            "date": s["date"],
            "vix": s["vix"],
            "peak": peak_by_idx[i],
            "regime": s["regime"],
            "trend": s["trend"],
            "iv_signal": s["iv_signal"],
            "ivp63": s.get("ivp63", 0),
            "rising": rising,
            "reason": _classify_wait(s, rising),
            "spx": s["spx"],
            "fwd5":  _forward_return(signals, i, 5),
            "fwd10": _forward_return(signals, i, 10),
            "fwd20": _forward_return(signals, i, 20),
        })
    print(f"  Aftermath wait days (trend NOT BULLISH): {len(wait_days)}")

    # ── Breakdown by wait-reason ──────────────────────────────────────
    print(f"\n{'=' * 80}")
    print(f"  BREAKDOWN BY WAIT REASON")
    print(f"{'=' * 80}")
    by_reason: dict[str, list[dict]] = {}
    for w in wait_days:
        by_reason.setdefault(w["reason"], []).append(w)
    for reason, items in sorted(by_reason.items(), key=lambda kv: -len(kv[1])):
        print(f"\n  {reason}: n={len(items)}")

    # ── Forward returns per bucket + overall ──────────────────────────
    print(f"\n{'=' * 80}")
    print(f"  FORWARD SPX RETURNS FROM AFTERMATH WAIT DAYS")
    print(f"{'=' * 80}")
    for reason, items in sorted(by_reason.items(), key=lambda kv: -len(kv[1])):
        if len(items) < 5:
            continue
        print(f"\n  {reason}  (n={len(items)})")
        for d in FORWARD_DAYS:
            vals = [w[f"fwd{d}"] for w in items if w[f"fwd{d}"] is not None]
            if not vals:
                continue
            ci = bootstrap_ci(vals)
            lo, hi = ci["ci_lo"], ci["ci_hi"]
            sig = "SIG+" if lo > 0 else ("SIG-" if hi < 0 else "n.s.")
            print(f"    fwd{d:2d}d: {_fmt_stats(vals)}  "
                  f"CI95 [{lo:+.2f}%, {hi:+.2f}%]  {sig}")

    # ── Baseline: wait days OUTSIDE aftermath, trend NOT BULLISH ──────
    print(f"\n{'=' * 80}")
    print(f"  BASELINE (non-aftermath wait days, trend not BULLISH)")
    print(f"{'=' * 80}")
    aftermath_set = set(aftermath_idx)
    baseline: list[dict] = []
    for i, s in enumerate(signals):
        if i in aftermath_set:
            continue
        if "Reduce" not in s["strategy"]:
            continue
        if s["trend"] == "BULLISH":
            continue
        baseline.append({
            "fwd5":  _forward_return(signals, i, 5),
            "fwd10": _forward_return(signals, i, 10),
            "fwd20": _forward_return(signals, i, 20),
        })
    print(f"  baseline wait days: n={len(baseline)}")
    for d in FORWARD_DAYS:
        vals = [b[f"fwd{d}"] for b in baseline if b[f"fwd{d}"] is not None]
        print(f"    fwd{d:2d}d: {_fmt_stats(vals)}")

    # ── Side-by-side: aftermath vs baseline (all-wait totals) ─────────
    print(f"\n{'=' * 80}")
    print(f"  AFTERMATH vs BASELINE (all-wait comparison)")
    print(f"{'=' * 80}")
    for d in FORWARD_DAYS:
        aft = [w[f"fwd{d}"] for w in wait_days if w[f"fwd{d}"] is not None]
        base = [b[f"fwd{d}"] for b in baseline if b[f"fwd{d}"] is not None]
        if not aft or not base:
            continue
        delta = np.mean(aft) - np.mean(base)
        print(f"  fwd{d:2d}d  aftermath_mean={np.mean(aft):+.2f}%  "
              f"baseline_mean={np.mean(base):+.2f}%  delta={delta:+.2f}%")

    # ── Callout: PM-referenced events (2020-03, 2022-06, 2025-04, 2026-04) ──
    print(f"\n{'=' * 80}")
    print(f"  PER-EVENT CALLOUTS")
    print(f"{'=' * 80}")
    targets = [
        ("2008-10 crisis",  "2008-10-01", "2008-12-31"),
        ("2011-08 downgrade","2011-08-01","2011-10-31"),
        ("2020-03 COVID",   "2020-03-15", "2020-05-31"),
        ("2022-06 cpi",     "2022-05-15", "2022-07-31"),
        ("2025-04 tariff",  "2025-04-01", "2025-05-31"),
        ("2026-04 recent",  "2026-03-15", "2026-04-30"),
    ]
    for label, lo, hi in targets:
        ev_waits = [w for w in wait_days if lo <= w["date"] <= hi]
        if not ev_waits:
            print(f"\n  {label}: no aftermath wait days in [{lo}..{hi}]")
            continue
        print(f"\n  {label}: n={len(ev_waits)} wait days in [{lo}..{hi}]")
        reasons_here = {}
        for w in ev_waits:
            reasons_here[w["reason"]] = reasons_here.get(w["reason"], 0) + 1
        for r, cnt in sorted(reasons_here.items(), key=lambda kv: -kv[1]):
            print(f"    {r}: {cnt}")
        for d in FORWARD_DAYS:
            vals = [w[f"fwd{d}"] for w in ev_waits if w[f"fwd{d}"] is not None]
            if not vals:
                continue
            print(f"    fwd{d:2d}d  mean={np.mean(vals):+.2f}%  "
                  f"median={np.median(vals):+.2f}%  pos={(np.array(vals) > 0).mean() * 100:.0f}%")

        # First few rows for flavor
        print(f"    First 5 rows:")
        print(f"      {'Date':>12} {'VIX':>5} {'Peak':>5} {'Regime':<9} "
              f"{'Trend':<8} {'IV':<7} {'Rising':<6} {'Fwd20d':>8}  Reason")
        for w in sorted(ev_waits, key=lambda x: x["date"])[:5]:
            fwd20 = f"{w['fwd20']:+.2f}%" if w['fwd20'] is not None else "—"
            print(f"      {w['date']:>12} {w['vix']:>5.1f} {w['peak']:>5.1f} "
                  f"{w['regime']:<9} {w['trend']:<8} {w['iv_signal']:<7} "
                  f"{str(w['rising']):<6} {fwd20:>8}  {w['reason']}")


if __name__ == "__main__":
    run_study()
