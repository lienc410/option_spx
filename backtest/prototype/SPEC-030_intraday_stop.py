"""
SPEC-030: Intraday Stop Loss Analysis — OHLC intraday touch study.

Scope:
  - Analyze BPS / BPS_HV stop-loss exits only
  - Use exact engine leg repricing with SPX daily low/high
  - Keep sigma fixed at daily VIX close
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backtest.engine import _build_legs, _current_value, run_backtest
from signals.vix_regime import fetch_vix_history
from strategy.selector import StrategyName, StrategyParams


BPS_STRATEGIES = {
    StrategyName.BULL_PUT_SPREAD,
    StrategyName.BULL_PUT_SPREAD_HV,
}

ACCOUNT_SIZE = 150_000.0
START_DATE = "2000-01-01"
END_DATE = "2026-03-31"
SPX_CACHE = Path(__file__).resolve().parents[2] / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"


def fetch_spx_ohlc(period: str = "max") -> pd.DataFrame:
    """
    Return SPX OHLC history, preferring the existing local GSPC cache.
    """
    if SPX_CACHE.exists():
        cached = pd.read_pickle(SPX_CACHE)
        required = {"Open", "High", "Low", "Close"}
        if required.issubset(cached.columns):
            out = cached[["Open", "High", "Low", "Close"]].rename(
                columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"}
            )
            out.index = pd.to_datetime(out.index.date)
            return out

    ticker = yf.Ticker("^GSPC")
    df = ticker.history(period=period, interval="1d")
    if df.empty:
        raise RuntimeError("Could not fetch SPX OHLC data.")
    out = df[["Open", "High", "Low", "Close"]].rename(
        columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"}
    )
    out.index = pd.to_datetime(out.index.date)
    return out


def run_and_collect(params: StrategyParams):
    """
    Run the standard backtest and return relevant BPS trades.
    """
    print("Running 26yr backtest...")
    result = run_backtest(
        start_date=START_DATE,
        end_date=END_DATE,
        account_size=ACCOUNT_SIZE,
        params=params,
        verbose=False,
    )
    stop_trades = [
        trade for trade in result.trades
        if trade.exit_reason == "stop_loss" and trade.strategy in BPS_STRATEGIES
    ]
    profit_trades = [
        trade for trade in result.trades
        if trade.exit_reason == "50pct_profit" and trade.strategy in BPS_STRATEGIES
    ]
    all_bps = [trade for trade in result.trades if trade.strategy in BPS_STRATEGIES]
    print(f"  Total BPS/BPS_HV trades: {len(all_bps)}")
    print(f"  Stop loss trades:        {len(stop_trades)}")
    print(f"  50pct profit trades:     {len(profit_trades)}")
    return stop_trades, profit_trades, result.trades


def _reconstruct_legs(trade, params: StrategyParams):
    sigma_entry = trade.entry_vix / 100.0
    legs, _ = _build_legs(trade.strategy, trade.entry_spx, sigma_entry, params)
    return legs


def _holding_dates(entry_date: str, exit_date: str, index: pd.Index) -> list[pd.Timestamp]:
    entry_dt = pd.Timestamp(entry_date)
    exit_dt = pd.Timestamp(exit_date)
    return list(index[(index > entry_dt) & (index <= exit_dt)])


def _trade_pnl(entry_value: float, current_value: float, contracts: float) -> float:
    return (current_value - entry_value) * contracts * 100.0


def _advance_days(hit_idx: int, total_days: int) -> int:
    return (total_days - 1) - hit_idx


def scan_intraday_stop(trade, spx_ohlc: pd.DataFrame, vix_eod: pd.Series, params: StrategyParams) -> dict:
    """
    Scan the holding window of one stop-loss trade using SPX daily lows.
    """
    legs = _reconstruct_legs(trade, params)
    dates = _holding_dates(trade.entry_date, trade.exit_date, spx_ohlc.index)
    entry_value = trade.entry_credit
    hit_date = None
    hit_pnl = None
    hit_ratio = None

    for idx, date in enumerate(dates):
        if date not in vix_eod.index:
            continue
        spx_low = float(spx_ohlc.loc[date, "low"])
        sigma = float(vix_eod.loc[date]) / 100.0
        days_held = idx + 1
        current_value = _current_value(legs, spx_low, sigma, days_held)
        pnl = _trade_pnl(entry_value, current_value, trade.contracts)
        pnl_ratio = (current_value - entry_value) / abs(entry_value) if entry_value else 0.0
        if pnl_ratio <= -params.stop_mult:
            hit_date = date
            hit_pnl = pnl
            hit_ratio = pnl_ratio
            break

    advance_days = None
    if hit_date is not None:
        hit_idx = dates.index(hit_date)
        advance_days = _advance_days(hit_idx, len(dates))

    saving = (hit_pnl - trade.exit_pnl) if hit_pnl is not None and advance_days and advance_days > 0 else None

    return {
        "entry_date": trade.entry_date,
        "exit_date": trade.exit_date,
        "strategy": trade.strategy.value,
        "entry_spx": round(trade.entry_spx, 1),
        "spread_width": round(trade.spread_width, 1),
        "actual_exit_pnl": round(trade.exit_pnl, 2),
        "intraday_first_hit_date": str(hit_date.date()) if hit_date is not None else None,
        "advance_days": advance_days,
        "pnl_at_intraday_hit": round(hit_pnl, 2) if hit_pnl is not None else None,
        "pnl_ratio_at_intraday_hit": round(hit_ratio, 3) if hit_ratio is not None else None,
        "saving_vs_close": round(saving, 2) if saving is not None else None,
    }


def scan_intraday_profit(trade, spx_ohlc: pd.DataFrame, vix_eod: pd.Series, params: StrategyParams) -> dict | None:
    """
    Secondary analysis: scan BPS 50pct-profit exits using SPX daily highs.
    """
    legs = _reconstruct_legs(trade, params)
    dates = _holding_dates(trade.entry_date, trade.exit_date, spx_ohlc.index)
    entry_value = trade.entry_credit
    hit_date = None

    for idx, date in enumerate(dates):
        if date not in vix_eod.index:
            continue
        days_held = idx + 1
        if days_held < params.min_hold_days:
            continue
        spx_high = float(spx_ohlc.loc[date, "high"])
        sigma = float(vix_eod.loc[date]) / 100.0
        current_value = _current_value(legs, spx_high, sigma, days_held)
        pnl_ratio = (current_value - entry_value) / abs(entry_value) if entry_value else 0.0
        if pnl_ratio >= params.profit_target:
            hit_date = date
            break

    if hit_date is None:
        return None

    hit_idx = dates.index(hit_date)
    return {
        "entry_date": trade.entry_date,
        "exit_date": trade.exit_date,
        "advance_days": _advance_days(hit_idx, len(dates)),
    }


def report_stop_distribution(scan_results: list[dict]) -> dict:
    print("\n" + "=" * 60)
    print("Report 1: Intraday Stop-Loss Touch Distribution")
    print("=" * 60)

    total = len(scan_results)
    never_hit = [row for row in scan_results if row["advance_days"] is None]
    same_day = [row for row in scan_results if row["advance_days"] == 0]
    advance_1 = [row for row in scan_results if row["advance_days"] == 1]
    advance_2 = [row for row in scan_results if row["advance_days"] == 2]
    advance_3p = [row for row in scan_results if row["advance_days"] is not None and row["advance_days"] >= 3]

    buckets = [
        ("Same day (0 days early)", same_day),
        ("1 day early", advance_1),
        ("2 days early", advance_2),
        ("3+ days early", advance_3p),
        ("Never early", never_hit),
    ]

    print(f"{'Bucket':<24} {'Count':>8} {'Pct':>8}")
    print("-" * 42)
    for label, rows in buckets:
        pct = len(rows) / total * 100 if total else 0.0
        print(f"{label:<24} {len(rows):>8} {pct:>7.1f}%")

    advanced = [row for row in scan_results if row["advance_days"] is not None and row["advance_days"] > 0]
    avg_advance = float(np.mean([row["advance_days"] for row in advanced])) if advanced else 0.0
    print(f"\nEarly-hit rate (>0 days): {len(advanced)}/{total} ({(len(advanced)/total*100 if total else 0):.1f}%)")
    print(f"Average advance days: {avg_advance:.2f}")
    return {
        "total": total,
        "same_day": len(same_day),
        "advance_1": len(advance_1),
        "advance_2": len(advance_2),
        "advance_3p": len(advance_3p),
        "never_early": len(never_hit),
        "early_rate": (len(advanced) / total) if total else 0.0,
        "avg_advance_days": avg_advance,
    }


def report_pnl_saving(scan_results: list[dict]) -> dict:
    print("\n" + "=" * 60)
    print("Report 2: PnL Saved by Earlier Intraday Exit")
    print("=" * 60)

    advanced = [
        row for row in scan_results
        if row["advance_days"] is not None and row["advance_days"] > 0 and row["saving_vs_close"] is not None
    ]
    if not advanced:
        print("No early-hit trades found.")
        return {"avg_saving": 0.0, "max_saving": 0.0, "count": 0}

    avg_saving = float(np.mean([row["saving_vs_close"] for row in advanced]))
    max_saving = float(max(row["saving_vs_close"] for row in advanced))
    print(f"Trades with positive lead time: {len(advanced)}")
    print(f"Average loss avoided: ${avg_saving:,.0f}")
    print(f"Max loss avoided:     ${max_saving:,.0f}")
    print()
    print(f"{'Entry':<12} {'Early':>6} {'Actual':>12} {'Intraday':>12} {'Saved':>10}")
    print("-" * 58)
    for row in sorted(advanced, key=lambda item: item["saving_vs_close"], reverse=True)[:10]:
        print(
            f"{row['entry_date']:<12} {row['advance_days']:>6} "
            f"{row['actual_exit_pnl']:>12,.0f} {row['pnl_at_intraday_hit']:>12,.0f} {row['saving_vs_close']:>10,.0f}"
        )
    return {"avg_saving": avg_saving, "max_saving": max_saving, "count": len(advanced)}


def report_by_year(scan_results: list[dict]) -> dict[int, dict]:
    print("\n" + "=" * 60)
    print("Report 3: Stress-Year Distribution")
    print("=" * 60)

    stress_years = {2008, 2011, 2015, 2020, 2022}
    by_year: dict[int, list[dict]] = {}
    for row in scan_results:
        year = int(row["exit_date"][:4])
        by_year.setdefault(year, []).append(row)

    print(f"{'Year':<8} {'Stops':>8} {'Early':>8} {'Rate':>8} {'Note':>10}")
    print("-" * 46)
    summary: dict[int, dict] = {}
    for year in sorted(by_year):
        rows = by_year[year]
        early = sum(1 for row in rows if row["advance_days"] is not None and row["advance_days"] > 0)
        rate = early / len(rows) if rows else 0.0
        note = "stress" if year in stress_years else ""
        print(f"{year:<8} {len(rows):>8} {early:>8} {rate*100:>7.1f}% {note:>10}")
        summary[year] = {"stops": len(rows), "early": early, "rate": rate}
    return summary


def report_profit_summary(results: list[dict]) -> dict:
    print("\n" + "=" * 60)
    print("Report 4: Intraday Profit-Target Touches")
    print("=" * 60)

    if not results:
        print("No valid profit-target records.")
        return {"count": 0, "same_day": 0, "advance_1p": 0, "avg_advance": 0.0}

    same_day = sum(1 for row in results if row["advance_days"] == 0)
    advance_1p = sum(1 for row in results if row["advance_days"] >= 1)
    avg_advance = float(np.mean([row["advance_days"] for row in results if row["advance_days"] >= 1])) if advance_1p else 0.0
    print(f"Analyzed trades:        {len(results)}")
    print(f"Same-day intraday hit:  {same_day} ({same_day/len(results)*100:.1f}%)")
    print(f"1+ day early hit:       {advance_1p} ({advance_1p/len(results)*100:.1f}%)")
    print(f"Avg advance days:       {avg_advance:.2f}")
    return {"count": len(results), "same_day": same_day, "advance_1p": advance_1p, "avg_advance": avg_advance}


def print_conclusion(stop_summary: dict) -> str:
    print("\n" + "=" * 60)
    print("AC4 Conclusion")
    print("=" * 60)

    hit_rate = stop_summary["early_rate"]
    avg_advance = stop_summary["avg_advance_days"]
    print(f"Early-hit rate:  {hit_rate*100:.1f}%  (threshold 30%)")
    print(f"Avg advance:     {avg_advance:.2f} days  (threshold 1.0)")
    print()
    if hit_rate > 0.30 and avg_advance >= 1.0:
        conclusion = "Recommend SPEC-031: intraday stop mechanism has enough edge."
    else:
        conclusion = "Close this direction: close-based stop is sufficient."
    print(conclusion)
    return conclusion


def main() -> dict:
    params = StrategyParams()

    print("Fetching SPX OHLC data...")
    spx_ohlc = fetch_spx_ohlc(period="max")

    vix_df = fetch_vix_history(period="max")
    vix_df.index = pd.to_datetime(vix_df.index.date)
    vix_eod = vix_df["vix"]

    stop_trades, profit_trades, _all_trades = run_and_collect(params)
    if not stop_trades:
        raise RuntimeError("No BPS stop-loss trades found.")

    print(f"\nScanning intraday stop for {len(stop_trades)} stop-loss trades...")
    stop_results = [scan_intraday_stop(trade, spx_ohlc, vix_eod, params) for trade in stop_trades]

    print(f"Scanning intraday profit for {len(profit_trades)} profit trades...")
    profit_results = []
    for trade in profit_trades:
        result = scan_intraday_profit(trade, spx_ohlc, vix_eod, params)
        if result is not None:
            profit_results.append(result)

    stop_summary = report_stop_distribution(stop_results)
    pnl_summary = report_pnl_saving(stop_results)
    yearly_summary = report_by_year(stop_results)
    profit_summary = report_profit_summary(profit_results)
    conclusion = print_conclusion(stop_summary)

    return {
        "report_1": stop_summary,
        "report_2": pnl_summary,
        "report_3": yearly_summary,
        "report_4": profit_summary,
        "conclusion": conclusion,
    }


if __name__ == "__main__":
    main()
