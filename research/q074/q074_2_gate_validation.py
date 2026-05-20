"""Q074.2 — Gate F / F2 Portfolio Validation.

Per 2nd Quant REVISE (2026-05-19):
  - Q074.1b Gate F discovery is real, but needs portfolio-level ROE / V1V2V3 / transition validation
  - Run B4-current / B4-F / B4-F2 three-way comparison
  - 8 required checks:
      1. Full portfolio metrics (Net ROE, MaxDD, W20d, W63d, Sharpe, V1/V2/V3)
      2. Newly-added-day PnL attribution
      3. VIX 14-15 sub-bucket attribution (key for F vs F2)
      4. Transition forensic (booster prior 10d/20d, severity, crisis windows)
      5. Walk-forward H1 (2000-2012) / H2 (2013-2026)
      6. Active days % diagnostic (< 60% normal days)
      7. Bootstrap (block=250, 20 seeds) (informational)
      8. Friction sensitivity (informational)

Gate definitions (B4 with 7 conditions, only IVP gate varies):
  Common 6 conditions:
    not stress_active, not second_leg_active,
    above_ma50, ddath > -0.04, vix < 22, vix_5d_change <= 1.5

  Variants:
    B4-current: ivp_252 < 55
    B4-F:       ivp_252 < 55 OR vix < 15
    B4-F2:      ivp_252 < 55 OR vix < 14

Outputs:
  q074_2_portfolio_metrics.csv         — main result table
  q074_2_added_day_attribution.csv     — newly-added day PnL
  q074_2_vix_bucket_attribution.csv    — F-only days by VIX sub-bucket
  q074_2_transition_summary.csv        — severity + cum incremental loss
  q074_2_transition_events.csv         — per-trigger event log
  q074_2_crisis_breakdown.csv          — 5 crisis windows
  q074_2_walkforward.csv               — H1 / H2 split-sample
  q074_2_bootstrap.csv                 — block bootstrap ΔROE noise
  q074_2_top_booster_losses.csv        — top-5 worst booster windows per variant
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
BOOSTER_CAP = 0.90       # all three variants use 90% cap (B4 family)
NORMAL_CAP = 0.80

print("Q074.2 — Gate F / F2 Portfolio Validation", flush=True)
print("=" * 70)

# ── Load data ──────────────────────────────────────────────────────────
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
mkt["normal_state"] = (~mkt["stress_active"] & ~mkt["second_leg_active"])

# ── B4 variant signal functions ────────────────────────────────────────
def _b4_common(row):
    """6 conditions shared across all B4 variants."""
    return (
        not row["stress_active"]
        and not row["second_leg_active"]
        and row["above_ma50"] == 1
        and row["ddath"] > -0.04
        and row["vix"] < 22
        and row["vix_5d_change"] <= 1.5
    )

def b4_current(row):
    return _b4_common(row) and (row["ivp_252"] < 55)

def b4_f(row):
    return _b4_common(row) and ((row["ivp_252"] < 55) or (row["vix"] < 15))

def b4_f2(row):
    return _b4_common(row) and ((row["ivp_252"] < 55) or (row["vix"] < 14))

# ── Simulator ──────────────────────────────────────────────────────────
def build_candidate(name, booster_fn, booster_cap, date_range=None):
    df = combined.copy().join(mkt[["above_ma50", "ma50_slope_pos", "ddath", "vix",
                                    "vix_5d_change", "ivp_252",
                                    "stress_active", "second_leg_active", "normal_state"]],
                              how="left").ffill()
    if date_range is not None:
        s, e = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        df = df[(df.index >= s) & (df.index <= e)].copy()

    valid = df["ivp_252"].notna()
    df["booster_active"] = False
    if booster_fn is not None:
        df.loc[valid, "booster_active"] = df.loc[valid].apply(booster_fn, axis=1)
    df["booster_active"] = df["booster_active"].astype(bool)

    spx_alloc = pd.Series(NORMAL_CAP, index=df.index)
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

    df["cum_pnl"] = df["total_pnl"].cumsum()
    df["equity"] = NLV + df["cum_pnl"]
    df["equity_start"] = df["equity"].shift(1).fillna(NLV)
    df["daily_ret"] = df["total_pnl"] / df["equity_start"]
    df.attrs["name"] = name
    return df

def compute_metrics(df, name):
    years = len(df) / 252
    final_eq = df["equity"].iloc[-1]
    ann_roe = (final_eq / NLV) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    running_max = df["equity"].cummax()
    drawdown = (df["equity"] - running_max) / running_max
    max_dd = drawdown.min()
    worst_20d = df["daily_ret"].rolling(20).sum().min()
    worst_63d = df["daily_ret"].rolling(63).sum().min()
    sharpe = df["daily_ret"].mean() / df["daily_ret"].std() * (252**0.5) if df["daily_ret"].std() > 0 else 0.0

    booster_eligible = df["booster_active"] & ~df["stress_active"] & ~df["second_leg_active"]
    booster_days = int(booster_eligible.sum())
    booster_pct_of_total = booster_days / len(df) * 100
    n_normal = df["normal_state"].sum()
    booster_pct_of_normal = booster_days / n_normal * 100 if n_normal > 0 else 0

    return {
        "candidate": name,
        "n_days": len(df),
        "ann_roe_pct": ann_roe * 100,
        "max_dd_pct": max_dd * 100,
        "worst_20d_pct": worst_20d * 100,
        "worst_63d_pct": worst_63d * 100,
        "sharpe": sharpe,
        "v1_pass_dd28": bool(max_dd >= -0.28),
        "v2_pass_w20d11": bool(worst_20d >= -0.11),
        "v3_pass_w63d17": bool(worst_63d >= -0.17),
        "floor_8_pass": bool(ann_roe >= 0.08),
        "booster_days": booster_days,
        "booster_pct_of_total": booster_pct_of_total,
        "booster_pct_of_normal": booster_pct_of_normal,
        "final_equity_M": final_eq / 1e6,
    }

# ── 1. Full sample portfolio metrics ──────────────────────────────────
print("\n" + "=" * 70)
print("1. Full-sample portfolio metrics (B4-current vs F vs F2)")
print("=" * 70)

variants = [
    ("B0_baseline",  None,        None),
    ("B4_current",   b4_current,  BOOSTER_CAP),
    ("B4_F",         b4_f,        BOOSTER_CAP),
    ("B4_F2",        b4_f2,       BOOSTER_CAP),
]

cands = {}
for name, fn, cap in variants:
    cands[name] = build_candidate(name, fn, cap)

rows = [compute_metrics(cands[n], n) for n, _, _ in variants]
metrics_df = pd.DataFrame(rows)
metrics_df.to_csv(OUT / "q074_2_portfolio_metrics.csv", index=False)

print(f"\n{'Variant':<14} {'ROE %':>7} {'ΔROE pp':>8} {'MaxDD %':>9} {'W20d %':>8} {'W63d %':>8} {'Sharpe':>7} {'BoostDays':>10} {'%Norm':>7}")
print("-" * 90)
baseline = metrics_df[metrics_df["candidate"] == "B4_current"].iloc[0]
for _, r in metrics_df.iterrows():
    droe = r["ann_roe_pct"] - baseline["ann_roe_pct"]
    flag = ""
    if not r["v1_pass_dd28"]: flag += " V1✗"
    if not r["v2_pass_w20d11"]: flag += " V2✗"
    if not r["v3_pass_w63d17"]: flag += " V3✗"
    print(f"{r['candidate']:<14} {r['ann_roe_pct']:>7.3f} {droe:>+7.3f} {r['max_dd_pct']:>9.2f} "
          f"{r['worst_20d_pct']:>8.2f} {r['worst_63d_pct']:>8.2f} {r['sharpe']:>7.2f} "
          f"{r['booster_days']:>10d} {r['booster_pct_of_normal']:>6.1f}%{flag}")

# ── 2. Newly-added-day PnL attribution ────────────────────────────────
print("\n" + "=" * 70)
print("2. Newly-added-day PnL attribution (F/F2 added vs current)")
print("=" * 70)

cur_active = cands["B4_current"]["booster_active"] & ~cands["B4_current"]["stress_active"] & ~cands["B4_current"]["second_leg_active"]

attr_rows = []
for var in ["B4_F", "B4_F2"]:
    df = cands[var]
    var_active = df["booster_active"] & ~df["stress_active"] & ~df["second_leg_active"]
    added_mask = var_active & ~cur_active  # added by variant but blocked by current
    n_added = int(added_mask.sum())
    if n_added == 0:
        continue
    # On added days, total_pnl_variant - total_pnl_current ≈ extra PnL from 80→90 cap
    extra_pnl = (df.loc[added_mask, "total_pnl"] - cands["B4_current"].loc[added_mask, "total_pnl"]).sum()
    daily_avg = extra_pnl / n_added
    hit = (df.loc[added_mask, "total_pnl"] > cands["B4_current"].loc[added_mask, "total_pnl"]).mean() * 100
    spx_pnl_added = combined.loc[added_mask.index[added_mask], "spx_pnl"].copy()
    worst_added_day = spx_pnl_added.min() * (BOOSTER_CAP - NORMAL_CAP) / P13R_SPX  # incremental worst
    years = len(df) / 252
    print(f"\n{var}: {n_added} added days, cum extra PnL ${extra_pnl:+,.0f}, "
          f"avg ${daily_avg:+,.0f}/day, hit {hit:.1f}%")
    print(f"   Annualized contribution: ${extra_pnl / years:+,.0f}/yr "
          f"(= {extra_pnl / years / NLV * 100:+.3f}% NLV/yr)")
    print(f"   Worst single added-day incremental contribution: ${worst_added_day:+,.0f}")
    attr_rows.append({
        "variant": var,
        "n_added_days": n_added,
        "cum_extra_pnl_usd": extra_pnl,
        "avg_extra_pnl_per_day_usd": daily_avg,
        "annual_contribution_usd": extra_pnl / years,
        "annual_contribution_pct_nlv": extra_pnl / years / NLV * 100,
        "hit_rate_vs_current": hit,
        "worst_single_added_day_incr_usd": worst_added_day,
    })
pd.DataFrame(attr_rows).to_csv(OUT / "q074_2_added_day_attribution.csv", index=False)

# ── 3. VIX bucket attribution (key for F vs F2) ────────────────────────
print("\n" + "=" * 70)
print("3. VIX bucket attribution within F-added days (<14 vs 14-15)")
print("=" * 70)

df_f = cands["B4_F"]
f_active = df_f["booster_active"] & ~df_f["stress_active"] & ~df_f["second_leg_active"]
added_in_f = f_active & ~cur_active
df_f_added = df_f[added_in_f].copy()
df_f_added["vix_sub"] = pd.cut(df_f_added["vix"],
                                bins=[0, 13, 14, 15, 100],
                                labels=["<13", "13-14", "14-15", "≥15"],
                                include_lowest=True)
cur_pnl_on_added = cands["B4_current"].loc[added_in_f, "total_pnl"]
df_f_added["extra_pnl"] = df_f_added["total_pnl"] - cur_pnl_on_added

bucket_rows = []
print(f"\n{'VIX bucket':<12} {'n':>6} {'cum_extra_$':>14} {'avg_$/day':>12} {'hit%':>7}")
for b in ["<13", "13-14", "14-15", "≥15"]:
    sub = df_f_added[df_f_added["vix_sub"] == b]
    if len(sub) == 0:
        continue
    cum = sub["extra_pnl"].sum()
    avg = cum / len(sub)
    hit = (sub["extra_pnl"] > 0).mean() * 100
    print(f"{b:<12} {len(sub):>6} {cum:>+13,.0f} {avg:>+11,.0f} {hit:>6.1f}%")
    bucket_rows.append({
        "vix_bucket": b,
        "n_days": len(sub),
        "cum_extra_pnl_usd": cum,
        "avg_extra_pnl_per_day_usd": avg,
        "hit_rate_pct": hit,
    })
pd.DataFrame(bucket_rows).to_csv(OUT / "q074_2_vix_bucket_attribution.csv", index=False)

# ── 4. Transition forensic ─────────────────────────────────────────────
print("\n" + "=" * 70)
print("4. Transition forensic (lookback 10d before stress trigger)")
print("=" * 70)

b0 = cands["B0_baseline"]
b0["stress_prev"] = b0["stress_active"].shift(1).fillna(False)
b0["stress_trigger"] = b0["stress_active"] & ~b0["stress_prev"]
trigger_dates = b0.index[b0["stress_trigger"]]
print(f"Total stress trigger events: {len(trigger_dates)}")

def analyze_transitions(cand_name, df_cand, lookback=10):
    rows = []
    for trig in trigger_dates:
        idx = df_cand.index.get_loc(trig)
        if idx < lookback:
            continue
        win = df_cand.iloc[idx - lookback: idx]
        b0_win = b0.iloc[idx - lookback: idx]
        booster_mask = win["booster_active"]
        booster_days = int(booster_mask.sum())
        if booster_mask.any():
            inc = (win.loc[booster_mask, "total_pnl"].sum() - b0_win.loc[booster_mask, "total_pnl"].sum())
        else:
            inc = 0.0
        fwd_end = min(idx + 20, len(df_cand) - 1)
        fwd = df_cand.iloc[idx: fwd_end + 1]
        has_2leg = bool(fwd["second_leg_active"].any())
        severity = "acute" if has_2leg else "mild"
        failed = (booster_days > 0) and (inc < 0)
        rows.append({
            "candidate": cand_name,
            "trigger_date": trig.strftime("%Y-%m-%d"),
            "lookback_days": lookback,
            "booster_active_in_window": booster_days,
            "incremental_pnl_usd": round(inc, 0),
            "incremental_pct_nlv": round(inc / NLV * 100, 3),
            "severity": severity,
            "failed_benign": failed,
        })
    return rows

all_events = []
for var in ["B4_current", "B4_F", "B4_F2"]:
    for row in analyze_transitions(var, cands[var], 10):
        row["window"] = "10d"
        all_events.append(row)
    for row in analyze_transitions(var, cands[var], 20):
        row["window"] = "20d"
        all_events.append(row)
events_df = pd.DataFrame(all_events)
events_df.to_csv(OUT / "q074_2_transition_events.csv", index=False)

# Severity summary
print(f"\n{'Variant':<14} {'mild':>6} {'acute':>7} {'failed_benign':>15} {'cum_inc_$ 10d':>15} {'worst_episode':>15}")
print("-" * 78)
summary_rows = []
for var in ["B4_current", "B4_F", "B4_F2"]:
    sub = events_df[(events_df["candidate"] == var) & (events_df["window"] == "10d")]
    sub_b = sub[sub["booster_active_in_window"] > 0]
    mild = (sub_b["severity"] == "mild").sum()
    acute = (sub_b["severity"] == "acute").sum()
    failed = sub_b["failed_benign"].sum()
    cum = sub_b["incremental_pnl_usd"].sum()
    worst = sub_b["incremental_pnl_usd"].min() if len(sub_b) else 0.0
    print(f"{var:<14} {mild:>6} {acute:>7} {failed:>15} ${cum:>+14,.0f} ${worst:>+14,.0f}")
    summary_rows.append({
        "variant": var,
        "n_transitions_total": int(len(sub)),
        "n_transitions_with_booster": int(len(sub_b)),
        "mild": int(mild),
        "acute": int(acute),
        "failed_benign": int(failed),
        "cum_incremental_pnl_10d_usd": float(cum),
        "worst_single_episode_usd": float(worst),
        "worst_single_episode_pct_nlv": float(worst / NLV * 100),
    })
pd.DataFrame(summary_rows).to_csv(OUT / "q074_2_transition_summary.csv", index=False)

# Crisis breakdown
print("\n" + "=" * 70)
print("Crisis-specific examination (20d lookback)")
print("=" * 70)
crisis_windows = {
    "DotCom_2000_03": ("2000-03-01", "2000-04-30"),
    "PreGFC_2007_07": ("2007-07-01", "2007-09-30"),
    "Vol_2018_02":    ("2018-01-15", "2018-03-15"),
    "COVID_2020_02":  ("2020-02-15", "2020-03-31"),
    "Bear_2022_01":   ("2022-01-01", "2022-02-28"),
}
crisis_rows = []
for cname, (s, e) in crisis_windows.items():
    s_ts, e_ts = pd.Timestamp(s), pd.Timestamp(e)
    trigs = trigger_dates[(trigger_dates >= s_ts) & (trigger_dates <= e_ts)]
    if len(trigs) == 0:
        print(f"[{cname}] no trigger in range")
        continue
    first = trigs[0]
    idx = b0.index.get_loc(first)
    print(f"\n[{cname}] first trigger: {first.strftime('%Y-%m-%d')}")
    for var in ["B4_current", "B4_F", "B4_F2"]:
        df_c = cands[var]
        win = df_c.iloc[max(0, idx - 20): idx]
        b0_win = b0.iloc[max(0, idx - 20): idx]
        m = win["booster_active"]
        if m.any():
            inc = (win.loc[m, "total_pnl"].sum() - b0_win.loc[m, "total_pnl"].sum())
        else:
            inc = 0
        bdays = int(m.sum())
        print(f"   {var:<12} booster_days={bdays}/20d, incremental ${inc:+,.0f}")
        crisis_rows.append({
            "crisis": cname,
            "trigger_date": first.strftime("%Y-%m-%d"),
            "variant": var,
            "booster_days_20d": bdays,
            "incremental_pnl_20d_usd": round(inc, 0),
            "incremental_pct_nlv": round(inc / NLV * 100, 3),
        })
pd.DataFrame(crisis_rows).to_csv(OUT / "q074_2_crisis_breakdown.csv", index=False)

# Top-5 worst episodes per variant
print("\n" + "=" * 70)
print("Top-5 worst booster-window episodes per variant (10d primary)")
print("=" * 70)
top_rows = []
for var in ["B4_current", "B4_F", "B4_F2"]:
    sub = events_df[(events_df["candidate"] == var) & (events_df["window"] == "10d")
                    & (events_df["booster_active_in_window"] > 0)].copy()
    worst5 = sub.nsmallest(5, "incremental_pnl_usd")
    print(f"\n[{var}]")
    for _, r in worst5.iterrows():
        print(f"  {r['trigger_date']}  booster_days={r['booster_active_in_window']}  "
              f"incremental ${r['incremental_pnl_usd']:+,.0f} "
              f"({r['incremental_pct_nlv']:+.3f}% NLV) severity={r['severity']}")
        top_rows.append({**r.to_dict()})
pd.DataFrame(top_rows).to_csv(OUT / "q074_2_top_booster_losses.csv", index=False)

# ── 5. Walk-forward H1 / H2 ────────────────────────────────────────────
print("\n" + "=" * 70)
print("5. Walk-forward H1 (2000-2012) / H2 (2013-2026)")
print("=" * 70)

splits = {
    "H1_2000_2012": ("2000-01-01", "2012-12-31"),
    "H2_2013_2026": ("2013-01-01", "2026-12-31"),
}
wf_rows = []
print(f"\n{'Period':<14} {'Variant':<12} {'ROE %':>7} {'ΔROE vs cur':>12} {'W20d %':>8} {'V2 ok':>6}")
for period, dr in splits.items():
    period_metrics = {}
    for var, fn, cap in variants:
        if var == "B0_baseline":
            continue
        df = build_candidate(var, fn, cap, date_range=dr)
        m = compute_metrics(df, var)
        period_metrics[var] = m
    base = period_metrics["B4_current"]
    for var, m in period_metrics.items():
        d = m["ann_roe_pct"] - base["ann_roe_pct"]
        v2 = "✓" if m["v2_pass_w20d11"] else "✗"
        print(f"{period:<14} {var:<12} {m['ann_roe_pct']:>7.3f} {d:>+11.3f}pp {m['worst_20d_pct']:>8.2f} {v2:>6}")
        wf_rows.append({
            "period": period,
            "variant": var,
            "ann_roe_pct": m["ann_roe_pct"],
            "delta_roe_vs_current_pp": d,
            "max_dd_pct": m["max_dd_pct"],
            "worst_20d_pct": m["worst_20d_pct"],
            "worst_63d_pct": m["worst_63d_pct"],
            "sharpe": m["sharpe"],
            "v2_pass": m["v2_pass_w20d11"],
            "v3_pass": m["v3_pass_w63d17"],
            "booster_pct_of_normal": m["booster_pct_of_normal"],
        })
pd.DataFrame(wf_rows).to_csv(OUT / "q074_2_walkforward.csv", index=False)

# ── 6. Bootstrap (block=250, 20 seeds) on ΔROE ─────────────────────────
print("\n" + "=" * 70)
print("6. Block-bootstrap (block=250, 20 seeds) on ΔROE vs B4_current")
print("=" * 70)

def block_bootstrap_droe(df_var, df_base, n_seeds=20, block=250):
    """Return array of ΔROE samples by block-bootstrapping daily PnL."""
    rng = np.random.default_rng(42)
    n = len(df_var)
    n_blocks = n // block
    deltas = []
    for s in range(n_seeds):
        seeds_rng = np.random.default_rng(42 + s)
        starts = seeds_rng.integers(0, n - block, size=n_blocks)
        var_pnl = np.concatenate([df_var["total_pnl"].values[i:i+block] for i in starts])
        base_pnl = np.concatenate([df_base["total_pnl"].values[i:i+block] for i in starts])
        years = len(var_pnl) / 252
        eq_var = NLV + var_pnl.cumsum()
        eq_base = NLV + base_pnl.cumsum()
        roe_var = (eq_var[-1] / NLV) ** (1.0/years) - 1
        roe_base = (eq_base[-1] / NLV) ** (1.0/years) - 1
        deltas.append((roe_var - roe_base) * 100)
    return np.array(deltas)

boot_rows = []
for var in ["B4_F", "B4_F2"]:
    deltas = block_bootstrap_droe(cands[var], cands["B4_current"])
    print(f"\n{var} vs B4_current:")
    print(f"  ΔROE mean {deltas.mean():+.3f}pp, σ {deltas.std():.3f}pp, "
          f"5th-95th [{np.percentile(deltas, 5):+.3f}, {np.percentile(deltas, 95):+.3f}]")
    pos = (deltas > 0).mean() * 100
    print(f"  P(ΔROE > 0) = {pos:.1f}%")
    boot_rows.append({
        "variant": var,
        "delta_roe_mean_pp": float(deltas.mean()),
        "delta_roe_std_pp": float(deltas.std()),
        "p5_pp": float(np.percentile(deltas, 5)),
        "p95_pp": float(np.percentile(deltas, 95)),
        "p_droe_positive_pct": float(pos),
        "n_seeds": 20,
        "block": 250,
    })
pd.DataFrame(boot_rows).to_csv(OUT / "q074_2_bootstrap.csv", index=False)

# ── 7. Done ────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("Q074.2 complete. Outputs in research/q074/q074_2_*.csv")
print("=" * 70)
