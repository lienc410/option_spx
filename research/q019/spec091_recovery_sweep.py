"""
SPEC-091 F2 — Recovery sweep across θ candidates
==================================================
Builds on Tier 2.6 machinery. For each θ ∈ {0.4, 0.5, 0.6, 0.7, 0.8}, runs the
full engine with stable-rule injected via intraday_current and reports the
recovery rate vs open-mode drag.

Window: 2024-05 to 2026-05 (Yahoo 1h cap = 730 days), same as Tier 2.6.

This is the missing piece in F2 — operational stats favor θ=0.7-0.8,
but the actual research goal is recovery rate (closeness to backtest close baseline).
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

THETAS = [0.4, 0.5, 0.6, 0.7, 0.8]
START = "2024-05-08"
END   = "2026-05-08"


def _strip_tz(df):
    idx = df.index
    if hasattr(idx, "tz") and idx.tz is not None:
        idx = idx.tz_localize(None)
    out = df.copy()
    out.index = idx.normalize() if hasattr(idx, "normalize") else idx
    return out


def build_decision_dicts(thetas: list[float]) -> dict:
    """Returns dict of mode → {date: vix} mappings.
    Modes: close, open, stable_<θ> for each θ.
    """
    print("  Fetching 2y hourly VIX …", flush=True)
    hv_raw = yf.Ticker("^VIX").history(period="2y", interval="1h")
    hv = hv_raw.copy()
    if hv.index.tz is not None:
        hv.index = hv.index.tz_convert("America/New_York").tz_localize(None)
    hv["date"] = hv.index.normalize()
    hv["hour"] = hv.index.hour
    print(f"    {len(hv)} bars; {hv['date'].nunique()} days")

    out = {"close": {}, "open": {}}
    for theta in thetas:
        out[f"stable_{theta:.1f}"] = {}

    for day, group in hv.groupby("date"):
        group = group.sort_index()
        if len(group) < 3:
            continue
        rth = group[(group["hour"] >= 9) & (group["hour"] <= 16)]
        if len(rth) < 2:
            rth = group
        opens  = rth["Open"].values
        closes = rth["Close"].values

        out["close"][day] = float(closes[-1])
        out["open"][day]  = float(opens[0])

        for theta in thetas:
            # Stable rule: first bar i≥1 where |close[i] - close[i-1]| < theta
            stable_idx = 0  # fallback to first bar (== open mode) if never settles
            for i in range(1, len(closes)):
                if abs(closes[i] - closes[i - 1]) < theta:
                    stable_idx = i
                    break
            out[f"stable_{theta:.1f}"][day] = float(closes[stable_idx])

    return out


def build_synthetic_1h(decision_dict, spx_close_series):
    rows_v, rows_s = [], []
    for d, v in sorted(decision_dict.items()):
        if d not in spx_close_series.index:
            continue
        ts = pd.Timestamp(d) + pd.Timedelta(hours=9, minutes=30)
        rows_v.append({"ts": ts, "vix": float(v)})
        rows_s.append({"ts": ts, "close": float(spx_close_series.loc[d])})
    return (pd.DataFrame(rows_v).set_index("ts"),
            pd.DataFrame(rows_s).set_index("ts"))


def run_mode(label, syn_v, syn_s):
    from backtest.engine import run_backtest
    import backtest.engine as engine_mod
    from signals.vix_regime import fetch_vix_history as orig_v
    from signals.trend     import fetch_spx_history as orig_s

    if syn_v is None:
        return run_backtest(start_date=START, end_date=END,
                             account_size=500_000, interval="1d", verbose=False)

    def patched_v(*args, **kwargs):
        interval = kwargs.get("interval", args[1] if len(args) > 1 else "1d")
        return syn_v.copy() if interval == "1h" else orig_v(*args, **kwargs)
    def patched_s(*args, **kwargs):
        interval = kwargs.get("interval", args[1] if len(args) > 1 else "1d")
        return syn_s.copy() if interval == "1h" else orig_s(*args, **kwargs)

    engine_mod.fetch_vix_history = patched_v
    engine_mod.fetch_spx_history = patched_s
    try:
        return run_backtest(start_date=START, end_date=END,
                             account_size=500_000, interval="1h", verbose=False)
    finally:
        engine_mod.fetch_vix_history = orig_v
        engine_mod.fetch_spx_history = orig_s


def metrics(label, r):
    trades = r.trades
    if not trades:
        return {"label": label, "n": 0, "total_pnl": 0, "ann_roe": 0, "max_dd": 0}
    pnls = [t.exit_pnl for t in trades]
    start_nlv = 500_000.0
    years = (pd.Timestamp(trades[-1].exit_date or trades[-1].entry_date) -
              pd.Timestamp(trades[0].entry_date)).days / 365.25
    end_nlv = start_nlv + sum(pnls)
    ann_roe = ((end_nlv / start_nlv) ** (1 / max(years, 0.5)) - 1) * 100 if end_nlv > 0 else 0
    eq = peak = start_nlv
    max_dd = 0.0
    for t in sorted(trades, key=lambda x: x.entry_date):
        eq += t.exit_pnl
        peak = max(peak, eq)
        dd = (peak - eq) / peak * 100
        max_dd = max(max_dd, dd)
    return {"label": label, "n": len(trades),
            "total_pnl": sum(pnls), "ann_roe": ann_roe,
            "max_dd": max_dd, "years": years}


def main():
    print("=" * 100)
    print("SPEC-091 F2 — Recovery sweep across θ candidates")
    print("=" * 100)
    print(f"  Window: {START} → {END}, $500k start NLV")
    print(f"  θ candidates: {THETAS}")

    print("\n  Step 1: build decision dicts …", flush=True)
    dicts = build_decision_dicts(THETAS)

    print("\n  Decision-VIX summary (mean / median / P90):")
    for mode, d in dicts.items():
        v = pd.Series(d.values())
        print(f"    {mode:<12} mean={v.mean():.2f}  med={v.median():.2f}  P90={v.quantile(0.9):.2f}")

    from signals.trend import fetch_spx_history
    spx = _strip_tz(fetch_spx_history(period="max", interval="1d"))
    spx_close = spx["close"]

    print("\n  Step 2: running engine for each mode …\n", flush=True)

    runs = {}
    print("    [close baseline] running 1d interval …", flush=True)
    runs["close"] = run_mode("close", None, None)
    print(f"      → {len(runs['close'].trades)} trades")

    for mode in ["open"] + [f"stable_{θ:.1f}" for θ in THETAS]:
        print(f"    [{mode}] running 1h interval …", flush=True)
        v_1h, s_1h = build_synthetic_1h(dicts[mode], spx_close)
        runs[mode] = run_mode(mode, v_1h, s_1h)
        print(f"      → {len(runs[mode].trades)} trades")

    # Metrics
    M = {mode: metrics(mode, runs[mode]) for mode in runs}

    base_pnl = M["close"]["total_pnl"]
    base_ann = M["close"]["ann_roe"]
    open_drag = M["open"]["total_pnl"] - base_pnl
    open_ann_drag = M["open"]["ann_roe"] - base_ann

    print("\n\n" + "=" * 100)
    print(f"HEADLINE COMPARISON ({M['close']['years']:.2f} years)")
    print("=" * 100)
    print(f"\n  {'Mode':<14}  {'n':>4}  {'Total PnL':>14}  {'AnnROE':>8}  "
          f"{'MaxDD':>7}  {'ΔPnL vs close':>15}  {'ΔAnn':>8}  {'recovery%':>10}")
    print(f"  {'─' * 100}")

    for mode in ["close", "open"] + [f"stable_{θ:.1f}" for θ in THETAS]:
        m = M[mode]
        d_pnl = m["total_pnl"] - base_pnl
        d_ann = m["ann_roe"] - base_ann
        if mode == "close":
            d_pnl_str = "—"; d_ann_str = "—"; rec_str = "—"
        elif mode == "open":
            d_pnl_str = f"${d_pnl:+,.0f}"
            d_ann_str = f"{d_ann:+.2f}pp"
            rec_str = "0% (def)"
        else:
            recovery = (1 - d_pnl / open_drag) * 100 if abs(open_drag) > 0 else 0
            d_pnl_str = f"${d_pnl:+,.0f}"
            d_ann_str = f"{d_ann:+.2f}pp"
            rec_str = f"{recovery:+.1f}%"
        print(f"  {mode:<14}  {m['n']:>4}  ${m['total_pnl']:>+12,.0f}  {m['ann_roe']:>7.2f}%  "
              f"{m['max_dd']:>6.2f}%  {d_pnl_str:>15}  {d_ann_str:>8}  {rec_str:>10}")

    # Sweep recommendation
    print("\n\n" + "=" * 100)
    print("RECOVERY RATE SWEEP")
    print("=" * 100)

    print(f"\n  Open-mode drag baseline: ${open_drag:+,.0f} ({open_ann_drag:+.2f}pp AnnROE)")
    print(f"  Higher recovery% = closer to close baseline = better.")
    print(f"\n  {'θ':>5}  {'Δ PnL':>15}  {'Δ AnnROE':>10}  {'Recovery%':>10}")
    print(f"  {'─' * 50}")
    sweep = []
    for theta in THETAS:
        mode = f"stable_{theta:.1f}"
        m = M[mode]
        d_pnl = m["total_pnl"] - base_pnl
        d_ann = m["ann_roe"] - base_ann
        recovery = (1 - d_pnl / open_drag) * 100 if abs(open_drag) > 0 else 0
        sweep.append({"theta": theta, "d_pnl": d_pnl, "d_ann": d_ann, "recovery": recovery})
        print(f"  {theta:>5.2f}  ${d_pnl:>+13,.0f}  {d_ann:>+7.2f}pp  {recovery:>+8.1f}%")

    # Pick optimal
    best = max(sweep, key=lambda s: s["recovery"])
    print(f"\n  ➤ Best recovery: θ={best['theta']:.2f} → {best['recovery']:+.1f}% recovery, "
          f"{best['d_ann']:+.2f}pp AnnROE drag")

    # vs current SPEC value θ=0.5
    cur = next(s for s in sweep if abs(s["theta"] - 0.5) < 1e-6)
    if abs(best["theta"] - 0.5) < 1e-6:
        print(f"\n  ✅ θ=0.5 (current SPEC value) is recovery-optimal — keep it.")
    else:
        delta_rec = best["recovery"] - cur["recovery"]
        delta_ann = best["d_ann"] - cur["d_ann"]
        if delta_rec > 5:
            print(f"\n  ⚠ θ={best['theta']:.2f} materially better than θ=0.5 "
                  f"({delta_rec:+.1f}pp recovery, {delta_ann:+.2f}pp AnnROE).")
            print(f"     Consider updating SPEC-091 F2 to θ={best['theta']:.2f}.")
        else:
            print(f"\n  ⚪ θ={best['theta']:.2f} marginally better than θ=0.5 ({delta_rec:+.1f}pp). "
                  f"Either acceptable.")

    # Per-year breakdown for context
    print("\n\n" + "=" * 100)
    print("PER-YEAR PnL")
    print("=" * 100)

    def year_pnl(trades):
        out = defaultdict(float)
        for t in trades:
            y = int(t.entry_date[:4]) if t.entry_date else 0
            out[y] += t.exit_pnl
        return out

    yp = {mode: year_pnl(runs[mode].trades) for mode in runs}
    years = sorted(set().union(*[set(yp[m]) for m in yp]))
    cols = ["close", "open"] + [f"stable_{θ:.1f}" for θ in THETAS]
    print(f"\n  Year " + "  ".join(f"{c:>11}" for c in cols))
    print(f"  {'─' * (5 + len(cols) * 13)}")
    for y in years:
        row = f"  {y}  " + "  ".join(f"${yp[c][y]:>+9,.0f}" for c in cols)
        print(row)


if __name__ == "__main__":
    main()
