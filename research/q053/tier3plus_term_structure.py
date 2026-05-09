"""
Q053 Tier-3+ — VIX Term Structure Signal Test (narrow scope, half-day)
=======================================================================
Source: PM authorised this last-mile signal test before C3 decision.

Hypothesis: VIX term structure (VIX − VIX3M spread) better separates
grinding-decline regimes than VIX level / SPX drawdown signals already
exhausted in Tier 3.

Rationale:
  - VIX3M shows backwardation when SHORT-end fear exceeds 3-month-end fear
  - Acute spikes (2011, 2018-Q1, 2008, 2020) → sharp brief backwardation
  - Persistent grinding → persistent flat-to-mild backwardation
  - This is a STRUCTURAL feature different from VIX level alone

Test grid (7 candidates):
  TS1: spread ≤ 0           (in backwardation)
  TS2: spread ≤ +2          (flat or backwardation)
  TS3: VIX ≥ 20 AND spread ≤ 0
  TS4: VIX ≥ 20 AND spread ≤ +2
  R1:  VIX 30d MA ≥ 22 AND VIX 60d max < 35  (Tier 3 best baseline)
  TS6: R1 AND spread ≤ 0    (R1 + no-spike confirm)
  TS7: R1 AND spread ≤ +2

Scoring vs R1 (4 criteria; need ≥ 3 to declare TS better):
  FP rate          target ≤ 5%        R1 baseline 9.0%
  2022 capture     target ≥ 50% of 18 trades   R1 baseline ~5%
  Spike-recover flag rate    minimise
  Avg PnL flagged  target more negative than -$4k/trade
"""
from __future__ import annotations

import sys
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backtest.engine import run_backtest
from signals.trend import fetch_spx_history
from signals.vix_regime import fetch_vix_history, fetch_vix3m_history


FULL_START = "2007-01-01"
ACCOUNT    = 500_000.0

TRUE_GRINDING = {
    "2015-2016 China/oil":  ("2015-08-01", "2016-02-29"),
    "2018-Q4 selloff":      ("2018-10-01", "2018-12-31"),
    "2022 grinding bear":   ("2022-01-01", "2022-12-31"),
}
SPIKE_RECOVER = {
    "2011-Q3 Eurozone":     ("2011-08-01", "2011-12-31"),
    "2018-Q1 Volmageddon":  ("2018-01-01", "2018-04-30"),
}


def _strip_tz(df):
    idx = df.index
    if hasattr(idx, "tz") and idx.tz is not None:
        idx = idx.tz_localize(None)
    out = df.copy()
    out.index = idx.normalize()
    return out


def build_features() -> pd.DataFrame:
    vdf  = _strip_tz(fetch_vix_history(period="max", interval="1d"))
    v3m  = _strip_tz(fetch_vix3m_history(period="max", interval="1d"))
    sdf  = _strip_tz(fetch_spx_history(period="max", interval="1d"))
    df = pd.DataFrame({"vix": vdf["vix"], "vix3m": v3m["vix3m"],
                        "spx": sdf["close"]}).dropna()
    df = df[df.index >= pd.Timestamp(FULL_START)].copy()
    df["spread"]      = df["vix"] - df["vix3m"]
    df["vix_ma_30"]   = df["vix"].rolling(30, min_periods=15).mean()
    df["vix_max_60"]  = df["vix"].rolling(60, min_periods=30).max()
    df["spread_ma5"]  = df["spread"].rolling(5, min_periods=3).mean()
    return df


def define_signals(df):
    return {
        "TS1: spread ≤ 0":                       df["spread"] <= 0,
        "TS2: spread ≤ +2":                      df["spread"] <= 2,
        "TS3: VIX ≥ 20 AND spread ≤ 0":          (df["vix"] >= 20) & (df["spread"] <= 0),
        "TS4: VIX ≥ 20 AND spread ≤ +2":         (df["vix"] >= 20) & (df["spread"] <= 2),
        "R1: VIX30dMA≥22 AND VIX60dmax<35":      (df["vix_ma_30"] >= 22) & (df["vix_max_60"] < 35),
        "TS6: R1 AND spread ≤ 0":                ((df["vix_ma_30"] >= 22) & (df["vix_max_60"] < 35)
                                                  & (df["spread"] <= 0)),
        "TS7: R1 AND spread ≤ +2":               ((df["vix_ma_30"] >= 22) & (df["vix_max_60"] < 35)
                                                  & (df["spread"] <= 2)),
        # Bonus: 5-day smoothed spread to filter daily noise
        "TS8: VIX≥20 AND spread_ma5 ≤ 0":        (df["vix"] >= 20) & (df["spread_ma5"] <= 0),
    }


def evaluate(signal: pd.Series, df: pd.DataFrame, trades) -> dict:
    g_dates = set()
    for s, e in TRUE_GRINDING.values():
        ts, te = pd.Timestamp(s), pd.Timestamp(e)
        g_dates.update(d for d in df.index if ts <= d <= te)
    sp_dates = set()
    for s, e in SPIKE_RECOVER.values():
        ts, te = pd.Timestamp(s), pd.Timestamp(e)
        sp_dates.update(d for d in df.index if ts <= d <= te)
    other_dates = set(df.index) - g_dates - sp_dates

    in_g  = df.index.isin(pd.Index(sorted(g_dates)))
    in_sp = df.index.isin(pd.Index(sorted(sp_dates)))
    in_o  = df.index.isin(pd.Index(sorted(other_dates)))

    fp_rate    = signal[in_o].sum()  / max(in_o.sum(), 1)  * 100
    g_cov      = signal[in_g].sum()  / max(in_g.sum(), 1)  * 100
    sp_cov     = signal[in_sp].sum() / max(in_sp.sum(), 1) * 100

    flagged, unflagged = [], []
    flagged_2022, unflagged_2022 = [], []
    flagged_2022_loser, unflagged_2022_loser = [], []
    for t in trades:
        if not t.entry_date:
            continue
        try:
            ed = pd.Timestamp(t.entry_date)
        except Exception:
            continue
        if ed not in df.index:
            continue
        is_flag = bool(signal.loc[ed])
        is_2022 = ed.year == 2022
        is_loser = t.exit_pnl < 0
        if is_flag:
            flagged.append(t)
            if is_2022:
                flagged_2022.append(t)
                if is_loser:
                    flagged_2022_loser.append(t)
        else:
            unflagged.append(t)
            if is_2022:
                unflagged_2022.append(t)
                if is_loser:
                    unflagged_2022_loser.append(t)

    avgF = np.mean([t.exit_pnl for t in flagged]) if flagged else 0
    avgU = np.mean([t.exit_pnl for t in unflagged]) if unflagged else 0
    n2022_total  = len(flagged_2022) + len(unflagged_2022)
    n2022_loser_total = len(flagged_2022_loser) + len(unflagged_2022_loser)

    return {
        "fp_rate":           fp_rate,
        "g_cov":             g_cov,
        "sp_cov":            sp_cov,
        "n_flagged":         len(flagged),
        "avg_pnl_flagged":   avgF,
        "avg_pnl_unflagged": avgU,
        "selectivity":       avgF - avgU,
        "n_2022_flagged":    len(flagged_2022),
        "n_2022_unflagged":  len(unflagged_2022),
        "pnl_2022_flagged":  sum(t.exit_pnl for t in flagged_2022),
        "pnl_2022_unflagged": sum(t.exit_pnl for t in unflagged_2022),
        "cov_2022_total":    len(flagged_2022) / max(n2022_total, 1) * 100,
        "cov_2022_losers":   len(flagged_2022_loser) / max(n2022_loser_total, 1) * 100,
        "n_2022_losers":     n2022_loser_total,
    }


def main():
    print("=" * 90)
    print("Q053 Tier-3+ — VIX Term Structure Signal Test (narrow scope)")
    print("=" * 90)

    print("\n  Loading data + running backtest …", flush=True)
    df = build_features()
    r = run_backtest(start_date=FULL_START, account_size=ACCOUNT, verbose=False)
    trades = r.trades
    print(f"  Series: {len(df)} days  Trades: {len(trades)}")
    print(f"  Spread distribution: min {df['spread'].min():.1f}, "
          f"P25 {df['spread'].quantile(0.25):.1f}, "
          f"P50 {df['spread'].median():.1f}, "
          f"P75 {df['spread'].quantile(0.75):.1f}, "
          f"max {df['spread'].max():.1f}")
    pct_backw = (df['spread'] <= 0).mean() * 100
    print(f"  Days in backwardation (spread ≤ 0): {pct_backw:.1f}%")

    print("\n\n  Evaluating signals …", flush=True)
    sigs = define_signals(df)
    results = {name: evaluate(sig, df, trades) for name, sig in sigs.items()}

    # ── Master table ─────────────────────────────────────────────────────────
    print("\n\n" + "=" * 110)
    print("RESULTS TABLE")
    print("=" * 110)
    print(f"  {'Signal':<42}  {'FP%':>5}  {'gCov%':>6}  {'spCov%':>7}  "
          f"{'2022(f/u)':>10}  {'2022losers':>11}  {'avgF':>9}  {'Δ':>9}")
    print(f"  {'─'*108}")
    for name, ev in results.items():
        loser_cov = f"{int(ev['cov_2022_losers'])}% ({ev['n_2022_losers']})"
        print(f"  {name:<42}  {ev['fp_rate']:>5.1f}  {ev['g_cov']:>6.1f}  "
              f"{ev['sp_cov']:>7.1f}  {ev['n_2022_flagged']:>3}/{ev['n_2022_unflagged']:<3}    "
              f"{loser_cov:>11}  ${ev['avg_pnl_flagged']:>+7,.0f}  ${ev['selectivity']:>+7,.0f}")
    print()
    print("  Legend: FP% = false-positive on Other days")
    print("          gCov% = % of grinding-window days flagged")
    print("          spCov% = % of spike-recover days flagged (lower better)")
    print("          2022(f/u) = trades flagged/unflagged in 2022 (out of 18 total)")
    print("          2022losers = % of 2022 losing trades flagged (target ≥ 50%)")
    print("          Δ = selectivity (more negative = better detector)")

    # ── Score vs R1 ──────────────────────────────────────────────────────────
    print("\n\n" + "=" * 90)
    print("SCORING vs R1 BASELINE (4 criteria, need ≥ 3 to declare TS better)")
    print("=" * 90)
    r1 = results["R1: VIX30dMA≥22 AND VIX60dmax<35"]
    print(f"\n  R1 baseline: FP {r1['fp_rate']:.1f}%, "
          f"2022 loser cov {r1['cov_2022_losers']:.0f}%, "
          f"sp flag {r1['sp_cov']:.1f}%, avg flagged ${r1['avg_pnl_flagged']:+,.0f}")
    print()

    print(f"  {'Signal':<42}  {'FP':>4}  {'2022Lo':>6}  {'spCov':>6}  {'avgF':>4}  {'Score':>5}  Verdict")
    print(f"  {'─'*98}")
    for name, ev in results.items():
        if name.startswith("R1"):
            continue
        # 4 criteria, each a binary improvement vs R1:
        c_fp       = ev['fp_rate']         < r1['fp_rate']
        c_2022     = ev['cov_2022_losers'] > r1['cov_2022_losers']
        c_sp       = ev['sp_cov']          < r1['sp_cov']
        c_avgF     = ev['avg_pnl_flagged'] < r1['avg_pnl_flagged']
        score = sum([c_fp, c_2022, c_sp, c_avgF])
        verdict = "✅ BETTER" if score >= 3 else "❌ NOT BETTER"
        print(f"  {name:<42}  {('✓' if c_fp else '·'):>4}  {('✓' if c_2022 else '·'):>6}  "
              f"{('✓' if c_sp else '·'):>6}  {('✓' if c_avgF else '·'):>4}  "
              f"{score}/4  {verdict}")

    # ── Final verdict ────────────────────────────────────────────────────────
    print("\n\n" + "=" * 90)
    print("FINAL VERDICT")
    print("=" * 90)

    winners = [name for name, ev in results.items()
                if not name.startswith("R1") and
                sum([
                    ev['fp_rate']         < r1['fp_rate'],
                    ev['cov_2022_losers'] > r1['cov_2022_losers'],
                    ev['sp_cov']          < r1['sp_cov'],
                    ev['avg_pnl_flagged'] < r1['avg_pnl_flagged'],
                ]) >= 3]

    if winners:
        print(f"\n  ✅ {len(winners)} term-structure signal(s) beat R1 on ≥ 3/4 criteria:")
        for w in winners:
            ev = results[w]
            print(f"\n     {w}")
            print(f"       FP {ev['fp_rate']:.1f}%  |  "
                  f"2022 loser cov {ev['cov_2022_losers']:.0f}% ({ev['n_2022_losers']} losers)  |  "
                  f"sp flag {ev['sp_cov']:.1f}%  |  avg flagged ${ev['avg_pnl_flagged']:+,.0f}")
            print(f"       Δ vs R1: FP {ev['fp_rate']-r1['fp_rate']:+.1f}pp  "
                  f"loser cov {ev['cov_2022_losers']-r1['cov_2022_losers']:+.0f}pp  "
                  f"avg flagged Δ ${ev['avg_pnl_flagged']-r1['avg_pnl_flagged']:+,.0f}")

        best = min(winners, key=lambda n: results[n]['avg_pnl_flagged'])
        print(f"\n  → RECOMMENDED for C3 DRAFT Spec: {best}")
        print(f"  → Term structure adds genuine separation power vs R1.")
    else:
        print(f"\n  ❌ No term-structure signal beats R1 on ≥ 3/4 criteria.")
        print(f"  Best contender details:")
        # Show TS6 (R1 + backwardation) since it's the most likely combo
        for n in ["TS6: R1 AND spread ≤ 0", "TS3: VIX ≥ 20 AND spread ≤ 0",
                   "TS4: VIX ≥ 20 AND spread ≤ +2"]:
            if n in results:
                ev = results[n]
                score = sum([
                    ev['fp_rate']         < r1['fp_rate'],
                    ev['cov_2022_losers'] > r1['cov_2022_losers'],
                    ev['sp_cov']          < r1['sp_cov'],
                    ev['avg_pnl_flagged'] < r1['avg_pnl_flagged'],
                ])
                print(f"    {n}: scored {score}/4 vs R1")
        print(f"\n  → Term structure does NOT cleanly improve on R1.")
        print(f"  → PM should choose between path C (accept) or path 1 (accept R1 with current FP).")


if __name__ == "__main__":
    main()
