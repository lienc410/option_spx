"""Q085 — chain skew calibration (external review C6: reproducibility fix).

Measures 25-35 DTE SPX put IV at |delta|~0.30/0.15/0.50 from real Schwab
chain snapshots and joins daily VIX to derive the CALIB offsets used in
q085_p3_s2bps_robustness.py (scen="CALIB").

Data source: raw chain parquets live on oldair at ~/SPX_strat/data/q041_chains/
<YYYY-MM-DD>/SPX.parquet (operational store, accumulating daily via
com.spxstrat.q041_collect). Run THIS SCRIPT ON OLDAIR (or point CHAIN_ROOT at
a local copy). Derived per-day measurements are committed to the repo as
q085_chain_skew_offsets.csv (2026-05-29..07-02, n=23 VIX-joined days).

Median offsets (2026-07-04 run): d0.30 = VIX-1.97vp, d0.15 = VIX+1.02vp,
ATM = VIX-4.3vp -> CALIB scenario (short VIX-2.0, long VIX+1.0).
Re-measure quarterly and before any degradation-rule resume (review C3).
"""
from __future__ import annotations
import glob
import statistics as st
from pathlib import Path
import pandas as pd

CHAIN_ROOT = Path.home() / "SPX_strat" / "data" / "q041_chains"
OUT = Path(__file__).resolve().parent / "q085_chain_skew_offsets.csv"


def leg_iv(p: pd.DataFrame, target: float, k: int = 3) -> float:
    p = p.assign(ad=p.delta.abs())
    return float(p.iloc[(p.ad - target).abs().argsort()[:k]].iv.mean())


def measure_day(day_dir: str):
    f = glob.glob(day_dir + "/SPX.parquet")
    if not f:
        return None
    df = pd.read_parquet(f[0])
    p = df[(df.option_type == "PUT") & (df.dte >= 25) & (df.dte <= 35)
           & df.iv.notna() & (df.iv > 1)]
    if len(p) < 10:
        return None
    return dict(date=day_dir[-10:], atm_iv=leg_iv(p, 0.50),
                d30_iv=leg_iv(p, 0.30), d15_iv=leg_iv(p, 0.15))


def main():
    rows = [r for d in sorted(glob.glob(str(CHAIN_ROOT / "20*")))
            if (r := measure_day(d))]
    m = pd.DataFrame(rows)
    import yfinance as yf
    vix = yf.Ticker("^VIX").history(start=m.date.min(), end=None)["Close"]
    vix.index = [d.date().isoformat() for d in vix.index]
    m["vix"] = m.date.map(vix)
    m = m.dropna(subset=["vix"])
    for c in ("d30", "d15", "atm"):
        m[f"{c}_off_vs_vix"] = (m[f"{c}_iv"] - m.vix).round(2)
    m.to_csv(OUT, index=False, float_format="%.2f")
    print(m.to_string(index=False))
    print(f"\nmedians vs VIX: d30 {st.median(m.d30_off_vs_vix):+.2f} | "
          f"d15 {st.median(m.d15_off_vs_vix):+.2f} | atm {st.median(m.atm_off_vs_vix):+.2f} "
          f"(n={len(m)})")


if __name__ == "__main__":
    main()
