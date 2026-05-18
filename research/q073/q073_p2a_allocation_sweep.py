"""Q073 P2A — Capital Allocation Sweep.

Anchor (V2-pass frontier, from P1.5b):
  Stress SPX cap = 50%
  Second-leg SPX cap = 40%
  (these are LOCKED, not swept)

Levers:
  L1: Normal SPX cap (70 / 75 / 80)
  L2: HV Ladder allocation (5 / 7.5 / 10%)
  L3: Q042 Sleeve A allocation (10 / 12.5 / 15%)
  L4: Cash (residual)

Candidates (hypothesis-driven, per PM 2026-05-17):
  Base: SPX 70 / HV 5 / Q42 10 / Cash 15
  A:    SPX 75 / HV 5 / Q42 10 / Cash 10
  B:    SPX 70 / HV 7.5 / Q42 10 / Cash 12.5
  C:    SPX 70 / HV 5 / Q42 12.5 / Cash 12.5
  D:    SPX 75 / HV 7.5 / Q42 10 / Cash 7.5
  E:    SPX 75 / HV 5 / Q42 12.5 / Cash 7.5
  F:    SPX 75 / HV 7.5 / Q42 12.5 / Cash 5

Plus bonus probe to bracket the floor:
  G:    SPX 80 / HV 7.5 / Q42 12.5 / Cash 0
  H:    SPX 75 / HV 10 / Q42 15 / Cash 0

Output:
  q073_p2a_candidate_results.csv
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

# Locked V2-pass anchor caps
STRESS_SPX_CAP = 0.50
SECOND_LEG_CAP = 0.40

# Baseline P1.3R allocations used in the engine runs (for PnL scaling)
P13R_SPX_ALLOC = 0.60
P13R_HV_ALLOC  = 0.05
P13R_Q42_ALLOC = 0.10
P13R_CASH_ALLOC = 0.25

print("Q073 P2A — Allocation Sweep", flush=True)
print("=" * 70, flush=True)
print(f"\nLocked V2-pass anchor:")
print(f"  Stress SPX cap     : {STRESS_SPX_CAP*100:.0f}%")
print(f"  Second-leg SPX cap : {SECOND_LEG_CAP*100:.0f}%")

# ── Load P1.3R daily PnL series ────────────────────────────────────────
combined = pd.read_csv(OUT / "q073_p1_3R_unified_daily_pnl.csv",
                       parse_dates=["date"], index_col="date")
print(f"\nLoaded P1.3R daily series: {len(combined)} days", flush=True)

# ── Load market data for stress / second-leg flags ─────────────────────
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
print(f"Market frame: stress {mkt['stress_active'].mean()*100:.1f}% of days, second-leg {mkt['second_leg_active'].mean()*100:.1f}%", flush=True)


def simulate(name: str, normal_spx: float, hv_alloc: float, q42a_alloc: float):
    """Run one candidate. Returns metrics dict."""
    cash_normal = 1.0 - normal_spx - hv_alloc - q42a_alloc
    if cash_normal < 0:
        return None  # infeasible

    df = combined.copy().join(mkt[["stress_active", "second_leg_active"]], how="left").ffill()

    # Day-by-day SPX allocation (state-dependent)
    spx_alloc = pd.Series(normal_spx, index=df.index)
    spx_alloc[df["stress_active"].astype(bool)] = STRESS_SPX_CAP
    spx_alloc[df["second_leg_active"].astype(bool)] = SECOND_LEG_CAP
    df["spx_alloc"] = spx_alloc

    # Cash residual (state-dependent: shrinks when SPX shrinks, kept HV/Q42 fixed)
    df["cash_alloc"] = 1.0 - df["spx_alloc"] - hv_alloc - q42a_alloc
    df["cash_alloc"] = df["cash_alloc"].clip(lower=0)

    # Scale PnL streams (HV / Q42 static, SPX / Cash state-dependent)
    df["spx_pnl_scaled"] = df["spx_pnl"] * (df["spx_alloc"] / P13R_SPX_ALLOC)
    df["hv_pnl_scaled"]  = df["hv_pnl"]  * (hv_alloc / P13R_HV_ALLOC)
    df["q42a_pnl_scaled"] = df["q42a_pnl"] * (q42a_alloc / P13R_Q42_ALLOC)
    df["cash_pnl_scaled"] = df["cash_pnl"] * (df["cash_alloc"] / P13R_CASH_ALLOC)
    df["total_pnl"] = df["spx_pnl_scaled"] + df["hv_pnl_scaled"] + df["q42a_pnl_scaled"] + df["cash_pnl_scaled"]
    df["cum_pnl"] = df["total_pnl"].cumsum()
    df["equity"] = NLV + df["cum_pnl"]
    df["equity_start"] = df["equity"].shift(1).fillna(NLV)
    df["daily_ret"] = df["total_pnl"] / df["equity_start"]

    years = len(df) / 252
    final_eq = df["equity"].iloc[-1]
    ann_roe_geo = (final_eq / NLV) ** (1.0 / years) - 1.0 if years > 0 else 0.0

    running_max = df["equity"].cummax()
    drawdown = (df["equity"] - running_max) / running_max
    max_dd = drawdown.min()

    roll_20d = df["daily_ret"].rolling(20).sum()
    roll_63d = df["daily_ret"].rolling(63).sum()
    worst_20d = roll_20d.min()
    worst_63d = roll_63d.min()

    sharpe = df["daily_ret"].mean() / df["daily_ret"].std() * (252**0.5) if df["daily_ret"].std() > 0 else 0.0
    downside = df["daily_ret"][df["daily_ret"] < 0]
    sortino = df["daily_ret"].mean() / (downside.pow(2).mean() ** 0.5) * (252**0.5) if len(downside) > 0 else 0.0

    # Crisis windows
    crises = {
        "DotCom_2000_2002": ("2000-03-01", "2002-10-31"),
        "GFC_2008":         ("2008-08-01", "2009-03-31"),
        "COVID_2020":       ("2020-02-15", "2020-05-31"),
        "Bear_2022":        ("2022-01-01", "2022-12-31"),
    }
    crisis_returns = {}
    for cname, (s, e) in crises.items():
        sub = df[(df.index >= s) & (df.index <= e)]
        if len(sub) > 0:
            eq_at_start = sub["equity_start"].iloc[0]
            crisis_returns[cname] = sub["total_pnl"].sum() / eq_at_start if eq_at_start > 0 else 0.0

    return {
        "candidate": name,
        "normal_spx_pct": int(normal_spx * 100),
        "hv_pct": hv_alloc * 100,
        "q42a_pct": q42a_alloc * 100,
        "cash_normal_pct": cash_normal * 100,
        "ann_roe_pct": round(ann_roe_geo * 100, 2),
        "max_dd_pct": round(max_dd * 100, 2),
        "worst_20d_pct": round(worst_20d * 100, 2),
        "worst_63d_pct": round(worst_63d * 100, 2),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "v1_pass": max_dd >= -0.28,
        "v2_pass": worst_20d >= -0.11,
        "v3_pass": worst_63d >= -0.17,
        "all_vetoes_pass": (max_dd >= -0.28) and (worst_20d >= -0.11) and (worst_63d >= -0.17),
        "roe_meets_floor": ann_roe_geo >= 0.08,
        "final_eq_M": round(final_eq / 1e6, 2),
        "DotCom_2000_2002": round(crisis_returns.get("DotCom_2000_2002", 0) * 100, 2),
        "GFC_2008": round(crisis_returns.get("GFC_2008", 0) * 100, 2),
        "COVID_2020": round(crisis_returns.get("COVID_2020", 0) * 100, 2),
        "Bear_2022": round(crisis_returns.get("Bear_2022", 0) * 100, 2),
    }


# Candidates per PM list
candidates = [
    ("Base", 0.70, 0.05,   0.10),
    ("A",    0.75, 0.05,   0.10),
    ("B",    0.70, 0.075,  0.10),
    ("C",    0.70, 0.05,   0.125),
    ("D",    0.75, 0.075,  0.10),
    ("E",    0.75, 0.05,   0.125),
    ("F",    0.75, 0.075,  0.125),
    ("G_aggressive_80",  0.80, 0.075,  0.125),
    ("H_max_overlay",    0.75, 0.10,   0.15),
]

results = []
for name, spx, hv, q42 in candidates:
    r = simulate(name, spx, hv, q42)
    if r is None:
        print(f"  {name}: INFEASIBLE (negative cash)")
        continue
    results.append(r)
    print(f"\n[{name}] SPX={int(spx*100)}% HV={hv*100:.1f}% Q42={q42*100:.1f}% Cash={r['cash_normal_pct']:.1f}%")
    print(f"  Ann ROE:   {r['ann_roe_pct']}%   MaxDD: {r['max_dd_pct']}%   "
          f"Worst20d: {r['worst_20d_pct']}%   Sharpe: {r['sharpe']}")
    print(f"  V1: {'PASS' if r['v1_pass'] else 'FAIL'}  V2: {'PASS' if r['v2_pass'] else 'FAIL'}  "
          f"V3: {'PASS' if r['v3_pass'] else 'FAIL'}   "
          f"Floor 8%: {'PASS' if r['roe_meets_floor'] else 'FAIL'}")

df_results = pd.DataFrame(results)
df_results.to_csv(OUT / "q073_p2a_candidate_results.csv", index=False)

print("\n" + "=" * 70)
print("Summary table (sorted: V1+V2+V3 pass first, then ROE desc)")
print("=" * 70)
df_results_sorted = df_results.sort_values(
    by=["all_vetoes_pass", "roe_meets_floor", "ann_roe_pct"],
    ascending=[False, False, False]
)
pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
print(df_results_sorted[["candidate", "normal_spx_pct", "hv_pct", "q42a_pct",
                          "ann_roe_pct", "worst_20d_pct", "max_dd_pct", "sharpe",
                          "v1_pass", "v2_pass", "v3_pass", "all_vetoes_pass",
                          "roe_meets_floor"]].to_string(index=False))

print("\n[crisis windows by candidate (% of equity at window start)]")
print(df_results_sorted[["candidate", "DotCom_2000_2002", "GFC_2008", "COVID_2020", "Bear_2022"]].to_string(index=False))

print("\n" + "=" * 70)
print("Verdict")
print("=" * 70)
qualifying = df_results[df_results["all_vetoes_pass"] & df_results["roe_meets_floor"]]
if len(qualifying) > 0:
    best = qualifying.sort_values("ann_roe_pct", ascending=False).iloc[0]
    print(f"\n✓ P2A SUCCESS — {len(qualifying)} architecture(s) pass V1-V3 + floor 8%")
    print(f"\nBest by ROE:")
    print(f"  Candidate {best['candidate']}: SPX {best['normal_spx_pct']}% / HV {best['hv_pct']:.1f}% / Q42 {best['q42a_pct']:.1f}% / Cash {best['cash_normal_pct']:.1f}%")
    print(f"  Ann ROE {best['ann_roe_pct']}%, Worst 20d {best['worst_20d_pct']}%, MaxDD {best['max_dd_pct']}%")
else:
    v2_pass_only = df_results[df_results["all_vetoes_pass"]]
    if len(v2_pass_only) > 0:
        best_below_floor = v2_pass_only.sort_values("ann_roe_pct", ascending=False).iloc[0]
        print(f"\n⚠️  NO architecture passes BOTH V1-V3 AND floor 8%")
        print(f"Best V1-V3 pass (still below floor):")
        print(f"  Candidate {best_below_floor['candidate']}: {best_below_floor['ann_roe_pct']}% ROE, V2 {best_below_floor['worst_20d_pct']}%")
        print(f"  Gap to floor: {8.0 - best_below_floor['ann_roe_pct']:.2f}pp")
    else:
        print(f"\n❌ NO architecture even passes V1-V3 vetoes")

print(f"\nOutput: {OUT / 'q073_p2a_candidate_results.csv'}")
