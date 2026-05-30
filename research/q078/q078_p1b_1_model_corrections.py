"""Q078 P1b-1 — Model corrections (engine PnL + bootstrap + uniform sizing).

Per 2nd Quant G2 PASS (2026-05-27):
  Fix 1 (BCD model):        use engine's BCD trades as empirical PnL distribution
  Fix 2 (Sizing normalize): uniform 1 contract per entry across ALL variants (View 1)
                            (BP-normalized View 2 deferred to P1b-2 sizing sweep)
  Fix 3 (MTM bias):         replace analytical mtm_at with engine actual PnL or
                            bootstrap from engine empirical distribution per strategy

Approach:
  1. Run engine 26y → 373 historical trades with realistic exit_pnl
  2. Build empirical PnL distribution per strategy_key
  3. For each ladder eval-PASS day, prefer engine actual trade if entry_date matches
     within ±2 trading days; else bootstrap from strategy_key distribution
  4. Re-run V1b + V3 + Baseline B at uniform 1-contract sizing
  5. Output corrected metrics

Outputs:
  q078_p1b1_engine_trades.csv             — engine 26y trade log
  q078_p1b1_empirical_pnl_distribution.csv — per-strategy PnL stats
  q078_p1b1_cadence_results_corrected.csv  — corrected variant comparison
  q078_p1b1_entry_timing.csv               — per-entry log with pnl_source
  q078_p1b1_expiry_dispersion.csv          — unchanged from P1a structure
  q078_p1b1_memo.md
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

print("Q078 P1b-1 — Model Corrections", flush=True)
print("=" * 70)

# ── Step 1: Get/cache 26y engine trade log ───────────────────────────
engine_cache = OUT / "_engine_trades_26y_cache.csv"
if engine_cache.exists():
    print(f"\n[Engine] Cache hit: {engine_cache}")
    trades_df = pd.read_csv(engine_cache, parse_dates=["entry_date", "exit_date"])
else:
    print("\n[Engine] Running 26y backtest (~30s)...")
    from backtest.engine import run_backtest
    result = run_backtest(start_date="2000-01-01")
    trades_list = result.trades
    rows = []
    for t in trades_list:
        rows.append({
            "entry_date": pd.Timestamp(t.entry_date),
            "exit_date": pd.Timestamp(t.exit_date),
            "strategy": t.strategy,
            "exit_pnl": float(t.exit_pnl),
            "contracts": float(t.contracts) if t.contracts else 1,
            "total_bp": float(t.total_bp) if t.total_bp else 0,
            "entry_spx": float(t.entry_spx),
            "entry_vix": float(t.entry_vix),
            "dte_at_entry": int(t.dte_at_entry) if t.dte_at_entry else 30,
            "hold_days": int(t.hold_days) if t.hold_days else 0,
            "exit_reason": t.exit_reason,
            "spread_width": float(t.spread_width) if t.spread_width else 0,
        })
    trades_df = pd.DataFrame(rows)
    trades_df.to_csv(engine_cache, index=False)
    print(f"[Engine] Cached {len(trades_df)} trades to {engine_cache}")

print(f"\n[Engine 26y] {len(trades_df)} trades, {trades_df['entry_date'].min().date()} → {trades_df['entry_date'].max().date()}")

# Normalize per-contract PnL to "1 contract equivalent" for uniform comparison
trades_df["pnl_per_contract"] = trades_df["exit_pnl"] / trades_df["contracts"].replace(0, 1)
trades_df["bp_per_contract"] = trades_df["total_bp"] / trades_df["contracts"].replace(0, 1)

# ── Step 2: Build empirical PnL distribution per strategy ────────────
print("\n[Empirical] PnL distribution per strategy (per-contract):")
dist_rows = []
for strat in trades_df["strategy"].unique():
    sub = trades_df[trades_df["strategy"] == strat]
    pnl_per_ct = sub["pnl_per_contract"]
    bp_per_ct = sub["bp_per_contract"]
    print(f"  {strat:<30} n={len(sub):>3}  "
          f"avg ${pnl_per_ct.mean():>+7,.0f}  median ${pnl_per_ct.median():>+7,.0f}  "
          f"worst ${pnl_per_ct.min():>+7,.0f}  best ${pnl_per_ct.max():>+7,.0f}  "
          f"avg_BP ${bp_per_ct.mean():,.0f}")
    dist_rows.append({
        "strategy": strat,
        "n_trades": len(sub),
        "avg_pnl_per_contract": pnl_per_ct.mean(),
        "median_pnl_per_contract": pnl_per_ct.median(),
        "std_pnl_per_contract": pnl_per_ct.std(),
        "worst_pnl_per_contract": pnl_per_ct.min(),
        "best_pnl_per_contract": pnl_per_ct.max(),
        "avg_bp_per_contract": bp_per_ct.mean(),
        "hit_rate_pct": (pnl_per_ct > 0).mean() * 100,
    })
pd.DataFrame(dist_rows).to_csv(OUT / "q078_p1b1_empirical_pnl_distribution.csv", index=False)

# Build lookup: strategy → list of (entry_date, pnl_per_contract, bp_per_contract)
empirical_lookup = {}
for strat in trades_df["strategy"].unique():
    sub = trades_df[trades_df["strategy"] == strat][["entry_date", "pnl_per_contract", "bp_per_contract"]]
    empirical_lookup[strat] = sub.values.tolist()

# Engine entries indexed by date for exact-match preference
engine_by_date = {}
for _, row in trades_df.iterrows():
    d = row["entry_date"]
    engine_by_date.setdefault(d, []).append({
        "strategy": row["strategy"],
        "pnl_per_contract": row["pnl_per_contract"],
        "bp_per_contract": row["bp_per_contract"],
        "exit_date": row["exit_date"],
        "dte": row["dte_at_entry"],
    })

# ── Step 3: Load selector signal history (from P1a cache) ────────────
print("\n[Signal] Loading selector signal history from P1a cache...")
sig_cache = OUT / "_signal_history_cache.csv"
if not sig_cache.exists():
    print("  Cache missing; regenerating via run_signals_only...")
    from backtest.engine import run_signals_only
    sig_history = run_signals_only(start_date="2000-01-01")
    sig_df_tmp = pd.DataFrame(sig_history)
    sig_df_tmp["date"] = pd.to_datetime(sig_df_tmp["date"])
    sig_df_tmp.to_csv(sig_cache, index=False)
    print(f"  Cached {len(sig_df_tmp)} signal days")
sig_df = pd.read_csv(sig_cache, parse_dates=["date"])
sig_df = sig_df.set_index("date").sort_index()
all_days = sig_df.index.tolist()

# Per Q078 P0 R8: ladder uses selector-provided strategy. Strategy name mapping:
# Selector returns "Bull Put Spread" (no _NNB suffix). Engine matches exactly.

# ── Step 4: Cadence eval day generators (same as P1a) ────────────────
def v1b_weekly_catchup_days(all_days, sig_df):
    weeks = {}
    for d in all_days:
        if d.weekday() in (0, 1, 2):
            week_key = d.isocalendar()[:2]
            weeks.setdefault(week_key, []).append(d)
    eval_list = []
    for week_key, days_in_week in sorted(weeks.items()):
        for d in days_in_week:
            if d in sig_df.index and sig_df.loc[d, "strategy"] != "Reduce / Wait":
                eval_list.append(d)
                break
        else:
            if days_in_week:
                eval_list.append(days_in_week[0])
    return eval_list

def v3_daily_cluster_days(sig_df):
    eval_list = []
    last_entry = None
    for d in sig_df.index:
        if last_entry is not None and (d - last_entry).days < 5:
            continue
        if sig_df.loc[d, "strategy"] != "Reduce / Wait":
            eval_list.append(d)
            last_entry = d
    return eval_list

def baseline_b_days(sig_df):
    """Cluster proxy: every ~30 cal days, first PASS day."""
    eval_list = []
    last_entry = None
    for d in sig_df.index:
        if last_entry is not None and (d - last_entry).days < 30:
            continue
        if sig_df.loc[d, "strategy"] != "Reduce / Wait":
            eval_list.append(d)
            last_entry = d
    return eval_list

variants = {
    "V1b_weekly_catchup": v1b_weekly_catchup_days(all_days, sig_df),
    "V3_daily_cluster":   v3_daily_cluster_days(sig_df),
    "BaselineB_cluster":  baseline_b_days(sig_df),
}

for name, days in variants.items():
    print(f"  {name}: {len(days)} eval days")

# ── Step 5: PnL lookup with engine-actual or bootstrap ───────────────
rng = np.random.default_rng(42)

def lookup_pnl(entry_date, strategy_name):
    """Returns (pnl_per_contract, bp_per_contract, source) for the trade.
    Preference: engine exact match (±2 days same strategy) → engine bootstrap.
    """
    # Try exact match ±2 days
    for delta in [0, 1, -1, 2, -2]:
        cand_date = entry_date + pd.Timedelta(days=delta)
        if cand_date in engine_by_date:
            for entry in engine_by_date[cand_date]:
                if entry["strategy"] == strategy_name:
                    return entry["pnl_per_contract"], entry["bp_per_contract"], f"engine_exact_d{delta:+d}"
    # Bootstrap from strategy distribution
    if strategy_name in empirical_lookup and empirical_lookup[strategy_name]:
        pool = empirical_lookup[strategy_name]
        idx = rng.integers(0, len(pool))
        return pool[idx][1], pool[idx][2], "bootstrap"
    return None, None, "no_data"

# ── Step 6: Simulate variants at UNIFORM 1 contract per entry ────────
print("\nSimulating variants at uniform 1 contract per entry (View 1)...")

def simulate_variant_uniform(name, eval_days, sig_df):
    trades = []
    skipped_no_data = 0
    for d in eval_days:
        if d not in sig_df.index:
            continue
        strat = sig_df.loc[d, "strategy"]
        if strat == "Reduce / Wait":
            continue
        pnl, bp, source = lookup_pnl(d, strat)
        if pnl is None:
            skipped_no_data += 1
            continue
        # Approximate expiry date from selector DTE
        if "High Vol" in strat:
            dte = 35
        elif "Diagonal" in strat:
            dte = 45
        else:
            dte = 30
        # For ladder vs baseline_b, same per-entry sizing = 1 contract
        trades.append({
            "variant": name, "entry_date": d, "strategy": strat,
            "pnl": pnl, "bp_per_contract": bp, "pnl_source": source,
            "entry_planned_dte": dte,
            "expiry_proxy": d + pd.Timedelta(days=dte),
        })
    if skipped_no_data > 0:
        print(f"    [warn] {skipped_no_data} {name} entries had no PnL data (skipped)")
    return pd.DataFrame(trades)

results = {}
for name, eval_days in variants.items():
    df = simulate_variant_uniform(name, eval_days, sig_df)
    results[name] = df
    n = len(df)
    cum = df["pnl"].sum() if n else 0
    worst = df["pnl"].min() if n else 0
    hit = (df["pnl"] > 0).mean() * 100 if n else 0
    src_counts = df["pnl_source"].value_counts().to_dict() if n else {}
    print(f"  {name}: {n} trades, cum ${cum:+,.0f}, worst ${worst:+,.0f}, hit {hit:.1f}%")
    print(f"    Sources: {src_counts}")

# ── Step 7: BP utilization + expiry concentration timeline ──────────
print("\nComputing BP utilization + expiry dispersion at uniform 1ct...")

def compute_timeline(trades_df, sample_dates):
    if trades_df.empty:
        return pd.DataFrame(columns=["date", "bp_used", "max_conc_pct", "eff_expiry_count"])
    trades_df = trades_df.copy()
    trades_df["entry_date"] = pd.to_datetime(trades_df["entry_date"])
    trades_df["expiry_proxy"] = pd.to_datetime(trades_df["expiry_proxy"])
    rows = []
    for d in sample_dates:
        active = trades_df[(trades_df["entry_date"] <= d) & (trades_df["expiry_proxy"] > d)]
        if len(active) == 0:
            rows.append({"date": d, "bp_used": 0.0, "max_conc_pct": 0.0, "eff_expiry_count": 0.0})
            continue
        bp_used = active["bp_per_contract"].sum()
        # Group by expiry
        active["expiry_key"] = active["expiry_proxy"].dt.date
        by_exp = active.groupby("expiry_key")["bp_per_contract"].sum()
        total = by_exp.sum()
        if total <= 0:
            rows.append({"date": d, "bp_used": 0.0, "max_conc_pct": 0.0, "eff_expiry_count": 0.0})
            continue
        weights = by_exp / total
        max_conc = float(weights.max() * 100)
        eff_count = float(1.0 / (weights ** 2).sum())
        rows.append({"date": d, "bp_used": float(bp_used),
                     "max_conc_pct": max_conc, "eff_expiry_count": eff_count})
    return pd.DataFrame(rows)

sample_dates = pd.date_range(sig_df.index.min(), sig_df.index.max(), freq="W-MON")

timelines = {}
for name, df in results.items():
    if df.empty:
        timelines[name] = pd.DataFrame()
        continue
    print(f"  {name}: computing {len(sample_dates)} weekly snapshots...")
    tl = compute_timeline(df, sample_dates)
    tl["variant"] = name
    timelines[name] = tl

bp_combined = pd.concat([tl for tl in timelines.values() if not tl.empty], ignore_index=True)
bp_combined.to_csv(OUT / "q078_p1b1_bp_timeline.csv", index=False)

# ── Step 8: Summary metrics ─────────────────────────────────────────
print("\n" + "=" * 70)
print("P1b-1 Cadence Summary (UNIFORM 1-contract, ENGINE-CALIBRATED PnL)")
print("=" * 70)

summary_rows = []
years = (sig_df.index.max() - sig_df.index.min()).days / 365.25

for name, df in results.items():
    n_trades = len(df)
    entries_per_yr = n_trades / years if years else 0
    cum_pnl = df["pnl"].sum() if n_trades else 0
    avg_pnl = df["pnl"].mean() if n_trades else 0
    worst_trade = df["pnl"].min() if n_trades else 0
    best_trade = df["pnl"].max() if n_trades else 0
    hit_rate = (df["pnl"] > 0).mean() * 100 if n_trades else 0
    median_pnl = df["pnl"].median() if n_trades else 0

    # Source mix
    src_engine = (df["pnl_source"].str.startswith("engine_exact").sum()) if n_trades else 0
    src_boot = (df["pnl_source"] == "bootstrap").sum() if n_trades else 0
    engine_match_pct = src_engine / n_trades * 100 if n_trades else 0

    tl = timelines[name]
    if not tl.empty:
        active = tl[tl["bp_used"] > 0]
        bp_mean = active["bp_used"].mean() if len(active) else 0
        bp_p95 = active["bp_used"].quantile(0.95) if len(active) else 0
        max_conc_mean = active["max_conc_pct"].mean() if len(active) else 0
        eff_count_mean = active["eff_expiry_count"].mean() if len(active) else 0
    else:
        bp_mean = bp_p95 = max_conc_mean = eff_count_mean = 0

    # Selector PASS rate
    eval_days = variants[name]
    eval_in_sig = [d for d in eval_days if d in sig_df.index]
    n_pass = sum(sig_df.loc[d, "strategy"] != "Reduce / Wait" for d in eval_in_sig)
    pass_rate = n_pass / len(eval_in_sig) * 100 if eval_in_sig else 0

    summary_rows.append({
        "variant": name,
        "n_eval_days": len(eval_days),
        "selector_pass_rate_pct": pass_rate,
        "n_trades": n_trades,
        "entries_per_yr": entries_per_yr,
        "cum_pnl_usd": cum_pnl,
        "ann_pnl_usd": cum_pnl / years if years else 0,
        "ann_pnl_pct_nlv": (cum_pnl / years / NLV * 100) if years else 0,
        "avg_pnl_per_trade": avg_pnl,
        "median_pnl_per_trade": median_pnl,
        "worst_trade_usd": worst_trade,
        "best_trade_usd": best_trade,
        "hit_rate_pct": hit_rate,
        "engine_match_pct": engine_match_pct,
        "bp_mean_usd_per_contract": bp_mean,
        "bp_p95_usd_per_contract": bp_p95,
        "max_expiry_concentration_pct": max_conc_mean,
        "effective_expiry_count_mean": eff_count_mean,
    })

    print(f"\n[{name}]")
    print(f"  Eval: {len(eval_days)} days ({pass_rate:.1f}% PASS)")
    print(f"  Trades: {n_trades} ({entries_per_yr:.1f}/yr)  Engine match: {engine_match_pct:.0f}%")
    print(f"  PnL: cum ${cum_pnl:+,.0f}  ann ${cum_pnl/years:+,.0f}/yr ({cum_pnl/years/NLV*100:+.3f}% NLV)")
    print(f"       avg ${avg_pnl:+,.0f}/trade  median ${median_pnl:+,.0f}  worst ${worst_trade:+,.0f}  hit {hit_rate:.1f}%")
    print(f"  BP/ct: mean ${bp_mean:,.0f}  p95 ${bp_p95:,.0f}")
    print(f"  Expiry: max_conc {max_conc_mean:.1f}%  eff_count {eff_count_mean:.2f}")

pd.DataFrame(summary_rows).to_csv(OUT / "q078_p1b1_cadence_results_corrected.csv", index=False)

# Entry log
entry_rows = []
for name, df in results.items():
    for _, t in df.iterrows():
        entry_rows.append({
            "variant": name, "entry_date": t["entry_date"],
            "strategy": t["strategy"], "pnl": t["pnl"],
            "bp_per_contract": t["bp_per_contract"],
            "pnl_source": t["pnl_source"],
            "expiry_proxy": t["expiry_proxy"],
        })
pd.DataFrame(entry_rows).to_csv(OUT / "q078_p1b1_entry_timing.csv", index=False)

# Dispersion summary
dispersion_rows = []
for name, tl in timelines.items():
    if tl.empty:
        continue
    nonzero = tl[tl["max_conc_pct"] > 0]
    if len(nonzero) == 0:
        continue
    dispersion_rows.append({
        "variant": name,
        "active_periods": len(nonzero),
        "mean_max_concentration_pct": nonzero["max_conc_pct"].mean(),
        "p95_max_concentration_pct": nonzero["max_conc_pct"].quantile(0.95),
        "mean_effective_expiry_count": nonzero["eff_expiry_count"].mean(),
        "median_effective_expiry_count": nonzero["eff_expiry_count"].median(),
        "max_eff_expiry_count": nonzero["eff_expiry_count"].max(),
    })
pd.DataFrame(dispersion_rows).to_csv(OUT / "q078_p1b1_expiry_dispersion.csv", index=False)

# Save engine trade log (full)
trades_df.to_csv(OUT / "q078_p1b1_engine_trades.csv", index=False)

# ── Step 9: Comparison vs Baseline B ─────────────────────────────────
print("\n" + "=" * 70)
print("UNIFORM 1-contract comparison vs Baseline B (engine-calibrated)")
print("=" * 70)
base = next((r for r in summary_rows if r["variant"] == "BaselineB_cluster"), None)
if base:
    print(f"\nBaseline B (1 contract/entry): {base['n_trades']} trades, "
          f"cum ${base['cum_pnl_usd']:+,.0f} ({base['ann_pnl_pct_nlv']:+.3f}% NLV/yr), "
          f"max_conc {base['max_expiry_concentration_pct']:.1f}%, "
          f"eff_count {base['effective_expiry_count_mean']:.2f}")
    print()
    for r in summary_rows:
        if r["variant"] == "BaselineB_cluster":
            continue
        d_pnl = r["cum_pnl_usd"] - base["cum_pnl_usd"]
        d_ann_pct = r["ann_pnl_pct_nlv"] - base["ann_pnl_pct_nlv"]
        d_conc = r["max_expiry_concentration_pct"] - base["max_expiry_concentration_pct"]
        d_eff = r["effective_expiry_count_mean"] - base["effective_expiry_count_mean"]
        print(f"{r['variant']:<22} ΔPnL ${d_pnl:>+10,.0f}  Δann {d_ann_pct:+.3f}pp  "
              f"ΔMaxConc {d_conc:+.1f}pp  ΔEffCount {d_eff:+.2f}")

print("\n" + "=" * 70)
print("Q078 P1b-1 done. CSVs in research/q078/")
print("=" * 70)
print("\nNotes:")
print("  - UNIFORM 1-contract sizing across ALL variants (View 1 per 2nd Quant G2)")
print("  - PnL uses engine actual where date match available; bootstrap elsewhere")
print("  - View 2 (BP-normalized) deferred to P1b-2 sizing sweep")
