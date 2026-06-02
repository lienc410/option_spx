"""Q082 P1 — Sample coverage assessment.

Enumerate historical days where current matrix would have opened BCD
(strategy_key = 'bull_call_diagonal' per the deployed selector). Group
by year + regime + IVP bucket. Identify coverage of key stress periods.

Output:
- q082_p1_bcd_days_per_year.csv  (annual count + IVP/VIX distribution)
- q082_p1_stress_period_coverage.csv  (how many BCD-eligible days in
  each named stress window)
- q082_p1_memo.md  (narrative + kill-gate verdict)
"""
from __future__ import annotations
import csv
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"
ANNUAL_OUT = ROOT / "research" / "q082" / "q082_p1_bcd_days_per_year.csv"
STRESS_OUT = ROOT / "research" / "q082" / "q082_p1_stress_period_coverage.csv"

# Named stress windows (per Q082 framing §1)
STRESS_WINDOWS = [
    ("2008_GFC",       "2007-10-01", "2009-06-30"),
    ("2018_Q4",        "2018-10-01", "2019-01-31"),
    ("2020_COVID",     "2020-02-15", "2020-05-31"),
    ("2022_rates",     "2022-01-01", "2022-12-31"),
    ("2015_aug",       "2015-08-01", "2015-10-31"),
    ("2011_summer",    "2011-07-01", "2011-10-31"),
]

# Benign-bull controls (sanity)
BENIGN_WINDOWS = [
    ("2017_low_vol",   "2017-01-01", "2017-12-31"),
    ("2021_bull",      "2021-01-01", "2021-12-31"),
    ("2024_bull",      "2024-01-01", "2024-12-31"),
]


def load_signal_history() -> list[dict]:
    rows = []
    with open(SIGNAL) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def ivp_bucket(ivp_str: str) -> str:
    try:
        ivp = float(ivp_str)
    except (TypeError, ValueError):
        return "UNK"
    if ivp < 33:
        return "LOW"
    if ivp < 67:
        return "MID"
    return "HIGH"


def main() -> None:
    rows = load_signal_history()
    print(f"Loaded {len(rows)} signal-history rows ({rows[0]['date']} → {rows[-1]['date']})")

    bcd_rows = [r for r in rows if r["strategy_key"] == "bull_call_diagonal"]
    print(f"BCD-eligible days (per current matrix): {len(bcd_rows)}")

    # Annual breakdown
    by_year: dict[int, dict] = defaultdict(lambda: {
        "n": 0,
        "ivp_LOW": 0, "ivp_MID": 0, "ivp_HIGH": 0,
        "vix_sum": 0.0, "vix_count": 0,
        "spx_first": None, "spx_last": None,
    })
    for r in bcd_rows:
        y = int(r["date"][:4])
        b = by_year[y]
        b["n"] += 1
        ib = ivp_bucket(r["ivp"])
        b[f"ivp_{ib}"] += 1
        try:
            b["vix_sum"] += float(r["vix"])
            b["vix_count"] += 1
        except (TypeError, ValueError):
            pass
        try:
            spx = float(r["spx"])
            if b["spx_first"] is None:
                b["spx_first"] = spx
            b["spx_last"] = spx
        except (TypeError, ValueError):
            pass

    annual_rows = []
    print("\nBCD-eligible days per year:")
    print(f"{'year':>4} {'n':>4} {'ivp_LOW':>8} {'ivp_MID':>8} {'ivp_HIGH':>9} {'vix_avg':>8}")
    print("-" * 50)
    for y in sorted(by_year.keys()):
        b = by_year[y]
        vix_avg = b["vix_sum"] / b["vix_count"] if b["vix_count"] else 0
        print(f"{y:>4} {b['n']:>4} {b['ivp_LOW']:>8} {b['ivp_MID']:>8} {b['ivp_HIGH']:>9} {vix_avg:>8.2f}")
        annual_rows.append({
            "year":          y,
            "n_bcd_eligible": b["n"],
            "ivp_LOW":       b["ivp_LOW"],
            "ivp_MID":       b["ivp_MID"],
            "ivp_HIGH":      b["ivp_HIGH"],
            "vix_avg":       round(vix_avg, 2),
            "spx_year_chg_pct": round(((b["spx_last"] - b["spx_first"]) / b["spx_first"] * 100), 2) if b["spx_first"] else None,
        })

    with open(ANNUAL_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(annual_rows[0].keys()))
        w.writeheader()
        w.writerows(annual_rows)
    print(f"\nwrote {ANNUAL_OUT}")

    # Stress window coverage
    print("\nStress window coverage:")
    print(f"{'window':<20} {'date range':<26} {'BCD days':>9} {'avg VIX':>8}")
    print("-" * 70)
    stress_rows = []
    for name, lo, hi in STRESS_WINDOWS + BENIGN_WINDOWS:
        sub = [r for r in bcd_rows if lo <= r["date"] <= hi]
        n = len(sub)
        vix_avg = mean(float(r["vix"]) for r in sub) if sub else 0
        print(f"{name:<20} {lo} → {hi}  {n:>9} {vix_avg:>8.2f}")
        stress_rows.append({
            "window":       name,
            "kind":         "stress" if (name, lo, hi) in STRESS_WINDOWS else "benign",
            "start":        lo,
            "end":          hi,
            "bcd_days":     n,
            "vix_avg":      round(vix_avg, 2),
        })

    with open(STRESS_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(stress_rows[0].keys()))
        w.writeheader()
        w.writerows(stress_rows)
    print(f"\nwrote {STRESS_OUT}")

    # Kill-gate verdict
    print("\n" + "=" * 60)
    print("KILL-GATE VERDICT")
    print("=" * 60)
    stress_total = sum(r["bcd_days"] for r in stress_rows if r["kind"] == "stress")
    benign_total = sum(r["bcd_days"] for r in stress_rows if r["kind"] == "benign")
    print(f"Stress windows: {stress_total} BCD-eligible days across {sum(1 for r in stress_rows if r['kind']=='stress')} named periods")
    print(f"Benign controls: {benign_total} BCD-eligible days across {sum(1 for r in stress_rows if r['kind']=='benign')} named periods")
    print(f"All BCD days: {len(bcd_rows)} (2000-2026)")
    if stress_total < 20:
        print("\n⚠ STRESS COVERAGE LOW — kill-gate may trigger")
        print("  Q082 P2-P5 may need to relax stress window definitions or accept lower CI")
    else:
        print("\n✓ Stress coverage adequate to continue P2")


if __name__ == "__main__":
    main()
