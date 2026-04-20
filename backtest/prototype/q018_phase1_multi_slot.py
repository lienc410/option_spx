"""
Q018 Phase 1: HIGH_VOL aftermath multi-slot tradeoff — prototype only.

Trigger (2026-03 double-spike case):
  Peak 1 = 2026-03-06 (VIX 29.49) → IC_HV aftermath trade opened.
  Peak 2 = 2026-03-27 (VIX 31.05) → aftermath conditions met 03-31/04-01/04-02,
    but selector recommendation was blocked by engine's single-slot constraint
    (_already_open = any(p.strategy == rec.strategy for p in positions)).
  First position exited 2026-04-08 (21 DTE reached); by then the window closed.

Phase 1 scope:
  NO production code changes. Two prototype variants measure the tradeoff
  between "entry coverage" and "risk discipline".

  Variant A — multi-slot allowance (post-hoc approximation)
    Engine's _already_open is a local var in run_backtest (not monkey-patchable).
    Approximation: walk baseline signals, identify "aftermath-eligible" days
    (regime=HIGH_VOL, iv_signal=HIGH, trend∈{BEARISH,NEUTRAL}, vix<40,
    is_aftermath=True) where a baseline IC_HV position is already open.
    Cluster consecutive blocked days; treat each cluster as one missed entry.
    Apply baseline aftermath avg PnL (+$1,023/trade per SPEC-064 handoff)
    as upper-bound PnL estimate. Flag clusters that sit inside known
    disaster windows (2008-10, 2020-03) — those are cases where
    multi-slot would have doubled exposure into continuation.

  Variant B — tightened aftermath OFF_PEAK threshold (exact)
    Monkey-patch sel.AFTERMATH_OFF_PEAK_PCT: 0.05 → 0.10.
    Full-backtest diff vs baseline: trade count, PnL, Sharpe, max drawdown.
    Captures: "only deeper pullbacks qualify" — does it dodge
    the double-entry problem by making peak-2 ineligible?

Approximation caveats (Variant A only):
  - No BP ceiling interaction — second entry might be blocked by BP cap anyway.
  - No shock-engine / overlay interaction — aftermath in deep drawdown may
    be overridden at the engine layer.
  - PnL upper-bound is optimistic (+$1,023 per cluster); under disaster
    continuation the second entry would realize loss, not aftermath gain.

  Variant A is a SCOPING signal — "is the missed volume big enough to
  warrant Phase 2 engine changes?" — not a PnL forecast.

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.q018_phase1_multi_slot
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import strategy.selector as sel
from backtest.engine import run_backtest, Trade
from strategy.selector import StrategyName

START = "2000-01-01"

# Baseline aftermath window per SPEC-064 handoff.
BASELINE_AFTERMATH_AVG_PNL = 1023.0  # +$1,023 avg per SPEC-064 / SPEC-065 metric cards
BASELINE_AFTERMATH_COUNT = 32        # SPEC-064 handoff ground truth

# Disaster windows to flag in blocked-cluster analysis.
DISASTER_WINDOWS = [
    ("2008 GFC",    "2008-09-15", "2008-12-31"),
    ("2020 COVID",  "2020-02-20", "2020-05-31"),
    ("2025 Tariff", "2025-04-01", "2025-05-31"),
]


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _closed(trades: list[Trade]) -> list[Trade]:
    return [t for t in trades if t.exit_reason != "end_of_backtest"]


def _in_window(date: str, lo: str, hi: str) -> bool:
    return lo <= date <= hi


def _disaster_label(date: str) -> str | None:
    for name, lo, hi in DISASTER_WINDOWS:
        if _in_window(date, lo, hi):
            return name
    return None


def _rolling_max(vals: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(vals)):
        lo = max(0, i - window + 1)
        out.append(max(vals[lo:i + 1]))
    return out


def _is_aftermath_row(row: dict, peak_10d: float | None) -> bool:
    """Mirror selector.is_aftermath on a signal dict + precomputed peak."""
    vix = row["vix"]
    if peak_10d is None:
        return False
    if peak_10d < sel.AFTERMATH_PEAK_VIX_10D_MIN:
        return False
    if vix >= 40.0:
        return False
    return vix <= peak_10d * (1.0 - sel.AFTERMATH_OFF_PEAK_PCT)


def _aftermath_eligible_days(signals: list[dict]) -> list[dict]:
    """Days where selector would route to IC_HV aftermath bypass.

    Criteria = HIGH_VOL + IV HIGH + trend∈{BEARISH,NEUTRAL} + is_aftermath.
    (BULLISH path routes elsewhere; EXTREME_VOL vix≥40 is already excluded
    by is_aftermath's vix<40 guard.)
    """
    vixes = [r["vix"] for r in signals]
    peaks = _rolling_max(vixes, sel.AFTERMATH_LOOKBACK_DAYS)
    out = []
    for r, peak in zip(signals, peaks):
        if r["regime"] != "HIGH_VOL":
            continue
        if r.get("iv_signal") != "HIGH":
            continue
        if r["trend"] not in ("BEARISH", "NEUTRAL"):
            continue
        if not _is_aftermath_row(r, peak):
            continue
        enriched = dict(r)
        enriched["vix_peak_10d"] = peak
        out.append(enriched)
    return out


# ──────────────────────────────────────────────────────────────────
# Variant A — post-hoc blocked-cluster analysis
# ──────────────────────────────────────────────────────────────────

@dataclass
class BlockedCluster:
    first_day: str
    last_day: str
    n_days: int
    blocking_trade_entry: str
    blocking_trade_exit: str
    disaster: str | None


def _find_blocked_clusters(
    signals: list[dict],
    ic_hv_positions: list[Trade],
) -> tuple[list[BlockedCluster], list[dict]]:
    """Return (blocked_clusters, aftermath_eligible_days)."""
    elig = _aftermath_eligible_days(signals)
    elig_by_date = {r["date"]: r for r in elig}

    # Sort IC_HV positions by entry_date; each covers [entry_date, exit_date] inclusive.
    ic_periods = sorted(
        [(p.entry_date, p.exit_date) for p in ic_hv_positions],
        key=lambda x: x[0],
    )

    blocked: list[tuple[str, str, str]] = []  # (date, entry, exit) of blocking pos
    for r in elig:
        d = r["date"]
        for ent, ex in ic_periods:
            # Block iff d is strictly after entry (not same day; same-day opens
            # the first slot — second slot only matters for subsequent days).
            if ent < d <= ex:
                blocked.append((d, ent, ex))
                break

    # Cluster consecutive blocked days that share the same blocking position.
    clusters: list[BlockedCluster] = []
    cur: list[tuple[str, str, str]] = []
    for row in blocked:
        if not cur:
            cur = [row]
            continue
        prev_d = cur[-1][0]
        # Consecutive if next trading day in signals is equal to row[0]
        # and same blocking position.
        if row[1:] == cur[-1][1:]:
            cur.append(row)
        else:
            clusters.append(_make_cluster(cur))
            cur = [row]
    if cur:
        clusters.append(_make_cluster(cur))

    return clusters, elig


def _make_cluster(rows: list[tuple[str, str, str]]) -> BlockedCluster:
    first = rows[0][0]
    last = rows[-1][0]
    ent = rows[0][1]
    ex = rows[0][2]
    return BlockedCluster(
        first_day=first,
        last_day=last,
        n_days=len(rows),
        blocking_trade_entry=ent,
        blocking_trade_exit=ex,
        disaster=_disaster_label(first),
    )


def _report_variant_a(clusters: list[BlockedCluster], elig: list[dict]) -> None:
    print("=" * 90)
    print("  VARIANT A — post-hoc blocked-cluster analysis (NO engine change)")
    print("=" * 90)
    print(f"  aftermath-eligible days (HIGH_VOL + HIGH IV + non-bullish + is_aftermath): {len(elig)}")
    print(f"  blocked clusters (eligible day falls inside open IC_HV position window): {len(clusters)}")

    if not clusters:
        print("  (no blocked clusters — multi-slot has nothing to add)")
        return

    print()
    print(f"  {'First day':<12} {'Last day':<12} {'Days':>5}  "
          f"{'Blocking entry':<12} {'Blocking exit':<12}  Disaster")
    for c in clusters:
        disaster = c.disaster or ""
        print(f"  {c.first_day:<12} {c.last_day:<12} {c.n_days:>5}  "
              f"{c.blocking_trade_entry:<12} {c.blocking_trade_exit:<12}  {disaster}")

    # Year distribution
    by_year: dict[str, int] = {}
    for c in clusters:
        yr = c.first_day[:4]
        by_year[yr] = by_year.get(yr, 0) + 1
    print()
    print("  Year distribution:")
    for yr in sorted(by_year):
        print(f"    {yr}: {by_year[yr]}")

    # Disaster overlap
    disaster_clusters = [c for c in clusters if c.disaster]
    safe_clusters = [c for c in clusters if not c.disaster]
    print()
    print(f"  Disaster-window overlap: {len(disaster_clusters)} / {len(clusters)}")
    for c in disaster_clusters:
        print(f"    {c.first_day}..{c.last_day}  [{c.disaster}]  "
              f"← would double-enter during continuation")

    # PnL upper-bound estimate
    upper = len(clusters) * BASELINE_AFTERMATH_AVG_PNL
    safe_upper = len(safe_clusters) * BASELINE_AFTERMATH_AVG_PNL
    print()
    print(f"  Upper-bound PnL estimate (all clusters × baseline avg ${BASELINE_AFTERMATH_AVG_PNL:,.0f}):")
    print(f"    All clusters:     ${upper:+,.0f}  (optimistic — ignores continuation losses)")
    print(f"    Safe clusters:    ${safe_upper:+,.0f}  (excludes disaster windows)")
    print(f"    Per-year rate:    {len(clusters) / 27:.2f} clusters/yr over 27-year backtest")
    print()
    print("  APPROXIMATION CAVEATS:")
    print("    - No BP ceiling interaction (second entry might be BP-blocked anyway)")
    print("    - No shock engine / overlay interaction")
    print("    - Disaster-window clusters would realize LOSS, not +$1,023 gain")
    print("    - Upper-bound is optimistic; true PnL likely lower, possibly negative")


# ──────────────────────────────────────────────────────────────────
# Variant B — tightened OFF_PEAK threshold (exact)
# ──────────────────────────────────────────────────────────────────

def _stats(trades: list[Trade]) -> dict:
    if not trades:
        return {"n": 0, "mean": 0, "total": 0, "win%": 0.0, "sharpe": 0.0}
    p = np.array([t.exit_pnl for t in trades])
    n = len(p)
    mu = float(p.mean())
    sd = float(p.std(ddof=1)) if n > 1 else 0.0
    return {
        "n": n,
        "mean": round(mu),
        "total": int(p.sum()),
        "win%": round((p > 0).mean() * 100, 1),
        "sharpe": round(mu / sd, 2) if sd > 0 else 0.0,
    }


def _fmt(tag: str, s: dict) -> str:
    return (f"    {tag:<20} n={s['n']:>4}  total=${s['total']:>+10,}  "
            f"avg=${s['mean']:>+6,}  win={s['win%']:>5.1f}%  sharpe={s['sharpe']:>+5.2f}")


def _run_variant_b() -> tuple[list[Trade], list[Trade]]:
    """Return (baseline_closed_trades, variant_b_closed_trades)."""
    print("  Running baseline ...")
    bt_base = run_backtest(start_date=START, verbose=False)
    base_closed = _closed(bt_base.trades)

    print("  Running variant B (AFTERMATH_OFF_PEAK_PCT 0.05 → 0.10) ...")
    orig = sel.AFTERMATH_OFF_PEAK_PCT
    sel.AFTERMATH_OFF_PEAK_PCT = 0.10
    try:
        bt_b = run_backtest(start_date=START, verbose=False)
    finally:
        sel.AFTERMATH_OFF_PEAK_PCT = orig
    b_closed = _closed(bt_b.trades)
    return base_closed, b_closed


def _report_variant_b(base: list[Trade], b: list[Trade]) -> None:
    print()
    print("=" * 90)
    print("  VARIANT B — tightened AFTERMATH_OFF_PEAK_PCT (0.05 → 0.10)")
    print("=" * 90)

    # System-level
    print("  System-level:")
    print(_fmt("baseline", _stats(base)))
    print(_fmt("variant B", _stats(b)))
    s_base = _stats(base)
    s_b = _stats(b)
    print(f"\n  Delta: n {s_b['n'] - s_base['n']:+d}, "
          f"total ${s_b['total'] - s_base['total']:+,}, "
          f"avg ${s_b['mean'] - s_base['mean']:+,}, "
          f"sharpe {s_b['sharpe'] - s_base['sharpe']:+.2f}")

    # IC_HV aftermath subset (approximation: IC_HV trades entering in HIGH_VOL)
    def _ic_hv(ts: list[Trade]) -> list[Trade]:
        return [t for t in ts if t.strategy.value == StrategyName.IRON_CONDOR_HV.value]

    ic_base = _ic_hv(base)
    ic_b = _ic_hv(b)
    print()
    print("  IC_HV subset:")
    print(_fmt("baseline IC_HV", _stats(ic_base)))
    print(_fmt("variant B IC_HV", _stats(ic_b)))
    print(f"\n  IC_HV delta: n {len(ic_b) - len(ic_base):+d} "
          f"(positive = stricter gate somehow added trades via regime path change)")

    # Drawdown (simple: cumsum of PnL, max peak-to-trough)
    def _max_dd(trades: list[Trade]) -> float:
        if not trades:
            return 0.0
        ts = sorted(trades, key=lambda t: t.exit_date)
        cum = np.cumsum([t.exit_pnl for t in ts])
        peak = np.maximum.accumulate(cum)
        dd = cum - peak
        return float(dd.min())

    print()
    print(f"  Max drawdown (PnL cumsum peak-to-trough):")
    print(f"    baseline:  ${_max_dd(base):+,.0f}")
    print(f"    variant B: ${_max_dd(b):+,.0f}")


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────

def run_study() -> None:
    print("Q018 Phase 1 — HIGH_VOL aftermath multi-slot tradeoff")
    print()

    # Baseline once (Variant A needs it; Variant B re-runs for cleanliness)
    print("  Loading baseline (for Variant A blocked-cluster scan) ...")
    bt = run_backtest(start_date=START, verbose=False)
    base_closed = _closed(bt.trades)
    ic_hv_base = [t for t in base_closed if t.strategy.value == StrategyName.IRON_CONDOR_HV.value]
    print(f"  baseline closed trades: {len(base_closed)}, IC_HV subset: {len(ic_hv_base)}")
    print()

    # Variant A
    clusters, elig = _find_blocked_clusters(bt.signals, ic_hv_base)
    _report_variant_a(clusters, elig)
    print()

    # Sanity check vs 2026-03 trigger case
    q2 = [c for c in clusters if "2026-03" <= c.first_day <= "2026-04-10"]
    print(f"  Sanity — 2026-03/04 clusters (expected ≥1 from Peak 2): {len(q2)}")
    for c in q2:
        print(f"    {c.first_day}..{c.last_day}  "
              f"blocked by trade entered {c.blocking_trade_entry}")
    print()

    # Variant B
    _, b_closed = _run_variant_b()
    _report_variant_b(base_closed, b_closed)


if __name__ == "__main__":
    run_study()
