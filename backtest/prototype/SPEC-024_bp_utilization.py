"""
SPEC-024: BP Utilization Research
2026-03-30

Research questions:
1. Root cause: why is average BP utilization only ~7% despite 25-50% ceiling?
2. Position sizing scaling: what happens to Sharpe/Calmar/MaxDD at bp_target = 7%, 10%?
3. T-bill overlay: how much does risk-free yield on idle capital add to total returns?
4. Which constraint is binding: signal frequency or BP ceiling?

Usage:
    python -m backtest.prototype.SPEC-024_bp_utilization
"""

from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import math
import numpy as np
import pandas as pd

from backtest.engine import run_backtest, compute_metrics
from strategy.selector import StrategyParams


# ── Config ────────────────────────────────────────────────────────────────────
ACCOUNT_SIZE   = 150_000.0
START_5YR      = "2021-01-01"
START_26YR     = "2000-01-01"
RISK_FREE_RATE = 0.045   # ~4.5% annualized T-bill (conservative 2021-2026 avg)


# ══════════════════════════════════════════════════════════════════════════════
# Part 1 — Root Cause Analysis: BP Utilization Distribution
# ══════════════════════════════════════════════════════════════════════════════

def analyze_bp_utilization(trades, signal_history, account_size, label=""):
    """
    Compute daily BP utilization from trade records and signal history.
    Reconstructs approximate daily BP usage by tracking open positions over time.
    """
    if not trades:
        print(f"[{label}] No trades.")
        return {}

    trade_periods = []
    for t in trades:
        if t.exit_date and t.entry_date:
            trade_periods.append({
                "entry": pd.Timestamp(t.entry_date),
                "exit":  pd.Timestamp(t.exit_date),
                "bp":    t.total_bp,
            })

    if not trade_periods:
        return {}

    # Build daily BP time series
    all_dates = pd.date_range(
        start=min(p["entry"] for p in trade_periods),
        end=max(p["exit"] for p in trade_periods),
        freq="B"
    )
    daily_bp = pd.Series(0.0, index=all_dates)
    for p in trade_periods:
        mask = (daily_bp.index >= p["entry"]) & (daily_bp.index < p["exit"])
        daily_bp[mask] += p["bp"]

    daily_bp_pct = daily_bp / account_size * 100

    # Filter to trading days with any market activity (non-zero region)
    active_days = daily_bp_pct[daily_bp_pct > 0]
    zero_days   = daily_bp_pct[daily_bp_pct == 0]

    print(f"\n{'='*60}")
    print(f"  BP Utilization Analysis — {label}")
    print(f"{'='*60}")
    print(f"  Total trades:          {len(trades)}")
    print(f"  Trading days analyzed: {len(daily_bp_pct)}")
    print(f"  Days with BP > 0:      {len(active_days)} ({len(active_days)/len(daily_bp_pct)*100:.1f}%)")
    print(f"  Days with BP = 0:      {len(zero_days)} ({len(zero_days)/len(daily_bp_pct)*100:.1f}%)")
    print()
    print(f"  BP utilization (ALL days incl. zero):")
    print(f"    Mean:   {daily_bp_pct.mean():.1f}%")
    print(f"    Median: {daily_bp_pct.median():.1f}%")
    print(f"    P75:    {daily_bp_pct.quantile(0.75):.1f}%")
    print(f"    P90:    {daily_bp_pct.quantile(0.90):.1f}%")
    print(f"    Max:    {daily_bp_pct.max():.1f}%")
    print()
    print(f"  BP utilization (days WITH positions):")
    if len(active_days) > 0:
        print(f"    Mean:   {active_days.mean():.1f}%")
        print(f"    Median: {active_days.median():.1f}%")
        print(f"    P75:    {active_days.quantile(0.75):.1f}%")
        print(f"    Max:    {active_days.max():.1f}%")
    print()

    # Concurrent position count distribution
    concurrent_counts = {}
    for i in range(1, 8):
        n_days = len(daily_bp_pct[daily_bp_pct >= i * 3.0])
        concurrent_counts[f"BP≥{i*3}%"] = n_days
    print(f"  Days by approximate concurrent positions:")
    for k, v in concurrent_counts.items():
        print(f"    {k}: {v} days")

    return {
        "mean_bp_all":    daily_bp_pct.mean(),
        "mean_bp_active": active_days.mean() if len(active_days) > 0 else 0,
        "pct_days_active": len(active_days) / len(daily_bp_pct) * 100,
        "max_bp":         daily_bp_pct.max(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Part 2 — Position Sizing Scale Test
# ══════════════════════════════════════════════════════════════════════════════

SIZING_SCENARIOS = [
    # label, bp_target_normal, bp_target_high_vol, bp_target_low_vol
    ("Baseline (5% / 3.5%)",  0.05,  0.035, 0.05),
    ("Scale 1.5× (7.5% / 5%)", 0.075, 0.05,  0.075),
    ("Scale 2× (10% / 7%)",    0.10,  0.07,  0.10),
    ("Scale 2.5× (12% / 8%)",  0.12,  0.08,  0.12),
]


def run_sizing_scenarios(start_date, label_prefix):
    print(f"\n{'='*60}")
    print(f"  Sizing Scale Test — {label_prefix} (from {start_date})")
    print(f"{'='*60}")
    print(f"  {'Scenario':<28} {'Trades':>6} {'WR':>6} {'Sharpe':>7} {'Calmar':>7} "
          f"{'MaxDD':>8} {'TotalPnL':>10} {'AvgBP%':>7}")
    print(f"  {'-'*28} {'-'*6} {'-'*6} {'-'*7} {'-'*7} {'-'*8} {'-'*10} {'-'*7}")

    results = []
    for label, bt_n, bt_hv, bt_lv in SIZING_SCENARIOS:
        params = StrategyParams(
            bp_target_normal   = bt_n,
            bp_target_high_vol = bt_hv,
            bp_target_low_vol  = bt_lv,
            # ceilings scale proportionally
            bp_ceiling_normal   = min(bt_n * 7, 0.70),
            bp_ceiling_high_vol = min(bt_hv * 14, 0.70),
            bp_ceiling_low_vol  = min(bt_lv * 5, 0.50),
        )
        try:
            trades, metrics, sig_hist = run_backtest(
                start_date=start_date,
                account_size=ACCOUNT_SIZE,
                params=params,
            )
        except Exception as e:
            print(f"  {label:<28}  ERROR: {e}")
            continue

        m = metrics
        n = m.get("total_trades", 0)
        wr = m.get("win_rate", 0) * 100
        sharpe = m.get("sharpe", 0)
        calmar = m.get("calmar", 0)
        maxdd  = m.get("max_drawdown", 0)
        tpnl   = m.get("total_pnl", 0)
        avg_bp = (sum(t.total_bp for t in trades) / n / ACCOUNT_SIZE * 100) if n > 0 else 0

        print(f"  {label:<28} {n:>6} {wr:>5.1f}% {sharpe:>7.2f} {calmar:>7.1f} "
              f"${maxdd:>7,.0f} ${tpnl:>9,.0f} {avg_bp:>6.1f}%")

        results.append({
            "label": label,
            "bp_target_normal": bt_n,
            "trades": n,
            "win_rate": wr,
            "sharpe": sharpe,
            "calmar": calmar,
            "max_drawdown": maxdd,
            "total_pnl": tpnl,
            "avg_bp_per_trade": avg_bp,
            "cvar5": m.get("cvar5", 0),
            "skew": m.get("skew", 0),
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# Part 3 — T-Bill Overlay: Risk-Free Yield on Idle Capital
# ══════════════════════════════════════════════════════════════════════════════

def compute_tbill_overlay(bp_util_results_by_scenario, account_size, rfr, start_date, end_date_approx):
    """
    Estimate additional yield from investing idle margin in T-bills/SOFR.
    Idle capital = account_size × (1 - daily_bp_pct / 100)
    """
    # Calendar days in backtest window
    n_years = (pd.Timestamp(end_date_approx) - pd.Timestamp(start_date)).days / 365.25

    print(f"\n{'='*60}")
    print(f"  T-Bill Overlay Estimate ({start_date} to {end_date_approx})")
    print(f"  Assumptions: RFR={rfr*100:.1f}%, Account=${account_size:,.0f}")
    print(f"{'='*60}")
    print(f"  {'Scenario':<28} {'AvgIdleBP%':>10} {'AnnlOvrlayPnL':>14} {'TotalOvrlayPnL':>15}")
    print(f"  {'-'*28} {'-'*10} {'-'*14} {'-'*15}")

    for scenario_name, mean_bp_pct in bp_util_results_by_scenario.items():
        idle_pct = max(0, 100 - mean_bp_pct) / 100
        # T-bill yield only on non-margin portion; PM accounts typically
        # receive ~80% of T-bill rate on idle cash (broker sweep rate)
        broker_rate = rfr * 0.80
        annual_overlay = account_size * idle_pct * broker_rate
        total_overlay  = annual_overlay * n_years
        print(f"  {scenario_name:<28} {mean_bp_pct:>9.1f}%  ${annual_overlay:>12,.0f}  ${total_overlay:>13,.0f}")

    print()
    print(f"  Note: at BP utilization=7%, idle=93%, annual T-bill overlay ≈ "
          f"${account_size*0.93*rfr*0.80:,.0f}/yr")
    print(f"  This is risk-free — no strategy change required.")
    print(f"  Schwab/tastytrade pay ~80–85% of SOFR on idle PM cash balances.")


# ══════════════════════════════════════════════════════════════════════════════
# Part 4 — Binding Constraint Analysis
# ══════════════════════════════════════════════════════════════════════════════

def analyze_binding_constraint(trades, signal_history, params, label=""):
    """
    Determine whether low utilization is caused by:
    A) Signal frequency (not enough OPEN signals generated)
    B) BP ceiling (OPEN signals rejected due to ceiling)
    C) Dedup (OPEN signals rejected due to same-strategy already open)
    D) Spell throttle (OPEN signals rejected due to HV spell age/count)
    """
    print(f"\n{'='*60}")
    print(f"  Binding Constraint Analysis — {label}")
    print(f"{'='*60}")

    if not signal_history:
        print("  No signal history.")
        return

    total_days = len(signal_history)
    reduce_wait_days = sum(1 for s in signal_history if s.get("strategy") == "Reduce / Wait")
    active_signal_days = total_days - reduce_wait_days

    print(f"  Total trading days:          {total_days}")
    print(f"  Days with REDUCE_WAIT signal: {reduce_wait_days} ({reduce_wait_days/total_days*100:.1f}%)")
    print(f"  Days with actionable signal:  {active_signal_days} ({active_signal_days/total_days*100:.1f}%)")
    print()

    # Signal distribution by regime
    regime_counts = {}
    for s in signal_history:
        r = s.get("regime", "UNKNOWN")
        regime_counts[r] = regime_counts.get(r, 0) + 1
    print(f"  Regime distribution:")
    for r, cnt in sorted(regime_counts.items()):
        print(f"    {r:<15} {cnt:>5} days ({cnt/total_days*100:.1f}%)")
    print()

    # Strategy signal distribution
    strat_counts = {}
    for s in signal_history:
        st = s.get("strategy", "UNKNOWN")
        strat_counts[st] = strat_counts.get(st, 0) + 1
    print(f"  Strategy signal distribution:")
    for st, cnt in sorted(strat_counts.items(), key=lambda x: -x[1]):
        print(f"    {st:<30} {cnt:>5} days ({cnt/total_days*100:.1f}%)")
    print()

    # Actual entries vs signal days
    n_entries = len(trades)
    print(f"  Actual entries:              {n_entries}")
    if active_signal_days > 0:
        print(f"  Entry rate on active days:   {n_entries/active_signal_days*100:.1f}%")
    print()

    # Estimate "missed" opportunities: consecutive same-strategy runs
    # Each run of the same strategy day-over-day represents dedup blocking re-entry
    strategy_runs = []
    current_strat = None
    run_len = 0
    for s in signal_history:
        st = s.get("strategy")
        if st == current_strat and st != "Reduce / Wait":
            run_len += 1
        else:
            if run_len > 1:
                strategy_runs.append(run_len)
            current_strat = st
            run_len = 1

    if strategy_runs:
        avg_run = sum(strategy_runs) / len(strategy_runs)
        print(f"  Consecutive same-strategy signal runs:")
        print(f"    Count:     {len(strategy_runs)}")
        print(f"    Avg length:{avg_run:.1f} days")
        print(f"    Max length:{max(strategy_runs)} days")
        print(f"    → Each run = 1 entry; dedup blocks {avg_run-1:.1f} extra entries on average")
    print()

    # HV spell age stats
    hv_ages = [s.get("hv_spell_age", 0) for s in signal_history if s.get("hv_spell_age", 0) > 0]
    if hv_ages:
        print(f"  HIGH_VOL spell age distribution (days with HV positions):")
        ages = pd.Series(hv_ages)
        print(f"    Mean:  {ages.mean():.1f}d")
        print(f"    Median:{ages.median():.1f}d")
        print(f"    Max:   {ages.max():.0f}d")
        blocked_by_age = sum(1 for a in hv_ages if a > params.spell_age_cap)
        print(f"    Days where spell_age > {params.spell_age_cap}: {blocked_by_age}")


# ══════════════════════════════════════════════════════════════════════════════
# Part 5 — Ceiling Sensitivity: How many MORE positions could enter if ceiling raised?
# ══════════════════════════════════════════════════════════════════════════════

def run_ceiling_sensitivity(start_date):
    """
    Test whether raising bp_ceiling allows more concurrent positions.
    If results don't change → ceiling is not binding (signal frequency is).
    """
    print(f"\n{'='*60}")
    print(f"  Ceiling Sensitivity — {start_date}")
    print(f"{'='*60}")

    ceiling_scenarios = [
        ("Current ceilings",    0.25, 0.35, 0.50),
        ("Double ceilings",     0.50, 0.70, 0.80),
        ("Uncapped (90%)",      0.90, 0.90, 0.90),
    ]

    print(f"  {'Scenario':<22} {'Trades':>6} {'Sharpe':>7} {'TotalPnL':>10} {'AvgBP%':>7}")
    print(f"  {'-'*22} {'-'*6} {'-'*7} {'-'*10} {'-'*7}")

    for label, cl_lv, cl_n, cl_hv in ceiling_scenarios:
        params = StrategyParams(
            bp_ceiling_low_vol  = cl_lv,
            bp_ceiling_normal   = cl_n,
            bp_ceiling_high_vol = cl_hv,
        )
        try:
            trades, metrics, _ = run_backtest(start_date=start_date, account_size=ACCOUNT_SIZE, params=params)
        except Exception as e:
            print(f"  {label:<22}  ERROR: {e}")
            continue
        n     = metrics.get("total_trades", 0)
        s     = metrics.get("sharpe", 0)
        tpnl  = metrics.get("total_pnl", 0)
        avg_bp = (sum(t.total_bp for t in trades) / n / ACCOUNT_SIZE * 100) if n > 0 else 0
        print(f"  {label:<22} {n:>6} {s:>7.2f} ${tpnl:>9,.0f} {avg_bp:>6.1f}%")


# ══════════════════════════════════════════════════════════════════════════════
# Part 6 — Multi-Underlying Correlation Check
# ══════════════════════════════════════════════════════════════════════════════

def analyze_underlying_correlation():
    """
    Check SPY / QQQ / IWM correlation with SPX during HIGH_VOL regimes.
    If all corr → 1.0 in stress, adding them doesn't diversify — it just
    concentrates the same short-vol bet.
    """
    try:
        import yfinance as yf
        tickers = ["^GSPC", "SPY", "QQQ", "IWM", "^VIX"]
        data = yf.download(tickers, start="2000-01-01", progress=False)["Close"]
        data.columns = ["SPX", "SPY", "QQQ", "IWM", "VIX"]
        data = data.dropna()

        # Daily returns
        rets = data[["SPX","SPY","QQQ","IWM"]].pct_change().dropna()

        # Define stress periods (VIX > 25)
        vix_series = data["VIX"].reindex(rets.index)
        stress_mask   = vix_series > 25
        calm_mask     = vix_series <= 25

        print(f"\n{'='*60}")
        print(f"  Multi-Underlying Correlation Analysis (2000–2026)")
        print(f"{'='*60}")
        print(f"\n  Calm periods (VIX ≤ 25, n={calm_mask.sum()} days):")
        corr_calm = rets[calm_mask].corr()
        for col in ["SPY", "QQQ", "IWM"]:
            print(f"    SPX vs {col:<4}: {corr_calm.loc['SPX', col]:.3f}")

        print(f"\n  Stress periods (VIX > 25, n={stress_mask.sum()} days):")
        corr_stress = rets[stress_mask].corr()
        for col in ["SPY", "QQQ", "IWM"]:
            print(f"    SPX vs {col:<4}: {corr_stress.loc['SPX', col]:.3f}")

        print()
        print(f"  → Correlation change (calm → stress):")
        for col in ["SPY", "QQQ", "IWM"]:
            delta = corr_stress.loc['SPX', col] - corr_calm.loc['SPX', col]
            print(f"    {col}: {corr_calm.loc['SPX',col]:.3f} → {corr_stress.loc['SPX',col]:.3f}  "
                  f"Δ{delta:+.3f}")

        print()
        print(f"  VIX correlation with each index (stress periods):")
        vix_rets = data["VIX"].pct_change().reindex(rets.index)
        for col in ["SPX","SPY","QQQ","IWM"]:
            c = vix_rets[stress_mask].corr(rets[col][stress_mask])
            print(f"    VIX vs {col:<4}: {c:.3f}")

    except Exception as e:
        print(f"  [Correlation analysis skipped: {e}]")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    params_base = StrategyParams()

    print("\n" + "="*60)
    print("  SPEC-024: BP UTILIZATION RESEARCH")
    print("  Date: 2026-03-30")
    print("="*60)

    # ── Part 1: Baseline BP utilization distribution ─────────────────
    print("\n[1/6] Baseline BP utilization (5yr 2021–2026)...")
    trades_5yr, metrics_5yr, sighist_5yr = run_backtest(
        start_date=START_5YR, account_size=ACCOUNT_SIZE, params=params_base
    )
    bp_5yr = analyze_bp_utilization(trades_5yr, sighist_5yr, ACCOUNT_SIZE, "5yr 2021–2026")

    print("\n[1b] Baseline BP utilization (26yr 2000–2026)...")
    trades_26yr, metrics_26yr, sighist_26yr = run_backtest(
        start_date=START_26YR, account_size=ACCOUNT_SIZE, params=params_base
    )
    bp_26yr = analyze_bp_utilization(trades_26yr, sighist_26yr, ACCOUNT_SIZE, "26yr 2000–2026")

    # ── Part 2: Binding constraint ────────────────────────────────────
    print("\n[2/6] Binding constraint analysis...")
    analyze_binding_constraint(trades_5yr, sighist_5yr, params_base, "5yr baseline")

    # ── Part 3: Ceiling sensitivity ───────────────────────────────────
    print("\n[3/6] BP ceiling sensitivity (does raising ceiling help?)...")
    run_ceiling_sensitivity(START_5YR)

    # ── Part 4: Position sizing scale test (5yr) ─────────────────────
    print("\n[4/6] Position sizing scale test (5yr)...")
    results_5yr = run_sizing_scenarios(START_5YR, "5yr")

    # ── Part 5: Position sizing scale test (26yr) ────────────────────
    print("\n[5/6] Position sizing scale test (26yr)...")
    results_26yr = run_sizing_scenarios(START_26YR, "26yr")

    # ── Part 6: T-bill overlay ────────────────────────────────────────
    print("\n[6/6] T-bill overlay on idle capital...")
    bp_by_scenario = {}
    if bp_5yr:
        bp_by_scenario["Baseline (5yr avg BP)"] = bp_5yr["mean_bp_all"]
    for r in results_5yr:
        bp_by_scenario[r["label"]] = r.get("avg_bp_per_trade", 0) * (bp_5yr.get("pct_days_active", 40) / 100) if bp_5yr else r.get("avg_bp_per_trade", 0)

    compute_tbill_overlay(
        bp_by_scenario,
        ACCOUNT_SIZE,
        RISK_FREE_RATE,
        START_5YR,
        "2026-03-30"
    )

    # ── Part 7: Multi-underlying correlation ─────────────────────────
    print("\n[7/6] Multi-underlying correlation in stress periods...")
    analyze_underlying_correlation()

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("  SUMMARY: KEY FINDINGS")
    print("="*60)
    print()
    print("  5yr Baseline Metrics:")
    print(f"    Trades:     {metrics_5yr.get('total_trades',0)}")
    print(f"    Sharpe:     {metrics_5yr.get('sharpe',0):.2f}")
    print(f"    Calmar:     {metrics_5yr.get('calmar',0):.2f}")
    print(f"    Total PnL:  ${metrics_5yr.get('total_pnl',0):,.0f}")
    print(f"    MaxDD:      ${metrics_5yr.get('max_drawdown',0):,.0f}")
    print(f"    CVaR 5%:    ${metrics_5yr.get('cvar5',0):,.0f}")
    print()

    if results_5yr and results_26yr:
        print("  Sizing Scale — 5yr Sharpe sensitivity:")
        for r in results_5yr:
            print(f"    {r['label']:<28} Sharpe={r['sharpe']:.2f}  "
                  f"Calmar={r['calmar']:.1f}  MaxDD=${r['max_drawdown']:,.0f}")
        print()
        print("  Sizing Scale — 26yr Sharpe sensitivity:")
        for r in results_26yr:
            print(f"    {r['label']:<28} Sharpe={r['sharpe']:.2f}  "
                  f"Calmar={r['calmar']:.1f}  MaxDD=${r['max_drawdown']:,.0f}")
