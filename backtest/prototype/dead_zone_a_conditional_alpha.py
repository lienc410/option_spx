"""
Dead Zone A — Conditional Alpha Test

Question:
  In NORMAL+HIGH+BULLISH days that fall within a VIX recovery context
  (HIGH_VOL in the prior 5 trading days), does BPS have significant
  positive alpha?

Method:
  1. Run gate-OFF backtest (SPEC-060 Change 3 bypassed) to get BPS trades
     that WOULD have entered in the NORMAL+HIGH+BULLISH cell
  2. Tag each such trade: "recovery" if HIGH_VOL appeared in prior 5 days,
     "non-recovery" otherwise
  3. Compare: recovery BPS vs non-recovery BPS vs production (no BPS here)
  4. Bootstrap CI on recovery subset
  5. Single-slot reality: count actual TRADES, not days

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.dead_zone_a_conditional_alpha
"""

from __future__ import annotations

import numpy as np

import strategy.selector as sel
from backtest.engine import run_backtest, Trade
from backtest.run_bootstrap_ci import bootstrap_ci

START_DATE = "2000-01-01"
ACCOUNT_SIZE = 150_000.0
BPS_NAME = "Bull Put Spread"


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


def run_study():
    # ── Step 0: Production baseline ───────────────────────────────────
    print("  Running production backtest (baseline)...")
    bt_prod = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    prod_signals = bt_prod.signals

    # Build regime history: for each date, was HIGH_VOL in prior 5 days?
    regime_by_date = {s["date"]: s["regime"] for s in prod_signals}
    dates_list = [s["date"] for s in prod_signals]
    date_to_idx = {d: i for i, d in enumerate(dates_list)}

    def _is_recovery(date: str) -> bool:
        """Was HIGH_VOL present in the prior 1-5 trading days?"""
        idx = date_to_idx.get(date)
        if idx is None:
            return False
        for lookback in range(1, 6):
            j = idx - lookback
            if j >= 0 and prod_signals[j]["regime"] == "HIGH_VOL":
                return True
        return False

    # ── Step 1: Identify NORMAL+HIGH+BULLISH days ─────────────────────
    nhb_days = [s for s in prod_signals
                if s["regime"] == "NORMAL"
                and s["iv_signal"] == "HIGH"
                and s["trend"] == "BULLISH"]

    nhb_recovery = [s for s in nhb_days if _is_recovery(s["date"])]
    nhb_non_recovery = [s for s in nhb_days if not _is_recovery(s["date"])]

    print(f"\n{'=' * 80}")
    print(f"  1. NORMAL+HIGH+BULLISH DAY CLASSIFICATION")
    print(f"{'=' * 80}")
    print(f"\n  Total NHB days:      {len(nhb_days)}")
    print(f"  Recovery context:    {len(nhb_recovery)} ({len(nhb_recovery)/len(nhb_days)*100:.0f}%)")
    print(f"  Non-recovery:        {len(nhb_non_recovery)} ({len(nhb_non_recovery)/len(nhb_days)*100:.0f}%)")

    recovery_dates = set(s["date"] for s in nhb_recovery)
    non_recovery_dates = set(s["date"] for s in nhb_non_recovery)

    # Show VIX profile of each group
    if nhb_recovery:
        vix_r = [s["vix"] for s in nhb_recovery]
        ivp_r = [s["ivp"] for s in nhb_recovery]
        print(f"\n  Recovery group:")
        print(f"    VIX: [{min(vix_r):.1f}, {max(vix_r):.1f}], mean {np.mean(vix_r):.1f}")
        print(f"    IVP: [{min(ivp_r):.0f}, {max(ivp_r):.0f}], mean {np.mean(ivp_r):.0f}")

    if nhb_non_recovery:
        vix_nr = [s["vix"] for s in nhb_non_recovery]
        ivp_nr = [s["ivp"] for s in nhb_non_recovery]
        print(f"\n  Non-recovery group:")
        print(f"    VIX: [{min(vix_nr):.1f}, {max(vix_nr):.1f}], mean {np.mean(vix_nr):.1f}")
        print(f"    IVP: [{min(ivp_nr):.0f}, {max(ivp_nr):.0f}], mean {np.mean(ivp_nr):.0f}")

    # ── Step 2: Run gate-OFF backtest ─────────────────────────────────
    # We need to open the NORMAL+HIGH+BULLISH cell to BPS.
    # The block is at selector.py:879-888 — it's a hardcoded return.
    # We can't monkey-patch it like BPS_NNB_IVP_UPPER.
    # Instead: lift the BPS IVP gate (which lets BPS enter when BULLISH+IVP>50)
    # AND lift the NORMAL+HIGH+BULLISH block.
    #
    # The simplest approach: since NORMAL+HIGH+BULLISH currently returns
    # REDUCE_WAIT with canonical_strategy=BPS, and no IVP gate applies
    # (it's before the NEUTRAL IV block), we need to actually patch
    # the selector function.
    #
    # Alternative: use the existing backtest with disable_entry_gates.
    # But that only affects BCS ivp63 gate and retired DIAGONAL Gate 1.
    #
    # Cleanest approach: temporarily replace the selector's _reduce_wait
    # call for this specific cell.

    # Monkey-patch select_strategy to override NORMAL+HIGH+BULLISH → BPS
    # We patch in BOTH the selector module AND the engine module's namespace
    from strategy.selector import (
        select_strategy as _orig_select,
        StrategyName, Leg, _build_recommendation, _size_rule,
        get_position_action, catalog_strategy_key, IVSignal,
        _effective_iv_signal, Regime,
    )
    import backtest.engine as engine_mod

    def _patched_select(vix, iv, trend, params=sel.DEFAULT_PARAMS):
        rec = _orig_select(vix, iv, trend, params)
        # Override NHB REDUCE_WAIT to BPS
        if (vix.regime == Regime.NORMAL
                and _effective_iv_signal(iv) == IVSignal.HIGH
                and trend.signal.value == "BULLISH"
                and rec.strategy == StrategyName.REDUCE_WAIT):
            action = get_position_action(
                StrategyName.BULL_PUT_SPREAD.value,
                is_wait=False,
                strategy_key=catalog_strategy_key(StrategyName.BULL_PUT_SPREAD.value),
            )
            return _build_recommendation(
                StrategyName.BULL_PUT_SPREAD,
                vix=vix, iv=iv, trend=trend,
                legs=[
                    Leg("SELL", "PUT", 30, 0.30, "Short put"),
                    Leg("BUY",  "PUT", 30, 0.05, "Long put (wing)"),
                ],
                size_rule=_size_rule(vix, IVSignal.HIGH, trend.signal),
                rationale="NORMAL + IV HIGH + BULLISH — patched to BPS for dead zone test",
                position_action=action,
                macro_warning=not trend.above_200,
            )
        return rec

    print(f"\n{'=' * 80}")
    print(f"  2. COUNTERFACTUAL: NORMAL+HIGH+BULLISH → BPS (patched)")
    print(f"{'=' * 80}")

    _saved = engine_mod.select_strategy
    engine_mod.select_strategy = _patched_select
    print("  Running patched backtest (NHB → BPS)...")
    bt_patched = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    engine_mod.select_strategy = _saved

    # Find BPS trades that entered on NHB dates
    all_nhb_dates = set(s["date"] for s in nhb_days)
    prod_bps = [t for t in bt_prod.trades if t.strategy == BPS_NAME]
    patched_bps = [t for t in bt_patched.trades if t.strategy == BPS_NAME]

    # New BPS trades = in patched but not in production
    prod_entries = {(t.entry_date, t.strategy) for t in bt_prod.trades}
    new_bps = [t for t in patched_bps
               if (t.entry_date, t.strategy) not in prod_entries
               and t.exit_reason != "end_of_backtest"]

    # Split new BPS by recovery vs non-recovery
    new_bps_recovery = [t for t in new_bps if t.entry_date in recovery_dates]
    new_bps_non_recovery = [t for t in new_bps if t.entry_date in non_recovery_dates]
    new_bps_other = [t for t in new_bps
                     if t.entry_date not in recovery_dates
                     and t.entry_date not in non_recovery_dates]

    print(f"\n  Production BPS trades: {len(prod_bps)}")
    print(f"  Patched BPS trades:    {len(patched_bps)}")
    print(f"  NEW BPS trades:        {len(new_bps)}")
    print(f"    Recovery context:    {len(new_bps_recovery)}")
    print(f"    Non-recovery:        {len(new_bps_non_recovery)}")
    print(f"    Other:               {len(new_bps_other)}")

    # ── Step 3: Recovery BPS trade details ────────────────────────────
    print(f"\n{'=' * 80}")
    print(f"  3. RECOVERY CONTEXT BPS TRADES — INDIVIDUAL DETAIL")
    print(f"{'=' * 80}")

    sig_map = {s["date"]: s for s in prod_signals}

    if new_bps_recovery:
        print(f"\n  {'Entry':>12} {'Exit':>12} {'PnL':>10} {'Reason':<15} "
              f"{'VIX':>5} {'IVP':>4} {'SPX':>7}")
        print(f"  {'─' * 12} {'─' * 12} {'─' * 10} {'─' * 15} {'─' * 5} {'─' * 4} {'─' * 7}")
        for t in sorted(new_bps_recovery, key=lambda x: x.entry_date):
            sig = sig_map.get(t.entry_date, {})
            print(f"  {t.entry_date:>12} {t.exit_date:>12} ${t.exit_pnl:>+9,.0f} "
                  f"{t.exit_reason:<15} {sig.get('vix', 0):>5.1f} "
                  f"{sig.get('ivp', 0):>4.0f} {sig.get('spx', 0):>7.0f}")

        s = _trade_stats(new_bps_recovery)
        print(f"\n  Stats: n={s['n']}  total=${s['total_pnl']:,}  avg=${s['avg_pnl']:,}  "
              f"win={s['win_rate']}%  sharpe={s['sharpe']}")

        # Bootstrap CI
        pnls = [t.exit_pnl for t in new_bps_recovery]
        if len(pnls) >= 5:
            ci = bootstrap_ci(pnls)
            lo, hi = ci["ci_lo"], ci["ci_hi"]
            if not (np.isnan(lo) or np.isnan(hi)):
                print(f"  Bootstrap 95% CI on avg PnL: [${round(lo):,}, ${round(hi):,}]")
                sig = "SIGNIFICANT" if lo > 0 else "NOT significant"
                print(f"  → {sig}")
            else:
                print(f"  Bootstrap CI: NaN (sample too small for reliable CI)")
        else:
            print(f"  Bootstrap CI: skipped (n={len(pnls)} < 5)")

    # ── Step 4: Non-recovery BPS trades ───────────────────────────────
    print(f"\n{'=' * 80}")
    print(f"  4. NON-RECOVERY CONTEXT BPS TRADES — COMPARISON")
    print(f"{'=' * 80}")

    if new_bps_non_recovery:
        print(f"\n  {'Entry':>12} {'Exit':>12} {'PnL':>10} {'Reason':<15} "
              f"{'VIX':>5} {'IVP':>4}")
        print(f"  {'─' * 12} {'─' * 12} {'─' * 10} {'─' * 15} {'─' * 5} {'─' * 4}")
        for t in sorted(new_bps_non_recovery, key=lambda x: x.entry_date):
            sig = sig_map.get(t.entry_date, {})
            print(f"  {t.entry_date:>12} {t.exit_date:>12} ${t.exit_pnl:>+9,.0f} "
                  f"{t.exit_reason:<15} {sig.get('vix', 0):>5.1f} "
                  f"{sig.get('ivp', 0):>4.0f}")

        s = _trade_stats(new_bps_non_recovery)
        print(f"\n  Stats: n={s['n']}  total=${s['total_pnl']:,}  avg=${s['avg_pnl']:,}  "
              f"win={s['win_rate']}%  sharpe={s['sharpe']}")

        pnls = [t.exit_pnl for t in new_bps_non_recovery]
        if len(pnls) >= 5:
            ci = bootstrap_ci(pnls)
            lo, hi = ci["ci_lo"], ci["ci_hi"]
            if not (np.isnan(lo) or np.isnan(hi)):
                print(f"  Bootstrap 95% CI on avg PnL: [${round(lo):,}, ${round(hi):,}]")
                sig = "SIGNIFICANT" if lo > 0 else "NOT significant"
                print(f"  → {sig}")

    # ── Step 5: Displaced trades analysis ─────────────────────────────
    print(f"\n{'=' * 80}")
    print(f"  5. DISPLACEMENT CHECK — did new BPS crowd out existing trades?")
    print(f"{'=' * 80}")

    # Find trades that exist in production but NOT in patched version
    patched_entries = {(t.entry_date, t.strategy) for t in bt_patched.trades}
    displaced = [t for t in bt_prod.trades
                 if (t.entry_date, t.strategy) not in patched_entries
                 and t.exit_reason != "end_of_backtest"]

    if displaced:
        print(f"\n  Displaced trades (in production, missing from patched): {len(displaced)}")
        d_stats = _trade_stats(displaced)
        print(f"  Stats: n={d_stats['n']}  total=${d_stats['total_pnl']:,}  avg=${d_stats['avg_pnl']:,}")
        for t in sorted(displaced, key=lambda x: x.entry_date):
            print(f"    {t.entry_date} {t.strategy} ${t.exit_pnl:+,.0f}")
    else:
        print(f"\n  No displaced trades — new BPS entries did not crowd out existing trades")

    # ── Step 6: Full system impact ────────────────────────────────────
    print(f"\n{'=' * 80}")
    print(f"  6. FULL SYSTEM COMPARISON")
    print(f"{'=' * 80}")

    prod_closed = [t for t in bt_prod.trades if t.exit_reason != "end_of_backtest"]
    patched_closed = [t for t in bt_patched.trades if t.exit_reason != "end_of_backtest"]

    s_prod = _trade_stats(prod_closed)
    s_patched = _trade_stats(patched_closed)

    print(f"\n  {'Metric':<20} {'Production':>12} {'NHB→BPS':>12} {'Delta':>10}")
    print(f"  {'─' * 20} {'─' * 12} {'─' * 12} {'─' * 10}")
    for k in ["n", "total_pnl", "avg_pnl", "win_rate", "sharpe"]:
        v1 = s_prod[k]
        v2 = s_patched[k]
        d = v2 - v1
        if k == "total_pnl":
            print(f"  {k:<20} ${v1:>11,} ${v2:>11,} ${d:>+9,}")
        elif k == "win_rate":
            print(f"  {k:<20} {v1:>11.1f}% {v2:>11.1f}% {d:>+9.1f}%")
        elif k == "sharpe":
            print(f"  {k:<20} {v1:>12.2f} {v2:>12.2f} {d:>+10.2f}")
        else:
            print(f"  {k:<20} {v1:>12} {v2:>12} {d:>+10}")

    # ── Step 7: Recovery-only system (most conservative test) ─────────
    # What if we ONLY open NHB→BPS during recovery, and keep
    # NHB→REDUCE_WAIT for non-recovery?
    # We can approximate: take system impact and subtract non-recovery trades
    print(f"\n{'=' * 80}")
    print(f"  7. RECOVERY-ONLY IMPACT (most conservative estimate)")
    print(f"     What if NHB→BPS only during VIX recovery, keep REDUCE_WAIT otherwise?")
    print(f"{'=' * 80}")

    recovery_pnl = sum(t.exit_pnl for t in new_bps_recovery) if new_bps_recovery else 0
    non_recovery_pnl = sum(t.exit_pnl for t in new_bps_non_recovery) if new_bps_non_recovery else 0
    displaced_pnl = sum(t.exit_pnl for t in displaced) if displaced else 0

    # Net impact of recovery-only = recovery gains - displacement costs
    # (assuming non-recovery trades don't exist in recovery-only version)
    print(f"\n  Recovery BPS gain:      ${recovery_pnl:>+10,}")
    print(f"  Non-recovery BPS gain:  ${non_recovery_pnl:>+10,}  (would NOT exist)")
    print(f"  Displaced trade cost:   ${-displaced_pnl:>+10,}  (partial, hard to attribute)")
    print(f"\n  → Recovery-only net is approximately ${recovery_pnl:>+,}")
    print(f"    across {len(new_bps_recovery)} trades over {len(dates_list)} trading days")

    print()


if __name__ == "__main__":
    run_study()
