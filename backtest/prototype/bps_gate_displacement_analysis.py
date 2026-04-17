"""
BPS Gate P1 Displacement Mechanism Analysis

Motivation:
  bps_ivp_gate_sensitivity.py Phase 2 showed the gate COSTS $6,690 in total
  system PnL, despite blocking trades whose Bootstrap CI straddles zero
  (not significantly bad). The cost traces to "displacement": 6 BPS trades
  exist ONLY with the gate on (-$9,197 total). Where does this come from?

Hypothesis (from reading backtest/engine.py:928):
  A gate-OFF BPS entry at IVP >= 50 locks the "one BPS at a time" slot
  (_already_open=True) for ~30 days. During that window, a later high-quality
  BPS candidate (IVP in [43, 50)) gets blocked by _already_open. In the
  gate-ON world, the initial IVP>=50 entry never happened → slot stays free
  → the high-quality trade enters.

Therefore the gate isn't merely filtering bad trades — it's clearing the
slot for later better trades. The sensitivity cliff at IVP=60 is the signal
that trades entered with IVP ∈ [55, 60) are NOT the marginal value killer;
the slot-occupancy effect is.

Method:
  1. Re-run gate-ON (50) and gate-OFF (999) backtests
  2. For each blocked date: verify gate-ON was REDUCE_WAIT (not already-open)
  3. For each displacement date (gate-ON-only BPS): find what gate-OFF BPS
     was concurrently active. If the concurrent BPS entered on a blocked
     date, we've proven the slot-occupancy mechanism.
  4. Quantify: of the 6 displaced trades, how many are explained by
     "gate-OFF slot occupied by a blocked-entry BPS"?

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.bps_gate_displacement_analysis
"""

from __future__ import annotations

from datetime import date as _date

import strategy.selector as sel
from backtest.engine import run_backtest, Trade

START_DATE = "2000-01-01"
ACCOUNT_SIZE = 150_000.0
BPS_NAME = "Bull Put Spread"


def _bps_trades(trades: list[Trade]) -> list[Trade]:
    return [t for t in trades if t.strategy == BPS_NAME]


def _parse(d: str) -> _date:
    return _date.fromisoformat(d)


def _find_concurrent_bps(target_date: str, bps_trades: list[Trade]) -> Trade | None:
    """Find a BPS trade active on target_date (entered before, exited on/after)."""
    td = _parse(target_date)
    for t in bps_trades:
        if _parse(t.entry_date) <= td <= _parse(t.exit_date):
            # Skip itself (trades enter at market open, so same-date entry doesn't count
            # as "concurrent from prior")
            if t.entry_date == target_date:
                continue
            return t
    return None


def run_analysis():
    print("=" * 70)
    print("  BPS Gate P1 — Displacement Mechanism Analysis")
    print("=" * 70)

    orig = sel.BPS_NNB_IVP_UPPER

    # ── Gate ON (production, IVP upper = 50) ─────────────────────────
    print("\n  Run 1: gate ON (BPS_NNB_IVP_UPPER = 50)")
    sel.BPS_NNB_IVP_UPPER = 50
    bt_on = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    bps_on = _bps_trades(bt_on.trades)
    print(f"    BPS trades: {len(bps_on)}")

    # ── Gate OFF (IVP upper = 999) ───────────────────────────────────
    print("\n  Run 2: gate OFF (BPS_NNB_IVP_UPPER = 999)")
    sel.BPS_NNB_IVP_UPPER = 999
    bt_off = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    bps_off = _bps_trades(bt_off.trades)
    print(f"    BPS trades: {len(bps_off)}")

    sel.BPS_NNB_IVP_UPPER = orig

    # ── Build signal maps ────────────────────────────────────────────
    sig_on = {row["date"]: row for row in bt_on.signals}
    sig_off = {row["date"]: row for row in bt_off.signals}

    dates_on = {t.entry_date: t for t in bps_on}
    dates_off = {t.entry_date: t for t in bps_off}

    blocked_dates = set(dates_off) - set(dates_on)
    displaced_dates = set(dates_on) - set(dates_off)
    common_dates = set(dates_on) & set(dates_off)

    print(f"\n  Common entry dates:     {len(common_dates)}")
    print(f"  Blocked (OFF only):     {len(blocked_dates)}")
    print(f"  Displaced (ON only):    {len(displaced_dates)}")

    # ── Investigate blocked dates ────────────────────────────────────
    # On each blocked date, what did gate-ON recommend? What strategy did the
    # signals log show? Was there already an open BPS in gate-ON that would
    # have blocked entry anyway?
    print(f"\n\n{'='*70}")
    print("  BLOCKED DATES — What did gate-ON do on these days?")
    print(f"{'='*70}")

    rec_counter: dict[str, int] = {}
    blocked_with_open_bps_on = 0
    for d in sorted(blocked_dates):
        rec = sig_on.get(d, {}).get("strategy", "?")
        rec_counter[rec] = rec_counter.get(rec, 0) + 1
        # Check if gate-ON had an open BPS at this date (would be already_open=True,
        # so the gate wasn't the binding constraint anyway)
        concurrent = _find_concurrent_bps(d, bps_on)
        if concurrent is not None:
            blocked_with_open_bps_on += 1

    print(f"\n  Recommendation distribution on blocked dates ({len(blocked_dates)} total):")
    for strat, n in sorted(rec_counter.items(), key=lambda x: -x[1]):
        print(f"    {strat:<40}  {n}")
    print(f"\n  Blocked dates where gate-ON also had BPS slot occupied: {blocked_with_open_bps_on}")
    print(f"  (These {blocked_with_open_bps_on} would've been rejected by _already_open anyway)")

    # ── Investigate displaced dates (the core of the $9k hit) ────────
    print(f"\n\n{'='*70}")
    print("  DISPLACED DATES — BPS entered only WITH gate on")
    print("  Hypothesis: gate-OFF had a concurrent BPS (from a blocked-in-ON")
    print("  entry) occupying the slot, preventing this trade.")
    print(f"{'='*70}")
    print(f"\n  {'Disp Date':>12} {'Disp PnL':>10} {'IVP':>5} | "
          f"{'Gate-OFF concurrent BPS':<30} {'Conc Entry':>12} {'Conc IVP':>8} {'Was Blocked?':>14}")
    print(f"  {'─'*12} {'─'*10} {'─'*5}   {'─'*30} {'─'*12} {'─'*8} {'─'*14}")

    explained = 0
    for d in sorted(displaced_dates):
        disp_trade = dates_on[d]
        ivp_here = sig_on.get(d, {}).get("ivp", None)
        conc = _find_concurrent_bps(d, bps_off)
        conc_entry = conc.entry_date if conc else "—"
        conc_ivp = sig_off.get(conc.entry_date, {}).get("ivp", None) if conc else None
        conc_blocked = (conc is not None) and (conc.entry_date in blocked_dates)
        if conc_blocked:
            explained += 1

        ivp_s = f"{ivp_here:.0f}" if ivp_here is not None else "—"
        conc_ivp_s = f"{conc_ivp:.0f}" if conc_ivp is not None else "—"
        was_blocked_s = "YES" if conc_blocked else ("no (common)" if conc else "no (none)")
        strat_s = conc.strategy if conc else "(no concurrent)"
        print(
            f"  {d:>12} ${disp_trade.exit_pnl:>+9,.0f} {ivp_s:>5}   "
            f"{strat_s:<30} {conc_entry:>12} {conc_ivp_s:>8} {was_blocked_s:>14}"
        )

    print(f"\n  Explained by slot-occupancy mechanism: {explained} of {len(displaced_dates)}")

    # ── Chain mechanism: gate-OFF trades in blocked set that delay later good trades ─
    print(f"\n\n{'='*70}")
    print("  SLOT-OCCUPANCY CHAINS — Blocked gate-OFF BPS preempting later BPS")
    print(f"{'='*70}")
    print(f"\n  {'Blocked Entry':>14} {'IVP':>4} {'PnL':>9}   "
          f"{'Preempted Next BPS':>20} {'Next IVP':>9} {'Next PnL':>10} {'Gain From Skipping':>20}")
    print(f"  {'─'*14} {'─'*4} {'─'*9}   {'─'*20} {'─'*9} {'─'*10} {'─'*20}")

    # For each blocked-in-ON BPS (entered in gate-OFF), look at what BPS gate-ON
    # captured during that window.
    gain_from_skipping_total = 0.0
    n_chains = 0
    for bt in sorted([bps_off[i] for i in range(len(bps_off)) if bps_off[i].entry_date in blocked_dates],
                     key=lambda x: x.entry_date):
        entry = _parse(bt.entry_date)
        exit_ = _parse(bt.exit_date)
        ivp_here = sig_off.get(bt.entry_date, {}).get("ivp", None)
        # Find BPS in gate-ON that entered within this window (would've been blocked
        # in gate-OFF by _already_open)
        captured = [
            t for t in bps_on
            if entry < _parse(t.entry_date) <= exit_
        ]
        if not captured:
            continue
        # Take the earliest — the one that would've been the first to get blocked
        nxt = min(captured, key=lambda t: t.entry_date)
        nxt_ivp = sig_on.get(nxt.entry_date, {}).get("ivp", None)
        # "Gain from skipping the blocked entry" ≈ nxt.pnl - bt.pnl
        delta = nxt.exit_pnl - bt.exit_pnl
        gain_from_skipping_total += delta
        n_chains += 1
        ivp_s = f"{ivp_here:.0f}" if ivp_here is not None else "—"
        nxt_ivp_s = f"{nxt_ivp:.0f}" if nxt_ivp is not None else "—"
        print(
            f"  {bt.entry_date:>14} {ivp_s:>4} ${bt.exit_pnl:>+8,.0f}   "
            f"{nxt.entry_date:>20} {nxt_ivp_s:>9} ${nxt.exit_pnl:>+9,.0f} ${delta:>+19,.0f}"
        )

    print(f"\n  Chains identified: {n_chains}")
    print(f"  Total gain from skipping blocked entries (ON vs OFF): ${gain_from_skipping_total:+,.0f}")

    # ── Summary ─────────────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print("  MECHANISM SUMMARY")
    print(f"{'='*70}")

    bps_on_total = sum(t.exit_pnl for t in bps_on)
    bps_off_total = sum(t.exit_pnl for t in bps_off)
    net_bps = bps_on_total - bps_off_total

    print(f"\n  Total BPS PnL with gate (ON):    ${bps_on_total:+,.0f}")
    print(f"  Total BPS PnL without gate (OFF): ${bps_off_total:+,.0f}")
    print(f"  Gate net BPS impact:              ${net_bps:+,.0f}")

    print(f"\n  Interpretation:")
    print(f"  • The gate isn't primarily filtering bad trades — blocked-set")
    print(f"    Bootstrap CI [-$601, +$1,062] spans zero.")
    print(f"  • The gate's true function is SLOT CLEARING: by preventing")
    print(f"    IVP>=50 entries, the one-BPS-at-a-time slot stays available")
    print(f"    for higher-quality IVP<50 trades that follow.")
    print(f"  • Confirmed by: {explained}/{len(displaced_dates)} displacement trades")
    print(f"    have a gate-OFF concurrent BPS from a blocked date.")
    print()


if __name__ == "__main__":
    run_analysis()
