"""Q085 P1b — Tier-3 battery + final account seal.

Signals (pre-registered in framing memo F7/F8; data acquired 2026-07-04,
all script-generated per no-hand-transcription rule):
  F7_fomc_pre : next trading day is an FOMC announcement day
                (data/q085_fomc_dates.csv, 220 announcements 2000-2026,
                scraped from federalreserve.gov pages — Lucca-Moench prior)
  F8_cot_washed: ES net-spec 3y-rolling percentile < 20 (contrarian bullish),
                applied with 3-business-day release lag
                (data/q085_cot_es.csv, 1,382 weekly rows 2000-2026, CFTC 13874A)
  F8_pc_high  : CBOE equity P/C 10d-MA 252d-percentile > 80 (contrarian),
                span 2006-11..2019-10 ONLY (feed discontinued — operationally
                dead regardless of result; run for battery completeness)
  AAII        : NOT ACQUIRED (HTTP 403 membership wall) — documented unavailable.

Protocol: studentized permutation, own-batch BH q=0.10 (per corrected
accounting: no pooling), 2 strata x 4 horizons.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q085_battery_lib as B

RNG = np.random.default_rng(20260705)
df, C = B.df, B.C
ROOT = B.ROOT

fomc = pd.read_csv(ROOT / "data/q085_fomc_dates.csv", parse_dates=["announce_date"])
ann = set(fomc.announce_date)
next_day = pd.Series(df.index, index=df.index).shift(-1)
f7 = next_day.isin(ann)

cot = pd.read_csv(ROOT / "data/q085_cot_es.csv", parse_dates=["report_date"])
cot["pctile"] = cot.net_spec.rolling(156, min_periods=52).rank(pct=True) * 100
cot["avail"] = cot.report_date + pd.tseries.offsets.BDay(3)
cot_daily = cot.set_index("avail")["pctile"].reindex(df.index, method="ffill")
f8_cot = cot_daily < 20

pc = pd.read_csv(ROOT / "data/q085_cboe_equity_pc.csv", skiprows=2)
pc.columns = [c.strip() for c in pc.columns]
pc["DATE"] = pd.to_datetime(pc["DATE"])
pc = pc.set_index("DATE")["P/C Ratio"].astype(float).sort_index()
pc10 = pc.rolling(10).mean()
pc_pct = pc10.rolling(252).rank(pct=True) * 100
f8_pc = (pc_pct > 80).reindex(df.index).fillna(False)
pc_valid = pc_pct.reindex(df.index).notna()

SIGNALS = {"F7_fomc_pre": (f7, B.default_valid),
           "F8_cot_washed": (f8_cot, cot_daily.notna()),
           "F8_pc_high": (f8_pc, pc_valid)}
ENDPOINTS = {"fwd1": C.shift(-1)/C - 1, "fwd5": C.shift(-5)/C - 1,
             "fwd21": C.shift(-21)/C - 1, "fwd31": C.shift(-31)/C - 1}
stratA = pd.Series(True, index=df.index)

rows = []
for ep, out in ENDPOINTS.items():
    for name, (cond, valid) in SIGNALS.items():
        for sname, smask in (("A_all", stratA), ("B_norm_bull", df["stratB"])):
            r = B.perm_test_studentized(cond, valid, smask, out, RNG, df.index)
            row = dict(signal=name, stratum=sname, endpoint=ep)
            row.update(r if r else dict(n_on=0, mean_diff_bp=np.nan, t=np.nan,
                                        p=np.nan, sign_consistent=False))
            rows.append(row)
res = pd.DataFrame(rows)
res["bh_pass"] = False
for ep in ENDPOINTS:
    sub = res[(res.endpoint == ep) & res.p.notna()]
    pv = sub.p.sort_values(); m = len(pv)
    bh = 0.10 * np.arange(1, m + 1) / m
    passed = pv.to_numpy() <= bh
    k = passed.nonzero()[0].max() + 1 if passed.any() else 0
    thr = pv.iloc[k - 1] if k else 0.0
    res.loc[(res.endpoint == ep) & (res.p <= thr), "bh_pass"] = True
res["survive"] = res.bh_pass & res.sign_consistent
res.to_csv(ROOT / "research/q085/q085_p1b_results.csv", index=False, float_format="%.5f")
print(f"P1b: {int(res.p.notna().sum())} tests, survivors {int(res.survive.sum())}")
print(res[res.p.notna()].sort_values("p")[
    ["signal","stratum","endpoint","n_on","mean_diff_bp","t","p","sign_consistent","bh_pass"]
].head(10).to_string(index=False))
