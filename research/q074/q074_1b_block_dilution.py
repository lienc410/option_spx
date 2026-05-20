"""Q074.1b — Block-rate dilution hypothesis test.

PM observation (2026-05-19):
  Higher Block% in a year → LOWER actual fwd stress rate on blocked days.
  i.e., the gate dilutes itself when it fires too often.

Mathematical claim:
  When VIX has been persistently low → IVP_252 fires on "modestly less calm"
  days that aren't dangerous in absolute terms. The relative signal loses
  meaning when absolute volatility is low.

Tests:
  1. Compute (block_rate, stress_lift) per year across full 26y sample.
     Test Pearson correlation. Expect negative.
  2. Stratify by avg VIX of blocked days. Hypothesis: when avg blocked-VIX
     is low absolute (<15), gate is noise; when ≥15, gate is signal.
  3. New gate candidate F: IVP_252 >= 55 AND VIX >= 15 (block only when
     BOTH relative AND absolute elevated).
  4. New gate candidate G: VIX absolute percentile vs 5-year window
     (longer baseline → high IVP also means high absolute).

Outputs:
  q074_1b_yearly_block_vs_lift.csv
  q074_1b_blocked_vix_strata.csv
  q074_1b_gate_F_G_comparison.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
OUT = REPO / "research" / "q074"

print("Q074.1b — Block-rate dilution test", flush=True)
print("=" * 70)

# ── Load market features ───────────────────────────────────────────────
from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history
vix_df = fetch_vix_history(period="max")
spx_df = fetch_spx_history(period="max")
vix_df.index = pd.to_datetime(vix_df.index.date)
spx_df.index = pd.to_datetime(spx_df.index.date)

mkt = pd.DataFrame({"vix": vix_df["vix"], "spx_close": spx_df["close"]}).dropna()
combined = pd.read_csv(REPO / "research" / "q073" / "q073_p1_3R_unified_daily_pnl.csv",
                       parse_dates=["date"], index_col="date")
mkt = mkt[(mkt.index >= combined.index.min()) & (mkt.index <= combined.index.max())]

def rolling_percentile(series, window):
    def w(arr):
        if len(arr) < window:
            return np.nan
        cur = arr[-1]
        return (arr[:-1] < cur).mean() * 100.0
    return series.rolling(window).apply(w, raw=True)

mkt["ivp_252"] = rolling_percentile(mkt["vix"], 252)
mkt["ivp_1260"] = rolling_percentile(mkt["vix"], 1260)   # ~5y baseline

mkt["high_20d"] = mkt["spx_close"].rolling(20, min_periods=5).max()
mkt["dd_20d"] = mkt["spx_close"] / mkt["high_20d"] - 1.0
mkt["high_60d"] = mkt["spx_close"].rolling(60, min_periods=10).max()
mkt["dd_60d"] = mkt["spx_close"] / mkt["high_60d"] - 1.0
stress_flag = ((mkt["vix"] >= 22.0) | (mkt["dd_20d"] <= -0.04) | (mkt["dd_60d"] <= -0.04))
mkt["stress_active"] = stress_flag.rolling(3, min_periods=1).max().astype(bool)
mkt["second_leg_active"] = ((mkt["dd_60d"] <= -0.08) & (mkt["vix"] >= 25.0)).astype(bool)
mkt["normal_state"] = (~mkt["stress_active"] & ~mkt["second_leg_active"])

mkt["stress_in_next_10d"] = mkt["stress_active"].shift(-1).rolling(10).max().shift(-9).astype(float)
mkt["stress_in_next_20d"] = mkt["stress_active"].shift(-1).rolling(20).max().shift(-19).astype(float)

df = mkt[mkt["normal_state"]].dropna(subset=["ivp_252", "stress_in_next_10d"]).copy()
df["year"] = df.index.year
df["blocked"] = (df["ivp_252"] >= 55).astype(int)

# ── Test 1: yearly block% vs lift correlation ──────────────────────────
print("\n1. Yearly block% vs lift correlation")
print("-" * 70)

rows = []
for y, sub in df.groupby("year"):
    n = len(sub)
    blocked = sub[sub["blocked"] == 1]
    passed = sub[sub["blocked"] == 0]
    if len(blocked) < 3 or len(passed) < 3:
        continue
    rows.append({
        "year": y,
        "n_normal": n,
        "block_pct": len(blocked) / n * 100,
        "blocked_p_stress_10d": blocked["stress_in_next_10d"].mean() * 100,
        "passed_p_stress_10d":  passed["stress_in_next_10d"].mean() * 100,
        "lift_pp": (blocked["stress_in_next_10d"].mean() - passed["stress_in_next_10d"].mean()) * 100,
        "avg_blocked_vix": blocked["vix"].mean(),
        "avg_year_vix": sub["vix"].mean(),
    })
yearly = pd.DataFrame(rows)
yearly.to_csv(OUT / "q074_1b_yearly_block_vs_lift.csv", index=False)

# Pearson + Spearman
from scipy.stats import pearsonr, spearmanr
pr, pp = pearsonr(yearly["block_pct"], yearly["lift_pp"])
sr, sp = spearmanr(yearly["block_pct"], yearly["lift_pp"])
print(f"  Pearson  corr(block%, lift_pp): r={pr:+.3f}, p={pp:.3f}")
print(f"  Spearman corr(block%, lift_pp): rho={sr:+.3f}, p={sp:.3f}")
print(f"\n  N years (block_n>=3 & passed_n>=3): {len(yearly)}")
print(f"  Median block%: {yearly['block_pct'].median():.1f}")
print(f"  Median lift_pp: {yearly['lift_pp'].median():+.1f}")

# Same test using avg_blocked_vix as predictor of lift
pr2, pp2 = pearsonr(yearly["avg_blocked_vix"], yearly["lift_pp"])
sr2, sp2 = spearmanr(yearly["avg_blocked_vix"], yearly["lift_pp"])
print(f"\n  Pearson  corr(avg_blocked_VIX, lift_pp): r={pr2:+.3f}, p={pp2:.3f}")
print(f"  Spearman corr(avg_blocked_VIX, lift_pp): rho={sr2:+.3f}, p={sp2:.3f}")

print("\n  Full yearly table:")
print(yearly.sort_values("block_pct").to_string(index=False, float_format=lambda x: f"{x:.1f}"))

# ── Test 2: stratify all blocked days by VIX level ─────────────────────
print("\n" + "=" * 70)
print("2. All blocked days stratified by absolute VIX")
print("=" * 70)

blocked_all = df[df["blocked"] == 1].copy()
passed_all = df[df["blocked"] == 0].copy()

def bucket_vix(v):
    if pd.isna(v): return "NA"
    if v < 13: return "1_<13"
    if v < 15: return "2_13-15"
    if v < 17: return "3_15-17"
    if v < 19: return "4_17-19"
    return "5_19-22"

blocked_all["vix_bucket"] = blocked_all["vix"].apply(bucket_vix)
stratify = blocked_all.groupby("vix_bucket", observed=True).agg(
    n=("blocked", "size"),
    p_stress_10d=("stress_in_next_10d", "mean"),
    p_stress_20d=("stress_in_next_20d", "mean"),
    avg_ivp=("ivp_252", "mean"),
).reset_index()
baseline_pass_stress_10d = passed_all["stress_in_next_10d"].mean()
stratify["lift_vs_passed_pp"] = (stratify["p_stress_10d"] - baseline_pass_stress_10d) * 100
stratify.to_csv(OUT / "q074_1b_blocked_vix_strata.csv", index=False)
print(f"\n  Baseline passed-day P(stress 10d): {baseline_pass_stress_10d*100:.1f}%\n")
print(stratify.to_string(index=False, formatters={
    "p_stress_10d": "{:.1%}".format,
    "p_stress_20d": "{:.1%}".format,
    "avg_ivp": "{:.1f}".format,
    "lift_vs_passed_pp": "{:+.1f}".format,
}))

# ── Test 3: Gate F (IVP>=55 AND VIX>=15) vs current ────────────────────
print("\n" + "=" * 70)
print("3. Gate F: IVP_252<55 OR VIX<15  (block only when BOTH elevated)")
print("=" * 70)

df["gate_current"] = (df["ivp_252"] < 55).astype(int)
df["gate_F_vix15"] = ((df["ivp_252"] < 55) | (df["vix"] < 15)).astype(int)
df["gate_F2_vix14"] = ((df["ivp_252"] < 55) | (df["vix"] < 14)).astype(int)
df["gate_G_ivp1260"] = (df["ivp_1260"] < 55).astype(int)
df["gate_H_combo"] = ((df["ivp_252"] < 55) | (df["ivp_1260"] < 30)).astype(int)

gates = {
    "A: IVP_252<55 (current)":    "gate_current",
    "F: IVP_252<55 OR VIX<15":    "gate_F_vix15",
    "F2: IVP_252<55 OR VIX<14":   "gate_F2_vix14",
    "G: IVP_1260<55 (5y window)": "gate_G_ivp1260",
    "H: IVP_252<55 OR IVP_1260<30": "gate_H_combo",
}

rows = []
for label, col in gates.items():
    passed = df[df[col] == 1]
    blocked = df[df[col] == 0]
    rows.append({
        "gate": label,
        "pass_rate_pct": len(passed) / len(df) * 100,
        "passed_p_stress_10d": passed["stress_in_next_10d"].mean(),
        "passed_p_stress_20d": passed["stress_in_next_20d"].mean(),
        "blocked_p_stress_10d": blocked["stress_in_next_10d"].mean() if len(blocked) else np.nan,
        "blocked_p_stress_20d": blocked["stress_in_next_20d"].mean() if len(blocked) else np.nan,
        "n_blocked": len(blocked),
    })
gate_cmp = pd.DataFrame(rows)
gate_cmp.to_csv(OUT / "q074_1b_gate_F_G_comparison.csv", index=False)
print(gate_cmp.to_string(index=False, formatters={
    "pass_rate_pct": "{:.1f}".format,
    "passed_p_stress_10d": "{:.1%}".format,
    "passed_p_stress_20d": "{:.1%}".format,
    "blocked_p_stress_10d": "{:.1%}".format,
    "blocked_p_stress_20d": "{:.1%}".format,
}))

# Marginal stress on added days
print("\n  Marginal stress on added-pass days (gate passes vs current blocks):")
for label, col in gates.items():
    if col == "gate_current": continue
    added = df[(df[col] == 1) & (df["gate_current"] == 0)]
    if len(added) == 0:
        continue
    print(f"    {label}: +{len(added)} days, "
          f"P(stress 10d)={added['stress_in_next_10d'].mean()*100:.1f}%, "
          f"P(stress 20d)={added['stress_in_next_20d'].mean()*100:.1f}%")

# ── Test 4: Gate F pass rate by slow-bull year ─────────────────────────
print("\n" + "=" * 70)
print("4. Slow-bull year pass rate under Gate F variants")
print("=" * 70)
slow_years = [2007, 2017, 2018, 2024, 2025, 2026]
rows = []
for y in slow_years:
    sub = df[df["year"] == y]
    if len(sub) == 0: continue
    rows.append({
        "year": y,
        "n_normal": len(sub),
        "A_current": sub["gate_current"].mean() * 100,
        "F_vix15": sub["gate_F_vix15"].mean() * 100,
        "F2_vix14": sub["gate_F2_vix14"].mean() * 100,
        "G_ivp1260": sub["gate_G_ivp1260"].mean() * 100,
        "H_combo": sub["gate_H_combo"].mean() * 100,
    })
slow = pd.DataFrame(rows)
slow.to_csv(OUT / "q074_1b_slow_year_gate_pass.csv", index=False)
print(slow.to_string(index=False, float_format=lambda x: f"{x:.1f}"))

print("\n" + "=" * 70)
print("Q074.1b done.")
print("=" * 70)
