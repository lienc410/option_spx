"""Q080 P1 — unsmoothed MTM control vs Q078 P4 daily-linear smoothing.

Critical-path test of ChatGPT Q4 challenge: does linear MTM smoothing across
hold days artificially inflate ladder's tail improvement (W20d / W63d / MaxDD)?

Method
------
Re-run Q078 P4 portfolio integration with two MTM modes side-by-side:

  smoothed   (current default, Q078 P2 REVISED → P4):
             total_pnl / len(hold_days) → distributed across all hold biz days

  unsmoothed (Q080 P1 control):
             total_pnl booked entirely on exit_date (single-day spike)

Both modes use:
  - identical engine 26y trade pool (stratified by strategy × year × VIX bucket)
  - identical V3 cadence (≤1 entry per 5 trading days)
  - identical S3 sizing (3 contracts)
  - identical production gates (concurrency + 35% BP ceiling)
  - identical 20 seeds (seed 42..61)
  - identical baseline (SPEC-104 + SPEC-105 v2)

Compare per-metric (mean + 5/95 CI):
  - ΔAnnROE pp
  - ΔMaxDD pp
  - ΔW20d pp
  - ΔW63d pp
  - ΔSharpe

Verdict rules
-------------
  ΔROE invariant (smoothing is PnL-preserving)        → expected
  ΔMaxDD: unsmoothed worse (single-day spike)          → confirms smoothing
                                                          masks single-day DD
  ΔW20d / ΔW63d: critical. If unsmoothed shows similar
                  +pp improvement → SPEC-108 tail claim robust
                  If unsmoothed shows ≈baseline or
                  net-negative → SPEC-108 tail claim
                  was smoothing artifact

Outputs
-------
  research/q080/q080_p1_results.csv
  research/q080/q080_p1_distribution.csv
  printed verdict (also persisted in memo separately)
"""

from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
OUT = REPO / "research" / "q080"
P4_OUT = REPO / "research" / "q078"

NLV = 894_000.0
SPX_TODAY = 7400.0
SIZING_CONTRACTS = 3
N_SEEDS = 20
AVG_HOLD_DAYS = 14
BP_CEILING_NORMAL = 0.35

# Baseline allocation constants (mirror P4)
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


print("Q080 P1 — Unsmoothed MTM control vs P4 smoothed", flush=True)
print("=" * 70)

# ── Reuse P4 baseline daily series (already saved) ───────────────────
baseline_path = P4_OUT / "q078_p4_baseline_daily.csv"
if not baseline_path.exists():
    print(f"FATAL: P4 baseline cache missing at {baseline_path}; re-run P4 first")
    sys.exit(1)

df = pd.read_csv(baseline_path, parse_dates=["date"], index_col="date")
print(f"Loaded P4 baseline: {len(df):,} days, total PnL ${df['baseline_pnl'].sum():+,.0f}")

# ── Load market frame (for VIX at entry) ─────────────────────────────
from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history
vix_df = fetch_vix_history(period="max")
spx_df = fetch_spx_history(period="max")
vix_df.index = pd.to_datetime(vix_df.index.date)
spx_df.index = pd.to_datetime(spx_df.index.date)
mkt = pd.DataFrame({"vix": vix_df["vix"], "spx_close": spx_df["close"]}).dropna()
mkt = mkt[(mkt.index >= df.index.min()) & (mkt.index <= df.index.max())]
print(f"Loaded market frame: VIX days {len(mkt)}")

# ── Load engine trades pool (same as P4) ─────────────────────────────
print("Loading engine 26y trades pool...")
trades_df = pd.read_csv(P4_OUT / "_engine_trades_26y_cache.csv", parse_dates=["entry_date"])
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

pool_by_strat = {}
for strat in trades_df["strategy"].unique():
    sub = trades_df[trades_df["strategy"] == strat]
    pool_by_strat[strat] = list(zip(
        sub["pnl_today_per_ct"].tolist(),
        sub["max_loss_today_per_ct"].tolist(),
    ))

# ── Load signal history + V3 eval days ───────────────────────────────
sig_df = pd.read_csv(P4_OUT / "_signal_history_cache.csv", parse_dates=["date"])
sig_df = sig_df.set_index("date").sort_index()

v3_eval = set()
last = None
for d in sig_df.index:
    if last is not None and (d - last).days < 5:
        continue
    if sig_df.loc[d, "strategy"] != "Reduce / Wait":
        v3_eval.add(d)
        last = d
print(f"V3 eval days: {len(v3_eval)}")

# ── Stratified PnL lookup (same as P4) ───────────────────────────────
def lookup_pnl_stratified(entry_date, strategy_name, vix_val, rng):
    yb = year_bucket(entry_date.year)
    vb = vix_bucket(vix_val)
    key = (strategy_name, yb, vb)
    if key in pool_2axis and pool_2axis[key]:
        pool = pool_2axis[key]
        idx = rng.integers(0, len(pool))
        return pool[idx]
    if strategy_name in pool_by_strat and pool_by_strat[strategy_name]:
        pool = pool_by_strat[strategy_name]
        idx = rng.integers(0, len(pool))
        return pool[idx]
    return None, None


# ── Parameterized simulator ─────────────────────────────────────────
def simulate_ladder_daily(eval_set, n_contracts, seed, mtm_mode: str):
    """Simulate ladder PnL with selectable MTM booking mode.

    mtm_mode='smoothed'   → P4 default: pnl / len(hold) per business day
    mtm_mode='unsmoothed' → Q080 control: full pnl on exit_date only
    """
    assert mtm_mode in ("smoothed", "unsmoothed")
    rng = np.random.default_rng(seed)
    positions = []
    ladder_daily = pd.Series(0.0, index=df.index)
    bp_daily = pd.Series(0.0, index=df.index)
    n_trades = 0

    for d in df.index:
        if d not in sig_df.index:
            continue
        positions = [p for p in positions if p["exit"] > d]

        if d not in eval_set:
            bp_daily.loc[d] = sum(p["max_loss"] for p in positions)
            continue
        strat = sig_df.loc[d, "strategy"]
        if strat == "Reduce / Wait":
            bp_daily.loc[d] = sum(p["max_loss"] for p in positions)
            continue

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

        vix_at_entry = mkt.loc[d, "vix"] if d in mkt.index else 17
        pnl_per_ct, max_loss_per_ct = lookup_pnl_stratified(d, strat, vix_at_entry, rng)
        if pnl_per_ct is None:
            bp_daily.loc[d] = current_bp
            continue

        total_pnl = pnl_per_ct * n_contracts
        total_max_loss = max_loss_per_ct * n_contracts
        exit_d = d + pd.Timedelta(days=AVG_HOLD_DAYS)

        if mtm_mode == "smoothed":
            hold = pd.date_range(d, exit_d, freq="B")
            hold = [h for h in hold if h in ladder_daily.index]
            if hold:
                per_day = total_pnl / len(hold)
                for h in hold:
                    ladder_daily.loc[h] += per_day
        else:
            # unsmoothed: book full PnL on exit_date (single-day spike)
            # if exit_d not exactly in index, snap to nearest forward index date
            if exit_d in ladder_daily.index:
                ladder_daily.loc[exit_d] += total_pnl
            else:
                future = ladder_daily.index[ladder_daily.index >= exit_d]
                if len(future) > 0:
                    ladder_daily.loc[future[0]] += total_pnl

        positions.append({"entry": d, "exit": exit_d, "strategy": strat,
                          "pnl": total_pnl, "max_loss": total_max_loss})
        bp_daily.loc[d] = current_bp + total_max_loss
        n_trades += 1

    return ladder_daily, bp_daily, n_trades


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


# ── Baseline metrics ─────────────────────────────────────────────────
baseline_metrics = compute_metrics_from_daily(df["baseline_pnl"], df.index, "baseline")
print()
print("Baseline SPEC-104+105v2 (no ladder):")
for k in ("ann_roe_pct", "max_dd_pct", "w20d_pct", "w63d_pct", "sharpe"):
    print(f"  {k}: {baseline_metrics[k]:+.3f}")


# ── 20-seed sweep for BOTH modes ─────────────────────────────────────
results = []
for seed in range(N_SEEDS):
    for mode in ("smoothed", "unsmoothed"):
        ladder_daily, bp_daily, n_tr = simulate_ladder_daily(
            v3_eval, SIZING_CONTRACTS, seed=42+seed, mtm_mode=mode)
        combined = df["baseline_pnl"] + ladder_daily
        m = compute_metrics_from_daily(combined, df.index, f"{mode}_seed{seed}")
        m.update({
            "seed": seed,
            "mtm_mode": mode,
            "ladder_cum_pnl": ladder_daily.sum(),
            "n_trades": n_tr,
            "delta_roe_pp": m["ann_roe_pct"] - baseline_metrics["ann_roe_pct"],
            "delta_maxdd_pp": m["max_dd_pct"] - baseline_metrics["max_dd_pct"],
            "delta_w20d_pp": m["w20d_pct"] - baseline_metrics["w20d_pct"],
            "delta_w63d_pp": m["w63d_pct"] - baseline_metrics["w63d_pct"],
            "delta_sharpe": m["sharpe"] - baseline_metrics["sharpe"],
        })
        results.append(m)
    print(f"  seed {seed+1:2d}/{N_SEEDS} done", flush=True)


res = pd.DataFrame(results)
res.to_csv(OUT / "q080_p1_results.csv", index=False)
print(f"\nSaved {len(res)} rows → q080_p1_results.csv")


# ── Distribution summary per metric × mode ───────────────────────────
def summarize(group):
    return pd.Series({
        "mean":   group.mean(),
        "median": group.median(),
        "p05":    group.quantile(0.05),
        "p95":    group.quantile(0.95),
        "std":    group.std(),
        "worst":  group.min(),
        "best":   group.max(),
    })

metrics = ["delta_roe_pp", "delta_maxdd_pp", "delta_w20d_pp", "delta_w63d_pp",
           "delta_sharpe", "n_trades", "ladder_cum_pnl"]
dist_rows = []
for metric in metrics:
    for mode in ("smoothed", "unsmoothed"):
        sub = res[res["mtm_mode"] == mode][metric]
        s = summarize(sub)
        s["metric"] = metric
        s["mode"] = mode
        dist_rows.append(s)
dist = pd.DataFrame(dist_rows)
dist.to_csv(OUT / "q080_p1_distribution.csv", index=False)
print(f"Saved distribution summary → q080_p1_distribution.csv")


# ── Print side-by-side comparison ────────────────────────────────────
print()
print("=" * 100)
print("SIDE-BY-SIDE — smoothed vs unsmoothed (20 seeds)")
print("=" * 100)
print(f"{'metric':<22} {'smoothed mean':>15} {'unsmoothed mean':>17} "
      f"{'Δ (un−sm)':>13} {'smoothed 5/95':>20} {'unsmoothed 5/95':>22}")
print("-" * 100)
for metric in ("delta_roe_pp", "delta_maxdd_pp", "delta_w20d_pp", "delta_w63d_pp", "delta_sharpe"):
    sm = res[res["mtm_mode"] == "smoothed"][metric]
    un = res[res["mtm_mode"] == "unsmoothed"][metric]
    sm_ci = f"[{sm.quantile(0.05):+.2f}, {sm.quantile(0.95):+.2f}]"
    un_ci = f"[{un.quantile(0.05):+.2f}, {un.quantile(0.95):+.2f}]"
    delta_means = un.mean() - sm.mean()
    print(f"{metric:<22} {sm.mean():+15.3f} {un.mean():+17.3f} {delta_means:+13.3f} "
          f"{sm_ci:>20} {un_ci:>22}")
print()

# Trade count sanity
print(f"Avg n_trades smoothed:   {res[res.mtm_mode=='smoothed']['n_trades'].mean():.1f}")
print(f"Avg n_trades unsmoothed: {res[res.mtm_mode=='unsmoothed']['n_trades'].mean():.1f}  (should match)")
print(f"Avg cum PnL smoothed:    ${res[res.mtm_mode=='smoothed']['ladder_cum_pnl'].mean():+,.0f}")
print(f"Avg cum PnL unsmoothed:  ${res[res.mtm_mode=='unsmoothed']['ladder_cum_pnl'].mean():+,.0f}  (should match)")

# ── Verdict logic ────────────────────────────────────────────────────
print()
print("=" * 100)
print("VERDICT")
print("=" * 100)
sm_w20 = res[res.mtm_mode=='smoothed']['delta_w20d_pp'].mean()
un_w20 = res[res.mtm_mode=='unsmoothed']['delta_w20d_pp'].mean()
sm_w63 = res[res.mtm_mode=='smoothed']['delta_w63d_pp'].mean()
un_w63 = res[res.mtm_mode=='unsmoothed']['delta_w63d_pp'].mean()
sm_roe = res[res.mtm_mode=='smoothed']['delta_roe_pp'].mean()
un_roe = res[res.mtm_mode=='unsmoothed']['delta_roe_pp'].mean()

print(f"ΔROE   smoothed={sm_roe:+.3f}pp   unsmoothed={un_roe:+.3f}pp   "
      f"diff={un_roe-sm_roe:+.3f}pp  (expected ~0 since PnL preserved)")
print(f"ΔW20d  smoothed={sm_w20:+.3f}pp   unsmoothed={un_w20:+.3f}pp   "
      f"diff={un_w20-sm_w20:+.3f}pp  (← critical: if diff < 0, smoothing inflated tail benefit)")
print(f"ΔW63d  smoothed={sm_w63:+.3f}pp   unsmoothed={un_w63:+.3f}pp   "
      f"diff={un_w63-sm_w63:+.3f}pp  (← critical)")
print()

if un_w20 >= sm_w20 - 0.5 and un_w63 >= sm_w63 - 0.5:
    print("VERDICT: SPEC-108 tail claims SURVIVE — unsmoothed within 0.5pp of smoothed.")
elif un_w20 < 0 or un_w63 < 0:
    print("VERDICT: SPEC-108 tail claims COLLAPSE — unsmoothed shows ladder NET HURTS tail.")
else:
    print("VERDICT: SPEC-108 tail claims DEFLATE — unsmoothed materially smaller but still positive.")
print()
print("(Detailed memo + recommendation in research/q080/q080_p1_memo.md)")
