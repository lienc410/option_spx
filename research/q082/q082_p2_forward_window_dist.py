"""Q082 P2 — Forward-window direction distribution across 26y BCD-eligible days.

Reframed scope per P1 finding: matrix gates BCD out of named stress periods,
so testing BCD in 2008/2022/etc is moot. Real question is forward-window
direction distribution across BCD-eligible entry days.

Method:
1. Load BCD-eligible days from signal history cache (1747 days).
2. For each day, compute forward 21/34/60-day SPX return using
   yfinance SPX history (no need for option chains in this analysis).
3. Bucket: UP (>+1%), FLAT (±1%), DOWN (<-1%).
4. Compare 26y profile to Q081's 3y sample (48% up / 10% flat / 43% down).
5. Sub-bucket by IVP / VIX / year regime.

Output:
- q082_p2_forward_returns.csv (per-day forward returns)
- q082_p2_forward_dist.csv (aggregate distribution stats)
- q082_p2_memo.md (verdict V1/V2/V3 per P1 §Connection back to Q081)
"""
from __future__ import annotations
import csv
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median, stdev
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
SIGNAL = ROOT / "research" / "q078" / "_signal_history_cache.csv"
PER_DAY_OUT = ROOT / "research" / "q082" / "q082_p2_forward_returns.csv"
DIST_OUT = ROOT / "research" / "q082" / "q082_p2_forward_dist.csv"


def load_signal_history() -> list[dict]:
    rows = []
    with open(SIGNAL) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def fetch_spx_history() -> dict[str, float]:
    """Pull SPX close from earliest BCD-eligible date through today via yfinance."""
    import yfinance as yf
    df = yf.Ticker("^GSPC").history(start="2003-01-01", end="2026-06-15", auto_adjust=True)
    return {ts.date().isoformat(): float(row["Close"]) for ts, row in df.iterrows()}


def find_forward_close(hist: dict[str, float], anchor: str, days_forward: int,
                        max_lookforward: int = 10) -> tuple[str, float] | None:
    d = date.fromisoformat(anchor) + timedelta(days=days_forward)
    for _ in range(max_lookforward):
        iso = d.isoformat()
        if iso in hist:
            return iso, hist[iso]
        d += timedelta(days=1)
    return None


def percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


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


def direction_bucket(ret: float | None) -> str:
    if ret is None:
        return "MISSING"
    if ret > 0.01:
        return "UP"
    if ret < -0.01:
        return "DOWN"
    return "FLAT"


def main() -> None:
    rows = load_signal_history()
    bcd_days = [r for r in rows if r["strategy_key"] == "bull_call_diagonal"]
    print(f"BCD-eligible days: {len(bcd_days)}")

    print("Fetching SPX history...")
    spx_hist = fetch_spx_history()
    print(f"SPX history rows: {len(spx_hist)}")

    enriched = []
    missed = 0
    for r in bcd_days:
        anchor_iso = r["date"]
        # Anchor close (the BCD-eligible day's close)
        anchor_lookup = find_forward_close(spx_hist, anchor_iso, 0, max_lookforward=5)
        if anchor_lookup is None:
            missed += 1
            continue
        anchor_close = anchor_lookup[1]
        result = {
            "date":       anchor_iso,
            "ivp":        ivp_bucket(r["ivp"]),
            "vix":        float(r["vix"]) if r["vix"] else None,
            "trend":      r["trend"],
            "anchor_spx": round(anchor_close, 2),
        }
        for h in (21, 34, 60):
            fwd = find_forward_close(spx_hist, anchor_iso, h)
            if fwd is None:
                result[f"fwd_{h}d_ret"] = None
                result[f"fwd_{h}d_dir"] = "MISSING"
            else:
                ret = (fwd[1] - anchor_close) / anchor_close
                result[f"fwd_{h}d_ret"] = round(ret, 4)
                result[f"fwd_{h}d_dir"] = direction_bucket(ret)
        enriched.append(result)

    print(f"Enriched: {len(enriched)} (missed {missed} due to SPX data gaps)")

    with open(PER_DAY_OUT, "w", newline="") as f:
        fieldnames = ["date", "ivp", "vix", "trend", "anchor_spx",
                      "fwd_21d_ret", "fwd_21d_dir",
                      "fwd_34d_ret", "fwd_34d_dir",
                      "fwd_60d_ret", "fwd_60d_dir"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(enriched)
    print(f"wrote {PER_DAY_OUT}")

    # Aggregate distribution
    print()
    print("=" * 88)
    print("DIRECTION DISTRIBUTION ACROSS 26Y BCD-ELIGIBLE DAYS")
    print("=" * 88)
    dist_rows = []
    for h in (21, 34, 60):
        valid = [r for r in enriched if r[f"fwd_{h}d_ret"] is not None]
        n = len(valid)
        rets = [r[f"fwd_{h}d_ret"] for r in valid]
        dirs = [r[f"fwd_{h}d_dir"] for r in valid]
        up = sum(1 for d in dirs if d == "UP")
        flat = sum(1 for d in dirs if d == "FLAT")
        down = sum(1 for d in dirs if d == "DOWN")
        dist_rows.append({
            "horizon_days": h,
            "n":            n,
            "pct_up":       round(100 * up / n, 1),
            "pct_flat":     round(100 * flat / n, 1),
            "pct_down":     round(100 * down / n, 1),
            "mean_ret":     round(mean(rets), 4),
            "median_ret":   round(median(rets), 4),
            "std_ret":      round(stdev(rets), 4) if n > 1 else None,
            "p05_ret":      round(percentile(rets, 5), 4),
            "p95_ret":      round(percentile(rets, 95), 4),
            "min_ret":      round(min(rets), 4),
            "max_ret":      round(max(rets), 4),
        })
        print(f"forward {h:>2}d: n={n}  UP={up} ({100*up/n:.1f}%)  "
              f"FLAT={flat} ({100*flat/n:.1f}%)  DOWN={down} ({100*down/n:.1f}%)  "
              f"mean={mean(rets):+.2%}  p05={percentile(rets,5):+.2%}")

    with open(DIST_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dist_rows[0].keys()))
        w.writeheader()
        w.writerows(dist_rows)
    print(f"wrote {DIST_OUT}")

    # Q081 3y comparison (34d horizon — Q081 median hold was 34 days)
    print()
    print("=" * 88)
    print("COMPARISON: 26Y BASELINE vs Q081 3Y SAMPLE")
    print("=" * 88)
    print(f"{'sample':<22} {'n':>4} {'%UP':>7} {'%FLAT':>7} {'%DOWN':>7} {'mean':>9} {'p05':>9}")
    print("-" * 76)
    row34 = next(r for r in dist_rows if r["horizon_days"] == 34)
    print(f"{'26y baseline (34d fwd)':<22} {row34['n']:>4} "
          f"{row34['pct_up']:>6.1f}% {row34['pct_flat']:>6.1f}% {row34['pct_down']:>6.1f}% "
          f"{row34['mean_ret']:>+9.2%} {row34['p05_ret']:>+9.2%}")
    # Q081 actual 21-trade matched-window comparison from prior research
    print(f"{'Q081 3y sample':<22}    21   47.6%    9.5%   42.9%    +0.52%    -3.56%")

    # Verdict
    verdict = ""
    diff_up = row34["pct_up"] - 47.6
    diff_down = row34["pct_down"] - 42.9
    if diff_up > 5:
        verdict = "V1 — 26y is MORE up-biased than Q081 3y → B-1 stronger than implied"
    elif diff_up < -5:
        verdict = "V3 — 26y is MORE down-biased than Q081 3y → B-1's residual risk real"
    else:
        verdict = "V2 — 26y matches Q081 3y within noise → B-1 holds as-is"

    print(f"\nVerdict: {verdict}")
    print(f"  Δ%up   = {diff_up:+.1f}pp")
    print(f"  Δ%down = {diff_down:+.1f}pp")


if __name__ == "__main__":
    main()
