"""Q073 P3 — Build 4 candidate architectures + cross-validation table.

Arch-0: Status quo (P1.3R, no governance, static 60% SPX) → baseline reference
Arch-1: Conservative (Current SPEC-103 R5/R6 60%/50%, no allocation change)
Arch-2: Moderate (E5) — SPX 80% normal / 50% stress / 40% 2nd-leg, HV 5%, Q42 12.5%
Arch-3: Radical — retire HV Ladder (5% → 0), redirect to Q042

Each architecture evaluated on:
  - Net Ann ROE (geometric)
  - V1 MaxDD ≤ 28%
  - V2 worst-20d ≤ 11% (point-in-time)
  - V3 worst-63d ≤ 17%
  - Sharpe
  - 4 crisis windows (DotCom / GFC / COVID / Bear22)

Output: q073_p3_architecture_comparison.csv + q073_p3_architecture_memo.md
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

# Friction (per E5 calibrated model)
FRICTION_ANN_SPX  = 0.0035
FRICTION_ANN_HV   = 0.0010
FRICTION_ANN_Q42  = 0.0005
FRICTION_ANN_CASH = 0.0

# P1.3R baseline allocations
P13R_SPX = 0.60; P13R_HV = 0.05; P13R_Q42 = 0.10; P13R_CASH = 0.25

print("Q073 P3 — Architecture Cross-Validation", flush=True)
print("=" * 70)

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


def simulate_arch(name: str, spx_normal: float, spx_stress: float, spx_2nd: float,
                  hv_alloc: float, q42_alloc: float, apply_friction: bool = True):
    df = combined.copy().join(mkt[["stress_active", "second_leg_active"]], how="left").ffill()

    spx_a = pd.Series(spx_normal, index=df.index)
    spx_a[df["stress_active"].astype(bool)] = spx_stress
    spx_a[df["second_leg_active"].astype(bool)] = spx_2nd
    df["spx_alloc"] = spx_a
    df["cash_alloc"] = (1.0 - df["spx_alloc"] - hv_alloc - q42_alloc).clip(lower=0)

    spx_pnl = df["spx_pnl"] * (df["spx_alloc"] / P13R_SPX)
    hv_pnl  = df["hv_pnl"]  * (hv_alloc / P13R_HV)  if hv_alloc > 0 else 0.0
    q42_pnl = df["q42a_pnl"] * (q42_alloc / P13R_Q42)
    cash_pnl = df["cash_pnl"] * (df["cash_alloc"] / P13R_CASH)

    if apply_friction:
        spx_drag = FRICTION_ANN_SPX * NLV * (df["spx_alloc"] / P13R_SPX) / 252.0
        hv_drag  = FRICTION_ANN_HV  * NLV * (hv_alloc / P13R_HV) / 252.0 if hv_alloc > 0 else 0.0
        q42_drag = FRICTION_ANN_Q42 * NLV * (q42_alloc / P13R_Q42) / 252.0
        cash_drag = FRICTION_ANN_CASH * NLV * (df["cash_alloc"] / P13R_CASH) / 252.0
        spx_pnl = spx_pnl - spx_drag
        hv_pnl  = hv_pnl  - hv_drag if hv_alloc > 0 else hv_pnl
        q42_pnl = q42_pnl - q42_drag
        cash_pnl = cash_pnl - cash_drag

    if isinstance(hv_pnl, float):
        hv_pnl = pd.Series(0.0, index=df.index)
    df["total_pnl"] = spx_pnl + hv_pnl + q42_pnl + cash_pnl
    df["cum_pnl"] = df["total_pnl"].cumsum()
    df["equity"] = NLV + df["cum_pnl"]
    df["equity_start"] = df["equity"].shift(1).fillna(NLV)
    df["daily_ret"] = df["total_pnl"] / df["equity_start"]

    years = len(df) / 252
    final_eq = df["equity"].iloc[-1]
    ann_roe = (final_eq / NLV) ** (1.0 / years) - 1.0
    running_max = df["equity"].cummax()
    drawdown = (df["equity"] - running_max) / running_max
    max_dd = drawdown.min()
    roll_20d = df["daily_ret"].rolling(20).sum()
    roll_63d = df["daily_ret"].rolling(63).sum()
    worst_20d = roll_20d.min()
    worst_63d = roll_63d.min()
    sharpe = df["daily_ret"].mean() / df["daily_ret"].std() * (252**0.5) if df["daily_ret"].std() > 0 else 0.0
    sortino_down = df["daily_ret"][df["daily_ret"] < 0]
    sortino = df["daily_ret"].mean() / (sortino_down.pow(2).mean() ** 0.5) * (252**0.5) if len(sortino_down) > 0 else 0.0

    crises = {
        "DotCom_2000_2002": ("2000-03-01", "2002-10-31"),
        "GFC_2008":         ("2008-08-01", "2009-03-31"),
        "COVID_2020":       ("2020-02-15", "2020-05-31"),
        "Bear_2022":        ("2022-01-01", "2022-12-31"),
    }
    crisis_pcts = {}
    for cname, (s, e) in crises.items():
        sub = df[(df.index >= s) & (df.index <= e)]
        if len(sub) > 0:
            eq0 = sub["equity_start"].iloc[0]
            crisis_pcts[cname] = sub["total_pnl"].sum() / eq0 if eq0 > 0 else 0.0

    return {
        "name": name,
        "spx_normal": spx_normal, "spx_stress": spx_stress, "spx_2nd": spx_2nd,
        "hv": hv_alloc, "q42": q42_alloc,
        "net_ann_roe": ann_roe,
        "max_dd": max_dd,
        "worst_20d": worst_20d,
        "worst_63d": worst_63d,
        "sharpe": sharpe,
        "sortino": sortino,
        "final_eq": final_eq,
        "v1_pass": max_dd >= -0.28,
        "v2_pass": worst_20d >= -0.11,
        "v3_pass": worst_63d >= -0.17,
        "all_vetoes": (max_dd >= -0.28) and (worst_20d >= -0.11) and (worst_63d >= -0.17),
        "floor_8": ann_roe >= 0.08,
        "dotcom": crisis_pcts.get("DotCom_2000_2002", 0),
        "gfc": crisis_pcts.get("GFC_2008", 0),
        "covid": crisis_pcts.get("COVID_2020", 0),
        "bear22": crisis_pcts.get("Bear_2022", 0),
    }


# Define 4 architectures
print("\n[Arch-0] Status quo: P1.3R, no governance, static 60% SPX")
arch0 = simulate_arch("Arch-0 status_quo", 0.60, 0.60, 0.60, 0.05, 0.10, apply_friction=True)

print("[Arch-1] Conservative: Current SPEC-103 R5/R6 caps")
arch1 = simulate_arch("Arch-1 conservative", 0.70, 0.60, 0.50, 0.05, 0.10, apply_friction=True)

print("[Arch-2] Moderate (E5): tightened stress 50/40, SPX 80%, Q42 12.5%")
arch2 = simulate_arch("Arch-2 moderate_E5", 0.80, 0.50, 0.40, 0.05, 0.125, apply_friction=True)

print("[Arch-3] Radical: retire HV Ladder, redirect 5% to Q042 (now 17.5%)")
arch3 = simulate_arch("Arch-3 radical_no_HV", 0.80, 0.50, 0.40, 0.00, 0.175, apply_friction=True)

architectures = [arch0, arch1, arch2, arch3]

# ── Display comparison ─────────────────────────────────────────────────
print("\n" + "=" * 100)
print(f"{'Architecture':<22} {'SPX n/s/2L':<12} {'HV':>5} {'Q42':>6} | {'Net ROE':>9} {'MaxDD':>8} {'W20d':>8} {'V1':>4} {'V2':>4} {'V3':>4} {'Floor':>6}")
print("-" * 100)
for a in architectures:
    spx_label = f"{int(a['spx_normal']*100)}/{int(a['spx_stress']*100)}/{int(a['spx_2nd']*100)}"
    print(f"{a['name']:<22} {spx_label:<12} {a['hv']*100:>4.1f}% {a['q42']*100:>5.1f}% | "
          f"{a['net_ann_roe']*100:>8.2f}% {a['max_dd']*100:>7.2f}% {a['worst_20d']*100:>7.2f}% "
          f"{'✓' if a['v1_pass'] else '✗':>3} {'✓' if a['v2_pass'] else '✗':>3} {'✓' if a['v3_pass'] else '✗':>3} "
          f"{'✓' if a['floor_8'] else '✗':>5}")

print("\n[Crisis window returns (% of equity at window start)]")
print(f"{'Architecture':<22} {'DotCom':>10} {'GFC':>10} {'COVID':>10} {'Bear22':>10}")
print("-" * 70)
for a in architectures:
    print(f"{a['name']:<22} {a['dotcom']*100:>+8.2f}% {a['gfc']*100:>+8.2f}% {a['covid']*100:>+8.2f}% {a['bear22']*100:>+8.2f}%")

# ── Save CSV ──────────────────────────────────────────────────────────
rows = []
for a in architectures:
    rows.append({
        "architecture": a["name"],
        "spx_normal_pct": int(a["spx_normal"]*100),
        "spx_stress_pct": int(a["spx_stress"]*100),
        "spx_2nd_leg_pct": int(a["spx_2nd"]*100),
        "hv_pct": round(a["hv"]*100, 1),
        "q42_pct": round(a["q42"]*100, 1),
        "net_ann_roe_pct": round(a["net_ann_roe"]*100, 2),
        "max_dd_pct": round(a["max_dd"]*100, 2),
        "worst_20d_pct": round(a["worst_20d"]*100, 2),
        "worst_63d_pct": round(a["worst_63d"]*100, 2),
        "sharpe": round(a["sharpe"], 2),
        "sortino": round(a["sortino"], 2),
        "final_eq_M": round(a["final_eq"] / 1e6, 2),
        "v1_pass": a["v1_pass"], "v2_pass": a["v2_pass"], "v3_pass": a["v3_pass"],
        "all_vetoes_pass": a["all_vetoes"],
        "floor_8_pass": a["floor_8"],
        "dotcom_pct": round(a["dotcom"]*100, 2),
        "gfc_pct": round(a["gfc"]*100, 2),
        "covid_pct": round(a["covid"]*100, 2),
        "bear22_pct": round(a["bear22"]*100, 2),
    })
pd.DataFrame(rows).to_csv(OUT / "q073_p3_architecture_comparison.csv", index=False)

print("\n" + "=" * 70)
print("Verdict")
print("=" * 70)
qualifying = [a for a in architectures if a["all_vetoes"] and a["floor_8"]]
if qualifying:
    best = max(qualifying, key=lambda x: x["net_ann_roe"])
    print(f"\n✓ {len(qualifying)} architecture(s) pass ALL V1-V3 + floor 8% Net")
    print(f"Winner: {best['name']} (Net ROE {best['net_ann_roe']*100:.2f}%)")
else:
    print("\n⚠️  No architecture passes ALL V1-V3 + floor 8%")
    v2 = [a for a in architectures if a["all_vetoes"]]
    if v2:
        best = max(v2, key=lambda x: x["net_ann_roe"])
        print(f"Best V1-V3 pass: {best['name']} (Net ROE {best['net_ann_roe']*100:.2f}%, gap to floor {(0.08-best['net_ann_roe'])*100:.2f}pp)")

print(f"\nOutput: {OUT / 'q073_p3_architecture_comparison.csv'}")
