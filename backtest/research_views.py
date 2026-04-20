from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import backtest.engine as engine_mod
import strategy.selector as sel
from backtest.engine import BacktestResult, Trade, run_backtest
from strategy.catalog import strategy_key as catalog_strategy_key
from strategy.selector import StrategyName, StrategyParams

START_DATE = "2000-01-01"
RESEARCH_VIEWS_FILE = Path(__file__).resolve().parent.parent / "data" / "research_views.json"


def _params_hash() -> str:
    import hashlib

    canonical = json.dumps(asdict(StrategyParams()), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:10]


def _trade_identity(trade: Trade) -> tuple[str, str, str]:
    return trade.entry_date, trade.strategy.value, trade.underlying


def _closed_trades(trades: list[Trade]) -> list[Trade]:
    return [t for t in trades if t.exit_reason != "end_of_backtest"]


def _serialize_trade(trade: Trade, *, source_view: str) -> dict:
    return {
        "strategy": trade.strategy.value,
        "strategy_key": catalog_strategy_key(trade.strategy.value),
        "underlying": trade.underlying,
        "entry_date": trade.entry_date,
        "exit_date": trade.exit_date,
        "entry_spx": round(trade.entry_spx, 2),
        "exit_spx": round(trade.exit_spx, 2),
        "entry_vix": round(trade.entry_vix, 2),
        "entry_credit": round(trade.entry_credit, 2),
        "exit_pnl": round(trade.exit_pnl, 2),
        "exit_reason": trade.exit_reason,
        "dte_at_entry": trade.dte_at_entry,
        "dte_at_exit": trade.dte_at_exit,
        "spread_width": round(trade.spread_width, 0),
        "option_premium": round(trade.option_premium, 2),
        "bp_per_contract": round(trade.bp_per_contract, 2),
        "contracts": round(trade.contracts, 4),
        "total_bp": round(trade.total_bp, 2),
        "bp_pct_account": round(trade.bp_pct_account, 2),
        "source_view": source_view,
    }


def _view_payload(*, key: str, label: str, description: str, trades: list[Trade]) -> dict:
    return {
        "label": label,
        "description": description,
        "trades": [_serialize_trade(t, source_view=key) for t in trades],
    }


def _run_with_bps_upper(ivp_upper: int) -> BacktestResult:
    orig_upper = sel.BPS_NNB_IVP_UPPER
    try:
        sel.BPS_NNB_IVP_UPPER = ivp_upper
        return run_backtest(start_date=START_DATE, verbose=False)
    finally:
        sel.BPS_NNB_IVP_UPPER = orig_upper


def _run_dead_zone_a_variant() -> BacktestResult:
    from strategy.selector import (
        IVSignal,
        Leg,
        Regime,
        _build_recommendation,
        _effective_iv_signal,
        _size_rule,
        catalog_strategy_key,
        get_position_action,
        select_strategy as orig_select_strategy,
    )

    def patched_select(vix, iv, trend, params=sel.DEFAULT_PARAMS):
        rec = orig_select_strategy(vix, iv, trend, params)
        if (
            vix.regime == Regime.NORMAL
            and _effective_iv_signal(iv) == IVSignal.HIGH
            and trend.signal.value == "BULLISH"
            and rec.strategy == StrategyName.REDUCE_WAIT
        ):
            action = get_position_action(
                StrategyName.BULL_PUT_SPREAD.value,
                is_wait=False,
                strategy_key=catalog_strategy_key(StrategyName.BULL_PUT_SPREAD.value),
            )
            return _build_recommendation(
                StrategyName.BULL_PUT_SPREAD,
                vix=vix,
                iv=iv,
                trend=trend,
                legs=[
                    Leg("SELL", "PUT", 30, 0.30, "Short put"),
                    Leg("BUY", "PUT", 30, 0.05, "Long put (wing)"),
                ],
                size_rule=_size_rule(vix, IVSignal.HIGH, trend.signal),
                rationale="NORMAL + IV HIGH + BULLISH — patched to BPS for dead zone test",
                position_action=action,
                macro_warning=not trend.above_200,
            )
        return rec

    saved = engine_mod.select_strategy
    try:
        engine_mod.select_strategy = patched_select
        return run_backtest(start_date=START_DATE, verbose=False)
    finally:
        engine_mod.select_strategy = saved


def _run_with_aftermath_disabled() -> BacktestResult:
    orig_peak = sel.AFTERMATH_PEAK_VIX_10D_MIN
    try:
        sel.AFTERMATH_PEAK_VIX_10D_MIN = 999.0
        return run_backtest(start_date=START_DATE, verbose=False)
    finally:
        sel.AFTERMATH_PEAK_VIX_10D_MIN = orig_peak


def _recovery_dates(signals: list[dict]) -> set[str]:
    by_date = {row["date"]: idx for idx, row in enumerate(signals)}
    recovery: set[str] = set()
    for row in signals:
        if not (
            row["regime"] == "NORMAL"
            and row["iv_signal"] == "HIGH"
            and row["trend"] == "BULLISH"
        ):
            continue
        idx = by_date[row["date"]]
        for offset in range(1, 6):
            prev_idx = idx - offset
            if prev_idx >= 0 and signals[prev_idx]["regime"] == "HIGH_VOL":
                recovery.add(row["date"])
                break
    return recovery


def build_research_views() -> dict:
    baseline_result = run_backtest(start_date=START_DATE, verbose=False)
    baseline_closed = _closed_trades(baseline_result.trades)
    baseline_ids = {_trade_identity(t) for t in baseline_closed}

    # Baseline 已是 IVP<55（Q015 fast-path 入生产后）；对比 IVP<50 旧行为，
    # 展示 baseline 相对旧 gate 多出的 IVP [50,55) 边际交易。
    bt_ivp50 = _run_with_bps_upper(50)
    ivp50_ids = {_trade_identity(t) for t in _closed_trades(bt_ivp50.trades)}
    sig_by_date = {row["date"]: row for row in baseline_result.signals}
    q015_trades = [
        t
        for t in baseline_closed
        if _trade_identity(t) not in ivp50_ids
        and t.strategy.value == StrategyName.BULL_PUT_SPREAD.value
        and 50 <= float(sig_by_date.get(t.entry_date, {}).get("ivp", -1)) < 55
    ]

    bt_dza = _run_dead_zone_a_variant()
    recovery_dates = _recovery_dates(baseline_result.signals)
    q016_trades = [
        t
        for t in _closed_trades(bt_dza.trades)
        if _trade_identity(t) not in baseline_ids
        and t.strategy.value == StrategyName.BULL_PUT_SPREAD.value
        and t.entry_date in recovery_dates
    ]

    bt_no_aftermath = _run_with_aftermath_disabled()
    no_aftermath_ids = {_trade_identity(t) for t in _closed_trades(bt_no_aftermath.trades)}
    spec064_trades = [
        t
        for t in baseline_closed
        if _trade_identity(t) not in no_aftermath_ids
        and t.strategy.value == StrategyName.IRON_CONDOR_HV.value
    ]

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "params_hash": _params_hash(),
        "views": {
            "baseline": _view_payload(
                key="baseline",
                label="Baseline (Production)",
                description="当前生产参数的完整回测",
                trades=baseline_closed,
            ),
            "q015_ivp55_marginal": _view_payload(
                key="q015_ivp55_marginal",
                label="Q015: IVP [50,55) Marginal BPS",
                description="BPS gate 从 IVP<50 放宽到 IVP<55 的边际交易",
                trades=q015_trades,
            ),
            "q016_dza_recovery_bps": _view_payload(
                key="q016_dza_recovery_bps",
                label="Q016: Dead Zone A Recovery BPS",
                description="NORMAL+HIGH+BULLISH 恢复窗口 BPS（已否决，仅留存参考）",
                trades=q016_trades,
            ),
            "spec064_aftermath_ic_hv": _view_payload(
                key="spec064_aftermath_ic_hv",
                label="SPEC-064: Aftermath IC_HV",
                description="HIGH_VOL aftermath (10d peak VIX ≥ 28, ≥5% off peak, VIX < 40) 窗口 IC_HV bypass 触发的边际交易",
                trades=spec064_trades,
            ),
        },
    }


def generate_research_views(path: Path | None = None) -> Path:
    output = path or RESEARCH_VIEWS_FILE
    payload = build_research_views()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, default=str))
    return output


def main(argv: list[str] | None = None) -> int:
    args = argv or []
    if not args or args[0] != "generate":
        print("Usage: python -m backtest.research_views generate")
        return 1
    path = generate_research_views()
    print(f"Generated {path}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
