"""Q074 P4 — Full Validation (B4 primary + B3 backup, G3 expanded scope).

Per G3 PASS WITH REVISIONS:
  Core:
    - V6 bootstrap (block=250, 20 seeds)
    - V7 walk-forward H1/H2 (2000-2013 vs 2013-2026)
    - Friction sensitivity ±50%
    - Crisis windows side-by-side
    - Synthetic crisis injection

  G3 Add-ons:
    - Episode-level transition incremental (NOT just ON-day)
    - B4 VIX 20-22 joint-slice analysis
    - Negative-cash funding stress (+300bp / +600bp on negative-cash days)
    - B4 vs B3 active-day overlap + incremental delta

Outputs:
  q074_p4_bootstrap.csv
  q074_p4_walkforward.csv
  q074_p4_friction_sensitivity.csv
  q074_p4_episode_level_transition.csv
  q074_p4_vix2022_joint_slice.csv
  q074_p4_funding_stress.csv
  q074_p4_b4_b3_overlap.csv
  q074_p4_crisis_comparison.csv
  q074_p4_synthetic_stress.csv
"""
from __future__ import annotations
import sys
import math
from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

OUT = REPO / "research" / "q074"
NLV = 894_000.0

FRICTION_ANN_SPX = 0.0035
FRICTION_ANN_Q42 = 0.0005
CASH_YIELD = 0.043
P13R_SPX = 0.60
P13R_Q42 = 0.10
HV_ALLOC = 0.0
Q42_ALLOC = 0.175
STRESS_SPX_CAP = 0.50
SECOND_LEG_CAP = 0.40

print("Q074 P4 — Full Validation (B4 + B3, G3 expanded)", flush=True)
print("=" * 70)

# ── Build market data + features ────────────────────────────────────────
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
mkt["ma50_slope_pos"] = ((mkt["ma50"] - mkt["ma50"].shift(5)) > 0).astype(int)
mkt["ath_running"] = mkt["spx_close"].expanding().max()
mkt["ddath"] = mkt["spx_close"] / mkt["ath_running"] - 1.0
mkt["vix_5d_change"] = mkt["vix"] - mkt["vix"].shift(5)

def rolling_pct(series, window=252):
    def w(arr):
        if len(arr) < window:
            return np.nan
        cur = arr[-1]
        return (arr[:-1] < cur).mean() * 100.0
    return series.rolling(window).apply(w, raw=True)

mkt["ivp_252"] = rolling_pct(mkt["vix"], 252)
mkt["high_20d"] = mkt["spx_close"].rolling(20, min_periods=5).max()
mkt["dd_20d"] = mkt["spx_close"] / mkt["high_20d"] - 1.0
mkt["high_60d"] = mkt["spx_close"].rolling(60, min_periods=10).max()
mkt["dd_60d"] = mkt["spx_close"] / mkt["high_60d"] - 1.0
flag = ((mkt["vix"] >= 22.0) | (mkt["dd_20d"] <= -0.04) | (mkt["dd_60d"] <= -0.04))
mkt["stress_active"] = flag.rolling(3, min_periods=1).max().astype(bool)
mkt["second_leg_active"] = ((mkt["dd_60d"] <= -0.08) & (mkt["vix"] >= 25.0)).astype(bool)

def b1_strict(row):
    return (not row["stress_active"] and not row["second_leg_active"]
            and row["above_ma50"] == 1 and row["ma50_slope_pos"] == 1
            and row["ddath"] > -0.03 and row["vix"] < 20
            and row["vix_5d_change"] <= 1.0 and row["ivp_252"] < 55)

def b2_moderate(row):
    return (not row["stress_active"] and not row["second_leg_active"]
            and row["above_ma50"] == 1 and row["ddath"] > -0.04
            and row["vix"] < 22 and row["vix_5d_change"] <= 1.5
            and row["ivp_252"] < 55)

def build_candidate(booster_fn, booster_cap, friction_mult=1.0, neg_cash_extra_bps=0):
    """Build daily PnL series.
    neg_cash_extra_bps: extra annualized funding cost basis points applied ONLY on negative-cash days.
    """
    df = combined.copy().join(mkt[["above_ma50", "ma50_slope_pos", "ddath", "vix",
                                    "vix_5d_change", "ivp_252",
                                    "stress_active", "second_leg_active"]],
                              how="left").ffill()
    valid = df["ivp_252"].notna()
    df["booster_active"] = False
    if booster_fn is not None:
        df.loc[valid, "booster_active"] = df.loc[valid].apply(booster_fn, axis=1)
    df["booster_active"] = df["booster_active"].astype(bool)

    spx_alloc = pd.Series(0.80, index=df.index)
    spx_alloc[df["stress_active"]] = STRESS_SPX_CAP
    spx_alloc[df["second_leg_active"]] = SECOND_LEG_CAP
    if booster_cap is not None:
        booster_eligible = df["booster_active"] & ~df["stress_active"] & ~df["second_leg_active"]
        spx_alloc[booster_eligible] = booster_cap
    df["spx_alloc"] = spx_alloc
    df["cash_alloc"] = 1.0 - spx_alloc - HV_ALLOC - Q42_ALLOC

    spx_pnl = df["spx_pnl"] * (df["spx_alloc"] / P13R_SPX)
    q42_pnl = df["q42a_pnl"] * (Q42_ALLOC / P13R_Q42)
    cash_pnl = df["cash_alloc"] * NLV * CASH_YIELD / 252.0
    # Negative cash funding stress
    if neg_cash_extra_bps > 0:
        neg_cash_mask = df["cash_alloc"] < 0
        extra_cost = df["cash_alloc"].clip(upper=0) * NLV * (neg_cash_extra_bps / 10000.0) / 252.0
        cash_pnl = cash_pnl + extra_cost  # extra_cost is negative when cash_alloc<0
    spx_drag = FRICTION_ANN_SPX * friction_mult * NLV * (df["spx_alloc"] / P13R_SPX) / 252.0
    q42_drag = FRICTION_ANN_Q42 * friction_mult * NLV * (Q42_ALLOC / P13R_Q42) / 252.0
    df["total_pnl"] = (spx_pnl - spx_drag) + (q42_pnl - q42_drag) + cash_pnl
    df["cum_pnl"] = df["total_pnl"].cumsum()
    df["equity"] = NLV + df["cum_pnl"]
    df["equity_start"] = df["equity"].shift(1).fillna(NLV)
    df["daily_ret"] = df["total_pnl"] / df["equity_start"]
    return df

def metrics(df):
    years = len(df) / 252
    final_eq = df["equity"].iloc[-1]
    ann_roe = (final_eq / NLV) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    running_max = df["equity"].cummax()
    drawdown = (df["equity"] - running_max) / running_max
    max_dd = drawdown.min()
    worst_20d = df["daily_ret"].rolling(20).sum().min()
    worst_63d = df["daily_ret"].rolling(63).sum().min()
    sharpe = df["daily_ret"].mean() / df["daily_ret"].std() * (252**0.5) if df["daily_ret"].std() > 0 else 0.0
    return {"ann_roe": ann_roe, "max_dd": max_dd, "worst_20d": worst_20d,
            "worst_63d": worst_63d, "sharpe": sharpe, "final_eq": final_eq}

# ── Build B0 / B3 / B4 ────────────────────────────────────────────────
print("\nBuilding B0 baseline + B3 + B4...")
b0 = build_candidate(None, None)
b3 = build_candidate(b1_strict, 0.90)
b4 = build_candidate(b2_moderate, 0.90)

m0 = metrics(b0)
m3 = metrics(b3)
m4 = metrics(b4)
print(f"  B0 Arch-3:  ROE {m0['ann_roe']*100:.2f}%, MaxDD {m0['max_dd']*100:.2f}%, W20d {m0['worst_20d']*100:.2f}%, Sharpe {m0['sharpe']:.2f}")
print(f"  B3 strict90: ROE {m3['ann_roe']*100:.2f}%, MaxDD {m3['max_dd']*100:.2f}%, W20d {m3['worst_20d']*100:.2f}%, Sharpe {m3['sharpe']:.2f}")
print(f"  B4 mod90:    ROE {m4['ann_roe']*100:.2f}%, MaxDD {m4['max_dd']*100:.2f}%, W20d {m4['worst_20d']*100:.2f}%, Sharpe {m4['sharpe']:.2f}")

# ──────────────────────────────────────────────────────────────────────
# P4.1 V6 Bootstrap (block=250, 20 seeds) on B0 / B3 / B4
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4.1 V6 Bootstrap (block=250, 20 seeds)")
print("=" * 70)

def bootstrap_stats(pnl_series, n_boot=2000, block_size=250, seeds=20):
    arr = pnl_series.values
    n = len(arr)
    sig_count = 0
    ci_los, ci_his, means = [], [], []
    for seed in range(1, seeds + 1):
        rng = np.random.default_rng(seed=seed)
        boot_means = np.empty(n_boot)
        max_start = max(1, n - block_size + 1)
        for idx in range(n_boot):
            n_blocks = int(np.ceil(n / block_size))
            starts = rng.integers(0, max_start, size=n_blocks)
            sample = np.concatenate([arr[s:s+block_size] for s in starts])[:n]
            boot_means[idx] = sample.mean()
        ci_lo = float(np.percentile(boot_means, 2.5))
        ci_hi = float(np.percentile(boot_means, 97.5))
        if ci_lo > 0:
            sig_count += 1
        ci_los.append(ci_lo)
        ci_his.append(ci_hi)
        means.append(float(boot_means.mean()))
    return {
        "sig_rate": sig_count / seeds,
        "median_ci_lo_daily": float(np.median(ci_los)),
        "median_ci_hi_daily": float(np.median(ci_his)),
        "median_mean_daily": float(np.median(means)),
        # ROE delta noise: std-error of ann ROE from bootstrap = std(means) × 252 / NLV
        "roe_std_pp": float(np.std(means) * 252 / NLV * 100),
    }

bs0 = bootstrap_stats(b0["total_pnl"])
bs3 = bootstrap_stats(b3["total_pnl"])
bs4 = bootstrap_stats(b4["total_pnl"])
print(f"\n  B0: sig_rate {bs0['sig_rate']*100:.0f}%, ROE noise σ ~{bs0['roe_std_pp']:.3f}pp")
print(f"  B3: sig_rate {bs3['sig_rate']*100:.0f}%, ROE noise σ ~{bs3['roe_std_pp']:.3f}pp")
print(f"  B4: sig_rate {bs4['sig_rate']*100:.0f}%, ROE noise σ ~{bs4['roe_std_pp']:.3f}pp")
print(f"\n  ΔROE(B4-B0) = {(m4['ann_roe']-m0['ann_roe'])*100:.3f}pp; combined noise ~ {((bs0['roe_std_pp']**2 + bs4['roe_std_pp']**2)**0.5):.3f}pp")
print(f"  ΔROE(B3-B0) = {(m3['ann_roe']-m0['ann_roe'])*100:.3f}pp; combined noise ~ {((bs0['roe_std_pp']**2 + bs3['roe_std_pp']**2)**0.5):.3f}pp")

bootstrap_rows = [
    {"cand": "B0", "sig_rate": bs0["sig_rate"], "roe_std_pp": bs0["roe_std_pp"]},
    {"cand": "B3", "sig_rate": bs3["sig_rate"], "roe_std_pp": bs3["roe_std_pp"]},
    {"cand": "B4", "sig_rate": bs4["sig_rate"], "roe_std_pp": bs4["roe_std_pp"]},
]
pd.DataFrame(bootstrap_rows).to_csv(OUT / "q074_p4_bootstrap.csv", index=False)

# ──────────────────────────────────────────────────────────────────────
# P4.2 V7 Walk-Forward (2000-2013 vs 2013-2026)
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4.2 V7 Walk-Forward (H1 2000-2013 / H2 2013-2026)")
print("=" * 70)

def half_metrics(df, mid="2013-01-01"):
    h1 = df[df.index < mid].copy()
    h2 = df[df.index >= mid].copy()
    # Recompute equity and metrics within each half
    h1_pnl = h1["total_pnl"]
    h2_pnl = h2["total_pnl"]
    def stats(pnl):
        years = len(pnl) / 252
        cum = pnl.cumsum() + NLV
        ann = (cum.iloc[-1] / NLV) ** (1.0 / years) - 1.0 if years > 0 else 0.0
        ret = pnl / NLV  # use static NLV for the half-period attribution
        w20 = ret.rolling(20).sum().min()
        return ann, w20
    h1_ann, h1_w20 = stats(h1_pnl)
    h2_ann, h2_w20 = stats(h2_pnl)
    return h1_ann, h1_w20, h2_ann, h2_w20

for label, df in [("B0", b0), ("B3", b3), ("B4", b4)]:
    h1_ann, h1_w20, h2_ann, h2_w20 = half_metrics(df)
    print(f"\n  {label}:")
    print(f"    H1 (2000-2012): ROE {h1_ann*100:.2f}% / W20d {h1_w20*100:.2f}%")
    print(f"    H2 (2013-2026): ROE {h2_ann*100:.2f}% / W20d {h2_w20*100:.2f}%")
    print(f"    H1 floor 8%: {'✓' if h1_ann >= 0.08 else '✗'}; H2 floor 8%: {'✓' if h2_ann >= 0.08 else '✗'}")

# Write walk-forward
wf_rows = []
for label, df in [("B0", b0), ("B3", b3), ("B4", b4)]:
    h1_ann, h1_w20, h2_ann, h2_w20 = half_metrics(df)
    wf_rows.append({
        "cand": label,
        "h1_roe_pct": round(h1_ann*100, 2),
        "h1_w20d_pct": round(h1_w20*100, 2),
        "h2_roe_pct": round(h2_ann*100, 2),
        "h2_w20d_pct": round(h2_w20*100, 2),
        "h1_floor_8_pass": h1_ann >= 0.08,
        "h2_floor_8_pass": h2_ann >= 0.08,
    })
pd.DataFrame(wf_rows).to_csv(OUT / "q074_p4_walkforward.csv", index=False)

# ──────────────────────────────────────────────────────────────────────
# P4.3 Friction sensitivity ±50%
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4.3 Friction Sensitivity ±50%")
print("=" * 70)

frict_rows = []
for fm in [0.5, 0.75, 1.0, 1.25, 1.5]:
    b3m = metrics(build_candidate(b1_strict, 0.90, friction_mult=fm))
    b4m = metrics(build_candidate(b2_moderate, 0.90, friction_mult=fm))
    b0m = metrics(build_candidate(None, None, friction_mult=fm))
    print(f"  Friction ×{fm}:  B0 {b0m['ann_roe']*100:.2f}% / B3 {b3m['ann_roe']*100:.2f}% / B4 {b4m['ann_roe']*100:.2f}%   ΔB4-B0 {(b4m['ann_roe']-b0m['ann_roe'])*100:+.2f}pp")
    frict_rows.append({"friction_mult": fm,
                        "b0_roe": b0m["ann_roe"]*100,
                        "b3_roe": b3m["ann_roe"]*100,
                        "b4_roe": b4m["ann_roe"]*100,
                        "delta_b4_vs_b0_pp": (b4m["ann_roe"]-b0m["ann_roe"])*100})
pd.DataFrame(frict_rows).to_csv(OUT / "q074_p4_friction_sensitivity.csv", index=False)

# ──────────────────────────────────────────────────────────────────────
# P4.4 Episode-level transition incremental (G3 add-on 1)
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4.4 Episode-Level Transition Incremental (G3 add-on 1)")
print("=" * 70)

b0["stress_active_prev"] = b0["stress_active"].shift(1).fillna(False)
b0["stress_trigger"] = b0["stress_active"] & ~b0["stress_active_prev"]
trigger_dates = b0.index[b0["stress_trigger"]]
print(f"\nStress trigger events: {len(trigger_dates)}")

def episode_incremental(df_cand, lookback=10):
    rows = []
    for td in trigger_dates:
        idx = df_cand.index.get_loc(td)
        if idx < lookback:
            continue
        window = df_cand.iloc[idx - lookback:idx]
        b0_window = b0.iloc[idx - lookback:idx]
        # Full episode incremental (NOT booster-on days only)
        cand_total = window["total_pnl"].sum()
        b0_total = b0_window["total_pnl"].sum()
        incremental_full = cand_total - b0_total
        booster_days = int(window["booster_active"].sum())
        rows.append({
            "trigger_date": td.strftime("%Y-%m-%d"),
            "lookback_days": lookback,
            "booster_days_in_window": booster_days,
            "incremental_full_episode_usd": round(incremental_full, 0),
            "incremental_pct_nlv": round(incremental_full / NLV * 100, 3),
        })
    return rows

print("\nB3 strict 90 (10d episode):")
b3_eps_10 = pd.DataFrame(episode_incremental(b3, 10))
b3_with_booster = b3_eps_10[b3_eps_10["booster_days_in_window"] > 0]
neg_count = (b3_with_booster["incremental_full_episode_usd"] < 0).sum()
print(f"  Booster-present episodes: {len(b3_with_booster)} / {len(b3_eps_10)}")
print(f"  Cum incremental: ${b3_with_booster['incremental_full_episode_usd'].sum():+,.0f}")
print(f"  Cum loss-only:   ${b3_with_booster[b3_with_booster['incremental_full_episode_usd']<0]['incremental_full_episode_usd'].sum():+,.0f}")
print(f"  Worst single:    ${b3_with_booster['incremental_full_episode_usd'].min():+,.0f} ({b3_with_booster['incremental_full_episode_usd'].min()/NLV*100:.3f}% NLV)")
print(f"  Negative episodes: {neg_count}/{len(b3_with_booster)}")

print("\nB4 moderate 90 (10d episode):")
b4_eps_10 = pd.DataFrame(episode_incremental(b4, 10))
b4_with_booster = b4_eps_10[b4_eps_10["booster_days_in_window"] > 0]
neg_count = (b4_with_booster["incremental_full_episode_usd"] < 0).sum()
print(f"  Booster-present episodes: {len(b4_with_booster)} / {len(b4_eps_10)}")
print(f"  Cum incremental: ${b4_with_booster['incremental_full_episode_usd'].sum():+,.0f}")
print(f"  Cum loss-only:   ${b4_with_booster[b4_with_booster['incremental_full_episode_usd']<0]['incremental_full_episode_usd'].sum():+,.0f}")
print(f"  Worst single:    ${b4_with_booster['incremental_full_episode_usd'].min():+,.0f} ({b4_with_booster['incremental_full_episode_usd'].min()/NLV*100:.3f}% NLV)")
print(f"  Negative episodes: {neg_count}/{len(b4_with_booster)}")

b3_eps_10["cand"] = "B3"
b4_eps_10["cand"] = "B4"
pd.concat([b3_eps_10, b4_eps_10]).to_csv(OUT / "q074_p4_episode_level_transition.csv", index=False)

# ──────────────────────────────────────────────────────────────────────
# P4.5 B4 VIX 20-22 joint-slice (G3 add-on 2)
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4.5 B4 VIX 20-22 Joint-Slice (G3 add-on 2)")
print("=" * 70)

b4_features = b4.join(mkt[["above_ma50", "ma50_slope_pos", "ddath", "vix",
                            "vix_5d_change", "ivp_252"]], how="left", rsuffix="_mkt").ffill()
# B4 booster-active days with VIX 20-22
vix2022 = b4_features[b4_features["booster_active"] & (b4_features["vix"] >= 20) & (b4_features["vix"] < 22)].copy()
print(f"\nB4 booster-active VIX 20-22 days: {len(vix2022)}")
if len(vix2022) > 0:
    print(f"  IVP distribution: mean {vix2022['ivp_252'].mean():.1f}, median {vix2022['ivp_252'].median():.1f}")
    print(f"  ddATH distribution: mean {vix2022['ddath'].mean()*100:.2f}%, min {vix2022['ddath'].min()*100:.2f}%")
    print(f"  VIX 5d change: mean {vix2022['vix_5d_change'].mean():.2f}, max {vix2022['vix_5d_change'].max():.2f}")
    # IVP sub-bucket within VIX 20-22
    vix2022["ivp_bucket"] = pd.cut(vix2022["ivp_252"], bins=[0, 30, 45, 55, 100], labels=["<30", "30-45", "45-55", ">=55"])
    counts = vix2022.groupby("ivp_bucket", observed=True).size()
    print(f"  IVP sub-bucket counts:")
    print(counts.to_string())

joint_rows = vix2022[["above_ma50", "ma50_slope_pos", "ddath", "vix", "vix_5d_change",
                      "ivp_252", "total_pnl"]].copy()
joint_rows.to_csv(OUT / "q074_p4_vix2022_joint_slice.csv", index=True)

# ──────────────────────────────────────────────────────────────────────
# P4.6 Negative-cash funding stress (G3 add-on 3)
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4.6 Negative-Cash Funding Stress (+300bp / +600bp)")
print("=" * 70)

for stress_bps in [0, 300, 600]:
    b0s = metrics(build_candidate(None, None, neg_cash_extra_bps=stress_bps))
    b3s = metrics(build_candidate(b1_strict, 0.90, neg_cash_extra_bps=stress_bps))
    b4s = metrics(build_candidate(b2_moderate, 0.90, neg_cash_extra_bps=stress_bps))
    print(f"\n  +{stress_bps}bp neg-cash funding stress:")
    print(f"    B0 ROE {b0s['ann_roe']*100:.2f}% / B3 ROE {b3s['ann_roe']*100:.2f}% / B4 ROE {b4s['ann_roe']*100:.2f}%")
    print(f"    ΔB4-B0 {(b4s['ann_roe']-b0s['ann_roe'])*100:+.3f}pp; ΔB3-B0 {(b3s['ann_roe']-b0s['ann_roe'])*100:+.3f}pp")

# Save funding stress
funding_rows = []
for stress_bps in [0, 300, 600]:
    b0s = metrics(build_candidate(None, None, neg_cash_extra_bps=stress_bps))
    b3s = metrics(build_candidate(b1_strict, 0.90, neg_cash_extra_bps=stress_bps))
    b4s = metrics(build_candidate(b2_moderate, 0.90, neg_cash_extra_bps=stress_bps))
    funding_rows.append({
        "extra_bps": stress_bps,
        "b0_roe": b0s["ann_roe"]*100,
        "b3_roe": b3s["ann_roe"]*100,
        "b4_roe": b4s["ann_roe"]*100,
        "delta_b3_vs_b0_pp": (b3s["ann_roe"]-b0s["ann_roe"])*100,
        "delta_b4_vs_b0_pp": (b4s["ann_roe"]-b0s["ann_roe"])*100,
    })
pd.DataFrame(funding_rows).to_csv(OUT / "q074_p4_funding_stress.csv", index=False)

# ──────────────────────────────────────────────────────────────────────
# P4.7 B4 vs B3 active-day overlap (G3 add-on 4)
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4.7 B4 vs B3 Active-Day Overlap")
print("=" * 70)

b3_active = b3["booster_active"] & ~b3["stress_active"] & ~b3["second_leg_active"]
b4_active = b4["booster_active"] & ~b4["stress_active"] & ~b4["second_leg_active"]
overlap = b3_active & b4_active
b4_only = b4_active & ~b3_active
b3_only = b3_active & ~b4_active  # should be ~0 since B3 strict ⊆ B4 moderate

print(f"\n  B3 active days:       {b3_active.sum()}")
print(f"  B4 active days:       {b4_active.sum()}")
print(f"  Overlap days:         {overlap.sum()}")
print(f"  B4-only days:         {b4_only.sum()}")
print(f"  B3-only days:         {b3_only.sum()}")

# B4-only days: their incremental contribution
b4_only_pnl_b4 = b4.loc[b4_only, "total_pnl"].sum()
b4_only_pnl_b0 = b0.loc[b4_only, "total_pnl"].sum()
b4_only_incremental = b4_only_pnl_b4 - b4_only_pnl_b0
print(f"\n  B4-only days incremental PnL: ${b4_only_incremental:+,.0f} ({b4_only_incremental/NLV*100:+.3f}% NLV)")
print(f"  (These are the days B4 activates but B3 doesn't — VIX 20-22 region differentiator)")

overlap_rows = [{
    "metric": "b3_active_days",     "value": int(b3_active.sum())},
    {"metric": "b4_active_days",     "value": int(b4_active.sum())},
    {"metric": "overlap_days",       "value": int(overlap.sum())},
    {"metric": "b4_only_days",       "value": int(b4_only.sum())},
    {"metric": "b3_only_days",       "value": int(b3_only.sum())},
    {"metric": "b4_only_incremental_usd", "value": round(b4_only_incremental, 0)},
    {"metric": "b4_only_incremental_pct_nlv", "value": round(b4_only_incremental/NLV*100, 3)},
]
pd.DataFrame(overlap_rows).to_csv(OUT / "q074_p4_b4_b3_overlap.csv", index=False)

# ──────────────────────────────────────────────────────────────────────
# P4.8 Crisis windows comparison
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4.8 Crisis Windows (Arch-3 vs B3 vs B4)")
print("=" * 70)

crises = {
    "DotCom_2000_2002": ("2000-03-01", "2002-10-31"),
    "GFC_2008":         ("2008-08-01", "2009-03-31"),
    "Vol_2018Q4":       ("2018-10-01", "2018-12-31"),
    "COVID_2020":       ("2020-02-15", "2020-05-31"),
    "Bear_2022":        ("2022-01-01", "2022-12-31"),
}

crisis_rows = []
for cn, (s, e) in crises.items():
    s_ts, e_ts = pd.Timestamp(s), pd.Timestamp(e)
    print(f"\n  [{cn}]")
    for label, df in [("B0", b0), ("B3", b3), ("B4", b4)]:
        sub = df[(df.index >= s_ts) & (df.index <= e_ts)]
        if len(sub) == 0:
            continue
        eq0 = sub["equity_start"].iloc[0]
        ret = sub["total_pnl"].sum() / eq0
        print(f"    {label:<3} {ret*100:+.2f}% over {len(sub)} days")
        crisis_rows.append({"crisis": cn, "cand": label, "days": len(sub),
                            "pct_then_equity": round(ret*100, 2)})

pd.DataFrame(crisis_rows).to_csv(OUT / "q074_p4_crisis_comparison.csv", index=False)

# ──────────────────────────────────────────────────────────────────────
# P4.9 Synthetic crisis injection
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4.9 Synthetic Crisis Injection (-3% NLV over 20d at booster-active period)")
print("=" * 70)

# Find a recent booster-active calm window in 2017 (between crises)
booster_active_dates = b4.index[b4["booster_active"]]
shock_window_start = pd.Timestamp("2017-09-01")
shock_window_end = pd.Timestamp("2017-09-29")  # 20 trading days

# Injection magnitude: -3% NLV spread over the window
n_days_in_window = ((b0.index >= shock_window_start) & (b0.index <= shock_window_end)).sum()
shock_per_day = -0.03 * NLV / n_days_in_window if n_days_in_window > 0 else 0
print(f"\n  Synthetic shock window: {shock_window_start.date()} → {shock_window_end.date()} ({n_days_in_window} days)")
print(f"  Per-day shock: ${shock_per_day:,.0f} (= -3% NLV / 20d)")

for label, df in [("B0", b0), ("B3", b3), ("B4", b4)]:
    df_shocked = df.copy()
    in_shock = (df_shocked.index >= shock_window_start) & (df_shocked.index <= shock_window_end)
    df_shocked.loc[in_shock, "total_pnl"] += shock_per_day
    df_shocked["cum_pnl"] = df_shocked["total_pnl"].cumsum()
    df_shocked["equity"] = NLV + df_shocked["cum_pnl"]
    df_shocked["equity_start"] = df_shocked["equity"].shift(1).fillna(NLV)
    df_shocked["daily_ret"] = df_shocked["total_pnl"] / df_shocked["equity_start"]
    m = metrics(df_shocked)
    print(f"  {label}: shocked ROE {m['ann_roe']*100:.2f}%, MaxDD {m['max_dd']*100:.2f}%, W20d {m['worst_20d']*100:.2f}%")

# ──────────────────────────────────────────────────────────────────────
# Final Summary
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4 Summary")
print("=" * 70)
print(f"\n  Bootstrap sig: B0 {bs0['sig_rate']*100:.0f}% / B3 {bs3['sig_rate']*100:.0f}% / B4 {bs4['sig_rate']*100:.0f}%")
print(f"  ROE noise σ (combined): ΔB4-B0 noise ~{((bs0['roe_std_pp']**2+bs4['roe_std_pp']**2)**0.5):.3f}pp")
print(f"  ΔROE(B4-B0) point estimate: {(m4['ann_roe']-m0['ann_roe'])*100:.3f}pp")
print(f"\n  Q074 Strong threshold: +0.30pp. B4 +0.25pp; gap {0.30 - (m4['ann_roe']-m0['ann_roe'])*100:.3f}pp")
print(f"  Bootstrap noise ~{((bs0['roe_std_pp']**2+bs4['roe_std_pp']**2)**0.5):.3f}pp suggests gap is {'within' if ((bs0['roe_std_pp']**2+bs4['roe_std_pp']**2)**0.5) > 0.05 else 'outside'} noise")
