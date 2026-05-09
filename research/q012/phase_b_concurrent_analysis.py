"""
Q012 Phase B — /ES & SPX Credit Concurrent Entry Frequency Analysis
=====================================================================
Questions answered:
  B1. On what fraction of historical days would both /ES (BULLISH trend)
      and SPX Credit (any signal) want to enter simultaneously?
  B2. On those collision days, what does combined BP consumption look like?
  B3. In which regimes (NORMAL / HIGH_VOL / LOW_VOL) do collisions cluster?
  B4. How often does the combined BP exceed the current 20% NLV cap?

Method:
  - Extract /ES BULLISH trend signal from historical data (same logic as run_phase1)
  - Extract SPX Credit entry days from existing backtest (open days)
  - Combine: collision = /ES BULLISH + SPX Credit position already open
    (the dangerous case is: SPX Credit is open AND /ES wants to enter)
  - Also check: both want to enter on same day (double-open day)
  - For each collision, compute combined BP using Phase A SPAN model

Inputs:
  - signals/trend.py  (trend filter)
  - signals/vix_regime.py  (VIX regime)
  - backtest/engine.py  (SPX Credit entry days from backtest run)
  - Phase A SPAN model
"""

from __future__ import annotations
import sys, pickle
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from signals.trend import fetch_spx_history, _classify_trend_atr, _compute_atr14_close, TREND_THRESHOLD, TrendSignal
from signals.vix_regime import fetch_vix_history

# SPAN model from Phase A (inline to avoid import dependency)
from backtest.pricer import find_strike_for_delta, put_price

# ── Constants ─────────────────────────────────────────────────────────────────
ES_MULTIPLIER   = 50
CALIB_VIX       = 19.0
CALIB_SPAN      = 20_529.0
CALIB_ES        = 5_400.0
SCAN_EXPONENT   = 1.10
NLV             = 500_000.0       # account NLV assumption
BP_CAP_FRAC     = 0.20            # SPEC-061 shared-BP ceiling (20% NLV)
BP_CAP_DOLLARS  = NLV * BP_CAP_FRAC

WARMUP_DAYS     = 64
START_DATE      = "2007-01-01"    # consistent with 19y backtest window


# ── Trend filter helpers ───────────────────────────────────────────────────────

def _trend_signal(window: pd.Series, spx_today: float) -> TrendSignal:
    if len(window) < 50:
        return TrendSignal.NEUTRAL
    ma50 = float(window.iloc[-50:].mean())
    atr_raw = _compute_atr14_close(window)
    try:
        atr = float(atr_raw.iloc[-1]) if hasattr(atr_raw, "iloc") else float(atr_raw)
    except Exception:
        return TrendSignal.NEUTRAL
    if atr == 0.0:
        return TrendSignal.NEUTRAL
    gap = (spx_today - ma50) / atr
    return _classify_trend_atr(gap)


# ── SPAN estimate (simplified Phase A inline) ─────────────────────────────────

def _base_scan_pct() -> float:
    """Re-calibrate BASE_SCAN_PCT inline."""
    sigma0 = CALIB_VIX / 100.0
    k0     = find_strike_for_delta(CALIB_ES, 45, sigma0, 0.20, is_call=False)
    p0     = put_price(CALIB_ES, k0, 45, sigma0)
    target = CALIB_SPAN / ES_MULTIPLIER
    lo, hi = 0.01, 0.30
    for _ in range(60):
        mid     = (lo + hi) / 2.0
        sigma_u = sigma0 * 1.50
        es_dn   = CALIB_ES * (1.0 - mid)
        pdn     = put_price(es_dn, k0, 45, sigma_u)
        val     = max(pdn - p0, 0.0) + p0
        if val < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0

_BASE_SCAN = _base_scan_pct()

def es_span_estimate(es_price: float, vix: float) -> float:
    """Approximate SPAN for /ES 20-delta 45-DTE short put."""
    scan_pct = _BASE_SCAN * (vix / CALIB_VIX) ** SCAN_EXPONENT
    return scan_pct * es_price * ES_MULTIPLIER


# ── SPX Credit position extractor ─────────────────────────────────────────────

def extract_spx_credit_open_days(start: str = START_DATE) -> pd.DataFrame:
    """
    Extract days when SPX Credit had an open position using the production
    backtest engine. Returns DataFrame with date + regime + estimated BP used.
    We run the backtest and record open-position days.
    """
    print("  Running SPX Credit backtest to extract open-position days …", flush=True)
    try:
        from backtest.engine import run_backtest
        from strategy.selector import StrategyParams
        params = StrategyParams()
        result = run_backtest(params, start_date=start, verbose=False)

        # daily_rows has equity + is_in_position equivalent via trade overlap
        trades = result.get("trades", [])
        open_days: set[str] = set()
        spx_bp_by_date: dict[str, float] = {}

        for t in trades:
            if not (t.get("entry_date") and t.get("exit_date")):
                continue
            entry = pd.Timestamp(t["entry_date"])
            exit_ = pd.Timestamp(t["exit_date"])
            bp_used = float(t.get("bp_used", 0) or 0)
            d = entry
            while d <= exit_:
                ds = d.strftime("%Y-%m-%d")
                open_days.add(ds)
                spx_bp_by_date[ds] = spx_bp_by_date.get(ds, 0) + bp_used
                d += pd.Timedelta(days=1)

        rows = [{"date": d, "spx_bp": spx_bp_by_date.get(d, 0)} for d in sorted(open_days)]
        df   = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df

    except Exception as e:
        print(f"  [WARN] Full backtest failed ({e}), using lightweight signal proxy")
        return _extract_spx_signal_proxy(start)


def _extract_spx_signal_proxy(start: str) -> pd.DataFrame:
    """
    Lightweight proxy: SPX Credit 'open' = any day trend + VIX regime allows
    entry (NORMAL/HIGH_VOL). Conservative under-estimate of collision days.
    """
    vix_df = _strip_tz(fetch_vix_history(period="max", interval="1d"))
    spx_df = _strip_tz(fetch_spx_history(period="max", interval="1d"))

    merged = pd.DataFrame({"spx": spx_df["close"], "vix": vix_df["vix"]}).dropna()
    merged = merged[merged.index >= pd.Timestamp(start)]

    open_days = []
    # approximation: SPX Credit is "open" ~60% of the time (historical avg)
    # use regime as a proxy: NORMAL/HIGH_VOL days = potential SPX entry
    for date, row in merged.iterrows():
        vix = float(row["vix"])
        # rough: NORMAL = 15≤VIX<25, HIGH_VOL = 25≤VIX<35
        if 14 <= vix <= 40:
            open_days.append({
                "date": date,
                "spx_bp": NLV * 0.15 * min(vix / 20.0, 1.5),  # BP proxy
            })
    df = pd.DataFrame(open_days)
    df["date"] = pd.to_datetime(df["date"])
    return df


# ── /ES BULLISH trend signal extractor ────────────────────────────────────────

def _strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index
    if hasattr(idx, "tz") and idx.tz is not None:
        idx = idx.tz_localize(None)
    df = df.copy()
    df.index = idx.normalize()
    return df


def extract_es_bullish_days(start: str = START_DATE) -> pd.DataFrame:
    """Extract days when /ES trend filter = BULLISH."""
    print("  Computing /ES BULLISH trend signal …", flush=True)
    vix_df = _strip_tz(fetch_vix_history(period="max", interval="1d"))
    spx_df = _strip_tz(fetch_spx_history(period="max", interval="1d"))

    merged = pd.DataFrame({"spx": spx_df["close"], "vix": vix_df["vix"]}).dropna()
    full   = merged.copy()
    merged = merged[merged.index >= pd.Timestamp(start)]

    rows = []
    for date, row in merged.iterrows():
        spx = float(row["spx"])
        vix = float(row["vix"])
        window = full[full.index <= date]["spx"].iloc[-200:]
        sig    = _trend_signal(window, spx)
        if sig == TrendSignal.BULLISH and len(window) >= WARMUP_DAYS:
            rows.append({
                "date": date,
                "spx": spx,
                "vix": vix,
                "es_span": es_span_estimate(spx, vix),
            })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


# ── VIX regime classifier ─────────────────────────────────────────────────────

def vix_regime_label(vix: float) -> str:
    if vix < 15:   return "LOW_VOL"
    if vix < 25:   return "NORMAL"
    if vix < 35:   return "HIGH_VOL"
    return "EXTREME_VOL"


# ── Collision analysis ────────────────────────────────────────────────────────

def analyse_collisions(
    es_bullish: pd.DataFrame,
    spx_open:   pd.DataFrame,
) -> dict:
    """
    Collision = day where /ES wants to enter (BULLISH) AND
    SPX Credit already has an open position.
    """
    es_dates  = set(es_bullish["date"].dt.normalize())
    spx_dates = set(spx_open["date"].dt.normalize())

    collision_dates = es_dates & spx_dates

    # Build lookup maps
    es_lkp  = es_bullish.set_index(es_bullish["date"].dt.normalize())
    spx_lkp = spx_open.set_index(spx_open["date"].dt.normalize())

    rows = []
    for d in sorted(collision_dates):
        er  = es_lkp.loc[d]
        sr  = spx_lkp.loc[d]
        vix = float(er["vix"])
        spx = float(er["spx"])
        es_span   = float(er["es_span"])
        spx_bp    = float(sr["spx_bp"].iloc[0] if hasattr(sr["spx_bp"], "iloc") else sr["spx_bp"])
        combined  = es_span + spx_bp
        cap_breach = combined > BP_CAP_DOLLARS
        rows.append({
            "date": d,
            "vix": round(vix, 1),
            "regime": vix_regime_label(vix),
            "es_span": round(es_span, 0),
            "spx_bp": round(spx_bp, 0),
            "combined_bp": round(combined, 0),
            "combined_pct_nlv": round(combined / NLV * 100, 1),
            "cap_breach": cap_breach,
        })

    df_coll = pd.DataFrame(rows) if rows else pd.DataFrame()
    total_es_days   = len(es_dates)
    total_spx_days  = len(spx_dates)
    total_both_days = len(collision_dates)

    # all days denominator
    vix_df  = _strip_tz(fetch_vix_history(period="max", interval="1d"))
    spx_df2 = _strip_tz(fetch_spx_history(period="max", interval="1d"))
    all_days = len(pd.DataFrame({"v": vix_df["vix"], "s": spx_df2["close"]}).dropna()
                   .pipe(lambda x: x[x.index >= pd.Timestamp(START_DATE)]))

    return {
        "all_days":         all_days,
        "es_bullish_days":  total_es_days,
        "spx_open_days":    total_spx_days,
        "collision_days":   total_both_days,
        "collision_df":     df_coll,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    print("=" * 68)
    print("Q012 PHASE B — /ES & SPX Credit Concurrent Entry Analysis")
    print(f"  Window: {START_DATE} → today   NLV assumption: ${NLV:,.0f}")
    print("=" * 68)

    # Load signals
    es_bullish = extract_es_bullish_days()
    spx_open   = extract_spx_credit_open_days()

    print(f"\n  /ES BULLISH trend days:        {len(es_bullish):,}")
    print(f"  SPX Credit open-position days: {len(spx_open):,}")

    # Collision analysis
    result = analyse_collisions(es_bullish, spx_open)
    all_d   = result["all_days"]
    n_coll  = result["collision_days"]
    df_coll = result["collision_df"]

    print(f"\n  Total trading days (since {START_DATE}): {all_d:,}")
    print(f"  /ES BULLISH days: {result['es_bullish_days']:,}  ({result['es_bullish_days']/all_d*100:.1f}%)")
    print(f"  SPX Credit open:  {result['spx_open_days']:,}  ({result['spx_open_days']/all_d*100:.1f}%)")
    print(f"  Collision days:   {n_coll:,}  ({n_coll/all_d*100:.1f}% of all days)")
    print(f"  Collision / /ES BULLISH days: {n_coll/result['es_bullish_days']*100:.1f}%")

    if df_coll.empty:
        print("\n  [No collision data — check SPX backtest extraction]")
        return

    # ── B2: BP consumption on collision days ──────────────────────────────────
    print("\n" + "─" * 68)
    print("B2 — Combined BP on collision days")
    print("─" * 68)
    pcts = [10, 25, 50, 75, 90, 95, 99]
    for p in pcts:
        v = np.percentile(df_coll["combined_bp"], p)
        print(f"  P{p:3d}: ${v:,.0f}  ({v/NLV*100:.1f}% NLV)")
    n_breach = df_coll["cap_breach"].sum()
    print(f"\n  Days where combined BP > {BP_CAP_DOLLARS/1000:.0f}k cap: "
          f"{n_breach:,} / {n_coll:,}  ({n_breach/n_coll*100:.1f}%)")

    # ── B3: Regime distribution of collisions ─────────────────────────────────
    print("\n" + "─" * 68)
    print("B3 — Collision regime distribution")
    print("─" * 68)
    regime_stats = df_coll.groupby("regime").agg(
        days=("date", "count"),
        cap_breaches=("cap_breach", "sum"),
        median_combined=("combined_bp", "median"),
        p90_combined=("combined_bp", lambda x: np.percentile(x, 90)),
    ).reset_index()
    regime_stats["pct_total"] = (regime_stats["days"] / n_coll * 100).round(1)
    regime_stats["breach_rate"] = (regime_stats["cap_breaches"] / regime_stats["days"] * 100).round(1)
    print(regime_stats.to_string(index=False))

    # ── B4: Annualised collision rate ─────────────────────────────────────────
    print("\n" + "─" * 68)
    print("B4 — Annualised collision frequency")
    print("─" * 68)
    years = all_d / 252.0
    print(f"  Collision days / year: {n_coll / years:.1f}")
    print(f"  Breach days / year:    {n_breach / years:.1f}")

    # ── B5: Worst 10 collision events ─────────────────────────────────────────
    print("\n" + "─" * 68)
    print("B5 — Top 10 highest combined-BP collision days")
    print("─" * 68)
    top10 = df_coll.nlargest(10, "combined_bp")[
        ["date","vix","regime","es_span","spx_bp","combined_bp","combined_pct_nlv","cap_breach"]
    ]
    print(top10.to_string(index=False))

    # ── Governance conclusion ─────────────────────────────────────────────────
    print("\n" + "─" * 68)
    print("B6 — Governance implications")
    print("─" * 68)
    coll_pct = n_coll / all_d * 100
    breach_pct = n_breach / n_coll * 100 if n_coll else 0
    yearly = n_coll / years

    if coll_pct < 5:
        freq_label = "LOW — Rule A (simple shared cap) is sufficient"
    elif coll_pct < 15:
        freq_label = "MODERATE — Rule A+ with stress buffer is recommended"
    else:
        freq_label = "HIGH — consider Rule B (reserved sub-budget)"

    print(f"  Collision frequency {coll_pct:.1f}% → {freq_label}")
    print(f"  Cap-breach rate on collision days: {breach_pct:.1f}%")
    print(f"  Typical collision volume: {yearly:.0f} days/year")
    print()
    if breach_pct < 10:
        print("  → SPAN stress correction post-entry is the primary gap.")
        print("    Pre-entry rule needs only a stress-buffer multiplier for HIGH_VOL.")
        print("    Reserved sub-budget (Rule B) is NOT justified at current scale.")
    elif breach_pct < 30:
        print("  → Consider a stress-adjusted pre-entry cap (Rule A+).")
        print("    Post-entry SPAN correction is mandatory.")
    else:
        print("  → High breach rate warrants reserved sub-budget (Rule B) discussion.")

    return result


if __name__ == "__main__":
    run()
