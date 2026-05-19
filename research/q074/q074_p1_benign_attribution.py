"""Q074 P1 — Benign-regime Attribution (DIAGNOSTIC ONLY).

Per P0:
  - B1-B4 candidate definitions are FROZEN (per 2nd Quant Revision 4)
  - P1 forward returns are for attribution only, NOT signal construction (look-ahead safe)
  - This script reports per-bucket forward PnL distributions for normal-state days

Buckets (PM-anchored 6 features per P0 §3):
  - SPX trend: above MA50 or not
  - MA50 slope: positive (MA50[t] - MA50[t-5] > 0) or negative
  - ddATH: 4 buckets (>0%, -3% to 0%, -6% to -3%, < -6%)
  - VIX absolute: 4 buckets (<15, 15-18, 18-20, 20-22) (only normal-state days where VIX < 22)
  - VIX 5d change: 3 buckets (≤-0.5, -0.5 to +0.5, >+0.5)
  - IVP_252: 4 buckets (<30, 30-55, 55-70, >70)

Output per bucket (computed only on normal-state days, i.e., NOT stress_active AND NOT second_leg_active):
  - count of normal days in bucket
  - avg forward 20d PnL ($)
  - avg forward 63d PnL ($)
  - worst forward 20d PnL
  - hit rate (positive forward 20d %)
  - P(stress trigger within next 10d)
  - P(stress trigger within next 20d)

Outputs:
  q074_p1_attribution_spx_trend.csv
  q074_p1_attribution_ma50_slope.csv
  q074_p1_attribution_ddath.csv
  q074_p1_attribution_vix.csv
  q074_p1_attribution_vix_5d_change.csv
  q074_p1_attribution_ivp.csv
  q074_p1_attribution_summary.md
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

OUT = REPO / "research" / "q074"
NLV = 894_000.0

# Q074 normal-state SPX allocation: per Arch-3 baseline, 80%
# Q1.3R simulator ran SPX at 60% allocation. Scale SPX PnL by 80/60 to approximate
# Arch-3 normal-state PnL.
SCALE_SPX = 0.80 / 0.60   # = 1.333x

print("Q074 P1 — Benign-regime Attribution", flush=True)
print("=" * 70)

# ── Load P1.3R unified-NLV daily series + scale SPX to 80% ─────────────
print("\nLoading P1.3R daily PnL + scaling SPX to 80% allocation...")
combined = pd.read_csv(REPO / "research" / "q073" / "q073_p1_3R_unified_daily_pnl.csv",
                       parse_dates=["date"], index_col="date")
combined["spx_pnl_80"] = combined["spx_pnl"] * SCALE_SPX
print(f"  Loaded {len(combined)} days; SPX PnL scaled {SCALE_SPX:.3f}x to 80% Arch-3 baseline")

# ── Load market features (VIX, SPX, MA50, ddATH, IVP) ──────────────────
print("\nLoading VIX + SPX history for feature calculation...")
from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history
vix_df = fetch_vix_history(period="max")
spx_df = fetch_spx_history(period="max")
vix_df.index = pd.to_datetime(vix_df.index.date)
spx_df.index = pd.to_datetime(spx_df.index.date)

mkt = pd.DataFrame({"vix": vix_df["vix"], "spx_close": spx_df["close"]}).dropna()
mkt = mkt[(mkt.index >= combined.index.min()) & (mkt.index <= combined.index.max())]

# Feature 1: SPX > MA50
mkt["ma50"] = mkt["spx_close"].rolling(50).mean()
mkt["above_ma50"] = (mkt["spx_close"] > mkt["ma50"]).astype(int)

# Feature 2: MA50 slope (5-day change)
mkt["ma50_slope_5d"] = mkt["ma50"] - mkt["ma50"].shift(5)
mkt["ma50_slope_pos"] = (mkt["ma50_slope_5d"] > 0).astype(int)

# Feature 3: ddATH (running ATH since start of sample)
mkt["ath_running"] = mkt["spx_close"].expanding().max()
mkt["ddath"] = mkt["spx_close"] / mkt["ath_running"] - 1.0

# Feature 4: VIX absolute (already loaded)

# Feature 5: VIX 5d change
mkt["vix_5d_change"] = mkt["vix"] - mkt["vix"].shift(5)

# Feature 6: IVP_252 (rolling 252-day percentile of VIX)
def rolling_percentile(series, window=252):
    """% of prior values where series was < today's value"""
    def w(arr):
        if len(arr) < window:
            return np.nan
        cur = arr[-1]
        return (arr[:-1] < cur).mean() * 100.0
    return series.rolling(window).apply(w, raw=True)

print("  Computing IVP_252 (rolling 252-day VIX percentile)...")
mkt["ivp_252"] = rolling_percentile(mkt["vix"], 252)

# Stress / second-leg flags (per SPEC-104 R5/R6, definitions UNCHANGED)
mkt["high_20d"] = mkt["spx_close"].rolling(20, min_periods=5).max()
mkt["dd_20d"] = mkt["spx_close"] / mkt["high_20d"] - 1.0
mkt["high_60d"] = mkt["spx_close"].rolling(60, min_periods=10).max()
mkt["dd_60d"] = mkt["spx_close"] / mkt["high_60d"] - 1.0
stress_flag = ((mkt["vix"] >= 22.0) | (mkt["dd_20d"] <= -0.04) | (mkt["dd_60d"] <= -0.04))
mkt["stress_active"] = stress_flag.rolling(3, min_periods=1).max().astype(bool)
mkt["second_leg_active"] = ((mkt["dd_60d"] <= -0.08) & (mkt["vix"] >= 25.0)).astype(bool)
mkt["normal_state"] = (~mkt["stress_active"] & ~mkt["second_leg_active"])

n_total = len(mkt)
n_normal = mkt["normal_state"].sum()
print(f"\n  Total days: {n_total}")
print(f"  Normal-state days: {n_normal} ({n_normal/n_total*100:.1f}%)")
print(f"  Stress days: {mkt['stress_active'].sum()} ({mkt['stress_active'].mean()*100:.1f}%)")
print(f"  Second-leg days: {mkt['second_leg_active'].sum()} ({mkt['second_leg_active'].mean()*100:.1f}%)")

# ── Compute forward returns (Arch-3 80% SPX BPS PnL) ───────────────────
# Forward 20d cumulative PnL and forward 63d cumulative PnL
combined["fwd_pnl_20d"] = combined["spx_pnl_80"].shift(-1).rolling(20).sum().shift(-19)
combined["fwd_pnl_63d"] = combined["spx_pnl_80"].shift(-1).rolling(63).sum().shift(-62)

# ── Forward stress probability ─────────────────────────────────────────
# P(stress within next N days) for each day
mkt["stress_in_next_10d"] = mkt["stress_active"].shift(-1).rolling(10).max().shift(-9).astype(float)
mkt["stress_in_next_20d"] = mkt["stress_active"].shift(-1).rolling(20).max().shift(-19).astype(float)

# Merge features + forward returns onto normal-state days
df = combined[["spx_pnl_80", "fwd_pnl_20d", "fwd_pnl_63d"]].join(
    mkt[["vix", "above_ma50", "ma50_slope_pos", "ddath",
         "vix_5d_change", "ivp_252", "stress_active", "second_leg_active", "normal_state",
         "stress_in_next_10d", "stress_in_next_20d"]],
    how="left"
)
df_normal = df[df["normal_state"]].dropna(subset=["fwd_pnl_20d", "ivp_252"]).copy()
print(f"  Normal-state days with complete features + forward windows: {len(df_normal)}")

# ── Bucketing helpers ──────────────────────────────────────────────────
def bucket_ddath(d):
    if pd.isna(d): return "NA"
    if d > 0: return "1_pos_or_zero"
    if d > -0.03: return "2_-3pct_to_0"
    if d > -0.06: return "3_-6pct_to_-3pct"
    return "4_below_-6pct"

def bucket_vix(v):
    if pd.isna(v): return "NA"
    if v < 15: return "1_below_15"
    if v < 18: return "2_15_to_18"
    if v < 20: return "3_18_to_20"
    return "4_20_to_22"   # normal-state requires VIX < 22 (stress excludes ≥22)

def bucket_vix_5d_change(c):
    if pd.isna(c): return "NA"
    if c <= -0.5: return "1_falling"
    if c <= 0.5: return "2_flat"
    return "3_rising"

def bucket_ivp(ivp):
    if pd.isna(ivp): return "NA"
    if ivp < 30: return "1_below_30"
    if ivp < 55: return "2_30_to_55"
    if ivp < 70: return "3_55_to_70"
    return "4_above_70"

df_normal["bucket_ddath"] = df_normal["ddath"].apply(bucket_ddath)
df_normal["bucket_vix"] = df_normal["vix"].apply(bucket_vix)
df_normal["bucket_vix5d"] = df_normal["vix_5d_change"].apply(bucket_vix_5d_change)
df_normal["bucket_ivp"] = df_normal["ivp_252"].apply(bucket_ivp)

# ── Aggregator ────────────────────────────────────────────────────────
def aggregate(df_, group_col, out_name):
    g = df_.groupby(group_col, observed=True)
    out = g.agg(
        n_days=("spx_pnl_80", "size"),
        avg_fwd_20d=("fwd_pnl_20d", "mean"),
        median_fwd_20d=("fwd_pnl_20d", "median"),
        worst_fwd_20d=("fwd_pnl_20d", "min"),
        hit_rate=("fwd_pnl_20d", lambda s: (s > 0).mean()),
        avg_fwd_63d=("fwd_pnl_63d", "mean"),
        worst_fwd_63d=("fwd_pnl_63d", "min"),
        p_stress_10d=("stress_in_next_10d", "mean"),
        p_stress_20d=("stress_in_next_20d", "mean"),
    ).reset_index()
    out["avg_fwd_20d_pct_nlv"] = out["avg_fwd_20d"] / NLV * 100
    out["worst_fwd_20d_pct_nlv"] = out["worst_fwd_20d"] / NLV * 100
    out.to_csv(OUT / f"q074_p1_attribution_{out_name}.csv", index=False)
    return out

print("\n" + "=" * 70)
print("Per-feature attribution (normal-state days only)")
print("=" * 70)

pd.set_option("display.width", 200)
pd.set_option("display.float_format", lambda x: f"{x:.3f}")

print("\n── above_ma50 ──")
out_ma50 = aggregate(df_normal, "above_ma50", "spx_trend")
print(out_ma50.to_string(index=False))

print("\n── ma50_slope_pos ──")
out_slope = aggregate(df_normal, "ma50_slope_pos", "ma50_slope")
print(out_slope.to_string(index=False))

print("\n── ddath bucket ──")
out_ddath = aggregate(df_normal, "bucket_ddath", "ddath")
print(out_ddath.to_string(index=False))

print("\n── VIX absolute bucket ──")
out_vix = aggregate(df_normal, "bucket_vix", "vix")
print(out_vix.to_string(index=False))

print("\n── VIX 5d change bucket ──")
out_vix5 = aggregate(df_normal, "bucket_vix5d", "vix_5d_change")
print(out_vix5.to_string(index=False))

print("\n── IVP_252 bucket ──")
out_ivp = aggregate(df_normal, "bucket_ivp", "ivp")
print(out_ivp.to_string(index=False))

# ── Joint bucket: B1 strict full stack ─────────────────────────────────
# B1 strict criteria (per P0 §3.B1):
#   SPX > MA50 AND MA50_slope > 0 AND ddATH > -3% AND VIX < 20
#   AND VIX_5d_change ≤ +1.0 AND IVP < 55
print("\n" + "=" * 70)
print("B1-strict signal: full feature stack (informational, not a candidate change)")
print("=" * 70)
df_normal["b1_strict_signal"] = (
    (df_normal["above_ma50"] == 1)
    & (df_normal["ma50_slope_pos"] == 1)
    & (df_normal["ddath"] > -0.03)
    & (df_normal["vix"] < 20)
    & (df_normal["vix_5d_change"] <= 1.0)
    & (df_normal["ivp_252"] < 55)
).astype(int)

df_normal["b2_moderate_signal"] = (
    (df_normal["above_ma50"] == 1)
    & (df_normal["ddath"] > -0.04)
    & (df_normal["vix"] < 22)
    & (df_normal["vix_5d_change"] <= 1.5)
    & (df_normal["ivp_252"] < 55)
).astype(int)

for label, col in [("B1 strict", "b1_strict_signal"), ("B2 moderate", "b2_moderate_signal")]:
    on = df_normal[df_normal[col] == 1]
    off = df_normal[df_normal[col] == 0]
    pct = len(on) / len(df_normal) * 100
    print(f"\n{label}: {len(on)}/{len(df_normal)} ({pct:.1f}%) normal days satisfy signal")
    print(f"  ON  : avg fwd 20d ${on['fwd_pnl_20d'].mean():,.0f} ({on['fwd_pnl_20d'].mean()/NLV*100:+.3f}%), "
          f"hit_rate {(on['fwd_pnl_20d']>0).mean()*100:.1f}%, "
          f"P(stress 10d) {on['stress_in_next_10d'].mean()*100:.1f}%, "
          f"P(stress 20d) {on['stress_in_next_20d'].mean()*100:.1f}%")
    print(f"  OFF : avg fwd 20d ${off['fwd_pnl_20d'].mean():,.0f} ({off['fwd_pnl_20d'].mean()/NLV*100:+.3f}%), "
          f"hit_rate {(off['fwd_pnl_20d']>0).mean()*100:.1f}%, "
          f"P(stress 10d) {off['stress_in_next_10d'].mean()*100:.1f}%, "
          f"P(stress 20d) {off['stress_in_next_20d'].mean()*100:.1f}%")

# Save joint signal frequencies
joint_summary = []
for label, col in [("B1_strict", "b1_strict_signal"), ("B2_moderate", "b2_moderate_signal")]:
    on = df_normal[df_normal[col] == 1]
    off = df_normal[df_normal[col] == 0]
    joint_summary.append({
        "signal": label,
        "active_days": len(on),
        "active_pct": len(on) / len(df_normal) * 100,
        "avg_fwd_20d_pct_nlv_ON": on["fwd_pnl_20d"].mean() / NLV * 100,
        "avg_fwd_20d_pct_nlv_OFF": off["fwd_pnl_20d"].mean() / NLV * 100,
        "delta_fwd_20d_pct_nlv": (on["fwd_pnl_20d"].mean() - off["fwd_pnl_20d"].mean()) / NLV * 100,
        "hit_rate_ON": (on["fwd_pnl_20d"] > 0).mean(),
        "hit_rate_OFF": (off["fwd_pnl_20d"] > 0).mean(),
        "p_stress_10d_ON": on["stress_in_next_10d"].mean(),
        "p_stress_10d_OFF": off["stress_in_next_10d"].mean(),
        "p_stress_20d_ON": on["stress_in_next_20d"].mean(),
        "p_stress_20d_OFF": off["stress_in_next_20d"].mean(),
    })
pd.DataFrame(joint_summary).to_csv(OUT / "q074_p1_attribution_joint_signals.csv", index=False)

print("\n" + "=" * 70)
print("P1 done. CSVs written to research/q074/")
print("=" * 70)
print("\nReminder: P1 is DIAGNOSTIC ONLY (per P0 + 2nd Quant Revision 4).")
print("Do NOT derive new candidate definitions from these buckets.")
print("B1-B4 remain FROZEN. Proceed to P2 with B0/B1/B2/B3/B4 only.")
