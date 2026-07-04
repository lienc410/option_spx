"""Q085 P2b — mirror (overbought) battery for the S6 exit arm.

Pre-registered mirror signals (P2 plan v2): RSI(2)>90, RSI(14)>70, IBS>0.8,
%B>1, 3 consecutive up days, z5>+1. Four horizons x 2 strata, Welch-
studentized permutation, own-batch BH q=0.10 (no pooling). Expected
direction: negative forward edge (overbought -> weak); two-sided inference.
If nothing survives, S6 exit grid degrades to {2td, 5td}.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q085_battery_lib as B

RNG = np.random.default_rng(20260704)
df, C, L, H = B.df, B.C, B.L, B.H
ret1 = C.pct_change()
ibs = (C - L) / (H - L)
bb_mid, bb_sd = C.rolling(20).mean(), C.rolling(20).std()
pctb = (C - (bb_mid - 2 * bb_sd)) / (4 * bb_sd)
z5 = ((C / C.shift(5) - 1) - (C / C.shift(5) - 1).rolling(252).mean()) \
     / (C / C.shift(5) - 1).rolling(252).std()

def wilder_rsi(close, n):
    d = close.diff()
    ru = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    rd = (-d).clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + ru / rd)

MIRRORS = {
    "M_rsi2_ob":   wilder_rsi(C, 2) > 90,
    "M_rsi14_ob":  wilder_rsi(C, 14) > 70,
    "M_ibs_high":  ibs > 0.8,
    "M_pctb_high": pctb > 1,
    "M_up3":       (ret1 > 0) & (ret1.shift(1) > 0) & (ret1.shift(2) > 0),
    "M_z5_high":   z5 > 1,
}
stratA = pd.Series(True, index=df.index)
STRATA = (("A_all", stratA), ("B_norm_bull", df["stratB"]))
ENDPOINTS = {"fwd1": C.shift(-1)/C - 1, "fwd5": C.shift(-5)/C - 1,
             "fwd21": C.shift(-21)/C - 1, "fwd31": C.shift(-31)/C - 1}

rows = []
for ep_name, out in ENDPOINTS.items():
    for name, cond in MIRRORS.items():
        for sname, smask in STRATA:
            r = B.perm_test_studentized(cond, B.default_valid, smask, out, RNG, df.index)
            row = dict(signal=name, stratum=sname, endpoint=ep_name)
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
res.to_csv(B.ROOT / "research/q085/q085_p2b_mirror_results.csv",
           index=False, float_format="%.5f")
print("mirror battery: tests", int(res.p.notna().sum()), "| survivors:", int(res.survive.sum()))
sv = res[res.survive]
if len(sv):
    print(sv[["signal", "stratum", "endpoint", "n_on", "mean_diff_bp", "t", "p"]].to_string(index=False))
else:
    print("(none) -> S6 exit grid degrades to {2td, 5td}")
print("\nfull grid, p<0.05 rows for reference:")
ref = res[res.p < 0.05]
print(ref[["signal", "stratum", "endpoint", "n_on", "mean_diff_bp", "p", "sign_consistent"]].to_string(index=False) if len(ref) else "(none)")
