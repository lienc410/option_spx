"""Q089 E1 — fact layer (pre-registered in q089_framing.md, no PnL).

Question: on BCD-eligible days (LOW_VOL x BULLISH lane, same mask as Q087 A4),
how often does an F3 oversold day (any-of: rsi2<10 | down3 | ibs<0.2, Q085
original cutpoints, zero new degrees of freedom) appear within N={3,5,10}
trading days? Wait-day distribution, window-exhaustion rate, and whether the
lane is STILL eligible on the F3 day (a wait is only actionable if the matrix
still allows entry). Two views: all eligible days / episode starts (first
eligible day after a gap = the actual decision moment). Era-stratified.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "q085"))
import q085_battery_lib as B

df, C = B.df, B.C
sig = pd.read_csv(ROOT / "research/q078/_signal_history_cache.csv",
                  parse_dates=["date"]).set_index("date")
for col in ("regime", "trend", "strategy_key"):
    df[col] = sig[col].reindex(df.index)

lane = ((df.regime == "LOW_VOL") & (df.trend == "BULLISH")
        & (df.strategy_key == "bull_call_diagonal")
        & (df.index >= "2000-01-01") & B.default_valid & df["vix"].notna())

F3 = (B.SIGNALS["F3_rsi2_os"] | B.SIGNALS["F3_down3"]
      | B.SIGNALS["F3_ibs_low"]).fillna(False)

for name in ("F3_rsi2_os", "F3_down3", "F3_ibs_low"):
    s = B.SIGNALS[name].fillna(False)
    print(f"component {name}: fires on {100*s[lane].mean():.1f}% of lane days")
print(f"F3 any-of: fires on {100*F3[lane].mean():.1f}% of lane days | lane n={int(lane.sum())}")

f3 = F3.values
elig = lane.values
MAXW = 10

def first_f3(pos):
    """(offset, still_eligible_on_that_day) of first F3 at offset 0..MAXW, else (None, None)."""
    hi = min(pos + MAXW, len(f3) - 1)
    for p in range(pos, hi + 1):
        if f3[p]:
            return p - pos, bool(elig[p])
    return None, None

episode_start = lane & ~lane.shift(1, fill_value=False)
views = {"all_days": np.where(lane)[0], "episode_start": np.where(episode_start)[0]}

ERAS = [("full", "2000-01-01", None), ("2000s", "2000-01-01", "2010-01-01"),
        ("2010s", "2010-01-01", "2020-01-01"), ("2020-23", "2020-01-01", "2024-01-01"),
        ("2024+", "2024-01-01", None), ("last24m", "2024-07-06", None)]

rows = []
for view, positions in views.items():
    res = pd.DataFrame({"date": df.index[positions]})
    res[["off", "elig_at_hit"]] = [first_f3(p) for p in positions]
    for era, lo, hi in ERAS:
        w = res[(res.date >= lo) & ((res.date < hi) if hi else True)]
        if not len(w):
            continue
        row = {"view": view, "era": era, "n": len(w),
               "pct_f3_day0": 100 * (w.off == 0).mean()}
        later = w[w.off != 0]  # decision days not already oversold
        for N in (3, 5, 10):
            hit = later.off.notna() & (later.off <= N)
            row[f"hit_{N}td_pct"] = 100 * hit.mean() if len(later) else np.nan
            row[f"hit_elig_{N}td_pct"] = (100 * (hit & later.elig_at_hit.fillna(False)).mean()
                                          if len(later) else np.nan)
            row[f"med_wait_{N}td"] = later.off[hit].median() if hit.any() else np.nan
        rows.append(row)

out = pd.DataFrame(rows)
out.to_csv(ROOT / "research/q089/q089_e1_results.csv", index=False)
pd.set_option("display.width", 200)
for view in views:
    print(f"\n== {view} == (pct among days NOT already F3 on day 0)")
    cols = ["era", "n", "pct_f3_day0", "hit_3td_pct", "hit_elig_3td_pct", "med_wait_3td",
            "hit_5td_pct", "hit_elig_5td_pct", "med_wait_5td",
            "hit_10td_pct", "hit_elig_10td_pct", "med_wait_10td"]
    print(out[out.view == view][cols].to_string(index=False, float_format=lambda x: f"{x:.1f}"))
