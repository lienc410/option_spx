"""Q073 P1.3 — Combined Portfolio Daily PnL + Correlation + Crisis + ROE Bridge.

Re-runs SPX BPS engine + HV Ladder engine, extracts daily PnL series for each,
plus Q042 Sleeve A from trades csv. Computes:
  - Cross-strategy daily PnL correlation matrix
  - Combined portfolio MaxDD / Sharpe / worst rolling 20d / 3m
  - Crisis windows (2008 GFC, 2020 COVID, 2022 bear)
  - Full ROE bridge

Outputs in research/q073/:
  q073_p1_3_combined_daily_pnl.csv
  q073_p1_3_correlation_matrix.csv
  q073_p1_3_combined_metrics.md
  q073_p1_3_crisis_windows.csv
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

print("Q073 P1.3 — Combined Portfolio Run", flush=True)
print("=" * 70, flush=True)

# ── 1. SPX BPS engine (with V3-A) — re-run + extract daily PnL ──────────
print("\n[1/3] Re-running SPX BPS 26y engine + extracting daily_rows...", flush=True)
from backtest.engine import run_backtest
spx_result = run_backtest(start_date="2000-01-01", end_date="2026-05-17",
                          account_size=NLV, verbose=False)
spx_daily = pd.DataFrame([{
    "date": pd.Timestamp(dr.date),
    "spx_pnl": dr.total_pnl,
    "spx_start_equity": dr.start_equity,
} for dr in spx_result.portfolio_rows])
spx_daily.set_index("date", inplace=True)
print(f"  SPX daily rows: {len(spx_daily)}, total PnL: ${spx_daily['spx_pnl'].sum():,.0f}", flush=True)

# ── 2. HV Ladder /ES — re-run + extract daily PnL ───────────────────────
print("\n[2/3] Re-running HV Ladder 26y engine...", flush=True)
from research.strategies.ES_puts.backtest import run_phase2_hvlad
hv_result = run_phase2_hvlad(start_date="2000-01-01", end_date="2026-05-17", verbose=False)
hv_daily = pd.DataFrame([{
    "date": pd.Timestamp(dr.date),
    "hv_pnl": dr.total_pnl,
} for dr in hv_result.daily_rows])
hv_daily.set_index("date", inplace=True)
print(f"  HV Ladder daily rows: {len(hv_daily)}, total PnL: ${hv_daily['hv_pnl'].sum():,.0f}", flush=True)

# ── 3. Q042 Sleeve A — from trades csv (PnL on exit_date) ───────────────
print("\n[3/3] Loading Q042 Sleeve A trades...", flush=True)
q42_trades = pd.read_csv(REPO / "data" / "q042_backtest_trades.csv")
sleeve_a = q42_trades[q42_trades["sleeve_id"] == "A"].copy()
sleeve_a["exit_date"] = pd.to_datetime(sleeve_a["exit_date"])
# PnL crystallizes on exit_date — simple model
q42a_daily = sleeve_a.groupby("exit_date")["exit_pnl"].sum().to_frame("q42a_pnl")
q42a_daily.index.name = "date"
print(f"  Q042 Sleeve A: {len(sleeve_a)} trades, total PnL: ${sleeve_a['exit_pnl'].sum():,.0f}", flush=True)

# ── 4. Merge into combined daily series ─────────────────────────────────
print("\n[merge] Building combined daily series...", flush=True)
combined = spx_daily.join(hv_daily, how="outer").join(q42a_daily, how="outer").fillna(0.0)
combined["total_pnl"] = combined[["spx_pnl", "hv_pnl", "q42a_pnl"]].sum(axis=1)
combined["cum_pnl"] = combined["total_pnl"].cumsum()
combined["equity"] = NLV + combined["cum_pnl"]
combined.to_csv(OUT / "q073_p1_3_combined_daily_pnl.csv")
print(f"  Combined daily series: {len(combined)} days, final equity ${combined['equity'].iloc[-1]:,.0f}", flush=True)

# ── 5. Correlation matrix (daily PnL) ───────────────────────────────────
print("\n[correlation] Computing daily PnL correlation matrix...", flush=True)
corr_cols = ["spx_pnl", "hv_pnl", "q42a_pnl"]
corr_matrix = combined[corr_cols].corr()
corr_matrix.to_csv(OUT / "q073_p1_3_correlation_matrix.csv")
print(corr_matrix.to_string())

# ── 6. Portfolio metrics ───────────────────────────────────────────────
print("\n[metrics] Computing combined portfolio metrics...", flush=True)
years = len(combined) / 252
total_pnl = combined["total_pnl"].sum()
final_eq = combined["equity"].iloc[-1]
ann_roe_geo = (final_eq / NLV) ** (1.0 / years) - 1.0 if years > 0 else 0.0
ann_roe_arith = total_pnl / years / NLV

# MaxDD
equity = combined["equity"]
running_max = equity.cummax()
drawdown = (equity - running_max) / running_max
max_dd = drawdown.min()

# Daily return series
daily_ret = combined["total_pnl"] / NLV
sharpe = daily_ret.mean() / daily_ret.std() * (252 ** 0.5) if daily_ret.std() > 0 else 0.0
downside = daily_ret[daily_ret < 0]
sortino = daily_ret.mean() / (downside.pow(2).mean() ** 0.5) * (252 ** 0.5) if len(downside) > 0 else 0.0

# Worst rolling 20d / 63d (3m)
# Two normalization views:
# (a) Constant initial NLV $894k (conservative — % feels larger in late-year stress)
# (b) Point-in-time equity (proper percentage at that time, as PM experiences it)
roll_20d_sum = combined["total_pnl"].rolling(20).sum()
roll_63d_sum = combined["total_pnl"].rolling(63).sum()
worst_20d = roll_20d_sum.min()
worst_63d = roll_63d_sum.min()
worst_20d_pct_initial = worst_20d / NLV
worst_63d_pct_initial = worst_63d / NLV

# Point-in-time normalization
combined["equity_start"] = combined["equity"].shift(1).fillna(NLV)
combined["daily_ret"] = combined["total_pnl"] / combined["equity_start"]
# rolling sum-of-returns ≈ worst-period return for short windows
roll_20d_ret = combined["daily_ret"].rolling(20).sum()
roll_63d_ret = combined["daily_ret"].rolling(63).sum()
worst_20d_pct_pit = roll_20d_ret.min()
worst_63d_pct_pit = roll_63d_ret.min()
worst_20d_pit_date = combined.loc[roll_20d_ret.idxmin(), "equity_start"] if roll_20d_ret.idxmin() == roll_20d_ret.idxmin() else None
worst_63d_pit_date = roll_63d_ret.idxmin()

print(f"  Years:                 {years:.2f}")
print(f"  Total PnL:             ${total_pnl:,.0f}")
print(f"  Final equity:          ${final_eq:,.0f}")
print(f"  Ann ROE (geometric):   {ann_roe_geo*100:.2f}%")
print(f"  Ann ROE (arithmetic):  {ann_roe_arith*100:.2f}%")
print(f"  Sharpe (daily ann):    {sharpe:.2f}")
print(f"  Sortino:               {sortino:.2f}")
print(f"  MaxDD:                 {max_dd*100:.2f}%")
print(f"  Worst 20d (V2):        ${worst_20d:,.0f}")
print(f"    Constant initial NLV:  {worst_20d_pct_initial*100:.2f}% (CONSERVATIVE — may overstate)")
print(f"    Point-in-time equity:  {worst_20d_pct_pit*100:.2f}% (PROPER — vs V2 11%)")
print(f"  Worst 63d ≈ 3m (V3):   ${worst_63d:,.0f}")
print(f"    Constant initial NLV:  {worst_63d_pct_initial*100:.2f}%")
print(f"    Point-in-time equity:  {worst_63d_pct_pit*100:.2f}% (vs V3 17%)")
print(f"    Worst 63d window ends: {worst_63d_pit_date}")

# ── 7. Crisis windows ──────────────────────────────────────────────────
print("\n[crisis] Computing crisis window outcomes...", flush=True)
crises = {
    "GFC_2008_full":   ("2008-01-01", "2009-06-30"),
    "GFC_2008_acute":  ("2008-08-01", "2009-03-31"),
    "COVID_2020":      ("2020-02-15", "2020-05-31"),
    "Bear_2022":       ("2022-01-01", "2022-12-31"),
    "Vol_2018Q4":      ("2018-10-01", "2018-12-31"),
}
crisis_rows = []
for name, (s, e) in crises.items():
    s_ts, e_ts = pd.Timestamp(s), pd.Timestamp(e)
    sub = combined[(combined.index >= s_ts) & (combined.index <= e_ts)]
    if len(sub) == 0:
        continue
    crisis_rows.append({
        "window": name, "start": s, "end": e,
        "days": len(sub),
        "spx_pnl":  round(sub["spx_pnl"].sum(), 0),
        "hv_pnl":   round(sub["hv_pnl"].sum(), 0),
        "q42a_pnl": round(sub["q42a_pnl"].sum(), 0),
        "total_pnl": round(sub["total_pnl"].sum(), 0),
        "pct_nlv":  round(sub["total_pnl"].sum() / NLV * 100, 2),
        "worst_day": round(sub["total_pnl"].min(), 0),
        "worst_20d": round(sub["total_pnl"].rolling(20).sum().min(), 0),
    })
crisis_df = pd.DataFrame(crisis_rows)
crisis_df.to_csv(OUT / "q073_p1_3_crisis_windows.csv", index=False)
print(crisis_df.to_string(index=False))

# ── 8. ROE Bridge ──────────────────────────────────────────────────────
print("\n[bridge] ROE Bridge (combined-NLV per Rule 6)...", flush=True)
spx_total = spx_daily["spx_pnl"].sum()
hv_total = hv_daily["hv_pnl"].sum()
q42a_total = sleeve_a["exit_pnl"].sum()
years_spx = len(spx_daily) / 252
years_hv = len(hv_daily) / 252
# Q042 Sleeve A is 19y based on memo
years_q42a = (pd.Timestamp(sleeve_a["exit_date"].max()) - pd.Timestamp("2007-02-28")).days / 365.25

print(f"\n{'Source':40} {'PnL':>15} {'Years':>7} {'Ann ROE':>10}")
print("-" * 76)
print(f"{'SPX BPS (incl V3-A)':40} ${spx_total:>13,.0f} {years_spx:>7.2f} {spx_total/years_spx/NLV*100:>9.2f}%")
print(f"{'HV Ladder /ES':40} ${hv_total:>13,.0f} {years_hv:>7.2f} {hv_total/years_hv/NLV*100:>9.2f}%")
print(f"{'Q042 Sleeve A (PnL on exit)':40} ${q42a_total:>13,.0f} {years_q42a:>7.2f} {q42a_total/years_q42a/NLV*100:>9.2f}%")
total_3 = spx_total + hv_total + q42a_total
combined_years = years_spx  # use SPX window as combined window
print("-" * 76)
print(f"{'Sum (additive arithmetic)':40} ${total_3:>13,.0f} {combined_years:>7.2f} {total_3/combined_years/NLV*100:>9.2f}%")
print(f"{'Combined daily-series geometric':40} {'-':>15} {years:>7.2f} {ann_roe_geo*100:>9.2f}%")

print("\nDone. Outputs:", flush=True)
print(f"  {OUT / 'q073_p1_3_combined_daily_pnl.csv'}")
print(f"  {OUT / 'q073_p1_3_correlation_matrix.csv'}")
print(f"  {OUT / 'q073_p1_3_crisis_windows.csv'}")
