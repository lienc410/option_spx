"""
Q019 Tier 2.5 — Mixed-mode backtest: open VIX (current decision) + close VIX (history)
========================================================================================
PM-authorised after Tier 2 showed -1.37pp upper bound. 2nd Quant APPROVE.

Method (mirrors live behavior precisely):
  - Current-decision VIX  = OPEN  (proxies live intraday-near-open VIX)
  - 5d MA / peak_10d      = CLOSE-based history (unchanged from baseline)
  - IV history (252d)     = CLOSE-based (unchanged)
  - SPX                   = CLOSE-based (this study is about VIX only)

Implementation: use the engine's existing `intraday_current` mechanism
(designed for 1h-bar interval mode) by monkey-patching the 1h fetches
to return synthetic data where "first bar of each day" = VIX open.

Decision matrix (from R-20260509-08):
  |ΔAnnROE| < 0.5pp   → NEGLIGIBLE — Path A (document, no change)
  0.5 ≤ |ΔAnnROE| < 1  → MARGINAL — PM decides A vs C vs D (hysteresis)
  |ΔAnnROE| ≥ 1.0pp    → MATERIAL — evaluate Path C and Path D in parallel
"""
from __future__ import annotations

import sys
import pickle
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _strip_tz(df):
    idx = df.index
    if hasattr(idx, "tz") and idx.tz is not None:
        idx = idx.tz_localize(None)
    out = df.copy()
    out.index = idx.normalize()
    return out


def _load_vix_ohlc():
    path = ROOT / "data/market_cache/yahoo__VIX__max__1d.pkl"
    with open(path, "rb") as f:
        d = pickle.load(f)
    raw = d if isinstance(d, pd.DataFrame) else pd.DataFrame(d)
    return _strip_tz(raw)


def _build_synthetic_1h_vix(vix_ohlc: pd.DataFrame) -> pd.DataFrame:
    """
    Synthetic 'first 1h bar of each day' frame for the engine.
    Each day gets ONE row, timestamp at 09:30 ET (representative open).
    Column 'vix' = the day's OPEN value.
    Engine code at engine.py:761 calls .groupby('_date').first() on this,
    so a single row per day works perfectly.
    """
    out = pd.DataFrame({
        "vix": vix_ohlc["Open"].values,
    }, index=vix_ohlc.index + pd.Timedelta(hours=9, minutes=30))
    return out


def _build_synthetic_1h_spx(spx_close_df: pd.DataFrame) -> pd.DataFrame:
    """
    SPX 1h synthetic — we DON'T want to substitute SPX (this study is VIX-only).
    Provide same close value as 'first bar' so the override is effectively a no-op for SPX.
    Engine reads this as "close" column.
    """
    out = pd.DataFrame({
        "close": spx_close_df["close"].values,
    }, index=spx_close_df.index + pd.Timedelta(hours=9, minutes=30))
    return out


def _summarise_run(label: str, r) -> dict:
    trades = r.trades
    if not trades:
        return {"label": label, "n": 0}
    pnls = [t.exit_pnl for t in trades]
    wins = [t for t in trades if t.exit_pnl > 0]
    stops = [t for t in trades if t.exit_reason == "stop_loss"]
    start_nlv = 500_000.0
    end_nlv = start_nlv + sum(pnls)
    years = (pd.Timestamp(trades[-1].exit_date or trades[-1].entry_date) -
              pd.Timestamp(trades[0].entry_date)).days / 365.25
    ann_roe = ((end_nlv / start_nlv) ** (1 / years) - 1) * 100 if end_nlv > 0 else float("nan")
    # MaxDD from running equity
    eq = start_nlv
    peak = start_nlv
    max_dd = 0.0
    for t in sorted(trades, key=lambda x: x.entry_date):
        eq += t.exit_pnl
        peak = max(peak, eq)
        dd = (peak - eq) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)
    return {
        "label":     label,
        "n":         len(trades),
        "wr":        len(wins) / len(trades) * 100,
        "stop_rate": len(stops) / len(trades) * 100,
        "total_pnl": sum(pnls),
        "end_nlv":   end_nlv,
        "ann_roe":   ann_roe,
        "max_dd":    max_dd,
        "worst":     min(pnls),
        "best":      max(pnls),
    }


def main() -> None:
    print("=" * 90)
    print("Q019 Tier 2.5 — Mixed-mode: open VIX (decision) + close VIX (history)")
    print("=" * 90)

    from backtest.engine import run_backtest
    import backtest.engine as engine_mod
    from signals.vix_regime import fetch_vix_history as orig_vix_fetch
    from signals.trend     import fetch_spx_history as orig_spx_fetch

    # ── Pre-load OHLC for synthetic 1h injection ─────────────────────────────
    vix_ohlc = _load_vix_ohlc()
    spx_max  = _strip_tz(orig_spx_fetch(period="max", interval="1d"))
    print(f"  Source data: VIX OHLC {len(vix_ohlc)} days; SPX {len(spx_max)} days")
    syn_vix_1h = _build_synthetic_1h_vix(vix_ohlc)
    syn_spx_1h = _build_synthetic_1h_spx(spx_max)
    print(f"  Synthetic 1h frames: vix {len(syn_vix_1h)}, spx {len(syn_spx_1h)}")

    # ── Monkey-patch: route 1h fetches to synthetic frames ────────────────────
    def patched_vix_fetch(*args, **kwargs):
        interval = kwargs.get("interval", args[1] if len(args) > 1 else "1d")
        if interval == "1h":
            return syn_vix_1h.copy()
        return orig_vix_fetch(*args, **kwargs)

    def patched_spx_fetch(*args, **kwargs):
        interval = kwargs.get("interval", args[1] if len(args) > 1 else "1d")
        if interval == "1h":
            return syn_spx_1h.copy()
        return orig_spx_fetch(*args, **kwargs)

    # Also patch the engine module's reference to these names
    engine_mod.fetch_vix_history = patched_vix_fetch
    engine_mod.fetch_spx_history = patched_spx_fetch

    # ── Run baseline (close-only, interval="1d") ──────────────────────────────
    print("\n  [1/2] Running baseline close-everywhere (interval='1d') …", flush=True)
    try:
        r_close = run_backtest(start_date="2007-01-01", account_size=500_000,
                                interval="1d", verbose=False)
    finally:
        # Restore original fetches before next run wouldn't be needed yet,
        # but baseline already loaded — no harm to leave patches in place.
        pass
    print(f"        Trades: {len(r_close.trades)}")

    # ── Run mixed-mode (open at decision, close history, interval="1h") ──────
    print("  [2/2] Running mixed-mode open-decision/close-history (interval='1h') …", flush=True)
    try:
        r_mixed = run_backtest(start_date="2007-01-01", account_size=500_000,
                                interval="1h", verbose=False)
    finally:
        engine_mod.fetch_vix_history = orig_vix_fetch
        engine_mod.fetch_spx_history = orig_spx_fetch
    print(f"        Trades: {len(r_mixed.trades)}")

    # ── Compare ───────────────────────────────────────────────────────────────
    s_c = _summarise_run("Close (baseline)", r_close)
    s_m = _summarise_run("Mixed (open/close)", r_mixed)

    print("\n\n" + "=" * 90)
    print("HEADLINE COMPARISON — Close baseline vs Mixed-mode (open decision + close history)")
    print("=" * 90)
    print(f"\n  {'Metric':<14}  {'Close':>14}  {'Mixed':>14}  {'Δ':>14}  {'Δ%':>8}")
    print(f"  {'─'*70}")

    for k, fmt in [("n", "{:>14d}"), ("wr", "{:>13.1f}%"),
                    ("stop_rate", "{:>13.1f}%"), ("total_pnl", "${:>13,.0f}"),
                    ("end_nlv", "${:>13,.0f}"), ("ann_roe", "{:>13.2f}%"),
                    ("max_dd", "{:>13.2f}%"), ("worst", "${:>13,.0f}"),
                    ("best", "${:>13,.0f}")]:
        cv = s_c[k]; mv = s_m[k]
        delta = mv - cv
        if k == "n":
            dpct = (mv - cv) / cv * 100 if cv else 0
            print(f"  {k:<14}  {fmt.format(cv)}  {fmt.format(mv)}  "
                  f"{'{:>+14d}'.format(int(delta))}  {dpct:>+7.1f}")
        elif k in ("wr", "stop_rate", "ann_roe", "max_dd"):
            print(f"  {k:<14}  {fmt.format(cv)}  {fmt.format(mv)}  "
                  f"{'{:>+13.2f}pp'.format(delta)}  {'    --':>8}")
        else:
            dpct = (mv - cv) / abs(cv) * 100 if cv else 0
            print(f"  {k:<14}  {fmt.format(cv)}  {fmt.format(mv)}  "
                  f"{'${:>+13,.0f}'.format(delta)}  {dpct:>+7.1f}")

    # ── Trade overlap ────────────────────────────────────────────────────────
    close_keys = {(t.entry_date, str(t.strategy)) for t in r_close.trades}
    mixed_keys = {(t.entry_date, str(t.strategy)) for t in r_mixed.trades}
    shared = close_keys & mixed_keys
    print(f"\n  Trade overlap (same date+strategy):")
    print(f"    Close trades:  {len(close_keys)}")
    print(f"    Mixed trades:  {len(mixed_keys)}")
    print(f"    Shared:        {len(shared)}  "
          f"({len(shared)/max(len(close_keys),1)*100:.1f}% of close)")
    print(f"    Close-only:    {len(close_keys - mixed_keys)}")
    print(f"    Mixed-only:    {len(mixed_keys - close_keys)}")

    # ── Per-strategy ─────────────────────────────────────────────────────────
    def by_strategy(trades):
        out = defaultdict(lambda: {"n": 0, "pnl": 0.0})
        for t in trades:
            s = str(t.strategy).split('.')[-1]
            out[s]["n"] += 1
            out[s]["pnl"] += t.exit_pnl
        return dict(out)

    by_c = by_strategy(r_close.trades)
    by_m = by_strategy(r_mixed.trades)
    all_strats = sorted(set(by_c) | set(by_m))
    print(f"\n  Per-strategy:")
    print(f"    {'Strategy':<25}  {'Close n':>8}  {'Mixed n':>8}  {'Δn':>5}  "
          f"{'Close PnL':>12}  {'Mixed PnL':>12}  {'Δ PnL':>11}")
    print(f"    {'─'*88}")
    for s in all_strats:
        c = by_c.get(s, {"n": 0, "pnl": 0})
        m = by_m.get(s, {"n": 0, "pnl": 0})
        print(f"    {s:<25}  {c['n']:>8}  {m['n']:>8}  {m['n']-c['n']:>+5}  "
              f"${c['pnl']:>+11,.0f}  ${m['pnl']:>+11,.0f}  ${m['pnl']-c['pnl']:>+10,.0f}")

    # ── Per-year ─────────────────────────────────────────────────────────────
    def by_year(trades):
        pnl = defaultdict(float); cnt = defaultdict(int)
        for t in trades:
            y = int(t.entry_date[:4]) if t.entry_date else 0
            pnl[y] += t.exit_pnl; cnt[y] += 1
        return pnl, cnt

    pc, cc = by_year(r_close.trades)
    pm, cm = by_year(r_mixed.trades)
    years = sorted(set(pc) | set(pm))
    print(f"\n  Per-year:")
    print(f"    {'Year':<6}  {'Close n':>7}  {'Mixed n':>7}  {'Close PnL':>12}  {'Mixed PnL':>12}  {'Δ PnL':>11}")
    print(f"    {'─'*68}")
    for y in years:
        print(f"    {y:<6}  {cc.get(y,0):>7}  {cm.get(y,0):>7}  "
              f"${pc.get(y,0):>+11,.0f}  ${pm.get(y,0):>+11,.0f}  "
              f"${pm.get(y,0)-pc.get(y,0):>+10,.0f}")

    # ── Verdict ───────────────────────────────────────────────────────────────
    print(f"\n\n" + "=" * 90)
    print("TIER 2.5 VERDICT")
    print("=" * 90)
    ann_diff = s_m["ann_roe"] - s_c["ann_roe"]
    pnl_diff_pct = (s_m["total_pnl"] - s_c["total_pnl"]) / s_c["total_pnl"] * 100 if s_c["total_pnl"] else 0
    dd_diff = s_m["max_dd"] - s_c["max_dd"]

    # Reference: Tier 2 upper bound was -1.37pp
    print(f"\n  Tier 2.5 mixed-mode result:")
    print(f"    ΔAnnROE:    {ann_diff:+.2f}pp ({s_c['ann_roe']:.2f}% → {s_m['ann_roe']:.2f}%)")
    print(f"    ΔTotal PnL: {pnl_diff_pct:+.1f}%")
    print(f"    ΔMaxDD:     {dd_diff:+.2f}pp")
    print(f"\n  Tier 2 upper bound for reference: ΔAnnROE -1.37pp")
    if abs(s_c['ann_roe'] - 7.92) > 0.5:
        print(f"  [Note: close baseline AnnROE differs from Tier 2 baseline; check setup]")

    # Decomposition: how much of the upper bound comes from current-VIX vs history?
    fraction = abs(ann_diff) / 1.37 * 100 if abs(ann_diff) > 0 else 0
    print(f"\n  Component decomposition:")
    print(f"    Current-VIX substitution alone: ΔAnnROE = {ann_diff:+.2f}pp "
          f"({fraction:.0f}% of -1.37pp upper bound)")
    print(f"    Implied rolling-stat (history) component: "
          f"{abs(-1.37 - ann_diff):.2f}pp (the rest)")

    print()
    if abs(ann_diff) < 0.5:
        verdict_label = "✅ NEGLIGIBLE"
        path = "Path A — document and close. No production change needed."
    elif abs(ann_diff) < 1.0:
        verdict_label = "⚠️ MARGINAL"
        path = "Path A or C/D — PM decides. Tier 2.5 confirms current-VIX is the dominant component."
    else:
        verdict_label = "🔴 MATERIAL"
        path = "Path C and Path D in parallel — most error from current-VIX substitution; threshold hysteresis (Path D) is a clean candidate."
    print(f"  {verdict_label}: |ΔAnnROE| = {abs(ann_diff):.2f}pp")
    print(f"  → {path}")


if __name__ == "__main__":
    main()
