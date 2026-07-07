"""Q089 E2 — entry-timing head-to-head (problem A), pre-registered protocol.

Incumbent: enter on first eligible non-busy lane day (A4 run_arm pattern).
Challenger(N): at each decision point (episode start / first eligible day
after a trade exits) wait for the first F3 day within N trading days, enter
only if the lane is still eligible that day; exhaustion -> disarm until the
next lane gap re-opens an episode (E2 design lock in q089_framing.md).
Both arms: simulate_cycle (CALIB legs + friction). Foregone trades enter the
comparison through arm TOTALS over the identical calendar span.
Window N in {3,5,10}: selected on entries <2013-01-01 (max total-PnL delta
vs incumbent), confirmed on >=2013. Era slices mandatory; year-block
bootstrap CI on the delta of totals.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "q085"))
sys.path.insert(0, str(Path(__file__).parent))
import q085_battery_lib as B
from q089_calib_lib import build_offsets, simulate_cycle, load_spx_history, load_vix_history

SCRATCH = Path("/private/tmp/claude-501/-Users-lienchen-Documents-workspace-SPX-strat/"
               "b43fdd42-cec2-4795-b85c-8ef4d4adf354/scratchpad")
SPLIT = "2013-01-01"

df = B.df
sig = pd.read_csv(ROOT / "research/q078/_signal_history_cache.csv",
                  parse_dates=["date"]).set_index("date")
for col in ("regime", "trend", "strategy_key"):
    df[col] = sig[col].reindex(df.index)
lane = ((df.regime == "LOW_VOL") & (df.trend == "BULLISH")
        & (df.strategy_key == "bull_call_diagonal")
        & (df.index >= "2000-01-01") & B.default_valid & df["vix"].notna()).values
F3 = (B.SIGNALS["F3_rsi2_os"] | B.SIGNALS["F3_down3"]
      | B.SIGNALS["F3_ibs_low"]).fillna(False).values
DATES = [d.date().isoformat() for d in df.index]

offsets = build_offsets(SCRATCH)
spx, vix = load_spx_history(), load_vix_history()


def run_incumbent() -> pd.DataFrame:
    trades, busy = [], ""
    for p, d in enumerate(DATES):
        if d <= busy or not lane[p]:
            continue
        t = simulate_cycle(offsets, d, spx, vix)
        if t:
            trades.append(t)
            busy = t["exit_date"]
    return pd.DataFrame(trades)


def run_challenger(N: int) -> pd.DataFrame:
    trades, busy = [], ""
    window_end, disarmed = None, False
    for p, d in enumerate(DATES):
        if not lane[p]:
            window_end, disarmed = None, False  # lane gap re-arms
            continue
        if d <= busy:
            continue
        if disarmed:
            continue
        if window_end is None:
            window_end = p + N  # decision point (offset 0 counts)
        if F3[p]:
            t = simulate_cycle(offsets, d, spx, vix)
            if t:
                trades.append(t)
                busy = t["exit_date"]
            window_end = None
        elif p >= window_end:
            window_end, disarmed = None, True
    return pd.DataFrame(trades)


ERAS = [("full", "2000", "2100"), ("2000s", "2000", "2010"), ("2010s", "2010", "2020"),
        ("2020-23", "2020", "2024"), ("2024+", "2024", "2100"), ("last24m", "2024-07-06", "2100")]


def era_stats(t: pd.DataFrame, lo: str, hi: str) -> tuple[int, float, float]:
    w = t[(t.entry_date >= lo) & (t.entry_date < hi)]
    return len(w), w.pnl_usd.sum(), (w.pnl_usd.mean() if len(w) else float("nan"))


def boot_delta_total(a: pd.DataFrame, b: pd.DataFrame, n=2000, seed=89) -> tuple[float, float]:
    """Year-block bootstrap CI (2.5/97.5%) of total(b) - total(a)."""
    years = sorted({d[:4] for d in DATES})
    ya = a.groupby(a.entry_date.str[:4]).pnl_usd.sum()
    yb = b.groupby(b.entry_date.str[:4]).pnl_usd.sum()
    rng, out = np.random.default_rng(seed), []
    for _ in range(n):
        pick = rng.choice(years, size=len(years), replace=True)
        out.append(sum(yb.get(y, 0.0) - ya.get(y, 0.0) for y in pick))
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def main():
    inc = run_incumbent()
    arms = {"incumbent": inc}
    for N in (3, 5, 10):
        arms[f"wait{N}"] = run_challenger(N)

    rows = []
    for name, t in arms.items():
        for era, lo, hi in ERAS:
            n, tot, mean = era_stats(t, lo, hi)
            rows.append({"arm": name, "era": era, "n": n,
                         "total_usd": round(tot), "mean_usd": round(mean) if n else None})
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "research/q089/q089_e2_results.csv", index=False)

    print("\n== arm x era (n / total$ / mean$) ==")
    piv = out.pivot(index="era", columns="arm", values="total_usd")
    print(piv.reindex([e[0] for e in ERAS]).to_string())
    print("\ntrade counts:", {k: len(v) for k, v in arms.items()})

    # half-sample: select window on <SPLIT by delta total, confirm on >=SPLIT
    print(f"\n== half-sample (split {SPLIT}) ==")
    sel = {}
    for N in (3, 5, 10):
        ch = arms[f"wait{N}"]
        d1 = (ch[ch.entry_date < SPLIT].pnl_usd.sum()
              - inc[inc.entry_date < SPLIT].pnl_usd.sum())
        d2 = (ch[ch.entry_date >= SPLIT].pnl_usd.sum()
              - inc[inc.entry_date >= SPLIT].pnl_usd.sum())
        sel[N] = (d1, d2)
        print(f"wait{N}: select-half dTotal={d1:+,.0f}  confirm-half dTotal={d2:+,.0f}")
    best = max(sel, key=lambda k: sel[k][0])
    lo95, hi95 = boot_delta_total(inc, arms[f"wait{best}"])
    print(f"\nselected window (select-half): wait{best}; confirm-half dTotal={sel[best][1]:+,.0f}")
    print(f"full-sample year-block bootstrap 95% CI of dTotal(wait{best} - incumbent): "
          f"[{lo95:+,.0f}, {hi95:+,.0f}]")

    for name in ("incumbent", f"wait{best}"):
        t = arms[name]
        k = max(1, int(0.10 * len(t)))
        print(f"{name:<10} n={len(t):>3} mean=${t.pnl_usd.mean():>7,.0f} "
              f"median=${t.pnl_usd.median():>7,.0f} worst=${t.pnl_usd.min():>8,.0f} "
              f"CVaR10=${t.pnl_usd.nsmallest(k).mean():>8,.0f}")


if __name__ == "__main__":
    main()
