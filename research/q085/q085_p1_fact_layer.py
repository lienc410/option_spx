"""Q085 P1a — fact-layer battery (Tier 1+2: 40 signals x 2 strata = 80 tests).

Protocol (pre-registered, framing memo section 2/4/6):
  Endpoint : fwd-31td SPX simple return, conditional-mean minus stratum-mean.
  Inference: circular-shift permutation (2000 shifts, min offset 63td) of the
             condition series over the full calendar, stratum mask and returns
             fixed -> handles overlapping-window serial correlation.
             p = (1 + #{|stat_perm| >= |stat_obs|}) / (1 + n_perm), two-sided.
  Survival : BH-FDR q=0.10 over the batch AND same stat sign in both halves
             of the signal's own valid span AND n_cond >= 30 per stratum.
  Batching : P1a = Tier 1+2 (this file). P1b = Tier 3 (FOMC/COT/AAII/PC)
             after data acquisition; joint FDR re-run at P1b close.
  Look-ahead: every feature uses data <= t only (swing lows require 5-bar
             confirmation lag). Median-split binarizations use full-span
             medians — mild in-sample choice, acceptable for association
             testing, flagged for slot layer (walk-forward there).

Strata: A = all trading days 2000+; B = NORMAL x BULLISH (signal cache).
Output: q085_p1_results.csv
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RNG = np.random.default_rng(20260703)
N_PERM, MIN_SHIFT, FWD, MIN_N = 2000, 63, 31, 30

# ---------- load ----------
ohlc = pd.DataFrame(json.load(open(ROOT / "data/q085_spx_ohlc_cache.json"))["history"])
ohlc["date"] = pd.to_datetime(ohlc["date"])
ohlc = ohlc.set_index("date").sort_index()

sig = pd.read_csv(ROOT / "research/q078/_signal_history_cache.csv", parse_dates=["date"])
sig = sig.set_index("date").sort_index()

xa = json.load(open(ROOT / "data/q085_crossasset_cache.json"))
def series(tk, field="c"):
    d = xa[tk]
    s = pd.Series({pd.Timestamp(k): v[field] for k, v in d.items()}).sort_index()
    return s.reindex(ohlc.index).ffill(limit=5)

df = ohlc.copy()
df["vix"] = sig["vix"].reindex(df.index)
df["stratB"] = ((sig["regime"] == "NORMAL") & (sig["trend"] == "BULLISH")).reindex(df.index).fillna(False)
C, H, L, O, V = df["close"], df["high"], df["low"], df["open"], df["volume"]

# ---------- indicator helpers (all data <= t) ----------
def sma(s, n): return s.rolling(n).mean()
def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def wilder_rsi(close, n):
    d = close.diff()
    up, dn = d.clip(lower=0), (-d).clip(lower=0)
    ru = up.ewm(alpha=1 / n, adjust=False).mean()
    rd = dn.ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + ru / rd)

def wilder_adx(h, l, c, n=14):
    up, dn = h.diff(), -l.diff()
    plus = ((up > dn) & (up > 0)) * up
    minus = ((dn > up) & (dn > 0)) * dn
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / n, adjust=False).mean()
    pdi = 100 * plus.ewm(alpha=1 / n, adjust=False).mean() / atr
    mdi = 100 * minus.ewm(alpha=1 / n, adjust=False).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    return dx.ewm(alpha=1 / n, adjust=False).mean()

def pctile_roll(s, n):
    return s.rolling(n).rank(pct=True) * 100

def swing_low_dist(low, close, k=5):
    """Distance to last CONFIRMED swing low (local min, k bars each side, k-bar lag)."""
    is_swing = (low == low.rolling(2 * k + 1, center=True).min())
    lvl = low.where(is_swing).shift(k).ffill()   # known only k bars later
    return close / lvl - 1.0

# ---------- signal battery ----------
ret1 = C.pct_change()
tr = pd.concat([H - L, (H - C.shift()).abs(), (L - C.shift()).abs()], axis=1).max(axis=1)
atr14 = tr.ewm(alpha=1 / 14, adjust=False).mean()
rv21 = ret1.rolling(21).std() * np.sqrt(252) * 100
macd_hist = ema(C, 12) - ema(C, 26) - ema(ema(C, 12) - ema(C, 26), 9)
bb_mid, bb_sd = sma(C, 20), C.rolling(20).std()
pctb = (C - (bb_mid - 2 * bb_sd)) / (4 * bb_sd)
ibs = (C - L) / (H - L)
body, pbody = (C - O), (C.shift() - O.shift())
month = pd.Series(df.index.month, index=df.index)
tdom = df.groupby(df.index.to_period("M")).cumcount()          # trading day of month, 0-based
tdom_rev = df[::-1].groupby(df.index[::-1].to_period("M")).cumcount()[::-1]
third_fri = df.index.to_series().apply(
    lambda d: d.weekday() == 4 and 15 <= d.day <= 21)
opex_week = third_fri.groupby(df.index.to_period("W")).transform("max")

def rs(tk_a, tk_b, n):
    a, b = series(tk_a), series(tk_b)
    return (a / a.shift(n)) / (b / b.shift(n)) - 1.0

spyv = series("SPY", "v")
spyv_z = (spyv - spyv.rolling(20).mean()) / spyv.rolling(20).std()
vix3m, vvix, skew = series("^VIX3M"), series("^VVIX"), series("^SKEW")
tlt, gld, dxy = series("TLT"), series("GLD"), series("DX-Y.NYB")

SIGNALS = {
    # F1 slow trend / momentum
    "F1_sma200":      C > sma(C, 200),
    "F1_sma50_200":   sma(C, 50) > sma(C, 200),
    "F1_tsmom_12_1":  C.shift(21) / C.shift(252) - 1 > 0,
    "F1_tsmom_3m":    C / C.shift(63) - 1 > 0,
    "F1_tsmom_6m":    C / C.shift(126) - 1 > 0,
    "F1_donchian55":  C > H.shift(1).rolling(55).max(),
    "F1_adx25":       wilder_adx(H, L, C) > 25,
    "F1_macd_pos":    macd_hist > 0,
    # F2 price structure
    "F2_d63low_near":  (C / L.rolling(63).min() - 1) < (C / L.rolling(63).min() - 1).median(),
    "F2_d126low_near": (C / L.rolling(126).min() - 1) < (C / L.rolling(126).min() - 1).median(),
    "F2_swing_near":   swing_low_dist(L, C) < swing_low_dist(L, C).median(),
    "F2_near52wh":     (C / C.rolling(252).max() - 1) >= -0.02,
    "F2_pmhigh_brk":   C > H.groupby(H.index.to_period("M")).transform("max").shift(21),
    "F2_gap_up":       O > H.shift(1),
    # F3 short-term mean reversion
    "F3_rsi2_os":     wilder_rsi(C, 2) < 10,
    "F3_rsi14_os":    wilder_rsi(C, 14) < 30,
    "F3_ibs_low":     ibs < 0.2,
    "F3_pctb_low":    pctb < 0,
    "F3_down3":       (ret1 < 0) & (ret1.shift(1) < 0) & (ret1.shift(2) < 0),
    "F3_z5_low":      ((C / C.shift(5) - 1) - (C / C.shift(5) - 1).rolling(252).mean())
                      / (C / C.shift(5) - 1).rolling(252).std() < -1,
    # F4 candlestick controls
    "F4_engulf":      (body > 0) & (pbody < 0) & (C > O.shift()) & (O < C.shift()),
    "F4_hammer":      ((np.minimum(O, C) - L) > 2 * body.abs()) & (ibs > 0.5)
                      & (L <= L.rolling(20).min()),
    "F4_rev3":        (ret1.shift(2) < 0) & (ret1.shift(1) < 0) & (ret1 > 0),
    # F5 volatility structure
    "F5_vrp_rich":    (df["vix"] - rv21) > (df["vix"] - rv21).median(),
    "F5_atrp_low":    pctile_roll(atr14, 252) < 50,
    "F5_vix5d_dn":    df["vix"].diff(5) < 0,
    "F5_skew_high":   skew > skew.rolling(252).median(),
    "F5_vixts_cont":  (df["vix"] / vix3m) < 1.0,
    "F5_vvix_low":    pctile_roll(vvix, 252) < 50,
    # F6 cross-asset risk-on/off
    "F6_xlu_weak":    rs("XLU", "SPY", 63) < 0,
    "F6_rsp_strong":  rs("RSP", "SPY", 63) > 0,
    "F6_tlt_up":      tlt / tlt.shift(21) - 1 > 0,
    "F6_hyg_strong":  rs("HYG", "IEF", 63) > 0,
    "F6_dxy_dn":      dxy / dxy.shift(63) - 1 < 0,
    "F6_gld_up":      gld / gld.shift(63) - 1 > 0,
    # F7 calendar
    "F7_tom":         (tdom <= 2) | (tdom_rev <= 3),
    "F7_opex_wk":     opex_week.astype(bool),
    "F7_halloween":   month.isin([11, 12, 1, 2, 3, 4]),
    "F7_monday":      pd.Series(df.index.weekday == 0, index=df.index),
    # F10 volume proxy
    "F10_spyvol_hi":  spyv_z > 1,
}

# validity mask per signal: non-NaN underlying (booleans lose NaN; recompute)
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
default_valid = C.rolling(253).count().eq(253)  # warmup for 252d features

fwd = C.shift(-FWD) / C - 1.0
start = pd.Timestamp("2000-01-01")

def run_test(cond, valid, strat_mask):
    m = valid & strat_mask & fwd.notna() & (df.index >= start)
    m = m.to_numpy()
    c = (cond.fillna(False).astype(bool)).to_numpy()
    f = fwd.to_numpy()
    n_cond = int((c & m).sum())
    if n_cond < MIN_N:
        return None
    base = f[m].mean()
    obs = f[c & m].mean() - base
    # circular-shift permutation of condition over full calendar
    N = len(c)
    shifts = RNG.integers(MIN_SHIFT, N - MIN_SHIFT, size=N_PERM)
    exceed = 0
    for s in shifts:
        cs = np.roll(c, s)
        sel = cs & m
        if sel.sum() < MIN_N:
            continue
        if abs(f[sel].mean() - base) >= abs(obs):
            exceed += 1
    p = (1 + exceed) / (1 + N_PERM)
    # IS/OOS sign consistency over the signal's own valid span
    idx = np.where(m)[0]
    mid = idx[len(idx) // 2]
    s1, s2 = m.copy(), m.copy()
    s1[mid:] = False
    s2[:mid] = False
    d1 = f[c & s1].mean() - f[s1].mean() if (c & s1).sum() >= 10 else np.nan
    d2 = f[c & s2].mean() - f[s2].mean() if (c & s2).sum() >= 10 else np.nan
    sign_ok = bool(np.sign(d1) == np.sign(d2)) if not (np.isnan(d1) or np.isnan(d2)) else False
    # tail: p10 of conditional vs stratum
    p10c, p10b = np.quantile(f[c & m], 0.10), np.quantile(f[m], 0.10)
    return dict(n_cond=n_cond, n_strat=int(m.sum()), mean_diff_pp=obs * 100, p=p,
                is_diff_pp=(0 if np.isnan(d1) else d1 * 100),
                oos_diff_pp=(0 if np.isnan(d2) else d2 * 100),
                sign_consistent=sign_ok, p10_diff_pp=(p10c - p10b) * 100)

rows = []
stratA = pd.Series(True, index=df.index)
for name, cond in SIGNALS.items():
    valid = VALID.get(name, default_valid)
    for sname, smask in (("A_all", stratA), ("B_norm_bull", df["stratB"])):
        r = run_test(cond, valid, smask)
        rows.append(dict(signal=name, stratum=sname,
                         **(r if r else dict(n_cond=0, n_strat=0, mean_diff_pp=np.nan,
                                             p=np.nan, is_diff_pp=np.nan, oos_diff_pp=np.nan,
                                             sign_consistent=False, p10_diff_pp=np.nan))))
res = pd.DataFrame(rows)

# BH-FDR q=0.10 over tests actually run
ran = res["p"].notna()
pv = res.loc[ran, "p"].sort_values()
m_tests = len(pv)
bh_line = 0.10 * (np.arange(1, m_tests + 1)) / m_tests
passed = pv.to_numpy() <= bh_line
k = passed.nonzero()[0].max() + 1 if passed.any() else 0
thresh = pv.iloc[k - 1] if k else 0.0
res["bh_pass"] = ran & (res["p"] <= thresh)
res["survive"] = res["bh_pass"] & res["sign_consistent"] & (res["n_cond"] >= MIN_N)

res.to_csv(ROOT / "research/q085/q085_p1_results.csv", index=False, float_format="%.5f")
print(f"tests run: {m_tests}/{len(res)}  BH threshold p<={thresh:.5f}  bh_pass: {int(res['bh_pass'].sum())}")
print(f"SURVIVORS (bh + sign-consistent + n>=30): {int(res['survive'].sum())}\n")
cols = ["signal", "stratum", "n_cond", "mean_diff_pp", "p", "is_diff_pp", "oos_diff_pp", "p10_diff_pp"]
surv = res[res["survive"]].sort_values("p")
print(surv[cols].to_string(index=False))
print("\n--- near-misses (bh_pass but sign-inconsistent) ---")
nm = res[res["bh_pass"] & ~res["survive"]]
print(nm[cols].to_string(index=False) if len(nm) else "(none)")
