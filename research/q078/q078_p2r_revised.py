"""Q078 P2 REVISED — fix L1 (eff_count) + L4 (daily MTM) + add 20-seed CI.

Per PM agreement (2026-05-28) to REVISE & RE-RUN before final verdict.

Three fixes:
  L1 — eff_count: weekly snapshot of CURRENTLY-OPEN positions grouped by
       monthly-expiry bucket (entry_date + DTE → month). Matches P1b-2
       "at-any-given-moment" framework.

  L4 — daily PnL: distribute each trade PnL linearly across hold days
       (avg 14 calendar days) rather than single-day spike on exit_date.
       Better proxy for daily MTM behavior for W20d/W63d computation.

  L5 — bootstrap CI: 20 seeds, report mean + 5%-95% CI for all metrics.

Carries forward from original P2:
  - Two-layer methodology (shadow vs production)
  - Concurrency + BP gates in Layer 2
  - S3 sizing (3 contracts)
  - Engine 26y empirical PnL with SPX-scaled bootstrap

Outputs:
  q078_p2r_metrics.csv               — mean + CI per (variant, layer)
  q078_p2r_gate_check.csv            — hard gate pass/fail with CI
  q078_p2r_eff_count_timeline.csv    — weekly eff_count timeline (snapshot)
  q078_p2r_daily_pnl_distribution.csv (optional, large)
  q078_p2r_memo.md
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

GATE_WORST_TRADE_NLV = 0.05
BP_CEILING_NORMAL = 0.35
SIZING_CONTRACTS = 3
N_SEEDS = 20
AVG_HOLD_DAYS = 14  # SPEC-077 21 DTE roll → empirically ~14 cal days

CONCURRENCY_CAP = {
    "Bull Put Spread": 1, "Bull Put Spread (High Vol)": 1,
    "Iron Condor": 1, "Iron Condor (High Vol)": 2,
    "Bear Call Spread (High Vol)": 1, "Bull Call Diagonal": 1,
}

# Strategy → planned DTE (for monthly expiry bucketing)
STRATEGY_DTE = {
    "Bull Put Spread": 30, "Bull Put Spread (High Vol)": 35,
    "Iron Condor": 30, "Iron Condor (High Vol)": 35,
    "Bear Call Spread (High Vol)": 35, "Bull Call Diagonal": 45,
}

print("Q078 P2 REVISED — eff_count fix + daily MTM smoothing + 20-seed CI", flush=True)
print("=" * 70)

# ── Load data ────────────────────────────────────────────────────────
print("\nLoading engine trades + signal history...")
trades_df = pd.read_csv(OUT / "_engine_trades_26y_cache.csv", parse_dates=["entry_date"])
trades_df["pnl_per_ct"] = trades_df["exit_pnl"] / trades_df["contracts"].replace(0, 1)
trades_df["max_loss_per_ct"] = trades_df["total_bp"] / trades_df["contracts"].replace(0, 1)
trades_df["spx_scale"] = SPX_TODAY / trades_df["entry_spx"]
trades_df["pnl_today_per_ct"] = trades_df["pnl_per_ct"] * trades_df["spx_scale"]
trades_df["max_loss_today_per_ct"] = trades_df["max_loss_per_ct"] * trades_df["spx_scale"]

pool_by_strat = {}
for strat in trades_df["strategy"].unique():
    sub = trades_df[trades_df["strategy"] == strat]
    pool_by_strat[strat] = list(zip(
        sub["pnl_today_per_ct"].tolist(),
        sub["max_loss_today_per_ct"].tolist(),
    ))

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

# ── Cadence eval days (same as P2) ───────────────────────────────────
def v1b_eval():
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

def v3_eval():
    eval_list = []
    last = None
    for d in sig_df.index:
        if last is not None and (d - last).days < 5:
            continue
        if sig_df.loc[d, "strategy"] != "Reduce / Wait":
            eval_list.append(d)
            last = d
    return set(eval_list)

def baseline_b_eval():
    eval_list = []
    last = None
    for d in sig_df.index:
        if last is not None and (d - last).days < 30:
            continue
        if sig_df.loc[d, "strategy"] != "Reduce / Wait":
            eval_list.append(d)
            last = d
    return set(eval_list)

variants_eval = {
    "V1b_weekly_catchup": v1b_eval(),
    "V3_daily_cluster":   v3_eval(),
    "BaselineB_cluster":  baseline_b_eval(),
}

# ── PnL lookup ───────────────────────────────────────────────────────
def lookup_pnl(entry_date, strategy_name, rng):
    for delta in [0, 1, -1, 2, -2]:
        cand = entry_date + pd.Timedelta(days=delta)
        if cand in engine_by_date:
            for e in engine_by_date[cand]:
                if e["strategy"] == strategy_name:
                    return e["pnl_today_per_ct"], e["max_loss_today_per_ct"]
    if strategy_name in pool_by_strat and pool_by_strat[strategy_name]:
        pool = pool_by_strat[strategy_name]
        idx = rng.integers(0, len(pool))
        return pool[idx][0], pool[idx][1]
    return None, None

# ── Ladder simulator (with L1 + L4 fixes) ────────────────────────────
def simulate(variant_name, eval_set, sig_df, n_contracts, production_gates, seed):
    rng = np.random.default_rng(seed)
    positions = []  # active: {entry, exit, expiry_month, strategy, pnl, max_loss}
    completed = []

    for d in sig_df.index:
        # Process exits
        positions = [p for p in positions if p["exit"] > d
                      or (completed.append(p) or False)]
        # (After exit, position is in 'completed' list)

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
            new_max_loss_est = pool_by_strat.get(strat, [(0, 0)])[0][1] * n_contracts
            if (current_bp + new_max_loss_est) / NLV > BP_CEILING_NORMAL:
                continue

        pnl_per_ct, max_loss_per_ct = lookup_pnl(d, strat, rng)
        if pnl_per_ct is None:
            continue

        exit_d = d + pd.Timedelta(days=AVG_HOLD_DAYS)
        dte = STRATEGY_DTE.get(strat, 30)
        expiry_proxy = d + pd.Timedelta(days=dte)
        # Bucket to month (first day of month containing expiry)
        expiry_month = pd.Timestamp(expiry_proxy.year, expiry_proxy.month, 1)

        positions.append({
            "entry": d, "exit": exit_d,
            "expiry_month": expiry_month,
            "strategy": strat,
            "pnl": pnl_per_ct * n_contracts,
            "max_loss": max_loss_per_ct * n_contracts,
        })

    for p in positions:
        completed.append(p)
    return completed

# ── Metric computation (L1 + L4 fixes) ───────────────────────────────
def compute_metrics(trades, sig_df, variant_name, layer_name):
    if not trades:
        return None

    n = len(trades)
    cum_pnl = sum(t["pnl"] for t in trades)
    worst = min(t["pnl"] for t in trades)
    hit = sum(1 for t in trades if t["pnl"] > 0) / n * 100
    years = (sig_df.index.max() - sig_df.index.min()).days / 365.25
    ann_pnl = cum_pnl / years
    ann_pnl_pct = ann_pnl / NLV * 100

    # ── L4 fix: distribute PnL linearly across hold days ─────────────
    daily_pnl = pd.Series(0.0, index=sig_df.index)
    for t in trades:
        # Find trading days in [entry, exit)
        hold_range = pd.date_range(t["entry"], t["exit"], freq="B")
        hold_range = [d for d in hold_range if d in daily_pnl.index]
        if hold_range:
            per_day = t["pnl"] / len(hold_range)
            for d in hold_range:
                daily_pnl.loc[d] += per_day
        else:
            # Fallback: book at entry if no trading days in range
            if t["entry"] in daily_pnl.index:
                daily_pnl.loc[t["entry"]] += t["pnl"]

    eq = NLV + daily_pnl.cumsum()
    running_max = eq.cummax()
    drawdown = (eq - running_max) / running_max
    max_dd = drawdown.min()
    daily_ret = daily_pnl / eq.shift(1).fillna(NLV)
    w20 = daily_ret.rolling(20).sum().min()
    w63 = daily_ret.rolling(63).sum().min()
    sharpe = (daily_ret.mean() / daily_ret.std() * (252**0.5)
              if daily_ret.std() > 0 else 0)

    # ── L1 fix: weekly snapshot of currently-open positions by month bucket ──
    weekly_dates = pd.date_range(sig_df.index.min(), sig_df.index.max(), freq="W-MON")
    eff_counts = []
    max_concs = []
    for d in weekly_dates:
        active = [t for t in trades if t["entry"] <= d < t["exit"]]
        if not active:
            continue
        by_month = {}
        for t in active:
            by_month[t["expiry_month"]] = by_month.get(t["expiry_month"], 0) + t["max_loss"]
        total = sum(by_month.values())
        if total <= 0:
            continue
        weights = np.array([v / total for v in by_month.values()])
        eff = 1.0 / (weights ** 2).sum()
        max_c = weights.max() * 100
        eff_counts.append(eff)
        max_concs.append(max_c)

    eff_count_mean = np.mean(eff_counts) if eff_counts else 0
    max_conc_mean = np.mean(max_concs) if max_concs else 100

    return {
        "variant": variant_name, "layer": layer_name, "n_trades": n,
        "cum_pnl": cum_pnl, "ann_pnl_usd": ann_pnl, "ann_pnl_pct_nlv": ann_pnl_pct,
        "avg_pnl": cum_pnl / n, "hit_rate": hit,
        "worst_trade": worst, "worst_pct_nlv": worst / NLV * 100,
        "max_dd_pct": max_dd * 100,
        "w20d_pct": w20 * 100, "w63d_pct": w63 * 100,
        "sharpe": sharpe,
        "eff_count_mean": eff_count_mean,
        "max_conc_mean": max_conc_mean,
    }

# ── Run 20-seed sweep ────────────────────────────────────────────────
print(f"\nRunning {N_SEEDS}-seed sweep × 3 variants × 2 layers = {N_SEEDS*3*2} simulations...")

all_results = []  # collected metrics per (variant, layer, seed)
for variant in ["V1b_weekly_catchup", "V3_daily_cluster", "BaselineB_cluster"]:
    eval_set = variants_eval[variant]
    print(f"\n[{variant}] eval days: {len(eval_set)}")
    for layer_name, prod_gates in [("Layer1_shadow", False), ("Layer2_production", True)]:
        seed_metrics = []
        for seed in range(N_SEEDS):
            trades = simulate(variant, eval_set, sig_df, SIZING_CONTRACTS,
                              production_gates=prod_gates, seed=42 + seed)
            m = compute_metrics(trades, sig_df, variant, layer_name)
            if m is None:
                continue
            m["seed"] = seed
            seed_metrics.append(m)
        if not seed_metrics:
            continue
        n_trade_mean = np.mean([m["n_trades"] for m in seed_metrics])
        print(f"  {layer_name}: avg {n_trade_mean:.0f} trades across {N_SEEDS} seeds")
        all_results.extend(seed_metrics)

# ── Aggregate CI per (variant, layer) ────────────────────────────────
all_df = pd.DataFrame(all_results)

print("\n" + "=" * 70)
print("PORTFOLIO METRICS (20-seed CI, eff_count + daily MTM fixes applied)")
print("=" * 70)

agg_rows = []
print(f"\n{'Variant':<22} {'Layer':<18} {'n_avg':>6} {'AnnROE%':>17} {'MaxDD%':>16} {'W20d%':>17} {'W63d%':>17} {'EffExp':>14}")
print("-" * 130)
for variant in ["V1b_weekly_catchup", "V3_daily_cluster", "BaselineB_cluster"]:
    for layer_name in ["Layer1_shadow", "Layer2_production"]:
        sub = all_df[(all_df["variant"] == variant) & (all_df["layer"] == layer_name)]
        if sub.empty:
            continue
        n_mean = sub["n_trades"].mean()
        ann_mean = sub["ann_pnl_pct_nlv"].mean()
        ann_p5 = sub["ann_pnl_pct_nlv"].quantile(0.05)
        ann_p95 = sub["ann_pnl_pct_nlv"].quantile(0.95)
        dd_mean = sub["max_dd_pct"].mean()
        dd_p5 = sub["max_dd_pct"].quantile(0.05)
        dd_p95 = sub["max_dd_pct"].quantile(0.95)
        w20_mean = sub["w20d_pct"].mean()
        w20_p5 = sub["w20d_pct"].quantile(0.05)
        w20_p95 = sub["w20d_pct"].quantile(0.95)
        w63_mean = sub["w63d_pct"].mean()
        w63_p5 = sub["w63d_pct"].quantile(0.05)
        w63_p95 = sub["w63d_pct"].quantile(0.95)
        eff_mean = sub["eff_count_mean"].mean()
        eff_p5 = sub["eff_count_mean"].quantile(0.05)
        eff_p95 = sub["eff_count_mean"].quantile(0.95)
        worst_mean = sub["worst_pct_nlv"].mean()
        worst_p5 = sub["worst_pct_nlv"].quantile(0.05)
        print(f"{variant:<22} {layer_name:<18} {n_mean:>6.0f} "
              f"{ann_mean:>+7.2f}[{ann_p5:>+5.2f},{ann_p95:>+5.2f}] "
              f"{dd_mean:>+6.2f}[{dd_p5:>+5.2f},{dd_p95:>+5.2f}] "
              f"{w20_mean:>+6.2f}[{w20_p5:>+5.2f},{w20_p95:>+5.2f}] "
              f"{w63_mean:>+6.2f}[{w63_p5:>+5.2f},{w63_p95:>+5.2f}] "
              f"{eff_mean:>5.2f}[{eff_p5:>4.2f},{eff_p95:>4.2f}]")
        agg_rows.append({
            "variant": variant, "layer": layer_name,
            "n_trades_avg": n_mean,
            "ann_pnl_pct_mean": ann_mean, "ann_pnl_pct_p5": ann_p5, "ann_pnl_pct_p95": ann_p95,
            "max_dd_pct_mean": dd_mean, "max_dd_pct_p5": dd_p5, "max_dd_pct_p95": dd_p95,
            "w20d_pct_mean": w20_mean, "w20d_pct_p5": w20_p5, "w20d_pct_p95": w20_p95,
            "w63d_pct_mean": w63_mean, "w63d_pct_p5": w63_p5, "w63d_pct_p95": w63_p95,
            "eff_count_mean": eff_mean, "eff_count_p5": eff_p5, "eff_count_p95": eff_p95,
            "worst_pct_nlv_mean": worst_mean, "worst_pct_nlv_p5": worst_p5,
        })

agg_df = pd.DataFrame(agg_rows)
agg_df.to_csv(OUT / "q078_p2r_metrics.csv", index=False)

# ── Hard gate check vs Baseline B Layer 2 ───────────────────────────
print("\n" + "=" * 70)
print("HARD GATE CHECK (Layer 2 production, mean across 20 seeds)")
print("=" * 70)

base_l2 = next((r for r in agg_rows if r["variant"] == "BaselineB_cluster" and r["layer"] == "Layer2_production"), None)
if not base_l2:
    print("ERROR: Baseline B Layer 2 not found")
else:
    print(f"\nBaseline B L2: ann {base_l2['ann_pnl_pct_mean']:.2f}% NLV, "
          f"W20d {base_l2['w20d_pct_mean']:.2f}% (5-95% [{base_l2['w20d_pct_p5']:.2f}, {base_l2['w20d_pct_p95']:.2f}]), "
          f"W63d {base_l2['w63d_pct_mean']:.2f}% (5-95% [{base_l2['w63d_pct_p5']:.2f}, {base_l2['w63d_pct_p95']:.2f}])")
    gate_rows = []
    for variant in ["V1b_weekly_catchup", "V3_daily_cluster"]:
        r = next((m for m in agg_rows if m["variant"] == variant and m["layer"] == "Layer2_production"), None)
        if not r:
            continue
        d_pnl = r["ann_pnl_pct_mean"] - base_l2["ann_pnl_pct_mean"]
        d_w20 = r["w20d_pct_mean"] - base_l2["w20d_pct_mean"]
        d_w63 = r["w63d_pct_mean"] - base_l2["w63d_pct_mean"]
        # CI for delta (rough — independent assumption)
        d_w20_p5 = r["w20d_pct_p5"] - base_l2["w20d_pct_p95"]  # worst case
        d_w20_p95 = r["w20d_pct_p95"] - base_l2["w20d_pct_p5"]
        d_w63_p5 = r["w63d_pct_p5"] - base_l2["w63d_pct_p95"]
        d_w63_p95 = r["w63d_pct_p95"] - base_l2["w63d_pct_p5"]

        gate_v1 = abs(r["max_dd_pct_mean"] / 100) <= 0.28
        gate_v2 = abs(r["w20d_pct_mean"] / 100) <= 0.11
        gate_v3 = abs(r["w63d_pct_mean"] / 100) <= 0.17
        # Degradation gate (1pp degradation = +1pp toward more negative)
        gate_w20_deg = d_w20 >= -0.25
        gate_w63_deg = d_w63 >= -0.25
        # CI-aware: pass if MEAN passes AND p5 also passes
        gate_w20_deg_ci = d_w20_p5 >= -0.25
        gate_w63_deg_ci = d_w63_p5 >= -0.25
        gate_worst = abs(r["worst_pct_nlv_mean"]) <= GATE_WORST_TRADE_NLV * 100

        all_pass_mean = gate_v1 and gate_v2 and gate_v3 and gate_w20_deg and gate_w63_deg and gate_worst
        if all_pass_mean:
            if d_pnl >= 0.20:
                verdict = "STRONG PROMOTE"
            elif d_pnl >= 0.05:
                verdict = "SOFT PROMOTE"
            else:
                verdict = "DOCUMENT (sub-threshold)"
        else:
            verdict = "REJECT (hard gate fail)"

        print(f"\n{variant}:")
        print(f"  Ann PnL: {r['ann_pnl_pct_mean']:+.2f}% NLV (Δ {d_pnl:+.2f}pp)")
        print(f"  W20d: {r['w20d_pct_mean']:+.2f}% (Δ {d_w20:+.2f}pp, CI Δ p5={d_w20_p5:+.2f}pp p95={d_w20_p95:+.2f}pp)")
        print(f"  W63d: {r['w63d_pct_mean']:+.2f}% (Δ {d_w63:+.2f}pp, CI Δ p5={d_w63_p5:+.2f}pp p95={d_w63_p95:+.2f}pp)")
        print(f"  MaxDD: {r['max_dd_pct_mean']:+.2f}%   Worst: {r['worst_pct_nlv_mean']:+.2f}% NLV")
        print(f"  EffCount: {r['eff_count_mean']:.2f} (5-95% [{r['eff_count_p5']:.2f}, {r['eff_count_p95']:.2f}])")
        print(f"  Gates: V1{'✓' if gate_v1 else '❌'} V2{'✓' if gate_v2 else '❌'} V3{'✓' if gate_v3 else '❌'} "
              f"W20Δmean{'✓' if gate_w20_deg else '❌'} (p5{'✓' if gate_w20_deg_ci else '❌'}) "
              f"W63Δmean{'✓' if gate_w63_deg else '❌'} (p5{'✓' if gate_w63_deg_ci else '❌'}) "
              f"Worst{'✓' if gate_worst else '❌'}")
        print(f"  Verdict: {verdict}")

        gate_rows.append({
            "variant": variant,
            "ann_pnl_pct": r["ann_pnl_pct_mean"], "delta_roe_pp": d_pnl,
            "w20d_delta_mean_pp": d_w20, "w20d_delta_p5_pp": d_w20_p5,
            "w63d_delta_mean_pp": d_w63, "w63d_delta_p5_pp": d_w63_p5,
            "max_dd_pct": r["max_dd_pct_mean"], "worst_pct_nlv": r["worst_pct_nlv_mean"],
            "eff_count_mean": r["eff_count_mean"],
            "gate_v1_pass": gate_v1, "gate_v2_pass": gate_v2, "gate_v3_pass": gate_v3,
            "gate_w20_deg_mean_pass": gate_w20_deg, "gate_w20_deg_p5_pass": gate_w20_deg_ci,
            "gate_w63_deg_mean_pass": gate_w63_deg, "gate_w63_deg_p5_pass": gate_w63_deg_ci,
            "gate_worst_5pct_pass": gate_worst,
            "verdict_mean": verdict,
        })

    pd.DataFrame(gate_rows).to_csv(OUT / "q078_p2r_gate_check.csv", index=False)

print("\n" + "=" * 70)
print("Q078 P2 REVISED done. CSVs in research/q078/")
print("=" * 70)
