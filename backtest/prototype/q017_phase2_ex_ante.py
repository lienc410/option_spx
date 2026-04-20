"""
Q017 Phase 2 — Ex-ante identifiability

Phase 1 confirmed the aftermath-window missed-opportunity is real under
strategy PnL (IC_HV concentrated, system Sharpe non-degrading).

Phase 2 tests whether we can identify these windows WITHOUT hindsight:
  T2.2: peak_drop_pct — current VIX's drop from 10d peak
  T2.1: vix_3d_roc   — 3-day VIX rate of change vs current 5d VIX_RISING

Focus strategy: IC_HV (Phase 1 showed alpha concentrates here).

NO production code. NO Spec. NO full parameter grid — spot-check only.

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.q017_phase2_ex_ante
"""

from __future__ import annotations

import numpy as np

import strategy.selector as sel
import backtest.engine as engine_mod
from backtest.engine import run_backtest, Trade
from backtest.run_bootstrap_ci import bootstrap_ci
from signals.vix_regime import Trend

START = "2000-01-01"

PEAK_VIX_MIN = 28.0
PEAK_LOOKBACK = 10
OFF_PEAK_MIN_PCT = 0.05


def _identity(t):
    return (t.entry_date, t.strategy.value, round(t.entry_spx, 2), round(t.entry_vix, 2))


def _closed(trades):
    return [t for t in trades if t.exit_reason != "end_of_backtest"]


def _aftermath_dates(signals):
    aftermath = set()
    peak_at = {}
    for i, s in enumerate(signals):
        lo = max(0, i - PEAK_LOOKBACK)
        window = signals[lo:i + 1]
        if not window:
            continue
        peak = max(x["vix"] for x in window)
        if peak < PEAK_VIX_MIN:
            continue
        if s["vix"] >= peak * (1 - OFF_PEAK_MIN_PCT):
            continue
        aftermath.add(s["date"])
        peak_at[s["date"]] = peak
    return aftermath, peak_at


def _stats(pnls):
    if not pnls:
        return {"n": 0, "mean": 0, "total": 0, "win%": 0, "sharpe": 0.0, "ci_lo": None, "ci_hi": None}
    arr = np.array(pnls)
    n = len(arr)
    mu = float(arr.mean())
    sd = float(arr.std(ddof=1)) if n > 1 else 0.0
    ci = bootstrap_ci(arr.tolist()) if n >= 5 else {"ci_lo": float("nan"), "ci_hi": float("nan")}
    return {
        "n": n,
        "mean": round(mu),
        "total": int(arr.sum()),
        "win%": round((arr > 0).mean() * 100, 1),
        "sharpe": round(mu / sd, 2) if sd > 0 else 0.0,
        "ci_lo": ci["ci_lo"],
        "ci_hi": ci["ci_hi"],
    }


def _fmt_line(tag, st):
    if st["ci_lo"] is None or (isinstance(st["ci_lo"], float) and np.isnan(st["ci_lo"])):
        ci_s = "—"
        sig = ""
    else:
        ci_s = f"[${round(st['ci_lo']):,}, ${round(st['ci_hi']):,}]"
        sig = "SIG+" if st["ci_lo"] > 0 else ("SIG-" if st["ci_hi"] < 0 else "n.s.")
    return (f"    {tag:<28} n={st['n']:>3}  avg=${st['mean']:>+6,}  "
            f"total=${st['total']:>+8,}  win={st['win%']:>5.1f}%  "
            f"sharpe={st['sharpe']:>+5.2f}  CI95 {ci_s} {sig}")


def _patch_both_off():
    orig_ivp = sel.IVP63_BCS_BLOCK
    orig_vt = engine_mod._vix_classify_trend
    sel.IVP63_BCS_BLOCK = 999
    engine_mod._vix_classify_trend = lambda a, b: Trend.FLAT
    def undo():
        sel.IVP63_BCS_BLOCK = orig_ivp
        engine_mod._vix_classify_trend = orig_vt
    return undo


def run_study():
    # ── Baseline + signals ────────────────────────────────────────────
    print("  Baseline ...")
    bt_base = run_backtest(start_date=START, verbose=False)
    baseline_closed = _closed(bt_base.trades)
    baseline_ids = {_identity(t) for t in baseline_closed}

    signals = bt_base.signals
    aftermath, peak_at = _aftermath_dates(signals)
    sig_by_date = {s["date"]: s for s in signals}
    idx_by_date = {s["date"]: i for i, s in enumerate(signals)}

    # ── Variant C (both gates off) ────────────────────────────────────
    print("  Variant C (both gates off) ...")
    undo = _patch_both_off()
    try:
        bt_c = run_backtest(start_date=START, verbose=False)
    finally:
        undo()
    new_trades = [t for t in _closed(bt_c.trades) if _identity(t) not in baseline_ids]
    ic_hv_aftermath = [
        t for t in new_trades
        if t.strategy.value == "Iron Condor (High Vol)"
        and t.entry_date in aftermath
    ]
    print(f"    IC_HV aftermath new trades: {len(ic_hv_aftermath)}")

    # ── Enrich each trade with entry-time features ────────────────────
    rows = []
    for t in ic_hv_aftermath:
        i = idx_by_date.get(t.entry_date)
        if i is None:
            continue
        peak = peak_at[t.entry_date]
        vix = t.entry_vix
        peak_drop_pct = (peak - vix) / peak * 100

        # 3-day VIX ROC: (vix_today - vix_3d_ago) / vix_3d_ago
        vix_3d_ago = signals[max(0, i - 3)]["vix"]
        vix_3d_roc = (vix - vix_3d_ago) / vix_3d_ago * 100 if vix_3d_ago > 0 else 0

        # Current production VIX_RISING (recomputed):
        today_5d = signals[i].get("vix_5d_avg", vix)
        prior_5d = signals[max(0, i - 5)].get("vix_5d_avg", today_5d)
        if prior_5d > 0:
            vix_rising_5d = (today_5d - prior_5d) / prior_5d > 0.05
        else:
            vix_rising_5d = False

        rows.append({
            "date": t.entry_date,
            "pnl": t.exit_pnl,
            "vix": vix,
            "peak": peak,
            "peak_drop_pct": peak_drop_pct,
            "vix_3d_roc": vix_3d_roc,
            "vix_rising_5d": vix_rising_5d,
            "era": _era(t.entry_date),
        })

    # ── Print per-trade table ─────────────────────────────────────────
    print(f"\n{'=' * 100}")
    print(f"  IC_HV AFTERMATH TRADES (n={len(rows)})")
    print(f"{'=' * 100}")
    print(f"  {'Date':>12} {'PnL':>9} {'VIX':>6} {'Peak':>6} "
          f"{'Drop%':>7} {'3dROC%':>8} {'5dRising':>9}  Era")
    print(f"  {'-' * 12} {'-' * 9} {'-' * 6} {'-' * 6} "
          f"{'-' * 7} {'-' * 8} {'-' * 9}  {'-' * 12}")
    for r in sorted(rows, key=lambda x: x["date"]):
        print(f"  {r['date']:>12} ${r['pnl']:>+8,.0f} {r['vix']:>6.1f} {r['peak']:>6.1f} "
              f"{r['peak_drop_pct']:>+7.1f} {r['vix_3d_roc']:>+8.1f} "
              f"{str(r['vix_rising_5d']):>9}  {r['era']}")

    # ── Era breakdown ─────────────────────────────────────────────────
    print(f"\n{'=' * 100}")
    print(f"  BY ERA")
    print(f"{'=' * 100}")
    era_groups = {}
    for r in rows:
        era_groups.setdefault(r["era"], []).append(r["pnl"])
    for era in sorted(era_groups):
        print(_fmt_line(era, _stats(era_groups[era])))

    # ── T2.2 — peak_drop_pct bucketing ────────────────────────────────
    print(f"\n{'=' * 100}")
    print(f"  T2.2 — peak_drop_pct buckets (IC_HV aftermath)")
    print(f"{'=' * 100}")
    buckets_drop = [
        ("[5%, 10%)",   5.0, 10.0),
        ("[10%, 15%)", 10.0, 15.0),
        ("[15%, 20%)", 15.0, 20.0),
        ("[20%, 30%)", 20.0, 30.0),
        ("[30%+]",     30.0, 999.0),
    ]
    for label, lo, hi in buckets_drop:
        pnls = [r["pnl"] for r in rows if lo <= r["peak_drop_pct"] < hi]
        print(_fmt_line(label, _stats(pnls)))

    # Threshold sweeps: drop>=X
    print(f"\n  Threshold sweep: peak_drop_pct >= X")
    for thr in [5, 7, 10, 12, 15, 20]:
        pnls = [r["pnl"] for r in rows if r["peak_drop_pct"] >= thr]
        st = _stats(pnls)
        print(_fmt_line(f"drop >= {thr}%", st))

    # ── T2.1 — vix_3d_roc vs production 5d ────────────────────────────
    print(f"\n{'=' * 100}")
    print(f"  T2.1 — vix_3d_roc buckets (IC_HV aftermath)")
    print(f"{'=' * 100}")
    buckets_roc = [
        ("(-inf, -20%]", -999.0, -20.0),
        ("(-20%, -10%]",  -20.0, -10.0),
        ("(-10%,  0%]",   -10.0,   0.0),
        ("(0%,  +10%]",     0.0,  10.0),
        ("(+10%, +inf)",   10.0, 999.0),
    ]
    for label, lo, hi in buckets_roc:
        pnls = [r["pnl"] for r in rows if lo < r["vix_3d_roc"] <= hi]
        print(_fmt_line(label, _stats(pnls)))

    # Compare production 5d_rising vs alternative 3d_roc threshold
    print(f"\n  Rule comparison (what each filter would BLOCK):")

    prod_rising = [r for r in rows if r["vix_rising_5d"]]
    prod_stable = [r for r in rows if not r["vix_rising_5d"]]
    print(f"\n  Production rule (vix_rising_5d):")
    print(_fmt_line("would BLOCK (still rising)", _stats([r["pnl"] for r in prod_rising])))
    print(_fmt_line("would ALLOW (stable/falling)", _stats([r["pnl"] for r in prod_stable])))

    for roc_thr in [0, -5, -10]:
        blocked = [r for r in rows if r["vix_3d_roc"] > roc_thr]
        allowed = [r for r in rows if r["vix_3d_roc"] <= roc_thr]
        print(f"\n  Alt rule: vix_3d_roc <= {roc_thr}%  (3d VIX falling)")
        print(_fmt_line(f"would BLOCK (roc > {roc_thr}%)", _stats([r["pnl"] for r in blocked])))
        print(_fmt_line(f"would ALLOW (roc <= {roc_thr}%)", _stats([r["pnl"] for r in allowed])))

    # Combined rule: drop >= X AND roc <= Y
    print(f"\n  Combined rule: peak_drop_pct >= 10% AND vix_3d_roc <= 0%")
    combined = [r for r in rows if r["peak_drop_pct"] >= 10.0 and r["vix_3d_roc"] <= 0]
    print(_fmt_line("would ALLOW", _stats([r["pnl"] for r in combined])))

    # ── Losers detail — what were they? ───────────────────────────────
    print(f"\n{'=' * 100}")
    print(f"  LOSERS (useful for spotting false positives)")
    print(f"{'=' * 100}")
    losers = [r for r in rows if r["pnl"] < 0]
    if losers:
        for r in sorted(losers, key=lambda x: x["date"]):
            print(f"    {r['date']}  PnL=${r['pnl']:+,.0f}  VIX={r['vix']:.1f}  "
                  f"Peak={r['peak']:.1f}  Drop%={r['peak_drop_pct']:+.1f}  "
                  f"3dROC%={r['vix_3d_roc']:+.1f}  Era={r['era']}")
    else:
        print("    None.")


def _era(date: str) -> str:
    y = int(date[:4])
    if y < 2010:
        return "2000-2009"
    if y < 2020:
        return "2010-2019"
    if y < 2025:
        return "2020-2024"
    return "2025+"


if __name__ == "__main__":
    run_study()
