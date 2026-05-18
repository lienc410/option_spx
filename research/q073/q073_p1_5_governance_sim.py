"""Q073 P1.5 — Governance-aware Combined Simulator.

Two-part:

  P1.5a: Apply ACTUAL SPEC-103 R1-R6 governance as written.
    - Normal SPX cap = 70%   (R1)
    - Stress SPX cap = 60%   (R5 trigger reduces 70% → 60%)
    - Second-leg block = freeze new SPX BPS entries (effective ~50%)
    - Stress trigger from stress_episode_from_flags()
    - Second-leg from detect_second_leg_state()

  P1.5b: Enhanced stress cap sensitivity.
    - Test stress SPX cap = 60 / 55 / 50 / 45 / 40
    - For each: ROE, MaxDD, worst-20d, V2 pass/fail
    - Goal: which stress cap delivers V2 PASS + ROE ≥ 8%?

Approach: P1.3R produced SPX PnL stream sized to 60% allocation. We rescale
externally by allocation_t / 60% to model dynamic allocation under governance.

Outputs:
  q073_p1_5a_actual_governance.md
  q073_p1_5b_stress_cap_sweep.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

OUT = REPO / "research" / "q073"
NLV = 894_000.0

print("Q073 P1.5 — Governance-aware Combined Simulator", flush=True)
print("=" * 70, flush=True)

# ── Load P1.3R daily PnL series ─────────────────────────────────────────
combined = pd.read_csv(OUT / "q073_p1_3R_unified_daily_pnl.csv",
                       parse_dates=["date"], index_col="date")
print(f"\nLoaded P1.3R daily series: {len(combined)} days", flush=True)

# ── Load VIX / SPX history for stress detection ─────────────────────────
print("Loading VIX + SPX history for governance triggers...", flush=True)
from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history
vix_df = fetch_vix_history(period="max")
spx_df = fetch_spx_history(period="max")
vix_df.index = pd.to_datetime(vix_df.index.date)
spx_df.index = pd.to_datetime(spx_df.index.date)

# Build daily frame with VIX + SPX close
mkt = pd.DataFrame({
    "vix": vix_df["vix"],
    "spx_close": spx_df["close"],
})
mkt = mkt.dropna()
mkt = mkt[(mkt.index >= combined.index.min()) & (mkt.index <= combined.index.max())]
print(f"Market frame: {len(mkt)} days {mkt.index.min().date()} → {mkt.index.max().date()}", flush=True)

# Rolling drawdowns
mkt["high_20d"] = mkt["spx_close"].rolling(20, min_periods=5).max()
mkt["dd_20d"] = mkt["spx_close"] / mkt["high_20d"] - 1.0
mkt["high_60d"] = mkt["spx_close"].rolling(60, min_periods=10).max()
mkt["dd_60d"] = mkt["spx_close"] / mkt["high_60d"] - 1.0

# Stress trigger (per stress_episode_from_flags)
flag = (
    (mkt["vix"] >= 22.0)
    | (mkt["dd_20d"] <= -0.04)
    | (mkt["dd_60d"] <= -0.04)
)
mkt["stress_active"] = flag.rolling(3, min_periods=1).max().astype(bool)

# Second-leg state (per detect_second_leg_state, simplified)
mkt["second_leg_active"] = ((mkt["dd_60d"] <= -0.08) & (mkt["vix"] >= 25.0)).astype(bool)

print(f"\n[stress trigger frequency]")
print(f"  Stress active days:     {mkt['stress_active'].sum()} ({mkt['stress_active'].mean()*100:.1f}%)")
print(f"  Second-leg active days: {mkt['second_leg_active'].sum()} ({mkt['second_leg_active'].mean()*100:.1f}%)")

# ──────────────────────────────────────────────────────────────────────
# Helper to compute portfolio metrics for given SPX allocation policy
# ──────────────────────────────────────────────────────────────────────
def simulate_with_policy(spx_alloc_series: pd.Series, label: str) -> dict:
    """
    spx_alloc_series: per-day SPX allocation %. Scales P1.3R SPX PnL externally.
    Other strategies unchanged (HV 5%, Q42A 10%, Cash variable based on residual).
    """
    df = combined.copy().join(mkt[["vix", "dd_20d", "dd_60d", "stress_active", "second_leg_active"]], how="left").ffill()
    df["spx_alloc"] = spx_alloc_series.reindex(df.index).ffill().fillna(0.60)
    # Scale SPX PnL externally: P1.3R ran at 60% allocation → scale by alloc/0.60
    df["spx_pnl_scaled"] = df["spx_pnl"] * (df["spx_alloc"] / 0.60)
    # Cash residual = 1 - spx_alloc - HV(0.05) - Q42A(0.10)
    df["cash_alloc"] = 1.0 - df["spx_alloc"] - 0.05 - 0.10
    df["cash_alloc"] = df["cash_alloc"].clip(lower=0)
    # Cash PnL scales linearly with cash allocation; original was 25% → adjust
    df["cash_pnl_scaled"] = df["cash_pnl"] * (df["cash_alloc"] / 0.25)
    df["total_pnl_scaled"] = df["spx_pnl_scaled"] + df["hv_pnl"] + df["q42a_pnl"] + df["cash_pnl_scaled"]
    df["cum_pnl"] = df["total_pnl_scaled"].cumsum()
    df["equity"] = NLV + df["cum_pnl"]
    df["equity_start"] = df["equity"].shift(1).fillna(NLV)
    df["daily_ret"] = df["total_pnl_scaled"] / df["equity_start"]

    years = len(df) / 252
    final_eq = df["equity"].iloc[-1]
    ann_roe_geo = (final_eq / NLV) ** (1.0 / years) - 1.0 if years > 0 else 0.0

    running_max = df["equity"].cummax()
    drawdown = (df["equity"] - running_max) / running_max
    max_dd = drawdown.min()

    roll_20d_ret = df["daily_ret"].rolling(20).sum()
    roll_63d_ret = df["daily_ret"].rolling(63).sum()
    worst_20d = roll_20d_ret.min()
    worst_63d = roll_63d_ret.min()
    worst_20d_end = roll_20d_ret.idxmin()
    worst_63d_end = roll_63d_ret.idxmin()

    sharpe = df["daily_ret"].mean() / df["daily_ret"].std() * (252**0.5) if df["daily_ret"].std() > 0 else 0.0

    return {
        "label": label,
        "ann_roe_geo": ann_roe_geo,
        "max_dd": max_dd,
        "worst_20d": worst_20d,
        "worst_63d": worst_63d,
        "worst_20d_end": worst_20d_end,
        "sharpe": sharpe,
        "v1_pass": max_dd >= -0.28,
        "v2_pass": worst_20d >= -0.11,
        "v3_pass": worst_63d >= -0.17,
        "final_eq": final_eq,
        "df": df,
    }

# ──────────────────────────────────────────────────────────────────────
# P1.5a — Actual R1-R6 governance
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P1.5a — Actual SPEC-103 R1-R6 governance")
print("=" * 70)
# Normal: 70%, Stress: 60%, Second-leg: 50% (block new ~= half size)
spx_alloc = pd.Series(0.70, index=combined.index)  # default normal
spx_alloc[mkt["stress_active"]] = 0.60             # R5 stress
spx_alloc[mkt["second_leg_active"]] = 0.50         # R6 block (effective half-size)

r156a = simulate_with_policy(spx_alloc, "P1.5a actual R1-R6")
print(f"\n  Ann ROE (geo):    {r156a['ann_roe_geo']*100:.2f}%")
print(f"  MaxDD:            {r156a['max_dd']*100:.2f}%   V1 {'PASS' if r156a['v1_pass'] else 'FAIL'}")
print(f"  Worst 20d:        {r156a['worst_20d']*100:.2f}%   V2 {'PASS' if r156a['v2_pass'] else 'FAIL'}  (window end {r156a['worst_20d_end'].date()})")
print(f"  Worst 63d:        {r156a['worst_63d']*100:.2f}%   V3 {'PASS' if r156a['v3_pass'] else 'FAIL'}")
print(f"  Sharpe:           {r156a['sharpe']:.2f}")
print(f"  Final equity:     ${r156a['final_eq']:,.0f}")

# R6 trigger dates around DotCom
print(f"\n[R6 second-leg trigger dates 2000-2002]")
r6_2000 = mkt[(mkt.index >= "2000-01-01") & (mkt.index <= "2002-12-31") & mkt["second_leg_active"]]
print(f"  R6 active days in 2000-2002: {len(r6_2000)}")
if len(r6_2000) > 0:
    print(f"  First R6 trigger: {r6_2000.index.min().date()}")
    print(f"  Last R6 trigger:  {r6_2000.index.max().date()}")
print(f"  V2 worst-20d window: ended {r156a['worst_20d_end'].date()}")
print(f"  → R6 {'triggered BEFORE' if (len(r6_2000) > 0 and r6_2000.index.min() < r156a['worst_20d_end']) else 'did NOT trigger before'} V2 breach")

# ──────────────────────────────────────────────────────────────────────
# P1.5b — Enhanced stress cap sensitivity
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P1.5b — Enhanced stress SPX cap sensitivity")
print("=" * 70)
print("\nNormal cap fixed at 70%. Stress cap varied. Second-leg = stress_cap - 10%.\n")

sweep_results = []
for stress_cap in [0.60, 0.55, 0.50, 0.45, 0.40]:
    second_leg_cap = max(stress_cap - 0.10, 0.30)
    alloc = pd.Series(0.70, index=combined.index)
    alloc[mkt["stress_active"]] = stress_cap
    alloc[mkt["second_leg_active"]] = second_leg_cap
    r = simulate_with_policy(alloc, f"stress={stress_cap*100:.0f}%/2nd={second_leg_cap*100:.0f}%")
    sweep_results.append({
        "stress_cap_pct": int(stress_cap*100),
        "second_leg_cap_pct": int(second_leg_cap*100),
        "ann_roe_pct": round(r["ann_roe_geo"]*100, 2),
        "max_dd_pct": round(r["max_dd"]*100, 2),
        "worst_20d_pct": round(r["worst_20d"]*100, 2),
        "worst_63d_pct": round(r["worst_63d"]*100, 2),
        "sharpe": round(r["sharpe"], 2),
        "v1_pass": r["v1_pass"],
        "v2_pass": r["v2_pass"],
        "v3_pass": r["v3_pass"],
        "all_vetoes_pass": r["v1_pass"] and r["v2_pass"] and r["v3_pass"],
        "roe_meets_floor": r["ann_roe_geo"] >= 0.08,
    })

sweep_df = pd.DataFrame(sweep_results)
sweep_df.to_csv(OUT / "q073_p1_5b_stress_cap_sweep.csv", index=False)
print(sweep_df.to_string(index=False))

print("\n" + "=" * 70)
print("Summary — find architecture passing ALL vetoes AND floor 8%")
print("=" * 70)
winners = sweep_df[sweep_df["all_vetoes_pass"] & sweep_df["roe_meets_floor"]]
if len(winners) > 0:
    print("\nQUALIFYING ARCHITECTURES:")
    print(winners[["stress_cap_pct", "second_leg_cap_pct", "ann_roe_pct",
                    "worst_20d_pct", "max_dd_pct"]].to_string(index=False))
else:
    print("\nNO single-lever stress-cap reduction satisfies BOTH V1-V3 vetoes AND floor 8%.")
    print("Best ROE under V2 PASS:")
    v2_pass_only = sweep_df[sweep_df["v2_pass"]]
    if len(v2_pass_only):
        print(v2_pass_only[["stress_cap_pct", "ann_roe_pct", "worst_20d_pct"]].to_string(index=False))
    print("\nBest ROE under floor 8%:")
    floor_only = sweep_df[sweep_df["roe_meets_floor"]]
    if len(floor_only):
        print(floor_only[["stress_cap_pct", "ann_roe_pct", "worst_20d_pct"]].to_string(index=False))

print("\nDone.", flush=True)
