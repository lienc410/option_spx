"""
Q019 Tier 2.6 — Hourly-driven live simulation (recent 2y window)
===================================================================
Source: PM observation that Tier 2.5's "open snapshot" overstates live drag
because real live decisioning is dynamic — if open VIX = 24 spikes briefly
then settles to 19 by 11:00, the live system uses 19, not 24.

Method:
  - Fetch real hourly VIX 2024-05 to 2026-05 (2y, covers worst recent years)
  - For each trading day, define 4 candidate "current decision VIX" rules:
      A. close (4pm last bar)         — backtest baseline
      B. open  (first bar ≈ 9:30)     — Tier 2.5's pessimistic proxy
      C. 11:00 (1.5h after open)      — "wait for first hour to settle"
      D. stable (first hour where |VIX_h − VIX_{h-1}| < 0.5) — adaptive wait
  - Run engine 4 times with each rule injected via intraday_current
  - All other inputs identical (close-based 5d MA, IV history, peak_10d)
  - Compare PnL impact vs close baseline

Hypothesis: rules C and D will recover most of B's drag, because real live
behavior is closer to "wait for VIX to settle" than "decide at 9:30 panic".

Window: 2024-05-08 to 2026-05-08 (~520 trading days, 3 calendar years).
Tier 2.5 numbers for this window:
  2024 ΔPnL -$32k, 2025 -$66k, 2026 YTD -$21k = ~-$119k cumulative under open mode
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


def _strip_tz(df):
    idx = df.index
    if hasattr(idx, "tz") and idx.tz is not None:
        idx = idx.tz_localize(None)
    out = df.copy()
    out.index = idx.normalize() if hasattr(idx, "normalize") else idx
    return out


# ── Build per-day decision dicts from hourly VIX ─────────────────────────────

def build_decision_dicts() -> dict:
    """
    Returns dict of mode → {date_normalised: vix_value} mappings.
    Modes: open, eleven, stable, close.
    """
    print("  Fetching hourly VIX 2024-05 to 2026-05 …", flush=True)
    hv_raw = yf.Ticker("^VIX").history(period="2y", interval="1h")
    print(f"    raw rows: {len(hv_raw)}")

    # Convert to ET-naive for cleaner per-day grouping
    hv = hv_raw.copy()
    if hv.index.tz is not None:
        # Convert from Yahoo's tz to ET, drop tz
        hv.index = hv.index.tz_convert("America/New_York").tz_localize(None)

    hv["date"] = hv.index.normalize()
    hv["hour"] = hv.index.hour

    open_dict   = {}
    eleven_dict = {}
    stable_dict = {}
    close_dict  = {}

    for day, group in hv.groupby("date"):
        group = group.sort_index()
        if len(group) < 3:
            continue

        # Identify regular trading hours bars (9:30 ET to 16:00 ET)
        rth = group[(group["hour"] >= 9) & (group["hour"] <= 16)]
        if len(rth) < 2:
            rth = group  # fallback if hour filter empty (early data shape)

        opens  = rth["Open"].values
        closes = rth["Close"].values

        # A. close — last bar close
        close_dict[day] = float(closes[-1])

        # B. open — first bar open
        open_dict[day] = float(opens[0])

        # C. 11:00 — bar starting 11:00 ET (find the bar with hour == 11; fallback to 2nd bar)
        bar_11 = rth[rth["hour"] == 11]
        if len(bar_11) > 0:
            eleven_dict[day] = float(bar_11["Close"].iloc[0])
        elif len(rth) >= 2:
            eleven_dict[day] = float(closes[min(1, len(closes)-1)])
        else:
            eleven_dict[day] = float(closes[0])

        # D. stable — first hour where |VIX_h - VIX_{h-1}| < 0.5 (settled)
        stable_idx = 0  # default to first bar if never stabilises
        for i in range(1, len(closes)):
            if abs(closes[i] - closes[i-1]) < 0.5:
                stable_idx = i
                break
        stable_dict[day] = float(closes[stable_idx])

    return {
        "close":  close_dict,
        "open":   open_dict,
        "eleven": eleven_dict,
        "stable": stable_dict,
    }


# ── Build synthetic 1h frames for engine intraday_current injection ──────────

def build_synthetic_1h(
    decision_dict: dict,
    spx_close_series: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Each day → ONE row at 09:30 with vix=decision_value, spx=close.
    Engine groupby('_date').first() will pick this single row.
    """
    rows_vix = []
    rows_spx = []
    for d, v in sorted(decision_dict.items()):
        if d not in spx_close_series.index:
            continue
        ts = pd.Timestamp(d) + pd.Timedelta(hours=9, minutes=30)
        rows_vix.append({"ts": ts, "vix": float(v)})
        rows_spx.append({"ts": ts, "close": float(spx_close_series.loc[d])})

    vix_df = pd.DataFrame(rows_vix).set_index("ts")
    spx_df = pd.DataFrame(rows_spx).set_index("ts")
    return vix_df, spx_df


# ── Single-mode backtest run ─────────────────────────────────────────────────

def run_mode(
    label: str,
    syn_vix_1h: pd.DataFrame | None,
    syn_spx_1h: pd.DataFrame | None,
    start_date: str,
    end_date:   str,
):
    """
    If syn_*_1h is None → run baseline interval='1d' (close-based).
    Otherwise → run interval='1h' with monkey-patched fetches.
    """
    from backtest.engine import run_backtest
    import backtest.engine as engine_mod
    from signals.vix_regime import fetch_vix_history as orig_v
    from signals.trend     import fetch_spx_history as orig_s

    if syn_vix_1h is None:
        # Baseline run
        return run_backtest(start_date=start_date, end_date=end_date,
                             account_size=500_000, interval="1d", verbose=False)

    def patched_v(*args, **kwargs):
        interval = kwargs.get("interval", args[1] if len(args) > 1 else "1d")
        if interval == "1h":
            return syn_vix_1h.copy()
        return orig_v(*args, **kwargs)

    def patched_s(*args, **kwargs):
        interval = kwargs.get("interval", args[1] if len(args) > 1 else "1d")
        if interval == "1h":
            return syn_spx_1h.copy()
        return orig_s(*args, **kwargs)

    engine_mod.fetch_vix_history = patched_v
    engine_mod.fetch_spx_history = patched_s
    try:
        return run_backtest(start_date=start_date, end_date=end_date,
                             account_size=500_000, interval="1h", verbose=False)
    finally:
        engine_mod.fetch_vix_history = orig_v
        engine_mod.fetch_spx_history = orig_s


# ── Summary ──────────────────────────────────────────────────────────────────

def metrics(label: str, r) -> dict:
    trades = r.trades
    if not trades:
        return {"label": label, "n": 0, "total_pnl": 0, "ann_roe": 0,
                "wr": 0, "stop_rate": 0, "max_dd": 0}
    pnls = [t.exit_pnl for t in trades]
    wins = [t for t in trades if t.exit_pnl > 0]
    stops = [t for t in trades if t.exit_reason == "stop_loss"]
    start_nlv = 500_000.0
    years = (pd.Timestamp(trades[-1].exit_date or trades[-1].entry_date) -
              pd.Timestamp(trades[0].entry_date)).days / 365.25
    end_nlv = start_nlv + sum(pnls)
    ann_roe = ((end_nlv / start_nlv) ** (1 / max(years, 0.5)) - 1) * 100 if end_nlv > 0 else 0

    eq = start_nlv
    peak = start_nlv
    max_dd = 0.0
    for t in sorted(trades, key=lambda x: x.entry_date):
        eq += t.exit_pnl
        peak = max(peak, eq)
        dd = (peak - eq) / peak * 100
        max_dd = max(max_dd, dd)
    return {
        "label":     label,
        "n":         len(trades),
        "wr":        len(wins) / len(trades) * 100,
        "stop_rate": len(stops) / len(trades) * 100,
        "total_pnl": sum(pnls),
        "ann_roe":   ann_roe,
        "max_dd":    max_dd,
        "years":     years,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 90)
    print("Q019 Tier 2.6 — Hourly-driven live simulation (2024-05 to 2026-05)")
    print("=" * 90)

    START = "2024-05-08"
    END   = "2026-05-08"

    print("\n  Step 1: build per-day decision dicts from real hourly VIX …", flush=True)
    dicts = build_decision_dicts()

    # Quick sanity: per-mode VIX distribution
    print(f"\n  Decision-VIX statistics by rule (over {len(dicts['close'])} trading days):")
    print(f"    {'Mode':<8}  {'mean':>6}  {'P50':>6}  {'P90':>6}  {'P99':>6}")
    for mode, d in dicts.items():
        vals = pd.Series(d.values())
        print(f"    {mode:<8}  {vals.mean():>6.1f}  {vals.median():>6.1f}  "
              f"{vals.quantile(0.9):>6.1f}  {vals.quantile(0.99):>6.1f}")

    # Cross-mode same-day spread
    common_days = set(dicts["close"]) & set(dicts["open"]) & set(dicts["eleven"]) & set(dicts["stable"])
    diffs_oc = [dicts["open"][d] - dicts["close"][d] for d in common_days]
    diffs_11 = [dicts["eleven"][d] - dicts["close"][d] for d in common_days]
    diffs_st = [dicts["stable"][d] - dicts["close"][d] for d in common_days]
    print(f"\n  Same-day diff vs close (lower magnitude = closer to close):")
    print(f"    open  − close: mean abs {np.mean(np.abs(diffs_oc)):.2f}, P90 {np.percentile(np.abs(diffs_oc),90):.2f}")
    print(f"    11:00 − close: mean abs {np.mean(np.abs(diffs_11)):.2f}, P90 {np.percentile(np.abs(diffs_11),90):.2f}")
    print(f"    stable − close: mean abs {np.mean(np.abs(diffs_st)):.2f}, P90 {np.percentile(np.abs(diffs_st),90):.2f}")

    # Need SPX close series for synthetic 1h building
    from signals.trend import fetch_spx_history
    spx = _strip_tz(fetch_spx_history(period="max", interval="1d"))
    spx_close = spx["close"]

    # ── Step 2: run 4 engine modes ─────────────────────────────────────────
    runs = {}
    print(f"\n  Step 2: running 4 engine modes on {START} → {END} …", flush=True)

    print("    [1/4] close (baseline) …", flush=True)
    runs["close"] = run_mode("close", None, None, START, END)
    print(f"           trades: {len(runs['close'].trades)}")

    for mode in ("open", "eleven", "stable"):
        print(f"    [{['','open','eleven','stable'].index(mode)+1}/4] {mode} …", flush=True)
        v_1h, s_1h = build_synthetic_1h(dicts[mode], spx_close)
        runs[mode] = run_mode(mode, v_1h, s_1h, START, END)
        print(f"           trades: {len(runs[mode].trades)}")

    # ── Step 3: compare ────────────────────────────────────────────────────
    m_close  = metrics("close",  runs["close"])
    m_open   = metrics("open",   runs["open"])
    m_eleven = metrics("eleven", runs["eleven"])
    m_stable = metrics("stable", runs["stable"])

    print("\n\n" + "=" * 90)
    print(f"HEADLINE COMPARISON ({m_close['years']:.1f} years, $500k start NLV)")
    print("=" * 90)
    print(f"\n  {'Mode':<10}  {'n':>4}  {'WR':>6}  {'Total PnL':>13}  {'AnnROE':>8}  "
          f"{'MaxDD':>7}  {'Δ vs close':>13}")
    print(f"  {'─'*78}")
    base_pnl = m_close["total_pnl"]
    base_ann = m_close["ann_roe"]
    for m in [m_close, m_open, m_eleven, m_stable]:
        delta_pnl = m["total_pnl"] - base_pnl
        delta_pct = delta_pnl / base_pnl * 100 if base_pnl else 0
        delta_ann = m["ann_roe"] - base_ann
        ann_str = f"{delta_ann:+.2f}pp" if m["label"] != "close" else "—"
        pnl_str = f"${delta_pnl:+,.0f}" if m["label"] != "close" else "—"
        print(f"  {m['label']:<10}  {m['n']:>4}  {m['wr']:>5.1f}%  "
              f"${m['total_pnl']:>+11,.0f}  {m['ann_roe']:>7.2f}%  {m['max_dd']:>6.2f}%  "
              f"{pnl_str:>13}  {ann_str}")

    # ── Decomposition ────────────────────────────────────────────────────────
    print(f"\n\n  Recovery analysis (how much of open-mode drag is recovered by C/D):")
    open_drag = m_open["total_pnl"] - base_pnl
    eleven_drag = m_eleven["total_pnl"] - base_pnl
    stable_drag = m_stable["total_pnl"] - base_pnl
    if abs(open_drag) > 0:
        eleven_recovery = (1 - eleven_drag / open_drag) * 100 if open_drag != 0 else 0
        stable_recovery = (1 - stable_drag / open_drag) * 100 if open_drag != 0 else 0
        print(f"    Open mode drag: ${open_drag:+,.0f} (vs close baseline)")
        print(f"    11:00 recovers: {eleven_recovery:+.1f}% of open drag (residual ${eleven_drag:+,.0f})")
        print(f"    Stable recovers: {stable_recovery:+.1f}% of open drag (residual ${stable_drag:+,.0f})")

    # ── Per-year ─────────────────────────────────────────────────────────────
    print("\n\n" + "=" * 90)
    print("PER-YEAR PnL BY MODE")
    print("=" * 90)

    def year_pnl(trades):
        out = defaultdict(float)
        for t in trades:
            y = int(t.entry_date[:4]) if t.entry_date else 0
            out[y] += t.exit_pnl
        return out

    yp = {mode: year_pnl(runs[mode].trades) for mode in ("close", "open", "eleven", "stable")}
    years = sorted(set().union(*[set(yp[m]) for m in yp]))
    print(f"\n  {'Year':<6}  {'Close':>11}  {'Open':>11}  {'11:00':>11}  {'Stable':>11}  "
          f"{'Open Δ':>9}  {'11:00 Δ':>10}  {'Stable Δ':>10}")
    print(f"  {'─'*100}")
    for y in years:
        c, o, e, s = yp["close"][y], yp["open"][y], yp["eleven"][y], yp["stable"][y]
        print(f"  {y:<6}  ${c:>+9,.0f}  ${o:>+9,.0f}  ${e:>+9,.0f}  ${s:>+9,.0f}  "
              f"${o-c:>+8,.0f}  ${e-c:>+8,.0f}  ${s-c:>+8,.0f}")

    # ── Verdict ─────────────────────────────────────────────────────────────
    print("\n\n" + "=" * 90)
    print("TIER 2.6 VERDICT")
    print("=" * 90)
    print(f"""
  Tier 2.5 (open-only, full 19y): -0.63pp AnnROE, -$233k cumulative
  Tier 2.6 ({m_close['years']:.1f}y window):
    open:   {m_open['ann_roe'] - base_ann:+.2f}pp  (${m_open['total_pnl'] - base_pnl:+,.0f} drag)
    11:00:  {m_eleven['ann_roe'] - base_ann:+.2f}pp  (${m_eleven['total_pnl'] - base_pnl:+,.0f} drag)
    stable: {m_stable['ann_roe'] - base_ann:+.2f}pp  (${m_stable['total_pnl'] - base_pnl:+,.0f} drag)
""")

    best_recovery_mode = min(["eleven", "stable"],
                              key=lambda m: abs({"eleven": eleven_drag, "stable": stable_drag}[m]))
    if abs(open_drag) < 5000:
        print("  Note: open drag is small in this 2y sample — recovery analysis low-confidence.")
    elif min(abs(eleven_drag), abs(stable_drag)) < abs(open_drag) * 0.5:
        print(f"  ✅ Hourly-aware rule (best: {best_recovery_mode}) recovers ≥50% of open-mode drag.")
        print(f"     Implication: real live (with intraday adaptation) is materially better than")
        print(f"     Tier 2.5's open-snapshot proxy. Path A's documented ~0.6pp drag is overstated.")
    else:
        print(f"  ⚠️ Hourly-aware rules (11:00 / stable) DON'T meaningfully recover open drag.")
        print(f"     Implication: even with intraday adaptation, live faces meaningful drag.")
        print(f"     Tier 2.5's verdict stands; Path A's ~0.6pp drag is genuine.")


if __name__ == "__main__":
    main()
