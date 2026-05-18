"""Q073 P1.3R — Unified-NLV combined simulator.

Fix: each strategy runs on its ALLOCATED share of $894k combined NLV,
not assuming it has the full $894k. Allocations match production reality:

  SPX BPS Main         : 60% × $894k = $536,400  (core income engine, peak BP utilization)
  HV Ladder /ES        : 5%  × $894k = $44,700   (opportunistic sleeve, occupancy 21%)
  Q042 Sleeve A        : 10% × $894k = $89,400   (10% sleeve cap per SPEC-094)
  Cash baseline (BOXX) : 25% × $894k = $223,500  (idle reserve + cash yield ~4.3%)

Each engine runs on its allocation as account_size, then their daily PnL
streams sum to give COMBINED PORTFOLIO PnL on shared $894k base.

Outputs:
  q073_p1_3R_unified_daily_pnl.csv
  q073_p1_3R_unified_correlation.csv
  q073_p1_3R_unified_metrics.md
  q073_p1_3R_unified_crisis.csv
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

# Strategy allocations (% of combined NLV)
ALLOC_SPX  = 0.60   # core income engine
ALLOC_HV   = 0.05   # opportunistic, low avg BP usage (21% occupancy)
ALLOC_Q42A = 0.10   # sleeve cap per SPEC-094
ALLOC_CASH = 0.25   # idle/cash reserve (T-bill yield)

SPX_BUDGET  = NLV * ALLOC_SPX
HV_BUDGET   = NLV * ALLOC_HV
Q42A_BUDGET = NLV * ALLOC_Q42A
CASH_BUDGET = NLV * ALLOC_CASH
CASH_ANNUAL_YIELD = 0.043  # BOXX baseline per PM

print("Q073 P1.3R — Unified-NLV Combined Simulator", flush=True)
print("=" * 70, flush=True)
print(f"\nAllocations (combined NLV ${NLV:,.0f}):")
print(f"  SPX BPS Main         : {ALLOC_SPX*100:.0f}% = ${SPX_BUDGET:,.0f}")
print(f"  HV Ladder /ES        : {ALLOC_HV*100:.0f}% = ${HV_BUDGET:,.0f}")
print(f"  Q042 Sleeve A        : {ALLOC_Q42A*100:.0f}% = ${Q42A_BUDGET:,.0f}")
print(f"  Cash (BOXX ~4.3%)    : {ALLOC_CASH*100:.0f}% = ${CASH_BUDGET:,.0f}")
print(f"  Sum                  : {(ALLOC_SPX+ALLOC_HV+ALLOC_Q42A+ALLOC_CASH)*100:.0f}%")
print(flush=True)

# ── 1. SPX BPS on SPX_BUDGET ────────────────────────────────────────────
print(f"[1/3] SPX BPS engine on ${SPX_BUDGET:,.0f} budget...", flush=True)
from backtest.engine import run_backtest
spx_result = run_backtest(start_date="2000-01-01", end_date="2026-05-17",
                          account_size=SPX_BUDGET, verbose=False)
spx_daily = pd.DataFrame([{
    "date": pd.Timestamp(dr.date),
    "spx_pnl": dr.total_pnl,
    "spx_equity": dr.cumulative_equity,
} for dr in spx_result.portfolio_rows]).set_index("date")
print(f"  SPX trades: {spx_result.metrics.get('total_trades')}, "
      f"total PnL: ${spx_daily['spx_pnl'].sum():,.0f}, "
      f"engine ann ROE: {spx_result.metrics.get('annualized_roe')}%", flush=True)

# ── 2. HV Ladder on HV_BUDGET ──────────────────────────────────────────
# run_phase2_hvlad's internal P2_INITIAL_EQUITY default is $500k; pass HV_BUDGET
# via direct invocation. Need to check signature.
print(f"\n[2/3] HV Ladder engine on ${HV_BUDGET:,.0f} budget...", flush=True)
import research.strategies.ES_puts.backtest as es_bt
# HV Ladder engine uses P2_INITIAL_EQUITY constant for sizing
orig_p2_initial = es_bt.P2_INITIAL_EQUITY
es_bt.P2_INITIAL_EQUITY = HV_BUDGET
try:
    hv_result = es_bt.run_phase2_hvlad(start_date="2000-01-01", end_date="2026-05-17", verbose=False)
finally:
    es_bt.P2_INITIAL_EQUITY = orig_p2_initial
hv_daily = pd.DataFrame([{
    "date": pd.Timestamp(dr.date),
    "hv_pnl": dr.total_pnl,
} for dr in hv_result.daily_rows]).set_index("date")
print(f"  HV trades: {len(hv_result.trades)}, total PnL: ${hv_daily['hv_pnl'].sum():,.0f}", flush=True)

# ── 3. Q042 Sleeve A — trades pre-computed; rescale to budget ──────────
print(f"\n[3/3] Q042 Sleeve A trades (rescaled to ${Q42A_BUDGET:,.0f} budget)...", flush=True)
q42_trades = pd.read_csv(REPO / "data" / "q042_backtest_trades.csv")
sleeve_a = q42_trades[q42_trades["sleeve_id"] == "A"].copy()
sleeve_a["exit_date"] = pd.to_datetime(sleeve_a["exit_date"])
# Original Q042 trades were computed on sleeve sizing of (account_pct field shows fraction).
# Each trade's exit_pnl is in absolute $. The account_pct = exit_pnl / sleeve_capital_at_trade.
# We need to project onto Q42A_BUDGET ($89.4k constant). Take account_pct × Q42A_BUDGET.
sleeve_a["rescaled_pnl"] = sleeve_a["account_pct"] * Q42A_BUDGET
q42a_daily = sleeve_a.groupby("exit_date")["rescaled_pnl"].sum().to_frame("q42a_pnl")
q42a_daily.index.name = "date"
print(f"  Q042A: {len(sleeve_a)} trades, rescaled total PnL: ${sleeve_a['rescaled_pnl'].sum():,.0f}", flush=True)

# ── 4. Cash baseline (BOXX ~4.3%) on CASH_BUDGET ───────────────────────
# Daily cash return = annual / 252
daily_cash_pnl = CASH_BUDGET * CASH_ANNUAL_YIELD / 252
print(f"\n[cash] Cash baseline daily: ${daily_cash_pnl:.2f}/day on ${CASH_BUDGET:,.0f} @ {CASH_ANNUAL_YIELD*100:.1f}%", flush=True)

# ── 5. Merge into combined daily series ────────────────────────────────
print("\n[merge] Building combined daily series (unified-NLV)...", flush=True)
combined = spx_daily[["spx_pnl"]].join(hv_daily, how="outer").join(q42a_daily, how="outer").fillna(0.0)
combined["cash_pnl"] = daily_cash_pnl  # constant daily cash
combined["total_pnl"] = combined[["spx_pnl", "hv_pnl", "q42a_pnl", "cash_pnl"]].sum(axis=1)
combined["cum_pnl"] = combined["total_pnl"].cumsum()
combined["equity"] = NLV + combined["cum_pnl"]
combined.to_csv(OUT / "q073_p1_3R_unified_daily_pnl.csv")
print(f"  Combined days: {len(combined)}, final equity ${combined['equity'].iloc[-1]:,.0f}", flush=True)

# ── 6. Correlation matrix ──────────────────────────────────────────────
corr_cols = ["spx_pnl", "hv_pnl", "q42a_pnl"]  # cash excluded (constant)
corr = combined[corr_cols].corr()
corr.to_csv(OUT / "q073_p1_3R_unified_correlation.csv")
print(f"\n[correlation] Daily PnL correlation (cash excluded):")
print(corr.to_string())

# ── 7. Portfolio metrics ───────────────────────────────────────────────
years = len(combined) / 252
total_pnl = combined["total_pnl"].sum()
final_eq = combined["equity"].iloc[-1]
ann_roe_geo = (final_eq / NLV) ** (1.0 / years) - 1.0 if years > 0 else 0.0
ann_roe_arith = total_pnl / years / NLV

equity = combined["equity"]
running_max = equity.cummax()
drawdown = (equity - running_max) / running_max
max_dd = drawdown.min()

daily_ret = combined["total_pnl"] / equity.shift(1).fillna(NLV)
sharpe = daily_ret.mean() / daily_ret.std() * (252 ** 0.5) if daily_ret.std() > 0 else 0.0
downside = daily_ret[daily_ret < 0]
sortino = daily_ret.mean() / (downside.pow(2).mean() ** 0.5) * (252 ** 0.5) if len(downside) > 0 else 0.0

# Worst rolling 20d / 63d
roll_20d_ret = daily_ret.rolling(20).sum()
roll_63d_ret = daily_ret.rolling(63).sum()
worst_20d_ret = roll_20d_ret.min()
worst_63d_ret = roll_63d_ret.min()
worst_20d_idx = roll_20d_ret.idxmin()
worst_63d_idx = roll_63d_ret.idxmin()

print(f"\n[metrics] Combined Portfolio (unified-NLV):")
print(f"  Years:                {years:.2f}")
print(f"  Total PnL:            ${total_pnl:,.0f}")
print(f"  Final equity:         ${final_eq:,.0f}")
print(f"  Ann ROE (geometric):  {ann_roe_geo*100:.2f}%   ← vs floor 8% / stretch 20%")
print(f"  Ann ROE (arithmetic): {ann_roe_arith*100:.2f}%")
print(f"  Sharpe (daily ann):   {sharpe:.2f}")
print(f"  Sortino:              {sortino:.2f}")
print(f"  MaxDD (V1 ≤ 28%):     {max_dd*100:.2f}%   {'PASS' if max_dd >= -0.28 else 'FAIL'}")
print(f"  Worst 20d (V2 ≤ 11%): {worst_20d_ret*100:.2f}%   {'PASS' if worst_20d_ret >= -0.11 else 'FAIL'} (window ending {worst_20d_idx.date()})")
print(f"  Worst 63d (V3 ≤ 17%): {worst_63d_ret*100:.2f}%   {'PASS' if worst_63d_ret >= -0.17 else 'FAIL'} (window ending {worst_63d_idx.date()})")

# ── 8. Crisis windows ──────────────────────────────────────────────────
print("\n[crisis] Crisis window outcomes (unified-NLV):", flush=True)
crises = {
    "DotCom_2000_2002":  ("2000-03-01", "2002-10-31"),
    "GFC_2008_full":     ("2008-01-01", "2009-06-30"),
    "GFC_2008_acute":    ("2008-08-01", "2009-03-31"),
    "Flash_2010":        ("2010-04-23", "2010-07-31"),
    "Aug_2011":          ("2011-07-15", "2011-10-31"),
    "Vol_2015Aug":       ("2015-08-15", "2015-10-15"),
    "Vol_2018Q4":        ("2018-10-01", "2018-12-31"),
    "COVID_2020":        ("2020-02-15", "2020-05-31"),
    "Bear_2022":         ("2022-01-01", "2022-12-31"),
}
crisis_rows = []
for name, (s, e) in crises.items():
    s_ts, e_ts = pd.Timestamp(s), pd.Timestamp(e)
    sub = combined[(combined.index >= s_ts) & (combined.index <= e_ts)]
    if len(sub) == 0:
        continue
    eq_start = sub["equity"].iloc[0] - sub["total_pnl"].iloc[0]
    window_pnl_pct = sub["total_pnl"].sum() / eq_start if eq_start > 0 else 0.0
    drawdown_in_window = (sub["equity"] - sub["equity"].cummax()) / sub["equity"].cummax()
    worst_dd_window = drawdown_in_window.min()
    crisis_rows.append({
        "window": name, "start": s, "end": e,
        "days": len(sub),
        "spx_pnl":  round(sub["spx_pnl"].sum(), 0),
        "hv_pnl":   round(sub["hv_pnl"].sum(), 0),
        "q42a_pnl": round(sub["q42a_pnl"].sum(), 0),
        "cash_pnl": round(sub["cash_pnl"].sum(), 0),
        "total_pnl": round(sub["total_pnl"].sum(), 0),
        "eq_start": round(eq_start, 0),
        "window_pct_of_then_equity": round(window_pnl_pct * 100, 2),
        "worst_dd_in_window_pct": round(worst_dd_window * 100, 2),
    })
crisis_df = pd.DataFrame(crisis_rows)
crisis_df.to_csv(OUT / "q073_p1_3R_unified_crisis.csv", index=False)
print(crisis_df.to_string(index=False))

# ── 9. ROE Bridge ─────────────────────────────────────────────────────
print("\n[bridge] Combined ROE Bridge (unified-NLV, per Rule 6):", flush=True)
spx_total = combined["spx_pnl"].sum()
hv_total = combined["hv_pnl"].sum()
q42a_total = combined["q42a_pnl"].sum()
cash_total = combined["cash_pnl"].sum()
print(f"\n{'Source':40} {'Allocation':>12} {'PnL (26y)':>15} {'Ann %':>9}")
print("-" * 80)
print(f"{'SPX BPS (incl V3-A)':40} {f'{ALLOC_SPX*100:.0f}%':>12} ${spx_total:>13,.0f} {spx_total/years/NLV*100:>8.2f}%")
print(f"{'HV Ladder /ES':40} {f'{ALLOC_HV*100:.0f}%':>12} ${hv_total:>13,.0f} {hv_total/years/NLV*100:>8.2f}%")
print(f"{'Q042 Sleeve A (rescaled)':40} {f'{ALLOC_Q42A*100:.0f}%':>12} ${q42a_total:>13,.0f} {q42a_total/years/NLV*100:>8.2f}%")
print(f"{'Cash baseline (BOXX 4.3%)':40} {f'{ALLOC_CASH*100:.0f}%':>12} ${cash_total:>13,.0f} {cash_total/years/NLV*100:>8.2f}%")
print("-" * 80)
print(f"{'Total (additive arith)':40} {f'{(ALLOC_SPX+ALLOC_HV+ALLOC_Q42A+ALLOC_CASH)*100:.0f}%':>12} ${total_pnl:>13,.0f} {ann_roe_arith*100:>8.2f}%")
print(f"{'Combined geometric on $894k':40} {'':>12} {'':>15} {ann_roe_geo*100:>8.2f}%")

print(f"\nDone. Outputs in {OUT}", flush=True)
