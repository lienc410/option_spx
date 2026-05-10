"""
Q053 Tier 3 — Signal Refinement (after Tier 2 simple signals failed on 2022)
=============================================================================
Source: R-20260509-03 (Tier 2 confirmed pattern but simple VIX-MA signals
        couldn't separate cleanly; R4 missed 17/18 of 2022's losing trades).

Tier 3 hypothesis: a better detector should combine multiple structural
features of "grinding-decline regime":
    - VIX persistently elevated WITHOUT recovery to normal
    - SPX in medium-term decline (drawdown context)
    - Term structure stress (backwardation persistence)
    - But NO recent giant spike (excludes 2011, 2018-Q1, 2008, 2020)

Test 6 candidate signals against:
    - TRUE grinding windows (2015-2016, 2018-Q4, 2022) — should flag
    - Spike-recover windows (2011-Q3, 2018-Q1) — should NOT flag
    - Other (baseline) — should mostly NOT flag

Key new measures over Tier 2:
    1. SPX drawdown context (200d return, 100d return)
    2. VIX no-recovery (rolling min)
    3. Persistent backwardation (VIX > VIX3M for X of last 60 days)
    4. Specifically: 2022-coverage as required deliverable

Boundary:
    - Still no implementation; only signal selection
    - Output candidate ready for follow-up SPEC if signal passes bar
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backtest.engine import run_backtest
from signals.trend import fetch_spx_history
from signals.vix_regime import fetch_vix_history, fetch_vix3m_history


FULL_START = "2007-01-01"
ACCOUNT    = 500_000.0


# ── Window definitions ────────────────────────────────────────────────────────

TRUE_GRINDING = {
    "2015-2016 China/oil":  ("2015-08-01", "2016-02-29"),
    "2018-Q4 selloff":      ("2018-10-01", "2018-12-31"),
    "2022 grinding bear":   ("2022-01-01", "2022-12-31"),
}

SPIKE_RECOVER = {
    "2011-Q3 Eurozone":     ("2011-08-01", "2011-12-31"),
    "2018-Q1 Volmageddon":  ("2018-01-01", "2018-04-30"),
}


# ── Data preparation ──────────────────────────────────────────────────────────

def _strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index
    if hasattr(idx, "tz") and idx.tz is not None:
        idx = idx.tz_localize(None)
    out = df.copy()
    out.index = idx.normalize()
    return out


def build_market_features() -> pd.DataFrame:
    """Build daily market features for signal computation."""
    print("  Loading VIX / VIX3M / SPX …", flush=True)
    vdf  = _strip_tz(fetch_vix_history(period="max", interval="1d"))
    v3m  = _strip_tz(fetch_vix3m_history(period="max", interval="1d"))
    sdf  = _strip_tz(fetch_spx_history(period="max", interval="1d"))

    df = pd.DataFrame({
        "vix":   vdf["vix"],
        "vix3m": v3m["vix3m"],
        "spx":   sdf["close"],
    }).dropna()
    df = df[df.index >= pd.Timestamp(FULL_START)].copy()

    # VIX features
    df["vix_ma_30"]   = df["vix"].rolling(30, min_periods=15).mean()
    df["vix_ma_60"]   = df["vix"].rolling(60, min_periods=30).mean()
    df["vix_ma_90"]   = df["vix"].rolling(90, min_periods=45).mean()
    df["vix_min_30"]  = df["vix"].rolling(30, min_periods=15).min()
    df["vix_min_60"]  = df["vix"].rolling(60, min_periods=30).min()
    df["vix_max_60"]  = df["vix"].rolling(60, min_periods=30).max()
    df["vix_max_90"]  = df["vix"].rolling(90, min_periods=45).max()

    # SPX drawdown features
    df["spx_max_200"] = df["spx"].rolling(200, min_periods=100).max()
    df["spx_dd_pct"]  = (df["spx"] / df["spx_max_200"] - 1) * 100  # drawdown from 200d high
    df["spx_ret_50"]  = df["spx"].pct_change(50) * 100
    df["spx_ret_100"] = df["spx"].pct_change(100) * 100
    df["spx_ret_200"] = df["spx"].pct_change(200) * 100

    # Term structure backwardation
    df["backwardation"]   = df["vix"] > df["vix3m"]
    # % of last 60 days in backwardation
    df["backwardation_60d_pct"] = (df["backwardation"]
                                   .rolling(60, min_periods=30)
                                   .mean() * 100)

    return df


# ── Signal definitions ────────────────────────────────────────────────────────

def define_signals(df: pd.DataFrame) -> dict:
    """Six candidate signals targeting grinding-decline detection."""
    return {
        # T1: VIX persistent + SPX in drawdown (broad, simple)
        "T1: VIX 30d MA ≥ 20 AND SPX dd ≤ -5%":
            (df["vix_ma_30"] >= 20) & (df["spx_dd_pct"] <= -5),

        # T2: VIX no recovery (vix min stayed elevated)
        "T2: VIX 30d MA ≥ 22 AND VIX 30d min ≥ 17":
            (df["vix_ma_30"] >= 22) & (df["vix_min_30"] >= 17),

        # T3: Combined no-recovery + drawdown
        "T3: VIX 60d MA ≥ 20 AND VIX 60d min ≥ 16 AND SPX dd ≤ -5%":
            (df["vix_ma_60"] >= 20)
            & (df["vix_min_60"] >= 16)
            & (df["spx_dd_pct"] <= -5),

        # T4: Backwardation persistence
        "T4: backwardation in ≥ 30% of last 60 days":
            df["backwardation_60d_pct"] >= 30,

        # T5: SPX medium-term decline + VIX elevated (no spike requirement)
        "T5: SPX 100d ret ≤ -5% AND VIX 30d MA ≥ 18":
            (df["spx_ret_100"] <= -5) & (df["vix_ma_30"] >= 18),

        # T6: Combined "grinding" composite — needs persistence on multiple axes
        "T6: VIX 60d MA ≥ 20 AND backwardation 30d ≥ 20% AND SPX dd ≤ -5%":
            (df["vix_ma_60"] >= 20)
            & (df["backwardation"].rolling(30, min_periods=15).mean() >= 0.20)
            & (df["spx_dd_pct"] <= -5),
    }


# ── Evaluation ────────────────────────────────────────────────────────────────

@dataclass
class SignalEval:
    name:                  str
    coverage_grinding_pct: float    # % of TRUE grinding days flagged
    coverage_spike_pct:    float    # % of spike-recover days flagged (LOWER better)
    fp_rate_pct:           float    # % of OTHER (non-stress) days flagged
    n_flagged:             int      # trades flagged
    n_unflagged:           int
    avg_pnl_flagged:       float
    avg_pnl_unflagged:     float
    selectivity:           float    # avg_pnl_flagged - avg_pnl_unflagged
    # 2022-specific:
    n_2022_flagged:        int
    n_2022_unflagged:      int
    pnl_2022_flagged:      float
    pnl_2022_unflagged:    float


def evaluate_signal(name: str, signal: pd.Series, df: pd.DataFrame, trades) -> SignalEval:
    # Day-level dates
    grinding_dates = set()
    for s, e in TRUE_GRINDING.values():
        ts, te = pd.Timestamp(s), pd.Timestamp(e)
        grinding_dates.update(d for d in df.index if ts <= d <= te)
    spike_dates = set()
    for s, e in SPIKE_RECOVER.values():
        ts, te = pd.Timestamp(s), pd.Timestamp(e)
        spike_dates.update(d for d in df.index if ts <= d <= te)
    other_dates = set(df.index) - grinding_dates - spike_dates

    in_grinding = df.index.isin(pd.Index(sorted(grinding_dates)))
    in_spike    = df.index.isin(pd.Index(sorted(spike_dates)))
    in_other    = df.index.isin(pd.Index(sorted(other_dates)))

    cov_grinding = signal[in_grinding].sum() / max(in_grinding.sum(), 1) * 100
    cov_spike    = signal[in_spike].sum() / max(in_spike.sum(), 1) * 100
    fp_rate      = signal[in_other].sum() / max(in_other.sum(), 1) * 100

    # Trade-level evaluation
    flagged, unflagged = [], []
    flagged_2022, unflagged_2022 = [], []
    for t in trades:
        if not t.entry_date:
            continue
        try:
            ed = pd.Timestamp(t.entry_date)
        except Exception:
            continue
        if ed not in df.index:
            continue
        is_flagged = bool(signal.loc[ed])
        is_2022    = ed.year == 2022
        if is_flagged:
            flagged.append(t)
            if is_2022:
                flagged_2022.append(t)
        else:
            unflagged.append(t)
            if is_2022:
                unflagged_2022.append(t)

    avgF = np.mean([t.exit_pnl for t in flagged]) if flagged else 0.0
    avgU = np.mean([t.exit_pnl for t in unflagged]) if unflagged else 0.0

    return SignalEval(
        name=name,
        coverage_grinding_pct=cov_grinding,
        coverage_spike_pct=cov_spike,
        fp_rate_pct=fp_rate,
        n_flagged=len(flagged), n_unflagged=len(unflagged),
        avg_pnl_flagged=avgF, avg_pnl_unflagged=avgU,
        selectivity=avgF - avgU,
        n_2022_flagged=len(flagged_2022),
        n_2022_unflagged=len(unflagged_2022),
        pnl_2022_flagged=sum(t.exit_pnl for t in flagged_2022),
        pnl_2022_unflagged=sum(t.exit_pnl for t in unflagged_2022),
    )


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_signal(ev: SignalEval) -> tuple[float, list[str]]:
    """
    Composite score for signal quality.
    Higher = better. Critique points returned.
    """
    score = 0.0
    notes = []

    # Coverage of grinding (want ≥ 30% to be useful)
    if ev.coverage_grinding_pct >= 60:
        score += 3
    elif ev.coverage_grinding_pct >= 40:
        score += 2
    elif ev.coverage_grinding_pct >= 25:
        score += 1
    else:
        notes.append(f"low grinding coverage ({ev.coverage_grinding_pct:.0f}%)")

    # NOT flagging spike-recover (want < 30%)
    if ev.coverage_spike_pct < 15:
        score += 3
    elif ev.coverage_spike_pct < 30:
        score += 2
    elif ev.coverage_spike_pct < 50:
        score += 1
    else:
        notes.append(f"flags spike-recover too much ({ev.coverage_spike_pct:.0f}%)")

    # Low FP rate (want < 15%)
    if ev.fp_rate_pct < 8:
        score += 3
    elif ev.fp_rate_pct < 15:
        score += 2
    elif ev.fp_rate_pct < 25:
        score += 1
    else:
        notes.append(f"high FP rate ({ev.fp_rate_pct:.0f}%)")

    # Selectivity (want < -2000)
    if ev.selectivity < -4000:
        score += 3
    elif ev.selectivity < -2000:
        score += 2
    elif ev.selectivity < 0:
        score += 1
    else:
        notes.append(f"non-negative selectivity (${ev.selectivity:+,.0f})")

    # 2022 deep-dive: must catch most of the losses
    if ev.n_2022_flagged + ev.n_2022_unflagged > 0:
        coverage_2022_n = ev.n_2022_flagged / (ev.n_2022_flagged + ev.n_2022_unflagged)
        if coverage_2022_n >= 0.7:
            score += 3
            notes.append(f"strong 2022 capture ({ev.n_2022_flagged}/18)")
        elif coverage_2022_n >= 0.4:
            score += 2
            notes.append(f"partial 2022 capture ({ev.n_2022_flagged}/18)")
        elif coverage_2022_n >= 0.2:
            score += 1
            notes.append(f"weak 2022 capture ({ev.n_2022_flagged}/18)")
        else:
            notes.append(f"FAILS 2022 capture ({ev.n_2022_flagged}/18)")

    return score, notes


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    print("=" * 90)
    print("Q053 TIER 3 — Signal Refinement for Grinding-Decline Detection")
    print(f"  Window: {FULL_START} → today;  account NLV ${ACCOUNT:,.0f}")
    print("=" * 90)

    print("\n  Step 1: building market features …", flush=True)
    df = build_market_features()
    print(f"  Series: {len(df)} days from {df.index[0].date()} to {df.index[-1].date()}")

    print("\n  Step 2: running main strategy backtest …", flush=True)
    r = run_backtest(start_date=FULL_START, account_size=ACCOUNT, verbose=False)
    trades = r.trades
    print(f"  Total trades: {len(trades)}")

    print("\n  Step 3: evaluating 6 candidate signals …", flush=True)
    sigs = define_signals(df)
    evals = []
    for name, sig in sigs.items():
        ev = evaluate_signal(name, sig, df, trades)
        sc, notes = score_signal(ev)
        evals.append((sc, notes, ev))

    # Sort by score descending
    evals.sort(key=lambda x: -x[0])

    # ── Detailed table ────────────────────────────────────────────────────────
    print("\n\n" + "═" * 110)
    print("  EVALUATION TABLE")
    print("═" * 110)
    print(f"  {'Signal':<55}  {'CovGr%':>6}  {'CovSp%':>6}  "
          f"{'FP%':>5}  {'n_flag':>6}  {'avgF':>9}  {'avgU':>9}  {'Δ':>9}  {'2022(f/u)':>10}")
    print(f"  {'─'*110}")
    for sc, notes, ev in evals:
        print(f"  {ev.name:<55}  {ev.coverage_grinding_pct:>6.1f}  "
              f"{ev.coverage_spike_pct:>6.1f}  {ev.fp_rate_pct:>5.1f}  "
              f"{ev.n_flagged:>6}  ${ev.avg_pnl_flagged:>+7,.0f}  "
              f"${ev.avg_pnl_unflagged:>+7,.0f}  ${ev.selectivity:>+7,.0f}  "
              f"{ev.n_2022_flagged:>3}/{ev.n_2022_unflagged:<2}")
    print()
    print("  Legend: CovGr=grinding-window coverage | CovSp=spike-recover coverage (lower better)")
    print("          FP=false positive rate on Other days | avgF/avgU=avg PnL flagged/unflagged")
    print("          Δ=selectivity (more negative = better detector)")
    print("          2022(f/u)=2022 trades flagged/unflagged (out of 18 total)")

    # ── Per-signal score breakdown ────────────────────────────────────────────
    print("\n\n" + "═" * 90)
    print("  SCORE BREAKDOWN (descending)")
    print("═" * 90)
    for i, (sc, notes, ev) in enumerate(evals, 1):
        print(f"\n  #{i}  Score: {sc:.0f}/15  —  {ev.name}")
        for n in notes:
            print(f"      • {n}")
        print(f"      2022 flagged trades: ${ev.pnl_2022_flagged:+,.0f} "
              f"({ev.n_2022_flagged} trades)")
        print(f"      2022 unflagged trades: ${ev.pnl_2022_unflagged:+,.0f} "
              f"({ev.n_2022_unflagged} trades)")

    # ── Verdict & recommendation ──────────────────────────────────────────────
    print("\n\n" + "═" * 90)
    print("  TIER 3 VERDICT")
    print("═" * 90)
    best_score, best_notes, best_ev = evals[0]

    print(f"\n  Best signal: {best_ev.name}")
    print(f"    Composite score: {best_score:.0f}/15")
    print(f"    Coverage: grinding {best_ev.coverage_grinding_pct:.1f}%, "
          f"spike-recover {best_ev.coverage_spike_pct:.1f}% (low = good)")
    print(f"    FP rate: {best_ev.fp_rate_pct:.1f}%")
    print(f"    Selectivity: ${best_ev.selectivity:+,.0f}/trade")
    print(f"    2022 capture: {best_ev.n_2022_flagged}/18 trades flagged "
          f"(${best_ev.pnl_2022_flagged:+,.0f} captured of $-26,778 total)")
    print()

    # Production readiness
    if best_score >= 11:
        print("  → Signal is ready for candidate SPEC (size-reduction overlay).")
        print("    Recommended next step: write DRAFT Spec for soft-overlay using this signal.")
    elif best_score >= 8:
        print("  → Signal shows promise but has trade-offs. PM should decide:")
        print("    (a) accept current signal for soft-overlay SPEC, or")
        print("    (b) continue Tier 3 refinement (longer research, more parameters)")
    else:
        print("  → No signal cleanly captures grinding-decline. Multiple trade-offs.")
        print("    Reconsider whether soft-overlay approach is feasible, or step back to")
        print("    accept that grinding-decline is a structural feature not detectable")
        print("    by simple market-state signals.")


if __name__ == "__main__":
    run()
