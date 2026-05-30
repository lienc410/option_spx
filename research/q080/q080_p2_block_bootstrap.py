"""Q080 P2 — block bootstrap CI for ladder vs baseline ΔROE / Δtail metrics.

ChatGPT Q5 challenge: 20 seeds + independent (trade-level) bootstrap likely
underestimates CI width because daily PnL has autocorrelation. Fix:
  - 500 seeds
  - 5-day block bootstrap on the daily PnL series (preserves short-range
    autocorrelation; standard for time series)

Method
------
1. Compute a deterministic "reference" ladder daily PnL series (smoothed mode,
   seed=42 — chosen for consistency, the 5/95 CI will come from bootstrap not seed)
2. Compute combined_daily = baseline_daily + ladder_daily
3. Block-bootstrap combined_daily into 500 alternative paths (5-day blocks)
4. Compute Δ-metrics on each path vs same-path baseline
5. Report 5%/95% CI on each Δ-metric

Notes
-----
- Block bootstrap RESHUFFLES daily PnL blocks. It does NOT re-sample trades.
- This isolates time-series uncertainty (autocorrelation effect on CI width).
- For the trade-sampling uncertainty, the P1 distribution (20 seeds × 2 modes)
  already shows it is small (~0.1pp σ on ΔROE).

Compare
-------
  P4 / P1 reported:    ΔROE CI [+1.61, +1.97]
  Q080 P2 expectation: similar or wider (block bootstrap typically widens)

Output
------
  research/q080/q080_p2_results.csv         — per-bootstrap-replicate metrics
  research/q080/q080_p2_ci_table.csv        — CI table
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
AVG_HOLD_DAYS = 14
BP_CEILING_NORMAL = 0.35
BLOCK_SIZE = 5
N_BOOTSTRAPS = 500
REFERENCE_SEED = 42

CONCURRENCY_CAP = {
    "Bull Put Spread": 1, "Bull Put Spread (High Vol)": 1,
    "Iron Condor": 1, "Iron Condor (High Vol)": 2,
    "Bear Call Spread (High Vol)": 1, "Bull Call Diagonal": 1,
}

print("Q080 P2 — block bootstrap CI calibration", flush=True)
print("=" * 70)

# ── Load baseline + market frame ─────────────────────────────────────
df = pd.read_csv(P4_OUT / "q078_p4_baseline_daily.csv",
                 parse_dates=["date"], index_col="date")
print(f"Baseline days: {len(df):,}")

from signals.vix_regime import fetch_vix_history
from signals.trend import fetch_spx_history
vix_df = fetch_vix_history(period="max")
spx_df = fetch_spx_history(period="max")
vix_df.index = pd.to_datetime(vix_df.index.date)
spx_df.index = pd.to_datetime(spx_df.index.date)
mkt = pd.DataFrame({"vix": vix_df["vix"], "spx_close": spx_df["close"]}).dropna()
mkt = mkt[(mkt.index >= df.index.min()) & (mkt.index <= df.index.max())]


# ── Build ladder daily PnL using the reference seed (smoothed, the version
#    SPEC-108 was based on). Re-uses simulator from P4.
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


def simulate_ladder_daily(seed, mtm_mode):
    rng = np.random.default_rng(seed)
    positions = []
    ladder_daily = pd.Series(0.0, index=df.index)
    for d in df.index:
        if d not in sig_df.index:
            continue
        positions = [p for p in positions if p["exit"] > d]
        if d not in v3_eval:
            continue
        strat = sig_df.loc[d, "strategy"]
        if strat == "Reduce / Wait":
            continue
        cap = CONCURRENCY_CAP.get(strat, 1)
        if sum(1 for p in positions if p["strategy"] == strat) >= cap:
            continue
        current_bp = sum(p["max_loss"] for p in positions)
        new_max_loss = pool_by_strat.get(strat, [(0, 0)])[0][1] * SIZING_CONTRACTS
        if (current_bp + new_max_loss) / NLV > BP_CEILING_NORMAL:
            continue
        vix_at_entry = mkt.loc[d, "vix"] if d in mkt.index else 17
        pnl_per_ct, max_loss_per_ct = lookup_pnl_stratified(d, strat, vix_at_entry, rng)
        if pnl_per_ct is None:
            continue
        total_pnl = pnl_per_ct * SIZING_CONTRACTS
        total_max_loss = max_loss_per_ct * SIZING_CONTRACTS
        exit_d = d + pd.Timedelta(days=AVG_HOLD_DAYS)
        if mtm_mode == "smoothed":
            hold = pd.date_range(d, exit_d, freq="B")
            hold = [h for h in hold if h in ladder_daily.index]
            if hold:
                per_day = total_pnl / len(hold)
                for h in hold:
                    ladder_daily.loc[h] += per_day
        else:
            if exit_d in ladder_daily.index:
                ladder_daily.loc[exit_d] += total_pnl
            else:
                future = ladder_daily.index[ladder_daily.index >= exit_d]
                if len(future) > 0:
                    ladder_daily.loc[future[0]] += total_pnl
        positions.append({"entry": d, "exit": exit_d, "strategy": strat,
                          "pnl": total_pnl, "max_loss": total_max_loss})
    return ladder_daily


print("Building reference smoothed-mode ladder PnL (seed 42)...")
ladder_ref = simulate_ladder_daily(REFERENCE_SEED, "smoothed")
print(f"Ladder cum PnL: ${ladder_ref.sum():+,.0f}")


# ── Block bootstrap ──────────────────────────────────────────────────
baseline_pnl = df["baseline_pnl"].values
ladder_pnl = ladder_ref.reindex(df.index).fillna(0.0).values
combined_pnl = baseline_pnl + ladder_pnl
n_days = len(df)
n_blocks = n_days // BLOCK_SIZE


def compute_metrics(daily_pnl):
    eq = NLV + daily_pnl.cumsum()
    years = len(daily_pnl) / 252
    ann_roe = (eq[-1] / NLV) ** (1.0/years) - 1.0
    running_max = pd.Series(eq).cummax().values
    drawdown = (eq - running_max) / running_max
    max_dd = drawdown.min()
    daily_ret_series = pd.Series(daily_pnl) / pd.Series(eq).shift(1).fillna(NLV)
    w20 = daily_ret_series.rolling(20).sum().min()
    w63 = daily_ret_series.rolling(63).sum().min()
    sharpe = (daily_ret_series.mean() / daily_ret_series.std() * (252**0.5)
              if daily_ret_series.std() > 0 else 0)
    return ann_roe*100, max_dd*100, w20*100, w63*100, sharpe


# Baseline reference (no bootstrap)
b_roe, b_dd, b_w20, b_w63, b_sh = compute_metrics(baseline_pnl)
c_roe, c_dd, c_w20, c_w63, c_sh = compute_metrics(combined_pnl)
print()
print("Reference (single-path, no bootstrap):")
print(f"  baseline ann ROE  {b_roe:+.3f}   combined  {c_roe:+.3f}   Δ {c_roe-b_roe:+.3f}pp")
print(f"  baseline MaxDD    {b_dd:+.3f}    combined  {c_dd:+.3f}    Δ {c_dd-b_dd:+.3f}pp")
print(f"  baseline W20d     {b_w20:+.3f}    combined  {c_w20:+.3f}    Δ {c_w20-b_w20:+.3f}pp")
print(f"  baseline W63d     {b_w63:+.3f}    combined  {c_w63:+.3f}    Δ {c_w63-b_w63:+.3f}pp")
print(f"  baseline Sharpe   {b_sh:+.3f}    combined  {c_sh:+.3f}    Δ {c_sh-b_sh:+.3f}")
print()


# Build blocks: list of (block_baseline_pnl_arr, block_ladder_pnl_arr) so they
# stay paired (preserves correlation between baseline + ladder within each block)
blocks_baseline = [baseline_pnl[i*BLOCK_SIZE:(i+1)*BLOCK_SIZE] for i in range(n_blocks)]
blocks_ladder = [ladder_pnl[i*BLOCK_SIZE:(i+1)*BLOCK_SIZE] for i in range(n_blocks)]

# Handle remainder
remainder_baseline = baseline_pnl[n_blocks*BLOCK_SIZE:]
remainder_ladder = ladder_pnl[n_blocks*BLOCK_SIZE:]

print(f"Block bootstrap: {n_blocks} blocks × {BLOCK_SIZE} days, {N_BOOTSTRAPS} replicates")
print()

bootstrap_results = []
rng = np.random.default_rng(20260529)
for b in range(N_BOOTSTRAPS):
    # Sample blocks with replacement, same length as original series
    idxs = rng.integers(0, n_blocks, size=n_blocks)
    baseline_resampled = np.concatenate([blocks_baseline[i] for i in idxs])
    ladder_resampled = np.concatenate([blocks_ladder[i] for i in idxs])
    if len(remainder_baseline) > 0:
        baseline_resampled = np.concatenate([baseline_resampled, remainder_baseline])
        ladder_resampled = np.concatenate([ladder_resampled, remainder_ladder])
    combined_resampled = baseline_resampled + ladder_resampled

    b_m = compute_metrics(baseline_resampled)
    c_m = compute_metrics(combined_resampled)
    bootstrap_results.append({
        "rep": b,
        "delta_roe_pp":   c_m[0] - b_m[0],
        "delta_maxdd_pp": c_m[1] - b_m[1],
        "delta_w20d_pp":  c_m[2] - b_m[2],
        "delta_w63d_pp":  c_m[3] - b_m[3],
        "delta_sharpe":   c_m[4] - b_m[4],
        "baseline_roe":   b_m[0],
        "combined_roe":   c_m[0],
    })
    if (b+1) % 100 == 0:
        print(f"  {b+1}/{N_BOOTSTRAPS} done", flush=True)


bp_df = pd.DataFrame(bootstrap_results)
bp_df.to_csv(OUT / "q080_p2_results.csv", index=False)


# ── CI table ─────────────────────────────────────────────────────────
def summary(s):
    return {
        "mean":   s.mean(),
        "median": s.median(),
        "std":    s.std(),
        "p05":    s.quantile(0.05),
        "p25":    s.quantile(0.25),
        "p75":    s.quantile(0.75),
        "p95":    s.quantile(0.95),
        "worst":  s.min(),
        "best":   s.max(),
    }

ci_rows = []
for metric in ("delta_roe_pp", "delta_maxdd_pp", "delta_w20d_pp", "delta_w63d_pp", "delta_sharpe"):
    s = summary(bp_df[metric])
    s["metric"] = metric
    ci_rows.append(s)
ci_df = pd.DataFrame(ci_rows)
ci_df.to_csv(OUT / "q080_p2_ci_table.csv", index=False)


# ── Print ────────────────────────────────────────────────────────────
print()
print("=" * 100)
print(f"Block bootstrap CI (5-day blocks × {N_BOOTSTRAPS} replicates)")
print("=" * 100)
print(f"{'metric':<18} {'mean':>10} {'σ':>8} {'p05':>10} {'p95':>10} "
      f"{'CI width':>12} {'P4/P1 CI':>22}")
print("-" * 100)
p4_ci = {
    "delta_roe_pp":   ("+1.61", "+1.97", 0.36),
    "delta_maxdd_pp": ("-0.64", "+3.32", 3.96),
    "delta_w20d_pp":  ("-0.80", "+3.14", 3.94),
    "delta_w63d_pp":  ("+0.51", "+5.62", 5.11),
    "delta_sharpe":   ("+1.00", "+1.36", 0.36),
}
for metric in ("delta_roe_pp", "delta_maxdd_pp", "delta_w20d_pp", "delta_w63d_pp", "delta_sharpe"):
    s = bp_df[metric]
    width = s.quantile(0.95) - s.quantile(0.05)
    lo, hi, w_p4 = p4_ci[metric]
    multiplier = width / w_p4 if w_p4 > 0 else 0
    print(f"{metric:<18} {s.mean():+10.3f} {s.std():>8.3f} {s.quantile(0.05):+10.3f} "
          f"{s.quantile(0.95):+10.3f} {width:>12.3f} "
          f"[{lo}, {hi}] (×{multiplier:.1f})")
print()
print("CI 'multiplier' = block-bootstrap CI width / P4 trade-bootstrap CI width.")
print("Multiplier > 1 → block bootstrap gives a wider (honest) CI.")
print("Multiplier ≈ 1 → P4 CI was already representative.")


# ── Verdict ──────────────────────────────────────────────────────────
print()
print("=" * 100)
print("VERDICT")
print("=" * 100)
roe_p05 = bp_df["delta_roe_pp"].quantile(0.05)
if roe_p05 > 0:
    print(f"ΔROE p05 = {roe_p05:+.3f}pp > 0 → ΔROE 仍 robustly positive even after block bootstrap.")
else:
    print(f"ΔROE p05 = {roe_p05:+.3f}pp ≤ 0 → ΔROE NOT robust after block bootstrap; P4 CI was too narrow.")

w20_p05 = bp_df["delta_w20d_pp"].quantile(0.05)
w63_p05 = bp_df["delta_w63d_pp"].quantile(0.05)
print(f"ΔW20d p05 = {w20_p05:+.3f}pp")
print(f"ΔW63d p05 = {w63_p05:+.3f}pp")
if w20_p05 < 0 or w63_p05 < 0:
    print("⚠ Tail-improvement claim partially breaks under block bootstrap — p05 negative; "
          "SPEC-108 tail benefit is mean-positive but not lower-CI-robust.")
else:
    print("Tail improvement (W20d/W63d) robust at 5% CI.")
