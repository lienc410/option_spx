"""
Tieout #3 — 2026-05-02 (post-batch-2: SPEC-079 + SPEC-080)
window: start=2023-04-29

Scenarios:
  A: PT=0.60, both disabled  → regression vs tieout #2 Q-C
  B: PT=0.60, comfort_filter=active
  C: PT=0.60, stop=active
  D: PT=0.60, both active     → preview convergence
  D_pt050: PT=0.50, both active → gap vs MC@0.50=52/$45,922
"""
from __future__ import annotations
import csv, json, sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backtest.engine import run_backtest, DEFAULT_PARAMS

WINDOW_START = "2023-04-29"
OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)

# Tieout #2 Q-C reference (PT=0.60, disabled)
T2_QC_TRADES = 57
T2_QC_PNL    = 79933.69

# MC fair-comparison reference (PT=0.50, all disabled, from MC handoff)
MC_PT050_TRADES = 52
MC_PT050_PNL    = 45922.0

TRADE_FIELDS = [
    "entry_date","exit_date","strategy","exit_reason","exit_pnl","open_at_end",
    "dte_at_entry","dte_at_exit","contracts","total_bp","bp_pct_account",
]

def _export(trades, path):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=TRADE_FIELDS)
        w.writeheader()
        for t in trades:
            row = {f: getattr(t, f, "") for f in TRADE_FIELDS}
            row["strategy"] = t.strategy.value if hasattr(t.strategy,"value") else str(t.strategy)
            w.writerow(row)

def _per_strategy(trades):
    out = {}
    for t in trades:
        k = t.strategy.value if hasattr(t.strategy,"value") else str(t.strategy)
        if k not in out:
            out[k] = {"count":0,"pnl":0.0,"open":0}
        out[k]["count"] += 1
        out[k]["pnl"] = round(out[k]["pnl"] + t.exit_pnl, 2)
        if getattr(t,"open_at_end",False):
            out[k]["open"] += 1
    return out

def _run(label, params):
    print(f"\n[{label}] running …")
    res = run_backtest(start_date=WINDOW_START, params=params, verbose=False)
    trades = res.trades
    pnl = sum(t.exit_pnl for t in trades)
    open_n = sum(1 for t in trades if getattr(t,"open_at_end",False))
    print(f"  trades={len(trades)}  open={open_n}  pnl={pnl:+,.2f}")
    _export(trades, OUT / f"tieout3_{label}_trades.csv")
    return {"trades": len(trades), "open_at_end": open_n,
            "total_pnl": round(pnl,2), "per_strategy": _per_strategy(trades)}

def main():
    print(f"=== Tieout #3  window={WINDOW_START} ===")

    r = {}
    r["A"] = _run("A_pt060_disabled",
        replace(DEFAULT_PARAMS))
    r["B"] = _run("B_pt060_comfort_active",
        replace(DEFAULT_PARAMS, bcd_comfort_filter_mode="active"))
    r["C"] = _run("C_pt060_stop_active",
        replace(DEFAULT_PARAMS, bcd_stop_tightening_mode="active"))
    r["D"] = _run("D_pt060_both_active",
        replace(DEFAULT_PARAMS,
                bcd_comfort_filter_mode="active",
                bcd_stop_tightening_mode="active"))
    r["D_pt050"] = _run("D_pt050_both_active",
        replace(DEFAULT_PARAMS,
                profit_target=0.50,
                bcd_comfort_filter_mode="active",
                bcd_stop_tightening_mode="active"))

    # Regression check: A vs tieout #2 Q-C
    delta_trades_A = r["A"]["trades"] - T2_QC_TRADES
    delta_pnl_A    = r["A"]["total_pnl"] - T2_QC_PNL
    regression_pass = (delta_trades_A == 0) and (abs(delta_pnl_A) < 1.0)

    # Gap vs MC: D_pt050 vs MC@PT=0.50
    gap_trades = r["D_pt050"]["trades"] - MC_PT050_TRADES
    gap_pnl    = r["D_pt050"]["total_pnl"] - MC_PT050_PNL

    summary = {
        "window_start": WINDOW_START,
        "regression_pass": regression_pass,
        "scenarios": r,
        "tieout2_qc_reference": {"trades": T2_QC_TRADES, "pnl": T2_QC_PNL},
        "regression_A_vs_t2qc": {
            "trade_delta": delta_trades_A,
            "pnl_delta": round(delta_pnl_A, 2),
            "pass": regression_pass,
        },
        "mc_reference_pt050": {"trades": MC_PT050_TRADES, "pnl": MC_PT050_PNL},
        "gap_D_pt050_vs_mc": {
            "hc_trades": r["D_pt050"]["trades"],
            "mc_trades": MC_PT050_TRADES,
            "trade_delta": gap_trades,
            "hc_pnl": r["D_pt050"]["total_pnl"],
            "mc_pnl": MC_PT050_PNL,
            "pnl_delta": round(gap_pnl, 2),
        },
    }
    (OUT / "tieout3_summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n=== Regression A vs tieout #2 Q-C ===")
    print(f"  A: {r['A']['trades']} trades / ${r['A']['total_pnl']:,.2f}")
    print(f"  T2 QC: {T2_QC_TRADES} trades / ${T2_QC_PNL:,.2f}")
    print(f"  delta: {delta_trades_A:+d} trades / ${delta_pnl_A:+,.2f}")
    print(f"  REGRESSION_PASS: {regression_pass}")

    print(f"\n=== Preview: D_pt050 both-active vs MC@0.50 ===")
    print(f"  HC both-active: {r['D_pt050']['trades']} trades / ${r['D_pt050']['total_pnl']:,.2f}")
    print(f"  MC@0.50:        {MC_PT050_TRADES} trades / ${MC_PT050_PNL:,.2f}")
    print(f"  gap delta: {gap_trades:+d} trades / ${gap_pnl:+,.2f}")

    print(f"\n=== All scenarios summary ===")
    for k, v in r.items():
        print(f"  [{k}] trades={v['trades']} open={v['open_at_end']} pnl=${v['total_pnl']:,.2f}")
    print(f"\nWrote → {OUT}")

if __name__ == "__main__":
    main()
