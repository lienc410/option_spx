"""SPEC-120 — 26y force-entry matrix rerun under FLAT / CALIB / PESS.

Offsets: production skew monitor JSONL ∪ Q087 B2 backfill (mid-implied *_moff
fields only — pricing.calibration ignores vendor iv by design). Merge is
deduped by date, production first; per-source and missing-field counts are
printed and saved (AC-5).

Preflight AC-2: CALIB pricing of the 2026-07-02 real chain BPS 30DTE
δ.30/.15 vs actual mids must be <15% error (SPEC-119 AC-3 protocol, using
the MERGED offsets). The matrix run aborts if this gate fails.

Outputs (research/q087/):
  spec120_trades_{flat|calib|pess}.csv   trade-level, cell-labelled
  spec120_matrix_calib_compare.csv       per (strategy, cell) × mode summary,
                                         era columns, BCD carve row first (AC-4)
  spec120_offsets_stats.json             merger stats (AC-5)

Engine convention note: the matrix engine prices at T=dte/252 with sigma=
VIX/100 as its historical FLAT baseline. CALIB shifts each leg by the
mid-implied offset on top of that same baseline, isolating skew-offset
economics mode-vs-mode; absolute chain-fidelity is anchored by the paper
ledgers (SPEC-116), not by this engine.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import pandas as pd

from backtest.run_matrix_audit import run_matrix_audit
from pricing import core
from pricing.calibration import load_offsets_merged
from pricing.sigma import SigmaMode, sigma_for

OUT = REPO / "research" / "q087"
MODES = ("FLAT", "CALIB", "PESS")
PESS_BRACKET_VP = 1.0   # SPEC-120 §1.3: short legs −1vp / long legs +1vp

OFFSET_SOURCES = [
    REPO / "data" / "q085_skew_monitor.jsonl",                       # production
    Path.home() / "backups/oldair/data/q085_skew_monitor.jsonl",     # prod (backup pull)
    REPO / "research" / "q087" / "q087_moff_backfill.jsonl",         # Q087 B2 backfill
]

AC2_CHAIN = Path.home() / "backups/oldair/data/q041_chains/2026-07-02/SPX.parquet"


def build_offsets() -> tuple[dict, dict]:
    paths = [p for p in OFFSET_SOURCES if p.exists()]
    offsets, stats = load_offsets_merged(paths)
    print(f"offsets merged from {len(paths)} sources: "
          f"{stats['days_total']} days ({stats['days_no_moff']} without moff fields, "
          f"{stats['dupes_dropped']} date-dupes dropped)")
    for s in stats["sources"]:
        print(f"  · {s['path']}: {s['rows']} rows, {s['kept']} kept")
    (OUT / "spec120_offsets_stats.json").write_text(
        json.dumps({"stats": stats,
                    "curves": {f"{k[0]}|{k[1]}": v for k, v in offsets.items()}},
                   indent=1, sort_keys=True))
    return offsets, stats


def ac2_gate(offsets: dict) -> None:
    """SPEC-119 AC-3 protocol against the merged offsets."""
    if not AC2_CHAIN.exists():
        raise SystemExit(f"AC-2 chain missing: {AC2_CHAIN}")
    S = float(pd.read_pickle(REPO / "data/market_cache/yahoo__GSPC__max__1d.pkl").loc["2026-07-02"].Close)
    vix = float(pd.read_pickle(REPO / "data/market_cache/yahoo__VIX__max__1d.pkl").loc["2026-07-02"].Close)
    df = pd.read_parquet(AC2_CHAIN)
    puts = df[(df.option_type.str.upper() == "PUT") & df.iv.notna() & (df.iv > 1)].copy()
    covered = [d for d in sorted(puts[(puts.dte >= 25) & (puts.dte <= 35)].dte.unique())
               if puts[puts.dte == d].delta.abs().min() <= 0.16]
    dte = min(covered, key=lambda x: abs(x - 30))
    e = puts[puts.dte == dte].assign(ad=lambda x: x.delta.abs())
    T = dte / 365.0
    res = {}
    for tag, target in (("short_d30", 0.30), ("long_d15", 0.15)):
        leg = e.iloc[(e.ad - target).abs().argsort()].iloc[0]
        sig = sigma_for(SigmaMode.CALIB, vix=vix, option_type="PUT",
                        abs_delta=float(leg.ad), dte=int(dte), offsets=offsets)
        model = core.put_price(S, float(leg.strike), T, sig, 0.045, q=0.0)
        err = (model - leg.mid) / leg.mid * 100
        res[tag] = (model, float(leg.mid))
        print(f"AC-2 {tag}: K={leg.strike:.0f} model={model:.2f} mid={leg.mid:.2f} err {err:+.1f}%")
        assert abs(err) < 15, f"AC-2 FAIL on {tag}: {err:+.1f}%"
    cm = res["short_d30"][0] - res["long_d15"][0]
    cq = res["short_d30"][1] - res["long_d15"][1]
    err = (cm - cq) / cq * 100
    print(f"AC-2 net credit: model={cm:.2f} mid={cq:.2f} err {err:+.1f}%")
    assert abs(err) < 15, f"AC-2 FAIL on net credit: {err:+.1f}%"
    print("AC-2 PASS (<15%)")


def _summarize(trades: pd.DataFrame) -> dict:
    from backtest.run_matrix_audit import _worst_7y_net
    g2020 = trades[trades.entry_year >= 2020]
    g2024 = trades[trades.entry_year >= 2024]
    return {
        "n": len(trades),
        "win_rate": round(float((trades.pnl > 0).mean()), 3) if len(trades) else 0.0,
        "avg_pnl": round(float(trades.pnl.mean()), 0) if len(trades) else 0.0,
        "net_pnl": round(float(trades.pnl.sum()), 0),
        "worst7y_net": round(_worst_7y_net(trades), 0) if len(trades) else 0.0,
        "n_2020p": len(g2020), "net_2020p": round(float(g2020.pnl.sum()), 0),
        "n_2024p": len(g2024), "net_2024p": round(float(g2024.pnl.sum()), 0),
    }


def main(compare_only: bool = False) -> int:
    offsets, _stats = build_offsets()
    ac2_gate(offsets)

    trades_by_mode: dict[str, pd.DataFrame] = {}
    for mode in MODES:
        csv_path = OUT / f"spec120_trades_{mode.lower()}.csv"
        if compare_only and csv_path.exists():
            trades_by_mode[mode] = pd.read_csv(csv_path)
            print(f"{mode}: reusing {csv_path.name} ({len(trades_by_mode[mode])} trades)")
            continue
        print(f"\n=== matrix 26y {mode} ===")
        rows: list = []
        run_matrix_audit(save_csv=False, sigma_mode=mode,
                         sigma_offsets=None if mode == "FLAT" else offsets,
                         pess_bracket_vp=PESS_BRACKET_VP,
                         collect_trade_rows=rows)
        t = pd.DataFrame(rows)
        assert not t.isna().any().any(), f"NaN in {mode} trade rows (AC-3)"
        t.to_csv(csv_path, index=False)
        trades_by_mode[mode] = t
        print(f"{mode}: {len(t)} trades → {csv_path.name}")

    # ── compare CSV: per (strategy, cell) × mode + BCD carve row first (AC-4) ──
    out_rows: list[dict] = []

    def emit(label_strategy: str, label_cell: str, masks: dict, carve: bool):
        row: dict = {"strategy_key": label_strategy, "cell": label_cell,
                     "bcd_carve": carve}
        for mode in MODES:
            sub = masks[mode]
            s = _summarize(sub)
            for k, v in s.items():
                row[f"{k}_{mode.lower()}"] = v
        row["dnet_calib_minus_flat"] = round(
            row["net_pnl_calib"] - row["net_pnl_flat"], 0)
        out_rows.append(row)

    # AC-4: SPEC-113 carve — BCD in NORMAL × IV_LOW × BULLISH with VIX<18.
    # NB: the signals vocabulary spells the IV bucket "LOW" (IVSignal.value),
    # not "IV_LOW" — the selector docs use IV_LOW as the display name.
    carve_masks = {
        m: t[(t.strategy_key == "bull_call_diagonal") & (t.regime == "NORMAL")
             & (t.iv_signal == "LOW") & (t.trend == "BULLISH")
             & (t.entry_vix < 18.0)]
        for m, t in trades_by_mode.items()
    }
    emit("bull_call_diagonal", "SPEC-113_carve[NORMAL|IV_LOW|BULLISH|VIX<18]",
         carve_masks, carve=True)

    cells = trades_by_mode["FLAT"].groupby(
        ["strategy_key", "regime", "iv_signal", "trend"]).size().index
    for (sk, rg, iv, tr) in cells:
        masks = {m: t[(t.strategy_key == sk) & (t.regime == rg)
                      & (t.iv_signal == iv) & (t.trend == tr)]
                 for m, t in trades_by_mode.items()}
        emit(sk, f"{rg}|{iv}|{tr}", masks, carve=(sk == "bull_call_diagonal"))

    cmp_df = pd.DataFrame(out_rows)
    cmp_df["carve_row"] = cmp_df.cell.str.startswith("SPEC-113")
    cmp_df = cmp_df.sort_values(["carve_row", "bcd_carve", "strategy_key", "cell"],
                                ascending=[False, False, True, True]).drop(columns=["carve_row"])
    assert not cmp_df.isna().any().any(), "NaN in compare CSV (AC-3)"
    cmp_path = OUT / "spec120_matrix_calib_compare.csv"
    cmp_df.to_csv(cmp_path, index=False)
    print(f"\ncompare → {cmp_path} ({len(cmp_df)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main(compare_only="--compare-only" in sys.argv))
