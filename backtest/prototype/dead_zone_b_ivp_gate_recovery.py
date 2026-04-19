"""
Dead Zone B — IVP gates in VIX recovery windows

Continues Q015 after Dead Zone A was dropped.

Focus: BPS IVP≥50 gate and IC IVP [20,50] gate behavior
specifically during VIX recovery (HIGH_VOL in prior 5 days).

Questions:
  1. How many recovery-window blockages come from IVP gates specifically?
  2. What do those blocked trades look like when we lift each gate?
  3. Can IVP+VIX joint conditions do better than "delete the gate"?

Approach:
  Phase 1: Isolate IVP-gate-blocked days in recovery windows
  Phase 2: Lift BPS gate only, measure recovery-window trades
  Phase 3: Lift IC gate only, measure recovery-window trades
  Phase 4: Test joint filters:
    A) VIX < 18 bypass (let BPS enter even if IVP≥50 when VIX is low)
    B) VIX absolute level gate instead of IVP
    C) VIX FALLING bypass

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.dead_zone_b_ivp_gate_recovery
"""

from __future__ import annotations

import numpy as np

import strategy.selector as sel
from backtest.engine import run_backtest, Trade
from backtest.run_bootstrap_ci import bootstrap_ci

START_DATE = "2000-01-01"
ACCOUNT_SIZE = 150_000.0
BPS_NAME = "Bull Put Spread"
IC_NAME = "Iron Condor"


def _trade_stats(trades: list[Trade]) -> dict:
    if not trades:
        return {"n": 0, "total_pnl": 0, "avg_pnl": 0, "win_rate": 0, "sharpe": 0}
    pnls = [t.exit_pnl for t in trades]
    arr = np.array(pnls)
    n = len(pnls)
    mu = arr.mean()
    sigma = arr.std(ddof=1) if n > 1 else 0
    return {
        "n": n,
        "total_pnl": round(sum(pnls)),
        "avg_pnl": round(mu),
        "win_rate": round(sum(1 for p in pnls if p > 0) / n * 100, 1),
        "sharpe": round(mu / sigma, 2) if sigma > 0 else 0,
    }


def _bootstrap_summary(trades: list[Trade]) -> str:
    if len(trades) < 5:
        return f"n={len(trades)}, skipped (too few)"
    pnls = [t.exit_pnl for t in trades]
    ci = bootstrap_ci(pnls)
    lo, hi = ci["ci_lo"], ci["ci_hi"]
    if np.isnan(lo) or np.isnan(hi):
        return "NaN (degenerate)"
    sig = "SIG+" if lo > 0 else ("SIG-" if hi < 0 else "n.s.")
    return f"[${round(lo):,}, ${round(hi):,}] {sig}"


def _is_recovery(date: str, signals: list[dict], date_to_idx: dict) -> bool:
    idx = date_to_idx.get(date)
    if idx is None:
        return False
    for lookback in range(1, 6):
        j = idx - lookback
        if j >= 0 and signals[j]["regime"] == "HIGH_VOL":
            return True
    return False


def run_study():
    # ── Baseline ──────────────────────────────────────────────────────
    print("  Running production backtest...")
    bt_prod = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    signals = bt_prod.signals
    dates_list = [s["date"] for s in signals]
    date_to_idx = {d: i for i, d in enumerate(dates_list)}

    # ── Phase 1: Recovery window IVP-gate blockages ───────────────────
    print(f"\n{'=' * 80}")
    print(f"  PHASE 1: IVP-gate blockages in VIX recovery windows")
    print(f"{'=' * 80}")

    # Find all recovery days where IVP gates blocked entry
    bps_gate_recovery = []  # NEUTRAL IV + BULLISH + IVP≥50
    ic_gate_recovery = []   # NEUTRAL IV + NEUTRAL/BEARISH + IVP outside [20,50]

    for s in signals:
        if not _is_recovery(s["date"], signals, date_to_idx):
            continue
        if s["regime"] != "NORMAL":
            continue
        if "Reduce / Wait" not in s["strategy"]:
            continue

        iv_s = s["iv_signal"]
        trend = s["trend"]
        ivp = s["ivp"]

        if iv_s == "NEUTRAL" and trend == "BULLISH" and ivp >= 50:
            bps_gate_recovery.append(s)
        elif iv_s == "NEUTRAL" and trend in ("NEUTRAL", "BEARISH") and ivp > 50:
            ic_gate_recovery.append(s)

    print(f"\n  BPS IVP≥50 gate blocks in recovery: {len(bps_gate_recovery)} days")
    print(f"  IC IVP>50 gate blocks in recovery:  {len(ic_gate_recovery)} days")

    if bps_gate_recovery:
        vix_vals = [s["vix"] for s in bps_gate_recovery]
        ivp_vals = [s["ivp"] for s in bps_gate_recovery]
        print(f"\n  BPS-blocked recovery days:")
        print(f"    VIX: [{min(vix_vals):.1f}, {max(vix_vals):.1f}], mean {np.mean(vix_vals):.1f}")
        print(f"    IVP: [{min(ivp_vals):.0f}, {max(ivp_vals):.0f}], mean {np.mean(ivp_vals):.0f}")
        # VIX distribution
        for lo, hi in [(14, 16), (16, 18), (18, 20), (20, 22)]:
            n = sum(1 for v in vix_vals if lo <= v < hi)
            print(f"    VIX [{lo},{hi}): {n} days ({n/len(vix_vals)*100:.0f}%)")

    if ic_gate_recovery:
        vix_vals = [s["vix"] for s in ic_gate_recovery]
        ivp_vals = [s["ivp"] for s in ic_gate_recovery]
        print(f"\n  IC-blocked recovery days:")
        print(f"    VIX: [{min(vix_vals):.1f}, {max(vix_vals):.1f}], mean {np.mean(vix_vals):.1f}")
        print(f"    IVP: [{min(ivp_vals):.0f}, {max(ivp_vals):.0f}], mean {np.mean(ivp_vals):.0f}")
        # Trend split
        neut = sum(1 for s in ic_gate_recovery if s["trend"] == "NEUTRAL")
        bear = sum(1 for s in ic_gate_recovery if s["trend"] == "BEARISH")
        print(f"    NEUTRAL trend: {neut}, BEARISH trend: {bear}")

    # ── Phase 2: Lift BPS gate — recovery trades ─────────────────────
    print(f"\n{'=' * 80}")
    print(f"  PHASE 2: BPS IVP gate lifted (BPS_NNB_IVP_UPPER=999)")
    print(f"  Focus on recovery-window trades only")
    print(f"{'=' * 80}")

    orig_bps = sel.BPS_NNB_IVP_UPPER
    sel.BPS_NNB_IVP_UPPER = 999
    bt_bps_lifted = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    sel.BPS_NNB_IVP_UPPER = orig_bps

    bps_gate_dates = set(s["date"] for s in bps_gate_recovery)
    prod_entries = {(t.entry_date, t.strategy) for t in bt_prod.trades}

    new_bps = [t for t in bt_bps_lifted.trades
               if (t.entry_date, t.strategy) not in prod_entries
               and t.exit_reason != "end_of_backtest"
               and t.strategy == BPS_NAME]

    new_bps_recovery = [t for t in new_bps
                        if _is_recovery(t.entry_date, signals, date_to_idx)]
    new_bps_non_recovery = [t for t in new_bps
                            if not _is_recovery(t.entry_date, signals, date_to_idx)]

    sig_map = {s["date"]: s for s in signals}

    print(f"\n  NEW BPS trades (gate lifted): {len(new_bps)}")
    print(f"    Recovery:     {len(new_bps_recovery)}")
    print(f"    Non-recovery: {len(new_bps_non_recovery)}")

    if new_bps_recovery:
        print(f"\n  Recovery BPS trades:")
        print(f"  {'Entry':>12} {'Exit':>12} {'PnL':>10} {'Reason':<15} "
              f"{'VIX':>5} {'IVP':>4}")
        print(f"  {'─' * 12} {'─' * 12} {'─' * 10} {'─' * 15} {'─' * 5} {'─' * 4}")
        for t in sorted(new_bps_recovery, key=lambda x: x.entry_date):
            sig = sig_map.get(t.entry_date, {})
            print(f"  {t.entry_date:>12} {t.exit_date:>12} ${t.exit_pnl:>+9,.0f} "
                  f"{t.exit_reason:<15} {sig.get('vix', 0):>5.1f} "
                  f"{sig.get('ivp', 0):>4.0f}")

        s = _trade_stats(new_bps_recovery)
        print(f"\n  Stats: n={s['n']}  total=${s['total_pnl']:,}  avg=${s['avg_pnl']:,}  "
              f"win={s['win_rate']}%  sharpe={s['sharpe']}")
        print(f"  Bootstrap: {_bootstrap_summary(new_bps_recovery)}")

    # Full system comparison for BPS lift
    prod_closed = [t for t in bt_prod.trades if t.exit_reason != "end_of_backtest"]
    bps_closed = [t for t in bt_bps_lifted.trades if t.exit_reason != "end_of_backtest"]
    s_prod = _trade_stats(prod_closed)
    s_bps = _trade_stats(bps_closed)
    print(f"\n  Full system: {s_prod['n']}→{s_bps['n']} trades, "
          f"Sharpe {s_prod['sharpe']}→{s_bps['sharpe']}, "
          f"PnL ${s_prod['total_pnl']:,}→${s_bps['total_pnl']:,}")

    # ── Phase 3: Joint filter tests ──────────────────────────────────
    # These test WHETHER a compound condition can selectively open the
    # gate during recovery without the Sharpe damage of full removal.
    #
    # We test by running backtests with BPS_NNB_IVP_UPPER set to different
    # values, but we can't easily test compound conditions this way.
    #
    # Instead: use the gate-lifted backtest and CLASSIFY new trades by
    # VIX level / IVP level to see which sub-conditions are profitable.

    print(f"\n{'=' * 80}")
    print(f"  PHASE 3: JOINT FILTER ANALYSIS")
    print(f"  Among ALL new BPS trades (gate lifted), which conditions separate")
    print(f"  good from bad trades?")
    print(f"{'=' * 80}")

    # Classify ALL new BPS trades by VIX and IVP at entry
    all_new_bps = new_bps  # all new BPS from gate-lifted version

    print(f"\n  A) By VIX absolute level at entry:")
    vix_bins = [(14, 16), (16, 18), (18, 20), (20, 22), (22, 25)]
    print(f"  {'VIX':>10} {'n':>4} {'Avg':>8} {'Win%':>6} {'Sharpe':>7} {'Total':>10} {'Bootstrap'}")
    print(f"  {'─' * 10} {'─' * 4} {'─' * 8} {'─' * 6} {'─' * 7} {'─' * 10} {'─' * 30}")
    for lo, hi in vix_bins:
        subset = [t for t in all_new_bps
                  if lo <= sig_map.get(t.entry_date, {}).get("vix", 0) < hi]
        s = _trade_stats(subset)
        bs = _bootstrap_summary(subset) if subset else ""
        print(f"  [{lo:>2},{hi:>2}) {s['n']:>4} ${s['avg_pnl']:>+6,} "
              f"{s['win_rate']:>5.1f}% {s['sharpe']:>7.2f} ${s['total_pnl']:>+9,} {bs}")

    print(f"\n  B) By IVP band at entry:")
    ivp_bins = [(50, 55), (55, 60), (60, 65), (65, 75), (75, 100)]
    print(f"  {'IVP':>10} {'n':>4} {'Avg':>8} {'Win%':>6} {'Sharpe':>7} {'Total':>10} {'AvgVIX':>7}")
    print(f"  {'─' * 10} {'─' * 4} {'─' * 8} {'─' * 6} {'─' * 7} {'─' * 10} {'─' * 7}")
    for lo, hi in ivp_bins:
        subset = [t for t in all_new_bps
                  if lo <= sig_map.get(t.entry_date, {}).get("ivp", 0) < hi]
        s = _trade_stats(subset)
        avg_vix = np.mean([sig_map.get(t.entry_date, {}).get("vix", 0) for t in subset]) if subset else 0
        print(f"  [{lo:>2},{hi:>2}) {s['n']:>4} ${s['avg_pnl']:>+6,} "
              f"{s['win_rate']:>5.1f}% {s['sharpe']:>7.2f} ${s['total_pnl']:>+9,} {avg_vix:>6.1f}")

    print(f"\n  C) By recovery context:")
    for label, subset in [("Recovery", new_bps_recovery),
                           ("Non-recovery", new_bps_non_recovery)]:
        s = _trade_stats(subset)
        bs = _bootstrap_summary(subset) if subset else ""
        print(f"  {label:<15} n={s['n']:>3} avg=${s['avg_pnl']:>+6,} "
              f"win={s['win_rate']:>5.1f}% sharpe={s['sharpe']:>5.2f} {bs}")

    # ── Phase 4: VIX cross-tab for new BPS trades ─────────────────────
    print(f"\n{'=' * 80}")
    print(f"  PHASE 4: VIX × IVP CROSS-TAB (new BPS trades only)")
    print(f"  Can a compound filter separate profitable from unprofitable?")
    print(f"{'=' * 80}")

    vix_cuts = [(14, 17), (17, 19), (19, 21), (21, 23)]
    ivp_cuts = [(50, 60), (60, 70), (70, 85), (85, 100)]

    print(f"\n  {'':>12}", end="")
    for ilo, ihi in ivp_cuts:
        print(f"  IVP[{ilo},{ihi})", end="")
    print("  | Row total")
    print(f"  {'':>12}", end="")
    for _ in ivp_cuts:
        print(f"  {'─' * 11}", end="")
    print(f"  {'─' * 11}")

    for vlo, vhi in vix_cuts:
        print(f"  VIX[{vlo:>2},{vhi:>2})", end="")
        row_trades = []
        for ilo, ihi in ivp_cuts:
            subset = [t for t in all_new_bps
                      if vlo <= sig_map.get(t.entry_date, {}).get("vix", 0) < vhi
                      and ilo <= sig_map.get(t.entry_date, {}).get("ivp", 0) < ihi]
            if not subset:
                print(f"  {'—':>11}", end="")
            else:
                s = _trade_stats(subset)
                print(f"  {s['n']:>2}@${s['avg_pnl']:>+5,}", end="")
                row_trades.extend(subset)
        # Row total
        if row_trades:
            rs = _trade_stats(row_trades)
            print(f"  {rs['n']:>2}@${rs['avg_pnl']:>+5,}", end="")
        print()

    # ── Phase 5: Hypothetical compound filters ────────────────────────
    print(f"\n{'=' * 80}")
    print(f"  PHASE 5: HYPOTHETICAL COMPOUND FILTERS")
    print(f"  What if the BPS gate were replaced by a compound condition?")
    print(f"  (measured on new trades from gate-lifted backtest)")
    print(f"{'=' * 80}")

    filters = {
        "Current gate (IVP<50)":       lambda s: s.get("ivp", 0) < 50,
        "IVP<55":                      lambda s: s.get("ivp", 0) < 55,
        "IVP<60":                      lambda s: s.get("ivp", 0) < 60,
        "VIX<18":                      lambda s: s.get("vix", 0) < 18,
        "VIX<19":                      lambda s: s.get("vix", 0) < 19,
        "IVP<50 OR VIX<18":           lambda s: s.get("ivp", 0) < 50 or s.get("vix", 0) < 18,
        "IVP<55 OR VIX<18":           lambda s: s.get("ivp", 0) < 55 or s.get("vix", 0) < 18,
        "IVP<60 AND VIX<20":          lambda s: s.get("ivp", 0) < 60 and s.get("vix", 0) < 20,
        "No gate (all)":               lambda s: True,
    }

    # For each filter: which of the gate-lifted BPS trades would PASS?
    # Note: "Current gate" should pass 0 new trades (they all have IVP≥50)
    # But some may have entered on a day with IVP just below 50 due to
    # sequential replacement.

    # Actually, we need to evaluate the filter on ALL BPS trades (prod + new)
    # to get a fair comparison.
    all_bps_lifted = [t for t in bt_bps_lifted.trades
                      if t.strategy == BPS_NAME
                      and t.exit_reason != "end_of_backtest"]

    print(f"\n  Filter applied to ALL BPS in gate-lifted backtest ({len(all_bps_lifted)} trades):")
    print(f"\n  {'Filter':<25} {'Pass':>5} {'Avg':>8} {'Win%':>6} "
          f"{'Sharpe':>7} {'Total':>10}")
    print(f"  {'─' * 25} {'─' * 5} {'─' * 8} {'─' * 6} {'─' * 7} {'─' * 10}")

    for label, fn in filters.items():
        passed = [t for t in all_bps_lifted
                  if fn(sig_map.get(t.entry_date, {}))]
        s = _trade_stats(passed)
        marker = " ◄" if label == "Current gate (IVP<50)" else "  "
        print(f"{marker}{label:<23} {s['n']:>5} ${s['avg_pnl']:>+6,} "
              f"{s['win_rate']:>5.1f}% {s['sharpe']:>7.2f} ${s['total_pnl']:>+9,}")

    # ── Phase 6: Production + filter comparison ───────────────────────
    # The above only looks at BPS trades. For a fair system comparison,
    # we need to see: what happens to TOTAL system Sharpe under each filter?
    # We can only easily test: BPS_NNB_IVP_UPPER at different values.
    # Compound filters require code changes beyond monkey-patching.
    # So we report what we can: the sensitivity curve from Q015.

    print(f"\n{'=' * 80}")
    print(f"  PHASE 6: SYSTEM SHARPE SENSITIVITY (BPS IVP threshold)")
    print(f"{'=' * 80}")

    thresholds = [50, 55, 60, 65, 70, 999]
    print(f"\n  {'Threshold':>10} {'Trades':>7} {'PnL':>12} {'Sharpe':>8} {'BPS_n':>6}")
    print(f"  {'─' * 10} {'─' * 7} {'─' * 12} {'─' * 8} {'─' * 6}")

    for thresh in thresholds:
        sel.BPS_NNB_IVP_UPPER = thresh
        bt = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
        sel.BPS_NNB_IVP_UPPER = orig_bps
        closed = [t for t in bt.trades if t.exit_reason != "end_of_backtest"]
        bps_n = sum(1 for t in closed if t.strategy == BPS_NAME)
        s = _trade_stats(closed)
        marker = " ◄" if thresh == 50 else "  "
        label = f"IVP<{thresh}" if thresh < 999 else "No gate"
        print(f"{marker}{label:>8} {s['n']:>7} ${s['total_pnl']:>11,} "
              f"{s['sharpe']:>8.2f} {bps_n:>6}")

    print()


if __name__ == "__main__":
    run_study()
