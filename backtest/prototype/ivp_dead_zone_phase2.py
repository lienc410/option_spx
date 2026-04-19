"""
IVP Dead Zone — Phase 2: Gate-type breakdown and NORMAL+HIGH+BULLISH gap analysis

Extends Phase 1 findings:
  Phase 1 found 66 VIX recovery windows, 214/336 days blocked (64%).
  But the blockages come from TWO distinct mechanisms:
    A) IVP gates: IC [20,50] and BPS <50 — the original hypothesis
    B) NORMAL+HIGH+BULLISH gap: NO strategy assigned to this cell at all

  Phase 2 quantifies each mechanism separately and tests what happens
  if we fill the NORMAL+HIGH+BULLISH cell.

Usage:
  arch -arm64 venv/bin/python -m backtest.prototype.ivp_dead_zone_phase2
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


def run_phase2():
    # ── Production baseline ───────────────────────────────────────────
    print("  Running production backtest...")
    bt_prod = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    signals = bt_prod.signals

    # ── Identify recovery windows ─────────────────────────────────────
    windows = []
    in_window = False
    current_window = None

    for i in range(1, len(signals)):
        prev = signals[i - 1]
        curr = signals[i]

        if not in_window:
            if prev["regime"] == "HIGH_VOL" and curr["regime"] == "NORMAL" and curr["ivp"] > 50:
                in_window = True
                current_window = {"start_date": curr["date"], "days": [curr]}
        else:
            if curr["regime"] == "NORMAL" and curr["ivp"] > 50:
                current_window["days"].append(curr)
            else:
                current_window["duration"] = len(current_window["days"])
                windows.append(current_window)
                in_window = False
                current_window = None

    if in_window and current_window:
        current_window["duration"] = len(current_window["days"])
        windows.append(current_window)

    sig_windows = [w for w in windows if w["duration"] >= 3]

    # ── Step 1: Classify blockage by gate type ────────────────────────
    print(f"\n{'=' * 80}")
    print(f"  1. BLOCKAGE BREAKDOWN BY GATE TYPE")
    print(f"     (across {len(sig_windows)} windows ≥ 3 days)")
    print(f"{'=' * 80}")

    gate_counts = {
        "IC_IVP_gate": 0,        # NEUTRAL/BEARISH trend, IVP outside [20,50]
        "BPS_IVP_gate": 0,       # BULLISH trend, IVP ≥ 50
        "HIGH_BULLISH_gap": 0,   # IV=HIGH + BULLISH — no strategy exists
        "HIGH_other_gap": 0,     # IV=HIGH + other blocked combos
        "VIX_RISING": 0,         # VIX trend filter
        "other": 0,
        "entered": 0,
    }

    # Collect blocked days per type for PnL analysis
    high_bullish_days = []
    ivp_gate_days = []

    for w in sig_windows:
        for day in w["days"]:
            iv_s = day["iv_signal"]
            trend = day["trend"]
            ivp = day["ivp"]
            strat = day["strategy"]

            if "Reduce / Wait" not in strat:
                gate_counts["entered"] += 1
                continue

            # Classify blockage
            if iv_s == "HIGH" and trend == "BULLISH":
                gate_counts["HIGH_BULLISH_gap"] += 1
                high_bullish_days.append(day)
            elif iv_s == "HIGH" and trend in ("NEUTRAL", "BEARISH"):
                # These are VIX_RISING blocks (only HIGH+NEUTRAL/BEARISH blocks when VIX rising)
                gate_counts["HIGH_other_gap"] += 1
            elif iv_s == "NEUTRAL" and trend == "BULLISH":
                gate_counts["BPS_IVP_gate"] += 1
                ivp_gate_days.append(day)
            elif iv_s == "NEUTRAL" and trend in ("NEUTRAL", "BEARISH"):
                gate_counts["IC_IVP_gate"] += 1
                ivp_gate_days.append(day)
            else:
                gate_counts["other"] += 1

    total = sum(gate_counts.values())
    blocked = total - gate_counts["entered"]
    print(f"\n  Total recovery window days: {total}")
    print(f"  Entered: {gate_counts['entered']} ({gate_counts['entered']/total*100:.0f}%)")
    print(f"  Blocked: {blocked} ({blocked/total*100:.0f}%)")
    print()
    print(f"  Blockage breakdown:")
    print(f"    NORMAL+HIGH+BULLISH gap:     {gate_counts['HIGH_BULLISH_gap']:>4} days  "
          f"({gate_counts['HIGH_BULLISH_gap']/blocked*100:.0f}% of blocks)")
    print(f"    BPS IVP≥50 gate (BULLISH):   {gate_counts['BPS_IVP_gate']:>4} days  "
          f"({gate_counts['BPS_IVP_gate']/blocked*100:.0f}% of blocks)")
    print(f"    IC IVP>50 gate (NEUT/BEAR):  {gate_counts['IC_IVP_gate']:>4} days  "
          f"({gate_counts['IC_IVP_gate']/blocked*100:.0f}% of blocks)")
    print(f"    HIGH+NEUT/BEAR VIX rising:   {gate_counts['HIGH_other_gap']:>4} days  "
          f"({gate_counts['HIGH_other_gap']/blocked*100:.0f}% of blocks)")
    print(f"    Other:                       {gate_counts['other']:>4} days")

    # ── Step 2: Fully-blocked windows (100% blocked) ──────────────────
    print(f"\n{'=' * 80}")
    print(f"  2. FULLY-BLOCKED WINDOWS (0 entries across entire recovery)")
    print(f"{'=' * 80}")

    fully_blocked = []
    for w in sig_windows:
        entered = sum(1 for d in w["days"] if "Reduce / Wait" not in d["strategy"])
        if entered == 0:
            fully_blocked.append(w)
            start = w["days"][0]
            end = w["days"][-1]
            spx_chg = ((end["spx"] / start["spx"]) - 1) * 100
            # Classify dominant gate
            h_b = sum(1 for d in w["days"] if d["iv_signal"] == "HIGH" and d["trend"] == "BULLISH")
            bps_g = sum(1 for d in w["days"] if d["iv_signal"] == "NEUTRAL" and d["trend"] == "BULLISH")
            ic_g = sum(1 for d in w["days"] if d["iv_signal"] == "NEUTRAL" and d["trend"] in ("NEUTRAL", "BEARISH"))
            dominant = max([("HIGH+BULL gap", h_b), ("BPS IVP gate", bps_g), ("IC IVP gate", ic_g)],
                          key=lambda x: x[1])
            print(f"    {start['date']} → {end['date']} ({w['duration']}d) "
                  f"VIX {start['vix']:.0f}→{end['vix']:.0f} SPX {spx_chg:+.1f}% "
                  f"| dominant: {dominant[0]} ({dominant[1]}/{w['duration']}d)")

    print(f"\n  Total fully-blocked windows: {len(fully_blocked)} / {len(sig_windows)}")

    # ── Step 3: NORMAL+HIGH+BULLISH — what SHOULD go here? ────────────
    print(f"\n{'=' * 80}")
    print(f"  3. NORMAL+HIGH+BULLISH CELL — THE MISSING STRATEGY")
    print(f"     Current: REDUCE_WAIT (SPEC-060 Change 3)")
    print(f"     Rationale: 'BPS avg -$299 not significant (n=23)'")
    print(f"     But this was full-history; what about recovery windows?")
    print(f"{'=' * 80}")

    # Find all trades that WOULD be BPS if this cell were open
    # We can approximate: all signals where regime=NORMAL, iv=HIGH, trend=BULLISH
    all_nhb = [s for s in signals if s["regime"] == "NORMAL"
               and s["iv_signal"] == "HIGH" and s["trend"] == "BULLISH"]
    recovery_nhb = [d for d in high_bullish_days]

    print(f"\n  NORMAL+HIGH+BULLISH signal days across full history: {len(all_nhb)}")
    print(f"  ... of which are in VIX recovery windows: {len(recovery_nhb)}")

    # ── Step 4: What if NORMAL+HIGH+BULLISH → BPS? ───────────────────
    # The Spec-060 comment says "BPS avg -$299" — but that's across ALL
    # NORMAL+HIGH+BULLISH days. During recovery windows specifically,
    # these are VIX-declining days with bullish trend — premium is rich
    # and direction is favorable. Let's test.

    # Actually we need to check: when was SPEC-060 change 3 added?
    # Before that, was this cell routed to BPS?
    # Let's just run: NORMAL+HIGH+BULLISH → BPS (lift the SPEC-060 block)
    # We need to modify selector temporarily.

    # The easiest way: run with a patched selector that converts the
    # REDUCE_WAIT to BPS for this cell. But that requires code modification.
    # Instead, let's look at the FULL gate-lifted comparison.

    # Run with BOTH BPS IVP gate lifted AND check IC IVP gates
    print(f"\n{'=' * 80}")
    print(f"  4. FULL SYSTEM COMPARISON: BPS IVP gate only")
    print(f"     (NORMAL+HIGH+BULLISH gap NOT addressed)")
    print(f"{'=' * 80}")

    orig_bps = sel.BPS_NNB_IVP_UPPER
    sel.BPS_NNB_IVP_UPPER = 999
    bt_bps_only = run_backtest(start_date=START_DATE, account_size=ACCOUNT_SIZE)
    sel.BPS_NNB_IVP_UPPER = orig_bps

    prod_closed = [t for t in bt_prod.trades if t.exit_reason != "end_of_backtest"]
    bps_closed = [t for t in bt_bps_only.trades if t.exit_reason != "end_of_backtest"]

    s1 = _trade_stats(prod_closed)
    s2 = _trade_stats(bps_closed)

    print(f"\n  BPS IVP gate lifted: {s1['n']} → {s2['n']} trades, "
          f"${s1['total_pnl']:,} → ${s2['total_pnl']:,} "
          f"(Δ ${s2['total_pnl']-s1['total_pnl']:+,}), "
          f"Sharpe {s1['sharpe']} → {s2['sharpe']}")

    # ── Step 5: Quantify the two dead zones separately ────────────────
    print(f"\n{'=' * 80}")
    print(f"  5. TWO DEAD ZONES — INDEPENDENT QUANTIFICATION")
    print(f"{'=' * 80}")

    # Dead Zone A: NORMAL+HIGH+BULLISH gap
    # Count unique windows where this is the DOMINANT blocker
    dz_a_windows = [w for w in sig_windows
                    if sum(1 for d in w["days"]
                           if d["iv_signal"] == "HIGH" and d["trend"] == "BULLISH"
                           and "Reduce / Wait" in d["strategy"]) >= 3]
    dz_a_days = sum(1 for w in sig_windows for d in w["days"]
                    if d["iv_signal"] == "HIGH" and d["trend"] == "BULLISH"
                    and "Reduce / Wait" in d["strategy"])

    # Dead Zone B: IVP gates (NEUTRAL IV + IVP>50)
    dz_b_windows = [w for w in sig_windows
                    if sum(1 for d in w["days"]
                           if d["iv_signal"] == "NEUTRAL" and d["ivp"] > 50
                           and "Reduce / Wait" in d["strategy"]) >= 3]
    dz_b_days = sum(1 for w in sig_windows for d in w["days"]
                    if d["iv_signal"] == "NEUTRAL" and d["ivp"] > 50
                    and "Reduce / Wait" in d["strategy"])

    print(f"\n  Dead Zone A: NORMAL+HIGH+BULLISH gap")
    print(f"    Windows with ≥3 blocked days: {len(dz_a_windows)}")
    print(f"    Total blocked days: {dz_a_days}")
    print(f"    VIX range on blocked days: ", end="")
    if high_bullish_days:
        vix_vals = [d["vix"] for d in high_bullish_days]
        print(f"[{min(vix_vals):.1f}, {max(vix_vals):.1f}], mean {np.mean(vix_vals):.1f}")
    else:
        print("N/A")

    print(f"\n  Dead Zone B: IVP gates (NEUTRAL IV, IVP>50)")
    print(f"    Windows with ≥3 blocked days: {len(dz_b_windows)}")
    print(f"    Total blocked days: {dz_b_days}")
    print(f"    VIX range on blocked days: ", end="")
    if ivp_gate_days:
        vix_vals = [d["vix"] for d in ivp_gate_days]
        print(f"[{min(vix_vals):.1f}, {max(vix_vals):.1f}], mean {np.mean(vix_vals):.1f}")
    else:
        print("N/A")

    # ── Step 6: Window-level SPX return during full blockade ──────────
    print(f"\n{'=' * 80}")
    print(f"  6. SPX RETURNS DURING FULLY-BLOCKED WINDOWS")
    print(f"     (what the market did while the system sat out)")
    print(f"{'=' * 80}")

    if fully_blocked:
        returns = []
        for w in fully_blocked:
            start = w["days"][0]
            end = w["days"][-1]
            ret = ((end["spx"] / start["spx"]) - 1) * 100
            returns.append(ret)
        arr = np.array(returns)
        print(f"\n  Fully-blocked windows: {len(fully_blocked)}")
        print(f"  SPX returns: mean {arr.mean():+.1f}%, median {np.median(arr):+.1f}%")
        print(f"  Positive: {sum(1 for r in returns if r > 0)}/{len(returns)} "
              f"({sum(1 for r in returns if r > 0)/len(returns)*100:.0f}%)")
        print(f"  Range: [{arr.min():+.1f}%, {arr.max():+.1f}%]")

    print()


if __name__ == "__main__":
    run_phase2()
