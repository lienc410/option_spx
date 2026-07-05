"""Q087 Track-A #4 — SPEC-079 comfortable-top filter audit (LOW_VOL lane).

Filter (bcd_filter.py, Q038 walk-forward, thresholds NOT re-tuned here):
  risk_score=3 blocks BCD when VIX<=15 AND dist_30d_high<=-1% AND ma_gap>+1.5pp.
Applies to LOW_VOL x BULLISH BCD entries (structurally inert in NORMAL carve).

Pre-registered questions (no threshold scanning):
  Q1 fire rate: how many LOW_VOL x BULLISH BCD-eligible days does it block?
  Q2 quality: blocked vs allowed days, BCD counterfactual (Q082 P6 machinery,
     same model both arms -> relative comparison robust), Welch t.
  Q3 eras: where does any protective value live (full/worst-7y/2020+/2024+)?
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "q082"))
sys.path.insert(0, str(ROOT / "research" / "q085"))
from q082_p6_bcd_synth_reconstruction import simulate_bcd_trade, load_spx_history, load_vix_history
import q085_battery_lib as B

df, C = B.df, B.C
sig = pd.read_csv(ROOT / "research/q078/_signal_history_cache.csv",
                  parse_dates=["date"]).set_index("date")
for col in ("regime", "trend", "strategy_key"):
    df[col] = sig[col].reindex(df.index)

# filter features, point-in-time (close-based, mirrors trend.py conventions)
dist30 = C / C.rolling(30).max() - 1.0
ma50 = C.rolling(50).mean()
ma_gap = C / ma50 - 1.0
score = ((df["vix"] <= 15.0).astype(int)
         + (dist30 <= -0.01).astype(int)
         + (ma_gap > 0.015).astype(int))

lane = ((df.regime == "LOW_VOL") & (df.trend == "BULLISH")
        & (df.strategy_key == "bull_call_diagonal")
        & (df.index >= "2000-01-01") & B.default_valid & df["vix"].notna())
blocked = lane & (score == 3)
allowed = lane & (score < 3)
print(f"LOW_VOL x BULLISH BCD days: {int(lane.sum())} | filter blocks {int(blocked.sum())} "
      f"({100*blocked.sum()/lane.sum():.1f}%)")

spx, vix = load_spx_history(), load_vix_history()

def run_arm(mask):
    days = [d.date().isoformat() for d in df.index[mask]]
    trades, busy = [], ""
    for d in days:
        if d <= busy:
            continue
        t = simulate_bcd_trade(d, spx, vix)
        if t:
            trades.append(t)
            busy = t["exit_date"]
    return pd.DataFrame(trades)

def era(t, lo, hi=None):
    w = t[(t.entry_date >= lo) & ((t.entry_date < hi) if hi else True)]
    return len(w), (w.pnl_usd.mean() if len(w) else float("nan"))

print(f"{'arm':<10} {'n':>4} {'win%':>5} {'mean$':>7} {'worst$':>8} {'CVaR10':>8} "
      f"{'worst7y':>8} {'2020+':>7} {'2024+':>7}")
arms = {}
for name, m in (("ALLOWED", allowed), ("BLOCKED", blocked)):
    t = run_arm(m)
    t["entry_date"] = pd.to_datetime(t["entry_date"])
    arms[name] = t
    k = max(1, int(0.10 * len(t)))
    w7 = min((era(t, s, s + pd.DateOffset(years=7))[1]
              for s in pd.date_range("2000-01-01", "2019-07-01", freq="6MS")
              if era(t, s, s + pd.DateOffset(years=7))[0] >= 8), default=float("nan"))
    print(f"{name:<10} {len(t):>4} {100*(t.pnl_usd>0).mean():>4.0f}% {t.pnl_usd.mean():>7,.0f} "
          f"{t.pnl_usd.min():>8,.0f} {t.pnl_usd.nsmallest(k).mean():>8,.0f} {w7:>8,.0f} "
          f"{era(t, pd.Timestamp('2020-01-01'))[1]:>7,.0f} {era(t, pd.Timestamp('2024-01-01'))[1]:>7,.0f}")

a, b = arms["ALLOWED"].pnl_usd, arms["BLOCKED"].pnl_usd
if len(b) >= 8:
    se = np.sqrt(a.var(ddof=1)/len(a) + b.var(ddof=1)/len(b))
    t_stat = (b.mean() - a.mean()) / se
    print(f"\nBLOCKED - ALLOWED per-trade diff: ${b.mean()-a.mean():,.0f}  Welch t={t_stat:+.2f}")
    print(f"blocked-days trade count by year: "
          f"{dict(arms['BLOCKED'].entry_date.dt.year.value_counts().sort_index())}")
