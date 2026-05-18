"""Q073 P4 — 双轨 Validation: Arch-2 (E5) + Arch-3 (no HV).

Per P3 memo:
  Arch-2 (E5):  SPX 80/50/40, HV 5%, Q42 12.5%, Cash 2.5%
  Arch-3 (no HV): SPX 80/50/40, HV 0%, Q42 17.5%, Cash 2.5%

P4 modules:
  P4.1 V6 Bootstrap significance (Q071 method, block=250, 20 seeds)
  P4.2 V7 Walk-forward split-sample (2000-2013 vs 2013-2026)
  P4.3 Q042 concentration analysis (top-N trade contribution, at 17.5% sizing)
  P4.4 Friction sensitivity (±50% of base estimates)
  P4.5 Synthetic crisis stress + correlated model error

Outputs:
  q073_p4_results.csv (consolidated)
  q073_p4_q42_concentration.csv (Q042-specific)
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

FRICTION_ANN_SPX  = 0.0035
FRICTION_ANN_HV   = 0.0010
FRICTION_ANN_Q42  = 0.0005
FRICTION_ANN_CASH = 0.0

P13R_SPX = 0.60; P13R_HV = 0.05; P13R_Q42 = 0.10; P13R_CASH = 0.25

print("Q073 P4 — Dual-track Validation (Arch-2 + Arch-3)", flush=True)
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


def build_arch_pnl(spx_normal, spx_stress, spx_2nd, hv_alloc, q42_alloc,
                   friction_mult=1.0, apply_friction=True,
                   data=combined, market=mkt):
    """Return daily total PnL series for an architecture."""
    df = data.copy().join(market[["stress_active", "second_leg_active"]], how="left").ffill()
    spx_a = pd.Series(spx_normal, index=df.index)
    spx_a[df["stress_active"].astype(bool)] = spx_stress
    spx_a[df["second_leg_active"].astype(bool)] = spx_2nd
    df["spx_alloc"] = spx_a
    df["cash_alloc"] = (1.0 - df["spx_alloc"] - hv_alloc - q42_alloc).clip(lower=0)

    spx_pnl = df["spx_pnl"] * (df["spx_alloc"] / P13R_SPX)
    hv_pnl  = df["hv_pnl"]  * (hv_alloc / P13R_HV) if hv_alloc > 0 else pd.Series(0.0, index=df.index)
    q42_pnl = df["q42a_pnl"] * (q42_alloc / P13R_Q42)
    cash_pnl = df["cash_pnl"] * (df["cash_alloc"] / P13R_CASH)

    if apply_friction:
        spx_drag = FRICTION_ANN_SPX * friction_mult * NLV * (df["spx_alloc"] / P13R_SPX) / 252.0
        hv_drag  = (FRICTION_ANN_HV  * friction_mult * NLV * (hv_alloc / P13R_HV) / 252.0) if hv_alloc > 0 else 0.0
        q42_drag = FRICTION_ANN_Q42 * friction_mult * NLV * (q42_alloc / P13R_Q42) / 252.0
        cash_drag = FRICTION_ANN_CASH * friction_mult * NLV * (df["cash_alloc"] / P13R_CASH) / 252.0
        spx_pnl = spx_pnl - spx_drag
        if hv_alloc > 0:
            hv_pnl = hv_pnl - hv_drag
        q42_pnl = q42_pnl - q42_drag
        cash_pnl = cash_pnl - cash_drag

    return spx_pnl + hv_pnl + q42_pnl + cash_pnl


def metrics(pnl_series):
    cum = pnl_series.cumsum()
    eq = NLV + cum
    eq_start = eq.shift(1).fillna(NLV)
    ret = pnl_series / eq_start
    years = len(pnl_series) / 252
    ann_roe = (eq.iloc[-1] / NLV) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    rm = eq.cummax()
    dd = (eq - rm) / rm
    max_dd = dd.min()
    w20 = ret.rolling(20).sum().min()
    w63 = ret.rolling(63).sum().min()
    sharpe = ret.mean() / ret.std() * (252**0.5) if ret.std() > 0 else 0.0
    return ann_roe, max_dd, w20, w63, sharpe

# Build both architectures
print("\nBuilding Arch-2 (E5) and Arch-3 (no HV) PnL series...")
arch2_pnl = build_arch_pnl(0.80, 0.50, 0.40, 0.05, 0.125, friction_mult=1.0)
arch3_pnl = build_arch_pnl(0.80, 0.50, 0.40, 0.00, 0.175, friction_mult=1.0)

a2 = metrics(arch2_pnl)
a3 = metrics(arch3_pnl)
print(f"  Arch-2: ROE {a2[0]*100:.2f}%, MaxDD {a2[1]*100:.2f}%, W20d {a2[2]*100:.2f}%, Sharpe {a2[4]:.2f}")
print(f"  Arch-3: ROE {a3[0]*100:.2f}%, MaxDD {a3[1]*100:.2f}%, W20d {a3[2]*100:.2f}%, Sharpe {a3[4]:.2f}")

# ──────────────────────────────────────────────────────────────────────
# P4.1 V6 Bootstrap (Q071 method)
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4.1 V6 Bootstrap (block=250, 20 seeds)")
print("=" * 70)

def bootstrap_sig_rate(daily_pnl: pd.Series, n_boot=2000, block_size=250, seeds=20) -> dict:
    arr = daily_pnl.values
    n = len(arr)
    if n < block_size:
        return {"sig_rate": 0.0, "median_ci_lo_ann": float("nan")}
    sig_count = 0
    ci_los_ann = []
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
        # Annualize ci_lo: ci_lo is daily mean, ann = ci_lo × 252
        ci_los_ann.append(ci_lo * 252 / NLV * 100)  # as % NLV/yr
    return {
        "sig_rate": sig_count / seeds,
        "median_ci_lo_ann_pct": float(np.median(ci_los_ann)),
    }

print("\n  Running Arch-2 bootstrap...")
b2 = bootstrap_sig_rate(arch2_pnl)
print(f"    Sig rate: {b2['sig_rate']*100:.0f}%  | Median CI lo (ann %): {b2['median_ci_lo_ann_pct']:.2f}%")

print("\n  Running Arch-3 bootstrap...")
b3 = bootstrap_sig_rate(arch3_pnl)
print(f"    Sig rate: {b3['sig_rate']*100:.0f}%  | Median CI lo (ann %): {b3['median_ci_lo_ann_pct']:.2f}%")

# ──────────────────────────────────────────────────────────────────────
# P4.2 V7 Walk-Forward / Split-sample
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4.2 V7 Split-sample robustness (2000-2013 vs 2013-2026)")
print("=" * 70)

mid_date = pd.Timestamp("2013-01-01")
h1_idx = arch2_pnl.index < mid_date
h2_idx = arch2_pnl.index >= mid_date
a2_h1 = metrics(arch2_pnl[h1_idx])
a2_h2 = metrics(arch2_pnl[h2_idx])
a3_h1 = metrics(arch3_pnl[h1_idx])
a3_h2 = metrics(arch3_pnl[h2_idx])

print(f"\n  Arch-2 H1 (2000-2012): ROE {a2_h1[0]*100:.2f}%, W20d {a2_h1[2]*100:.2f}%")
print(f"  Arch-2 H2 (2013-2026): ROE {a2_h2[0]*100:.2f}%, W20d {a2_h2[2]*100:.2f}%")
print(f"  Arch-3 H1 (2000-2012): ROE {a3_h1[0]*100:.2f}%, W20d {a3_h1[2]*100:.2f}%")
print(f"  Arch-3 H2 (2013-2026): ROE {a3_h2[0]*100:.2f}%, W20d {a3_h2[2]*100:.2f}%")
print(f"  Arch-3 advantage:  H1 ROE {(a3_h1[0]-a2_h1[0])*100:+.2f}pp, W20d {(a3_h1[2]-a2_h1[2])*100:+.2f}pp")
print(f"                     H2 ROE {(a3_h2[0]-a2_h2[0])*100:+.2f}pp, W20d {(a3_h2[2]-a2_h2[2])*100:+.2f}pp")
print(f"  Arch-3 leads BOTH halves: {(a3_h1[2] > a2_h1[2]) and (a3_h2[2] > a2_h2[2])}")

# ──────────────────────────────────────────────────────────────────────
# P4.3 Q042 Concentration (Arch-3 specific, at 17.5% sizing)
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4.3 Q042 concentration (top-N contribution at 17.5% allocation)")
print("=" * 70)

q42_trades = pd.read_csv(REPO / "data" / "q042_backtest_trades.csv")
sleeve_a = q42_trades[q42_trades["sleeve_id"] == "A"].copy()
sleeve_a["exit_date"] = pd.to_datetime(sleeve_a["exit_date"])
# Rescale to 17.5% allocation (P1.3R was at 10%)
sleeve_a["pnl_at_17_5pct"] = sleeve_a["account_pct"] * (0.175 * NLV)
total_pnl = sleeve_a["pnl_at_17_5pct"].sum()
years = (sleeve_a["exit_date"].max() - pd.Timestamp("2007-02-28")).days / 365.25
ann_roe_contrib = total_pnl / years / NLV
print(f"\n  Total Q042 PnL at 17.5% allocation: ${total_pnl:,.0f}")
print(f"  Ann ROE contribution: {ann_roe_contrib*100:.2f}%")
print(f"  Trade count: {len(sleeve_a)}")

sorted_trades = sleeve_a.sort_values("pnl_at_17_5pct", ascending=False)
top3_sum = sorted_trades.head(3)["pnl_at_17_5pct"].sum()
top5_sum = sorted_trades.head(5)["pnl_at_17_5pct"].sum()
worst_trade = sleeve_a["pnl_at_17_5pct"].min()
print(f"\n  Top-1 trade:  ${sorted_trades.iloc[0]['pnl_at_17_5pct']:>10,.0f}   ({sorted_trades.iloc[0]['pnl_at_17_5pct']/total_pnl*100:.1f}% of total)")
print(f"  Top-3 trades: ${top3_sum:>10,.0f}   ({top3_sum/total_pnl*100:.1f}% of total)")
print(f"  Top-5 trades: ${top5_sum:>10,.0f}   ({top5_sum/total_pnl*100:.1f}% of total)")
print(f"  Worst trade:  ${worst_trade:>10,.0f}   ({worst_trade/NLV*100:.2f}% NLV at 17.5% sizing)")

# Simulate Arch-3 with top-N Q042 trades removed
def arch3_drop_top_n(n_drop):
    drop_dates = sorted_trades.head(n_drop)["exit_date"].tolist()
    sa_keep = sleeve_a[~sleeve_a["exit_date"].isin(drop_dates)].copy()
    daily = sa_keep.groupby("exit_date")["pnl_at_17_5pct"].sum().to_frame("q42a_pnl_modified")
    # Replace q42a_pnl in combined for this simulation
    df = combined.copy()
    df["q42a_pnl_orig"] = df["q42a_pnl"]
    df["q42a_pnl"] = 0.0
    df.loc[daily.index, "q42a_pnl"] = daily["q42a_pnl_modified"]
    # Re-run with modified Q042 series
    df = df.join(mkt[["stress_active", "second_leg_active"]], how="left").ffill()
    spx_a = pd.Series(0.80, index=df.index)
    spx_a[df["stress_active"].astype(bool)] = 0.50
    spx_a[df["second_leg_active"].astype(bool)] = 0.40
    df["spx_alloc"] = spx_a
    df["cash_alloc"] = (1.0 - df["spx_alloc"] - 0.0 - 0.175).clip(lower=0)
    spx_pnl  = df["spx_pnl"] * (df["spx_alloc"] / P13R_SPX)
    q42_pnl  = df["q42a_pnl"]  # already at 17.5% sizing
    cash_pnl = df["cash_pnl"] * (df["cash_alloc"] / P13R_CASH)
    spx_drag = FRICTION_ANN_SPX * NLV * (df["spx_alloc"] / P13R_SPX) / 252.0
    q42_drag = FRICTION_ANN_Q42 * NLV * (0.175 / P13R_Q42) / 252.0
    cash_drag = FRICTION_ANN_CASH * NLV * (df["cash_alloc"] / P13R_CASH) / 252.0
    spx_pnl = spx_pnl - spx_drag
    q42_pnl = q42_pnl - q42_drag
    cash_pnl = cash_pnl - cash_drag
    return metrics(spx_pnl + q42_pnl + cash_pnl)

print("\n  Arch-3 robustness — drop top Q042 trades and re-simulate:")
for n in [0, 1, 3, 5]:
    res = arch3_drop_top_n(n)
    print(f"    Drop top-{n}:  Net ROE {res[0]*100:.2f}%, W20d {res[2]*100:.2f}%, Sharpe {res[4]:.2f}")

# ──────────────────────────────────────────────────────────────────────
# P4.4 Friction sensitivity (±50%)
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4.4 Friction sensitivity (Net ROE under ±50% friction)")
print("=" * 70)
print(f"  {'Friction mult':<15} {'Arch-2 ROE':>12} {'Arch-3 ROE':>12} {'Δ (A3 - A2)':>14}")
for fm in [0.5, 0.75, 1.0, 1.25, 1.5]:
    a2m = metrics(build_arch_pnl(0.80, 0.50, 0.40, 0.05, 0.125, friction_mult=fm))
    a3m = metrics(build_arch_pnl(0.80, 0.50, 0.40, 0.00, 0.175, friction_mult=fm))
    print(f"  {fm:<15.2f} {a2m[0]*100:>11.2f}% {a3m[0]*100:>11.2f}% {(a3m[0]-a2m[0])*100:>+13.3f}pp")

# ──────────────────────────────────────────────────────────────────────
# P4.5 Synthetic crisis stress (COVID-style synthetic shock injection)
# ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("P4.5 Synthetic crisis stress (worst 20d shock injection)")
print("=" * 70)
# Idea: amplify daily PnL by -20% during a synthetic 20-day window
# Place synthetic shock at a normal period (2015 Q4 — actually fairly calm)
shock_start = pd.Timestamp("2015-09-01")
shock_end = pd.Timestamp("2015-10-15")
shock_window_idx = (arch2_pnl.index >= shock_start) & (arch2_pnl.index <= shock_end)

# Inject -2% NLV in 20-day window split across days
shock_per_day = -0.02 * NLV / shock_window_idx.sum()
arch2_shocked = arch2_pnl.copy()
arch3_shocked = arch3_pnl.copy()
arch2_shocked[shock_window_idx] = arch2_shocked[shock_window_idx] + shock_per_day
arch3_shocked[shock_window_idx] = arch3_shocked[shock_window_idx] + shock_per_day

a2s = metrics(arch2_shocked)
a3s = metrics(arch3_shocked)
print(f"\n  Synthetic shock injection (2015-09 to 2015-10, -2% NLV over 20d):")
print(f"    Arch-2 shocked: ROE {a2s[0]*100:.2f}%, MaxDD {a2s[1]*100:.2f}%, W20d {a2s[2]*100:.2f}%")
print(f"    Arch-3 shocked: ROE {a3s[0]*100:.2f}%, MaxDD {a3s[1]*100:.2f}%, W20d {a3s[2]*100:.2f}%")
print(f"    Robustness:     A2 deteriorate ROE {(a2s[0]-a2[0])*100:+.2f}pp / W20d {(a2s[2]-a2[2])*100:+.2f}pp")
print(f"                    A3 deteriorate ROE {(a3s[0]-a3[0])*100:+.2f}pp / W20d {(a3s[2]-a3[2])*100:+.2f}pp")

print("\n" + "=" * 70)
print("Done. P5 final memo writes from these results.")
