"""Q075 P1 — IVP-Blocked Normal-State Attribution.

Per Q075 P0 anchored memo (PASS by 2nd Quant 2026-05-19):

  Primary sample (Q075 main target):
    normal_state AND not stress_active AND not second_leg_active
    BPS_NNB entry blocked (IVP_252 >= 55, BPS_NNB_IVP_UPPER)
    Gate F inactive because (IVP_252 >= 55 AND VIX >= 15)
    other 5 benign conditions OTHERWISE pass:
      SPX > MA50
      ddATH > -0.04
      VIX < 22
      VIX_5d_change <= +1.5

  Secondary sample (diagnostic only):
    Gate F inactive because one of the other 5 benign conditions fails.

  4-Type partition:
    A: false block      (VIX < 15 — should be empty in Primary by construction)
    B: transition warning (VIX 15-22, IVP >= 70, VIX_5d > +0.5, ddATH expanding ≥ +1pp/5d)
    C: high-vol controlled (VIX 15-22, IVP >= 55, VIX_5d ≤ +0.5, ddATH stable/improving)
    D: trend-deteriorated (SPX <= MA50 OR MA50 slope neg OR ddATH <= -0.06 — empty in Primary)

  Sanity check: if Type A or D > 5% of Primary sample → flag warning.

  Bucketing axes:
    VIX: 15-17 / 17-19 / 19-22
    IVP_252: 55-70 / 70-85 / 85+
    VIX_5d: falling / flat / rising
    ddATH: 0 to -2 / -2 to -4
    (Primary always SPX > MA50)

  Forward measures: 5d/10d/20d SPX return, VIX change, stress probability,
                    20d/60d 2nd-leg probability, mean/worst held-position PnL.

  Hypothetical payoffs (alphabetical, NOT ranked) — per blocked day, per 1 contract:
    H1: cash / BOXX baseline (4.3% / 252 daily accrual)
    H2: BPS_NNB counterfactual (use combined.spx_pnl as proxy of engine PnL)
    H3: low-delta short-DTE BPS (14 DTE, ~0.15 delta, 25pt width, defined risk)
    H4: small iron condor (14 DTE, both wings, 25pt width)
    H5: bear call spread (14 DTE, 25pt width)
    H6: calendar / diagonal — SEED ONLY (skipped here, P2-conditional)

  Capital context per bucket:
    Average BP utilization (proxy: SPX exposure %)
    Existing SPX held position size (use combined data)
    Q042 active proxy (Q42 PnL nonzero)
    Cash residual

Outputs (research/q075/):
  q075_p1_primary_sample_days.csv    — every primary day with classification
  q075_p1_secondary_sample_days.csv  — every secondary day with classification
  q075_p1_type_classification.csv    — A/B/C/D counts per year per sample
  q075_p1_bucket_forward.csv         — per-bucket forward measures
  q075_p1_hypothetical_pnl.csv       — H1-H5 per Type, per VIX/IVP bucket
  q075_p1_capital_context.csv        — BP/SPX/Q042/cash per bucket
  q075_p1_first_screen.csv           — 2nd Quant first-screen summary table
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
OUT = REPO / "research" / "q075"
NLV = 894_000.0
CASH_YIELD = 0.043

print("Q075 P1 — IVP-Blocked Normal-State Attribution", flush=True)
print("=" * 70)

# ── Load market data (reuse Q074 pipeline) ─────────────────────────────
print("\nLoading combined PnL + market features...")
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

# Features (SPEC-104/105 v2 definitions)
mkt["ma50"] = mkt["spx_close"].rolling(50).mean()
mkt["above_ma50"] = (mkt["spx_close"] > mkt["ma50"]).astype(int)
mkt["ma50_slope_5d"] = mkt["ma50"] - mkt["ma50"].shift(5)
mkt["ma50_slope_pos"] = (mkt["ma50_slope_5d"] > 0).astype(int)
mkt["ath_running"] = mkt["spx_close"].expanding().max()
mkt["ddath"] = mkt["spx_close"] / mkt["ath_running"] - 1.0
mkt["vix_5d_change"] = mkt["vix"] - mkt["vix"].shift(5)
mkt["ddath_change_5d"] = mkt["ddath"] - mkt["ddath"].shift(5)

def rolling_pct(series, window=252):
    def w(arr):
        if len(arr) < window:
            return np.nan
        cur = arr[-1]
        return (arr[:-1] < cur).mean() * 100.0
    return series.rolling(window).apply(w, raw=True)

mkt["ivp_252"] = rolling_pct(mkt["vix"], 252)

# Stress / second-leg (SPEC-104 R5/R6, unchanged)
mkt["high_20d"] = mkt["spx_close"].rolling(20, min_periods=5).max()
mkt["dd_20d"] = mkt["spx_close"] / mkt["high_20d"] - 1.0
mkt["high_60d"] = mkt["spx_close"].rolling(60, min_periods=10).max()
mkt["dd_60d"] = mkt["spx_close"] / mkt["high_60d"] - 1.0
flag = ((mkt["vix"] >= 22.0) | (mkt["dd_20d"] <= -0.04) | (mkt["dd_60d"] <= -0.04))
mkt["stress_active"] = flag.rolling(3, min_periods=1).max().astype(bool)
mkt["second_leg_active"] = ((mkt["dd_60d"] <= -0.08) & (mkt["vix"] >= 25.0)).astype(bool)
mkt["normal_state"] = (~mkt["stress_active"] & ~mkt["second_leg_active"])

# Forward stress / second-leg
mkt["stress_in_next_5d"]  = mkt["stress_active"].shift(-1).rolling(5).max().shift(-4).astype(float)
mkt["stress_in_next_10d"] = mkt["stress_active"].shift(-1).rolling(10).max().shift(-9).astype(float)
mkt["stress_in_next_20d"] = mkt["stress_active"].shift(-1).rolling(20).max().shift(-19).astype(float)
mkt["second_leg_in_next_20d"] = mkt["second_leg_active"].shift(-1).rolling(20).max().shift(-19).astype(float)
mkt["second_leg_in_next_60d"] = mkt["second_leg_active"].shift(-1).rolling(60).max().shift(-59).astype(float)

# Forward SPX / VIX
mkt["spx_fwd_5d"]  = mkt["spx_close"].shift(-5)  / mkt["spx_close"] - 1.0
mkt["spx_fwd_10d"] = mkt["spx_close"].shift(-10) / mkt["spx_close"] - 1.0
mkt["spx_fwd_20d"] = mkt["spx_close"].shift(-20) / mkt["spx_close"] - 1.0
mkt["vix_fwd_5d"]  = mkt["vix"].shift(-5)  - mkt["vix"]
mkt["vix_fwd_10d"] = mkt["vix"].shift(-10) - mkt["vix"]
mkt["vix_fwd_20d"] = mkt["vix"].shift(-20) - mkt["vix"]

# ── Define Primary / Secondary samples ─────────────────────────────────
print("\nDefining Primary / Secondary samples...")

# Base eligibility: normal-state day with all features valid
base = (
    mkt["normal_state"]
    & mkt["ivp_252"].notna()
    & mkt["ma50"].notna()
    & mkt["vix_5d_change"].notna()
)

# Gate F (SPEC-105 v2): IVP_252 < 55 OR VIX < 15
gate_f_pass = base & ((mkt["ivp_252"] < 55.0) | (mkt["vix"] < 15.0))
gate_f_block = base & ~gate_f_pass

# BPS_NNB entry filter: IVP_252 < 55
bps_nnb_entry_block = base & (mkt["ivp_252"] >= 55.0)

# The 5 other benign conditions
benign_others_pass = (
    (mkt["above_ma50"] == 1)
    & (mkt["ddath"] > -0.04)
    & (mkt["vix"] < 22.0)
    & (mkt["vix_5d_change"] <= 1.5)
)

# PRIMARY: Gate F blocked because IVP>=55 AND VIX>=15, AND other 5 conditions pass
# (BPS_NNB also blocked automatically because IVP>=55)
primary_mask = (
    base
    & (mkt["ivp_252"] >= 55.0)
    & (mkt["vix"] >= 15.0)
    & benign_others_pass
    & bps_nnb_entry_block
)

# SECONDARY: Gate F blocked because one of the other 5 conditions fails
# (could overlap with IVP>=55 condition; key distinction is "otherwise benign" is FALSE)
secondary_mask = (
    base
    & gate_f_block
    & ~benign_others_pass
    & bps_nnb_entry_block   # BPS_NNB entry is blocked when IVP >= 55
)

# Some Secondary days may also have BPS_NNB entry NOT blocked (IVP < 55 but VIX >= 15
# means Gate F pass via VIX escape; if other conditions fail, Gate F still off
# but BPS_NNB may still enter). Track separately.
secondary_bps_entry_open = (
    base
    & gate_f_block
    & ~benign_others_pass
    & (mkt["ivp_252"] < 55.0)
)

print(f"  Total base normal-state days with features: {int(base.sum())}")
print(f"  Primary sample (Q075 main target): {int(primary_mask.sum())}")
print(f"  Secondary sample (other-condition-failed, IVP-blocked too): {int(secondary_mask.sum())}")
print(f"  Secondary, BPS entry still open (IVP<55): {int(secondary_bps_entry_open.sum())}")

# ── 4-Type classifier ─────────────────────────────────────────────────
print("\nClassifying days into Type A/B/C/D...")

def classify_type(row):
    """Per P0 §4.1 4-Type partition."""
    if row["vix"] < 15:
        return "A_false_block"
    if (row["spx_close"] <= row["ma50"]) or (row["ma50_slope_5d"] <= 0) or (row["ddath"] <= -0.06):
        return "D_trend_deteriorated"
    # Type B vs C split: VIX trend + ddATH evolution
    is_b = (
        row["ivp_252"] >= 70
        and row["vix_5d_change"] > 0.5
        and (row["ddath_change_5d"] is not None and row["ddath_change_5d"] <= -0.01)  # ddATH worsening ≥ +1pp
    )
    if is_b:
        return "B_transition_warning"
    return "C_high_vol_controlled"

# Apply classifier to primary + secondary
for sample_name, mask in [("primary", primary_mask), ("secondary", secondary_mask)]:
    df_s = mkt[mask].copy()
    df_s["type"] = df_s.apply(classify_type, axis=1)
    df_s["sample"] = sample_name
    if sample_name == "primary":
        primary_days = df_s
    else:
        secondary_days = df_s

print(f"\n  Primary Type counts:")
for t in ["A_false_block", "B_transition_warning", "C_high_vol_controlled", "D_trend_deteriorated"]:
    n = (primary_days["type"] == t).sum()
    pct = n / len(primary_days) * 100 if len(primary_days) > 0 else 0
    flag = " ⚠️" if t in ("A_false_block", "D_trend_deteriorated") and pct > 5 else ""
    print(f"    {t}: {n} ({pct:.1f}%){flag}")

print(f"\n  Secondary Type counts:")
for t in ["A_false_block", "B_transition_warning", "C_high_vol_controlled", "D_trend_deteriorated"]:
    n = (secondary_days["type"] == t).sum()
    pct = n / len(secondary_days) * 100 if len(secondary_days) > 0 else 0
    print(f"    {t}: {n} ({pct:.1f}%)")

# Sanity check
sanity_pass = True
for t in ["A_false_block", "D_trend_deteriorated"]:
    pct = (primary_days["type"] == t).sum() / len(primary_days) * 100 if len(primary_days) > 0 else 0
    if pct > 5.0:
        print(f"\n  ⚠️ SANITY WARNING: Primary Type {t} = {pct:.1f}% (>5%). Review sample construction.")
        sanity_pass = False

if sanity_pass:
    print(f"\n  ✓ Sanity check pass: Type A and D both ≤ 5% of Primary sample")

# ── Bucketing ──────────────────────────────────────────────────────────
def bucket_vix(v):
    if pd.isna(v): return "NA"
    if v < 17: return "1_15-17"
    if v < 19: return "2_17-19"
    return "3_19-22"

def bucket_ivp(ivp):
    if pd.isna(ivp): return "NA"
    if ivp < 70: return "1_55-70"
    if ivp < 85: return "2_70-85"
    return "3_85+"

def bucket_vix5d(c):
    if pd.isna(c): return "NA"
    if c < -0.5: return "1_falling"
    if c <= 0.5: return "2_flat"
    return "3_rising"

def bucket_ddath(d):
    if pd.isna(d): return "NA"
    if d > -0.02: return "1_0_to_-2"
    return "2_-2_to_-4"   # Primary stops at -4 by construction

for df_s in [primary_days, secondary_days]:
    df_s["bk_vix"]   = df_s["vix"].apply(bucket_vix)
    df_s["bk_ivp"]   = df_s["ivp_252"].apply(bucket_ivp)
    df_s["bk_vix5d"] = df_s["vix_5d_change"].apply(bucket_vix5d)
    df_s["bk_ddath"] = df_s["ddath"].apply(bucket_ddath)
    df_s["year"]     = df_s.index.year

# ── Hypothetical payoffs (per 1 contract, 14 DTE) ─────────────────────
print("\nComputing hypothetical payoffs H1-H5 per blocked day...")

# Assumptions (transparent, per 2nd Quant Q4 + Q5):
HOLD_DTE = 14
WIDTH_POINTS = 25            # 25-point SPX wide spread (~0.5% at SPX 5000)
FRICTION_PER_TRADE = 50.0    # $50 round-trip per defined-risk trade
STOP_MULT = 2.0              # exit at -2x credit (cluster rule below also applies)

def hypothetical_payoffs(idx_loc, mkt_idx):
    """Compute H1-H5 per 1 contract for a blocked day at integer position idx_loc.
    Uses backward-looking inputs at idx_loc and forward realized at idx_loc+HOLD_DTE.
    """
    row = mkt_idx.iloc[idx_loc]
    spx_0 = row["spx_close"]
    vix_0 = row["vix"]
    ivp_0 = row["ivp_252"]

    # Forward SPX at exit
    fwd_idx = min(idx_loc + HOLD_DTE, len(mkt_idx) - 1)
    spx_t = mkt_idx.iloc[fwd_idx]["spx_close"]
    if pd.isna(spx_t):
        spx_t = spx_0

    fwd_ret = spx_t / spx_0 - 1.0

    # Sigma over HOLD_DTE (using VIX as IV proxy)
    sigma = spx_0 * (vix_0 / 100.0) * (HOLD_DTE / 252.0) ** 0.5

    # Credit estimation: rich premium when IVP high
    credit_frac = 0.30 + min(0.20, (ivp_0 / 100.0) * 0.20)   # 30-50% of width
    credit = WIDTH_POINTS * credit_frac * 100.0              # $/contract (×100 multiplier)
    max_loss = WIDTH_POINTS * 100.0 - credit
    stop_loss = STOP_MULT * credit

    # H1 cash / BOXX: daily yield over HOLD_DTE
    h1 = NLV * CASH_YIELD / 252.0 * HOLD_DTE  # $ per HOLD_DTE on full NLV (informational)
    # But per-trade equivalent: scale to capital at risk = max_loss
    h1_per_capital = max_loss * CASH_YIELD / 252.0 * HOLD_DTE  # $ per 1 contract per HOLD_DTE
    # Use the per-capital figure for fair comparison

    # H2 BPS_NNB counterfactual: use combined.spx_pnl summed over HOLD_DTE
    if combined.index[0] <= mkt_idx.index[idx_loc] and idx_loc < len(mkt_idx):
        dt_0 = mkt_idx.index[idx_loc]
        if dt_0 in combined.index:
            cb_loc = combined.index.get_loc(dt_0)
            fwd_cb = min(cb_loc + HOLD_DTE, len(combined) - 1)
            h2 = combined["spx_pnl"].iloc[cb_loc:fwd_cb + 1].sum()
        else:
            h2 = np.nan
    else:
        h2 = np.nan

    # H3 short-DTE BPS (low-delta, ~1 sigma OTM short strike)
    short_strike_h3 = spx_0 - 1.0 * sigma
    long_strike_h3  = short_strike_h3 - WIDTH_POINTS
    if spx_t >= short_strike_h3:
        pnl_h3 = credit
    elif spx_t <= long_strike_h3:
        pnl_h3 = -max_loss
    else:
        # Linear interp in spread zone
        pnl_h3 = credit - (short_strike_h3 - spx_t) * 100.0
    # Apply stop: if realized intra-period worst would've breached -stop_loss
    # (use intra-period min as worst proxy)
    intra = mkt_idx.iloc[idx_loc + 1: fwd_idx + 1]["spx_close"]
    if len(intra) > 0:
        worst_intra = intra.min()
        if worst_intra <= short_strike_h3:
            # Estimate worst intra PnL: same linear interp but at worst_intra
            if worst_intra <= long_strike_h3:
                worst_pnl = -max_loss
            else:
                worst_pnl = credit - (short_strike_h3 - worst_intra) * 100.0
            if worst_pnl < -stop_loss:
                pnl_h3 = -stop_loss
    pnl_h3 -= FRICTION_PER_TRADE

    # H4 small iron condor (call + put wings, both at ~1 sigma)
    # Use 1/3 size adjustment via credit reduction (smaller position)
    call_short = spx_0 + 1.0 * sigma
    call_long  = call_short + WIDTH_POINTS
    call_credit = WIDTH_POINTS * credit_frac * 100.0 * 0.8  # call wing slightly cheaper
    call_max_loss = WIDTH_POINTS * 100.0 - call_credit
    if spx_t <= call_short:
        pnl_call = call_credit
    elif spx_t >= call_long:
        pnl_call = -call_max_loss
    else:
        pnl_call = call_credit - (spx_t - call_short) * 100.0
    # Put side same as H3 (already computed above as pnl_h3 + friction)
    pnl_put_clean = pnl_h3 + FRICTION_PER_TRADE  # back out friction for clean put side
    # IC PnL = put + call - friction (one round-trip pair)
    pnl_h4_raw = pnl_put_clean + pnl_call
    # Scale to "small IC" = 1/3 size of H3
    pnl_h4 = pnl_h4_raw / 3.0 - FRICTION_PER_TRADE

    # H5 bear call spread (call side only)
    pnl_h5 = pnl_call - FRICTION_PER_TRADE

    return {
        "h1_cash": h1_per_capital,
        "h2_bps_nnb_counterfactual": h2,
        "h3_short_dte_bps": pnl_h3,
        "h4_small_ic": pnl_h4,
        "h5_bcs": pnl_h5,
        "credit_est": credit,
        "max_loss": max_loss,
        "sigma_14d": sigma,
        "fwd_ret": fwd_ret,
    }

# Apply to all blocked days
mkt_idx = mkt.reset_index()  # idx 0..n-1
# Build lookup of position
for sample_name, df_s in [("primary", primary_days), ("secondary", secondary_days)]:
    print(f"  Computing payoffs for {sample_name} ({len(df_s)} days)...")
    h_rows = []
    for d in df_s.index:
        try:
            loc = mkt.index.get_loc(d)
        except KeyError:
            continue
        h = hypothetical_payoffs(loc, mkt)
        h["date"] = d
        h_rows.append(h)
    h_df = pd.DataFrame(h_rows).set_index("date")
    df_s = df_s.join(h_df, how="left")
    if sample_name == "primary":
        primary_days = df_s
    else:
        secondary_days = df_s

# Cluster rule: limit to first day per consecutive-blocked cluster (no second entry per P0 §5.1)
def first_per_cluster(df_s):
    df_s = df_s.sort_index()
    is_first = pd.Series(True, index=df_s.index)
    prev = None
    for i, d in enumerate(df_s.index):
        if prev is not None and (d - prev).days <= 3:  # within 3 cal days = same cluster
            is_first.iloc[i] = False
        prev = d
    return is_first

primary_days["is_first_in_cluster"] = first_per_cluster(primary_days)
secondary_days["is_first_in_cluster"] = first_per_cluster(secondary_days)

# Forward measures
fwd_cols = ["spx_fwd_5d", "spx_fwd_10d", "spx_fwd_20d",
            "vix_fwd_5d", "vix_fwd_10d", "vix_fwd_20d",
            "stress_in_next_5d", "stress_in_next_10d", "stress_in_next_20d",
            "second_leg_in_next_20d", "second_leg_in_next_60d"]
for col in fwd_cols:
    primary_days[col] = mkt.loc[primary_days.index, col].values
    secondary_days[col] = mkt.loc[secondary_days.index, col].values

# ── Capital context per bucket (proxy) ────────────────────────────────
# Use combined data: spx_pnl variance as proxy for SPX exposure level
# Q42 active proxy: |q42a_pnl| > 0
# Cash residual proxy: cash_pnl > 0 means net cash positive
combined["q42_active"] = (combined["q42a_pnl"].abs() > 1.0).astype(int)

# ── Output: per-day samples ────────────────────────────────────────────
keep_cols = ["sample", "type", "vix", "ivp_252", "vix_5d_change", "ddath", "ddath_change_5d",
             "above_ma50", "ma50_slope_5d", "year",
             "bk_vix", "bk_ivp", "bk_vix5d", "bk_ddath",
             "is_first_in_cluster",
             "h1_cash", "h2_bps_nnb_counterfactual", "h3_short_dte_bps",
             "h4_small_ic", "h5_bcs", "credit_est", "max_loss", "sigma_14d", "fwd_ret",
             "spx_fwd_5d", "spx_fwd_10d", "spx_fwd_20d",
             "vix_fwd_5d", "vix_fwd_10d", "vix_fwd_20d",
             "stress_in_next_5d", "stress_in_next_10d", "stress_in_next_20d",
             "second_leg_in_next_20d", "second_leg_in_next_60d"]

primary_days[keep_cols].to_csv(OUT / "q075_p1_primary_sample_days.csv")
secondary_days[keep_cols].to_csv(OUT / "q075_p1_secondary_sample_days.csv")

# ── Type classification summary ───────────────────────────────────────
type_rows = []
for sample_name, df_s in [("primary", primary_days), ("secondary", secondary_days)]:
    for y, sub in df_s.groupby("year"):
        for t in ["A_false_block", "B_transition_warning", "C_high_vol_controlled", "D_trend_deteriorated"]:
            n = (sub["type"] == t).sum()
            type_rows.append({"sample": sample_name, "year": y, "type": t, "n_days": int(n)})
pd.DataFrame(type_rows).to_csv(OUT / "q075_p1_type_classification.csv", index=False)

# ── Bucket forward measures + hypothetical PnL (FIRST in cluster only) ──
# Critical: per-trade aggregates use FIRST-IN-CLUSTER days only (no second entry)
print("\n" + "=" * 70)
print("Per-Type / per-bucket forward + hypothetical PnL (Primary, first-in-cluster only)")
print("=" * 70)

primary_first = primary_days[primary_days["is_first_in_cluster"]]
print(f"\nPrimary first-in-cluster (trade-eligible) days: {len(primary_first)} of {len(primary_days)}")

bucket_rows = []
for sample_name, df_s in [("primary", primary_first), ("secondary", secondary_days[secondary_days["is_first_in_cluster"]])]:
    for t, sub_t in df_s.groupby("type"):
        if len(sub_t) == 0:
            continue
        # Aggregate without further bucketing for first-screen
        for bk_label, bk_col in [("vix", "bk_vix"), ("ivp", "bk_ivp")]:
            for b, sub_b in sub_t.groupby(bk_col):
                bucket_rows.append({
                    "sample": sample_name,
                    "type": t,
                    "bucket_axis": bk_label,
                    "bucket": b,
                    "n_days": len(sub_b),
                    "avg_fwd_spx_5d_pct":   sub_b["spx_fwd_5d"].mean() * 100,
                    "avg_fwd_spx_20d_pct":  sub_b["spx_fwd_20d"].mean() * 100,
                    "avg_fwd_vix_change_5d": sub_b["vix_fwd_5d"].mean(),
                    "p_stress_10d":         sub_b["stress_in_next_10d"].mean() * 100,
                    "p_stress_20d":         sub_b["stress_in_next_20d"].mean() * 100,
                    "p_second_leg_60d":     sub_b["second_leg_in_next_60d"].mean() * 100,
                    "h1_cash_avg":          sub_b["h1_cash"].mean(),
                    "h2_bps_counter_avg":   sub_b["h2_bps_nnb_counterfactual"].mean(),
                    "h3_short_dte_bps_avg": sub_b["h3_short_dte_bps"].mean(),
                    "h4_small_ic_avg":      sub_b["h4_small_ic"].mean(),
                    "h5_bcs_avg":           sub_b["h5_bcs"].mean(),
                    "h3_hit_rate":          (sub_b["h3_short_dte_bps"] > 0).mean() * 100,
                    "h4_hit_rate":          (sub_b["h4_small_ic"] > 0).mean() * 100,
                    "h5_hit_rate":          (sub_b["h5_bcs"] > 0).mean() * 100,
                })
pd.DataFrame(bucket_rows).to_csv(OUT / "q075_p1_bucket_forward.csv", index=False)

# ── Hypothetical PnL summary per Type (Primary, first-in-cluster) ─────
print("\n" + "=" * 70)
print("Hypothetical payoff cumulative summary per Type (Primary, first-in-cluster)")
print("=" * 70)
print(f"\nAssumptions:")
print(f"  Hold DTE: {HOLD_DTE} days")
print(f"  Spread width: {WIDTH_POINTS} SPX points")
print(f"  Friction: ${FRICTION_PER_TRADE} round trip per trade")
print(f"  Stop: {STOP_MULT}x credit")
print(f"  Cluster rule: 1 entry per consecutive blocked cluster (≤ 3 cal days gap)")

hypo_rows = []
print(f"\n{'Type':<26} {'n':>5} {'H1 cash':>10} {'H2 BPS':>10} {'H3 sBPS':>10} {'H4 IC':>10} {'H5 BCS':>10}")
print("-" * 92)
for t, sub_t in primary_first.groupby("type"):
    if len(sub_t) == 0:
        continue
    h1 = sub_t["h1_cash"].sum()
    h2 = sub_t["h2_bps_nnb_counterfactual"].sum()
    h3 = sub_t["h3_short_dte_bps"].sum()
    h4 = sub_t["h4_small_ic"].sum()
    h5 = sub_t["h5_bcs"].sum()
    print(f"{t:<26} {len(sub_t):>5} {h1:>+10,.0f} {h2:>+10,.0f} {h3:>+10,.0f} {h4:>+10,.0f} {h5:>+10,.0f}")
    hypo_rows.append({
        "type": t,
        "n_trades_first_in_cluster": len(sub_t),
        "h1_cash_cum": h1,
        "h2_bps_nnb_counterfactual_cum": h2,
        "h3_short_dte_bps_cum": h3,
        "h4_small_ic_cum": h4,
        "h5_bcs_cum": h5,
        "h3_worst": sub_t["h3_short_dte_bps"].min(),
        "h4_worst": sub_t["h4_small_ic"].min(),
        "h5_worst": sub_t["h5_bcs"].min(),
        "h3_hit_pct": (sub_t["h3_short_dte_bps"] > 0).mean() * 100,
        "h4_hit_pct": (sub_t["h4_small_ic"] > 0).mean() * 100,
        "h5_hit_pct": (sub_t["h5_bcs"] > 0).mean() * 100,
    })
pd.DataFrame(hypo_rows).to_csv(OUT / "q075_p1_hypothetical_pnl.csv", index=False)

# ── Capital context per bucket (Primary) ──────────────────────────────
cap_rows = []
for t, sub_t in primary_days.groupby("type"):
    if len(sub_t) == 0:
        continue
    # Lookup combined data on those dates
    dates_in_combined = sub_t.index.intersection(combined.index)
    if len(dates_in_combined) == 0:
        continue
    cb_sub = combined.loc[dates_in_combined]
    q42_pct = cb_sub["q42_active"].mean() * 100
    avg_cash_pnl = cb_sub["cash_pnl"].mean()
    avg_spx_pnl_abs = cb_sub["spx_pnl"].abs().mean()
    cap_rows.append({
        "type": t,
        "n_days": len(dates_in_combined),
        "q42_active_pct_of_days": q42_pct,
        "avg_daily_cash_pnl_usd": avg_cash_pnl,
        "avg_daily_spx_pnl_abs_usd": avg_spx_pnl_abs,
        "spx_exposure_proxy_note": "spx_pnl variance proxy for active SPX position size",
    })
pd.DataFrame(cap_rows).to_csv(OUT / "q075_p1_capital_context.csv", index=False)

# ── First-screen summary table (2nd Quant required) ──────────────────
print("\n" + "=" * 70)
print("FIRST-SCREEN SUMMARY (Primary sample, all clusters)")
print("=" * 70)
fs_rows = []
total_primary = len(primary_days)
print(f"\nPrimary sample total: {total_primary} days")
print(f"Primary sample first-in-cluster: {len(primary_first)} days")
print(f"Sanity check: Type A + D combined ≤ 5% of Primary: ", end="")
ad_pct = ((primary_days["type"].isin(["A_false_block", "D_trend_deteriorated"])).sum() / total_primary * 100) if total_primary > 0 else 0
print(f"{ad_pct:.1f}% {'✓ PASS' if ad_pct <= 5 else '⚠️ WARNING'}")

print(f"\n{'Type':<26} {'n_all':>6} {'%':>5} {'n_first':>7} {'p_stress_10d':>13} {'fwd_spx_20d':>12} {'best_hypo':>15}")
print("-" * 96)
for t in ["A_false_block", "B_transition_warning", "C_high_vol_controlled", "D_trend_deteriorated"]:
    sub_all = primary_days[primary_days["type"] == t]
    sub_first = primary_first[primary_first["type"] == t]
    n_all = len(sub_all)
    pct_all = n_all / total_primary * 100 if total_primary > 0 else 0
    n_first = len(sub_first)
    if n_first > 0:
        p_stress = sub_first["stress_in_next_10d"].mean() * 100
        fwd_spx = sub_first["spx_fwd_20d"].mean() * 100
        # Best hypothetical (cumulative)
        hypos = {
            "H1 cash": sub_first["h1_cash"].sum(),
            "H3 sBPS": sub_first["h3_short_dte_bps"].sum(),
            "H4 IC":   sub_first["h4_small_ic"].sum(),
            "H5 BCS":  sub_first["h5_bcs"].sum(),
        }
        best = max(hypos, key=lambda k: hypos[k])
        best_str = f"{best} ${hypos[best]:+,.0f}"
    else:
        p_stress = float("nan")
        fwd_spx = float("nan")
        best_str = "n/a"
    print(f"{t:<26} {n_all:>6d} {pct_all:>4.1f}% {n_first:>7d} {p_stress:>12.1f}% {fwd_spx:>+11.2f}% {best_str:>15}")
    fs_rows.append({
        "type": t,
        "n_all_days": n_all,
        "pct_of_primary": pct_all,
        "n_first_in_cluster": n_first,
        "p_stress_10d_pct": p_stress,
        "avg_fwd_spx_20d_pct": fwd_spx,
        "best_hypothetical_label": best if n_first > 0 else "n/a",
        "best_hypothetical_cum_usd": hypos[best] if n_first > 0 else 0,
    })
pd.DataFrame(fs_rows).to_csv(OUT / "q075_p1_first_screen.csv", index=False)

# ── Branching guidance per 2nd Quant ─────────────────────────────────
print("\n" + "=" * 70)
print("Branching guidance (per 2nd Quant P0 review)")
print("=" * 70)
b_n = (primary_days["type"] == "B_transition_warning").sum()
c_n = (primary_days["type"] == "C_high_vol_controlled").sum()
b_pct = b_n / total_primary * 100 if total_primary > 0 else 0
c_pct = c_n / total_primary * 100 if total_primary > 0 else 0

if b_pct > c_pct:
    dominant = "B (transition warning)"
    print(f"\nType B dominates ({b_pct:.1f}% vs Type C {c_pct:.1f}%).")
    sub_b = primary_first[primary_first["type"] == "B_transition_warning"]
    if len(sub_b) > 0:
        p_stress_b = sub_b["stress_in_next_10d"].mean() * 100
        worst_h3 = sub_b["h3_short_dte_bps"].min() if len(sub_b) > 0 else 0
        worst_h4 = sub_b["h4_small_ic"].min() if len(sub_b) > 0 else 0
        print(f"  Type B P(stress 10d): {p_stress_b:.1f}%")
        print(f"  Type B worst H3 (sBPS): ${worst_h3:+,.0f}")
        print(f"  Type B worst H4 (IC):   ${worst_h4:+,.0f}")
        if p_stress_b > 35:
            print(f"  → Recommendation: Likely DOCUMENT path (blocked days are cash days)")
        else:
            print(f"  → Recommendation: Proceed to P2 with caution (Type B has manageable stress prob)")
else:
    dominant = "C (high-vol controlled)"
    print(f"\nType C dominates ({c_pct:.1f}% vs Type B {b_pct:.1f}%).")
    sub_c = primary_first[primary_first["type"] == "C_high_vol_controlled"]
    if len(sub_c) > 0:
        p_stress_c = sub_c["stress_in_next_10d"].mean() * 100
        h3 = sub_c["h3_short_dte_bps"].sum()
        h4 = sub_c["h4_small_ic"].sum()
        h5 = sub_c["h5_bcs"].sum()
        h1 = sub_c["h1_cash"].sum()
        print(f"  Type C P(stress 10d): {p_stress_c:.1f}%")
        print(f"  Type C cumulative: H1 cash=${h1:+,.0f}, H3=${h3:+,.0f}, H4=${h4:+,.0f}, H5=${h5:+,.0f}")
        best_strat = max([("H3 sBPS", h3), ("H4 IC", h4), ("H5 BCS", h5)], key=lambda x: x[1])
        if best_strat[1] > h1:
            print(f"  → Recommendation: Proceed to P2 with {best_strat[0]} as primary candidate")
        else:
            print(f"  → Recommendation: Cash beats all candidates; DOCUMENT path")

print("\n" + "=" * 70)
print("Q075 P1 done. CSVs written to research/q075/")
print("=" * 70)
print(f"\nReminder: P1 is DIAGNOSTIC. Do NOT promote any candidate from P1 alone.")
print(f"          P2 candidate priority must be derived from this attribution data.")
