"""Q078 P3 — Crisis forensic + walk-forward + bias correction.

Per PM Option B (2026-05-28): P3 before G3.

Three deliverables:
  1. Crisis window analysis — 5 named windows × V3 S3 L2 (primary candidate)
     DotCom 2000-03, PreGFC 2007-07, Vol 2018-02, COVID 2020-02, Bear 2022-01

  2. Walk-forward H1/H2 — split 2000-2012 vs 2013-2026 to check regime over-fit

  3. Bias correction via stratified bootstrap — pool engine trades by
     (strategy, year_bucket) instead of pure (strategy). Closer match to
     ladder eval days' regime.

Primary focus: V3 S3 Layer 2 (per P2R Quant prior). Baseline B for comparison.
Sizing: S3 (3 contracts).
Noise threshold: < 0.5pp = noise (per feedback_noise_threshold 2026-05-28).

Outputs:
  q078_p3_crisis_windows.csv
  q078_p3_walkforward.csv
  q078_p3_stratified_vs_unstratified.csv
  q078_p3_memo.md
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

CONCURRENCY_CAP = {
    "Bull Put Spread": 1, "Bull Put Spread (High Vol)": 1,
    "Iron Condor": 1, "Iron Condor (High Vol)": 2,
    "Bear Call Spread (High Vol)": 1, "Bull Call Diagonal": 1,
}

STRATEGY_DTE = {
    "Bull Put Spread": 30, "Bull Put Spread (High Vol)": 35,
    "Iron Condor": 30, "Iron Condor (High Vol)": 35,
    "Bear Call Spread (High Vol)": 35, "Bull Call Diagonal": 45,
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

print("Q078 P3 — Crisis forensic + Walk-forward + Bias correction", flush=True)
print("=" * 70)

# ── Load data ────────────────────────────────────────────────────────
print("\nLoading engine trades + signal history...")
trades_df = pd.read_csv(OUT / "_engine_trades_26y_cache.csv", parse_dates=["entry_date"])
trades_df["pnl_per_ct"] = trades_df["exit_pnl"] / trades_df["contracts"].replace(0, 1)
trades_df["max_loss_per_ct"] = trades_df["total_bp"] / trades_df["contracts"].replace(0, 1)
trades_df["spx_scale"] = SPX_TODAY / trades_df["entry_spx"]
trades_df["pnl_today_per_ct"] = trades_df["pnl_per_ct"] * trades_df["spx_scale"]
trades_df["max_loss_today_per_ct"] = trades_df["max_loss_per_ct"] * trades_df["spx_scale"]
trades_df["year"] = trades_df["entry_date"].dt.year

# Year buckets for stratified bootstrap
def year_bucket(y):
    if y < 2010: return "pre_2010"
    if y < 2018: return "2010_2017"
    return "2018_plus"

trades_df["year_bucket"] = trades_df["year"].apply(year_bucket)

# Per-strategy pool
pool_by_strat = {}
for strat in trades_df["strategy"].unique():
    sub = trades_df[trades_df["strategy"] == strat]
    pool_by_strat[strat] = list(zip(
        sub["pnl_today_per_ct"].tolist(),
        sub["max_loss_today_per_ct"].tolist(),
    ))

# Stratified pool by (strategy, year_bucket)
pool_strat_year = {}
for strat in trades_df["strategy"].unique():
    for yb in ["pre_2010", "2010_2017", "2018_plus"]:
        sub = trades_df[(trades_df["strategy"] == strat) & (trades_df["year_bucket"] == yb)]
        pool_strat_year[(strat, yb)] = list(zip(
            sub["pnl_today_per_ct"].tolist(),
            sub["max_loss_today_per_ct"].tolist(),
        ))
        if len(sub) > 0:
            print(f"  {strat:<32} {yb:<12} n={len(sub):>3}")

engine_by_date = {}
for _, row in trades_df.iterrows():
    d = row["entry_date"]
    engine_by_date.setdefault(d, []).append({
        "strategy": row["strategy"],
        "pnl_today_per_ct": row["pnl_today_per_ct"],
        "max_loss_today_per_ct": row["max_loss_today_per_ct"],
    })

sig_df = pd.read_csv(OUT / "_signal_history_cache.csv", parse_dates=["date"])
sig_df = sig_df.set_index("date").sort_index()
all_days = sig_df.index.tolist()

# ── Cadence eval days (V3 + Baseline B only) ─────────────────────────
def v3_eval(sig_df):
    eval_list = []
    last = None
    for d in sig_df.index:
        if last is not None and (d - last).days < 5:
            continue
        if sig_df.loc[d, "strategy"] != "Reduce / Wait":
            eval_list.append(d)
            last = d
    return set(eval_list)

def baseline_b_eval(sig_df):
    eval_list = []
    last = None
    for d in sig_df.index:
        if last is not None and (d - last).days < 30:
            continue
        if sig_df.loc[d, "strategy"] != "Reduce / Wait":
            eval_list.append(d)
            last = d
    return set(eval_list)

# ── PnL lookup (stratified or not) ───────────────────────────────────
def lookup_pnl_unstratified(entry_date, strategy_name, rng):
    for delta in [0, 1, -1, 2, -2]:
        cand = entry_date + pd.Timedelta(days=delta)
        if cand in engine_by_date:
            for e in engine_by_date[cand]:
                if e["strategy"] == strategy_name:
                    return e["pnl_today_per_ct"], e["max_loss_today_per_ct"]
    if strategy_name in pool_by_strat and pool_by_strat[strategy_name]:
        pool = pool_by_strat[strategy_name]
        idx = rng.integers(0, len(pool))
        return pool[idx]
    return None, None

def lookup_pnl_stratified(entry_date, strategy_name, rng):
    # Exact match preference
    for delta in [0, 1, -1, 2, -2]:
        cand = entry_date + pd.Timedelta(days=delta)
        if cand in engine_by_date:
            for e in engine_by_date[cand]:
                if e["strategy"] == strategy_name:
                    return e["pnl_today_per_ct"], e["max_loss_today_per_ct"]
    # Stratified by year bucket
    yb = year_bucket(entry_date.year)
    key = (strategy_name, yb)
    if key in pool_strat_year and pool_strat_year[key]:
        pool = pool_strat_year[key]
        idx = rng.integers(0, len(pool))
        return pool[idx]
    # Fallback to unstratified
    if strategy_name in pool_by_strat and pool_by_strat[strategy_name]:
        pool = pool_by_strat[strategy_name]
        idx = rng.integers(0, len(pool))
        return pool[idx]
    return None, None

# ── Simulator ────────────────────────────────────────────────────────
def simulate(eval_set, sig_df, n_contracts, production_gates, seed,
              date_range=None, stratified=False):
    rng = np.random.default_rng(seed)
    positions = []
    completed = []
    lookup_fn = lookup_pnl_stratified if stratified else lookup_pnl_unstratified

    days_to_iterate = sig_df.index
    if date_range:
        s, e = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        days_to_iterate = sig_df[(sig_df.index >= s) & (sig_df.index <= e)].index

    for d in days_to_iterate:
        # Process exits
        still = []
        for p in positions:
            if p["exit"] <= d:
                completed.append(p)
            else:
                still.append(p)
        positions = still

        if d not in eval_set:
            continue
        strat = sig_df.loc[d, "strategy"]
        if strat == "Reduce / Wait":
            continue

        if production_gates:
            cap = CONCURRENCY_CAP.get(strat, 1)
            same_strat = sum(1 for p in positions if p["strategy"] == strat)
            if same_strat >= cap:
                continue
            current_bp = sum(p["max_loss"] for p in positions)
            new_max_loss = pool_by_strat.get(strat, [(0, 0)])[0][1] * n_contracts
            if (current_bp + new_max_loss) / NLV > BP_CEILING_NORMAL:
                continue

        pnl_per_ct, max_loss_per_ct = lookup_fn(d, strat, rng)
        if pnl_per_ct is None:
            continue

        exit_d = d + pd.Timedelta(days=AVG_HOLD_DAYS)
        positions.append({
            "entry": d, "exit": exit_d, "strategy": strat,
            "pnl": pnl_per_ct * n_contracts,
            "max_loss": max_loss_per_ct * n_contracts,
        })

    for p in positions:
        completed.append(p)
    return completed

def compute_metrics_for_period(trades, sig_df, date_range, label):
    if not trades:
        return None
    s, e = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    period_days = sig_df[(sig_df.index >= s) & (sig_df.index <= e)]
    years = (period_days.index.max() - period_days.index.min()).days / 365.25 if len(period_days) > 0 else 1

    cum = sum(t["pnl"] for t in trades)
    worst = min(t["pnl"] for t in trades)
    hit = sum(1 for t in trades if t["pnl"] > 0) / len(trades) * 100
    ann_pnl = cum / years
    ann_pct = ann_pnl / NLV * 100

    # Daily PnL (linear distribution)
    daily = pd.Series(0.0, index=period_days.index)
    for t in trades:
        hold = pd.date_range(t["entry"], t["exit"], freq="B")
        hold = [d for d in hold if d in daily.index]
        if hold:
            per_day = t["pnl"] / len(hold)
            for d in hold:
                daily.loc[d] += per_day

    if len(daily) > 0:
        eq = NLV + daily.cumsum()
        running_max = eq.cummax()
        dd = (eq - running_max) / running_max
        max_dd = dd.min()
        ret = daily / eq.shift(1).fillna(NLV)
        w20 = ret.rolling(20).sum().min()
        w63 = ret.rolling(63).sum().min()
    else:
        max_dd = w20 = w63 = 0

    return {
        "label": label, "n_trades": len(trades),
        "cum_pnl": cum, "ann_pnl_usd": ann_pnl, "ann_pnl_pct_nlv": ann_pct,
        "worst_trade_usd": worst,
        "max_dd_pct": max_dd * 100, "w20d_pct": w20 * 100, "w63d_pct": w63 * 100,
        "hit_rate_pct": hit, "years": years,
    }

# ── Step 1: Crisis window analysis (V3 vs Baseline B) ────────────────
print("\n" + "=" * 70)
print("Step 1: Crisis window analysis (V3 S3 L2 vs Baseline B S3 L2)")
print("=" * 70)

v3_eval_full = v3_eval(sig_df)
bb_eval_full = baseline_b_eval(sig_df)

crisis_rows = []
for crisis_name, (s, e) in CRISIS_WINDOWS.items():
    print(f"\n[{crisis_name}: {s} → {e}]")
    s_ts = pd.Timestamp(s)
    e_ts = pd.Timestamp(e)
    for variant_name, eval_set in [("V3_S3", v3_eval_full), ("BaselineB_S3", bb_eval_full)]:
        # Aggregate across 20 seeds
        seed_metrics = []
        for seed in range(N_SEEDS):
            trades = simulate(eval_set, sig_df, SIZING_CONTRACTS,
                              production_gates=True, seed=42+seed,
                              date_range=(s, e), stratified=False)
            m = compute_metrics_for_period(trades, sig_df, (s, e), f"{crisis_name}_{variant_name}")
            if m:
                seed_metrics.append(m)
        if not seed_metrics:
            continue
        cum_mean = np.mean([m["cum_pnl"] for m in seed_metrics])
        cum_p5 = np.quantile([m["cum_pnl"] for m in seed_metrics], 0.05)
        cum_p95 = np.quantile([m["cum_pnl"] for m in seed_metrics], 0.95)
        ntrades_mean = np.mean([m["n_trades"] for m in seed_metrics])
        worst_mean = np.mean([m["worst_trade_usd"] for m in seed_metrics])
        print(f"  {variant_name}: n_trades avg {ntrades_mean:.1f}, "
              f"cum PnL mean ${cum_mean:+,.0f} (CI [${cum_p5:+,.0f}, ${cum_p95:+,.0f}]), "
              f"worst ${worst_mean:+,.0f}")
        crisis_rows.append({
            "crisis": crisis_name, "variant": variant_name,
            "n_trades_avg": ntrades_mean,
            "cum_pnl_mean": cum_mean, "cum_pnl_p5": cum_p5, "cum_pnl_p95": cum_p95,
            "worst_trade_mean": worst_mean,
        })
pd.DataFrame(crisis_rows).to_csv(OUT / "q078_p3_crisis_windows.csv", index=False)

# ── Step 2: Walk-forward H1/H2 ───────────────────────────────────────
print("\n" + "=" * 70)
print("Step 2: Walk-forward H1 vs H2")
print("=" * 70)

wf_rows = []
for period_name, (s, e) in WALKFORWARD.items():
    print(f"\n[{period_name}: {s} → {e}]")
    s_ts = pd.Timestamp(s)
    e_ts = pd.Timestamp(e)
    # Filter eval days to period
    for variant_name, eval_set_full in [("V3_S3", v3_eval_full), ("BaselineB_S3", bb_eval_full)]:
        eval_set = {d for d in eval_set_full if s_ts <= d <= e_ts}
        seed_metrics = []
        for seed in range(N_SEEDS):
            trades = simulate(eval_set, sig_df, SIZING_CONTRACTS,
                              production_gates=True, seed=42+seed,
                              date_range=(s, e), stratified=False)
            m = compute_metrics_for_period(trades, sig_df, (s, e), f"{period_name}_{variant_name}")
            if m:
                seed_metrics.append(m)
        if not seed_metrics:
            continue
        ann_mean = np.mean([m["ann_pnl_pct_nlv"] for m in seed_metrics])
        ann_p5 = np.quantile([m["ann_pnl_pct_nlv"] for m in seed_metrics], 0.05)
        ann_p95 = np.quantile([m["ann_pnl_pct_nlv"] for m in seed_metrics], 0.95)
        w20_mean = np.mean([m["w20d_pct"] for m in seed_metrics])
        w63_mean = np.mean([m["w63d_pct"] for m in seed_metrics])
        maxdd_mean = np.mean([m["max_dd_pct"] for m in seed_metrics])
        n_mean = np.mean([m["n_trades"] for m in seed_metrics])
        print(f"  {variant_name}: n {n_mean:.0f}, "
              f"ann ROE {ann_mean:+.2f}% [{ann_p5:+.2f}, {ann_p95:+.2f}], "
              f"MaxDD {maxdd_mean:+.2f}%, W20d {w20_mean:+.2f}%, W63d {w63_mean:+.2f}%")
        wf_rows.append({
            "period": period_name, "variant": variant_name,
            "n_trades_avg": n_mean,
            "ann_pnl_pct_mean": ann_mean, "ann_pnl_pct_p5": ann_p5, "ann_pnl_pct_p95": ann_p95,
            "max_dd_pct": maxdd_mean, "w20d_pct": w20_mean, "w63d_pct": w63_mean,
        })
pd.DataFrame(wf_rows).to_csv(OUT / "q078_p3_walkforward.csv", index=False)

# ── Step 3: Stratified vs unstratified bootstrap ─────────────────────
print("\n" + "=" * 70)
print("Step 3: Bias correction (stratified vs unstratified bootstrap)")
print("=" * 70)

strat_rows = []
for variant_name, eval_set in [("V3_S3", v3_eval_full), ("BaselineB_S3", bb_eval_full)]:
    print(f"\n[{variant_name}]")
    for strat_mode in [False, True]:
        seed_metrics = []
        for seed in range(N_SEEDS):
            trades = simulate(eval_set, sig_df, SIZING_CONTRACTS,
                              production_gates=True, seed=42+seed,
                              date_range=None, stratified=strat_mode)
            m = compute_metrics_for_period(trades, sig_df,
                                             ("2000-01-01", "2026-12-31"), variant_name)
            if m:
                seed_metrics.append(m)
        if not seed_metrics:
            continue
        ann_mean = np.mean([m["ann_pnl_pct_nlv"] for m in seed_metrics])
        ann_p5 = np.quantile([m["ann_pnl_pct_nlv"] for m in seed_metrics], 0.05)
        ann_p95 = np.quantile([m["ann_pnl_pct_nlv"] for m in seed_metrics], 0.95)
        worst_mean = np.mean([m["worst_trade_usd"] for m in seed_metrics])
        n_mean = np.mean([m["n_trades"] for m in seed_metrics])
        mode_label = "stratified" if strat_mode else "unstratified"
        print(f"  {mode_label}: n {n_mean:.0f}, ann ROE {ann_mean:+.2f}% "
              f"[{ann_p5:+.2f}, {ann_p95:+.2f}], worst trade ${worst_mean:+,.0f}")
        strat_rows.append({
            "variant": variant_name, "mode": mode_label,
            "n_trades_avg": n_mean,
            "ann_pnl_pct_mean": ann_mean,
            "ann_pnl_pct_p5": ann_p5, "ann_pnl_pct_p95": ann_p95,
            "worst_trade_mean": worst_mean,
        })
pd.DataFrame(strat_rows).to_csv(OUT / "q078_p3_stratified_vs_unstratified.csv", index=False)

print("\n" + "=" * 70)
print("Q078 P3 done. CSVs in research/q078/")
print("=" * 70)
