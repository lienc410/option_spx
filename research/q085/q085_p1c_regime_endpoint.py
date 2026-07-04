"""Q085 P1c — regime-clock endpoint (PM methodological challenge, 2026-07-03).

PM critique of P1a: fixed fwd-31td windows straddle signal flips -> attenuation
bias toward zero for FAST signals. The "follow every flip" use case is measured
without dilution by the STATE-CONDITIONAL NEXT-DAY return:

  Endpoint-2: mean(ret[t+1] | state_on at close t) - mean(ret[t+1] | stratum)

Applied uniformly to the FULL battery (no per-signal cherry-picking), same
circular-shift permutation inference, BH-FDR q=0.10 within this endpoint batch
(joint accounting with P1a/P1b recorded at P1b close).

Pre-registered additions (before running, PM-nominated family members):
  F1_sma5_10, F1_sma10_20, F1_sma20_50 fast crosses — evaluated on BOTH
  endpoints (fwd31 for parity with P1a, endpoint-2 here).

Extra descriptives per signal: state share, flips/yr (cost realism),
on-state and off-state mean daily returns (off-state must be NEGATIVE to
support a short leg, not merely lower).
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RNG = np.random.default_rng(20260703)
N_PERM, MIN_SHIFT, MIN_N = 2000, 63, 30

ohlc = pd.DataFrame(json.load(open(ROOT / "data/q085_spx_ohlc_cache.json"))["history"])
ohlc["date"] = pd.to_datetime(ohlc["date"])
ohlc = ohlc.set_index("date").sort_index()
sig = pd.read_csv(ROOT / "research/q078/_signal_history_cache.csv", parse_dates=["date"]).set_index("date").sort_index()
xa = json.load(open(ROOT / "data/q085_crossasset_cache.json"))

def series(tk, field="c"):
    s = pd.Series({pd.Timestamp(k): v[field] for k, v in xa[tk].items()}).sort_index()
    return s.reindex(ohlc.index).ffill(limit=5)

df = ohlc.copy()
df["vix"] = sig["vix"].reindex(df.index)
df["stratB"] = ((sig["regime"] == "NORMAL") & (sig["trend"] == "BULLISH")).reindex(df.index).fillna(False)
C, H, L, O, V = df["close"], df["high"], df["low"], df["open"], df["volume"]

def sma(s, n): return s.rolling(n).mean()
def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def wilder_rsi(close, n):
    d = close.diff()
    ru = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    rd = (-d).clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + ru / rd)
def wilder_adx(h, l, c, n=14):
    up, dn = h.diff(), -l.diff()
    plus = ((up > dn) & (up > 0)) * up
    minus = ((dn > up) & (dn > 0)) * dn
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi, mdi = 100*plus.ewm(alpha=1/n, adjust=False).mean()/atr, 100*minus.ewm(alpha=1/n, adjust=False).mean()/atr
    return (100*(pdi-mdi).abs()/(pdi+mdi)).ewm(alpha=1/n, adjust=False).mean()
def pctile_roll(s, n): return s.rolling(n).rank(pct=True) * 100
def swing_low_dist(low, close, k=5):
    is_swing = (low == low.rolling(2*k+1, center=True).min())
    return close / low.where(is_swing).shift(k).ffill() - 1.0

ret1 = C.pct_change()
tr = pd.concat([H-L, (H-C.shift()).abs(), (L-C.shift()).abs()], axis=1).max(axis=1)
atr14 = tr.ewm(alpha=1/14, adjust=False).mean()
rv21 = ret1.rolling(21).std() * np.sqrt(252) * 100
macd_hist = ema(C,12) - ema(C,26) - ema(ema(C,12)-ema(C,26), 9)
bb_mid, bb_sd = sma(C,20), C.rolling(20).std()
pctb = (C - (bb_mid - 2*bb_sd)) / (4*bb_sd)
ibs = (C - L) / (H - L)
body, pbody = C - O, C.shift() - O.shift()
month = pd.Series(df.index.month, index=df.index)
tdom = df.groupby(df.index.to_period("M")).cumcount()
tdom_rev = df[::-1].groupby(df.index[::-1].to_period("M")).cumcount()[::-1]
third_fri = df.index.to_series().apply(lambda d: d.weekday() == 4 and 15 <= d.day <= 21)
opex_week = third_fri.groupby(df.index.to_period("W")).transform("max")
def rs(a, b, n):
    A, B = series(a), series(b)
    return (A/A.shift(n)) / (B/B.shift(n)) - 1.0
spyv = series("SPY", "v")
spyv_z = (spyv - spyv.rolling(20).mean()) / spyv.rolling(20).std()
vix3m, vvix, skew = series("^VIX3M"), series("^VVIX"), series("^SKEW")
tlt, gld, dxy = series("TLT"), series("GLD"), series("DX-Y.NYB")

SIGNALS = {
    "F1_sma5_10":     sma(C,5) > sma(C,10),      # PM-nominated fast cross (new)
    "F1_sma10_20":    sma(C,10) > sma(C,20),     # new
    "F1_sma20_50":    sma(C,20) > sma(C,50),     # new
    "F1_sma200":      C > sma(C,200),
    "F1_sma50_200":   sma(C,50) > sma(C,200),
    "F1_tsmom_12_1":  C.shift(21)/C.shift(252) - 1 > 0,
    "F1_tsmom_3m":    C/C.shift(63) - 1 > 0,
    "F1_tsmom_6m":    C/C.shift(126) - 1 > 0,
    "F1_donchian55":  C > H.shift(1).rolling(55).max(),
    "F1_adx25":       wilder_adx(H,L,C) > 25,
    "F1_macd_pos":    macd_hist > 0,
    "F2_d63low_near":  (C/L.rolling(63).min()-1) < (C/L.rolling(63).min()-1).median(),
    "F2_d126low_near": (C/L.rolling(126).min()-1) < (C/L.rolling(126).min()-1).median(),
    "F2_swing_near":   swing_low_dist(L,C) < swing_low_dist(L,C).median(),
    "F2_near52wh":     (C/C.rolling(252).max()-1) >= -0.02,
    "F2_pmhigh_brk":   C > H.groupby(H.index.to_period("M")).transform("max").shift(21),
    "F2_gap_up":       O > H.shift(1),
    "F3_rsi2_os":     wilder_rsi(C,2) < 10,
    "F3_rsi14_os":    wilder_rsi(C,14) < 30,
    "F3_ibs_low":     ibs < 0.2,
    "F3_pctb_low":    pctb < 0,
    "F3_down3":       (ret1<0) & (ret1.shift(1)<0) & (ret1.shift(2)<0),
    "F3_z5_low":      ((C/C.shift(5)-1) - (C/C.shift(5)-1).rolling(252).mean())
                      / (C/C.shift(5)-1).rolling(252).std() < -1,
    "F4_engulf":      (body>0) & (pbody<0) & (C>O.shift()) & (O<C.shift()),
    "F4_hammer":      ((np.minimum(O,C)-L) > 2*body.abs()) & (ibs>0.5) & (L <= L.rolling(20).min()),
    "F4_rev3":        (ret1.shift(2)<0) & (ret1.shift(1)<0) & (ret1>0),
    "F5_vrp_rich":    (df["vix"]-rv21) > (df["vix"]-rv21).median(),
    "F5_atrp_low":    pctile_roll(atr14,252) < 50,
    "F5_vix5d_dn":    df["vix"].diff(5) < 0,
    "F5_skew_high":   skew > skew.rolling(252).median(),
    "F5_vixts_cont":  (df["vix"]/vix3m) < 1.0,
    "F5_vvix_low":    pctile_roll(vvix,252) < 50,
    "F6_xlu_weak":    rs("XLU","SPY",63) < 0,
    "F6_rsp_strong":  rs("RSP","SPY",63) > 0,
    "F6_tlt_up":      tlt/tlt.shift(21)-1 > 0,
    "F6_hyg_strong":  rs("HYG","IEF",63) > 0,
    "F6_dxy_dn":      dxy/dxy.shift(63)-1 < 0,
    "F6_gld_up":      gld/gld.shift(63)-1 > 0,
    "F7_tom":         (tdom <= 2) | (tdom_rev <= 3),
    "F7_opex_wk":     opex_week.astype(bool),
    "F7_halloween":   month.isin([11,12,1,2,3,4]),
    "F7_monday":      pd.Series(df.index.weekday == 0, index=df.index),
    "F10_spyvol_hi":  spyv_z > 1,
}
VALID = {
    "F5_vixts_cont": vix3m.notna() & df["vix"].notna(),
    "F5_vvix_low":   vvix.notna(),
    "F5_skew_high":  skew.rolling(252).median().notna(),
    "F6_rsp_strong": series("RSP").shift(63).notna(),
    "F6_hyg_strong": series("HYG").shift(63).notna(),
    "F6_tlt_up":     tlt.shift(21).notna(),
    "F6_gld_up":     gld.shift(63).notna(),
    "F6_dxy_dn":     dxy.shift(63).notna(),
    "F6_xlu_weak":   series("XLU").shift(63).notna(),
    "F5_vrp_rich":   rv21.notna() & df["vix"].notna(),
    "F10_spyvol_hi": spyv_z.notna(),
}
default_valid = C.rolling(253).count().eq(253)
nxt = ret1.shift(-1)                       # next-day return, state known at close t
fwd31 = C.shift(-31)/C - 1.0
start = pd.Timestamp("2000-01-01")

def perm_test(cond, valid, strat_mask, outcome):
    m = (valid & strat_mask & outcome.notna() & (df.index >= start)).to_numpy()
    c = cond.fillna(False).astype(bool).to_numpy()
    f = outcome.to_numpy()
    n_on = int((c & m).sum())
    n_off = int((~c & m).sum())
    if n_on < MIN_N or n_off < MIN_N:
        return None
    base = f[m].mean()
    obs = f[c & m].mean() - base
    N = len(c)
    shifts = RNG.integers(MIN_SHIFT, N - MIN_SHIFT, size=N_PERM)
    exceed = sum(1 for s in shifts
                 if (np.roll(c, s) & m).sum() >= MIN_N
                 and abs(f[np.roll(c, s) & m].mean() - base) >= abs(obs))
    p = (1 + exceed) / (1 + N_PERM)
    idx = np.where(m)[0]; mid = idx[len(idx)//2]
    s1, s2 = m.copy(), m.copy(); s1[mid:] = False; s2[:mid] = False
    d1 = f[c & s1].mean() - f[s1].mean() if (c & s1).sum() >= 10 else np.nan
    d2 = f[c & s2].mean() - f[s2].mean() if (c & s2).sum() >= 10 else np.nan
    sign_ok = bool(np.sign(d1) == np.sign(d2)) if not (np.isnan(d1) or np.isnan(d2)) else False
    # regime descriptives
    flips = int((np.diff(c[m].astype(int)) != 0).sum())
    yrs = m.sum() / 252
    on_mean = f[c & m].mean() * 252 * 100    # annualized %
    off_mean = f[~c & m].mean() * 252 * 100
    return dict(n_on=n_on, mean_diff_bp=obs*1e4, p=p, sign_consistent=sign_ok,
                on_ann_pct=on_mean, off_ann_pct=off_mean, flips_per_yr=flips/yrs)

rows = []
stratA = pd.Series(True, index=df.index)
for name, cond in SIGNALS.items():
    valid = VALID.get(name, default_valid)
    for sname, smask in (("A_all", stratA), ("B_norm_bull", df["stratB"])):
        r = perm_test(cond, valid, smask, nxt)
        row = dict(signal=name, stratum=sname, endpoint="nextday")
        row.update(r if r else dict(n_on=0, mean_diff_bp=np.nan, p=np.nan, sign_consistent=False,
                                    on_ann_pct=np.nan, off_ann_pct=np.nan, flips_per_yr=np.nan))
        rows.append(row)
# fwd31 parity for the 3 new crosses
for name in ("F1_sma5_10", "F1_sma10_20", "F1_sma20_50"):
    for sname, smask in (("A_all", stratA), ("B_norm_bull", df["stratB"])):
        r = perm_test(SIGNALS[name], default_valid, smask, fwd31)
        row = dict(signal=name, stratum=sname, endpoint="fwd31")
        row.update(r if r else dict(n_on=0, mean_diff_bp=np.nan, p=np.nan, sign_consistent=False,
                                    on_ann_pct=np.nan, off_ann_pct=np.nan, flips_per_yr=np.nan))
        rows.append(row)

res = pd.DataFrame(rows)
ran = res["p"].notna() & (res["endpoint"] == "nextday")
pv = res.loc[ran, "p"].sort_values()
mt = len(pv)
bh = 0.10 * np.arange(1, mt+1) / mt
passed = pv.to_numpy() <= bh
k = passed.nonzero()[0].max() + 1 if passed.any() else 0
thr = pv.iloc[k-1] if k else 0.0
res["bh_pass"] = ran & (res["p"] <= thr)
res["survive"] = res["bh_pass"] & res["sign_consistent"]
res.to_csv(ROOT / "research/q085/q085_p1c_results.csv", index=False, float_format="%.5f")

print(f"next-day endpoint: {mt} tests, BH thr p<={thr:.5f}, bh_pass={int(res['bh_pass'].sum())}, survive={int(res['survive'].sum())}\n")
cols = ["signal","stratum","n_on","mean_diff_bp","p","on_ann_pct","off_ann_pct","flips_per_yr","sign_consistent"]
print("top 15 by p (next-day endpoint):")
print(res[ran].sort_values("p")[cols].head(15).to_string(index=False))
print("\nfast crosses, both endpoints:")
print(res[res.signal.isin(["F1_sma5_10","F1_sma10_20","F1_sma20_50"])]
      [["signal","stratum","endpoint","n_on","mean_diff_bp","p","on_ann_pct","off_ann_pct","flips_per_yr"]].to_string(index=False))
