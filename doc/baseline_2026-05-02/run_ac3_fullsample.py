"""SPEC-077 AC3 full-sample HC rerun.

PM-required AC3 verification: rerun HC engine on the full sample with
profit_target=0.50 and profit_target=0.60, then check whether the directional
result matches Q037 Phase 2A's reported +0.91~+1.03pp ann ROE improvement.

Full-sample start: 2007-01-01 (VIX3M data starts 2006-07-17 — buffer for
rolling stats; first signals materialize after warm-up).

Outputs (under doc/baseline_2026-05-02/):
- ac3_metrics_pt050.json
- ac3_metrics_pt060.json
- ac3_summary.json   (delta + AC3 verdict)

Usage:  arch -arm64 venv/bin/python doc/baseline_2026-05-02/run_ac3_fullsample.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, is_dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backtest import engine as eng
from strategy.selector import DEFAULT_PARAMS

OUT = Path(__file__).resolve().parent
START = "2007-01-01"


def _to_serialisable(obj):
    if is_dataclass(obj):
        return {k: _to_serialisable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _to_serialisable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serialisable(v) for v in obj]
    if hasattr(obj, "value") and hasattr(obj, "name"):
        return obj.value
    return obj


def _run(pt: float) -> dict:
    params = replace(DEFAULT_PARAMS, profit_target=pt)
    print(f"  [PT={pt}] running {START} → today …")
    res = eng.run_backtest(start_date=START, verbose=False, params=params)
    m = _to_serialisable(res.metrics)
    print(f"    trades={m['total_trades']}  ann_roe={m['annualized_roe']:.4f}%  "
          f"sharpe={m['sharpe']:.2f}  max_dd={m['max_drawdown']:.0f}  "
          f"period_yrs={m['period_years']:.2f}")
    return m


def main() -> None:
    print(f"SPEC-077 AC3 full-sample rerun (start={START})")
    m050 = _run(0.50)
    m060 = _run(0.60)

    (OUT / "ac3_metrics_pt050.json").write_text(json.dumps(m050, indent=2))
    (OUT / "ac3_metrics_pt060.json").write_text(json.dumps(m060, indent=2))

    delta_ann_roe = m060["annualized_roe"] - m050["annualized_roe"]
    delta_sharpe = m060["sharpe"] - m050["sharpe"]
    delta_max_dd = m060["max_drawdown"] - m050["max_drawdown"]
    delta_total_pnl = m060["total_pnl"] - m050["total_pnl"]

    # AC3 (per SPEC-077.md): ann ROE 改善 ≥ +0.5pp 全样本，sharpe 不退化
    ac3_pass_roe = delta_ann_roe >= 0.5
    ac3_pass_sharpe = delta_sharpe >= 0.0
    ac3_pass = ac3_pass_roe and ac3_pass_sharpe
    # Q037 Phase 2A target band: +0.91 ~ +1.03 pp
    q037_band_lo, q037_band_hi = 0.91, 1.03
    in_q037_band = q037_band_lo <= delta_ann_roe <= q037_band_hi

    summary = {
        "start_date": START,
        "ac3_pass": ac3_pass,
        "ac3_pass_breakdown": {
            "roe_delta_ge_0_5pp": ac3_pass_roe,
            "sharpe_non_degrade": ac3_pass_sharpe,
        },
        "q037_phase2a_target": {"lo_pp": q037_band_lo, "hi_pp": q037_band_hi,
                                "hc_in_band": in_q037_band},
        "deltas": {
            "annualized_roe_pp": round(delta_ann_roe, 4),
            "sharpe": round(delta_sharpe, 4),
            "max_drawdown_usd": round(delta_max_dd, 2),
            "total_pnl_usd": round(delta_total_pnl, 2),
        },
        "pt050": {k: m050[k] for k in
                  ("total_trades", "n_open_at_end", "total_pnl",
                   "annualized_roe", "sharpe", "max_drawdown", "period_years")},
        "pt060": {k: m060[k] for k in
                  ("total_trades", "n_open_at_end", "total_pnl",
                   "annualized_roe", "sharpe", "max_drawdown", "period_years")},
    }
    (OUT / "ac3_summary.json").write_text(json.dumps(summary, indent=2))

    print()
    print(f"  Δ ann_roe = {delta_ann_roe:+.4f} pp  (Q037 band {q037_band_lo}~{q037_band_hi})")
    print(f"  Δ sharpe  = {delta_sharpe:+.4f}")
    print(f"  Δ max_dd  = ${delta_max_dd:+,.0f}")
    print(f"  AC3 PASS  = {ac3_pass}  (roe ≥ 0.5pp: {ac3_pass_roe}, sharpe non-degrade: {ac3_pass_sharpe})")
    print(f"  in Q037 band: {in_q037_band}")
    print(f"  Wrote → {OUT}")


if __name__ == "__main__":
    main()
