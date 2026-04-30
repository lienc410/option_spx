#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pandas as pd

from backtest.engine import (
    DEFAULT_PARAMS,
    TREND_THRESHOLD,
    _classify_trend_atr,
    _compute_atr14_close,
    fetch_spx_history,
    fetch_vix3m_history,
    fetch_vix_history,
    run_backtest,
)
from signals.iv_rank import compute_iv_percentile, compute_iv_rank
from signals.trend import TrendSignal
from signals.vix_regime import (
    _classify_regime,
    _classify_trend as _vix_classify_trend,
)
from strategy.catalog import strategy_descriptor
from strategy.selector import (
    IVSignal as SelectorIVSignal,
    IVSnapshot,
    TrendSnapshot,
    VixSnapshot,
    select_strategy,
)


def _default_start_date() -> str:
    today = date.today()
    return today.replace(year=today.year - 3).isoformat()


def _load_daily_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    vix_df = fetch_vix_history(period="max")
    spx_df = fetch_spx_history(period="max")
    try:
        vix3m_df = fetch_vix3m_history(period="max")
    except Exception:
        vix3m_df = pd.DataFrame(columns=["vix3m"])

    vix_df.index = pd.to_datetime(vix_df.index.date)
    spx_df.index = pd.to_datetime(spx_df.index.date)
    if not vix3m_df.empty:
        vix3m_df.index = pd.to_datetime(vix3m_df.index.date)
    return vix_df, spx_df, vix3m_df


def _effective_iv_signal(ivp: float) -> str:
    if ivp > 70:
        return SelectorIVSignal.HIGH.value
    if ivp < 40:
        return SelectorIVSignal.LOW.value
    return SelectorIVSignal.NEUTRAL.value


def _entry_recommendation(
    entry_date: str,
    *,
    vix_df: pd.DataFrame,
    spx_df: pd.DataFrame,
    vix3m_df: pd.DataFrame,
):
    dt = pd.Timestamp(entry_date)
    vix_window = vix_df[vix_df.index <= dt]["vix"]
    spx_window = spx_df[spx_df.index <= dt]["close"]
    if len(vix_window) < 60 or len(spx_window) < 55:
        raise ValueError(f"Not enough lookback to rebuild recommendation for {entry_date}")

    vix = float(vix_window.iloc[-1])
    spx = float(spx_window.iloc[-1])
    vix3m = None
    if not vix3m_df.empty and dt in vix3m_df.index:
        value = vix3m_df.loc[dt, "vix3m"]
        if pd.notna(value):
            vix3m = float(value)

    regime = _classify_regime(vix)
    iv_window = (vix_window.iloc[-252:] if len(vix_window) >= 252 else vix_window).copy()
    iv_window.iloc[-1] = vix
    ivr = float(compute_iv_rank(iv_window))
    ivp = float(compute_iv_percentile(iv_window))

    w63 = (vix_window.iloc[-63:] if len(vix_window) >= 63 else vix_window).copy()
    w63.iloc[-1] = vix
    if len(w63) < 63:
        ivp63 = ivp
    else:
        ivp63 = round(float((w63.iloc[:-1] < float(w63.iloc[-1])).mean()) * 100.0, 1)
    regime_decay = (ivp >= 50.0) and (ivp63 < 50.0)

    ma20 = float(spx_window.rolling(20).mean().iloc[-1]) if len(spx_window) >= 20 else spx
    ma50 = float(spx_window.rolling(50).mean().iloc[-1]) if len(spx_window) >= 50 else spx
    ma200 = float(spx_window.rolling(200).mean().iloc[-1]) if len(spx_window) >= 200 else spx
    gap = (spx - ma50) / ma50 if ma50 else 0.0

    atr14 = None
    gap_sigma = None
    if len(spx_window) >= 64:
        atr_series = _compute_atr14_close(spx_window)
        latest_atr = atr_series.iloc[-1]
        if pd.notna(latest_atr):
            atr14 = float(latest_atr)
            gap_sigma = (spx - ma50) / max(atr14, 1.0)
    if DEFAULT_PARAMS.use_atr_trend and gap_sigma is not None:
        trend = _classify_trend_atr(gap_sigma)
    else:
        trend = (
            TrendSignal.BULLISH
            if gap > TREND_THRESHOLD
            else TrendSignal.BEARISH if gap < -TREND_THRESHOLD else TrendSignal.NEUTRAL
        )

    vix_5d_avg = float(vix_window.iloc[-5:].mean()) if len(vix_window) >= 5 else vix
    vix_5d_ago = float(vix_window.iloc[-10:-5].mean()) if len(vix_window) >= 10 else vix_5d_avg
    vix_peak_10d = float(vix_window.iloc[-10:].max()) if len(vix_window) >= 10 else None

    vix_snap = VixSnapshot(
        date=entry_date,
        vix=vix,
        regime=regime,
        trend=_vix_classify_trend(vix_5d_avg, vix_5d_ago),
        vix_5d_avg=vix_5d_avg,
        vix_5d_ago=vix_5d_ago,
        transition_warning=False,
        vix3m=vix3m,
        backwardation=(vix3m is not None and vix > vix3m),
        vix_peak_10d=vix_peak_10d,
    )
    iv_snap = IVSnapshot(
        date=entry_date,
        vix=vix,
        iv_rank=ivr,
        iv_percentile=ivp,
        iv_signal=SelectorIVSignal(_effective_iv_signal(ivp)),
        iv_52w_high=float(iv_window.max()),
        iv_52w_low=float(iv_window.min()),
        ivp63=ivp63,
        ivp252=ivp,
        regime_decay=regime_decay,
    )
    trend_snap = TrendSnapshot(
        date=entry_date,
        spx=spx,
        ma20=ma20,
        ma50=ma50,
        ma_gap_pct=gap,
        signal=trend,
        above_200=(spx > ma200),
        atr14=atr14,
        gap_sigma=gap_sigma,
    )
    return select_strategy(vix_snap, iv_snap, trend_snap, DEFAULT_PARAMS)


def _legs_summary(rec) -> str:
    if not rec.legs:
        return ""
    return " | ".join(
        f"{leg.action} {leg.option} δ{leg.delta:.2f} {leg.dte}DTE"
        for leg in rec.legs
    )


def _leg_columns(rec) -> dict:
    out = {
        "short_call_delta": "",
        "long_call_delta": "",
        "short_put_delta": "",
        "long_put_delta": "",
        "short_call_dte": "",
        "long_call_dte": "",
        "short_put_dte": "",
        "long_put_dte": "",
        "short_call_strike": "",
        "long_call_strike": "",
        "short_put_strike": "",
        "long_put_strike": "",
    }
    for leg in rec.legs:
        side = "short" if leg.action == "SELL" else "long"
        opt = "call" if leg.option == "CALL" else "put"
        out[f"{side}_{opt}_delta"] = round(float(leg.delta), 4)
        out[f"{side}_{opt}_dte"] = int(leg.dte)
        # Strike is not stored in Recommendation legs; fill later from built engine legs if available.
    return out


def _starting_dte(rec, trade) -> int:
    if rec.legs:
        short_legs = [leg for leg in rec.legs if leg.action == "SELL"]
        if short_legs:
            return short_legs[0].dte
        return rec.legs[0].dte
    return int(trade.dte_at_entry)


def _net_option_px_exit(trade) -> float | None:
    if not trade.contracts:
        return None
    return trade.entry_credit + (trade.exit_pnl / (trade.contracts * 100.0))


def _entry_exit_vix(vix_df: pd.DataFrame, date_str: str) -> float | None:
    dt = pd.Timestamp(date_str)
    if dt in vix_df.index:
        value = vix_df.loc[dt, "vix"]
        if pd.notna(value):
            return round(float(value), 2)
    return None


def _engine_strike_columns(trade, rec) -> dict:
    """
    Rebuild the selector recommendation and corresponding engine legs so we can export
    concrete strikes per leg instead of only the target deltas.
    """
    from backtest.engine import _build_legs

    sigma = float(trade.entry_vix) / 100.0
    legs, _ = _build_legs(rec, float(trade.entry_spx), sigma, DEFAULT_PARAMS)
    out = {
        "short_call_strike": "",
        "long_call_strike": "",
        "short_put_strike": "",
        "long_put_strike": "",
    }
    for action, is_call, strike, _dte, _qty in legs:
        side = "short" if action < 0 else "long"
        opt = "call" if is_call else "put"
        out[f"{side}_{opt}_strike"] = round(float(strike), 2)
    return out


def export_trade_detail_csv(start_date: str, end_date: str | None, output_path: Path) -> Path:
    result = run_backtest(start_date=start_date, end_date=end_date, verbose=False)
    signal_map = {row["date"]: row for row in result.signals}
    vix_df, spx_df, vix3m_df = _load_daily_frames()

    rows: list[dict] = []
    for trade in result.trades:
        signal = signal_map.get(trade.entry_date, {})
        rec = _entry_recommendation(
            trade.entry_date,
            vix_df=vix_df,
            spx_df=spx_df,
            vix3m_df=vix3m_df,
        )
        leg_cols = _leg_columns(rec)
        leg_cols.update(_engine_strike_columns(trade, rec))
        exit_px = _net_option_px_exit(trade)
        rows.append(
            {
                "entry_date": trade.entry_date,
                "exit_date": trade.exit_date,
                "strategy": trade.strategy.value,
                "strategy_key": rec.strategy_key,
                "type": strategy_descriptor(rec.strategy_key).trade_type,
                "entry_spx": round(trade.entry_spx, 2),
                "exit_spx": round(trade.exit_spx, 2),
                "entry_vix": round(trade.entry_vix, 2),
                "exit_vix": _entry_exit_vix(vix_df, trade.exit_date),
                "entry_vix3m": round(float(rec.vix_snapshot.vix3m), 2) if rec.vix_snapshot.vix3m is not None else "",
                "backwardation": rec.backwardation,
                "ivr": signal.get("ivr"),
                "ivp": signal.get("ivp"),
                "iv_signal": signal.get("iv_signal"),
                "ivp63": signal.get("ivp63"),
                "ivp252": signal.get("ivp252"),
                "regime": signal.get("regime"),
                "trend": signal.get("trend"),
                "trend_gap_pct": signal.get("trend_gap"),
                "hv_spell_age": signal.get("hv_spell_age"),
                "bearish_streak": signal.get("bearish_streak"),
                "starting_dte": _starting_dte(rec, trade),
                "dte_at_entry": trade.dte_at_entry,
                "dte_at_exit": trade.dte_at_exit,
                "hold_days_dte": max(trade.dte_at_entry - trade.dte_at_exit, 0),
                "hold_days_calendar": (pd.Timestamp(trade.exit_date) - pd.Timestamp(trade.entry_date)).days,
                "legs": _legs_summary(rec),
                "net_option_px_enter": round(trade.entry_credit, 4),
                "net_option_px_exit": round(exit_px, 4) if exit_px is not None else "",
                "option_premium_enter_usd": round(trade.option_premium, 2),
                "option_premium_exit_usd": round(abs(exit_px or 0.0) * 100.0, 2),
                "entry_reason": rec.rationale,
                "exit_reason": trade.exit_reason,
                "exit_pnl_usd": round(trade.exit_pnl, 2),
                "contracts": trade.contracts,
                "total_bp": trade.total_bp,
                "bp_pct_account": trade.bp_pct_account,
                "open_at_end": trade.open_at_end,
                **leg_cols,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export detailed 3-year backtest trades to CSV.")
    parser.add_argument("--start-date", default=_default_start_date())
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--output", default=f"data/backtest_trades_3y_{date.today().isoformat()}.csv")
    args = parser.parse_args()

    output = export_trade_detail_csv(args.start_date, args.end_date, Path(args.output))
    print(output)


if __name__ == "__main__":
    main()
