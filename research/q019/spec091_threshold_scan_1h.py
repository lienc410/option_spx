"""
SPEC-091 F2 — 1h bar threshold calibration sweep
==================================================
Question: SPEC-091 currently locks θ=0.5 inheriting from Tier 2.6.
Is 0.5 actually optimal across θ ∈ {0.3, 0.4, 0.5, 0.6, 0.7, 0.8}?

Method:
  1. Fetch 2 years of 1h VIX (Yahoo's 730-day cap)
  2. For each candidate θ, simulate stable-rule per day with NO timeout
     (so we can see natural settle distribution) AND with 90-min / 120-min /
     180-min timeouts
  3. Per-θ × per-timeout metrics:
       - stable_rate: % days reaching stable
       - median time-to-stable
       - oscillation rate
       - distribution of stable bar-index

Note on bar timestamps: Yahoo timestamps each 1h bar at its START.
So bar at 09:30 covers 09:30-10:30. close[0] is the value at 10:30 ET.
First stable check (bar i≥1) compares 10:30 close to 11:30 close,
i.e. the soonest a stable signal can fire is 11:30 ET = 120 min after open.
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

THETAS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
TIMEOUTS = [90, 120, 180, 240]   # minutes after market open (09:30 ET)


def fetch_1h_vix() -> pd.DataFrame:
    print("  Fetching 2y of 1h VIX (Yahoo cap = 730 days) …", flush=True)
    df = yf.Ticker("^VIX").history(period="2y", interval="1h")
    if df.empty:
        raise RuntimeError("Yahoo returned empty 1h VIX dataset")
    if df.index.tz is not None:
        df.index = df.index.tz_convert("America/New_York").tz_localize(None)
    df["date"] = df.index.normalize()
    df["minute_of_day"] = df.index.hour * 60 + df.index.minute
    print(f"    OK — {len(df)} bars, {df.index[0]} → {df.index[-1]}")
    print(f"    {df['date'].nunique()} trading days covered")
    # Sanity-check first-bar timestamps
    first_bar_minutes = df.groupby("date")["minute_of_day"].min()
    print(f"    First-bar minute-of-day: mode={first_bar_minutes.mode().iloc[0]}, "
          f"min={first_bar_minutes.min()}, max={first_bar_minutes.max()}")
    return df


def simulate_per_day(group: pd.DataFrame, theta: float):
    """
    Returns (stable_idx, time_to_stable_min, oscillates_next).
    stable_idx = None if never stabilises within RTH bars.
    Time-to-stable measured from 09:30 to bar close timestamp of stable bar.
    Bar close = bar start + 60 min for 1h interval.
    """
    rth = group[(group["minute_of_day"] >= 540) & (group["minute_of_day"] <= 960)]
    rth = rth.sort_index()
    if len(rth) < 2:
        return (None, None, False)

    closes = rth["Close"].values
    bar_start_min = rth["minute_of_day"].values

    stable_idx = None
    for i in range(1, len(closes)):
        if abs(closes[i] - closes[i - 1]) < theta:
            stable_idx = i
            break

    if stable_idx is None:
        return (None, None, False)

    # Bar close timestamp = bar_start + 60 min
    bar_close_min = bar_start_min[stable_idx] + 60
    time_to_stable_min = int(bar_close_min - 570)  # measured from 09:30

    osc = False
    if stable_idx + 1 < len(closes):
        if abs(closes[stable_idx + 1] - closes[stable_idx]) >= theta:
            osc = True

    return (stable_idx, time_to_stable_min, osc)


def scan(df: pd.DataFrame):
    days = df.groupby("date")
    results = {}
    for theta in THETAS:
        per_day = []
        for day, group in days:
            per_day.append(simulate_per_day(group, theta))
        results[theta] = per_day
    return results


def summarize(results: dict, n_days: int):
    print("\n" + "=" * 100)
    print("PART A — Natural settle distribution (no timeout)")
    print("=" * 100)
    print(f"\n  {'θ':>5}  {'settled':>9}  {'never':>7}  {'med_wait':>9}  {'P75_wait':>9}  "
          f"{'P90_wait':>9}  {'P99_wait':>9}  {'osc_rate':>9}")
    print(f"  {'─' * 85}")

    natural_stats = {}
    for theta, per_day in results.items():
        stable_results = [r for r in per_day if r[0] is not None]
        n_stable = len(stable_results)
        n_never = len(per_day) - n_stable
        waits = [r[1] for r in stable_results]
        oscs = [r[2] for r in stable_results]
        med = np.median(waits) if waits else None
        p75 = np.percentile(waits, 75) if waits else None
        p90 = np.percentile(waits, 90) if waits else None
        p99 = np.percentile(waits, 99) if waits else None
        osc_rate = sum(oscs) / max(n_stable, 1) * 100
        natural_stats[theta] = {
            "n_stable": n_stable,
            "n_never":  n_never,
            "waits":    waits,
            "osc_rate": osc_rate,
        }
        print(f"  {theta:>5.2f}  {n_stable:>4d}/{n_days:<3d}  {n_never:>4d}/{n_days:<3d}  "
              f"{med:>7.0f}m  {p75:>7.0f}m  {p90:>7.0f}m  {p99:>7.0f}m  {osc_rate:>7.1f}%")

    # PART B — timeout scan
    print("\n" + "=" * 100)
    print("PART B — Stable rate at different operational timeouts")
    print("=" * 100)

    print(f"\n  Timeout = % days that reach stable within timeout_min after market open")
    print(f"  Higher % = fewer fallback events.\n")

    print(f"  {'θ':>5}  " + "  ".join(f"{'T='+str(t)+'m':>9}" for t in TIMEOUTS))
    print(f"  {'─' * (5 + len(TIMEOUTS) * 11)}")

    timeout_table = {}
    for theta, per_day in results.items():
        row = []
        timeout_table[theta] = {}
        for t in TIMEOUTS:
            n_within = sum(1 for r in per_day if r[1] is not None and r[1] <= t)
            pct = n_within / n_days * 100
            timeout_table[theta][t] = pct
            row.append(f"{pct:>7.1f}%")
        print(f"  {theta:>5.2f}  " + "  ".join(row))

    return natural_stats, timeout_table


def recommend(natural_stats, timeout_table, n_days):
    """
    Decision logic:
      - Operational target: ≥85% days reach stable within 120 min (1 stable check
        period for 1h bar; matches Tier 2.6 framing).
      - Among θ meeting that, prefer one with lowest oscillation.
      - If multiple θ tie, prefer middle θ (not too tight = more timeouts;
        not too loose = noisier signal).
    """
    print("\n" + "=" * 100)
    print("RECOMMENDATION")
    print("=" * 100)

    # Target: stable rate at 120m ≥ 85%
    target_stable_rate = 85.0
    target_timeout = 120

    qualifying = [θ for θ in THETAS
                   if timeout_table[θ][target_timeout] >= target_stable_rate]
    print(f"\n  Operational target: ≥{target_stable_rate}% stable within {target_timeout} min")
    print(f"  Qualifying θ: {qualifying}")

    if not qualifying:
        # Relax to 80%
        qualifying = [θ for θ in THETAS
                       if timeout_table[θ][target_timeout] >= 80.0]
        print(f"  ⚠ Loosened to 80%: {qualifying}")

    if not qualifying:
        # Pick highest stable rate
        qualifying = [max(THETAS, key=lambda θ: timeout_table[θ][target_timeout])]
        print(f"  ⚠ Best-effort fallback: {qualifying}")

    # Among qualifying, lowest oscillation
    osc_rates = {θ: natural_stats[θ]["osc_rate"] for θ in qualifying}
    print(f"\n  Oscillation rates among qualifying:")
    for θ in qualifying:
        print(f"    θ={θ:.2f}: {osc_rates[θ]:.1f}%")

    chosen = min(qualifying, key=lambda θ: osc_rates[θ])

    # Tier 2.6 reference (θ=0.5)
    ref_stable = timeout_table[0.5][target_timeout]
    ref_osc = natural_stats[0.5]["osc_rate"]

    print(f"\n  ➤ RECOMMENDED θ = {chosen:.2f}")
    print(f"\n  Comparison vs current SPEC value θ=0.5 (inherited from Tier 2.6):")
    print(f"    θ=0.50: stable@{target_timeout}m = {ref_stable:.1f}%, osc = {ref_osc:.1f}%")
    print(f"    θ={chosen:.2f}: stable@{target_timeout}m = {timeout_table[chosen][target_timeout]:.1f}%, "
          f"osc = {osc_rates[chosen]:.1f}%")

    delta_stable = timeout_table[chosen][target_timeout] - ref_stable
    delta_osc = osc_rates[chosen] - ref_osc

    if abs(chosen - 0.5) < 1e-6:
        print(f"\n  ✅ θ=0.5 is confirmed optimal — keep SPEC-091 F2 value.")
    elif delta_stable > 5 or delta_osc < -5:
        print(f"\n  ⚠ θ={chosen:.2f} materially better ({delta_stable:+.1f}pp stable, "
              f"{delta_osc:+.1f}pp osc).")
        print(f"     Consider updating SPEC-091 F2.")
    else:
        print(f"\n  ⚪ θ={chosen:.2f} marginally better than 0.5 ({delta_stable:+.1f}pp stable, "
              f"{delta_osc:+.1f}pp osc).")
        print(f"     Difference small; θ=0.5 acceptable to keep for continuity with Tier 2.6 backtest.")

    print("\n" + "=" * 100)


def main():
    print("=" * 100)
    print("SPEC-091 F2 — 1h bar threshold calibration sweep")
    print("=" * 100)

    df = fetch_1h_vix()
    n_days = df["date"].nunique()
    results = scan(df)
    natural_stats, timeout_table = summarize(results, n_days)
    recommend(natural_stats, timeout_table, n_days)


if __name__ == "__main__":
    main()
