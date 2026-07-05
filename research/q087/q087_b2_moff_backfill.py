"""Q087 B2 — mid-implied (*_moff) offset BACKFILL over stored chain snapshots.

PM directive 2026-07-05: don't wait for the monitor's forward 10-day
accumulation — the raw chains already exist (46 days, 2026-05-03..07-03,
local backup ~/backups/oldair/data/q041_chains). Reuses the PRODUCTION
measure_skew() verbatim (convention r045_q0_act365) so backfill and
forward monitor rows are byte-consistent.

Spot proxy: q085 OHLC close (16:30 snapshot vs close — minor skew, noted).
Output: q087_moff_backfill.jsonl (same schema as production monitor) +
median offsets table for immediate CALIB use. Validation: 07-01/07-02 rows
must match dev AC-3 ranges (ATM -1.7~-2.5, d30 -0.0~-1.0, d15 +1.6~+2.1).
"""
from __future__ import annotations
import glob
import json
import math
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from notify.q085_s2bps_paper import measure_skew  # production truth

CHAINS = Path.home() / "backups/oldair/data/q041_chains"
OUT = ROOT / "research/q087/q087_moff_backfill.jsonl"

spx_hist = {r["date"]: r["close"]
            for r in json.load(open(ROOT / "data/q085_spx_ohlc_cache.json"))["history"]}
import yfinance as yf
vix_s = yf.Ticker("^VIX").history(start="2026-05-01", end="2026-07-05")["Close"]
vix_map = {ts.date().isoformat(): float(v) for ts, v in vix_s.items()}

rows_out = []
for d in sorted(glob.glob(str(CHAINS / "2026-*"))):
    date = d[-10:]
    f = Path(d) / "SPX.parquet"
    if not f.exists() or date not in vix_map or date not in spx_hist:
        continue
    df = pd.read_parquet(f)
    df = df[df.iv.notna()] if "iv" in df.columns else df
    puts = df[df.option_type == "PUT"]
    calls = df[df.option_type == "CALL"]
    try:
        row = measure_skew(puts, vix_map[date], date, calls=calls, spx=spx_hist[date])
    except Exception as e:
        print(f"{date}: skipped ({type(e).__name__}: {e})")
        continue
    rows_out.append(row)

with open(OUT, "w") as fh:
    for r in rows_out:
        assert all(math.isfinite(v) for v in r.values() if isinstance(v, (int, float)))
        fh.write(json.dumps(r, sort_keys=True) + "\n")
print(f"backfilled {len(rows_out)} days -> {OUT}")

# median offsets
import statistics as st
fields = [k for k in rows_out[-1] if k.endswith("_moff") or k.endswith("_moff_far")]
print(f"\n{'field':<16} {'n':>3} {'median':>8} {'p25':>7} {'p75':>7}")
med = {}
for fld in sorted(fields):
    vals = [r[fld] for r in rows_out if fld in r and isinstance(r[fld], (int, float))]
    if not vals:
        continue
    vals.sort()
    med[fld] = st.median(vals)
    print(f"{fld:<16} {len(vals):>3} {st.median(vals):>+8.2f} {vals[len(vals)//4]:>+7.2f} {vals[3*len(vals)//4]:>+7.2f}")

# AC-3 cross-validation
print("\nAC-3 validation (dev measured 07-01/07-02):")
for r in rows_out:
    if r.get("date") in ("2026-07-01", "2026-07-02"):
        print(f"  {r['date']}: atm_moff={r.get('atm_moff'):+.2f} d30_moff={r.get('d30_moff'):+.2f} "
              f"d15_moff={r.get('d15_moff'):+.2f}")
