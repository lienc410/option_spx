"""Q085 P1g — OpEx-week 5td replication (corrected-standard treatment).

Context: PM challenged the "must hold at all horizons" phrasing (2026-07-03).
Corrected admission standard = joint-FDR pass at ANY horizon + half-sample
sign consistency (+ replication for isolated/post-hoc cases). Under that
standard F7_opex_wk B@5td deserved the replication protocol, not ad-hoc
dismissal ("no adjacent-horizon support" was an invalid argument — a 5-day
calendar effect needn't show at 1d/21d).

Result (2026-07-03): same sign everywhere, formally FAILS the gate:
  ^NDX -37.4bp p=0.400 | ^RUT -47.7bp p=0.275 | ^DJI -36.5bp p=0.205
  (SPX original: -38.1bp p=0.004)
Gate (>=2/3 at p<0.05): FAIL -> stays out, by protocol. Footnote: correlated
US indices are weak independent evidence for a shared-calendar effect; the
stronger test would be GDAXI's own expiry calendar. Given ~-38bp/5td slot
value is minor (skip-OpEx-week entry tweak), further pursuit deprioritized.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import q085_battery_lib as B
import numpy as np, yfinance as yf

RNG = np.random.default_rng(20260703)
if __name__ == "__main__":
    opex, stratB = B.SIGNALS["F7_opex_wk"], B.df["stratB"]
    for tk in ["^NDX", "^RUT", "^DJI"]:
        px = yf.Ticker(tk).history(start="1999-01-01", end="2026-07-04", auto_adjust=True)["Close"]
        px.index = px.index.tz_localize(None)
        px = px.reindex(B.df.index).ffill(limit=3)
        fwd5 = (px.shift(-5) / px - 1)
        mask = stratB & (B.df.index >= "2000-01-01")
        f = fwd5.where(mask).to_numpy()
        c = (opex & mask).to_numpy()
        m = ~np.isnan(f)
        base = f[m].mean(); obs = f[c & m].mean() - base
        ex = 0
        for s in RNG.integers(63, len(c) - 63, size=2000):
            cs = np.roll(c, s) & m
            if cs.sum() >= 30 and abs(f[cs].mean() - base) >= abs(obs):
                ex += 1
        print(tk, int((c & m).sum()), round(obs * 1e4, 1), "bp p=", (1 + ex) / 2001)
