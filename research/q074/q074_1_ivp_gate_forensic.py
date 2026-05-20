"""Q074.1 — IVP > 55 gate forensic.

PM observation (2026-05-18):
  IVP > 55 block is unevenly distributed across years:
    2007 / 2018:  ~66% of normal days blocked (pre-crisis low VIX)
    2024 / 2026:  32% / 53% blocked (slow bull → high relative IVP)
    2008-2010 / 2021 / 2023: ~0% (true stress or VIX falling from high)

  Concern: in slow-bull years (2024/2026), half of normal days blocked but
  are they ACTUALLY dangerous? Or just artifact of low-VIX baseline making
  modest IV bumps look "high"?

This forensic answers:
  1. Per-year breakdown of IVP > 55 normal days and their actual fwd stress hit-rate
  2. Compare "blocked but safe" vs "blocked and stress arrived" by year
  3. Test alternative gates:
     a. VIX-absolute escape: IVP<55 OR VIX<16  (only block IVP>55 when VIX≥16)
     b. IVP_63 (shorter trailing window, adapts to low-VIX new normal)

Output:
  q074_1_ivp_per_year.csv             — yearly distribution
  q074_1_blocked_stress_breakdown.csv — IVP>55 days: actual fwd stress
  q074_1_alt_gates_comparison.csv     — alt gate frequency + actual stress
  q074_1_forensic_memo.md             — narrative
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

OUT = REPO / "research" / "q074"

print("Q074.1 — IVP > 55 gate forensic", flush=True)
print("=" * 70)

# ── Load combined PnL + market features ────────────────────────────────
combined = pd.read_csv(REPO / "research" / "q073" / "q073_p1_3R_unified_daily_pnl.csv",
                       parse_dates=["date"], index_col="date")

from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history
vix_df = fetch_vix_history(period="max")
spx_df = fetch_spx_history(period="max")
vix_df.index = pd.to_datetime(vix_df.index.date)
spx_df.index = pd.to_datetime(spx_df.index.date)

mkt = pd.DataFrame({"vix": vix_df["vix"], "spx_close": spx_df["close"]}).dropna()
mkt = mkt[(mkt.index >= combined.index.min()) & (mkt.index <= combined.index.max())]

mkt["ma50"] = mkt["spx_close"].rolling(50).mean()
mkt["above_ma50"] = (mkt["spx_close"] > mkt["ma50"]).astype(int)
mkt["ath_running"] = mkt["spx_close"].expanding().max()
mkt["ddath"] = mkt["spx_close"] / mkt["ath_running"] - 1.0
mkt["vix_5d_change"] = mkt["vix"] - mkt["vix"].shift(5)

def rolling_percentile(series, window):
    def w(arr):
        if len(arr) < window:
            return np.nan
        cur = arr[-1]
        return (arr[:-1] < cur).mean() * 100.0
    return series.rolling(window).apply(w, raw=True)

print("Computing IVP_252 and IVP_63...")
mkt["ivp_252"] = rolling_percentile(mkt["vix"], 252)
mkt["ivp_63"]  = rolling_percentile(mkt["vix"], 63)

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

# Normal-state days only, with both IVP measures available
df = mkt[mkt["normal_state"]].dropna(subset=["ivp_252", "ivp_63"]).copy()
df["year"] = df.index.year
df["ivp252_ge_55"] = (df["ivp_252"] >= 55).astype(int)
df["ivp63_ge_55"]  = (df["ivp_63"]  >= 55).astype(int)

print(f"Total normal days with IVP_252 + IVP_63: {len(df)}")
print(f"  IVP_252 >= 55: {df['ivp252_ge_55'].sum()} ({df['ivp252_ge_55'].mean()*100:.1f}%)")
print(f"  IVP_63  >= 55: {df['ivp63_ge_55'].sum()} ({df['ivp63_ge_55'].mean()*100:.1f}%)")

# ── 1. Yearly distribution ─────────────────────────────────────────────
print("\n" + "=" * 70)
print("1. Per-year IVP > 55 block rate (normal days)")
print("=" * 70)

yearly = df.groupby("year").agg(
    n_normal=("ivp252_ge_55", "size"),
    n_blocked=("ivp252_ge_55", "sum"),
    avg_vix=("vix", "mean"),
    avg_ivp252=("ivp_252", "mean"),
).reset_index()
yearly["block_pct"] = yearly["n_blocked"] / yearly["n_normal"] * 100

# For blocked days only: what fraction actually saw stress within 10d / 20d?
blocked_stress = df[df["ivp252_ge_55"] == 1].groupby("year").agg(
    blocked_p_stress_10d=("stress_in_next_10d", "mean"),
    blocked_p_stress_20d=("stress_in_next_20d", "mean"),
).reset_index()
yearly = yearly.merge(blocked_stress, on="year", how="left")

# For passed days (IVP<55): baseline forward stress rate
passed_stress = df[df["ivp252_ge_55"] == 0].groupby("year").agg(
    passed_p_stress_10d=("stress_in_next_10d", "mean"),
    passed_p_stress_20d=("stress_in_next_20d", "mean"),
).reset_index()
yearly = yearly.merge(passed_stress, on="year", how="left")

yearly["fp_rate_10d"] = 1 - yearly["blocked_p_stress_10d"]   # blocked but no stress
yearly["block_lift_10d"] = yearly["blocked_p_stress_10d"] - yearly["passed_p_stress_10d"]
yearly.to_csv(OUT / "q074_1_ivp_per_year.csv", index=False)

print(yearly.to_string(
    index=False,
    formatters={
        "block_pct": "{:.1f}".format,
        "avg_vix": "{:.1f}".format,
        "avg_ivp252": "{:.1f}".format,
        "blocked_p_stress_10d": "{:.1%}".format,
        "blocked_p_stress_20d": "{:.1%}".format,
        "passed_p_stress_10d": "{:.1%}".format,
        "passed_p_stress_20d": "{:.1%}".format,
        "fp_rate_10d": "{:.1%}".format,
        "block_lift_10d": "{:+.1%}".format,
    },
))

# ── 2. Blocked-day forward stress: full sample vs slow-bull years ───────
print("\n" + "=" * 70)
print("2. Blocked-day forward stress: full vs slow-bull subset")
print("=" * 70)

SLOW_BULL_YEARS = [2007, 2017, 2018, 2024, 2025, 2026]   # PM-flagged + 2017/2025 similar profile
def label(y):
    return "slow_bull" if y in SLOW_BULL_YEARS else "other"

df["regime_label"] = df["year"].apply(label)
blocked = df[df["ivp252_ge_55"] == 1].copy()
breakdown = blocked.groupby("regime_label").agg(
    n_blocked=("ivp252_ge_55", "size"),
    p_stress_10d=("stress_in_next_10d", "mean"),
    p_stress_20d=("stress_in_next_20d", "mean"),
    avg_vix=("vix", "mean"),
).reset_index()
breakdown["fp_rate_10d"] = 1 - breakdown["p_stress_10d"]
breakdown.to_csv(OUT / "q074_1_blocked_stress_breakdown.csv", index=False)
print(breakdown.to_string(index=False, formatters={
    "p_stress_10d": "{:.1%}".format,
    "p_stress_20d": "{:.1%}".format,
    "avg_vix": "{:.1f}".format,
    "fp_rate_10d": "{:.1%}".format,
}))

# ── 3. Alternative gate comparison ─────────────────────────────────────
print("\n" + "=" * 70)
print("3. Alternative gate comparison (normal days)")
print("=" * 70)

# Gate A: current — IVP_252 < 55
df["gate_current"] = (df["ivp_252"] < 55).astype(int)

# Gate B: IVP_252 < 55 OR VIX < 16  (absolute VIX escape valve)
df["gate_b_vix16"] = ((df["ivp_252"] < 55) | (df["vix"] < 16)).astype(int)

# Gate C: IVP_252 < 55 OR VIX < 18
df["gate_c_vix18"] = ((df["ivp_252"] < 55) | (df["vix"] < 18)).astype(int)

# Gate D: IVP_63 < 55 (shorter window)
df["gate_d_ivp63"] = (df["ivp_63"] < 55).astype(int)

# Gate E: IVP_63 < 55 OR VIX < 16
df["gate_e_combo"] = ((df["ivp_63"] < 55) | (df["vix"] < 16)).astype(int)

gates = ["gate_current", "gate_b_vix16", "gate_c_vix18", "gate_d_ivp63", "gate_e_combo"]
gate_labels = {
    "gate_current":  "A: IVP252<55 (current)",
    "gate_b_vix16":  "B: IVP252<55 OR VIX<16",
    "gate_c_vix18":  "C: IVP252<55 OR VIX<18",
    "gate_d_ivp63":  "D: IVP63<55",
    "gate_e_combo":  "E: IVP63<55 OR VIX<16",
}

rows = []
for g in gates:
    passed = df[df[g] == 1]
    blocked = df[df[g] == 0]
    rows.append({
        "gate": gate_labels[g],
        "pass_rate_pct": len(passed) / len(df) * 100,
        "passed_p_stress_10d": passed["stress_in_next_10d"].mean(),
        "passed_p_stress_20d": passed["stress_in_next_20d"].mean(),
        "blocked_p_stress_10d": blocked["stress_in_next_10d"].mean() if len(blocked) else np.nan,
        "blocked_p_stress_20d": blocked["stress_in_next_20d"].mean() if len(blocked) else np.nan,
        "n_blocked": len(blocked),
    })

gate_cmp = pd.DataFrame(rows)
gate_cmp.to_csv(OUT / "q074_1_alt_gates_comparison.csv", index=False)
print(gate_cmp.to_string(index=False, formatters={
    "pass_rate_pct": "{:.1f}".format,
    "passed_p_stress_10d": "{:.1%}".format,
    "passed_p_stress_20d": "{:.1%}".format,
    "blocked_p_stress_10d": "{:.1%}".format,
    "blocked_p_stress_20d": "{:.1%}".format,
}))

# ── 4. By-year alt gate pass rate (focus on slow-bull years) ───────────
print("\n" + "=" * 70)
print("4. Slow-bull year pass rate under each gate (lift over current)")
print("=" * 70)

slow_years = [2007, 2017, 2018, 2024, 2025, 2026]
slow_df = df[df["year"].isin(slow_years)].copy()
rows = []
for y in slow_years:
    sub = slow_df[slow_df["year"] == y]
    if len(sub) == 0:
        continue
    row = {"year": y, "n_normal": len(sub)}
    for g in gates:
        row[f"{gate_labels[g]} pass%"] = sub[g].mean() * 100
    rows.append(row)
slow_summary = pd.DataFrame(rows)
slow_summary.to_csv(OUT / "q074_1_slow_bull_gate_pass.csv", index=False)
print(slow_summary.to_string(index=False, float_format=lambda x: f"{x:.1f}"))

# ── 5. Stress-validity of alt gate ADDITIONS (days passed by B/C/E but blocked by A) ─
print("\n" + "=" * 70)
print("5. Added-pass days (gate passes vs current): what's their stress rate?")
print("=" * 70)

rows = []
for g in ["gate_b_vix16", "gate_c_vix18", "gate_d_ivp63", "gate_e_combo"]:
    # Days that the new gate passes but current blocks
    added = df[(df[g] == 1) & (df["gate_current"] == 0)]
    if len(added) == 0:
        continue
    rows.append({
        "gate": gate_labels[g],
        "added_pass_days": len(added),
        "added_pct_of_total": len(added) / len(df) * 100,
        "added_p_stress_10d": added["stress_in_next_10d"].mean(),
        "added_p_stress_20d": added["stress_in_next_20d"].mean(),
        "current_baseline_p_stress_10d": df[df["gate_current"] == 1]["stress_in_next_10d"].mean(),
        "vs_baseline_lift_10d": added["stress_in_next_10d"].mean()
                              - df[df["gate_current"] == 1]["stress_in_next_10d"].mean(),
    })
added_cmp = pd.DataFrame(rows)
added_cmp.to_csv(OUT / "q074_1_added_pass_days_stress.csv", index=False)
print(added_cmp.to_string(index=False, formatters={
    "added_pct_of_total": "{:.1f}".format,
    "added_p_stress_10d": "{:.1%}".format,
    "added_p_stress_20d": "{:.1%}".format,
    "current_baseline_p_stress_10d": "{:.1%}".format,
    "vs_baseline_lift_10d": "{:+.1%}".format,
}))

print("\n" + "=" * 70)
print("Q074.1 forensic complete. CSVs written to research/q074/")
print("=" * 70)
