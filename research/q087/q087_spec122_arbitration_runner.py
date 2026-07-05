"""SPEC-122 backfilled arbitration — EXECUTABLE (review condition: 5th
results-only offense fixed). Reproduces q087_spec122_backfill_arbitration.csv.

v3 CORRECTION (external review): signal-day set must use production
_effective_iv_signal (IVR/IVP divergence reclassification) — 06-12 and 06-22
are NNB days, NOT carve. Final set n=10, PASS-CALIB 10/10, natural-basis
medians FLAT -10.6% / CALIB -3.8%. Residual -3.5~-3.8% is UNFAVORABLE
(real debit pricier than even CALIB -> thin margins thinner).
"""
import sys, json
sys.path.insert(0, "/Users/lienchen/Documents/workspace/SPX_strat")
import pandas as pd
from pricing import core as PC

R = 0.045
OFF = {"c70": -1.67, "c30": -4.735}
DAYS10 = ["2026-06-01","2026-06-02","2026-06-03","2026-06-04","2026-06-15",
          "2026-06-16","2026-06-18","2026-06-30","2026-07-01","2026-07-02"]
CH = "/Users/lienchen/backups/oldair/data/q041_chains"

def leg(calls, dte_t, delta_t):
    c = calls.assign(dgap=(calls.dte - dte_t).abs())
    e = calls[calls.dte == c.loc[c.dgap.idxmin(), "dte"]]
    e = e.assign(ad=(e.delta.abs() - delta_t).abs())
    return e.loc[e.ad.idxmin()]

def main(spx_hist, vix_map):
    rows = []
    for d in DAYS10:
        df = pd.read_parquet(f"{CH}/{d}/SPX.parquet")
        calls = df[(df.option_type == "CALL") & df.bid.notna() & (df.bid > 0)]
        lg, sh = leg(calls, 90, 0.70), leg(calls, 45, 0.30)
        S, v = spx_hist[d], vix_map[d]
        def model(o70, o30):
            return (PC.call_price(S, float(lg.strike), lg.dte/365, (v+o70)/100, R)
                  - PC.call_price(S, float(sh.strike), sh.dte/365, (v+o30)/100, R))
        rows.append(dict(date=d, real_nat=lg.ask - sh.bid, real_mid=lg.mid - sh.mid,
                         flat=model(0, 0), calib=model(OFF["c70"], OFF["c30"])))
    t = pd.DataFrame(rows)
    t["err_flat_nat%"] = (t.flat/t.real_nat - 1) * 100
    t["err_calib_nat%"] = (t.calib/t.real_nat - 1) * 100
    print(t.round(1).to_string(index=False))
    print(f"natural-basis median: FLAT {t['err_flat_nat%'].median():+.1f}% CALIB {t['err_calib_nat%'].median():+.1f}%")
    return t

if __name__ == "__main__":
    spx_hist = {r["date"]: r["close"] for r in json.load(open(
        "/Users/lienchen/Documents/workspace/SPX_strat/data/q085_spx_ohlc_cache.json"))["history"]}
    import yfinance as yf
    vixs = yf.Ticker("^VIX").history(start="2026-05-25", end="2026-07-06")["Close"]
    main(spx_hist, {ts.date().isoformat(): float(v) for ts, v in vixs.items()})
