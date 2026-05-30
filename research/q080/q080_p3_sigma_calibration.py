"""Q080 P3 — σ-relative calibration of the 0.5pp noise threshold.

ChatGPT Q18 challenge: the 0.5pp noise threshold has never been calibrated to
baseline σ. Q080 P3 asks: how many σ of baseline annROE is 0.5pp?

Two cuts:
  (A) Overall — across all (seed × year) pairs for baseline + ladder
  (B) Per regime — stratify years by dominant VIX regime

If 0.5pp is ~1σ globally → noise threshold too lenient (treating signal as noise)
If 0.5pp is < 0.3σ globally → too strict (treating noise as signal)
If 0.5pp is regime-dependent → noise threshold should be REGIME-CONDITIONAL

Method
------
Uses Q078 P4 baseline daily PnL + market VIX frame to compute:
  - per-year annROE for baseline alone (no ladder) → σ_baseline_annual
  - per-year max VIX → regime classification
    benign:   max_VIX < 18
    normal:   18 ≤ max_VIX < 22
    elevated: 22 ≤ max_VIX < 28
    stress:   max_VIX ≥ 28
  - per-regime baseline annROE σ
  - express 0.5pp as multiple of each σ

Output
------
  research/q080/q080_p3_regime_sigma.csv
  research/q080/q080_p3_memo.md (later)
"""

from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
OUT = REPO / "research" / "q080"
P4_OUT = REPO / "research" / "q078"

NLV = 894_000.0
NOISE_THRESHOLD_PP = 0.5  # current PM-set noise threshold

print("Q080 P3 — σ-relative calibration of 0.5pp noise threshold", flush=True)
print("=" * 70)

# ── Baseline daily PnL ────────────────────────────────────────────────
df = pd.read_csv(P4_OUT / "q078_p4_baseline_daily.csv",
                 parse_dates=["date"], index_col="date")
print(f"Loaded baseline daily: {len(df):,} days")

# ── Market frame ──────────────────────────────────────────────────────
from signals.vix_regime import fetch_vix_history
vix_df = fetch_vix_history(period="max")
vix_df.index = pd.to_datetime(vix_df.index.date)
mkt = vix_df["vix"].reindex(df.index).ffill()
print(f"Loaded VIX: {mkt.notna().sum()} aligned days")


# ── Per-year baseline annual return + max VIX ────────────────────────
df["year"] = df.index.year
mkt_df = pd.DataFrame({"vix": mkt})
mkt_df["year"] = mkt_df.index.year

eq_per_year = []
years = sorted(df["year"].unique())
for y in years:
    yd = df[df["year"] == y]
    if yd.empty:
        continue
    days = len(yd)
    if days < 100:
        # too few days for a real annual return (e.g., 2026 ytd)
        continue
    cum = yd["baseline_pnl"].sum()
    ann_roe_pct = cum / NLV * 100 * (252 / days)
    max_vix = mkt_df[mkt_df["year"] == y]["vix"].max()
    mean_vix = mkt_df[mkt_df["year"] == y]["vix"].mean()
    eq_per_year.append({
        "year": y,
        "n_days": days,
        "ann_roe_pct": ann_roe_pct,
        "max_vix": max_vix,
        "mean_vix": mean_vix,
        "cum_pnl": cum,
    })

ann = pd.DataFrame(eq_per_year)


# ── Regime classification (per year) ─────────────────────────────────
def classify_regime(max_vix):
    if max_vix < 18: return "benign"
    if max_vix < 22: return "normal"
    if max_vix < 28: return "elevated"
    return "stress"

ann["regime"] = ann["max_vix"].apply(classify_regime)
ann.to_csv(OUT / "q080_p3_annual_baseline.csv", index=False)


print()
print("Per-year baseline ann ROE + VIX classification:")
print(ann.to_string(index=False))


# ── Sigma by regime ─────────────────────────────────────────────────
print()
print("=" * 70)
print("σ (sigma) of baseline ann ROE — overall and per regime")
print("=" * 70)
print(f"{'cut':<25} {'n':>4} {'mean ROE%':>12} {'σ ROE%':>10} {'0.5pp/σ':>12}")
print("-" * 70)

overall_sigma = ann["ann_roe_pct"].std()
overall_mean = ann["ann_roe_pct"].mean()
print(f"{'overall':<25} {len(ann):>4} {overall_mean:>12.3f} {overall_sigma:>10.3f} "
      f"{NOISE_THRESHOLD_PP/overall_sigma:>12.3f}")

sigma_by_regime = []
for regime in ["benign", "normal", "elevated", "stress"]:
    sub = ann[ann["regime"] == regime]
    if len(sub) >= 2:
        sigma = sub["ann_roe_pct"].std()
        mean = sub["ann_roe_pct"].mean()
        ratio = NOISE_THRESHOLD_PP / sigma if sigma > 0 else float("inf")
        print(f"{regime:<25} {len(sub):>4} {mean:>12.3f} {sigma:>10.3f} {ratio:>12.3f}")
        sigma_by_regime.append({
            "regime": regime, "n_years": len(sub),
            "mean_ann_roe_pct": mean, "sigma_ann_roe_pct": sigma,
            "noise_threshold_pp_over_sigma": ratio,
        })
    else:
        print(f"{regime:<25} {len(sub):>4} (insufficient sample, skipped)")
        sigma_by_regime.append({
            "regime": regime, "n_years": len(sub),
            "mean_ann_roe_pct": float("nan"), "sigma_ann_roe_pct": float("nan"),
            "noise_threshold_pp_over_sigma": float("nan"),
        })

regime_df = pd.DataFrame(sigma_by_regime)
regime_df.to_csv(OUT / "q080_p3_regime_sigma.csv", index=False)


# ── Verdict ──────────────────────────────────────────────────────────
print()
print("=" * 70)
print("VERDICT — what is 0.5pp in σ units?")
print("=" * 70)
ratio_overall = NOISE_THRESHOLD_PP / overall_sigma
print(f"Overall: 0.5pp = {ratio_overall:.2f}σ of baseline ann ROE")

regime_ratios = {r["regime"]: r["noise_threshold_pp_over_sigma"]
                 for r in sigma_by_regime if not pd.isna(r.get("noise_threshold_pp_over_sigma"))}

if all(0.3 < r < 1.5 for r in regime_ratios.values()):
    if max(regime_ratios.values()) - min(regime_ratios.values()) < 0.5:
        verdict = "STABLE — 0.5pp is roughly 0.3-1.5σ uniformly; current threshold defensible as flat"
    else:
        verdict = "REGIME-CONDITIONAL — 0.5pp varies materially by regime; threshold should be σ-multiplier not flat pp"
elif all(r > 1.5 for r in regime_ratios.values()):
    verdict = "TOO LENIENT — 0.5pp > 1.5σ; treating real signal as noise; threshold should drop"
elif all(r < 0.3 for r in regime_ratios.values()):
    verdict = "TOO STRICT — 0.5pp < 0.3σ; treating noise as signal; threshold should rise"
else:
    verdict = "MIXED — some regimes 0.5pp adequate, others not; recommend regime-conditional"

print()
print(f"VERDICT: {verdict}")
