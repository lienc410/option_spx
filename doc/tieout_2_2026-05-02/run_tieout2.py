"""
Tieout #2 — 2026-05-02
两次 HC backtest：Q-A (PT=0.50) + Q-C (PT=0.60 default)
窗口：start=2023-04-29（与 tieout #1 相同）

输出（全部写到 doc/tieout_2_2026-05-02/）：
- tieout2_pt050_trades.csv   ← Q-A 用于与 tieout #1 CSV 比对
- tieout2_pt060_trades.csv   ← Q-C 新基线
- tieout2_summary.json       ← 各维度汇总 + 自洽性 verdict
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

# Tieout #1 reference（来自 data/backtest_trades_3y_2026-04-29.csv）
TIEOUT1_TRADES = 57
TIEOUT1_PNL    = 73952.0   # approximate; 精确到整数
TIEOUT1_REF_CSV = ROOT / "data" / "backtest_trades_3y_2026-04-29.csv"

# MC fair-comparison reference（PT=0.50，来自 MC_Handoff_2026-05-01_v5.md）
MC_PT050_TRADES = 52
MC_PT050_PNL    = 45922.0

TRADE_FIELDS = [
    "entry_date","exit_date","strategy","exit_reason","exit_pnl","open_at_end",
    "dte_at_entry","dte_at_exit","contracts","total_bp","bp_pct_account",
    "entry_spx","exit_spx","entry_vix","entry_credit","option_premium",
]

def _export_csv(trades, path: Path):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=TRADE_FIELDS)
        w.writeheader()
        for t in trades:
            row = {f: getattr(t, f, "") for f in TRADE_FIELDS}
            row["strategy"] = t.strategy.value if hasattr(t.strategy, "value") else str(t.strategy)
            w.writerow(row)

def _per_strategy(trades) -> dict:
    out = {}
    for t in trades:
        k = t.strategy.value if hasattr(t.strategy, "value") else str(t.strategy)
        if k not in out:
            out[k] = {"count": 0, "pnl": 0.0, "open": 0}
        out[k]["count"] += 1
        out[k]["pnl"] = round(out[k]["pnl"] + t.exit_pnl, 2)
        if getattr(t, "open_at_end", False):
            out[k]["open"] += 1
    return out

def _load_tieout1_entry_dates() -> set[str]:
    if not TIEOUT1_REF_CSV.exists():
        return set()
    dates = set()
    with TIEOUT1_REF_CSV.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            dates.add(row["entry_date"])
    return dates

def main():
    print(f"=== Tieout #2  window={WINDOW_START} ===")

    # Q-A：PT=0.50（验 batch-1 自洽性）
    print("\n[Q-A] PT=0.50 running …")
    res_a = run_backtest(
        start_date=WINDOW_START,
        params=replace(DEFAULT_PARAMS, profit_target=0.50),
        verbose=False,
    )
    trades_a = res_a.trades
    pnl_a = sum(t.exit_pnl for t in trades_a)
    _export_csv(trades_a, OUT / "tieout2_pt050_trades.csv")
    print(f"  trades={len(trades_a)}  pnl={pnl_a:+,.2f}")

    # Q-C：PT=0.60（当前 default）
    print("\n[Q-C] PT=0.60 (default) running …")
    res_c = run_backtest(
        start_date=WINDOW_START,
        verbose=False,
    )
    trades_c = res_c.trades
    pnl_c = sum(t.exit_pnl for t in trades_c)
    _export_csv(trades_c, OUT / "tieout2_pt060_trades.csv")
    print(f"  trades={len(trades_c)}  pnl={pnl_c:+,.2f}")

    # 自洽性：Q-A vs tieout #1
    tieout1_dates  = _load_tieout1_entry_dates()
    qa_dates       = {t.entry_date for t in trades_a}
    both     = tieout1_dates & qa_dates
    only_qa  = qa_dates - tieout1_dates
    only_t1  = tieout1_dates - qa_dates
    match_pct = len(both) / max(len(tieout1_dates | qa_dates), 1) * 100.0

    pnl_delta_qa_vs_t1 = pnl_a - TIEOUT1_PNL
    trade_delta_qa_vs_t1 = len(trades_a) - TIEOUT1_TRADES

    # 残余 gap vs MC@0.50
    gap_vs_mc_count = len(trades_a) - MC_PT050_TRADES
    gap_vs_mc_pnl   = pnl_a - MC_PT050_PNL

    # 自洽 verdict：match ≥ 99% 且 PnL 偏差 < $2,000（data refresh 容差）
    qa_self_consistent = (match_pct >= 99.0) and (abs(pnl_delta_qa_vs_t1) < 2000.0)

    per_a = _per_strategy(trades_a)
    per_c = _per_strategy(trades_c)

    summary = {
        "window_start": WINDOW_START,
        "qa_self_consistent": qa_self_consistent,
        "q_a_pt050": {
            "trades": len(trades_a),
            "open_at_end": sum(1 for t in trades_a if getattr(t, "open_at_end", False)),
            "total_pnl": round(pnl_a, 2),
            "per_strategy": per_a,
        },
        "q_c_pt060": {
            "trades": len(trades_c),
            "open_at_end": sum(1 for t in trades_c if getattr(t, "open_at_end", False)),
            "total_pnl": round(pnl_c, 2),
            "per_strategy": per_c,
        },
        "tieout1_reference": {
            "trades": TIEOUT1_TRADES,
            "pnl": TIEOUT1_PNL,
        },
        "self_consistency_qa_vs_tieout1": {
            "entry_date_match_pct": round(match_pct, 2),
            "only_in_qa": sorted(only_qa),
            "only_in_tieout1": sorted(only_t1),
            "trade_delta": trade_delta_qa_vs_t1,
            "pnl_delta": round(pnl_delta_qa_vs_t1, 2),
        },
        "hc_vs_mc_gap_pt050": {
            "hc_trades": len(trades_a),
            "mc_trades": MC_PT050_TRADES,
            "trade_delta": gap_vs_mc_count,
            "hc_pnl": round(pnl_a, 2),
            "mc_pnl": MC_PT050_PNL,
            "pnl_delta": round(gap_vs_mc_pnl, 2),
            "note": "Gap vs MC@0.50: batch 1 did not change selector/exit logic, so this is expected to be similar to tieout #1 gap. Real convergence requires SPEC-079/080 (batch 2).",
        },
    }
    (OUT / "tieout2_summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n=== 自洽性 Q-A vs tieout #1 ===")
    print(f"  entry date match:   {match_pct:.1f}%  (only_qa={sorted(only_qa)}, only_t1={sorted(only_t1)})")
    print(f"  trade delta:        {trade_delta_qa_vs_t1:+d}  ({len(trades_a)} vs {TIEOUT1_TRADES})")
    print(f"  PnL delta:          ${pnl_delta_qa_vs_t1:+,.0f}  ({pnl_a:,.0f} vs {TIEOUT1_PNL:,.0f})")
    print(f"  SELF_CONSISTENT:    {qa_self_consistent}")
    print(f"\n=== HC vs MC gap @ PT=0.50 ===")
    print(f"  HC {len(trades_a)} / MC {MC_PT050_TRADES}  → delta {gap_vs_mc_count:+d}")
    print(f"  HC ${pnl_a:,.0f} / MC ${MC_PT050_PNL:,.0f}  → delta ${gap_vs_mc_pnl:+,.0f}")
    print(f"\n=== Q-C 新基线 (PT=0.60) ===")
    print(f"  trades={len(trades_c)}  open={sum(1 for t in trades_c if getattr(t,'open_at_end',False))}  pnl={pnl_c:+,.2f}")
    print(f"\nWrote → {OUT}")

if __name__ == "__main__":
    main()
