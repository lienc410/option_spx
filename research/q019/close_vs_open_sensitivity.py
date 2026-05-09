"""
Q019 Tier 1 — close vs open-based VIX sensitivity scan
========================================================
Question: Does VIX open vs close materially change selector decisions?

Method:
  For each historical trading day (2007-2026):
    - Build IVSnapshot, TrendSnapshot from EOD close history (unchanged)
    - Build TWO VixSnapshots:
        VixSnapshot_close: current_vix = VIX close
        VixSnapshot_open:  current_vix = VIX open (same-day)
      Both share 5d avg, peak_10d, vix3m (all EOD-based — matches production)
    - Run select_strategy on each, compare:
        * regime flip
        * final strategy / route flip
        * position_action flip

Aggregate:
  - flip rates by layer (regime / route / action)
  - concentration by VIX bucket and year
  - flagged days: where open vs close gives different recommendation

Tier 1 success thresholds:
  - regime flip < 3%   AND no clear concentration → conclude "negligible", close Q019
  - regime flip 3-5%   OR mild concentration       → return for PM/Planner review
  - regime flip > 5%   OR strong concentration     → upgrade to Tier 2 (full backtest comparison)
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
import pickle

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from signals.iv_rank import IVSnapshot, IVSignal, _classify_iv_signal
from signals.trend import TrendSnapshot, TrendSignal, _classify_trend_atr, _compute_atr14_close, fetch_spx_history
from signals.vix_regime import (
    VixSnapshot, Regime, Trend,
    _classify_regime, _classify_trend, _is_near_threshold,
    fetch_vix_history, fetch_vix3m_history,
    HIGH_VOL_THRESHOLD, LOW_VOL_THRESHOLD,
)
from strategy.selector import select_strategy, DEFAULT_PARAMS


START = "2007-01-01"


def _strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index
    if hasattr(idx, "tz") and idx.tz is not None:
        idx = idx.tz_localize(None)
    out = df.copy()
    out.index = idx.normalize()
    return out


def load_vix_ohlc() -> pd.DataFrame:
    """Load VIX OHLC max-history with both Open and Close."""
    path = ROOT / "data/market_cache/yahoo__VIX__max__1d.pkl"
    with open(path, "rb") as f:
        d = pickle.load(f)
    df = d if isinstance(d, pd.DataFrame) else pd.DataFrame(d)
    df = _strip_tz(df)
    return df.rename(columns={"Open": "open", "Close": "close",
                              "High": "high", "Low": "low"})


def _build_iv_snapshot(vix_close_hist: pd.Series, current_vix: float, date) -> IVSnapshot:
    """IVSnapshot from historical VIX closes (matches production EOD-based)."""
    hist = vix_close_hist[:date].dropna()
    if len(hist) < 30:
        return IVSnapshot(
            date=date.strftime("%Y-%m-%d"),
            vix=current_vix,
            iv_rank=0.0, iv_percentile=0.0,
            iv_signal=IVSignal.NEUTRAL,
            iv_52w_high=current_vix, iv_52w_low=current_vix,
            ivp63=0.0, ivp252=0.0,
        )
    last_252 = hist.tail(252)
    last_63  = hist.tail(63)
    lo, hi   = float(last_252.min()), float(last_252.max())
    iv_rank  = (current_vix - lo) / (hi - lo) * 100 if hi > lo else 0.0
    iv_pct   = (last_252 < current_vix).sum() / len(last_252) * 100
    ivp63    = (last_63 < current_vix).sum() / len(last_63) * 100 if len(last_63) >= 20 else 0.0
    ivp252   = iv_pct
    sig      = _classify_iv_signal(iv_rank)
    return IVSnapshot(
        date=date.strftime("%Y-%m-%d"),
        vix=current_vix,
        iv_rank=iv_rank, iv_percentile=iv_pct,
        iv_signal=sig,
        iv_52w_high=hi, iv_52w_low=lo,
        ivp63=ivp63, ivp252=ivp252,
    )


def _build_trend_snapshot(spx_hist: pd.Series, date) -> TrendSnapshot:
    """TrendSnapshot from SPX close history (always EOD-based)."""
    window = spx_hist[:date].dropna().tail(200)
    if len(window) < 50:
        cur = float(window.iloc[-1]) if len(window) else 0.0
        return TrendSnapshot(
            date=date.strftime("%Y-%m-%d"),
            spx=cur, ma20=cur, ma50=cur,
            ma_gap_pct=0.0,
            signal=TrendSignal.NEUTRAL,
            above_200=False,
        )
    cur  = float(window.iloc[-1])
    ma20 = float(window.tail(20).mean())
    ma50 = float(window.tail(50).mean())
    ma200 = float(window.tail(200).mean())
    atr_raw = _compute_atr14_close(window)
    atr  = float(atr_raw.iloc[-1]) if hasattr(atr_raw, "iloc") else float(atr_raw)
    gap_atr = (cur - ma50) / atr if atr > 0 else 0.0
    sig = _classify_trend_atr(gap_atr)
    return TrendSnapshot(
        date=date.strftime("%Y-%m-%d"),
        spx=cur, ma20=ma20, ma50=ma50,
        ma_gap_pct=(cur - ma50) / ma50,
        signal=sig,
        above_200=(cur > ma200),
        atr14=atr,
        gap_sigma=gap_atr,
    )


def _build_vix_snapshot(
    vix_close_hist: pd.Series,
    current_vix: float,
    date,
    vix3m_hist: pd.Series | None = None,
) -> VixSnapshot:
    """VixSnapshot with current_vix override (close OR open). Rest EOD-based."""
    hist = vix_close_hist[:date].dropna()
    if len(hist) < 6:
        return None
    vix_5d_avg = float(hist.iloc[-5:].mean())
    vix_5d_ago = float(hist.iloc[-10:-5].mean()) if len(hist) >= 10 else vix_5d_avg
    peak10     = float(hist.iloc[-10:].max())  if len(hist) >= 10 else None
    regime     = _classify_regime(current_vix)
    trend      = _classify_trend(vix_5d_avg, vix_5d_ago)
    warn       = _is_near_threshold(current_vix)
    vix3m      = float(vix3m_hist.loc[date]) if vix3m_hist is not None and date in vix3m_hist.index else None
    backw      = (vix3m is not None) and (current_vix > vix3m)
    return VixSnapshot(
        date=date.strftime("%Y-%m-%d"),
        vix=current_vix, regime=regime, trend=trend,
        vix_5d_avg=vix_5d_avg, vix_5d_ago=vix_5d_ago,
        transition_warning=warn, vix3m=vix3m, backwardation=backw,
        vix_peak_10d=peak10,
    )


def _vix_bucket(v: float) -> str:
    if v < 15:    return "<15"
    if v < 20:    return "15-20"
    if v < 25:    return "20-25"
    if v < 30:    return "25-30"
    if v < 35:    return "30-35"
    return "≥35"


def main():
    print("=" * 90)
    print("Q019 Tier 1 — close vs open-based VIX sensitivity")
    print("=" * 90)

    print("\n  Loading data …", flush=True)
    vix_ohlc = load_vix_ohlc()
    spx_df   = _strip_tz(fetch_spx_history(period="max", interval="1d"))
    v3m_df   = _strip_tz(fetch_vix3m_history(period="max", interval="1d"))

    # Align: use VIX OHLC index, intersect with SPX dates
    df = pd.DataFrame({
        "vix_open":  vix_ohlc["open"],
        "vix_close": vix_ohlc["close"],
        "vix_high":  vix_ohlc["high"],
        "vix_low":   vix_ohlc["low"],
        "spx":       spx_df["close"],
    }).dropna()
    df = df[df.index >= pd.Timestamp(START)]
    print(f"  Series: {len(df)} trading days from {df.index[0].date()} to {df.index[-1].date()}")

    # Open-vs-close diff distribution sanity check
    diff = df["vix_close"] - df["vix_open"]
    diff_pct = diff / df["vix_open"] * 100
    print(f"\n  VIX open-vs-close magnitude:")
    print(f"    abs diff: mean {diff.abs().mean():.2f},  P50 {diff.abs().median():.2f},  "
          f"P90 {diff.abs().quantile(0.9):.2f},  P99 {diff.abs().quantile(0.99):.2f}")
    print(f"    abs %:    mean {diff_pct.abs().mean():.2f}%,  P50 {diff_pct.abs().median():.2f}%,  "
          f"P90 {diff_pct.abs().quantile(0.9):.2f}%,  P99 {diff_pct.abs().quantile(0.99):.2f}%")

    # Daily selector run
    print(f"\n  Running selector for each day with both close and open VIX …", flush=True)
    rows = []
    skipped = 0
    for date, row in df.iterrows():
        vix_close = float(row["vix_close"])
        vix_open  = float(row["vix_open"])

        spx_hist  = df["spx"][:date]
        vix_hist  = df["vix_close"][:date]
        vix3m_hist = v3m_df["vix3m"]

        try:
            vsnap_c = _build_vix_snapshot(vix_hist, vix_close, date, vix3m_hist)
            vsnap_o = _build_vix_snapshot(vix_hist, vix_open,  date, vix3m_hist)
            if vsnap_c is None or vsnap_o is None:
                skipped += 1
                continue
            iv_c    = _build_iv_snapshot(vix_hist, vix_close, date)
            iv_o    = _build_iv_snapshot(vix_hist, vix_open,  date)
            tsnap   = _build_trend_snapshot(df["spx"], date)

            rec_c   = select_strategy(vsnap_c, iv_c, tsnap)
            rec_o   = select_strategy(vsnap_o, iv_o, tsnap)
        except Exception as e:
            skipped += 1
            continue

        rows.append({
            "date":          date,
            "year":          date.year,
            "vix_close":     vix_close,
            "vix_open":      vix_open,
            "vix_diff":      vix_close - vix_open,
            "regime_close":  vsnap_c.regime.value,
            "regime_open":   vsnap_o.regime.value,
            "iv_sig_close":  iv_c.iv_signal.value,
            "iv_sig_open":   iv_o.iv_signal.value,
            "strat_close":   rec_c.strategy.value if hasattr(rec_c.strategy, 'value') else str(rec_c.strategy),
            "strat_open":    rec_o.strategy.value if hasattr(rec_o.strategy, 'value') else str(rec_o.strategy),
            "action_close":  getattr(rec_c, "position_action", None),
            "action_open":   getattr(rec_o, "position_action", None),
        })

    res = pd.DataFrame(rows)
    print(f"  Days computed: {len(res)}  (skipped {skipped})")

    # ── Flip statistics ───────────────────────────────────────────────────────
    n = len(res)
    regime_flip = (res["regime_close"] != res["regime_open"])
    iv_flip     = (res["iv_sig_close"] != res["iv_sig_open"])
    strat_flip  = (res["strat_close"]  != res["strat_open"])
    action_flip = (res["action_close"] != res["action_open"])

    print(f"\n\n" + "=" * 80)
    print("FLIP RATE SUMMARY")
    print("=" * 80)
    print(f"\n  {'Layer':<24}  {'Flip count':>11}  {'Flip rate':>10}")
    print(f"  {'─'*48}")
    print(f"  {'Regime':<24}  {regime_flip.sum():>11}  {regime_flip.mean()*100:>9.2f}%")
    print(f"  {'IV signal':<24}  {iv_flip.sum():>11}  {iv_flip.mean()*100:>9.2f}%")
    print(f"  {'Final strategy':<24}  {strat_flip.sum():>11}  {strat_flip.mean()*100:>9.2f}%")
    print(f"  {'Position action':<24}  {action_flip.sum():>11}  {action_flip.mean()*100:>9.2f}%")

    # ── Concentration analysis ────────────────────────────────────────────────
    print(f"\n\n" + "=" * 80)
    print("CONCENTRATION — VIX bucket")
    print("=" * 80)
    res["vix_bucket"] = res["vix_close"].apply(_vix_bucket)
    bucket_total  = res.groupby("vix_bucket").size()
    bucket_regime = res[regime_flip].groupby("vix_bucket").size()
    bucket_strat  = res[strat_flip].groupby("vix_bucket").size()
    print(f"\n  {'VIX bucket':<10}  {'Total':>7}  {'Regime flip':>12}  {'Regime%':>8}  "
          f"{'Strat flip':>11}  {'Strat%':>7}")
    print(f"  {'─'*70}")
    for bucket in ["<15", "15-20", "20-25", "25-30", "30-35", "≥35"]:
        if bucket not in bucket_total:
            continue
        tot = bucket_total[bucket]
        rf  = bucket_regime.get(bucket, 0)
        sf  = bucket_strat.get(bucket, 0)
        print(f"  {bucket:<10}  {tot:>7}  {rf:>12}  {rf/tot*100:>7.1f}%  "
              f"{sf:>11}  {sf/tot*100:>6.1f}%")

    print(f"\n\n" + "=" * 80)
    print("CONCENTRATION — Year")
    print("=" * 80)
    year_total  = res.groupby("year").size()
    year_regime = res[regime_flip].groupby("year").size()
    year_strat  = res[strat_flip].groupby("year").size()
    print(f"\n  {'Year':<6}  {'Total':>6}  {'Regime%':>8}  {'Strat%':>7}")
    print(f"  {'─'*38}")
    for y in sorted(year_total.index):
        tot = year_total[y]
        rf  = year_regime.get(y, 0)
        sf  = year_strat.get(y, 0)
        print(f"  {y:<6}  {tot:>6}  {rf/tot*100:>7.1f}%  {sf/tot*100:>6.1f}%")

    # ── Direction of regime flip ──────────────────────────────────────────────
    print(f"\n\n" + "=" * 80)
    print("REGIME FLIP DIRECTION")
    print("=" * 80)
    flip_only = res[regime_flip]
    direction = flip_only.apply(lambda r: f"{r['regime_close']} → {r['regime_open']}", axis=1)
    direction_count = direction.value_counts()
    print(f"\n  {'Direction':<35}  {'Count':>6}  {'% of flips':>10}")
    print(f"  {'─'*55}")
    for d, c in direction_count.items():
        print(f"  {d:<35}  {c:>6}  {c/regime_flip.sum()*100:>9.1f}%")

    # ── Strategy flip direction ───────────────────────────────────────────────
    print(f"\n\n" + "=" * 80)
    print("STRATEGY FLIP DIRECTION (top 10)")
    print("=" * 80)
    sflip_only = res[strat_flip]
    sdirection = sflip_only.apply(lambda r: f"{r['strat_close']} → {r['strat_open']}", axis=1)
    s_count = sdirection.value_counts().head(10)
    print(f"\n  {'Direction':<55}  {'Count':>6}  {'% of flips':>10}")
    print(f"  {'─'*78}")
    for d, c in s_count.items():
        print(f"  {d[:53]:<55}  {c:>6}  {c/strat_flip.sum()*100:>9.1f}%")

    # ── Verdict ──────────────────────────────────────────────────────────────
    print(f"\n\n" + "=" * 80)
    print("TIER 1 VERDICT")
    print("=" * 80)
    rfp = regime_flip.mean() * 100
    sfp = strat_flip.mean() * 100
    afp = action_flip.mean() * 100
    print(f"\n  Regime flip rate:    {rfp:.2f}%")
    print(f"  Strategy flip rate:  {sfp:.2f}%")
    print(f"  Action flip rate:    {afp:.2f}%")

    # MC reference (per Q019 sync/open_questions.md): regime 9.71% / trend 31.54% / aftermath 4.63%
    print(f"\n  MC reference (open_questions.md Q019):  regime 9.71%, aftermath 4.63%")
    print()
    if rfp < 3 and sfp < 3:
        verdict = "NEGLIGIBLE — close Q019"
        marker  = "✅"
    elif rfp < 5:
        verdict = "MARGINAL — return to PM/Planner for review"
        marker  = "⚠️"
    else:
        verdict = "MATERIAL — upgrade to Tier 2 (full backtest comparison)"
        marker  = "🔴"
    print(f"  {marker} {verdict}")


if __name__ == "__main__":
    main()
