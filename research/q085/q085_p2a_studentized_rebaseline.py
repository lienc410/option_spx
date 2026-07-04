"""Q085 P2a — studentized re-baseline of the full fact-layer battery.

External-review fix: Welch-studentized permutation, per-endpoint-batch BH
(no pooling — pooling correlated batches subsidizes). 43 signals x 2 strata
x 4 horizons. Output = the corrected survivor set that all P2 slots build on.
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
df, C = B.df, B.C
stratA = pd.Series(True, index=df.index)
STRATA = (("A_all", stratA), ("B_norm_bull", df["stratB"]))
ENDPOINTS = {"fwd1": C.shift(-1)/C - 1, "fwd5": C.shift(-5)/C - 1,
             "fwd21": C.shift(-21)/C - 1, "fwd31": C.shift(-31)/C - 1}

rows = []
for ep_name, out in ENDPOINTS.items():
    for name, cond in B.SIGNALS.items():
        valid = B.VALID.get(name, B.default_valid)
        for sname, smask in STRATA:
            r = B.perm_test_studentized(cond, valid, smask, out, RNG, df.index)
            row = dict(signal=name, stratum=sname, endpoint=ep_name)
            row.update(r if r else dict(n_on=0, mean_diff_bp=np.nan, t=np.nan,
                                        p=np.nan, sign_consistent=False))
            rows.append(row)
res = pd.DataFrame(rows)

# per-endpoint-batch BH q=0.10
res["bh_pass"] = False
for ep in ENDPOINTS:
    sub = res[(res.endpoint == ep) & res.p.notna()]
    pv = sub.p.sort_values()
    m = len(pv)
    bh = 0.10 * np.arange(1, m + 1) / m
    passed = pv.to_numpy() <= bh
    k = passed.nonzero()[0].max() + 1 if passed.any() else 0
    thr = pv.iloc[k - 1] if k else 0.0
    res.loc[(res.endpoint == ep) & (res.p <= thr), "bh_pass"] = True
    print(f"batch {ep}: {m} tests, BH thr {thr:.5f}, pass {int(((res.endpoint==ep)&res.bh_pass).sum())}")

res["survive"] = res.bh_pass & res.sign_consistent
res.to_csv(B.ROOT / "research/q085/q085_p2a_studentized_results.csv",
           index=False, float_format="%.5f")
surv = res[res.survive].sort_values(["endpoint", "p"])
print(f"\nSTUDENTIZED SURVIVORS: {len(surv)}")
print(surv[["signal", "stratum", "endpoint", "n_on", "mean_diff_bp", "t", "p"]].to_string(index=False))
