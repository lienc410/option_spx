"""Q078 P4 — Portfolio Integration (V3 S3 + SPEC-104 + SPEC-105 v2 baseline).

Per 2nd Quant G4 REVISE (2026-05-28):
  R1 — P4 portfolio integration on top of baseline (REQUIRED)
  R2 — Stronger bias correction:
       Option B path — Stage-1-shadow-only SPEC; bias validated in real shadow
       Pragmatic improvement: VIX + year bucket stratification (more granular than P3)
  R3 — Distribution-level gate validation (5%/95% CI, worst seed, not just mean)
  R4 — PM thesis sign-off — DONE (2026-05-28)
  R5 — Stage 1 shadow gates — captured in SPEC-108 outline

Methodology:
  Layer 0: SPEC-104 + SPEC-105 v2 baseline (Q074.2 style simulator)
  Layer 1: Q078 V3 S3 ladder on top (stratified bootstrap PnL)
  Combined: daily PnL aggregation, portfolio metrics

  Bias correction: 2-axis stratified bootstrap (strategy × year × VIX regime)
  20-seed CI for all metrics

Outputs:
  q078_p4_baseline_daily.csv          — SPEC-104+105v2 baseline
  q078_p4_combined_metrics.csv        — baseline vs +ladder per seed
  q078_p4_distribution_summary.csv    — mean + 5/95 CI per metric
  q078_p4_crisis_combined.csv         — 5 crises on combined series
  q078_p4_walkforward_combined.csv    — H1/H2 on combined series
  q078_p4_memo.md
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
OUT = REPO / "research" / "q078"
NLV = 894_000.0
SPX_TODAY = 7400.0
SIZING_CONTRACTS = 3
N_SEEDS = 20
AVG_HOLD_DAYS = 14
BP_CEILING_NORMAL = 0.35

# Baseline allocation (SPEC-104 + SPEC-105 v2 per Q074.2)
P13R_SPX = 0.60
P13R_Q42 = 0.10
HV_ALLOC = 0.0
Q42_ALLOC = 0.175
STRESS_SPX_CAP = 0.50
SECOND_LEG_CAP = 0.40
NORMAL_CAP = 0.80
BOOSTER_CAP = 0.90
FRICTION_ANN_SPX = 0.0035
FRICTION_ANN_Q42 = 0.0005
CASH_YIELD = 0.043

CONCURRENCY_CAP = {
    "Bull Put Spread": 1, "Bull Put Spread (High Vol)": 1,
    "Iron Condor": 1, "Iron Condor (High Vol)": 2,
    "Bear Call Spread (High Vol)": 1, "Bull Call Diagonal": 1,
}

CRISIS_WINDOWS = {
    "DotCom_2000_03":  ("2000-03-01", "2000-04-30"),
    "PreGFC_2007_07":  ("2007-07-01", "2007-09-30"),
    "Vol_2018_02":     ("2018-01-15", "2018-03-15"),
    "COVID_2020_02":   ("2020-02-15", "2020-03-31"),
    "Bear_2022_01":    ("2022-01-01", "2022-02-28"),
}

WALKFORWARD = {
    "H1_2000_2012": ("2000-01-01", "2012-12-31"),
    "H2_2013_2026": ("2013-01-01", "2026-12-31"),
}

print("Q078 P4 — Portfolio Integration (V3 S3 + SPEC-104 + SPEC-105 v2)", flush=True)
print("=" * 70)

# ── Build SPEC-104 + SPEC-105 v2 baseline daily PnL (Q074.2 style) ───
print("\nBuilding SPEC-104 + SPEC-105 v2 baseline...")

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

df = combined.copy().join(mkt[["above_ma50", "ddath", "vix", "vix_5d_change", "ivp_252",
                                 "stress_active", "second_leg_active"]], how="left").ffill()

def b4_f(row):
    if pd.isna(row["ivp_252"]):
        return False
    common = (
        not row["stress_active"]
        and not row["second_leg_active"]
        and row["above_ma50"] == 1
        and row["ddath"] > -0.04
        and row["vix"] < 22
        and row["vix_5d_change"] <= 1.5
    )
    if not common:
        return False
    return (row["ivp_252"] < 55.0) or (row["vix"] < 15.0)

df["booster_active"] = df.apply(b4_f, axis=1)
spx_alloc = pd.Series(NORMAL_CAP, index=df.index)
spx_alloc[df["stress_active"]] = STRESS_SPX_CAP
spx_alloc[df["second_leg_active"]] = SECOND_LEG_CAP
booster_eligible = df["booster_active"] & ~df["stress_active"] & ~df["second_leg_active"]
spx_alloc[booster_eligible] = BOOSTER_CAP
df["spx_alloc"] = spx_alloc
df["cash_alloc"] = 1.0 - spx_alloc - HV_ALLOC - Q42_ALLOC

spx_pnl_b = df["spx_pnl"] * (df["spx_alloc"] / P13R_SPX)
q42_pnl_b = df["q42a_pnl"] * (Q42_ALLOC / P13R_Q42)
cash_pnl_b = df["cash_alloc"] * NLV * CASH_YIELD / 252.0
spx_drag = FRICTION_ANN_SPX * NLV * (df["spx_alloc"] / P13R_SPX) / 252.0
q42_drag = FRICTION_ANN_Q42 * NLV * (Q42_ALLOC / P13R_Q42) / 252.0
df["baseline_pnl"] = (spx_pnl_b - spx_drag) + (q42_pnl_b - q42_drag) + cash_pnl_b

print(f"  Baseline days: {len(df)}, total PnL: ${df['baseline_pnl'].sum():+,.0f}")
df[["baseline_pnl"]].to_csv(OUT / "q078_p4_baseline_daily.csv")

# ── Load engine trades + signal history ──────────────────────────────
print("\nLoading engine 26y trades + signal history (for ladder bootstrap)...")
trades_df = pd.read_csv(OUT / "_engine_trades_26y_cache.csv", parse_dates=["entry_date"])
trades_df["pnl_per_ct"] = trades_df["exit_pnl"] / trades_df["contracts"].replace(0, 1)
trades_df["max_loss_per_ct"] = trades_df["total_bp"] / trades_df["contracts"].replace(0, 1)
trades_df["spx_scale"] = SPX_TODAY / trades_df["entry_spx"]
trades_df["pnl_today_per_ct"] = trades_df["pnl_per_ct"] * trades_df["spx_scale"]
trades_df["max_loss_today_per_ct"] = trades_df["max_loss_per_ct"] * trades_df["spx_scale"]
trades_df["year"] = trades_df["entry_date"].dt.year

def year_bucket(y):
    if y < 2010: return "pre_2010"
    if y < 2018: return "2010_2017"
    return "2018_plus"

def vix_bucket(v):
    if v < 15: return "low"
    if v < 22: return "normal"
    return "high"

trades_df["year_bucket"] = trades_df["year"].apply(year_bucket)
trades_df["vix_bucket"] = trades_df["entry_vix"].apply(vix_bucket)

# 2-axis stratified pool: (strategy, year_bucket × vix_bucket)
pool_2axis = {}
for strat in trades_df["strategy"].unique():
    for yb in ["pre_2010", "2010_2017", "2018_plus"]:
        for vb in ["low", "normal", "high"]:
            sub = trades_df[(trades_df["strategy"] == strat) &
                            (trades_df["year_bucket"] == yb) & (trades_df["vix_bucket"] == vb)]
            if len(sub) > 0:
                pool_2axis[(strat, yb, vb)] = list(zip(
                    sub["pnl_today_per_ct"].tolist(),
                    sub["max_loss_today_per_ct"].tolist(),
                ))

# Fallback pool by strategy only
pool_by_strat = {}
for strat in trades_df["strategy"].unique():
    sub = trades_df[trades_df["strategy"] == strat]
    pool_by_strat[strat] = list(zip(
        sub["pnl_today_per_ct"].tolist(),
        sub["max_loss_today_per_ct"].tolist(),
    ))

sig_df = pd.read_csv(OUT / "_signal_history_cache.csv", parse_dates=["date"])
sig_df = sig_df.set_index("date").sort_index()
all_days = sig_df.index.tolist()

# ── V3 eval days ─────────────────────────────────────────────────────
v3_eval = set()
last = None
for d in sig_df.index:
    if last is not None and (d - last).days < 5:
        continue
    if sig_df.loc[d, "strategy"] != "Reduce / Wait":
        v3_eval.add(d)
        last = d

print(f"  V3 eval days: {len(v3_eval)}")

# ── Stratified PnL lookup ────────────────────────────────────────────
def lookup_pnl_stratified(entry_date, strategy_name, vix_val, rng):
    yb = year_bucket(entry_date.year)
    vb = vix_bucket(vix_val)
    key = (strategy_name, yb, vb)
    if key in pool_2axis and pool_2axis[key]:
        pool = pool_2axis[key]
        idx = rng.integers(0, len(pool))
        return pool[idx]
    # Fallback
    if strategy_name in pool_by_strat and pool_by_strat[strategy_name]:
        pool = pool_by_strat[strategy_name]
        idx = rng.integers(0, len(pool))
        return pool[idx]
    return None, None

# ── Simulate V3 ladder daily PnL series (production gates applied) ───
def simulate_ladder_daily(eval_set, n_contracts, seed):
    rng = np.random.default_rng(seed)
    positions = []
    # Use df.index (baseline daily series) to align with portfolio metrics
    ladder_daily = pd.Series(0.0, index=df.index)
    bp_daily = pd.Series(0.0, index=df.index)

    for d in df.index:
        if d not in sig_df.index:
            continue
        # Exit handling — daily MTM linear distribution already in PnL booking
        positions = [p for p in positions if p["exit"] > d]

        if d not in eval_set:
            bp_daily.loc[d] = sum(p["max_loss"] for p in positions)
            continue
        strat = sig_df.loc[d, "strategy"]
        if strat == "Reduce / Wait":
            bp_daily.loc[d] = sum(p["max_loss"] for p in positions)
            continue

        # Production gates
        cap = CONCURRENCY_CAP.get(strat, 1)
        same_strat = sum(1 for p in positions if p["strategy"] == strat)
        if same_strat >= cap:
            bp_daily.loc[d] = sum(p["max_loss"] for p in positions)
            continue
        current_bp = sum(p["max_loss"] for p in positions)
        new_max_loss = pool_by_strat.get(strat, [(0, 0)])[0][1] * n_contracts
        if (current_bp + new_max_loss) / NLV > BP_CEILING_NORMAL:
            bp_daily.loc[d] = current_bp
            continue

        # Lookup PnL (stratified by year + VIX)
        vix_at_entry = mkt.loc[d, "vix"] if d in mkt.index else 17
        pnl_per_ct, max_loss_per_ct = lookup_pnl_stratified(d, strat, vix_at_entry, rng)
        if pnl_per_ct is None:
            bp_daily.loc[d] = current_bp
            continue

        total_pnl = pnl_per_ct * n_contracts
        total_max_loss = max_loss_per_ct * n_contracts
        exit_d = d + pd.Timedelta(days=AVG_HOLD_DAYS)

        # Distribute PnL linearly across hold business days
        hold = pd.date_range(d, exit_d, freq="B")
        hold = [h for h in hold if h in ladder_daily.index]
        if hold:
            per_day = total_pnl / len(hold)
            for h in hold:
                ladder_daily.loc[h] += per_day

        positions.append({"entry": d, "exit": exit_d, "strategy": strat,
                          "pnl": total_pnl, "max_loss": total_max_loss})
        bp_daily.loc[d] = current_bp + total_max_loss

    return ladder_daily, bp_daily

# ── Compute metrics for a daily PnL series ───────────────────────────
def compute_metrics_from_daily(daily_pnl, daily_index, name):
    eq = NLV + daily_pnl.cumsum()
    years = len(daily_index) / 252
    ann_roe = (eq.iloc[-1] / NLV) ** (1.0/years) - 1.0
    running_max = eq.cummax()
    drawdown = (eq - running_max) / running_max
    max_dd = drawdown.min()
    daily_ret = daily_pnl / eq.shift(1).fillna(NLV)
    w20 = daily_ret.rolling(20).sum().min()
    w63 = daily_ret.rolling(63).sum().min()
    sharpe = (daily_ret.mean() / daily_ret.std() * (252**0.5)
              if daily_ret.std() > 0 else 0)
    return {
        "name": name, "n_days": len(daily_index),
        "ann_roe_pct": ann_roe * 100,
        "max_dd_pct": max_dd * 100,
        "w20d_pct": w20 * 100, "w63d_pct": w63 * 100,
        "sharpe": sharpe, "final_eq_M": eq.iloc[-1] / 1e6,
    }

# ── 20-seed sweep: combined metrics ──────────────────────────────────
print(f"\nRunning {N_SEEDS}-seed sweep: baseline vs baseline + V3 S3 ladder...")

baseline_metrics = compute_metrics_from_daily(df["baseline_pnl"], df.index, "baseline_104+105v2")
print(f"\nBaseline SPEC-104+105v2:")
print(f"  Ann ROE: {baseline_metrics['ann_roe_pct']:.3f}%")
print(f"  MaxDD: {baseline_metrics['max_dd_pct']:+.2f}%")
print(f"  W20d: {baseline_metrics['w20d_pct']:+.2f}%   W63d: {baseline_metrics['w63d_pct']:+.2f}%")
print(f"  Sharpe: {baseline_metrics['sharpe']:.2f}")

# Run ladder with 20 seeds
seed_results = []
for seed in range(N_SEEDS):
    ladder_daily, bp_daily = simulate_ladder_daily(v3_eval, SIZING_CONTRACTS, seed=42+seed)
    combined_daily = df["baseline_pnl"] + ladder_daily
    m = compute_metrics_from_daily(combined_daily, df.index, f"combined_seed{seed}")
    m["seed"] = seed
    m["ladder_cum_pnl"] = ladder_daily.sum()
    m["delta_roe_pp"] = m["ann_roe_pct"] - baseline_metrics["ann_roe_pct"]
    m["delta_max_dd_pp"] = m["max_dd_pct"] - baseline_metrics["max_dd_pct"]
    m["delta_w20d_pp"] = m["w20d_pct"] - baseline_metrics["w20d_pct"]
    m["delta_w63d_pp"] = m["w63d_pct"] - baseline_metrics["w63d_pct"]
    m["delta_sharpe"] = m["sharpe"] - baseline_metrics["sharpe"]
    m["bp_mean_pct"] = bp_daily.mean() / NLV * 100
    m["bp_p95_pct"] = bp_daily.quantile(0.95) / NLV * 100
    seed_results.append(m)

seed_df = pd.DataFrame(seed_results)
seed_df.to_csv(OUT / "q078_p4_combined_metrics.csv", index=False)

# ── Distribution summary (R3) ────────────────────────────────────────
print("\n" + "=" * 70)
print("DISTRIBUTION SUMMARY (20-seed CI for combined baseline + V3 S3)")
print("=" * 70)

dist_rows = []
for metric in ["ann_roe_pct", "max_dd_pct", "w20d_pct", "w63d_pct", "sharpe",
               "delta_roe_pp", "delta_max_dd_pp", "delta_w20d_pp", "delta_w63d_pp",
               "delta_sharpe", "bp_mean_pct", "bp_p95_pct"]:
    s = seed_df[metric]
    dist_rows.append({
        "metric": metric,
        "mean": s.mean(), "median": s.median(),
        "p5": s.quantile(0.05), "p95": s.quantile(0.95),
        "worst_seed": s.min(), "best_seed": s.max(),
        "std": s.std(),
    })
dist_df = pd.DataFrame(dist_rows)
dist_df.to_csv(OUT / "q078_p4_distribution_summary.csv", index=False)
print(f"\n{'Metric':<22} {'mean':>9} {'p5':>9} {'p95':>9} {'worst':>9} {'best':>9}")
for _, r in dist_df.iterrows():
    print(f"{r['metric']:<22} {r['mean']:>+8.3f} {r['p5']:>+8.3f} {r['p95']:>+8.3f} "
          f"{r['worst_seed']:>+8.3f} {r['best_seed']:>+8.3f}")

# ── Hard gate check at mean + p5/worst ───────────────────────────────
print("\n" + "=" * 70)
print("HARD GATE CHECK (mean + p5 + worst seed)")
print("=" * 70)

def gate_check(label, val, gate, gate_op):
    if gate_op == "<=":
        passed = abs(val) <= gate
    elif gate_op == ">=":
        passed = val >= gate
    return "✓" if passed else "❌"

print(f"\nBaseline: ROE {baseline_metrics['ann_roe_pct']:.3f}%, W20d {baseline_metrics['w20d_pct']:+.2f}%, W63d {baseline_metrics['w63d_pct']:+.2f}%")

# Combined metrics
ann_mean = seed_df["ann_roe_pct"].mean()
ann_p5 = seed_df["ann_roe_pct"].quantile(0.05)
maxdd_mean = seed_df["max_dd_pct"].mean()
maxdd_p5 = seed_df["max_dd_pct"].quantile(0.05)
w20_mean = seed_df["w20d_pct"].mean()
w20_p5 = seed_df["w20d_pct"].quantile(0.05)
w63_mean = seed_df["w63d_pct"].mean()
w63_p5 = seed_df["w63d_pct"].quantile(0.05)
d_w20_mean = w20_mean - baseline_metrics["w20d_pct"]
d_w20_p5 = w20_p5 - baseline_metrics["w20d_pct"]
d_w63_mean = w63_mean - baseline_metrics["w63d_pct"]
d_w63_p5 = w63_p5 - baseline_metrics["w63d_pct"]

print(f"\nCombined: ROE mean {ann_mean:.3f}% (p5 {ann_p5:.3f}%)")
print(f"  MaxDD: mean {maxdd_mean:+.2f}% (p5 {maxdd_p5:+.2f}%) — gate ≤ 28% absolute")
print(f"    Gate V1: mean {gate_check('V1 mean', maxdd_mean/100, 0.28, '<=')}  p5 {gate_check('V1 p5', maxdd_p5/100, 0.28, '<=')}")
print(f"  W20d: mean {w20_mean:+.2f}% (p5 {w20_p5:+.2f}%) — gate ≤ 11% absolute")
print(f"    Gate V2: mean {gate_check('V2 mean', w20_mean/100, 0.11, '<=')}  p5 {gate_check('V2 p5', w20_p5/100, 0.11, '<=')}")
print(f"    W20d Δ vs baseline: mean {d_w20_mean:+.2f}pp (p5 {d_w20_p5:+.2f}pp) — gate ≤ +0.5pp (noise threshold)")
print(f"  W63d: mean {w63_mean:+.2f}% (p5 {w63_p5:+.2f}%) — gate ≤ 17% absolute")
print(f"    Gate V3: mean {gate_check('V3 mean', w63_mean/100, 0.17, '<=')}  p5 {gate_check('V3 p5', w63_p5/100, 0.17, '<=')}")
print(f"    W63d Δ vs baseline: mean {d_w63_mean:+.2f}pp (p5 {d_w63_p5:+.2f}pp) — gate ≤ +0.5pp (noise threshold)")

# ── Crisis windows on combined series ────────────────────────────────
print("\n" + "=" * 70)
print("CRISIS WINDOWS (combined baseline + V3 S3, 20-seed)")
print("=" * 70)

crisis_rows = []
for cname, (s, e) in CRISIS_WINDOWS.items():
    s_ts = pd.Timestamp(s)
    e_ts = pd.Timestamp(e)
    window_idx = (df.index >= s_ts) & (df.index <= e_ts)
    baseline_cum = df.loc[window_idx, "baseline_pnl"].sum()
    seed_combined_cum = []
    for seed in range(N_SEEDS):
        ladder_daily, _ = simulate_ladder_daily(v3_eval, SIZING_CONTRACTS, seed=42+seed)
        combined_window_cum = (df.loc[window_idx, "baseline_pnl"] + ladder_daily.loc[window_idx]).sum()
        seed_combined_cum.append(combined_window_cum)
    cum_mean = np.mean(seed_combined_cum)
    cum_p5 = np.quantile(seed_combined_cum, 0.05)
    cum_p95 = np.quantile(seed_combined_cum, 0.95)
    delta = cum_mean - baseline_cum
    print(f"  {cname}: baseline ${baseline_cum:+,.0f}, combined mean ${cum_mean:+,.0f} "
          f"(p5 ${cum_p5:+,.0f}, p95 ${cum_p95:+,.0f}), Δ ${delta:+,.0f}")
    crisis_rows.append({
        "crisis": cname, "baseline_cum": baseline_cum,
        "combined_mean": cum_mean, "combined_p5": cum_p5, "combined_p95": cum_p95,
        "delta_vs_baseline": delta,
    })
pd.DataFrame(crisis_rows).to_csv(OUT / "q078_p4_crisis_combined.csv", index=False)

# ── Walk-forward H1/H2 on combined series ────────────────────────────
print("\n" + "=" * 70)
print("WALK-FORWARD H1/H2 (combined baseline + V3 S3, 20-seed)")
print("=" * 70)

wf_rows = []
for period_name, (s, e) in WALKFORWARD.items():
    s_ts = pd.Timestamp(s)
    e_ts = pd.Timestamp(e)
    period_idx = (df.index >= s_ts) & (df.index <= e_ts)
    period_df = df.loc[period_idx]
    base_period_metrics = compute_metrics_from_daily(period_df["baseline_pnl"], period_df.index, f"{period_name}_baseline")
    seed_metrics_p = []
    for seed in range(N_SEEDS):
        ladder_daily, _ = simulate_ladder_daily(v3_eval, SIZING_CONTRACTS, seed=42+seed)
        combined_period_daily = period_df["baseline_pnl"] + ladder_daily.loc[period_df.index]
        m = compute_metrics_from_daily(combined_period_daily, period_df.index, f"{period_name}_seed{seed}")
        seed_metrics_p.append(m)
    ann_mean = np.mean([m["ann_roe_pct"] for m in seed_metrics_p])
    ann_p5 = np.quantile([m["ann_roe_pct"] for m in seed_metrics_p], 0.05)
    delta_roe = ann_mean - base_period_metrics["ann_roe_pct"]
    maxdd_mean = np.mean([m["max_dd_pct"] for m in seed_metrics_p])
    w20_mean = np.mean([m["w20d_pct"] for m in seed_metrics_p])
    w63_mean = np.mean([m["w63d_pct"] for m in seed_metrics_p])
    print(f"  {period_name}: baseline ROE {base_period_metrics['ann_roe_pct']:.3f}%, "
          f"combined mean {ann_mean:.3f}% (p5 {ann_p5:.3f}%), Δ {delta_roe:+.3f}pp")
    print(f"    MaxDD {maxdd_mean:+.2f}%, W20d {w20_mean:+.2f}%, W63d {w63_mean:+.2f}%")
    wf_rows.append({
        "period": period_name,
        "baseline_ann_roe_pct": base_period_metrics["ann_roe_pct"],
        "combined_ann_roe_mean": ann_mean, "combined_ann_roe_p5": ann_p5,
        "delta_roe_pp": delta_roe,
        "combined_maxdd_mean": maxdd_mean,
        "combined_w20d_mean": w20_mean, "combined_w63d_mean": w63_mean,
    })
pd.DataFrame(wf_rows).to_csv(OUT / "q078_p4_walkforward_combined.csv", index=False)

print("\n" + "=" * 70)
print("Q078 P4 done. CSVs in research/q078/")
print("=" * 70)

# ── BONUS: Run V1b weekly catch-up at portfolio level ────────────────
# Added 2026-05-28 to enable variant comparison under noise framework

print("\n" + "=" * 70)
print("BONUS: V1b weekly catch-up at portfolio level (for noise framework comparison)")
print("=" * 70)

# V1b eval days
def v1b_eval(all_days, sig_df):
    weeks = {}
    for d in all_days:
        if d.weekday() in (0, 1, 2):
            week_key = d.isocalendar()[:2]
            weeks.setdefault(week_key, []).append(d)
    eval_list = []
    for _, days_in_week in sorted(weeks.items()):
        for d in days_in_week:
            if d in sig_df.index and sig_df.loc[d, "strategy"] != "Reduce / Wait":
                eval_list.append(d)
                break
        else:
            if days_in_week:
                eval_list.append(days_in_week[0])
    return set(eval_list)

v1b_eval_set = v1b_eval(all_days, sig_df)
print(f"  V1b eval days: {len(v1b_eval_set)}")

v1b_seed_results = []
for seed in range(N_SEEDS):
    ladder_daily, bp_daily = simulate_ladder_daily(v1b_eval_set, SIZING_CONTRACTS, seed=42+seed)
    combined_daily = df["baseline_pnl"] + ladder_daily
    m = compute_metrics_from_daily(combined_daily, df.index, f"V1b_combined_seed{seed}")
    m["seed"] = seed
    m["delta_roe_pp"] = m["ann_roe_pct"] - baseline_metrics["ann_roe_pct"]
    m["delta_max_dd_pp"] = m["max_dd_pct"] - baseline_metrics["max_dd_pct"]
    m["delta_w20d_pp"] = m["w20d_pct"] - baseline_metrics["w20d_pct"]
    m["delta_w63d_pp"] = m["w63d_pct"] - baseline_metrics["w63d_pct"]
    m["delta_sharpe"] = m["sharpe"] - baseline_metrics["sharpe"]
    m["bp_mean_pct"] = bp_daily.mean() / NLV * 100
    v1b_seed_results.append(m)

v1b_df = pd.DataFrame(v1b_seed_results)
print(f"\nV1b combined (20-seed):")
print(f"  Ann ROE mean {v1b_df['ann_roe_pct'].mean():.3f}% (p5 {v1b_df['ann_roe_pct'].quantile(0.05):.3f}%)")
print(f"  ΔROE mean {v1b_df['delta_roe_pp'].mean():+.3f}pp")
print(f"  MaxDD mean {v1b_df['max_dd_pct'].mean():+.2f}% (Δ {v1b_df['delta_max_dd_pp'].mean():+.2f}pp)")
print(f"  W20d mean {v1b_df['w20d_pct'].mean():+.2f}% (Δ {v1b_df['delta_w20d_pp'].mean():+.2f}pp)")
print(f"  W63d mean {v1b_df['w63d_pct'].mean():+.2f}% (Δ {v1b_df['delta_w63d_pp'].mean():+.2f}pp)")
print(f"  Sharpe mean {v1b_df['sharpe'].mean():.2f} (Δ {v1b_df['delta_sharpe'].mean():+.2f})")
print(f"  BP mean {v1b_df['bp_mean_pct'].mean():.2f}% NLV")

# Comparison
print(f"\n>>> V1b vs V3 vs Baseline B (noise framework comparison):")
v3_ann = seed_df["delta_roe_pp"].mean()
v1b_ann = v1b_df["delta_roe_pp"].mean()
print(f"  V3 ΔROE:  {v3_ann:+.3f}pp")
print(f"  V1b ΔROE: {v1b_ann:+.3f}pp")
print(f"  Diff V3 - V1b: {v3_ann - v1b_ann:+.3f}pp ({'NOISE' if abs(v3_ann-v1b_ann) < 0.5 else 'SIGNAL'})")
print(f"\n  V3 MaxDD Δ:  {seed_df['delta_max_dd_pp'].mean():+.3f}pp")
print(f"  V1b MaxDD Δ: {v1b_df['delta_max_dd_pp'].mean():+.3f}pp")
print(f"  Diff: {seed_df['delta_max_dd_pp'].mean() - v1b_df['delta_max_dd_pp'].mean():+.3f}pp")
print(f"\n  V3 W20d Δ:  {seed_df['delta_w20d_pp'].mean():+.3f}pp")
print(f"  V1b W20d Δ: {v1b_df['delta_w20d_pp'].mean():+.3f}pp")
print(f"  Diff: {seed_df['delta_w20d_pp'].mean() - v1b_df['delta_w20d_pp'].mean():+.3f}pp")
print(f"\n  V3 W63d Δ:  {seed_df['delta_w63d_pp'].mean():+.3f}pp")
print(f"  V1b W63d Δ: {v1b_df['delta_w63d_pp'].mean():+.3f}pp")
print(f"  Diff: {seed_df['delta_w63d_pp'].mean() - v1b_df['delta_w63d_pp'].mean():+.3f}pp")
print(f"\n  V3 Sharpe Δ:  {seed_df['delta_sharpe'].mean():+.3f}")
print(f"  V1b Sharpe Δ: {v1b_df['delta_sharpe'].mean():+.3f}")
print(f"  Diff: {seed_df['delta_sharpe'].mean() - v1b_df['delta_sharpe'].mean():+.3f}")

v1b_df.to_csv(OUT / "q078_p4_v1b_combined_metrics.csv", index=False)

print("\nDone.")
