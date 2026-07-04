"""Q085 P0 — premise checks (run 2026-07-03, results in framing memo §1).

1. Directional share of the book: 68.4% of tradeable days route to
   leveraged-long structures (BCD + BPS/BPS_HV).
2. Anti-timing effect of the IVP upper gate in NORMAL x BULLISH:
   episode-level price giveaway vs tail protection.
"""
import csv
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
rows = []
with open(ROOT / "research/q078/_signal_history_cache.csv") as f:
    for r in csv.DictReader(f):
        try:
            r["spx_f"] = float(r["spx"]); r["ivp_f"] = float(r["ivp"]); r["vix_f"] = float(r["vix"])
        except (ValueError, TypeError):
            continue
        rows.append(r)

# 1. directional share
from collections import Counter
keys = Counter(r["strategy_key"] for r in rows if r["strategy_key"])
long_delta = sum(v for k, v in keys.items() if k in
                 ("bull_call_diagonal", "bull_put_spread", "bull_put_spread_hv"))
total = sum(keys.values())
print(f"long-delta share of tradeable days: {long_delta}/{total} = {100*long_delta/total:.1f}%")

# 2. anti-timing premise
for i, r in enumerate(rows):
    lo = max(0, i - 62)
    r["dd"] = r["spx_f"] / max(x["spx_f"] for x in rows[lo:i+1]) - 1.0

def upper_bound(sig):
    return 55.0 if sig == "NEUTRAL" else 70.0

allowed, blocked_high = [], []
for i, r in enumerate(rows):
    if r["regime"] != "NORMAL" or r["trend"] != "BULLISH":
        continue
    if r["strategy_key"] in ("bull_put_spread", "iron_condor"):
        allowed.append(i)
    elif r["iv_signal"] in ("HIGH", "NEUTRAL") and r["ivp_f"] > upper_bound(r["iv_signal"]):
        blocked_high.append(i)

def q(v, p):
    s = sorted(v); return s[min(len(s) - 1, int(p * len(s)))]

def fwd(i, n=31):
    j = i + n
    return rows[j]["spx_f"] / rows[i]["spx_f"] - 1.0 if j < len(rows) else None

print(f"allowed n={len(allowed)}, blocked-by-IVP-upper n={len(blocked_high)}")
for label, idx in (("allowed", allowed), ("blocked_high", blocked_high)):
    dd = [rows[i]["dd"] for i in idx]
    vx = [rows[i]["vix_f"] for i in idx]
    f = [x for x in (fwd(i) for i in idx) if x is not None]
    print(f"  {label:<13} dd med {st.median(dd):+.2%}  VIX med {st.median(vx):.1f}  "
          f"fwd31 med {st.median(f):+.2%} p10 {q(f,0.10):+.2%} p5 {q(f,0.05):+.2%} worst {min(f):+.2%}")

runs, cur = [], []
for i in sorted(blocked_high):
    if cur and i - cur[-1] <= 3:
        cur.append(i)
    else:
        if cur: runs.append(cur)
        cur = [i]
if cur: runs.append(cur)

al = sorted(allowed)
gaps = []
for run in runs:
    low_px = min(rows[i]["spx_f"] for i in run)
    nxt = next((a for a in al if a > run[-1]), None)
    if nxt:
        gaps.append((rows[nxt]["spx_f"] / low_px - 1.0, nxt - run[-1]))
ups, lags = [g[0] for g in gaps], [g[1] for g in gaps]
print(f"episodes n={len(runs)}: window-low -> next entry: med {st.median(ups):+.2%} "
      f"p75 {q(ups,0.75):+.2%} max {max(ups):+.2%}; lag med {st.median(lags):.0f}td; "
      f"below-low episodes {sum(1 for u in ups if u < 0)}/{len(gaps)}")
