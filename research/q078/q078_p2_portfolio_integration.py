"""Q078 P2 — Portfolio Integration (Two-Layer Shadow + Production Gates).

Per 2nd Quant G2.5 PASS (2026-05-28):
  Layer 1 — Shadow Valuation Engine:
    PnL estimate for ALL selector-PASS ladder eval days (no production gates).
    Already produced by P1b-2.
    Inflated ~3-5x by selection bias.

  Layer 2 — Production-Eligible Ladder:
    Apply real production gates:
      - Concurrency cap (1 per strategy; 2 for IC_HV)
      - BP ceiling (35% NLV selector NORMAL regime)
      - SPEC-077 21 DTE exit
    Compare to Layer 1 to quantify selection-bias correction.

  Sizing: S3 (3 contracts ≈ 7.5% BP, max under 5% NLV worst-trade gate)
  Cadence: V1b weekly catch-up + V3 daily-cluster + Baseline B (control)
  Strategy: agnostic per P0 R8 (selector-provided)

Outputs:
  q078_p2_layer1_shadow.csv          — unbiased shadow PnL (P1b-2 equivalent)
  q078_p2_layer2_production.csv      — production-realistic trades
  q078_p2_bias_quantified.csv        — Layer 1 vs Layer 2 delta
  q078_p2_portfolio_metrics.csv      — ROE / MaxDD / W20d / W63d / Sharpe per variant
  q078_p2_expiry_concentration.csv   — eff_count + max_conc per variant
  q078_p2_capital_competition.csv    — BP timeline + Q042 overlap
  q078_p2_crisis_windows.csv         — 5 named windows per variant
  q078_p2_action_days.csv            — operational burden
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

# Hard gates (per P0 §7 revised)
GATE_WORST_TRADE_NLV = 0.05
GATE_W20D_BASELINE_MAX = -0.11
GATE_W63D_BASELINE_MAX = -0.17
GATE_W20D_DEGRADATION = 0.0025
GATE_W63D_DEGRADATION = 0.0025

# Selector ceilings (per regime)
BP_CEILING_NORMAL = 0.35
BP_CEILING_LOW_VOL = 0.25
BP_CEILING_HIGH_VOL = 0.50

# Concurrency caps (per strategy, mirrors engine)
CONCURRENCY_CAP = {
    "Bull Put Spread": 1,
    "Bull Put Spread (High Vol)": 1,
    "Iron Condor": 1,
    "Iron Condor (High Vol)": 2,   # engine IC_HV_MAX_CONCURRENT
    "Bear Call Spread (High Vol)": 1,
    "Bull Call Diagonal": 1,
}

# Sizing
SIZING_CONTRACTS = 3   # S3

print("Q078 P2 — Portfolio Integration (Two-Layer Shadow + Production Gates)", flush=True)
print("=" * 70)
print(f"NLV ${NLV:,.0f}, SPX today {SPX_TODAY}")
print(f"Sizing: S3 ({SIZING_CONTRACTS} contracts)")
print(f"Production gates: concurrency + BP ceiling ({BP_CEILING_NORMAL*100:.0f}% NORMAL)")

# ── Load engine trades + signal history ──────────────────────────────
print("\nLoading engine 26y trades + signal history...")
trades_df = pd.read_csv(OUT / "_engine_trades_26y_cache.csv", parse_dates=["entry_date"])
trades_df["pnl_per_contract"] = trades_df["exit_pnl"] / trades_df["contracts"].replace(0, 1)
trades_df["max_loss_per_contract"] = trades_df["total_bp"] / trades_df["contracts"].replace(0, 1)
trades_df["spx_scale"] = SPX_TODAY / trades_df["entry_spx"]
trades_df["pnl_today_per_ct"] = trades_df["pnl_per_contract"] * trades_df["spx_scale"]
trades_df["max_loss_today_per_ct"] = trades_df["max_loss_per_contract"] * trades_df["spx_scale"]
trades_df["pnl_pct_max_loss"] = trades_df["pnl_per_contract"] / trades_df["max_loss_per_contract"].replace(0, 1)

# Empirical pool per strategy
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

# Engine entries by date for exact-match preference
engine_by_date = {}
for _, row in trades_df.iterrows():
    d = row["entry_date"]
    engine_by_date.setdefault(d, []).append({
        "strategy": row["strategy"],
        "pnl_today_per_ct": row["pnl_today_per_ct"],
        "max_loss_today_per_ct": row["max_loss_today_per_ct"],
    })

# ── Cadence eval days ────────────────────────────────────────────────
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

def v3_eval(sig_df):
    eval_list = []
    last_entry = None
    for d in sig_df.index:
        if last_entry is not None and (d - last_entry).days < 5:
            continue
        if sig_df.loc[d, "strategy"] != "Reduce / Wait":
            eval_list.append(d)
            last_entry = d
    return set(eval_list)

def baseline_b_eval(sig_df):
    eval_list = []
    last_entry = None
    for d in sig_df.index:
        if last_entry is not None and (d - last_entry).days < 30:
            continue
        if sig_df.loc[d, "strategy"] != "Reduce / Wait":
            eval_list.append(d)
            last_entry = d
    return set(eval_list)

variants_eval = {
    "V1b_weekly_catchup": v1b_eval(all_days, sig_df),
    "V3_daily_cluster":   v3_eval(sig_df),
    "BaselineB_cluster":  baseline_b_eval(sig_df),
}

print("\nCadence eval days:")
for name, days in variants_eval.items():
    print(f"  {name}: {len(days)} days")

# ── PnL lookup (engine actual or bootstrap) ──────────────────────────
def lookup_pnl(entry_date, strategy_name, rng):
    """Returns (pnl_today_per_ct, max_loss_today_per_ct, source)."""
    for delta in [0, 1, -1, 2, -2]:
        cand = entry_date + pd.Timedelta(days=delta)
        if cand in engine_by_date:
            for e in engine_by_date[cand]:
                if e["strategy"] == strategy_name:
                    return e["pnl_today_per_ct"], e["max_loss_today_per_ct"], f"engine_d{delta:+d}"
    if strategy_name in pool_by_strat and pool_by_strat[strategy_name]:
        pool = pool_by_strat[strategy_name]
        idx = rng.integers(0, len(pool))
        return pool[idx][0], pool[idx][1], "bootstrap"
    return None, None, "no_data"

# ── Ladder simulator with production gates ───────────────────────────
class Position:
    __slots__ = ("entry_date", "exit_date", "strategy", "pnl", "max_loss",
                  "n_contracts", "pnl_source")
    def __init__(self, entry_date, exit_date, strategy, pnl, max_loss, n_contracts, source):
        self.entry_date = entry_date
        self.exit_date = exit_date
        self.strategy = strategy
        self.pnl = pnl
        self.max_loss = max_loss
        self.n_contracts = n_contracts
        self.pnl_source = source

def simulate_variant(variant_name, eval_days_set, sig_df, n_contracts,
                     apply_production_gates: bool, seed: int = 42):
    """
    Layer 1 (apply_production_gates=False): selector PASS only → enter (P1b-2 behavior)
    Layer 2 (apply_production_gates=True):  + concurrency + BP ceiling → realistic
    """
    rng = np.random.default_rng(seed)
    positions: list[Position] = []  # active
    completed: list[Position] = []
    daily_records = []
    skipped_concurrency = 0
    skipped_bp_ceiling = 0
    skipped_no_data = 0

    for d in sig_df.index:
        # Process exits: anything with exit_date <= d
        still_active = []
        for p in positions:
            if p.exit_date <= d:
                completed.append(p)
            else:
                still_active.append(p)
        positions = still_active

        # Daily snapshot (for BP timeline)
        current_bp = sum(p.max_loss for p in positions)
        active_strategies = [p.strategy for p in positions]
        daily_records.append({
            "date": d, "active_positions": len(positions),
            "bp_used": current_bp, "bp_pct_nlv": current_bp / NLV * 100,
            "active_strategies": ",".join(active_strategies),
        })

        # Entry check only on eval days
        if d not in eval_days_set:
            continue
        if d not in sig_df.index:
            continue
        strat = sig_df.loc[d, "strategy"]
        if strat == "Reduce / Wait":
            continue

        # Production gates
        if apply_production_gates:
            cap = CONCURRENCY_CAP.get(strat, 1)
            same_strat = sum(1 for p in positions if p.strategy == strat)
            if same_strat >= cap:
                skipped_concurrency += 1
                continue
            # BP ceiling — use NORMAL ceiling 35% as conservative default
            new_bp_est = pool_by_strat.get(strat, [(0, 0)])[0][1] * n_contracts
            if (current_bp + new_bp_est) / NLV > BP_CEILING_NORMAL:
                skipped_bp_ceiling += 1
                continue

        # Lookup PnL
        pnl_per_ct, max_loss_per_ct, source = lookup_pnl(d, strat, rng)
        if pnl_per_ct is None:
            skipped_no_data += 1
            continue
        total_pnl = pnl_per_ct * n_contracts
        total_max_loss = max_loss_per_ct * n_contracts

        # SPEC-077 exit: 21 DTE roll → entry + 9 calendar days approximately (roll fires at d_off=10 trading days)
        # Use empirical avg hold ~14 calendar days from engine
        avg_hold_calendar = 14
        exit_date = d + pd.Timedelta(days=avg_hold_calendar)

        positions.append(Position(
            entry_date=d, exit_date=exit_date,
            strategy=strat, pnl=total_pnl, max_loss=total_max_loss,
            n_contracts=n_contracts, source=source,
        ))

    # Final exits
    for p in positions:
        completed.append(p)

    print(f"    {variant_name} ({'Layer 2' if apply_production_gates else 'Layer 1'}): "
          f"{len(completed)} trades, "
          f"skipped concurrency={skipped_concurrency}, BP={skipped_bp_ceiling}, no_data={skipped_no_data}")

    return completed, pd.DataFrame(daily_records)

# ── Run both layers ──────────────────────────────────────────────────
print(f"\nRunning both layers for each variant (sizing S3 = {SIZING_CONTRACTS} contracts)...")

layer1_trades = {}
layer1_daily = {}
layer2_trades = {}
layer2_daily = {}

for variant in ["V1b_weekly_catchup", "V3_daily_cluster", "BaselineB_cluster"]:
    print(f"\n[{variant}]")
    eval_set = variants_eval[variant]
    # Layer 1
    t1, d1 = simulate_variant(variant, eval_set, sig_df, SIZING_CONTRACTS,
                                apply_production_gates=False, seed=42)
    # Layer 2
    t2, d2 = simulate_variant(variant, eval_set, sig_df, SIZING_CONTRACTS,
                                apply_production_gates=True, seed=42)
    layer1_trades[variant] = t1
    layer1_daily[variant] = d1
    layer2_trades[variant] = t2
    layer2_daily[variant] = d2

# ── Export trade logs ───────────────────────────────────────────────
def export_trades(trades_dict, filename):
    rows = []
    for variant, trades in trades_dict.items():
        for p in trades:
            rows.append({
                "variant": variant, "entry_date": p.entry_date, "exit_date": p.exit_date,
                "strategy": p.strategy, "pnl": p.pnl, "max_loss": p.max_loss,
                "n_contracts": p.n_contracts, "pnl_source": p.pnl_source,
            })
    pd.DataFrame(rows).to_csv(OUT / filename, index=False)

export_trades(layer1_trades, "q078_p2_layer1_shadow.csv")
export_trades(layer2_trades, "q078_p2_layer2_production.csv")

# ── Compute portfolio metrics per variant per layer ─────────────────
def compute_metrics(trades: list, daily_records: pd.DataFrame, variant_name: str, layer: str):
    n_trades = len(trades)
    if n_trades == 0:
        return {"variant": variant_name, "layer": layer, "n_trades": 0}

    cum_pnl = sum(p.pnl for p in trades)
    worst = min(p.pnl for p in trades)
    avg_pnl = cum_pnl / n_trades
    hit = sum(1 for p in trades if p.pnl > 0) / n_trades * 100
    years = 26.4
    ann_pnl = cum_pnl / years
    ann_pnl_pct = ann_pnl / NLV * 100

    # Daily PnL series for MaxDD/W20d/W63d (place pnl on exit_date)
    pnl_by_date = {}
    for p in trades:
        d = p.exit_date.normalize()
        pnl_by_date[d] = pnl_by_date.get(d, 0) + p.pnl

    daily_series = daily_records.copy()
    daily_series["date"] = pd.to_datetime(daily_series["date"])
    daily_series = daily_series.set_index("date").sort_index()
    daily_series["pnl"] = 0.0
    for d, pnl in pnl_by_date.items():
        if d in daily_series.index:
            daily_series.loc[d, "pnl"] += pnl
    daily_series["cum"] = daily_series["pnl"].cumsum()
    daily_series["eq"] = NLV + daily_series["cum"]
    running_max = daily_series["eq"].cummax()
    drawdown = (daily_series["eq"] - running_max) / running_max
    max_dd = drawdown.min()
    daily_series["ret"] = daily_series["pnl"] / daily_series["eq"].shift(1).fillna(NLV)
    w20 = daily_series["ret"].rolling(20).sum().min()
    w63 = daily_series["ret"].rolling(63).sum().min()
    sharpe = (daily_series["ret"].mean() / daily_series["ret"].std() * (252**0.5)
              if daily_series["ret"].std() > 0 else 0)

    # BP metrics
    active = daily_records[daily_records["bp_used"] > 0]
    bp_mean = active["bp_used"].mean() if len(active) else 0
    bp_p95 = active["bp_used"].quantile(0.95) if len(active) else 0

    # Expiry concentration
    expiry_rows = []
    for p in trades:
        expiry_rows.append({"expiry_date": p.exit_date.normalize(), "max_loss": p.max_loss})
    if expiry_rows:
        exp_df = pd.DataFrame(expiry_rows)
        by_exp = exp_df.groupby("expiry_date")["max_loss"].sum()
        weights = by_exp / by_exp.sum()
        eff_count = 1.0 / (weights ** 2).sum() if len(weights) > 0 else 0
        max_conc = weights.max() * 100 if len(weights) > 0 else 100
    else:
        eff_count = 0
        max_conc = 0

    worst_pct_nlv = worst / NLV * 100
    gate_5pct = abs(worst_pct_nlv) <= GATE_WORST_TRADE_NLV * 100

    return {
        "variant": variant_name, "layer": layer, "n_trades": n_trades,
        "entries_per_yr": n_trades / years,
        "cum_pnl": cum_pnl, "ann_pnl_usd": ann_pnl, "ann_pnl_pct_nlv": ann_pnl_pct,
        "avg_pnl_per_trade": avg_pnl, "hit_rate_pct": hit,
        "worst_trade": worst, "worst_pct_nlv": worst_pct_nlv,
        "max_dd_pct": max_dd * 100,
        "w20d_pct": w20 * 100, "w63d_pct": w63 * 100,
        "sharpe": sharpe,
        "bp_mean": bp_mean, "bp_p95": bp_p95,
        "bp_mean_pct_nlv": bp_mean / NLV * 100,
        "bp_p95_pct_nlv": bp_p95 / NLV * 100,
        "effective_expiry_count": eff_count, "max_expiry_concentration_pct": max_conc,
        "gate_5pct_worst": gate_5pct,
    }

# ── Compute + report ────────────────────────────────────────────────
print("\n" + "=" * 70)
print("PORTFOLIO METRICS PER VARIANT (Layer 1 vs Layer 2)")
print("=" * 70)

metric_rows = []
for variant in ["V1b_weekly_catchup", "V3_daily_cluster", "BaselineB_cluster"]:
    for layer_name, trades, daily in [
        ("Layer1_shadow", layer1_trades[variant], layer1_daily[variant]),
        ("Layer2_production", layer2_trades[variant], layer2_daily[variant]),
    ]:
        m = compute_metrics(trades, daily, variant, layer_name)
        metric_rows.append(m)

metric_df = pd.DataFrame(metric_rows)
metric_df.to_csv(OUT / "q078_p2_portfolio_metrics.csv", index=False)

print(f"\n{'Variant':<22} {'Layer':<18} {'n_trades':>9} {'AnnROE%':>8} {'MaxDD%':>7} {'W20d%':>7} {'W63d%':>7} {'Worst%':>7} {'EffExp':>6} {'5%Gate'}")
print("-" * 110)
for _, r in metric_df.iterrows():
    gate = "✓" if r["gate_5pct_worst"] else "❌"
    print(f"{r['variant']:<22} {r['layer']:<18} {r['n_trades']:>9} "
          f"{r['ann_pnl_pct_nlv']:>+7.3f}% {r['max_dd_pct']:>+6.2f}% "
          f"{r['w20d_pct']:>+6.2f}% {r['w63d_pct']:>+6.2f}% "
          f"{r['worst_pct_nlv']:>+6.2f}% {r['effective_expiry_count']:>5.2f}  {gate}")

# ── Bias quantification (Layer 1 vs Layer 2) ────────────────────────
print("\n" + "=" * 70)
print("SELECTION BIAS QUANTIFIED (Layer 1 - Layer 2)")
print("=" * 70)
bias_rows = []
for variant in ["V1b_weekly_catchup", "V3_daily_cluster", "BaselineB_cluster"]:
    l1 = next((r for r in metric_rows if r["variant"] == variant and r["layer"] == "Layer1_shadow"), None)
    l2 = next((r for r in metric_rows if r["variant"] == variant and r["layer"] == "Layer2_production"), None)
    if not l1 or not l2:
        continue
    n_trade_reduction = (l1["n_trades"] - l2["n_trades"]) / l1["n_trades"] * 100 if l1["n_trades"] else 0
    pnl_reduction = (l1["ann_pnl_pct_nlv"] - l2["ann_pnl_pct_nlv"]) / l1["ann_pnl_pct_nlv"] * 100 if l1["ann_pnl_pct_nlv"] else 0
    print(f"\n[{variant}]")
    print(f"  Layer1 (shadow):     {l1['n_trades']} trades, +{l1['ann_pnl_pct_nlv']:.2f}% NLV/yr")
    print(f"  Layer2 (production): {l2['n_trades']} trades, +{l2['ann_pnl_pct_nlv']:.2f}% NLV/yr")
    print(f"  Production gates filtered: {n_trade_reduction:.0f}% of trades; PnL reduction: {pnl_reduction:.0f}%")
    bias_rows.append({
        "variant": variant,
        "layer1_trades": l1["n_trades"], "layer2_trades": l2["n_trades"],
        "trade_reduction_pct": n_trade_reduction,
        "layer1_ann_pnl_pct": l1["ann_pnl_pct_nlv"], "layer2_ann_pnl_pct": l2["ann_pnl_pct_nlv"],
        "pnl_reduction_pct": pnl_reduction,
        "layer2_w20d_pct": l2["w20d_pct"], "layer2_w63d_pct": l2["w63d_pct"],
        "layer2_max_dd_pct": l2["max_dd_pct"], "layer2_eff_expiry": l2["effective_expiry_count"],
    })
pd.DataFrame(bias_rows).to_csv(OUT / "q078_p2_bias_quantified.csv", index=False)

# ── Headline: V1b S3 / V3 S3 vs Baseline B (Layer 2 = production-realistic) ──
print("\n" + "=" * 70)
print("HEADLINE: Production-realistic (Layer 2) ladder vs Baseline B")
print("=" * 70)
base = next((r for r in metric_rows if r["variant"] == "BaselineB_cluster" and r["layer"] == "Layer2_production"), None)
if base:
    print(f"\nBaseline B Layer 2: {base['n_trades']} trades, ann PnL {base['ann_pnl_pct_nlv']:+.3f}% NLV, "
          f"W20d {base['w20d_pct']:+.2f}%, W63d {base['w63d_pct']:+.2f}%, MaxDD {base['max_dd_pct']:+.2f}%, "
          f"eff_count {base['effective_expiry_count']:.2f}")
    for variant in ["V1b_weekly_catchup", "V3_daily_cluster"]:
        r = next((m for m in metric_rows if m["variant"] == variant and m["layer"] == "Layer2_production"), None)
        if not r:
            continue
        d_pnl = r["ann_pnl_pct_nlv"] - base["ann_pnl_pct_nlv"]
        d_w20 = r["w20d_pct"] - base["w20d_pct"]
        d_w63 = r["w63d_pct"] - base["w63d_pct"]
        d_eff = r["effective_expiry_count"] - base["effective_expiry_count"]
        # Hard gate checks
        gate_v1 = abs(r["max_dd_pct"] / 100) <= 0.28
        gate_v2 = abs(r["w20d_pct"] / 100) <= 0.11
        gate_v3 = abs(r["w63d_pct"] / 100) <= 0.17
        gate_w20_deg = d_w20 >= -0.25
        gate_w63_deg = d_w63 >= -0.25
        gate_worst = r["gate_5pct_worst"]
        all_pass = gate_v1 and gate_v2 and gate_v3 and gate_w20_deg and gate_w63_deg and gate_worst
        verdict = ""
        if all_pass:
            if d_pnl >= 0.20:
                verdict = "STRONG PROMOTE"
            elif d_pnl >= 0.05:
                verdict = "SOFT PROMOTE"
            else:
                verdict = "DOCUMENT (sub-threshold)"
        else:
            verdict = "REJECT (hard gate fail)"
        print(f"\n{variant}: {r['n_trades']} trades, ann PnL {r['ann_pnl_pct_nlv']:+.3f}% NLV "
              f"(Δ vs base {d_pnl:+.3f}pp)")
        print(f"  W20d {r['w20d_pct']:+.2f}% (Δ {d_w20:+.2f}pp) / W63d {r['w63d_pct']:+.2f}% (Δ {d_w63:+.2f}pp) / MaxDD {r['max_dd_pct']:+.2f}%")
        print(f"  EffExp {r['effective_expiry_count']:.2f} (Δ {d_eff:+.2f}) / Worst {r['worst_pct_nlv']:+.2f}% NLV")
        print(f"  Hard gates: V1{'✓' if gate_v1 else '❌'} V2{'✓' if gate_v2 else '❌'} V3{'✓' if gate_v3 else '❌'} W20Δ{'✓' if gate_w20_deg else '❌'} W63Δ{'✓' if gate_w63_deg else '❌'} Worst{'✓' if gate_worst else '❌'}")
        print(f"  → {verdict}")

print("\n" + "=" * 70)
print("Q078 P2 done. CSVs in research/q078/")
print("=" * 70)
print("\nNote: Layer 2 metrics are production-realistic (concurrency + BP gates applied)")
print("Selection-bias correction = Layer 1 → Layer 2 trade/PnL reduction")
