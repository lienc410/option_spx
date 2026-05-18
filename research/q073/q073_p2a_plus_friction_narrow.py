"""Q073 P2A+ — Friction-adjusted narrow allocation sweep.

PM decision 2026-05-17: gross 7.92% candidate E gap to floor 8% is 0.08pp,
but this is PRE-FRICTION. Real ROE after friction is 0.3-0.6pp lower.
Need narrow P2A+ that:
  - Locks HV Ladder at 5% (proven V2 driver if increased)
  - Locks stress cap 50% / 2nd-leg 40% (V2-pass anchor)
  - Tests Q042 Sleeve A sizing 12.5 / 15 / 17.5 / 20
  - Tests Normal SPX cap 75 / 77.5 / 80
  - Reports both GROSS and NET-of-friction ROE

Friction model (conservative, applied as PnL haircut per strategy):
  SPX BPS:    -10% PnL haircut (slippage 20-40 bps × 4 legs + commissions)
  HV Ladder:  -10% (per Rule, live=0 → conservative paper-friction proxy)
  Q042:       -10% (similar 2-leg call spread structure)
  Cash BOXX:  0% (4.3% already net of 0.19% expense)

Output:
  q073_p2a_plus_friction_results.csv
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

# Locked anchors (V2-pass)
STRESS_SPX_CAP = 0.50
SECOND_LEG_CAP = 0.40
HV_ALLOC = 0.05  # locked per P2A finding

# Friction model (per P1.4 estimate: 0.3-0.6pp combined annual drag)
# Implemented as constant daily $ drag (= annual_friction_pct × NLV × allocation_factor / 252)
# This represents per-trade slippage + commission averaged across the year.
FRICTION_ANN_SPX  = 0.0035  # 0.35% NLV/yr at full SPX allocation (BPS 4-leg slippage + commission × ~14 trades/yr)
FRICTION_ANN_HV   = 0.0010  # 0.10% at 5% baseline (146 trades / 26y ≈ 5.6/yr, /ES naked put 2-leg)
FRICTION_ANN_Q42  = 0.0005  # 0.05% at 10% baseline (~2 trades/yr, simple 2-leg call spread)
FRICTION_ANN_CASH = 0.0     # already net of BOXX 0.19% expense in 4.3% baseline

# P1.3R baseline allocations (for scaling)
P13R_SPX  = 0.60
P13R_HV   = 0.05
P13R_Q42  = 0.10
P13R_CASH = 0.25

print("Q073 P2A+ — Friction-adjusted Narrow Sweep", flush=True)
print("=" * 70)
print(f"\nLocked:  Stress SPX {STRESS_SPX_CAP*100:.0f}% / 2nd-leg {SECOND_LEG_CAP*100:.0f}% / HV {HV_ALLOC*100:.0f}%")
print(f"Friction: SPX {FRICTION_ANN_SPX*100:.2f}%/yr / HV {FRICTION_ANN_HV*100:.2f}%/yr / Q42 {FRICTION_ANN_Q42*100:.2f}%/yr / Cash {FRICTION_ANN_CASH*100:.2f}%/yr (constant daily drag)")

# ── Load data ──────────────────────────────────────────────────────────
combined = pd.read_csv(OUT / "q073_p1_3R_unified_daily_pnl.csv",
                       parse_dates=["date"], index_col="date")

from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history
vix_df = fetch_vix_history(period="max")
spx_df = fetch_spx_history(period="max")
vix_df.index = pd.to_datetime(vix_df.index.date)
spx_df.index = pd.to_datetime(spx_df.index.date)
mkt = pd.DataFrame({"vix": vix_df["vix"], "spx_close": spx_df["close"]}).dropna()
mkt = mkt[(mkt.index >= combined.index.min()) & (mkt.index <= combined.index.max())]
mkt["high_20d"] = mkt["spx_close"].rolling(20, min_periods=5).max()
mkt["dd_20d"] = mkt["spx_close"] / mkt["high_20d"] - 1.0
mkt["high_60d"] = mkt["spx_close"].rolling(60, min_periods=10).max()
mkt["dd_60d"] = mkt["spx_close"] / mkt["high_60d"] - 1.0
flag = ((mkt["vix"] >= 22.0) | (mkt["dd_20d"] <= -0.04) | (mkt["dd_60d"] <= -0.04))
mkt["stress_active"] = flag.rolling(3, min_periods=1).max().astype(bool)
mkt["second_leg_active"] = ((mkt["dd_60d"] <= -0.08) & (mkt["vix"] >= 25.0)).astype(bool)


def simulate(name, normal_spx, q42a_alloc, friction_on):
    cash_normal = 1.0 - normal_spx - HV_ALLOC - q42a_alloc
    if cash_normal < 0:
        return None
    df = combined.copy().join(mkt[["stress_active", "second_leg_active"]], how="left").ffill()
    spx_alloc = pd.Series(normal_spx, index=df.index)
    spx_alloc[df["stress_active"].astype(bool)] = STRESS_SPX_CAP
    spx_alloc[df["second_leg_active"].astype(bool)] = SECOND_LEG_CAP
    df["spx_alloc"] = spx_alloc
    df["cash_alloc"] = (1.0 - df["spx_alloc"] - HV_ALLOC - q42a_alloc).clip(lower=0)

    # Scale (gross)
    spx_pnl_scaled = df["spx_pnl"] * (df["spx_alloc"] / P13R_SPX)
    hv_pnl_scaled  = df["hv_pnl"]  * (HV_ALLOC / P13R_HV)
    q42_pnl_scaled = df["q42a_pnl"] * (q42a_alloc / P13R_Q42)
    cash_pnl_scaled = df["cash_pnl"] * (df["cash_alloc"] / P13R_CASH)

    # Apply friction as constant daily $ drag (always negative)
    # Daily drag = annual_friction × NLV × (current_alloc / baseline_alloc) / 252
    if friction_on:
        spx_drag  = FRICTION_ANN_SPX  * NLV * (df["spx_alloc"] / P13R_SPX) / 252.0
        hv_drag   = FRICTION_ANN_HV   * NLV * (HV_ALLOC / P13R_HV) / 252.0
        q42_drag  = FRICTION_ANN_Q42  * NLV * (q42a_alloc / P13R_Q42) / 252.0
        cash_drag = FRICTION_ANN_CASH * NLV * (df["cash_alloc"] / P13R_CASH) / 252.0
        spx_pnl_scaled  = spx_pnl_scaled  - spx_drag
        hv_pnl_scaled   = hv_pnl_scaled   - hv_drag
        q42_pnl_scaled  = q42_pnl_scaled  - q42_drag
        cash_pnl_scaled = cash_pnl_scaled - cash_drag

    df["total_pnl"] = spx_pnl_scaled + hv_pnl_scaled + q42_pnl_scaled + cash_pnl_scaled
    df["cum_pnl"] = df["total_pnl"].cumsum()
    df["equity"] = NLV + df["cum_pnl"]
    df["equity_start"] = df["equity"].shift(1).fillna(NLV)
    df["daily_ret"] = df["total_pnl"] / df["equity_start"]

    years = len(df) / 252
    final_eq = df["equity"].iloc[-1]
    ann_roe = (final_eq / NLV) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    running_max = df["equity"].cummax()
    drawdown = (df["equity"] - running_max) / running_max
    max_dd = drawdown.min()
    roll_20d = df["daily_ret"].rolling(20).sum()
    roll_63d = df["daily_ret"].rolling(63).sum()
    worst_20d = roll_20d.min()
    worst_63d = roll_63d.min()
    sharpe = df["daily_ret"].mean() / df["daily_ret"].std() * (252**0.5) if df["daily_ret"].std() > 0 else 0.0
    return {
        "ann_roe": ann_roe, "max_dd": max_dd,
        "worst_20d": worst_20d, "worst_63d": worst_63d,
        "sharpe": sharpe, "final_eq": final_eq,
        "v1_pass": max_dd >= -0.28,
        "v2_pass": worst_20d >= -0.11,
        "v3_pass": worst_63d >= -0.17,
    }


candidates = [
    ("E0_anchor",     0.75, 0.125),  # baseline best V2-pass
    ("E1_q42_15",     0.75, 0.15),
    ("E2_q42_175",    0.75, 0.175),
    ("E3_spx775",     0.775, 0.125),
    ("E4_spx775_q15", 0.775, 0.15),
    ("E5_spx80",      0.80, 0.125),
    ("E6_spx80_q15",  0.80, 0.15),
    ("E7_spx80_q175", 0.80, 0.175),
    ("E8_q42_20",     0.75, 0.20),
]

print(f"\nCandidates (HV fixed 5%, stress/2nd-leg locked):")
print(f"{'Name':<18} {'SPX':>5} {'HV':>5} {'Q42':>6} {'Cash':>6} | {'Gross ROE':>10} {'Net ROE':>9} {'W20d':>8} {'V1':>4} {'V2':>4} {'V3':>4} {'Floor 8%':>11}")
print("-" * 105)

results = []
for name, spx, q42 in candidates:
    cash = 1.0 - spx - HV_ALLOC - q42
    if cash < 0:
        print(f"{name:<18}  INFEASIBLE (cash {cash*100:.1f}%)")
        continue
    gross = simulate(name, spx, q42, friction_on=False)
    net = simulate(name, spx, q42, friction_on=True)
    if gross is None or net is None:
        continue
    floor_pass_net = net["ann_roe"] >= 0.08
    print(f"{name:<18} {spx*100:>4.1f}% {HV_ALLOC*100:>4.1f}% {q42*100:>5.1f}% {cash*100:>5.1f}% | "
          f"{gross['ann_roe']*100:>9.2f}% {net['ann_roe']*100:>8.2f}% "
          f"{net['worst_20d']*100:>7.2f}% "
          f"{'✓' if net['v1_pass'] else '✗':>3} {'✓' if net['v2_pass'] else '✗':>3} {'✓' if net['v3_pass'] else '✗':>3} "
          f"{'PASS' if floor_pass_net else 'FAIL':>11}")
    results.append({
        "candidate": name, "spx_pct": int(spx*100), "hv_pct": HV_ALLOC*100,
        "q42_pct": q42*100, "cash_pct": cash*100,
        "gross_ann_roe_pct": round(gross["ann_roe"]*100, 2),
        "net_ann_roe_pct": round(net["ann_roe"]*100, 2),
        "friction_drag_pp": round((gross["ann_roe"] - net["ann_roe"])*100, 2),
        "net_max_dd_pct": round(net["max_dd"]*100, 2),
        "net_worst_20d_pct": round(net["worst_20d"]*100, 2),
        "net_worst_63d_pct": round(net["worst_63d"]*100, 2),
        "net_sharpe": round(net["sharpe"], 2),
        "v1_pass_net": net["v1_pass"],
        "v2_pass_net": net["v2_pass"],
        "v3_pass_net": net["v3_pass"],
        "all_vetoes_pass_net": net["v1_pass"] and net["v2_pass"] and net["v3_pass"],
        "floor_8_pass_net": net["ann_roe"] >= 0.08,
    })

pd.DataFrame(results).to_csv(OUT / "q073_p2a_plus_friction_results.csv", index=False)

print("\n" + "=" * 70)
print("VERDICT (NET ROE basis)")
print("=" * 70)
df = pd.DataFrame(results)
qualifying_net = df[df["all_vetoes_pass_net"] & df["floor_8_pass_net"]]
v2pass_only = df[df["all_vetoes_pass_net"]]

if len(qualifying_net) > 0:
    best = qualifying_net.sort_values("net_ann_roe_pct", ascending=False).iloc[0]
    print(f"\n✓ P2A+ SUCCESS — {len(qualifying_net)} architecture pass V1-V3 + floor 8% NET")
    print(f"\nBest by NET ROE:")
    print(f"  Candidate: {best['candidate']}  SPX {best['spx_pct']}% / HV 5% / Q42 {best['q42_pct']}%")
    print(f"  Net ROE {best['net_ann_roe_pct']}%   Worst 20d {best['net_worst_20d_pct']}%   MaxDD {best['net_max_dd_pct']}%")
else:
    print(f"\n⚠️  NO architecture passes BOTH V1-V3 AND floor 8% on NET basis")
    if len(v2pass_only) > 0:
        best = v2pass_only.sort_values("net_ann_roe_pct", ascending=False).iloc[0]
        gap = 8.0 - best["net_ann_roe_pct"]
        print(f"\nBest V1-V3 pass (NET, below floor):")
        print(f"  Candidate: {best['candidate']}  SPX {best['spx_pct']}% / Q42 {best['q42_pct']}%")
        print(f"  Net ROE {best['net_ann_roe_pct']}%   Worst 20d {best['net_worst_20d_pct']}%")
        print(f"  Net floor gap: {gap:.2f}pp")

print(f"\nOutput: {OUT / 'q073_p2a_plus_friction_results.csv'}")
