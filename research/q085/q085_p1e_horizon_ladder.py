"""Q085 P1e — horizon ladder (PM discussion point 1, 2026-07-03).

Completes the horizon grid: {1td (P1c), 5td, 21td, 31td (P1a)} for all 43
signals x 2 strata. New batches here: fwd-5td and fwd-21td (uniform across
battery — no per-signal horizon picking). Joint BH-FDR q=0.10 re-run over
ALL endpoint batteries (P1a + P1c + P1e), the strictest accounting.

PM discussion point 2 (generalize inverse-signal harvesting): the output
catalog is SIGNED — signals significant in the reverse of their conventional
direction are first-class rows, not anomalies.

Output: q085_p1e_results.csv (new tests) + q085_p1_horizon_catalog.csv
        (signal x stratum x horizon signed grid with joint-FDR survival).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q085_battery_lib as B

RNG = np.random.default_rng(20260703)
ROOT = B.ROOT
C, df = B.C, B.df

fwd5 = C.shift(-5) / C - 1.0
fwd21 = C.shift(-21) / C - 1.0
stratA = pd.Series(True, index=df.index)
STRATA = (("A_all", stratA), ("B_norm_bull", df["stratB"]))

rows = []
for name, cond in B.SIGNALS.items():
    valid = B.VALID.get(name, B.default_valid)
    for sname, smask in STRATA:
        for hname, out in (("fwd5", fwd5), ("fwd21", fwd21)):
            r = B.perm_test_generic(cond, valid, smask, out, RNG, df.index)
            row = dict(signal=name, stratum=sname, endpoint=hname)
            row.update(r if r else dict(n_on=0, mean_diff_bp=np.nan, p=np.nan,
                                        sign_consistent=False))
            rows.append(row)
res = pd.DataFrame(rows)
res.to_csv(ROOT / "research/q085/q085_p1e_results.csv", index=False, float_format="%.5f")

# ---- joint FDR over ALL batches ----
a = pd.read_csv(ROOT / "research/q085/q085_p1_results.csv")
a["endpoint"] = "fwd31"
a["mean_diff_bp"] = a["mean_diff_pp"] * 100
c = pd.read_csv(ROOT / "research/q085/q085_p1c_results.csv")
c.loc[c.endpoint == "nextday", "endpoint"] = "fwd1"
cols = ["signal", "stratum", "endpoint", "mean_diff_bp", "p", "sign_consistent"]
pool = pd.concat([a[cols], c[cols], res[cols]], ignore_index=True)
pool = pool[pool.p.notna()].reset_index(drop=True)
m = len(pool)
order = pool.p.sort_values()
bh = 0.10 * np.arange(1, m + 1) / m
passed = order.to_numpy() <= bh
k = passed.nonzero()[0].max() + 1 if passed.any() else 0
thr = order.iloc[k - 1] if k else 0.0
pool["joint_fdr_pass"] = pool.p <= thr
pool["survive"] = pool["joint_fdr_pass"] & pool["sign_consistent"]
print(f"JOINT FDR over {m} tests (all horizons): thr p<={thr:.5f}, survivors={int(pool['survive'].sum())}")

# ---- signed horizon catalog ----
cat = pool.pivot_table(index=["signal", "stratum"], columns="endpoint",
                       values=["mean_diff_bp", "p"], aggfunc="first")
cat.columns = [f"{a}_{b}" for a, b in cat.columns]
surv = pool[pool.survive].groupby(["signal", "stratum"])["endpoint"].apply(
    lambda s: ",".join(sorted(set(s)))).rename("survives_at")
cat = cat.join(surv)
cat.to_csv(ROOT / "research/q085/q085_p1_horizon_catalog.csv", float_format="%.4f")

# print any signal significant (joint) at any horizon, full profile
sig_keys = pool[pool.survive][["signal", "stratum"]].drop_duplicates()
print("\nHorizon profiles of joint-FDR survivors (mean_diff_bp @ 1/5/21/31 td, * = survives):")
H = ["fwd1", "fwd5", "fwd21", "fwd31"]
for _, (sg, st) in sig_keys.iterrows():
    sub = pool[(pool.signal == sg) & (pool.stratum == st)].set_index("endpoint")
    prof = []
    for h in H:
        if h in sub.index and not np.isnan(sub.loc[h, "p"]):
            star = "*" if bool(sub.loc[h, "survive"]) else " "
            prof.append(f"{h}:{sub.loc[h,'mean_diff_bp']:+7.1f}bp p={sub.loc[h,'p']:.4f}{star}")
        else:
            prof.append(f"{h}: n/a")
    print(f"  {sg:<16} {st:<12} " + " | ".join(prof))

# also: new-at-longer-horizon signals (significant at 5/21 but not at 1d) — PM point 1
print("\nNew survivors ONLY at 5td/21td (would have been missed by 1d+31d grid):")
s5 = pool[pool.survive & pool.endpoint.isin(["fwd5", "fwd21"])][["signal", "stratum"]]
s1 = pool[pool.survive & pool.endpoint.isin(["fwd1", "fwd31"])][["signal", "stratum"]]
only = set(map(tuple, s5.to_numpy())) - set(map(tuple, s1.to_numpy()))
print(only if only else "(none)")
