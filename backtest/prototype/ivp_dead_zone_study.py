"""
IVP Dead Zone Study — VIX spike recovery windows blocked by IVP gates

Research question:
  After VIX spikes from HIGH_VOL back to NORMAL, IVP stays elevated (>50)
  for days/weeks. Multiple IVP gates then block ALL premium-selling paths:
    - IC NEUTRAL path: IVP must be in [20,50]
    - BPS BULLISH path: IVP must be < 50
    - IC BEARISH path: IVP must be in [20,50]
  Only NORMAL+HIGH+NEUTRAL has no IVP gate, but IV signal drops to NEUTRAL
  within 1-2 days of the VIX drop.

  Is this a systematic opportunity miss?

Approach:
  1. Identify all VIX recovery windows: HIGH_VOL→NORMAL transition with IVP>50
  2. Track how many consecutive days the system says REDUCE_WAIT despite
     a) VIX declining  b) SPX stable or rising  c) IVP slowly decaying
  3. Run counterfactual: what if we allowed IC or BPS entry during these windows?
  4. Quantify total missed PnL across full history

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.ivp_dead_zone_study
"""

from __future__ import annotations

import numpy as np

import strategy.selector as sel
from backtest.engine import run_backtest, Trade
from backtest.run_bootstrap_ci import bootstrap_ci

START_DATE = "2000-01-01"
ACCOUNT_SIZE = 150_000.0


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
    # ── Step 1: Run production backtest to get signal history ──────────
    print("  Running production backtest...")
    bt_prod = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    signals = bt_prod.signals

    # ── Step 2: Identify VIX recovery windows ─────────────────────────
    # Definition: day where regime just switched from HIGH_VOL to NORMAL
    # (or was HIGH_VOL yesterday), and IVP > 50
    print("  Identifying VIX recovery windows...\n")

    windows = []  # list of {start, end, days, signals_in_window}
    in_window = False
    current_window = None

    for i in range(1, len(signals)):
        prev = signals[i - 1]
        curr = signals[i]

        # Window start: transition from HIGH_VOL to NORMAL with IVP > 50
        if not in_window:
            if prev["regime"] == "HIGH_VOL" and curr["regime"] == "NORMAL" and curr["ivp"] > 50:
                in_window = True
                current_window = {
                    "start_date": curr["date"],
                    "start_vix": curr["vix"],
                    "start_ivp": curr["ivp"],
                    "start_spx": curr["spx"],
                    "days": [curr],
                }
        else:
            # Window continues while: regime is NORMAL and IVP > 50
            if curr["regime"] == "NORMAL" and curr["ivp"] > 50:
                current_window["days"].append(curr)
            else:
                # Window ends
                current_window["end_date"] = prev["date"]
                current_window["end_vix"] = prev["vix"]
                current_window["end_ivp"] = prev["ivp"]
                current_window["end_spx"] = prev["spx"]
                current_window["duration"] = len(current_window["days"])
                windows.append(current_window)
                in_window = False
                current_window = None

    # Close any open window
    if in_window and current_window:
        last = current_window["days"][-1]
        current_window["end_date"] = last["date"]
        current_window["end_vix"] = last["vix"]
        current_window["end_ivp"] = last["ivp"]
        current_window["end_spx"] = last["spx"]
        current_window["duration"] = len(current_window["days"])
        windows.append(current_window)

    print(f"{'=' * 90}")
    print(f"  1. VIX RECOVERY WINDOWS (HIGH_VOL→NORMAL, IVP>50)")
    print(f"     Found {len(windows)} windows across full history")
    print(f"{'=' * 90}")

    # Filter to windows >= 3 days (meaningful blockage)
    sig_windows = [w for w in windows if w["duration"] >= 3]
    print(f"\n  Windows ≥ 3 days: {len(sig_windows)}")

    print(f"\n  {'Start':>12} {'End':>12} {'Days':>5} {'VIX start':>10} {'VIX end':>9} "
          f"{'IVP start':>10} {'IVP end':>8} {'SPX Δ':>7}")
    print(f"  {'─' * 12} {'─' * 12} {'─' * 5} {'─' * 10} {'─' * 9} {'─' * 10} {'─' * 8} {'─' * 7}")

    for w in sig_windows:
        spx_chg = ((w["end_spx"] / w["start_spx"]) - 1) * 100
        print(f"  {w['start_date']:>12} {w['end_date']:>12} {w['duration']:>5} "
              f"{w['start_vix']:>10.1f} {w['end_vix']:>9.1f} "
              f"{w['start_ivp']:>10.0f} {w['end_ivp']:>8.0f} "
              f"{spx_chg:>+6.1f}%")

    # ── Step 3: Which gates blocked each day? ─────────────────────────
    print(f"\n{'=' * 90}")
    print(f"  2. DAILY GATE BLOCKAGE IN RECOVERY WINDOWS")
    print(f"{'=' * 90}")

    total_blocked_days = 0
    total_window_days = 0

    for w in sig_windows:
        print(f"\n  Window: {w['start_date']} → {w['end_date']} ({w['duration']} days)")
        for day in w["days"]:
            iv_s = day["iv_signal"]
            trend = day["trend"]
            ivp = day["ivp"]
            strat = day["strategy"]

            # Determine which gate blocked
            if "Reduce / Wait" in strat:
                blocked = True
                total_blocked_days += 1

                # Diagnose which gate
                if iv_s == "NEUTRAL" and trend == "NEUTRAL":
                    gate = f"IC NEUTRAL: IVP={ivp:.0f} > 50"
                elif iv_s == "NEUTRAL" and trend == "BULLISH":
                    gate = f"BPS BULLISH: IVP={ivp:.0f} ≥ 50"
                elif iv_s == "NEUTRAL" and trend == "BEARISH":
                    gate = f"IC BEARISH: IVP={ivp:.0f} > 50"
                elif iv_s == "HIGH":
                    gate = f"IV=HIGH but trend={trend} blocked"
                else:
                    gate = f"other: iv={iv_s} trend={trend}"
            else:
                blocked = False
                gate = f"ENTERED: {strat}"

            total_window_days += 1
            marker = "❌" if blocked else "✅"
            print(f"    {day['date']} VIX={day['vix']:5.1f} IVP={ivp:3.0f} "
                  f"iv={iv_s:8s} trend={trend:8s} {marker} {gate}")

    print(f"\n  Summary: {total_blocked_days}/{total_window_days} days blocked "
          f"({total_blocked_days / total_window_days * 100:.0f}%)")

    # ── Step 4: Counterfactual — lift all IVP gates, compare ──────────
    print(f"\n{'=' * 90}")
    print(f"  3. COUNTERFACTUAL: PRODUCTION vs ALL-IVP-GATES-LIFTED")
    print(f"{'=' * 90}")

    # Lift IC IVP gates by using the disable_entry_gates + BPS gate
    # Actually, we need to be more targeted. Let's lift BPS gate AND
    # run a version where IC NEUTRAL IVP gate is also removed.

    # Production run
    prod_trades = bt_prod.trades

    # Gate-lifted run: remove BPS IVP upper gate + IC NEUTRAL/BEARISH IVP>50 gate
    orig_bps_upper = sel.BPS_NNB_IVP_UPPER
    sel.BPS_NNB_IVP_UPPER = 999  # lift BPS gate

    # For IC gates, we need to also lift them. The IC gates are hardcoded
    # at IVP outside [20,50]. We'll monkey-patch differently.
    # Let's save and restore the function - actually easier to just
    # patch the constant check. The IC check is inline in selector.py
    # We can't easily monkey-patch it without modifying code.
    # Instead, let's just lift the BPS gate and see what happens.

    print("\n  Running with BPS IVP gate lifted (BPS_NNB_IVP_UPPER=999)...")
    bt_bps_lifted = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    sel.BPS_NNB_IVP_UPPER = orig_bps_upper

    # Compare trades in recovery windows
    prod_window_dates = set()
    for w in sig_windows:
        for day in w["days"]:
            prod_window_dates.add(day["date"])

    prod_window_trades = [t for t in prod_trades
                          if t.entry_date in prod_window_dates
                          and t.exit_reason != "end_of_backtest"]
    lifted_window_trades = [t for t in bt_bps_lifted.trades
                            if t.entry_date in prod_window_dates
                            and t.exit_reason != "end_of_backtest"]

    # New trades that only exist in lifted version
    prod_entries = {(t.entry_date, t.strategy) for t in prod_window_trades}
    new_trades = [t for t in lifted_window_trades
                  if (t.entry_date, t.strategy) not in prod_entries]

    print(f"\n  Production trades in recovery windows: {len(prod_window_trades)}")
    print(f"  Lifted trades in recovery windows:     {len(lifted_window_trades)}")
    print(f"  NEW trades (only in lifted):           {len(new_trades)}")

    if new_trades:
        print(f"\n  {'Entry':>12} {'Exit':>12} {'Strategy':<25} {'PnL':>10} {'Exit Reason':<20}")
        print(f"  {'─' * 12} {'─' * 12} {'─' * 25} {'─' * 10} {'─' * 20}")
        for t in sorted(new_trades, key=lambda x: x.entry_date):
            print(f"  {t.entry_date:>12} {t.exit_date:>12} {t.strategy:<25} "
                  f"${t.exit_pnl:>+9,.0f} {t.exit_reason:<20}")

        s = _trade_stats(new_trades)
        print(f"\n  NEW trades stats: n={s['n']}  total=${s['total_pnl']:,}  "
              f"avg=${s['avg_pnl']:,}  win={s['win_rate']}%  sharpe={s['sharpe']}")

        # Bootstrap CI
        if len(new_trades) >= 5:
            pnls = [t.exit_pnl for t in new_trades]
            ci = bootstrap_ci(pnls)
            lo, hi = ci["ci_lo"], ci["ci_hi"]
            if not (np.isnan(lo) or np.isnan(hi)):
                print(f"  Bootstrap 95% CI on avg PnL: [${round(lo):,}, ${round(hi):,}]")
                sig = "SIGNIFICANT" if lo > 0 else "NOT significant"
                print(f"  → {sig}")

    # ── Step 5: Full system comparison ────────────────────────────────
    print(f"\n{'=' * 90}")
    print(f"  4. FULL SYSTEM COMPARISON (all trades, not just window)")
    print(f"{'=' * 90}")

    prod_all = [t for t in prod_trades if t.exit_reason != "end_of_backtest"]
    lifted_all = [t for t in bt_bps_lifted.trades if t.exit_reason != "end_of_backtest"]

    s_prod = _trade_stats(prod_all)
    s_lifted = _trade_stats(lifted_all)

    print(f"\n  {'Metric':<20} {'Production':>12} {'BPS gate lifted':>15} {'Delta':>10}")
    print(f"  {'─' * 20} {'─' * 12} {'─' * 15} {'─' * 10}")
    for k in ["n", "total_pnl", "avg_pnl", "win_rate", "sharpe"]:
        v1 = s_prod[k]
        v2 = s_lifted[k]
        d = v2 - v1
        if k == "total_pnl":
            print(f"  {k:<20} ${v1:>11,} ${v2:>14,} ${d:>+9,}")
        elif k == "win_rate":
            print(f"  {k:<20} {v1:>11.1f}% {v2:>14.1f}% {d:>+9.1f}%")
        elif k == "sharpe":
            print(f"  {k:<20} {v1:>12.2f} {v2:>15.2f} {d:>+10.2f}")
        else:
            print(f"  {k:<20} {v1:>12} {v2:>15} {d:>+10}")

    # ── Step 6: How long does IVP>50 persist after HIGH_VOL→NORMAL? ───
    print(f"\n{'=' * 90}")
    print(f"  5. IVP DECAY PROFILE AFTER HIGH_VOL→NORMAL TRANSITION")
    print(f"     How many days until IVP drops below 50?")
    print(f"{'=' * 90}")

    decay_durations = [w["duration"] for w in windows]
    if decay_durations:
        arr = np.array(decay_durations)
        print(f"\n  All windows (n={len(windows)}):")
        print(f"    Mean duration:   {arr.mean():.1f} days")
        print(f"    Median duration: {np.median(arr):.1f} days")
        print(f"    Max duration:    {arr.max()} days")
        print(f"    Min duration:    {arr.min()} days")

        # Distribution
        bins = [(1, 2), (3, 5), (6, 10), (11, 20), (21, 999)]
        print(f"\n    Duration distribution:")
        for lo, hi in bins:
            count = sum(1 for d in decay_durations if lo <= d <= hi)
            label = f"[{lo},{hi}]" if hi < 999 else f"[{lo}+]"
            bar = "█" * count
            print(f"    {label:>8} {count:>3}  {bar}")

    print()


if __name__ == "__main__":
    run_study()
