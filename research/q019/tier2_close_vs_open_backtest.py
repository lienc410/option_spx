"""
Q019 Tier 2 — Full backtest comparison: close-based VS open-based VIX
=====================================================================
PM-authorised after Tier 1 showed regime flip 9.48% (matches MC's 9.71%
reference). Tier 2 quantifies the actual PnL / trade-count impact.

Method:
  1. Run baseline backtest with default VIX history (close-based)
  2. Monkey-patch fetch_vix_history to return OPEN values
  3. Run substituted backtest (open-based throughout: current VIX, 5d MA,
     IV history all use OPEN)
  4. Compare:
     - Total trades / WR / stop rate
     - Total PnL / AnnROE / Sharpe / MaxDD
     - Per-year PnL diff
     - Trade-by-trade overlap (shared / close-only / open-only entries)

Important caveat:
  This is an UPPER BOUND. Live actually uses close-based history + intraday
  current VIX. Substituting the entire series with opens overstates the
  difference. If the upper bound is small (<1% AnnROE diff), the production
  change is safely negligible. If large (>2%), need a finer test.
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


def _strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index
    if hasattr(idx, "tz") and idx.tz is not None:
        idx = idx.tz_localize(None)
    out = df.copy()
    out.index = idx.normalize()
    return out


def _load_vix_open_as_close_series() -> pd.DataFrame:
    """Return VIX OHLC max-history with 'vix' column = OPEN (instead of close)."""
    path = ROOT / "data/market_cache/yahoo__VIX__max__1d.pkl"
    with open(path, "rb") as f:
        d = pickle.load(f)
    raw = d if isinstance(d, pd.DataFrame) else pd.DataFrame(d)
    raw = _strip_tz(raw)
    return pd.DataFrame({"vix": raw["Open"]}).dropna()


def _summarise(label: str, result) -> dict:
    trades = result.trades
    if not trades:
        return {"label": label, "n_trades": 0}
    pnls = [t.exit_pnl for t in trades]
    wins = [t for t in trades if t.exit_pnl > 0]
    stops = [t for t in trades if t.exit_reason == "stop_loss"]
    m = result.metrics
    return {
        "label":      label,
        "n_trades":   len(trades),
        "wr":         len(wins) / len(trades) * 100,
        "stop_rate":  len(stops) / len(trades) * 100,
        "total_pnl":  sum(pnls),
        "avg_pnl":    np.mean(pnls),
        "ann_return": m.get("ann_return", 0) * 100,
        "sharpe":     m.get("daily_sharpe", 0),
        "max_dd":     m.get("max_drawdown", 0) * 100,
        "win_pct":    m.get("win_rate", 0) * 100,
    }


def main() -> None:
    print("=" * 90)
    print("Q019 Tier 2 — Full backtest: close-based vs open-based VIX")
    print("=" * 90)

    # ── Run baseline (close-based) ─────────────────────────────────────────
    print("\n  [1/2] Running baseline (close-based VIX) …", flush=True)
    from backtest.engine import run_backtest
    r_close = run_backtest(start_date="2007-01-01", account_size=500_000, verbose=False)
    print(f"        Trades: {len(r_close.trades)}")

    # ── Run with open-substituted VIX ──────────────────────────────────────
    print("  [2/2] Running with OPEN-substituted VIX (full history) …", flush=True)
    import backtest.engine as engine_mod

    open_vix_df = _load_vix_open_as_close_series()
    original_fetch = engine_mod.fetch_vix_history

    def patched_fetch_vix_history(*args, **kwargs):
        return open_vix_df.copy()

    engine_mod.fetch_vix_history = patched_fetch_vix_history
    try:
        r_open = run_backtest(start_date="2007-01-01", account_size=500_000, verbose=False)
    finally:
        engine_mod.fetch_vix_history = original_fetch
    print(f"        Trades: {len(r_open.trades)}")

    # ── Summary ─────────────────────────────────────────────────────────────
    s_c = _summarise("Close (baseline)", r_close)
    s_o = _summarise("Open (full-substituted)", r_open)

    print("\n\n" + "=" * 90)
    print("HEADLINE METRICS COMPARISON")
    print("=" * 90)
    print(f"\n  {'Metric':<22}  {'Close (baseline)':>20}  {'Open (substituted)':>20}  "
          f"{'Δ':>15}  {'Δ%':>8}")
    print(f"  {'─'*88}")

    rows = [
        ("n_trades",   "{:>20.0f}",  "{:>15.0f}", lambda c, o: o - c, lambda c, o: (o-c)/c*100 if c else 0),
        ("wr",         "{:>19.1f}%", "{:>14.1f}pp", lambda c, o: o - c, lambda c, o: o - c),
        ("stop_rate",  "{:>19.1f}%", "{:>14.1f}pp", lambda c, o: o - c, lambda c, o: o - c),
        ("total_pnl",  "${:>18,.0f}", "${:>13,.0f}", lambda c, o: o - c, lambda c, o: (o-c)/c*100 if c else 0),
        ("avg_pnl",    "${:>18,.0f}", "${:>13,.0f}", lambda c, o: o - c, lambda c, o: (o-c)/c*100 if c else 0),
        ("ann_return", "{:>19.2f}%", "{:>13.2f}pp", lambda c, o: o - c, lambda c, o: o - c),
        ("sharpe",     "{:>20.3f}",  "{:>15.3f}",   lambda c, o: o - c, lambda c, o: (o-c)/c*100 if c else 0),
        ("max_dd",     "{:>19.2f}%", "{:>13.2f}pp", lambda c, o: o - c, lambda c, o: o - c),
    ]
    for key, fmt_c, fmt_d, dfn, dpct in rows:
        cv = s_c[key]
        ov = s_o[key]
        delta = dfn(cv, ov)
        delta_pct = dpct(cv, ov)
        print(f"  {key:<22}  " + fmt_c.format(cv) + "  " + fmt_c.format(ov) + "  "
              + fmt_d.format(delta) + f"  {delta_pct:>+7.1f}")

    # ── Trade-level overlap ─────────────────────────────────────────────────
    print("\n\n" + "=" * 90)
    print("TRADE OVERLAP (entry-date level)")
    print("=" * 90)

    close_keys = {(t.entry_date, str(t.strategy)) for t in r_close.trades}
    open_keys  = {(t.entry_date, str(t.strategy)) for t in r_open.trades}
    shared     = close_keys & open_keys
    close_only = close_keys - open_keys
    open_only  = open_keys - close_keys
    print(f"\n  Close trades:        {len(close_keys)}")
    print(f"  Open trades:         {len(open_keys)}")
    print(f"  Shared (same date+strategy):  {len(shared)}  "
          f"({len(shared)/max(len(close_keys),1)*100:.1f}% of close)")
    print(f"  Close-only:           {len(close_only)}")
    print(f"  Open-only:            {len(open_only)}")

    # ── Strategy-level diff ────────────────────────────────────────────────
    print("\n\n" + "=" * 90)
    print("PER-STRATEGY COMPARISON")
    print("=" * 90)

    def by_strategy(trades):
        out = defaultdict(lambda: {"n": 0, "pnl": 0.0, "wins": 0, "stops": 0})
        for t in trades:
            s = str(t.strategy).split('.')[-1]
            out[s]["n"] += 1
            out[s]["pnl"] += t.exit_pnl
            if t.exit_pnl > 0:
                out[s]["wins"] += 1
            if t.exit_reason == "stop_loss":
                out[s]["stops"] += 1
        return dict(out)

    by_c = by_strategy(r_close.trades)
    by_o = by_strategy(r_open.trades)
    all_strats = sorted(set(by_c) | set(by_o))

    print(f"\n  {'Strategy':<28}  {'Close n':>8}  {'Open n':>7}  Δn   "
          f"{'Close PnL':>12}  {'Open PnL':>12}  {'Δ PnL':>11}")
    print(f"  {'─'*98}")
    for s in all_strats:
        c = by_c.get(s, {"n": 0, "pnl": 0})
        o = by_o.get(s, {"n": 0, "pnl": 0})
        dn = o["n"] - c["n"]
        dp = o["pnl"] - c["pnl"]
        print(f"  {s:<28}  {c['n']:>8}  {o['n']:>7}  {dn:>+4}  "
              f"${c['pnl']:>+11,.0f}  ${o['pnl']:>+11,.0f}  ${dp:>+10,.0f}")

    # ── Per-year diff ───────────────────────────────────────────────────────
    print("\n\n" + "=" * 90)
    print("PER-YEAR PnL DIFF")
    print("=" * 90)

    def by_year(trades):
        out = defaultdict(float)
        cnt = defaultdict(int)
        for t in trades:
            y = int(t.entry_date[:4]) if t.entry_date else 0
            out[y] += t.exit_pnl
            cnt[y] += 1
        return out, cnt

    pnl_c, cnt_c = by_year(r_close.trades)
    pnl_o, cnt_o = by_year(r_open.trades)
    all_years = sorted(set(pnl_c) | set(pnl_o))
    print(f"\n  {'Year':<6}  {'Close n':>8}  {'Open n':>7}  Δn   "
          f"{'Close PnL':>12}  {'Open PnL':>12}  {'Δ PnL':>11}")
    print(f"  {'─'*78}")
    for y in all_years:
        cn = cnt_c.get(y, 0)
        on = cnt_o.get(y, 0)
        cp = pnl_c.get(y, 0)
        op = pnl_o.get(y, 0)
        dn = on - cn
        dp = op - cp
        print(f"  {y:<6}  {cn:>8}  {on:>7}  {dn:>+4}  "
              f"${cp:>+11,.0f}  ${op:>+11,.0f}  ${dp:>+10,.0f}")

    # ── Verdict ────────────────────────────────────────────────────────────
    print("\n\n" + "=" * 90)
    print("TIER 2 VERDICT")
    print("=" * 90)

    ann_diff = s_o["ann_return"] - s_c["ann_return"]
    pnl_diff_pct = (s_o["total_pnl"] - s_c["total_pnl"]) / s_c["total_pnl"] * 100 if s_c["total_pnl"] else 0
    sharpe_diff = s_o["sharpe"] - s_c["sharpe"]
    dd_diff = s_o["max_dd"] - s_c["max_dd"]

    print(f"\n  Headline differences (Open − Close):")
    print(f"    AnnROE:    {ann_diff:+.2f}pp ({pnl_diff_pct:+.1f}% of close PnL)")
    print(f"    Sharpe:    {sharpe_diff:+.3f}")
    print(f"    MaxDD:     {dd_diff:+.2f}pp")
    print(f"    Trade Δn:  {s_o['n_trades'] - s_c['n_trades']:+d}")
    print()
    if abs(ann_diff) < 0.5:
        print(f"  ✅ NEGLIGIBLE: |ΔAnnROE| < 0.5pp. Production VIX timing convention safely interchangeable.")
    elif abs(ann_diff) < 2.0:
        print(f"  ⚠️ MARGINAL: 0.5 ≤ |ΔAnnROE| < 2.0pp. PM decision: accept divergence or fix.")
    else:
        print(f"  🔴 MATERIAL: |ΔAnnROE| ≥ 2.0pp. Production VIX timing convention matters; recommend alignment.")
    print()
    print("  Caveat: this is an UPPER BOUND. Live uses close-based 5d MA / IV history with")
    print("  intraday current VIX. Full open substitution overstates the diff.")
    print("  If upper bound is small, production change definitely safe.")
    print("  If upper bound is large, consider a finer mixed-mode test.")


if __name__ == "__main__":
    main()
