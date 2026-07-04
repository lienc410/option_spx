"""Q085 P1d — joint FDR (P1a+P1c pooled, 159 tests) + pre-registered
cross-index replication of F3 representatives (RSI(2)<10, down3).

Amendment recorded BEFORE running (2026-07-03): replication endpoint updated
from fwd-31td to next-day return per P1c (the family's natural horizon);
representatives unchanged from P1a memo section 3 (RSI2, down3); gate
unchanged (>=2/3 indices same-sign raw p<0.05 per representative).

Result (2026-07-03 run): joint survivors = 15 (F3-dominated, both endpoints;
plus F1_sma5_10 and F4_rev3 with NEGATIVE signs — same short-horizon MR
phenomenon expressed inversely). Replication PASS:
  ^NDX  rsi2 +35.7bp p=0.0005 | down3 +39.9bp p=0.0005
  ^RUT  rsi2 +14.3bp p=0.0090 | down3 +13.0bp p=0.0335
  ^GDAXI rsi2 +9.0bp p=0.0755 | down3 +10.7bp p=0.0510  (same sign, misses .05)
F3 family ADMITTED to slot layer with K3 doubled ($4,000/yr).
"""
# (executable form of the inline run; see git history of this commit for the
#  exact session transcript. Re-run reproduces with seed 20260703.)
import numpy as np, pandas as pd, yfinance as yf

RNG = np.random.default_rng(20260703)

def wilder_rsi(close, n):
    d = close.diff()
    ru = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    rd = (-d).clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1+ru/rd)

def perm_p(cond, f, n_perm=2000, min_shift=63):
    m = ~np.isnan(f) & ~np.isnan(cond.astype(float))
    cb = cond.astype(bool) & m
    base = f[m].mean(); obs = f[cb].mean() - base
    N = len(f); ex = 0
    for s in RNG.integers(min_shift, N-min_shift, size=n_perm):
        cs = np.roll(cond.astype(bool), s) & m
        if cs.sum() >= 30 and abs(f[cs].mean()-base) >= abs(obs):
            ex += 1
    return obs, (1+ex)/(1+n_perm), int(cb.sum())

if __name__ == "__main__":
    from pathlib import Path
    ROOT = Path(__file__).resolve().parents[2]
    a = pd.read_csv(ROOT/"research/q085/q085_p1_results.csv"); a["batch"] = "P1a_fwd31"
    c = pd.read_csv(ROOT/"research/q085/q085_p1c_results.csv")
    c = c[c.endpoint == "nextday"].copy(); c["batch"] = "P1c_nextday"
    pool = pd.concat([a[["signal","stratum","p","sign_consistent","batch"]],
                      c[["signal","stratum","p","sign_consistent","batch"]]])
    pool = pool[pool.p.notna()].sort_values("p").reset_index(drop=True)
    m = len(pool); bh = 0.10*np.arange(1, m+1)/m
    passed = pool.p.to_numpy() <= bh
    k = passed.nonzero()[0].max()+1 if passed.any() else 0
    thr = pool.p.iloc[k-1] if k else 0
    print(pool[(pool.p <= thr) & pool.sign_consistent].to_string(index=False))
    for tk in ["^NDX", "^RUT", "^GDAXI"]:
        df = yf.Ticker(tk).history(start="1999-01-01", end="2026-07-04", auto_adjust=True)
        Cx = df["Close"]; r1 = Cx.pct_change(); nxt = r1.shift(-1)
        mask = Cx.index >= "2000-01-01"
        for nm, cd in {"rsi2_os": wilder_rsi(Cx,2) < 10,
                       "down3": (r1<0)&(r1.shift(1)<0)&(r1.shift(2)<0)}.items():
            obs, p, n = perm_p(cd[mask].to_numpy(), nxt[mask].to_numpy())
            print(tk, nm, n, round(obs*1e4,2), p)
