"""Q083 P16 — lockout acceptance metrics (before/after SPEC-113) + 2021 focus.

Companion to q083_p16_lockout_acceptance_2026-07-03.md and
task/q083_fable_external_review_2026-07-03.md. Two independent passes
concatenated; run top-to-bottom.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
"""Independent review calc: does SPEC-113 move the PM's actual metrics?

PM metrics (from the 2026-06-02 complaint):
  1. Tradeable-day frequency (some actionable strategy vs reduce_wait)
  2. Post-VIX-spike lockout duration ("single spike -> 6-10 months untradeable")

Before = production selector output cached 2026-05-27 (pre-SPEC-113).
After  = before + carve: NORMAL x IV_LOW x BULLISH x VIX<18 -> BCD.
Note: 'after' is an UPPER BOUND on tradability (SPEC-079 comfortable-top
filter and SPEC-111 cash gates not modeled here; both only subtract).
"""
import csv
from collections import Counter
from datetime import datetime

CACHE = str(ROOT / "research/q078/_signal_history_cache.csv")

rows = []
with open(CACHE) as f:
    for r in csv.DictReader(f):
        r["vix_f"] = float(r["vix"])
        r["tradeable_before"] = bool(r["strategy_key"])
        carved = (r["regime"] == "NORMAL" and r["iv_signal"] == "LOW"
                  and r["trend"] == "BULLISH" and r["vix_f"] < 18.0)
        r["tradeable_after"] = r["tradeable_before"] or carved
        r["carved"] = carved and not r["tradeable_before"]
        rows.append(r)

n = len(rows)
tb = sum(r["tradeable_before"] for r in rows)
ta = sum(r["tradeable_after"] for r in rows)
nc = sum(r["carved"] for r in rows)
print(f"Total trading days 2000-2026: {n}")
print(f"Tradeable BEFORE: {tb} ({100*tb/n:.1f}%)")
print(f"Tradeable AFTER : {ta} ({100*ta/n:.1f}%)  [carve adds {nc} days = +{100*nc/n:.1f}pp]")

# Which cells remain dead (blocked days by regime x iv_signal x trend), after
print("\n--- Remaining blocked days AFTER SPEC-113, by cell (top 12) ---")
cell = Counter()
for r in rows:
    if not r["tradeable_after"]:
        cell[(r["regime"], r["iv_signal"], r["trend"])] += 1
blocked_after = sum(cell.values())
for (k, v) in cell.most_common(12):
    print(f"  {str(k):<38} {v:>5}  ({100*v/blocked_after:.1f}% of blocked)")

# Consecutive blocked-stretch distribution, before vs after
def stretches(key):
    out, cur = [], 0
    for r in rows:
        if not r[key]:
            cur += 1
        else:
            if cur: out.append(cur)
            cur = 0
    if cur: out.append(cur)
    return sorted(out)

for key, label in (("tradeable_before", "BEFORE"), ("tradeable_after", "AFTER")):
    s = stretches(key)
    long90 = [x for x in s if x >= 90]   # ~4.3 months
    long126 = [x for x in s if x >= 126] # ~6 months
    p95 = s[int(0.95 * len(s)) - 1]
    print(f"\n--- Blocked stretches {label} ---")
    print(f"  count={len(s)}  median={s[len(s)//2]}  p95={p95}  max={s[-1]} trading days"
          f" (~{s[-1]/21:.1f} months)")
    print(f"  stretches >=90td (~4.3mo): {len(long90)}   >=126td (~6mo): {len(long126)}")
    print(f"  top 5 longest: {s[-5:]}")

# Spike-episode lockout: VIX crosses >=30 after >=20 days below 30
episodes = []
below = 0
for i, r in enumerate(rows):
    if r["vix_f"] >= 30:
        if below >= 20:
            episodes.append(i)
        below = 0
    else:
        below += 1

print(f"\n--- VIX>=30 spike episodes (n={len(episodes)}) ---")
print(f"{'spike date':<12} {'to next tradeable (before)':>28} {'(after)':>10}   {'blocked days in next 250td: before/after'}")
for i in episodes:
    d = rows[i]["date"]
    def next_trade(key):
        for j in range(i, len(rows)):
            if rows[j][key]:
                return j - i
        return None
    nb, na = next_trade("tradeable_before"), next_trade("tradeable_after")
    w = rows[i:i+250]
    bb = sum(not r["tradeable_before"] for r in w)
    ba = sum(not r["tradeable_after"] for r in w)
    # longest blocked stretch within 250td post-spike
    def longest(key):
        best = cur = 0
        for r in w:
            cur = cur + 1 if not r[key] else 0
            best = max(best, cur)
        return best
    lb, la = longest("tradeable_before"), longest("tradeable_after")
    fmt = lambda x: f"{x}td" if x is not None else "never"
    print(f"{d:<12} {fmt(nb):>28} {fmt(na):>10}   blocked {bb}/{ba} of 250; longest stretch {lb}->{la}")

# Carve fire-days per year (how often would PM actually see the new cell light up)
print("\n--- Carved-cell days per year (upper bound, pre-SPEC-079/111 gates) ---")
per_year = Counter(r["date"][:4] for r in rows if r["carved"])
years = sorted({r["date"][:4] for r in rows})
line = ", ".join(f"{y}:{per_year.get(y,0)}" for y in years)
print(line)
zero_years = [y for y in years if per_year.get(y, 0) == 0]
print(f"Years with ZERO carved days: {len(zero_years)}/{len(years)} -> {zero_years}")
"""2021 post-COVID focused evaluation of SPEC-113 carve.

Checks:
  A. SPEC-079 filter inertness inside carve (vix<=15 condition vs carve vix in [15,18))
  B. Per-year blocked density before/after, 2020-2022 focus
  C. 2021 carve-day characteristics (vix distribution, monthly spread)
  D. Carve trades (P11 CSV, entry_vix<18) in 2020-2022: count, PnL, ROE, occupancy
  E. Sequential-ladder realism: trade spacing vs carve-day count
"""
import csv
from collections import Counter, defaultdict

CACHE = str(ROOT / "research/q078/_signal_history_cache.csv")
TRADES = str(ROOT / "research/q083/q083_p11_bcd_normal_low_ivr_trades.csv")

rows = []
with open(CACHE) as f:
    for r in csv.DictReader(f):
        r["vix_f"] = float(r["vix"])
        r["tb"] = bool(r["strategy_key"])
        r["carve"] = (r["regime"] == "NORMAL" and r["iv_signal"] == "LOW"
                      and r["trend"] == "BULLISH" and r["vix_f"] < 18.0)
        r["ta"] = r["tb"] or r["carve"]
        rows.append(r)

# A. SPEC-079 inertness: carve days with vix <= 15.0 (necessary condition to block)
carve_days = [r for r in rows if r["carve"] and not r["tb"]]
v15 = [r for r in carve_days if r["vix_f"] <= 15.0]
vmin = min(r["vix_f"] for r in carve_days)
print(f"A. carve days n={len(carve_days)}, vix<=15.0 (SPEC-079 blockable): {len(v15)}  (min vix={vmin})")

# B. per-year blocked days before/after
by = defaultdict(lambda: [0, 0, 0])  # year -> [total, blocked_before, blocked_after]
for r in rows:
    y = r["date"][:4]
    by[y][0] += 1
    by[y][1] += (not r["tb"])
    by[y][2] += (not r["ta"])
print("\nB. per-year blocked days (total / before / after / carve-days):")
for y in sorted(by):
    t, b, a = by[y]
    c = b - a
    mark = " <== " if y in ("2020", "2021", "2022") else ""
    print(f"  {y}: total={t:>3} blocked {b:>3} -> {a:>3}  (carve {c:>3}){mark}")

# C. 2021 carve-day characteristics
c21 = [r for r in carve_days if r["date"].startswith("2021")]
print(f"\nC. 2021 carve days: {len(c21)}")
months = Counter(r["date"][:7] for r in c21)
print("  monthly:", dict(sorted(months.items())))
vs = sorted(r["vix_f"] for r in c21)
print(f"  vix: min={vs[0]} med={vs[len(vs)//2]} max={vs[-1]}")
ivrs = sorted(float(r["ivr"]) for r in c21)
print(f"  ivr: min={ivrs[0]} med={ivrs[len(ivrs)//2]} max={ivrs[-1]}")

# D. P11 trades with entry_vix<18 (the SPEC-113 carve), 2020-2022 focus + all-years summary
trades = []
with open(TRADES) as f:
    for t in csv.DictReader(f):
        t["entry_vix_f"] = float(t["entry_vix"])
        t["pnl_f"] = float(t["pnl_usd"])
        t["roe_f"] = float(t["period_roe"])
        t["debit_f"] = float(t["entry_debit_usd"])
        trades.append(t)
carve_tr = [t for t in trades if t["entry_vix_f"] < 18.0]
print(f"\nD. P11 trades total={len(trades)}; carve (entry_vix<18) n={len(carve_tr)}")
wins = sum(1 for t in carve_tr if t["pnl_f"] > 0)
print(f"  all-years: win {wins}/{len(carve_tr)} = {100*wins/len(carve_tr):.0f}%  "
      f"total PnL ${sum(t['pnl_f'] for t in carve_tr):,.0f}")
for span in ("2020", "2021", "2022"):
    tt = [t for t in carve_tr if t["entry_date"].startswith(span)]
    if not tt:
        print(f"  {span}: no trades")
        continue
    w = sum(1 for t in tt if t["pnl_f"] > 0)
    pnl = sum(t["pnl_f"] for t in tt)
    debits = [t["debit_f"] for t in tt]
    roes = [f"{t['roe_f']:+.1%}" for t in tt]
    print(f"  {span}: n={len(tt)} win {w}/{len(tt)}  PnL ${pnl:,.0f}  "
          f"debit med ${sorted(debits)[len(debits)//2]:,.0f}  ROEs {roes}")
    for t in tt:
        print(f"    {t['entry_date']} -> {t['exit_date']} ({t['hold_days']}d) "
              f"debit ${t['debit_f']:,.0f} pnl ${t['pnl_f']:,.0f} entry_vix {t['entry_vix']}")

# E. worst trade in carve + 2021 blocked-stretch shape after
worst = min(carve_tr, key=lambda t: t["pnl_f"])
print(f"\nE. worst carve trade: {worst['entry_date']} pnl ${worst['pnl_f']:,.0f} "
      f"(debit ${worst['debit_f']:,.0f}, roe {worst['roe_f']:+.1%})")
# longest blocked stretch within 2021 before/after
def longest_in(year, key):
    best = cur = 0
    for r in rows:
        if not r["date"].startswith(year):
            continue
        cur = cur + 1 if not r[key] else 0
        best = max(best, cur)
    return best
for y in ("2020", "2021", "2022"):
    print(f"  {y} longest blocked stretch: before={longest_in(y,'tb')}td after={longest_in(y,'ta')}td")
