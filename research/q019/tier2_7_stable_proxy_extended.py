"""
Q019 Tier 2.7 — Extended bad-years study using OHLC-based stable proxy
=======================================================================
Yahoo hourly VIX is hard-capped at 730 days, so we can't directly test
2018 / 2019 / 2021. Strategy:

  1. Define a stable-rule PROXY using daily OHLC: midpoint = (Open + Close) / 2
  2. Validate proxy quality on 2024-2026 by comparing to real stable rule from Tier 2.6
  3. If proxy ≈ real stable, apply proxy to full 19y, focus on bad years

Why midpoint? Tier 2.6 measurement on 515 trading days:
  - real stable rule mean |VIX - close| = 0.58
  - proxy midpoint mean |VIX - close| = 0.52
  Proxy is slightly *closer* to close than real stable (i.e., understates the drag
  by ~10%). Documented as proxy bias.

Worst years to focus on (per Tier 2.5):
  - 2018: -$121k (volmageddon)
  - 2021: -$77k
  - 2025: -$66k (Tier 2.6 has real data)
  - 2008: -$30k
  - 2024: -$32k (Tier 2.6 has real data)
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


def _build_synthetic_1h(vix_series_per_day: pd.Series, spx_close: pd.Series):
    """
    For each day in vix_series_per_day, produce one row at 09:30 with
    'vix' = the day's decision-VIX, 'close' = SPX close.
    Engine groupby('_date').first() picks this row.
    """
    rows_v = []
    rows_s = []
    for d, v in vix_series_per_day.dropna().items():
        if d not in spx_close.index:
            continue
        ts = pd.Timestamp(d) + pd.Timedelta(hours=9, minutes=30)
        rows_v.append({"ts": ts, "vix": float(v)})
        rows_s.append({"ts": ts, "close": float(spx_close.loc[d])})
    return (pd.DataFrame(rows_v).set_index("ts"),
            pd.DataFrame(rows_s).set_index("ts"))


def run_mode(label: str, syn_v_1h, syn_s_1h, start_date: str, end_date: str):
    from backtest.engine import run_backtest
    import backtest.engine as engine_mod
    from signals.vix_regime import fetch_vix_history as orig_v
    from signals.trend     import fetch_spx_history as orig_s

    if syn_v_1h is None:
        return run_backtest(start_date=start_date, end_date=end_date,
                             account_size=500_000, interval="1d", verbose=False)

    def patched_v(*a, **k):
        interval = k.get("interval", a[1] if len(a) > 1 else "1d")
        return syn_v_1h.copy() if interval == "1h" else orig_v(*a, **k)

    def patched_s(*a, **k):
        interval = k.get("interval", a[1] if len(a) > 1 else "1d")
        return syn_s_1h.copy() if interval == "1h" else orig_s(*a, **k)

    engine_mod.fetch_vix_history = patched_v
    engine_mod.fetch_spx_history = patched_s
    try:
        return run_backtest(start_date=start_date, end_date=end_date,
                             account_size=500_000, interval="1h", verbose=False)
    finally:
        engine_mod.fetch_vix_history = orig_v
        engine_mod.fetch_spx_history = orig_s


# ── Build proxy dicts ────────────────────────────────────────────────────────

def build_open_close_midpoint_dicts(vix_ohlc: pd.DataFrame):
    """Return per-day dicts: open, close, midpoint."""
    open_d  = vix_ohlc["Open"].copy()
    close_d = vix_ohlc["Close"].copy()
    mid_d   = ((open_d + close_d) / 2.0)
    return open_d, close_d, mid_d


def yearly_metrics(trades) -> dict:
    out = defaultdict(lambda: {"n": 0, "pnl": 0.0})
    for t in trades:
        if not t.entry_date:
            continue
        y = int(t.entry_date[:4])
        out[y]["n"] += 1
        out[y]["pnl"] += t.exit_pnl
    return dict(out)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 90)
    print("Q019 Tier 2.7 — Extended bad-years study using OHLC midpoint proxy")
    print("=" * 90)

    START = "2007-01-01"
    END   = None  # default to today

    print("\n  Loading data + building dicts …", flush=True)
    vix_ohlc = _load_vix_ohlc()
    from signals.trend import fetch_spx_history
    spx = _strip_tz(fetch_spx_history(period="max", interval="1d"))
    spx_close = spx["close"]

    open_d, close_d, mid_d = build_open_close_midpoint_dicts(vix_ohlc)

    # Sanity: proxy quality on 2024-2026 vs Tier 2.6 real stable rule
    recent_mask = vix_ohlc.index >= pd.Timestamp("2024-05-08")
    recent = vix_ohlc[recent_mask]
    open_v  = recent["Open"]
    close_v = recent["Close"]
    mid_v   = (open_v + close_v) / 2.0

    print(f"\n  Proxy quality check (2024-05 to 2026-05, n={len(recent)}):")
    print(f"    |open  − close| mean: {(open_v - close_v).abs().mean():.2f}, P90 {(open_v - close_v).abs().quantile(0.9):.2f}")
    print(f"    |mid   − close| mean: {(mid_v  - close_v).abs().mean():.2f}, P90 {(mid_v  - close_v).abs().quantile(0.9):.2f}")
    print(f"    Tier 2.6 real stable: 0.58 mean, 1.36 P90  (proxy is ~10% closer to close)")

    # ── Build synthetic 1h frames ────────────────────────────────────────────
    print("\n  Building synthetic 1h frames …", flush=True)
    open_v_1h,  open_s_1h  = _build_synthetic_1h(open_d,  spx_close)
    mid_v_1h,   mid_s_1h   = _build_synthetic_1h(mid_d,   spx_close)
    print(f"    open frame: {len(open_v_1h)} rows; mid frame: {len(mid_v_1h)} rows")

    # ── Run 3 modes on full 19y ──────────────────────────────────────────────
    print("\n  Running 3 modes (close, open, midpoint-proxy) on 2007 → today …", flush=True)
    print("    [1/3] close (baseline) …", flush=True)
    r_close = run_mode("close", None, None, START, END)
    print(f"           trades: {len(r_close.trades)}")
    print("    [2/3] open …", flush=True)
    r_open  = run_mode("open",  open_v_1h, open_s_1h,  START, END)
    print(f"           trades: {len(r_open.trades)}")
    print("    [3/3] midpoint (stable proxy) …", flush=True)
    r_mid   = run_mode("mid",   mid_v_1h,  mid_s_1h,   START, END)
    print(f"           trades: {len(r_mid.trades)}")

    # ── Per-year analysis ────────────────────────────────────────────────────
    yc = yearly_metrics(r_close.trades)
    yo = yearly_metrics(r_open.trades)
    ym = yearly_metrics(r_mid.trades)
    years = sorted(set(yc) | set(yo) | set(ym))

    print("\n\n" + "=" * 100)
    print("PER-YEAR PnL: close vs open vs midpoint-proxy")
    print("=" * 100)
    print(f"\n  {'Year':<6}  {'Close':>11}  {'Open':>11}  {'Mid (proxy)':>13}  "
          f"{'Open Δ':>10}  {'Mid Δ':>10}  {'Mid recovery%':>14}")
    print(f"  {'─'*92}")
    cum_open_drag = 0.0
    cum_mid_drag = 0.0
    for y in years:
        c = yc[y]["pnl"] if y in yc else 0
        o = yo[y]["pnl"] if y in yo else 0
        m = ym[y]["pnl"] if y in ym else 0
        open_d_v = o - c
        mid_d_v  = m - c
        cum_open_drag += open_d_v
        cum_mid_drag  += mid_d_v
        recovery = (1 - mid_d_v / open_d_v) * 100 if abs(open_d_v) > 5000 else float("nan")
        rec_str = f"{recovery:>13.1f}%" if not np.isnan(recovery) else "      —      "
        print(f"  {y:<6}  ${c:>+9,.0f}  ${o:>+9,.0f}  ${m:>+11,.0f}  "
              f"${open_d_v:>+8,.0f}  ${mid_d_v:>+8,.0f}  {rec_str}")
    print(f"  {'─'*92}")
    print(f"  Cumulative drag:  open={cum_open_drag:>+,.0f}  mid={cum_mid_drag:>+,.0f}  "
          f"recovery={(1 - cum_mid_drag/cum_open_drag)*100:.1f}%")

    # ── Worst-years focus ───────────────────────────────────────────────────
    print("\n\n" + "=" * 100)
    print("FOCUS: 5 WORST YEARS (largest |open Δ|)")
    print("=" * 100)
    drags = [(y, yo[y]["pnl"] - yc[y]["pnl"]) for y in years if y in yc and y in yo]
    drags_sorted = sorted(drags, key=lambda x: x[1])  # most negative first
    worst5 = drags_sorted[:5]
    print(f"\n  {'Year':<6}  {'Close':>11}  {'Open':>11}  {'Mid (proxy)':>13}  "
          f"{'Open Δ':>10}  {'Mid Δ':>10}  {'Mid recovery%':>14}")
    print(f"  {'─'*92}")
    cum_w_open = 0
    cum_w_mid  = 0
    for y, _ in worst5:
        c = yc[y]["pnl"]; o = yo[y]["pnl"]; m = ym[y]["pnl"]
        odv = o - c; mdv = m - c
        cum_w_open += odv; cum_w_mid += mdv
        rec = (1 - mdv/odv)*100 if abs(odv) > 5000 else float("nan")
        rec_str = f"{rec:>13.1f}%" if not np.isnan(rec) else "      —      "
        print(f"  {y:<6}  ${c:>+9,.0f}  ${o:>+9,.0f}  ${m:>+11,.0f}  "
              f"${odv:>+8,.0f}  ${mdv:>+8,.0f}  {rec_str}")
    print(f"  {'─'*92}")
    print(f"  Worst-5 cumulative: open={cum_w_open:>+,.0f}  mid={cum_w_mid:>+,.0f}  "
          f"recovery={(1 - cum_w_mid/cum_w_open)*100:.1f}%")

    # ── Recovery rate stability check ────────────────────────────────────────
    print("\n\n" + "=" * 100)
    print("RECOVERY RATE STABILITY — does midpoint proxy consistently recover?")
    print("=" * 100)
    bad_year_recoveries = []
    for y, odv in drags_sorted[:10]:  # 10 worst years
        if y not in yc or y not in ym:
            continue
        mdv = ym[y]["pnl"] - yc[y]["pnl"]
        if abs(odv) > 5000:
            rec = (1 - mdv/odv) * 100
            bad_year_recoveries.append(rec)
    rec_arr = np.array(bad_year_recoveries)
    print(f"\n  Recovery rates in 10 worst-drag years:")
    print(f"    mean:    {rec_arr.mean():>6.1f}%")
    print(f"    median:  {np.median(rec_arr):>6.1f}%")
    print(f"    P25-P75: {np.percentile(rec_arr,25):>6.1f}% — {np.percentile(rec_arr,75):>6.1f}%")
    print(f"    min:     {rec_arr.min():>6.1f}%")
    print(f"    max:     {rec_arr.max():>6.1f}%")
    print(f"\n  Reference: Tier 2.6 real stable rule recovered 67.4% of open drag (2024-2026)")

    # ── Total summary ────────────────────────────────────────────────────────
    total_close = sum(t.exit_pnl for t in r_close.trades)
    total_open  = sum(t.exit_pnl for t in r_open.trades)
    total_mid   = sum(t.exit_pnl for t in r_mid.trades)

    start_nlv = 500_000.0
    span_years = (pd.Timestamp(r_close.trades[-1].exit_date or r_close.trades[-1].entry_date) -
                   pd.Timestamp(r_close.trades[0].entry_date)).days / 365.25
    def ann_roe(total):
        end_nlv = start_nlv + total
        return ((end_nlv / start_nlv) ** (1/span_years) - 1) * 100 if end_nlv > 0 else 0

    print("\n\n" + "=" * 90)
    print(f"19y CUMULATIVE SUMMARY ($500k start, {span_years:.1f} years)")
    print("=" * 90)
    print(f"\n  {'Mode':<20}  {'Total PnL':>13}  {'AnnROE':>8}  {'Δ vs close':>14}  {'ΔAnnROE':>10}")
    print(f"  {'─'*72}")
    for label, t in [("close (baseline)", total_close),
                       ("open (Tier 2.5)", total_open),
                       ("midpoint proxy", total_mid)]:
        ann = ann_roe(t)
        delta = t - total_close
        d_ann = ann - ann_roe(total_close)
        ann_str = f"{d_ann:+.2f}pp" if "close" not in label else "—"
        delta_str = f"${delta:+,.0f}" if "close" not in label else "—"
        print(f"  {label:<20}  ${t:>+11,.0f}  {ann:>7.2f}%  {delta_str:>14}  {ann_str:>10}")

    # ── Verdict ─────────────────────────────────────────────────────────────
    print("\n\n" + "=" * 90)
    print("TIER 2.7 VERDICT")
    print("=" * 90)
    print(f"""
  Tier 2.5 (open mode, 19y): ΔAnnROE -0.63pp, drag $-233k
  Tier 2.7 (midpoint proxy ≈ stable rule, 19y):
    ΔAnnROE: {ann_roe(total_mid) - ann_roe(total_close):+.2f}pp
    drag:    ${total_mid - total_close:+,.0f}

  Worst-5-years recovery rate (median): {np.median(rec_arr):.0f}%
  Tier 2.6 real-stable on 2024-2026: 67.4% recovery

  Proxy bias: midpoint slightly closer to close than real stable
  (mean abs diff 0.52 vs 0.58). Real-stable would give a slightly larger
  drag than midpoint proxy reports. Caveat: subtract ~10% from recovery%
  to get conservative real-stable estimate.""")


if __name__ == "__main__":
    main()
