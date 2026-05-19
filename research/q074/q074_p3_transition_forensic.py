"""Q074 P3 — Transition-Risk Forensic (CORE).

Per P0 + 2nd Quant Revisions 2/3 + PM P2 follow-up:
  - Primary transition window: booster active in prior 10 TD before stress trigger
  - Secondary diagnostic: booster active in prior 20 TD before stress trigger
  - Severity classification:
      mild   = stress trigger without second-leg within next 20d
      acute  = stress trigger AND second-leg within next 20d
      failed = booster active, stress triggers, incremental booster PnL < 0
  - Incremental PnL = candidate PnL - B0 baseline PnL (NOT total)
  - Crisis-specific examination: 2000-03, 2007-07, 2018-02, 2020-02, 2022-01
  - VIX 20-22 attribution for B2/B4

Outputs:
  q074_p3_transition_events.csv (every stress trigger + booster prior + incremental loss)
  q074_p3_severity_summary.csv (mild/acute/failed counts per candidate)
  q074_p3_crisis_breakdown.csv (5 named crisis windows)
  q074_p3_top10_booster_losses.csv (worst 10 booster-window incremental losses per candidate)
  q074_p3_vix2022_attribution.csv (B2/B4 specific)
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

FRICTION_ANN_SPX = 0.0035
FRICTION_ANN_Q42 = 0.0005
CASH_YIELD = 0.043
P13R_SPX = 0.60
P13R_Q42 = 0.10
HV_ALLOC = 0.0
Q42_ALLOC = 0.175
STRESS_SPX_CAP = 0.50
SECOND_LEG_CAP = 0.40

print("Q074 P3 — Transition-Risk Forensic", flush=True)
print("=" * 70)

# Load and build market features (same as P2)
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

# Booster signals
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

# Build per-candidate daily PnL series + booster mask
def build_candidate(booster_fn, booster_cap):
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
    spx_drag = FRICTION_ANN_SPX * NLV * (df["spx_alloc"] / P13R_SPX) / 252.0
    q42_drag = FRICTION_ANN_Q42 * NLV * (Q42_ALLOC / P13R_Q42) / 252.0
    df["total_pnl"] = (spx_pnl - spx_drag) + (q42_pnl - q42_drag) + cash_pnl
    return df

print("\nBuilding 5 candidates...")
candidates = {
    "B0_baseline": build_candidate(None, None),
    "B1_strict_85": build_candidate(b1_strict, 0.85),
    "B2_moderate_85": build_candidate(b2_moderate, 0.85),
    "B3_strict_90": build_candidate(b1_strict, 0.90),
    "B4_moderate_90": build_candidate(b2_moderate, 0.90),
}

# ── Identify all stress trigger events ────────────────────────────────
# Stress trigger event = first day when stress_active becomes True (from False prev day)
b0 = candidates["B0_baseline"]
b0["stress_active_prev"] = b0["stress_active"].shift(1).fillna(False)
b0["stress_trigger"] = b0["stress_active"] & ~b0["stress_active_prev"]
trigger_dates = b0.index[b0["stress_trigger"]]
print(f"Stress trigger events (26y): {len(trigger_dates)}")

# ── Per-trigger transition analysis per candidate ─────────────────────
print(f"\nAnalyzing transition windows per candidate...")

def analyze_transitions(cand_name, df_cand, b0_df, lookback_days=10):
    """For each stress trigger, look back `lookback_days` and compute:
    - booster_active_count in window (any booster_active days in 10d/20d prior?)
    - incremental_pnl_window = (cand - b0) cumulative over the lookback window
    - severity: mild (no 2nd-leg in next 20d) / acute (2nd-leg in next 20d) / failed (booster active + incremental < 0)
    """
    rows = []
    for trigger_date in trigger_dates:
        trigger_idx = df_cand.index.get_loc(trigger_date)
        if trigger_idx < lookback_days:
            continue  # not enough history
        window_start_idx = trigger_idx - lookback_days
        window = df_cand.iloc[window_start_idx:trigger_idx]
        b0_window = b0_df.iloc[window_start_idx:trigger_idx]

        booster_days_in_window = window["booster_active"].sum()

        # Incremental PnL during the booster-active days in this window (only)
        booster_mask = window["booster_active"]
        if booster_mask.any():
            cand_pnl_booster_days = window.loc[booster_mask, "total_pnl"].sum()
            b0_pnl_booster_days = b0_window.loc[booster_mask, "total_pnl"].sum()
            incremental_pnl = cand_pnl_booster_days - b0_pnl_booster_days
        else:
            incremental_pnl = 0.0

        # Determine severity: look forward 20 days from trigger
        forward_end = min(trigger_idx + 20, len(df_cand) - 1)
        forward_window = df_cand.iloc[trigger_idx:forward_end + 1]
        has_second_leg = forward_window["second_leg_active"].any()

        severity = None
        if has_second_leg:
            severity = "acute"
        else:
            severity = "mild"
        # Add "failed-benign" overlay
        is_failed = (booster_days_in_window > 0) and (incremental_pnl < 0)

        # VIX 20-22 attribution: count of booster-active days in window where VIX 20-22
        vix_20_22_days = ((window["booster_active"]) & (window["vix"] >= 20) & (window["vix"] < 22)).sum()

        rows.append({
            "candidate": cand_name,
            "trigger_date": trigger_date.strftime("%Y-%m-%d"),
            "lookback_days": lookback_days,
            "booster_active_in_window": int(booster_days_in_window),
            "vix_20_22_booster_days": int(vix_20_22_days),
            "incremental_pnl_usd": round(incremental_pnl, 0),
            "incremental_pct_nlv": round(incremental_pnl / NLV * 100, 3),
            "has_second_leg_next_20d": bool(has_second_leg),
            "severity": severity,
            "failed_benign": bool(is_failed),
        })
    return rows

all_events = []
for cand_name in ["B1_strict_85", "B2_moderate_85", "B3_strict_90", "B4_moderate_90"]:
    df_cand = candidates[cand_name]
    # Primary 10d window
    for row in analyze_transitions(cand_name, df_cand, b0, lookback_days=10):
        row["window_type"] = "10d_primary"
        all_events.append(row)
    # Secondary 20d window
    for row in analyze_transitions(cand_name, df_cand, b0, lookback_days=20):
        row["window_type"] = "20d_secondary"
        all_events.append(row)

events_df = pd.DataFrame(all_events)
events_df.to_csv(OUT / "q074_p3_transition_events.csv", index=False)
print(f"\nTotal transition event rows: {len(events_df)} (across 4 candidates × 2 windows × {len(trigger_dates)} triggers)")

# ── Severity summary per candidate ───────────────────────────────────
print("\n" + "=" * 70)
print("Severity Summary (per candidate, primary 10d window)")
print("=" * 70)
print(f"{'Candidate':<20} {'mild':>6} {'acute':>7} {'failed_benign':>15} {'cum_incremental_loss_$':>22}")

summary_rows = []
for cand in ["B1_strict_85", "B2_moderate_85", "B3_strict_90", "B4_moderate_90"]:
    sub10 = events_df[(events_df["candidate"] == cand) & (events_df["window_type"] == "10d_primary")]
    sub_booster_present = sub10[sub10["booster_active_in_window"] > 0]
    mild = (sub_booster_present["severity"] == "mild").sum()
    acute = (sub_booster_present["severity"] == "acute").sum()
    failed = sub_booster_present["failed_benign"].sum()
    total_inc = sub_booster_present["incremental_pnl_usd"].sum()
    neg_inc = sub_booster_present[sub_booster_present["incremental_pnl_usd"] < 0]["incremental_pnl_usd"].sum()
    print(f"{cand:<20} {mild:>6} {acute:>7} {failed:>15} ${total_inc:>+20,.0f}")
    summary_rows.append({
        "candidate": cand,
        "mild_transitions": int(mild),
        "acute_transitions": int(acute),
        "failed_benign_count": int(failed),
        "total_booster_present_transitions": int(len(sub_booster_present)),
        "cum_incremental_pnl_window10d_usd": float(total_inc),
        "cum_incremental_loss_window10d_usd": float(neg_inc),
        "transitions_with_booster_active": int(len(sub_booster_present)),
        "transitions_total": int(len(sub10)),
    })

pd.DataFrame(summary_rows).to_csv(OUT / "q074_p3_severity_summary.csv", index=False)

# ── Crisis-specific examination ──────────────────────────────────────
print("\n" + "=" * 70)
print("Crisis-specific Examination (10d windows around named events)")
print("=" * 70)

# Find first stress trigger within each named crisis period
crisis_windows = {
    "DotCom_2000_03": ("2000-03-01", "2000-04-30"),
    "PreGFC_2007_07": ("2007-07-01", "2007-09-30"),
    "Vol_2018_02":    ("2018-01-15", "2018-03-15"),
    "COVID_2020_02":  ("2020-02-15", "2020-03-31"),
    "Bear_2022_01":   ("2022-01-01", "2022-02-28"),
}

crisis_rows = []
for crisis_name, (s, e) in crisis_windows.items():
    s_ts, e_ts = pd.Timestamp(s), pd.Timestamp(e)
    # Find first trigger in this period
    triggers_in_range = trigger_dates[(trigger_dates >= s_ts) & (trigger_dates <= e_ts)]
    if len(triggers_in_range) == 0:
        print(f"\n[{crisis_name}] No stress trigger in {s} - {e}")
        continue
    first_trigger = triggers_in_range[0]
    print(f"\n[{crisis_name}] First stress trigger: {first_trigger.strftime('%Y-%m-%d')}")
    for cand in ["B1_strict_85", "B2_moderate_85", "B3_strict_90", "B4_moderate_90"]:
        df_cand = candidates[cand]
        trigger_idx = df_cand.index.get_loc(first_trigger)
        window = df_cand.iloc[max(0, trigger_idx - 20):trigger_idx]
        b0_window = b0.iloc[max(0, trigger_idx - 20):trigger_idx]
        booster_mask = window["booster_active"]
        if booster_mask.any():
            inc_20 = (window.loc[booster_mask, "total_pnl"].sum() -
                      b0_window.loc[booster_mask, "total_pnl"].sum())
        else:
            inc_20 = 0
        booster_days_20 = booster_mask.sum()
        print(f"   {cand:<18} booster active {booster_days_20}/20d, incremental ${inc_20:+,.0f}")
        crisis_rows.append({
            "crisis": crisis_name,
            "trigger_date": first_trigger.strftime("%Y-%m-%d"),
            "candidate": cand,
            "booster_days_in_20d": int(booster_days_20),
            "incremental_pnl_20d": round(inc_20, 0),
            "incremental_pct_nlv": round(inc_20 / NLV * 100, 3),
        })

pd.DataFrame(crisis_rows).to_csv(OUT / "q074_p3_crisis_breakdown.csv", index=False)

# ── Top-10 worst booster windows per candidate ───────────────────────
print("\n" + "=" * 70)
print("Top-5 Worst Booster Windows (10d primary, per candidate)")
print("=" * 70)

top_rows = []
for cand in ["B1_strict_85", "B2_moderate_85", "B3_strict_90", "B4_moderate_90"]:
    sub = events_df[(events_df["candidate"] == cand) & (events_df["window_type"] == "10d_primary")
                    & (events_df["booster_active_in_window"] > 0)].copy()
    worst5 = sub.nsmallest(5, "incremental_pnl_usd")
    print(f"\n[{cand}]")
    for _, r in worst5.iterrows():
        print(f"  {r['trigger_date']} booster_days={r['booster_active_in_window']} "
              f"VIX_20_22_days={r['vix_20_22_booster_days']} "
              f"incremental ${r['incremental_pnl_usd']:+,.0f} ({r['incremental_pct_nlv']:+.3f}%) "
              f"severity={r['severity']} failed={r['failed_benign']}")
        top_rows.append({**r.to_dict()})

pd.DataFrame(top_rows).to_csv(OUT / "q074_p3_top_booster_losses.csv", index=False)

# ── VIX 20-22 attribution (B2 / B4 specific) ─────────────────────────
print("\n" + "=" * 70)
print("VIX 20-22 Attribution (B2 / B4 — moderate criteria includes VIX < 22)")
print("=" * 70)
for cand in ["B2_moderate_85", "B4_moderate_90"]:
    sub10 = events_df[(events_df["candidate"] == cand) & (events_df["window_type"] == "10d_primary")
                       & (events_df["booster_active_in_window"] > 0)]
    vix2022_dependent = sub10[sub10["vix_20_22_booster_days"] > 0]
    print(f"\n{cand}:")
    print(f"  Transitions with booster active 10d before: {len(sub10)}")
    print(f"  Transitions where booster active included VIX 20-22 days: {len(vix2022_dependent)}")
    print(f"  Their cum incremental PnL: ${vix2022_dependent['incremental_pnl_usd'].sum():+,.0f}")

print("\n" + "=" * 70)
print("Verdict")
print("=" * 70)
print(f"\nReview {OUT / 'q074_p3_severity_summary.csv'} + crisis_breakdown.csv + top_booster_losses.csv")
print("Decision pending PM + 2nd Quant G3 review.")
