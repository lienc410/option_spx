"""Q068 Drill — Re-check 2026-05-07 and 2026-05-12 (correct PM dates)
2026-05-13

PM clarified 5/7 and 5/12 are 2026 dates (recent dips), not 2025.
Need to verify whether these days match the low-vol bullish pullback override.
"""
import sys
import pickle
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# Load data
spx_pkl = REPO / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
vix_pkl = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"
spx = pickle.loads(spx_pkl.read_bytes())
vix = pickle.loads(vix_pkl.read_bytes())
spx.index = pd.to_datetime(spx.index).tz_localize(None)
vix.index = pd.to_datetime(vix.index).tz_localize(None)

features = pd.DataFrame({"spx": spx["Close"]})
features["vix"]  = vix["Close"].reindex(features.index).ffill()
features["ma5"]  = features["spx"].rolling(5).mean()
features["ma10"] = features["spx"].rolling(10).mean()
features["ma50"] = features["spx"].rolling(50).mean()
features["spx_5d_return"] = features["spx"].pct_change(5)

def rolling_ivp(s, w):
    arr = s.values
    out = np.full(len(arr), np.nan)
    for i in range(w, len(arr)):
        out[i] = (arr[i - w : i] < arr[i]).mean() * 100.0
    return pd.Series(out, index=s.index)

features["ivp_252"] = rolling_ivp(features["vix"], 252)
features = features.dropna()

# Override conditions
BLOCK_THRESHOLD = 55.0
VIX_LOW_MAX     = 20.0
MA_LOWER_PCT    = 0.99
MA_UPPER_PCT    = 1.005
RETURN_5D_MIN   = -0.02

print(f"{'='*100}")
print("  CORRECT PM DATES (2026): 2026-05-07 and 2026-05-12, with context days")
print(f"{'='*100}\n")

# Look at the actual dates PM mentioned + context days
check_dates = ["2026-04-30", "2026-05-01", "2026-05-04", "2026-05-05", "2026-05-06",
               "2026-05-07", "2026-05-08", "2026-05-11", "2026-05-12", "2026-05-13"]

print(f"{'Date':<12} {'SPX':>6} {'VIX':>6} {'IVP':>5} {'MA5':>6} {'MA10':>6} "
      f"{'MA50':>6} {'5dRet':>6} {'BL':>4} {'VIX<20':>6} {'>MA50':>6} "
      f"{'MA10dip':>7} {'MA5dip':>6} {'5dRet>-2%':>9} {'P6A':>4} {'P6B':>4} {'P6C':>4}")
print("-" * 130)

for dt in check_dates:
    ts = pd.Timestamp(dt)
    if ts not in features.index:
        print(f"  {dt}: not in features (non-trading day)")
        continue
    row = features.loc[ts]
    spx_v = row["spx"]; vix_v = row["vix"]; ivp = row["ivp_252"]
    ma5 = row["ma5"]; ma10 = row["ma10"]; ma50 = row["ma50"]
    ret5d = row["spx_5d_return"] * 100

    cond_vix      = vix_v < VIX_LOW_MAX
    cond_bullish  = spx_v > ma50
    cond_ma10_dip = (spx_v >= ma10 * MA_LOWER_PCT) and (spx_v <= ma10 * MA_UPPER_PCT)
    cond_ma5_dip  = (spx_v >= ma5  * MA_LOWER_PCT) and (spx_v <= ma5  * MA_UPPER_PCT)
    cond_5d_ret   = ret5d > RETURN_5D_MIN * 100
    bl_block = ivp >= BLOCK_THRESHOLD

    p6a_allow = bl_block and cond_vix and cond_bullish and cond_ma10_dip and cond_5d_ret
    p6b_allow = bl_block and cond_vix and cond_bullish and cond_ma5_dip  and cond_5d_ret
    p6c_allow = p6a_allow or p6b_allow

    print(f"{dt:<12} {spx_v:>6.0f} {vix_v:>6.1f} {ivp:>5.1f} "
          f"{ma5:>6.0f} {ma10:>6.0f} {ma50:>6.0f} {ret5d:>+5.1f}% "
          f"{'BLK' if bl_block else 'OK':>4} "
          f"{'Y' if cond_vix else 'N':>6} {'Y' if cond_bullish else 'N':>6} "
          f"{'Y' if cond_ma10_dip else 'N':>7} {'Y' if cond_ma5_dip else 'N':>6} "
          f"{'Y' if cond_5d_ret else 'N':>9} "
          f"{'Y' if p6a_allow else '-':>4} {'Y' if p6b_allow else '-':>4} {'Y' if p6c_allow else '-':>4}")

# Also check V5c (Round 1 simple) for these dates
print(f"\n{'='*100}")
print("  V5c (Round 1 simple: bypass IVP if SPX <= MA10) decisions on same days")
print(f"{'='*100}\n")
print(f"{'Date':<12} {'SPX':>6} {'MA10':>6} {'SPX<=MA10?':>10} {'V5c_allow?':>10}")
for dt in check_dates:
    ts = pd.Timestamp(dt)
    if ts not in features.index:
        continue
    row = features.loc[ts]
    spx_v = row["spx"]; ma10 = row["ma10"]; ivp = row["ivp_252"]
    below_ma10 = spx_v <= ma10
    bl_block = ivp >= BLOCK_THRESHOLD
    v5c_allow = bl_block and below_ma10
    print(f"{dt:<12} {spx_v:>6.0f} {ma10:>6.0f} {'Y' if below_ma10 else 'N':>10} "
          f"{'Y' if v5c_allow else '-':>10}")

# Also check 2026-02-25 in same view for compare
print(f"\n{'='*100}")
print("  Compare to 2026-02-25 (known bad trade — must be blocked)")
print(f"{'='*100}\n")
for dt in ["2026-02-24", "2026-02-25", "2026-02-26"]:
    ts = pd.Timestamp(dt)
    if ts not in features.index:
        continue
    row = features.loc[ts]
    spx_v = row["spx"]; vix_v = row["vix"]; ivp = row["ivp_252"]
    ma5 = row["ma5"]; ma10 = row["ma10"]; ma50 = row["ma50"]
    ret5d = row["spx_5d_return"] * 100
    bl_block = ivp >= BLOCK_THRESHOLD
    below_ma10 = spx_v <= ma10
    v5c_allow = bl_block and below_ma10
    print(f"  {dt}: SPX={spx_v:.0f} VIX={vix_v:.1f} IVP={ivp:.1f} "
          f"MA10={ma10:.0f} 5dRet={ret5d:+.1f}%  "
          f"SPX<=MA10={below_ma10}  V5c_allow={v5c_allow}  "
          f"BL_block={bl_block}")
