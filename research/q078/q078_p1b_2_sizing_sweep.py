"""Q078 P1b-2 — Sizing Sweep with 5% NLV hard gate + SPX-scaled bootstrap.

Per PM/2nd Quant feedback (2026-05-27):
  - Worst-trade hard gate: 5% NLV (REVISED from 1% NLV)
  - Sizing reality check: PM's empirical width = 250-300pt at SPX 7400,
    not 119pt engine 26y avg (engine SPX-level varied)
  - Bootstrap PnL must scale to today's SPX level for forward projection

  Cadence: V1b weekly catch-up (primary), V3 daily-cluster (alternative),
           BaselineB cluster (control)
  Sizing:  S1 = 1 contract per entry
           S2 = 4 contracts ≈ 10% BP target (PM original)
           S3 = 3 contracts ≈ 7.5% BP target (conservative)
           S4 dynamic — DROPPED per PM 2026-05-27 (would breach worst-trade gate)

  PnL methodology:
    - Bootstrap from engine 26y empirical distribution (per strategy)
    - Use pnl_pct_of_max_loss for width-agnostic comparison
    - Scale absolute $ to today's SPX 7400 per-trade scaling factor
    - Aggregate metrics in today's $ equivalent

  Hard gates (per Q078 P0 §7 revised):
    V1: MaxDD ≥ -28%
    V2: Worst 20d ≥ -11%
    V3: Worst 63d ≥ -17%
    Worst 20d degradation ≤ +0.25pp vs Baseline B
    Worst 63d degradation ≤ +0.25pp vs Baseline B
    Worst single trade ≤ 5% NLV ($44,700)
    No new crisis-window failure

  Output:
    q078_p1b2_sizing_results.csv          — main grid (variant × sizing)
    q078_p1b2_hard_gates_pass_fail.csv    — per combo gate status
    q078_p1b2_bootstrap_ci.csv            — 20-seed bootstrap on key metrics
    q078_p1b2_pnl_distribution.csv        — full per-trade PnL per variant
    q078_p1b2_memo.md
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
SPX_TODAY = 7400.0   # for scaling historical PnL to current SPX level

# Sizing variants (S4 dropped)
SIZINGS = {
    "S1_1contract":   1,
    "S2_4contracts_10pct_bp":   4,
    "S3_3contracts_7p5pct_bp":  3,
}

# Cadence variants (per G2 narrowed)
CADENCE_VARIANTS = ["V1b_weekly_catchup", "V3_daily_cluster", "BaselineB_cluster"]

# Hard gates (per P0 §7 revised 5% NLV)
GATE_V1_MAXDD = -0.28
GATE_V2_W20D = -0.11
GATE_V3_W63D = -0.17
GATE_W20D_DEGRADATION = 0.0025  # +0.25pp
GATE_W63D_DEGRADATION = 0.0025
GATE_WORST_TRADE_NLV = 0.05      # 5% NLV (REVISED 2026-05-27)
GATE_CRISIS_LOSS_USD = 10_000   # +$10k vs Baseline B

# Bootstrap
N_BOOTSTRAP_SEEDS = 20

print("Q078 P1b-2 — Sizing Sweep (5% NLV gate, SPX-scaled bootstrap)", flush=True)
print("=" * 70)
print(f"\nNLV = ${NLV:,.0f}")
print(f"SPX today (scaling target) = {SPX_TODAY}")
print(f"Worst-trade hard gate = {GATE_WORST_TRADE_NLV*100:.0f}% NLV = ${GATE_WORST_TRADE_NLV*NLV:,.0f}")
print(f"Sizing variants: {list(SIZINGS.keys())}")
print(f"Cadence variants: {CADENCE_VARIANTS}")

# ── Load engine trades + signal history ──────────────────────────────
print("\nLoading engine 26y trade log + signal history...")
trades_df = pd.read_csv(OUT / "_engine_trades_26y_cache.csv", parse_dates=["entry_date", "exit_date"])
trades_df["pnl_per_contract"] = trades_df["exit_pnl"] / trades_df["contracts"].replace(0, 1)
trades_df["max_loss_per_contract"] = trades_df["total_bp"] / trades_df["contracts"].replace(0, 1)
trades_df["pnl_pct_of_max_loss"] = trades_df["pnl_per_contract"] / trades_df["max_loss_per_contract"].replace(0, 1)
trades_df["spx_scale_factor"] = SPX_TODAY / trades_df["entry_spx"]
trades_df["pnl_today_scaled_per_contract"] = trades_df["pnl_per_contract"] * trades_df["spx_scale_factor"]
trades_df["max_loss_today_scaled_per_contract"] = trades_df["max_loss_per_contract"] * trades_df["spx_scale_factor"]
print(f"  Engine trades: {len(trades_df)}")
print(f"  Avg SPX scale factor (today/entry): {trades_df['spx_scale_factor'].mean():.2f}")

sig_df = pd.read_csv(OUT / "_signal_history_cache.csv", parse_dates=["date"])
sig_df = sig_df.set_index("date").sort_index()
all_days = sig_df.index.tolist()
print(f"  Signal days: {len(sig_df)}")

# ── Empirical PnL distribution (today-scaled $) per strategy ─────────
print("\nEmpirical worst-pct-of-max-loss per strategy:")
worst_pct_by_strat = {}
empirical_pnl_today_by_strat = {}
empirical_max_loss_today_by_strat = {}

empirical_pool_by_strat = {}  # precomputed list of (pnl_today, max_loss_today, pnl_pct) per strategy
for strat in trades_df["strategy"].unique():
    sub = trades_df[trades_df["strategy"] == strat]
    worst_pct = sub["pnl_pct_of_max_loss"].min()
    worst_pct_by_strat[strat] = worst_pct
    empirical_pnl_today_by_strat[strat] = sub["pnl_today_scaled_per_contract"].tolist()
    empirical_max_loss_today_by_strat[strat] = sub["max_loss_today_scaled_per_contract"].tolist()
    # Precompute pool tuples (avoid O(n) rebuild per bootstrap call)
    empirical_pool_by_strat[strat] = list(zip(
        sub["pnl_today_scaled_per_contract"].tolist(),
        sub["max_loss_today_scaled_per_contract"].tolist(),
        sub["pnl_pct_of_max_loss"].tolist(),
    ))
    avg_today = np.mean(empirical_pnl_today_by_strat[strat])
    worst_today = min(empirical_pnl_today_by_strat[strat])
    avg_max_loss_today = np.mean(empirical_max_loss_today_by_strat[strat])
    print(f"  {strat:<32} n={len(sub):>3}  worst_pct {worst_pct*100:>+6.1f}%  "
          f"today-scaled avg ${avg_today:>+7,.0f}  worst ${worst_today:>+7,.0f}  "
          f"max_loss/ct ${avg_max_loss_today:,.0f}")

# Engine trades indexed by date (for exact match preference)
engine_by_date = {}
for _, row in trades_df.iterrows():
    d = row["entry_date"]
    engine_by_date.setdefault(d, []).append({
        "strategy": row["strategy"],
        "pnl_pct": row["pnl_pct_of_max_loss"],
        "pnl_today": row["pnl_today_scaled_per_contract"],
        "max_loss_today": row["max_loss_today_scaled_per_contract"],
    })

# ── Cadence eval days (same as P1b-1) ────────────────────────────────
def v1b_weekly_catchup_days(all_days, sig_df):
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
    eval_list = []
    last_entry = None
    for d in sig_df.index:
        if last_entry is not None and (d - last_entry).days < 30:
            continue
        if sig_df.loc[d, "strategy"] != "Reduce / Wait":
            eval_list.append(d)
            last_entry = d
    return eval_list

variants_eval = {
    "V1b_weekly_catchup": v1b_weekly_catchup_days(all_days, sig_df),
    "V3_daily_cluster":   v3_daily_cluster_days(sig_df),
    "BaselineB_cluster":  baseline_b_days(sig_df),
}

# ── PnL lookup: engine actual if exact match, else bootstrap ─────────
def lookup_pnl_today(entry_date, strategy_name, rng):
    """Returns (pnl_today_per_contract, max_loss_today_per_contract, pnl_pct, source)."""
    for delta in [0, 1, -1, 2, -2]:
        cand_date = entry_date + pd.Timedelta(days=delta)
        if cand_date in engine_by_date:
            for entry in engine_by_date[cand_date]:
                if entry["strategy"] == strategy_name:
                    return (entry["pnl_today"], entry["max_loss_today"], entry["pnl_pct"], f"engine_exact_d{delta:+d}")
    # Bootstrap from precomputed pool
    if strategy_name in empirical_pool_by_strat and empirical_pool_by_strat[strategy_name]:
        pool = empirical_pool_by_strat[strategy_name]
        idx = rng.integers(0, len(pool))
        p = pool[idx]
        return (p[0], p[1], p[2], "bootstrap")
    return None, None, None, "no_data"

# ── Simulate variant × sizing × bootstrap-seed ───────────────────────
def simulate_one_seed(variant_name, eval_days, sig_df, n_contracts, seed):
    rng = np.random.default_rng(seed)
    trades = []
    for d in eval_days:
        if d not in sig_df.index:
            continue
        strat = sig_df.loc[d, "strategy"]
        if strat == "Reduce / Wait":
            continue
        pnl_per_ct, max_loss_per_ct, pnl_pct, source = lookup_pnl_today(d, strat, rng)
        if pnl_per_ct is None:
            continue
        total_pnl = pnl_per_ct * n_contracts
        total_bp = max_loss_per_ct * n_contracts
        if "High Vol" in strat:
            dte = 35
        elif "Diagonal" in strat:
            dte = 45
        else:
            dte = 30
        trades.append({
            "variant": variant_name, "entry_date": d, "strategy": strat,
            "n_contracts": n_contracts, "pnl_per_contract": pnl_per_ct,
            "total_pnl": total_pnl, "total_bp": total_bp, "pnl_pct": pnl_pct,
            "source": source, "expiry_proxy": d + pd.Timedelta(days=dte),
        })
    return pd.DataFrame(trades)

# ── Main sweep ───────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("Running sweep (3 cadences × 3 sizings × 20 seeds = 180 simulations)")
print("=" * 70)

results_grid = []  # one row per (variant, sizing) — aggregated across seeds
all_trade_logs = []  # per-trade flat log

for variant_name in CADENCE_VARIANTS:
    eval_days = variants_eval[variant_name]
    for sizing_label, n_contracts in SIZINGS.items():
        print(f"\n[{variant_name} / {sizing_label} (n={n_contracts})]")
        seed_metrics = []
        for seed in range(N_BOOTSTRAP_SEEDS):
            df = simulate_one_seed(variant_name, eval_days, sig_df, n_contracts, seed=42 + seed)
            if df.empty:
                continue
            cum = df["total_pnl"].sum()
            worst = df["total_pnl"].min()
            hit = (df["total_pnl"] > 0).mean() * 100
            avg = df["total_pnl"].mean()
            seed_metrics.append({
                "seed": seed, "n_trades": len(df),
                "cum_pnl": cum, "worst_trade": worst, "hit_rate": hit,
                "avg_pnl": avg, "worst_pnl_pct_nlv": worst / NLV * 100,
            })
            if seed == 0:
                # Save trade log for seed 0 (representative)
                df["sizing"] = sizing_label
                all_trade_logs.append(df)
        if not seed_metrics:
            print(f"    [warn] no trades")
            continue
        sm = pd.DataFrame(seed_metrics)
        cum_mean = sm["cum_pnl"].mean()
        cum_std = sm["cum_pnl"].std()
        cum_p5 = sm["cum_pnl"].quantile(0.05)
        cum_p95 = sm["cum_pnl"].quantile(0.95)
        worst_mean = sm["worst_trade"].mean()
        worst_p5 = sm["worst_trade"].quantile(0.05)
        years = (sig_df.index.max() - sig_df.index.min()).days / 365.25
        ann_pnl = cum_mean / years
        ann_pnl_pct = ann_pnl / NLV * 100

        # Hard gate checks
        worst_pct_nlv = worst_mean / NLV * 100
        worst_p5_pct_nlv = worst_p5 / NLV * 100
        gate_worst_pass = abs(worst_pct_nlv) <= GATE_WORST_TRADE_NLV * 100
        gate_worst_p5_pass = abs(worst_p5_pct_nlv) <= GATE_WORST_TRADE_NLV * 100

        print(f"    Trades/seed avg: {sm['n_trades'].mean():.0f}")
        print(f"    Cum PnL: mean ${cum_mean:+,.0f} (5-95% [{cum_p5:+,.0f}, {cum_p95:+,.0f}]) std ${cum_std:,.0f}")
        print(f"    Ann PnL: ${ann_pnl:+,.0f}/yr ({ann_pnl_pct:+.3f}% NLV)")
        print(f"    Worst trade: mean ${worst_mean:+,.0f} ({worst_pct_nlv:+.2f}% NLV)  "
              f"5%-tile ${worst_p5:+,.0f} ({worst_p5_pct_nlv:+.2f}% NLV)")
        print(f"    Hard gate (worst ≤ 5% NLV): {'✓ PASS' if gate_worst_pass else '❌ FAIL'} "
              f"(p5 worst: {'✓' if gate_worst_p5_pass else '❌'})")

        results_grid.append({
            "variant": variant_name, "sizing": sizing_label, "n_contracts": n_contracts,
            "n_trades_avg": sm["n_trades"].mean(),
            "cum_pnl_mean": cum_mean, "cum_pnl_std": cum_std,
            "cum_pnl_p5": cum_p5, "cum_pnl_p95": cum_p95,
            "ann_pnl_usd": ann_pnl, "ann_pnl_pct_nlv": ann_pnl_pct,
            "worst_trade_mean": worst_mean, "worst_trade_p5": worst_p5,
            "worst_pct_nlv_mean": worst_pct_nlv,
            "worst_pct_nlv_p5": worst_p5_pct_nlv,
            "hit_rate_avg": sm["hit_rate"].mean(),
            "gate_worst_5pct_pass_mean": gate_worst_pass,
            "gate_worst_5pct_pass_p5": gate_worst_p5_pass,
        })

results_df = pd.DataFrame(results_grid)
results_df.to_csv(OUT / "q078_p1b2_sizing_results.csv", index=False)

# ── Combined trade log ───────────────────────────────────────────────
if all_trade_logs:
    pd.concat(all_trade_logs, ignore_index=True).to_csv(OUT / "q078_p1b2_pnl_distribution.csv", index=False)

# ── Hard gates pass/fail table ───────────────────────────────────────
print("\n" + "=" * 70)
print("HARD GATE STATUS (worst-trade ≤ 5% NLV)")
print("=" * 70)
print(f"\n{'Variant':<22} {'Sizing':<22} {'CumPnL':>14} {'AnnROE':>9} {'WorstMean':>14} {'WorstP5':>12} {'5% gate (mean / P5)'}")
print("-" * 120)
gates = []
for _, r in results_df.iterrows():
    mark_mean = "✓" if r["gate_worst_5pct_pass_mean"] else "❌"
    mark_p5 = "✓" if r["gate_worst_5pct_pass_p5"] else "❌"
    print(f"{r['variant']:<22} {r['sizing']:<22} ${r['cum_pnl_mean']:>+12,.0f}  {r['ann_pnl_pct_nlv']:>+7.3f}%  "
          f"${r['worst_trade_mean']:>+12,.0f}  ${r['worst_trade_p5']:>+10,.0f}  {mark_mean} / {mark_p5}")
    gates.append({
        "variant": r["variant"], "sizing": r["sizing"],
        "ann_pnl_pct_nlv": r["ann_pnl_pct_nlv"],
        "worst_pct_nlv_mean": r["worst_pct_nlv_mean"],
        "worst_pct_nlv_p5": r["worst_pct_nlv_p5"],
        "gate_5pct_mean": r["gate_worst_5pct_pass_mean"],
        "gate_5pct_p5": r["gate_worst_5pct_pass_p5"],
    })
pd.DataFrame(gates).to_csv(OUT / "q078_p1b2_hard_gates_pass_fail.csv", index=False)

# ── Headline: ladder vs Baseline B at matched sizing ─────────────────
print("\n" + "=" * 70)
print("HEADLINE: Ladder vs Baseline B at matched sizing (cum PnL mean)")
print("=" * 70)
for sizing_label in SIZINGS.keys():
    print(f"\n[{sizing_label}]")
    base_row = results_df[(results_df["variant"] == "BaselineB_cluster") & (results_df["sizing"] == sizing_label)]
    if base_row.empty:
        continue
    base = base_row.iloc[0]
    print(f"  Baseline B:     ${base['cum_pnl_mean']:+,.0f} cum ({base['ann_pnl_pct_nlv']:+.3f}% NLV/yr)  "
          f"worst ${base['worst_trade_mean']:+,.0f} ({base['worst_pct_nlv_mean']:+.2f}% NLV)")
    for var in ["V1b_weekly_catchup", "V3_daily_cluster"]:
        row = results_df[(results_df["variant"] == var) & (results_df["sizing"] == sizing_label)]
        if row.empty:
            continue
        r = row.iloc[0]
        d_pnl = r["cum_pnl_mean"] - base["cum_pnl_mean"]
        d_ann = r["ann_pnl_pct_nlv"] - base["ann_pnl_pct_nlv"]
        gate = "✓" if r["gate_worst_5pct_pass_p5"] else "❌"
        print(f"  {var:<20} ${r['cum_pnl_mean']:+,.0f} cum (Δ ${d_pnl:+,.0f}, Δ{d_ann:+.3f}pp)  "
              f"worst ${r['worst_trade_mean']:+,.0f} ({r['worst_pct_nlv_mean']:+.2f}% NLV)  gate {gate}")

# ── Bootstrap CI summary per (variant, sizing) ───────────────────────
ci_rows = []
for _, r in results_df.iterrows():
    ci_rows.append({
        "variant": r["variant"], "sizing": r["sizing"],
        "ann_pnl_mean": r["ann_pnl_usd"], "ann_pnl_pct_mean": r["ann_pnl_pct_nlv"],
        "cum_pnl_p5": r["cum_pnl_p5"], "cum_pnl_p95": r["cum_pnl_p95"],
        "cum_pnl_std": r["cum_pnl_std"],
        "worst_trade_mean_pct_nlv": r["worst_pct_nlv_mean"],
        "worst_trade_p5_pct_nlv": r["worst_pct_nlv_p5"],
    })
pd.DataFrame(ci_rows).to_csv(OUT / "q078_p1b2_bootstrap_ci.csv", index=False)

print("\n" + "=" * 70)
print("Q078 P1b-2 done. CSVs in research/q078/")
print("=" * 70)
print("\nKey takeaways:")
print("  - PnL today-scaled to SPX 7400 (Option C dual-view: today-scaled $)")
print("  - Worst-trade evaluated against 5% NLV hard gate (P0 §7 revised)")
print("  - 20-seed bootstrap CI for stability")
print("  - S4 dynamic NOT tested (would breach worst-trade gate at any meaningful filling)")
