"""Q074 P2 — Booster Candidate Sweep (B0 / B1 / B2 / B3 / B4).

Per G2 review PASS and P0 frozen constraints:
  - B1-B4 candidate definitions FROZEN (no modifications from P1)
  - State-dependent SPX allocation policy (not linear scaling)
  - Incremental booster PnL = candidate - Arch-3 baseline
  - Q042 stays at 17.5% target per SPEC-104; cash absorbs residual (can be negative ≡ margin)
  - HV stays at 0% per SPEC-104

Policy:
  if second_leg_active:    spx_alloc = 0.40
  elif stress_active:      spx_alloc = 0.50
  elif benign_active:      spx_alloc = booster_cap (0.85 or 0.90)
  else:                    spx_alloc = 0.80

Outputs:
  q074_p2_candidate_results.csv (per-candidate Net ROE / MaxDD / W20d / etc.)
  q074_p2_incremental_summary.md (vs Arch-3 baseline B0)
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

# Friction (same as Q073 P4)
FRICTION_ANN_SPX  = 0.0035
FRICTION_ANN_HV   = 0.0010
FRICTION_ANN_Q42  = 0.0005
FRICTION_ANN_CASH = 0.0
CASH_YIELD = 0.043

# P1.3R baseline allocations (for scaling)
P13R_SPX = 0.60
P13R_HV  = 0.05
P13R_Q42 = 0.10
P13R_CASH = 0.25

# Arch-3 (SPEC-104) production target allocations
HV_ALLOC = 0.0      # demoted per SPEC-104
Q42_ALLOC = 0.175   # target cap per SPEC-104

# State-dependent SPX caps (locked Arch-3 Layer-1)
STRESS_SPX_CAP = 0.50
SECOND_LEG_CAP = 0.40

print("Q074 P2 — Booster Sweep (Arch-3 + state-dependent SPX cap)", flush=True)
print("=" * 70)
print(f"\nLocked Layer-1: stress={STRESS_SPX_CAP*100:.0f}% / 2nd-leg={SECOND_LEG_CAP*100:.0f}% / HV={HV_ALLOC*100:.0f}% / Q42={Q42_ALLOC*100:.1f}%")

# ── Load data ──────────────────────────────────────────────────────────
combined = pd.read_csv(REPO / "research" / "q073" / "q073_p1_3R_unified_daily_pnl.csv",
                       parse_dates=["date"], index_col="date")
print(f"Loaded {len(combined)} days of P1.3R daily PnL")

from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history
vix_df = fetch_vix_history(period="max")
spx_df = fetch_spx_history(period="max")
vix_df.index = pd.to_datetime(vix_df.index.date)
spx_df.index = pd.to_datetime(spx_df.index.date)
mkt = pd.DataFrame({"vix": vix_df["vix"], "spx_close": spx_df["close"]}).dropna()
mkt = mkt[(mkt.index >= combined.index.min()) & (mkt.index <= combined.index.max())]

# Features
mkt["ma50"] = mkt["spx_close"].rolling(50).mean()
mkt["above_ma50"] = (mkt["spx_close"] > mkt["ma50"]).astype(int)
mkt["ma50_slope_5d"] = mkt["ma50"] - mkt["ma50"].shift(5)
mkt["ma50_slope_pos"] = (mkt["ma50_slope_5d"] > 0).astype(int)
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

# Stress/2nd-leg flags
mkt["high_20d"] = mkt["spx_close"].rolling(20, min_periods=5).max()
mkt["dd_20d"] = mkt["spx_close"] / mkt["high_20d"] - 1.0
mkt["high_60d"] = mkt["spx_close"].rolling(60, min_periods=10).max()
mkt["dd_60d"] = mkt["spx_close"] / mkt["high_60d"] - 1.0
flag = ((mkt["vix"] >= 22.0) | (mkt["dd_20d"] <= -0.04) | (mkt["dd_60d"] <= -0.04))
mkt["stress_active"] = flag.rolling(3, min_periods=1).max().astype(bool)
mkt["second_leg_active"] = ((mkt["dd_60d"] <= -0.08) & (mkt["vix"] >= 25.0)).astype(bool)

# ── Booster signal functions (FROZEN per P0) ──────────────────────────
def b1_strict_signal(row):
    return (
        not row["stress_active"]
        and not row["second_leg_active"]
        and row["above_ma50"] == 1
        and row["ma50_slope_pos"] == 1
        and row["ddath"] > -0.03
        and row["vix"] < 20
        and row["vix_5d_change"] <= 1.0
        and row["ivp_252"] < 55
    )

def b2_moderate_signal(row):
    return (
        not row["stress_active"]
        and not row["second_leg_active"]
        and row["above_ma50"] == 1
        and row["ddath"] > -0.04
        and row["vix"] < 22
        and row["vix_5d_change"] <= 1.5
        and row["ivp_252"] < 55
    )

# ── Simulator ──────────────────────────────────────────────────────────
def simulate(name, booster_signal_fn, booster_cap, apply_friction=True):
    df = combined.copy().join(mkt[["above_ma50", "ma50_slope_pos", "ddath", "vix",
                                    "vix_5d_change", "ivp_252",
                                    "stress_active", "second_leg_active"]],
                              how="left").ffill()

    # Determine booster active (NaN for early dates with missing features)
    df["booster_active"] = False
    valid = df["ivp_252"].notna() & df["above_ma50"].notna()
    if booster_signal_fn is not None:
        # Vectorize a bit — apply row-wise
        df.loc[valid, "booster_active"] = df.loc[valid].apply(booster_signal_fn, axis=1)
    df["booster_active"] = df["booster_active"].astype(bool)

    # State-dependent SPX allocation
    spx_alloc = pd.Series(0.80, index=df.index)  # normal base
    spx_alloc[df["stress_active"]] = STRESS_SPX_CAP
    spx_alloc[df["second_leg_active"]] = SECOND_LEG_CAP
    # Booster overrides normal but NOT stress/2nd-leg (Layer 1 priority)
    booster_eligible = df["booster_active"] & ~df["stress_active"] & ~df["second_leg_active"]
    if booster_cap is not None:
        spx_alloc[booster_eligible] = booster_cap
    df["spx_alloc"] = spx_alloc

    # Cash allocation (can be negative if booster + Q42 exceed 100% - HV)
    df["cash_alloc"] = 1.0 - df["spx_alloc"] - HV_ALLOC - Q42_ALLOC
    # Note: cash_alloc may be negative when booster active (effective margin loan)

    # Scale PnL
    spx_pnl = df["spx_pnl"] * (df["spx_alloc"] / P13R_SPX)
    q42_pnl = df["q42a_pnl"] * (Q42_ALLOC / P13R_Q42)
    # Cash PnL: signed (positive when cash credit, negative when margin)
    cash_pnl = df["cash_alloc"] * NLV * CASH_YIELD / 252.0  # daily $ value
    # NOTE: cash_alloc * NLV * CASH_YIELD / 252 is constant daily rate × allocation

    if apply_friction:
        spx_drag = FRICTION_ANN_SPX * NLV * (df["spx_alloc"] / P13R_SPX) / 252.0
        q42_drag = FRICTION_ANN_Q42 * NLV * (Q42_ALLOC / P13R_Q42) / 252.0
        spx_pnl = spx_pnl - spx_drag
        q42_pnl = q42_pnl - q42_drag

    df["total_pnl"] = spx_pnl + q42_pnl + cash_pnl
    df["cum_pnl"] = df["total_pnl"].cumsum()
    df["equity"] = NLV + df["cum_pnl"]
    df["equity_start"] = df["equity"].shift(1).fillna(NLV)
    df["daily_ret"] = df["total_pnl"] / df["equity_start"]

    # Metrics
    years = len(df) / 252
    final_eq = df["equity"].iloc[-1]
    ann_roe = (final_eq / NLV) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    running_max = df["equity"].cummax()
    drawdown = (df["equity"] - running_max) / running_max
    max_dd = drawdown.min()
    worst_20d = df["daily_ret"].rolling(20).sum().min()
    worst_63d = df["daily_ret"].rolling(63).sum().min()
    sharpe = df["daily_ret"].mean() / df["daily_ret"].std() * (252**0.5) if df["daily_ret"].std() > 0 else 0.0
    booster_days = int(booster_eligible.sum())
    booster_pct = booster_days / len(df) * 100

    return {
        "name": name,
        "booster_cap": booster_cap if booster_cap else 0.80,
        "ann_roe": ann_roe,
        "max_dd": max_dd,
        "worst_20d": worst_20d,
        "worst_63d": worst_63d,
        "sharpe": sharpe,
        "v1_pass": max_dd >= -0.28,
        "v2_pass": worst_20d >= -0.11,
        "v3_pass": worst_63d >= -0.17,
        "all_vetoes_pass": (max_dd >= -0.28) and (worst_20d >= -0.11) and (worst_63d >= -0.17),
        "floor_8_pass": ann_roe >= 0.08,
        "booster_active_days": booster_days,
        "booster_active_pct": booster_pct,
        "final_eq": final_eq,
        "daily_pnl": df["total_pnl"].copy(),  # for incremental calc
        "booster_eligible_mask": booster_eligible.copy(),
    }

# ── Run all candidates ────────────────────────────────────────────────
print("\nRunning candidates...\n")

candidates = [
    ("B0_baseline_arch3", None, None),
    ("B1_strict_85",      b1_strict_signal, 0.85),
    ("B2_moderate_85",    b2_moderate_signal, 0.85),
    ("B3_strict_90",      b1_strict_signal, 0.90),
    ("B4_moderate_90",    b2_moderate_signal, 0.90),
]

results = {}
for name, signal_fn, cap in candidates:
    r = simulate(name, signal_fn, cap)
    results[name] = r
    print(f"[{name:<20}] cap={r['booster_cap']*100:.0f}% / booster active {r['booster_active_days']} days ({r['booster_active_pct']:.1f}%)")
    print(f"   Net ROE {r['ann_roe']*100:.2f}%   MaxDD {r['max_dd']*100:.2f}%   W20d {r['worst_20d']*100:.2f}%   W63d {r['worst_63d']*100:.2f}%   Sharpe {r['sharpe']:.2f}")
    print(f"   V1={'✓' if r['v1_pass'] else '✗'} V2={'✓' if r['v2_pass'] else '✗'} V3={'✓' if r['v3_pass'] else '✗'}   "
          f"Floor 8%: {'✓' if r['floor_8_pass'] else '✗'}")

# ── Incremental analysis (candidate - B0) ──────────────────────────────
print("\n" + "=" * 70)
print("Incremental booster PnL vs Arch-3 baseline (B0)")
print("=" * 70)

baseline = results["B0_baseline_arch3"]
b0_daily = baseline["daily_pnl"]

print(f"\n{'Candidate':<20} {'Cumul incr $':>15} {'Ann incr %NLV':>14} {'Δ Net ROE pp':>14} {'Δ Worst 20d pp':>15}")
print("-" * 78)

inc_rows = []
for name in ["B1_strict_85", "B2_moderate_85", "B3_strict_90", "B4_moderate_90"]:
    r = results[name]
    incremental_daily = r["daily_pnl"] - b0_daily
    cum_inc = incremental_daily.sum()
    years = len(incremental_daily) / 252
    ann_inc_pct = cum_inc / years / NLV * 100
    delta_roe = (r["ann_roe"] - baseline["ann_roe"]) * 100
    delta_w20d = (r["worst_20d"] - baseline["worst_20d"]) * 100
    print(f"{name:<20} ${cum_inc:>13,.0f} {ann_inc_pct:>13.3f}% {delta_roe:>+13.3f}pp {delta_w20d:>+14.3f}pp")
    inc_rows.append({
        "candidate": name,
        "booster_cap": r["booster_cap"] * 100,
        "booster_active_days": r["booster_active_days"],
        "booster_active_pct": r["booster_active_pct"],
        "cumulative_incremental_usd": cum_inc,
        "ann_incremental_pct_nlv": ann_inc_pct,
        "delta_net_roe_pp": delta_roe,
        "delta_worst_20d_pp": delta_w20d,
        "delta_worst_63d_pp": (r["worst_63d"] - baseline["worst_63d"]) * 100,
        "delta_max_dd_pp": (r["max_dd"] - baseline["max_dd"]) * 100,
        "delta_sharpe": r["sharpe"] - baseline["sharpe"],
    })

# Save consolidated CSV
all_rows = []
for name, r in results.items():
    all_rows.append({
        "candidate": name,
        "booster_cap_pct": r["booster_cap"] * 100,
        "booster_active_days": r["booster_active_days"],
        "booster_active_pct": r["booster_active_pct"],
        "net_ann_roe_pct": r["ann_roe"] * 100,
        "max_dd_pct": r["max_dd"] * 100,
        "worst_20d_pct": r["worst_20d"] * 100,
        "worst_63d_pct": r["worst_63d"] * 100,
        "sharpe": r["sharpe"],
        "v1_pass": r["v1_pass"],
        "v2_pass": r["v2_pass"],
        "v3_pass": r["v3_pass"],
        "all_vetoes_pass": r["all_vetoes_pass"],
        "floor_8_pass": r["floor_8_pass"],
        "final_equity_M": r["final_eq"] / 1e6,
    })
pd.DataFrame(all_rows).to_csv(OUT / "q074_p2_candidate_results.csv", index=False)
pd.DataFrame(inc_rows).to_csv(OUT / "q074_p2_incremental_summary.csv", index=False)

# ── Verdict + flag for P3 ────────────────────────────────────────────
print("\n" + "=" * 70)
print("Verdict")
print("=" * 70)

# Strong / Soft / Fail per success criteria
arch3_worst_20d = baseline["worst_20d"] * 100  # -7.04% expected
print(f"\nArch-3 baseline (B0): Net ROE {baseline['ann_roe']*100:.2f}%, Worst 20d {arch3_worst_20d:.2f}%")
print(f"Floor 8% threshold; V2 worst-20d ≤ -11%; Strong-pass relative threshold ≤ {arch3_worst_20d - 0.5:.2f}%")

print(f"\nP2 candidates classification:")
for inc in inc_rows:
    name = inc["candidate"]
    r = results[name]
    abs_v2 = r["v2_pass"]
    rel_w20d_pp = inc["delta_worst_20d_pp"]
    rel_pass = rel_w20d_pp >= -0.5  # not worse by more than 0.5pp
    roe_pp = inc["delta_net_roe_pp"]
    floor_pass = r["floor_8_pass"]

    if abs_v2 and rel_pass and roe_pp >= 0.30 and floor_pass:
        verdict = "STRONG PASS candidate"
    elif abs_v2 and roe_pp >= 0.10:
        verdict = "Soft pass (paper/shadow only)"
    elif not abs_v2:
        verdict = "FAIL V2"
    elif not floor_pass and roe_pp < 0.10:
        verdict = "FAIL — does not reach floor 8% or marginal ROE"
    else:
        verdict = "FAIL — does not meet criteria"
    print(f"  {name:<20} ΔROE {roe_pp:+.2f}pp / ΔW20d {rel_w20d_pp:+.2f}pp / Floor 8% {'✓' if floor_pass else '✗'} / V2 {'✓' if abs_v2 else '✗'} → {verdict}")

print(f"\nP3 transition-risk forensic should focus on:")
for name in ["B2_moderate_85", "B4_moderate_90"]:
    if not results[name]["v2_pass"]:
        print(f"  - {name} (V2 FAIL) — likely VIX 20-22 inclusion driving transition losses")
print(f"  - B1/B3 strict candidates should be compared for transition-risk symmetry")
print(f"  - Mild / acute / failed-benign classification per P0 §5 P3")

print(f"\nOutput: {OUT / 'q074_p2_candidate_results.csv'}")
print(f"        {OUT / 'q074_p2_incremental_summary.csv'}")
