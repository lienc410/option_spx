"""Q081 P3 — Per-trade matched-window comparison: BCD vs QQQ vs SPX.

Per G-review 1 (2026-06-01):
- §A thesis recentering: crowd-out non-issue, verdict narrowed to single-
  trade cash efficiency + qualitative routing + sizing.
- §B match each of 21 BCD hold windows to QQQ same-window period return.
- §C direction-bias control panel: SPX/QQQ return distribution across
  those 21 windows (if up-biased, BCD outperformance must be discounted).
- §E sizing prep: distribution of single-trade worst cash draw.

Output:
- q081_p3_per_trade_comparison.csv — per-trade BCD vs QQQ vs SPX
- q081_p3_window_bias.csv — direction distribution of 21 windows
- q081_p3_memo.md — narrative (separate file, hand-authored)
"""
from __future__ import annotations
import csv
import json
import random
from datetime import date
from pathlib import Path
from statistics import mean, median, stdev

ROOT = Path(__file__).resolve().parents[2]
TRADES = ROOT / "data" / "backtest_trades_3y_2026-04-29.csv"
SPX_CACHE = ROOT / "data" / "q042_spx_history_cache.json"
PER_TRADE_OUT = ROOT / "research" / "q081" / "q081_p3_per_trade_comparison.csv"
WINDOW_BIAS_OUT = ROOT / "research" / "q081" / "q081_p3_window_bias.csv"

BOOTSTRAP_N = 10_000
random.seed(2026)


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


def load_qqq_history() -> dict[str, float]:
    """Pull QQQ daily Close via yfinance, return {date_iso: close}."""
    import yfinance as yf
    df = yf.Ticker("QQQ").history(start="2023-05-01", end="2026-02-01", auto_adjust=True)
    out = {}
    for ts, row in df.iterrows():
        out[ts.date().isoformat()] = float(row["Close"])
    return out


def load_spx_history() -> dict[str, float]:
    """Try q042 cache first; fall back to yfinance ^GSPC."""
    if SPX_CACHE.exists():
        try:
            with open(SPX_CACHE) as f:
                cache = json.load(f)
            hist = cache["full"]["payload"]["history"]
            return {r["date"]: float(r["close"]) for r in hist}
        except (KeyError, json.JSONDecodeError):
            pass
    # Local-dev fallback: pull from yfinance directly
    import yfinance as yf
    df = yf.Ticker("^GSPC").history(start="2023-05-01", end="2026-02-01", auto_adjust=True)
    return {ts.date().isoformat(): float(row["Close"]) for ts, row in df.iterrows()}


def find_close(hist: dict[str, float], target: str, search_back_days: int = 5) -> tuple[str, float] | None:
    """Find most recent close on or before target date."""
    d = date.fromisoformat(target)
    for _ in range(search_back_days):
        iso = d.isoformat()
        if iso in hist:
            return iso, hist[iso]
        from datetime import timedelta
        d -= timedelta(days=1)
    return None


def load_bcd_trades() -> list[dict]:
    out = []
    with open(TRADES) as f:
        for r in csv.DictReader(f):
            if r["strategy_key"] != "bull_call_diagonal":
                continue
            debit = float(r["option_premium_enter_usd"])
            pnl = float(r["exit_pnl_usd"])
            hold = float(r["hold_days_calendar"])
            if debit <= 0 or hold <= 0:
                continue
            out.append({
                "entry":     r["entry_date"],
                "exit":      r["exit_date"],
                "debit":     debit,
                "pnl":       pnl,
                "hold_days": int(hold),
                "vix":       float(r["entry_vix"]),
                "ivp":       float(r["ivp"]),
                "iv_signal": r["iv_signal"],
                "regime":    r["regime"],
                "trend":     r["trend"],
                "period_roe": pnl / debit,
            })
    return sorted(out, key=lambda t: t["entry"])


def main() -> None:
    trades = load_bcd_trades()
    qqq_hist = load_qqq_history()
    spx_hist = load_spx_history()
    print(f"BCD trades: {len(trades)}")
    print(f"QQQ history rows: {len(qqq_hist)}")
    print(f"SPX history rows: {len(spx_hist)}")

    rows = []
    for t in trades:
        qqq_in = find_close(qqq_hist, t["entry"])
        qqq_out = find_close(qqq_hist, t["exit"])
        spx_in = find_close(spx_hist, t["entry"])
        spx_out = find_close(spx_hist, t["exit"])
        if not all([qqq_in, qqq_out, spx_in, spx_out]):
            print(f"  skip {t['entry']}-{t['exit']}: missing close")
            continue
        qqq_return = (qqq_out[1] - qqq_in[1]) / qqq_in[1]
        spx_return = (spx_out[1] - spx_in[1]) / spx_in[1]
        rows.append({
            "entry":          t["entry"],
            "exit":           t["exit"],
            "hold_days":      t["hold_days"],
            "vix":            round(t["vix"], 2),
            "ivp":            round(t["ivp"], 2),
            "iv_signal":      t["iv_signal"],
            "trend":          t["trend"],
            "debit":          round(t["debit"], 2),
            "pnl":            round(t["pnl"], 2),
            "bcd_period_roe": round(t["period_roe"], 4),
            "qqq_in_close":   round(qqq_in[1], 2),
            "qqq_out_close":  round(qqq_out[1], 2),
            "qqq_return":     round(qqq_return, 4),
            "spx_in_close":   round(spx_in[1], 2),
            "spx_out_close":  round(spx_out[1], 2),
            "spx_return":     round(spx_return, 4),
            "bcd_minus_qqq":  round(t["period_roe"] - qqq_return, 4),
            "bcd_minus_spx":  round(t["period_roe"] - spx_return, 4),
        })

    with open(PER_TRADE_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {PER_TRADE_OUT} ({len(rows)} rows)")

    # Distribution summary
    def stats(values: list[float], label: str) -> dict:
        if not values:
            return {"label": label, "n": 0}
        n = len(values)
        p05_boots = []
        for _ in range(BOOTSTRAP_N):
            sample = [random.choice(values) for _ in range(n)]
            p05_boots.append(percentile(sample, 5))
        return {
            "label":         label,
            "n":             n,
            "mean":          round(mean(values), 4),
            "median":        round(median(values), 4),
            "p05":           round(percentile(values, 5), 4),
            "p25":           round(percentile(values, 25), 4),
            "p75":           round(percentile(values, 75), 4),
            "min":           round(min(values), 4),
            "max":           round(max(values), 4),
            "p05_boot_lo":   round(percentile(p05_boots, 5), 4),
            "p05_boot_hi":   round(percentile(p05_boots, 95), 4),
            "p05_boot_se":   round(stdev(p05_boots), 4),
        }

    bcd = [r["bcd_period_roe"] for r in rows]
    qqq = [r["qqq_return"] for r in rows]
    spx = [r["spx_return"] for r in rows]
    diff = [r["bcd_minus_qqq"] for r in rows]

    summary = [
        stats(bcd,  "BCD period-ROE"),
        stats(qqq,  "QQQ same-window return"),
        stats(spx,  "SPX same-window return"),
        stats(diff, "BCD minus QQQ (per-trade diff)"),
    ]

    with open(WINDOW_BIAS_OUT, "w", newline="") as f:
        fieldnames = ["label", "n", "mean", "median", "p05", "p25", "p75",
                      "min", "max", "p05_boot_lo", "p05_boot_hi", "p05_boot_se"]
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(summary)
    print(f"wrote {WINDOW_BIAS_OUT}")

    print()
    print(f"{'bucket':<32} {'n':>3} {'mean':>9} {'med':>9} {'p05':>9} {'p25':>9} {'p75':>9}")
    print("-" * 88)
    for s in summary:
        if s.get("n", 0) == 0:
            print(f"{s['label']:<32} 0 (empty)")
            continue
        print(f"{s['label']:<32} {s['n']:>3} {s['mean']:>+9.2%} {s['median']:>+9.2%} "
              f"{s['p05']:>+9.2%} {s['p25']:>+9.2%} {s['p75']:>+9.2%}")
        print(f"  └ p05 95% CI [{s['p05_boot_lo']:>+8.2%}, {s['p05_boot_hi']:>+8.2%}]  "
              f"SE {s['p05_boot_se']:.4f}")

    # Direction bias panel
    up_qqq = sum(1 for r in rows if r["qqq_return"] > 0)
    up_spx = sum(1 for r in rows if r["spx_return"] > 0)
    print()
    print(f"DIRECTION BIAS: {up_qqq}/{len(rows)} windows had QQQ > 0, "
          f"{up_spx}/{len(rows)} had SPX > 0")
    print(f"  Mean QQQ window: {mean(qqq):+.2%}  Mean SPX window: {mean(spx):+.2%}")

    # Sizing prep §E: worst cash draw distribution (= worst PnL per trade)
    pnls = [r["pnl"] for r in rows]
    cash_baseline = 37046
    print()
    print(f"SIZING PREP (§E) — single-trade $ PnL distribution:")
    print(f"  worst:  ${min(pnls):>+8,.0f}  ({min(pnls)/cash_baseline*100:+.1f}% of $37k baseline)")
    print(f"  p05:    ${percentile(pnls, 5):>+8,.0f}  ({percentile(pnls, 5)/cash_baseline*100:+.1f}% of baseline)")
    print(f"  median: ${median(pnls):>+8,.0f}  ({median(pnls)/cash_baseline*100:+.1f}% of baseline)")
    print(f"  mean:   ${mean(pnls):>+8,.0f}  ({mean(pnls)/cash_baseline*100:+.1f}% of baseline)")

    # Counts where BCD > QQQ per trade
    bcd_wins = sum(1 for r in rows if r["bcd_minus_qqq"] > 0)
    print()
    print(f"BCD beats QQQ per-trade: {bcd_wins}/{len(rows)} = {bcd_wins/len(rows)*100:.1f}%")


if __name__ == "__main__":
    main()
