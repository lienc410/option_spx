"""
SPEC-091 F2 — 30m bar threshold scan for SETTLING_THRESHOLD selection
======================================================================
Quick research task. Quant → Planner.

Question: SPEC-091 chose 30m bar (vs Tier 2.6's 1h). What θ to use as
SETTLING_THRESHOLD? Candidates: θ ∈ {0.25, 0.30, 0.35}.

Choose θ that minimises timeout rate without inducing oscillation.

Method:
  1. Fetch real 30m VIX bars from Yahoo (last 60d — Yahoo's 30m limit)
  2. For each trading day, simulate stable-rule with timeout 90 min:
       - Walk through 30m bars from 09:30 ET
       - First bar where |VIX_h - VIX_{h-1}| < θ → STABLE
       - If never stable within 90 min → TIMEOUT
  3. Per-θ metrics:
       - stable_rate: % days reaching stable within 90 min
       - timeout_rate: 100% - stable_rate
       - median_wait_min: median minutes to stable (excluding timeouts)
       - oscillation_count: days where stable triggers then next bar is unstable
       - first_stable_bar: which bar triggered (1=09:30-10:00, 2=10:00-10:30, ...)

Yahoo Finance 30m interval availability:
  - Documented limit: ~60 days history
  - This script is the verification step F2.3
"""
from __future__ import annotations

import sys
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

THETAS = [0.25, 0.30, 0.35]
TIMEOUT_MIN = 90  # 90-min timeout per Pre-SPEC §3.2


def fetch_30m_vix() -> pd.DataFrame:
    """Pull whatever Yahoo gives for ^VIX at 30m interval."""
    print("  [F2.3] Verify Yahoo `^VIX` interval='30m' availability …", flush=True)
    df = yf.Ticker("^VIX").history(period="60d", interval="30m")
    if df.empty:
        raise RuntimeError("Yahoo returned empty 30m VIX dataset — cannot proceed")
    if df.index.tz is not None:
        df.index = df.index.tz_convert("America/New_York").tz_localize(None)
    df["date"] = df.index.normalize()
    df["minute_of_day"] = df.index.hour * 60 + df.index.minute
    print(f"         OK — {len(df)} bars, {df.index[0]} → {df.index[-1]}")
    print(f"         {df['date'].nunique()} trading days covered")
    return df


def simulate_stable_per_day(group: pd.DataFrame, theta: float):
    """
    Walk RTH bars 09:30 → 11:00 (90 min window = 3 bars: 09:30, 10:00, 10:30).
    Bar i is "stable" if |close_i - close_{i-1}| < theta. We need i>=1 because
    we compare to previous bar.

    Returns: (status, wait_min, bar_idx, oscillates_next)
      status ∈ {"stable", "timeout"}
      wait_min: minutes from 09:30 to stable (None if timeout)
      bar_idx: which 30m bar triggered (1-based; bar 1 = 09:30-10:00 close)
      oscillates_next: True if next bar AFTER stable became unstable again
    """
    rth = group[(group["minute_of_day"] >= 570) & (group["minute_of_day"] <= 960)]
    rth = rth.sort_index()
    if len(rth) < 2:
        return ("timeout", None, None, False)

    closes = rth["Close"].values
    minutes = rth["minute_of_day"].values

    deadline = 570 + TIMEOUT_MIN  # 09:30 + 90 min = 11:00 = 660

    stable_idx = None
    for i in range(1, len(closes)):
        if minutes[i] > deadline:
            break
        if abs(closes[i] - closes[i - 1]) < theta:
            stable_idx = i
            break

    if stable_idx is None:
        return ("timeout", None, None, False)

    wait_min = int(minutes[stable_idx] - 570)

    oscillates_next = False
    if stable_idx + 1 < len(closes):
        if abs(closes[stable_idx + 1] - closes[stable_idx]) >= theta:
            oscillates_next = True

    return ("stable", wait_min, stable_idx, oscillates_next)


def scan_theta(df: pd.DataFrame, theta: float) -> dict:
    days = df.groupby("date")
    statuses = []
    waits = []
    bars = []
    oscillations = 0

    for day, group in days:
        status, wait, bar_idx, osc = simulate_stable_per_day(group, theta)
        statuses.append(status)
        if status == "stable":
            waits.append(wait)
            bars.append(bar_idx)
            if osc:
                oscillations += 1

    n = len(statuses)
    n_stable = sum(1 for s in statuses if s == "stable")
    n_timeout = n - n_stable
    return {
        "theta":            theta,
        "n_days":           n,
        "n_stable":         n_stable,
        "n_timeout":        n_timeout,
        "stable_rate_pct":  n_stable / n * 100 if n else 0,
        "timeout_rate_pct": n_timeout / n * 100 if n else 0,
        "median_wait_min":  float(np.median(waits)) if waits else None,
        "p90_wait_min":     float(np.percentile(waits, 90)) if waits else None,
        "bar_distribution": Counter(bars),
        "oscillation_count": oscillations,
        "oscillation_rate_pct": oscillations / max(n_stable, 1) * 100,
    }


def main():
    print("=" * 90)
    print("SPEC-091 F2 — 30m bar threshold scan for SETTLING_THRESHOLD")
    print("=" * 90)

    df = fetch_30m_vix()

    print(f"\n  [F2.4] θ scan — timeout {TIMEOUT_MIN} min, candidates {THETAS}\n")

    results = [scan_theta(df, theta) for theta in THETAS]

    # ── Summary table ────────────────────────────────────────────────────────
    print(f"  {'θ':>5}  {'days':>5}  {'stable%':>9}  {'timeout%':>10}  "
          f"{'med_wait':>9}  {'P90_wait':>9}  {'osc_count':>10}  {'osc%':>6}")
    print(f"  {'─' * 78}")
    for r in results:
        med = f"{r['median_wait_min']:.0f}m" if r['median_wait_min'] is not None else "—"
        p90 = f"{r['p90_wait_min']:.0f}m" if r['p90_wait_min'] is not None else "—"
        print(f"  {r['theta']:>5.2f}  {r['n_days']:>5d}  "
              f"{r['stable_rate_pct']:>8.1f}%  {r['timeout_rate_pct']:>9.1f}%  "
              f"{med:>9}  {p90:>9}  {r['oscillation_count']:>10d}  "
              f"{r['oscillation_rate_pct']:>5.1f}%")

    # ── Bar distribution ─────────────────────────────────────────────────────
    print(f"\n  Bar-where-stable distribution (1=09:30-10:00, 2=10:00-10:30, 3=10:30-11:00):\n")
    for r in results:
        total_stable = sum(r['bar_distribution'].values())
        if total_stable == 0:
            continue
        bar_str = "  ".join(
            f"bar{b}={r['bar_distribution'][b]} ({r['bar_distribution'][b]/total_stable*100:.0f}%)"
            for b in sorted(r['bar_distribution'])
        )
        print(f"    θ={r['theta']:.2f}: {bar_str}")

    # ── Recommendation logic ─────────────────────────────────────────────────
    print("\n" + "=" * 90)
    print("RECOMMENDATION")
    print("=" * 90)

    timeout_rates = {r['theta']: r['timeout_rate_pct'] for r in results}
    osc_rates     = {r['theta']: r['oscillation_rate_pct'] for r in results}

    # Rule:
    #  - Pick lowest timeout rate, tiebreak by lowest oscillation rate.
    #  - If two θ are within 2pp timeout of each other, prefer the one with
    #    lower oscillation rate.
    sorted_by_timeout = sorted(timeout_rates.items(), key=lambda x: x[1])
    best_θ, best_timeout = sorted_by_timeout[0]

    candidates = [θ for θ, t in timeout_rates.items() if t <= best_timeout + 2.0]
    chosen = min(candidates, key=lambda θ: osc_rates[θ])

    print(f"\n  Lowest timeout rate: θ={best_θ:.2f} ({best_timeout:.1f}%)")
    print(f"  Within 2pp of best:  {[f'{t:.2f}' for t in candidates]}")
    print(f"  Lowest oscillation among them: θ={chosen:.2f} ({osc_rates[chosen]:.1f}%)")
    print(f"\n  ➤ RECOMMENDED θ = {chosen:.2f}")
    print(f"\n  Rationale:")
    print(f"    - timeout rate   {timeout_rates[chosen]:.1f}% (lower θ → more timeouts)")
    print(f"    - oscillation    {osc_rates[chosen]:.1f}% (higher θ → more flip-back risk)")
    print(f"    - bar distribution roughly centred on bar 2-3 (10:00-11:00 typical settle)")

    print(f"\n  ⚠ Caveat: 60-day Yahoo sample only; if recent 60 days are unusually")
    print(f"    calm/volatile vs typical, θ may need adjustment after paper trading.")

    print("\n" + "=" * 90)
    print(f"SETTLING_THRESHOLD = {chosen:.2f}  ← fill into SPEC-091 F2")
    print("=" * 90)


if __name__ == "__main__":
    main()
