"""Q071 P5 — Full portfolio viability of the recommended config.

Per P2/P3/P4 conclusions:
  Recommended config = V2f base + G6 gate (VIX ≥ 22), Mode A (hard skip), STOP=15

Comparison: V2f_base (production current) vs G6_recommended.

Outputs:
  q071_p5_results.csv       full portfolio metrics table
  q071_p5_yearly.csv        per-year pnl breakdown
  q071_p5_crisis.csv        2008/2020/2022 window breakdown
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from research.q071.q071_engine import run_v2f_with_gate, run_bootstrap, gate_pass_all  # noqa: E402
from research.q071.q071_p2_gate_sweep import _g6  # noqa: E402
from research.q071.q071_p3_cadence import worst_cluster_3m_nlv, slot_occupancy_pct  # noqa: E402

OUT = REPO / "research" / "q071"

NLV = 500_000.0
# ES futures SPAN is ~$15k/contract for 49-DTE 20-delta puts (typical); estimate for cross-check.
# (V2f actually uses SPX puts under Schwab PM, this is just for the prompt's "/ES SPAN" line.)
ES_SPAN_PER_CONTRACT_USD = 15_000.0


def yearly_breakdown(r: dict) -> pd.DataFrame:
    if not r["trades"]:
        return pd.DataFrame()
    df = pd.DataFrame(r["trades"])
    df["exit_year"] = pd.to_datetime(df["exit_date"]).dt.year
    g = df.groupby("exit_year")
    out = g.agg(
        n_trades=("pnl", "size"),
        total_pnl=("pnl", "sum"),
        wins=("pnl", lambda s: int((s > 0).sum())),
        worst=("pnl", "min"),
    ).reset_index()
    out["wr_pct"] = out["wins"] / out["n_trades"] * 100
    out["pnl_pct_nlv"] = out["total_pnl"] / NLV * 100
    return out[["exit_year", "n_trades", "wr_pct", "total_pnl", "pnl_pct_nlv", "worst"]]


def crisis_breakdown(r: dict, windows: dict[str, tuple[str, str]]) -> pd.DataFrame:
    if not r["trades"]:
        return pd.DataFrame()
    rows = []
    df = pd.DataFrame(r["trades"])
    df["entry_dt"] = pd.to_datetime(df["entry_date"])
    df["exit_dt"]  = pd.to_datetime(df["exit_date"])
    for name, (start, end) in windows.items():
        s = pd.Timestamp(start)
        e = pd.Timestamp(end)
        active = df[(df["entry_dt"] <= e) & (df["exit_dt"] >= s)]
        # daily pnl in window
        dr_in = [dr for dr in r["daily_rows"] if s.strftime("%Y-%m-%d") <= dr.date <= e.strftime("%Y-%m-%d")]
        if dr_in:
            daily_pnl = pd.Series([dr.total_pnl for dr in dr_in])
            cum = daily_pnl.cumsum()
            window_pnl = float(cum.iloc[-1])
            worst_drawdown = float(cum.min())
            window_ann_ret = (1.0 + window_pnl / NLV) ** (252 / len(dr_in)) - 1.0
        else:
            window_pnl = 0.0
            worst_drawdown = 0.0
            window_ann_ret = 0.0
        worst_trade = float(active["pnl"].min()) if not active.empty else 0.0
        rows.append({
            "window":           name,
            "start":            start,
            "end":              end,
            "n_active":         int(len(active)),
            "window_pnl":       round(window_pnl, 0),
            "window_pnl_pct_nlv": round(window_pnl / NLV * 100, 2),
            "worst_cluster_pct_nlv": round(worst_drawdown / NLV * 100, 2),
            "worst_trade_nlv_pct": round(worst_trade / NLV * 100, 2),
            "ann_ret_in_window": round(window_ann_ret * 100, 2),
        })
    return pd.DataFrame(rows)


def full_metrics(r: dict, label: str) -> dict:
    boot = run_bootstrap(r, seeds=20, block_size=250)
    stops = sum(1 for t in r["trades"] if t["exit_reason"] == "stop_loss")
    stop_rate = stops / r["n_trades"] if r["n_trades"] > 0 else 0.0
    cluster_3m = worst_cluster_3m_nlv(r["daily_rows"])
    occ = slot_occupancy_pct(r["daily_rows"])
    # /ES SPAN estimate
    peak_span_usd = r["peak_slots"] * ES_SPAN_PER_CONTRACT_USD
    peak_span_pct_nlv = peak_span_usd / NLV * 100
    avg_span_usd  = r["avg_slots"]  * ES_SPAN_PER_CONTRACT_USD
    avg_span_pct_nlv  = avg_span_usd  / NLV * 100
    return {
        "label":                   label,
        "n_trades":                r["n_trades"],
        "ann_roe_geo_pct":         round(r["ann_roe_geo"] * 100, 3),
        "sharpe_daily_ann":        round(r["sharpe"], 3),
        "sortino_daily_ann":       round(r["sortino"], 3),
        "max_drawdown_pct":        round(r["max_drawdown"] * 100, 2),
        "worst_single_trade_nlv_pct":  round(r["worst_pnl_nlv"] * 100, 2),
        "worst_cluster_3m_nlv_pct": round(cluster_3m * 100, 2),
        "stop_hit_rate_pct":       round(stop_rate * 100, 2),
        "avg_active_slots":        round(r["avg_slots"], 2),
        "peak_active_slots":       r["peak_slots"],
        "slot_occupancy_pct":      round(occ, 1),
        "peak_bp_pct_nlv":         round(r["peak_bp_pct_nlv"] * 100, 1),
        "avg_es_span_pct_nlv_est": round(avg_span_pct_nlv, 1),
        "peak_es_span_pct_nlv_est": round(peak_span_pct_nlv, 1),
        "v1_pass":                 bool(r["v1_pass"]),
        "bootstrap_sig_rate_pct":  round(boot["sig_rate"] * 100, 1),
        "bootstrap_ci_lo_ann_pct": round(boot["ci_lo"] * 100, 3),
        "years":                   round(r["years"], 2),
        "total_pnl_usd":           round(r["final_equity"] - NLV, 0),
    }


def main() -> None:
    print("=" * 100)
    print("Q071 P5 — Portfolio Viability (2000-01-01 → present)")
    print("=" * 100)

    print("\n[1/2] Running V2f_base (production current state) …")
    r_base = run_v2f_with_gate(label="V2f_base_p5")
    print(f"  → n={r_base['n_trades']}  ann_roe={r_base['ann_roe_geo']*100:+.2f}%")

    print("\n[2/2] Running V2f + G6 gate (VIX ≥ 22) — recommended config …")
    r_g6 = run_v2f_with_gate(gate_fn=_g6, label="V2f_G6_p5")
    print(f"  → n={r_g6['n_trades']}  ann_roe={r_g6['ann_roe_geo']*100:+.2f}%")

    # ── Full metrics ─────────────────────────────────────────
    m_base = full_metrics(r_base, "V2f_base")
    m_g6   = full_metrics(r_g6, "V2f_G6 (recommended)")

    df = pd.DataFrame([m_base, m_g6])
    df.to_csv(OUT / "q071_p5_results.csv", index=False)
    print(f"\nWrote {OUT / 'q071_p5_results.csv'}")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    print("\n" + "=" * 100)
    print("Full portfolio viability table")
    print("=" * 100)
    print(df.T.to_string())

    # ── Yearly breakdown ─────────────────────────────────────
    yr_base = yearly_breakdown(r_base); yr_base["config"] = "V2f_base"
    yr_g6   = yearly_breakdown(r_g6);   yr_g6["config"]   = "V2f_G6"
    yr = pd.concat([yr_base, yr_g6], ignore_index=True)
    yr.to_csv(OUT / "q071_p5_yearly.csv", index=False)
    print(f"\nWrote {OUT / 'q071_p5_yearly.csv'}")

    # Worst-year
    print("\n── Worst calendar year ───────────────────────────")
    for cfg, sub in yr.groupby("config"):
        worst = sub.loc[sub["pnl_pct_nlv"].idxmin()]
        print(f"  {cfg:20}  worst year = {int(worst['exit_year'])}  pnl_pct_nlv = {worst['pnl_pct_nlv']:+.2f}%  n={int(worst['n_trades'])}")

    # ── Crisis windows ──────────────────────────────────────
    crisis = {
        "GFC_2008":      ("2008-08-01", "2009-03-31"),
        "COVID_2020":    ("2020-02-15", "2020-05-31"),
        "Bear_2022":     ("2022-01-01", "2022-12-31"),
    }
    print("\n── Crisis window breakdown ──────────────────────")
    for cfg_label, r in [("V2f_base", r_base), ("V2f_G6", r_g6)]:
        sub = crisis_breakdown(r, crisis)
        sub["config"] = cfg_label
        print(f"\n  [{cfg_label}]")
        print(sub.to_string(index=False))
        if cfg_label == "V2f_base":
            crisis_df = sub
        else:
            crisis_df = pd.concat([crisis_df, sub], ignore_index=True)
    crisis_df.to_csv(OUT / "q071_p5_crisis.csv", index=False)
    print(f"\nWrote {OUT / 'q071_p5_crisis.csv'}")

    # ── Final verdict ────────────────────────────────────────
    print("\n" + "=" * 100)
    print("PROMOTE / HOLD / DROP DECISION")
    print("=" * 100)
    print("Decision criteria (from memo P0):")
    print("  Promote if  (ann_roe ≥ base + 0.3pp AND dd not worse)")
    print("           OR (ann_roe ±0.1pp AND maxDD or 3m cluster improves ≥ 2pp)")
    print("  Veto if  V1 FAIL  OR  sig_rate < 80%  OR  peak SPAN > 30% NLV")
    print()
    delta_ann = m_g6["ann_roe_geo_pct"] - m_base["ann_roe_geo_pct"]
    delta_dd  = m_g6["max_drawdown_pct"] - m_base["max_drawdown_pct"]
    delta_clu = m_g6["worst_cluster_3m_nlv_pct"] - m_base["worst_cluster_3m_nlv_pct"]
    print(f"Δ ann_roe (G6 vs base):     {delta_ann:+.2f}pp")
    print(f"Δ max_dd  (G6 vs base):     {delta_dd:+.2f}pp  (positive = improved)")
    print(f"Δ worst_3m_cluster:         {delta_clu:+.2f}pp  (positive = improved)")
    print(f"G6 V1 pass:                 {m_g6['v1_pass']}")
    print(f"G6 sig_rate:                {m_g6['bootstrap_sig_rate_pct']}%")
    print(f"G6 peak SPAN est:           {m_g6['peak_es_span_pct_nlv_est']}% NLV")
    print()

    crit_a = (delta_ann >= 0.3) and (delta_dd >= 0)
    crit_b = (abs(delta_ann) <= 0.1) and (max(delta_dd, delta_clu) >= 2.0)
    veto_v1   = not m_g6["v1_pass"]
    veto_sig  = m_g6["bootstrap_sig_rate_pct"] < 80
    veto_span = m_g6["peak_es_span_pct_nlv_est"] > 30
    veto_any  = veto_v1 or veto_sig or veto_span

    print(f"Criterion A (ROE+0.3pp & dd ok):  {crit_a}")
    print(f"Criterion B (ROE flat & ≥2pp dd):  {crit_b}")
    print(f"Veto any:                          {veto_any}")
    print()
    if veto_any:
        verdict = "DROP"
    elif crit_a or crit_b:
        verdict = "PROMOTE"
    else:
        verdict = "HOLD"
    print(f"FINAL VERDICT: {verdict}")


if __name__ == "__main__":
    main()
