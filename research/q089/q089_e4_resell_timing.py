"""Q089 E4 — short-leg re-sell timing head-to-head (problem B), pre-registered.

Campaign frame (q089_calib_lib.simulate_campaign): long held to 21 DTE;
short bought back on collapse (<=15% of entry prem) or short 21 DTE.
Entry stream: incumbent lane entries with campaign-length busy-lock, shared
by ALL rules -> per-campaign PAIRED deltas vs 'immediate' (same entries, only
management differs).
Rules: immediate (incumbent) | wait5 | retrace50 cap{5,10} | prev_high
cap{5,10} | prev_high_lit (PM's literal unbounded proposal, diagnostic).
Cap selection on entries <2013-01-01, confirmation on >=2013 (half-sample).
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
from q089_calib_lib import (build_offsets, simulate_campaign,
                            load_spx_history, load_vix_history)

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
DATES = [d.date().isoformat() for d in df.index]

offsets = build_offsets(SCRATCH)
spx, vix = load_spx_history(), load_vix_history()

# entry stream from the baseline rule (campaign-length busy-lock)
entries, busy = [], ""
for p, d in enumerate(DATES):
    if d <= busy or not lane[p]:
        continue
    c = simulate_campaign(offsets, d, spx, vix, "immediate")
    if c:
        entries.append(d)
        busy = c["exit_date"]
print(f"campaign entries (busy-locked): {len(entries)}")

RULES = [("immediate", 0), ("wait5", 0), ("retrace50", 5), ("retrace50", 10),
         ("prev_high", 5), ("prev_high", 10), ("prev_high_lit", 0)]

frames = {}
for rule, cap in RULES:
    rows = [simulate_campaign(offsets, d, spx, vix, rule, cap_td=cap) for d in entries]
    frames[(rule, cap)] = pd.DataFrame([r for r in rows if r])

base = frames[("immediate", 0)].set_index("entry_date")
ERAS = [("full", "2000", "2100"), ("<2013", "2000", "2013"), (">=2013", "2013", "2100"),
        ("2024+", "2024", "2100"), ("last24m", "2024-07-06", "2100")]

print(f"\nbaseline immediate: n={len(base)} mean=${base.pnl_usd.mean():,.0f} "
      f"total=${base.pnl_usd.sum():,.0f} cycles/campaign={base.n_cycles.mean():.2f}")
print(f"\n{'rule':<18} {'era':<8} {'n':>4} {'pairedD$':>9} {'t':>6} {'win%':>5} "
      f"{'naked_d':>8} {'cycles':>7}")
rows_out = []
for (rule, cap), t in frames.items():
    if rule == "immediate":
        continue
    m = t.set_index("entry_date").join(base, rsuffix="_b")
    m["d"] = m.pnl_usd - m.pnl_usd_b
    for era, lo, hi in ERAS:
        w = m[(m.index >= lo) & (m.index < hi)]
        if not len(w):
            continue
        tstat = (w.d.mean() / (w.d.std(ddof=1) / np.sqrt(len(w)))
                 if len(w) > 2 and w.d.std(ddof=1) > 0 else float("nan"))
        rows_out.append({"rule": rule, "cap": cap, "era": era, "n": len(w),
                         "paired_d_usd": round(w.d.mean()), "t": round(tstat, 2),
                         "win_pct": round(100 * (w.d > 0).mean()),
                         "naked_days": round(w.naked_days.mean(), 1),
                         "cycles": round(w.n_cycles.mean(), 2)})
        label = f"{rule}-c{cap}" if cap else rule
        print(f"{label:<18} {era:<8} {len(w):>4} {w.d.mean():>9,.0f} {tstat:>6.2f} "
              f"{100*(w.d>0).mean():>4.0f}% {w.naked_days.mean():>8.1f} {w.n_cycles.mean():>7.2f}")

pd.DataFrame(rows_out).to_csv(ROOT / "research/q089/q089_e4_results.csv", index=False)
