"""Q044 Tier 2 — BPS bp_target 15% Deep Dive.

Focus: A1 (bp_target=15%) vs A0 baseline (10%), plus A2 ceiling analysis.

Parts:
  1. Year-by-year attribution (A0 vs A1) — confirm robustness
  2. Full PM metrics pack per PM standing rule:
       marginal $/BP-day, worst trade, disaster window,
       max concurrent BP%, CVaR 5%, Sharpe, win rate
  3. A2 ceiling cliff autopsy — which trades blocked, why, what if ceiling lifted?
  4. Q036 combined ceiling simulation — BPS A1 + Overlay-F 2x peak BP check
"""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from backtest.engine import run_backtest, DEFAULT_PARAMS, StrategyParams
from strategy.selector import StrategyName

WINDOW_START = "2023-01-01"
ACCOUNT_SIZE = 150_000.0
BPS_KEY      = StrategyName.BULL_PUT_SPREAD


def _bps(trades):
    return [t for t in trades if t.strategy == BPS_KEY]


def _year(t):
    return str(t.entry_date)[:4]


# ─────────────────────────────────────────────────────────────────────────────
# Part 1: Year-by-year attribution
# ─────────────────────────────────────────────────────────────────────────────
def part1_yearly(r_a0, r_a1):
    print("\n" + "═" * 70)
    print("PART 1 — Year-by-Year Attribution (A0 bp=10% vs A1 bp=15%)")
    print("═" * 70)

    years = sorted({_year(t) for t in _bps(r_a0.trades) + _bps(r_a1.trades)})
    hdr = f"{'Year':<6} {'N_A0':>5} {'PnL_A0':>9} {'N_A1':>5} {'PnL_A1':>9} {'ΔPNL':>9} {'A0_WR%':>7} {'A1_WR%':>7}"
    print(hdr)
    print("-" * len(hdr))

    total_d0 = total_d1 = 0
    for yr in years:
        b0 = [t for t in _bps(r_a0.trades) if _year(t) == yr]
        b1 = [t for t in _bps(r_a1.trades) if _year(t) == yr]
        p0 = sum(t.exit_pnl for t in b0)
        p1 = sum(t.exit_pnl for t in b1)
        w0 = sum(1 for t in b0 if t.exit_pnl > 0) / len(b0) * 100 if b0 else float("nan")
        w1 = sum(1 for t in b1 if t.exit_pnl > 0) / len(b1) * 100 if b1 else float("nan")
        total_d0 += p0
        total_d1 += p1
        print(f"{yr:<6} {len(b0):>5} {p0:>9,.0f} {len(b1):>5} {p1:>9,.0f} "
              f"{p1-p0:>+9,.0f} {w0:>7.1f} {w1:>7.1f}")

    print("-" * len(hdr))
    print(f"{'Total':<6} {len(_bps(r_a0.trades)):>5} {total_d0:>9,.0f} "
          f"{len(_bps(r_a1.trades)):>5} {total_d1:>9,.0f} {total_d1-total_d0:>+9,.0f}")


# ─────────────────────────────────────────────────────────────────────────────
# Part 2: Full PM metrics pack
# ─────────────────────────────────────────────────────────────────────────────
def _disaster_window(bps_trades, window_days=60):
    """Max cumulative loss over any rolling window_days period."""
    if not bps_trades:
        return 0.0
    events = sorted([(t.entry_date, t.exit_pnl) for t in bps_trades], key=lambda x: x[0])
    worst = 0.0
    for i, (start_date, _) in enumerate(events):
        start_dt = pd.to_datetime(start_date)
        window_pnl = sum(
            p for d, p in events
            if start_dt <= pd.to_datetime(d) <= start_dt + pd.Timedelta(days=window_days)
        )
        worst = min(worst, window_pnl)
    return worst


def _peak_concurrent_bp(trades):
    """Max total BP% across all concurrent open positions (approximate)."""
    events = []
    for t in trades:
        if t.entry_date and t.exit_date:
            events.append((t.entry_date, +t.bp_pct_account))
            events.append((t.exit_date,  -t.bp_pct_account))
    events.sort(key=lambda x: x[0])
    current, peak = 0.0, 0.0
    for _, delta in events:
        current += delta
        peak = max(peak, current)
    return round(peak, 1)


def part2_metrics_pack(r_a0, r_a1):
    print("\n" + "═" * 70)
    print("PART 2 — Full PM Metrics Pack (BPS only + account CVaR)")
    print("═" * 70)

    from datetime import date
    yrs = (date.today() - pd.to_datetime(WINDOW_START).date()).days / 365.25

    def _pack(label, result):
        bps  = _bps(result.trades)
        all_ = result.trades
        if not bps:
            return {"label": label}

        pnls = [t.exit_pnl for t in bps]
        total_pnl = sum(pnls)
        n    = len(bps)
        win  = sum(1 for p in pnls if p > 0) / n * 100

        # $/BP-day
        bp_days = sum(t.total_bp * t.hold_days for t in bps if t.hold_days and t.total_bp)
        marg    = total_pnl / bp_days if bp_days > 0 else 0.0

        # worst trade
        worst = min(pnls)
        worst_pct = worst / ACCOUNT_SIZE * 100

        # disaster window (60-day rolling)
        disaster = _disaster_window(bps, 60)
        disaster_pct = disaster / ACCOUNT_SIZE * 100

        # peak concurrent BP% (all strategies)
        peak_bp = _peak_concurrent_bp(all_)

        # CVaR 5% (all strategies)
        all_pnl = sorted(t.exit_pnl for t in all_)
        cvar5   = float(np.mean(all_pnl[:max(1, int(len(all_pnl) * 0.05))]))

        # Sharpe (BPS trades as observations; annualized using mean/std × sqrt(n/yrs))
        pnl_arr = np.array(pnls)
        sharpe  = (np.mean(pnl_arr) / np.std(pnl_arr) * np.sqrt(n / yrs)) if np.std(pnl_arr) > 0 else float("nan")

        # annualized ROE (BPS contribution)
        ann_roe = total_pnl / ACCOUNT_SIZE / yrs * 100

        return {
            "label": label, "n": n, "win_rt": round(win, 1),
            "total_pnl": round(total_pnl, 0),
            "ann_roe_pp": round(ann_roe, 3),
            "marg_bpday": round(marg, 5),
            "worst_$": round(worst, 0),
            "worst_pct": round(worst_pct, 2),
            "disaster_$": round(disaster, 0),
            "disaster_pct": round(disaster_pct, 2),
            "peak_bp_pct": peak_bp,
            "cvar5": round(cvar5, 0),
            "sharpe": round(sharpe, 2),
        }

    p0 = _pack("A0 bp=10%", r_a0)
    p1 = _pack("A1 bp=15%", r_a1)

    rows = [
        ("Metric", "A0 bp=10%", "A1 bp=15%", "Delta"),
        ("N (BPS trades)",      p0["n"],          p1["n"],          "—"),
        ("Win rate %",          f"{p0['win_rt']}", f"{p1['win_rt']}", "—"),
        ("Total BPS PnL",       f"${p0['total_pnl']:,.0f}", f"${p1['total_pnl']:,.0f}", f"${p1['total_pnl']-p0['total_pnl']:+,.0f}"),
        ("Annualized ROE pp",   f"{p0['ann_roe_pp']:.3f}%", f"{p1['ann_roe_pp']:.3f}%", f"{p1['ann_roe_pp']-p0['ann_roe_pp']:+.3f}pp"),
        ("Marginal $/BP-day",   f"{p0['marg_bpday']:.5f}", f"{p1['marg_bpday']:.5f}", f"{(p1['marg_bpday']-p0['marg_bpday'])/p0['marg_bpday']*100:+.1f}%"),
        ("Worst trade $",       f"${p0['worst_$']:,.0f}", f"${p1['worst_$']:,.0f}", f"${p1['worst_$']-p0['worst_$']:+,.0f}"),
        ("Worst trade % acct",  f"{p0['worst_pct']:.2f}%", f"{p1['worst_pct']:.2f}%", f"{p1['worst_pct']-p0['worst_pct']:+.2f}pp"),
        ("Disaster 60d window", f"${p0['disaster_$']:,.0f}", f"${p1['disaster_$']:,.0f}", f"${p1['disaster_$']-p0['disaster_$']:+,.0f}"),
        ("Disaster % acct",     f"{p0['disaster_pct']:.2f}%", f"{p1['disaster_pct']:.2f}%", f"{p1['disaster_pct']-p0['disaster_pct']:+.2f}pp"),
        ("Peak concurrent BP%", f"{p0['peak_bp_pct']:.1f}%", f"{p1['peak_bp_pct']:.1f}%", f"{p1['peak_bp_pct']-p0['peak_bp_pct']:+.1f}pp"),
        ("CVaR 5% (all strat)", f"${p0['cvar5']:,.0f}", f"${p1['cvar5']:,.0f}", f"${p1['cvar5']-p0['cvar5']:+,.0f}"),
        ("Sharpe (BPS only)",   f"{p0['sharpe']:.2f}", f"{p1['sharpe']:.2f}", f"{p1['sharpe']-p0['sharpe']:+.2f}"),
    ]

    col_w = [30, 14, 14, 12]
    sep   = "-" * sum(col_w)
    print(f"{'Metric':<{col_w[0]}} {'A0 bp=10%':>{col_w[1]}} {'A1 bp=15%':>{col_w[2]}} {'Delta':>{col_w[3]}}")
    print(sep)
    for row in rows[1:]:
        print(f"{row[0]:<{col_w[0]}} {str(row[1]):>{col_w[1]}} {str(row[2]):>{col_w[2]}} {str(row[3]):>{col_w[3]}}")


# ─────────────────────────────────────────────────────────────────────────────
# Part 3: A2 ceiling cliff autopsy
# ─────────────────────────────────────────────────────────────────────────────
def part3_ceiling_autopsy(r_a0, r_a1, r_a2, r_a2_high_ceiling):
    print("\n" + "═" * 70)
    print("PART 3 — A2 (bp=20%) Ceiling Cliff Autopsy")
    print("═" * 70)

    b0 = _bps(r_a0.trades)
    b1 = _bps(r_a1.trades)
    b2 = _bps(r_a2.trades)
    b2h = _bps(r_a2_high_ceiling.trades)

    e0 = {t.entry_date for t in b0}
    e2 = {t.entry_date for t in b2}
    blocked = e0 - e2
    new_at_a2 = e2 - e0

    print(f"A0 BPS entry dates  : {len(e0)}")
    print(f"A2 BPS entry dates  : {len(e2)}")
    print(f"Blocked at A2       : {len(blocked)} trades  {sorted(blocked)}")
    print(f"New at A2 (not in A0): {len(new_at_a2)}  {sorted(new_at_a2)}")

    if blocked:
        print("\nBlocked trade PnL (what they would have earned at A0 scale):")
        for t in sorted(b0, key=lambda x: x.entry_date):
            if t.entry_date in blocked:
                print(f"  {t.entry_date}  pnl={t.exit_pnl:+,.0f}  exit={t.exit_reason}")

    print(f"\nA2 with ceiling 40%: {len(b2h)} BPS trades")
    print(f"  Total PnL: ${sum(t.exit_pnl for t in b2h):,.0f}  "
          f"WR: {sum(1 for t in b2h if t.exit_pnl>0)/len(b2h)*100:.1f}%"
          if b2h else "  No BPS trades")

    print(f"\nSummary:")
    print(f"  A2 (ceiling=35%): N={len(b2)}, PnL=${sum(t.exit_pnl for t in b2):,.0f}")
    print(f"  A2 (ceiling=40%): N={len(b2h)}, PnL=${sum(t.exit_pnl for t in b2h):,.0f}")
    print(f"  Lifting ceiling 35%→40% recovers {len(b2h)-len(b2)} blocked trades")


# ─────────────────────────────────────────────────────────────────────────────
# Part 4: Q036 combined ceiling stress test
# ─────────────────────────────────────────────────────────────────────────────
def part4_combined_ceiling(r_a1):
    print("\n" + "═" * 70)
    print("PART 4 — Q036 Combined Ceiling Stress Test (A1 + Overlay-F 2x)")
    print("═" * 70)

    all_t = r_a1.trades
    bps_t = _bps(all_t)
    ic_hv = [t for t in all_t if t.strategy == StrategyName.IRON_CONDOR_HV]

    print(f"A1 BPS trades: {len(bps_t)}  |  IC_HV trades: {len(ic_hv)}")

    # Simulate: for each IC_HV aftermath trade, assume Overlay-F doubles size (2x)
    # BP for IC_HV at 2x = bp_pct_account * 2.0
    # Check: max(BPS_bp + IC_HV_2x_bp) vs ceilings
    # NORMAL ceiling = 35%, HIGH_VOL ceiling = 50%

    print("\nIC_HV trades (would be Overlay-F candidates if active):")
    for t in sorted(ic_hv, key=lambda x: x.entry_date):
        bp_1x = t.bp_pct_account
        bp_2x = bp_1x * 2.0
        # Check concurrent BPS
        concurrent_bps = [
            b for b in bps_t
            if b.entry_date <= t.exit_date and b.exit_date >= t.entry_date
        ]
        bps_bp = sum(b.bp_pct_account for b in concurrent_bps)
        combined = bps_bp + bp_2x
        ceiling = 50.0  # HIGH_VOL ceiling applies during IC_HV
        status = "OK" if combined <= ceiling else "BREACH"
        print(f"  {t.entry_date}→{t.exit_date}  "
              f"IC_HV_1x={bp_1x:.1f}%  IC_HV_2x={bp_2x:.1f}%  "
              f"concur_BPS={bps_bp:.1f}%  combined={combined:.1f}%  "
              f"ceiling={ceiling}%  [{status}]")

    # Summary
    max_combined = max(
        (sum(b.bp_pct_account for b in bps_t
             if b.entry_date <= t.exit_date and b.exit_date >= t.entry_date)
         + t.bp_pct_account * 2.0)
        for t in ic_hv
    ) if ic_hv else 0.0

    print(f"\nPeak combined BP% (BPS A1 + IC_HV 2x): {max_combined:.1f}%")
    print(f"HIGH_VOL ceiling: 50.0%")
    print(f"Status: {'WITHIN CEILING' if max_combined <= 50 else 'EXCEEDS CEILING'}")
    print(f"\nNote: NORMAL ceiling (35%) applies when BPS is open but IC_HV is NOT open.")
    print(f"  Max BPS-only peak BP: {_peak_concurrent_bp(bps_t):.1f}%")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("Q044 Tier 2 — BPS bp_target 15% Deep Dive")
    print("=" * 70)
    print(f"Window: {WINDOW_START} → today  |  Account: ${ACCOUNT_SIZE:,.0f}\n")

    print("Running variants (4 backtests)...")

    p_a0 = deepcopy(DEFAULT_PARAMS)

    p_a1 = deepcopy(DEFAULT_PARAMS)
    p_a1.bp_target_normal  = 0.15
    p_a1.bp_target_low_vol = 0.15

    p_a2 = deepcopy(DEFAULT_PARAMS)
    p_a2.bp_target_normal  = 0.20
    p_a2.bp_target_low_vol = 0.20

    p_a2_hc = deepcopy(DEFAULT_PARAMS)   # A2 with ceiling lifted to 40%
    p_a2_hc.bp_target_normal   = 0.20
    p_a2_hc.bp_target_low_vol  = 0.20
    p_a2_hc.bp_ceiling_normal  = 0.40
    p_a2_hc.bp_ceiling_low_vol = 0.40 if hasattr(p_a2_hc, "bp_ceiling_low_vol") else None

    print("  A0 (baseline)...", flush=True)
    r_a0 = run_backtest(start_date=WINDOW_START, account_size=ACCOUNT_SIZE, params=p_a0)
    print("  A1 (bp=15%)...", flush=True)
    r_a1 = run_backtest(start_date=WINDOW_START, account_size=ACCOUNT_SIZE, params=p_a1)
    print("  A2 (bp=20%)...", flush=True)
    r_a2 = run_backtest(start_date=WINDOW_START, account_size=ACCOUNT_SIZE, params=p_a2)
    print("  A2+ceiling40%...", flush=True)
    r_a2h = run_backtest(start_date=WINDOW_START, account_size=ACCOUNT_SIZE, params=p_a2_hc)

    part1_yearly(r_a0, r_a1)
    part2_metrics_pack(r_a0, r_a1)
    part3_ceiling_autopsy(r_a0, r_a1, r_a2, r_a2h)
    part4_combined_ceiling(r_a1)

    print("\n" + "═" * 70)
    print("TIER 2 VERDICT")
    print("═" * 70)


if __name__ == "__main__":
    main()
