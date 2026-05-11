"""Q063 Phase 1 — VIX-Stratified Analysis of IVP≥55 Blocked Entries.

Question (PM hypothesis 2026-05-11):
    Current IVP < 55 gate for BPS (NORMAL+NEUTRAL+BULLISH path) is producing
    false alarms in low-absolute-VIX regimes. The gate's stated purpose is to
    avoid "stressed vol environment, BPS tail risk too high" — but if VIX
    absolute level is low (e.g. VIX 15-18), the "stress" interpretation may
    not apply.

Method:
    1. Run backtest with BPS_NNB_IVP_UPPER=999 (gate fully disabled)
    2. Use signal_history to identify all BPS trades that would have been
       blocked by current gate (IVP >= 55 at signal day, NNB path)
    3. Stratify blocked-but-recovered trades by VIX-at-entry bucket
    4. Compare per-bucket: win rate, avg PnL, worst trade, tail trade freq
    5. Compare to "allowed" entries (IVP 43-55) in same VIX bucket

Output:
    Console table per VIX bucket × (blocked / allowed) cross-tab
    research/q063/q063_phase1_blocked_trades.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import strategy.selector as sel
from backtest.engine import run_backtest

REPO = Path(__file__).resolve().parents[2]
OUT_CSV = REPO / "research" / "q063" / "q063_phase1_blocked_trades.csv"

START = "2007-01-01"
END = "2026-05-10"
ACCOUNT = 150_000.0


def main():
    print("=" * 80)
    print("Q063 Phase 1 — VIX-Stratified Analysis of IVP Gate Blocked Entries")
    print("=" * 80)
    print(f"Window: {START} → {END}")
    print()

    # Run baseline (gate ON, IVP < 55) to know current behavior
    print("Running BASELINE backtest (BPS_NNB_IVP_UPPER=55, current SPEC) ...")
    sel.BPS_NNB_IVP_UPPER = 55
    bt_baseline = run_backtest(start_date=START, end_date=END,
                               account_size=ACCOUNT, verbose=False)
    bps_baseline = [t for t in bt_baseline.trades if t.strategy.value == "Bull Put Spread"]
    print(f"  Baseline BPS trades: {len(bps_baseline)}")

    # Run with gate disabled (ivp_upper=999) to surface blocked entries
    print("\nRunning DISABLED-GATE backtest (BPS_NNB_IVP_UPPER=999) ...")
    sel.BPS_NNB_IVP_UPPER = 999
    bt_open = run_backtest(start_date=START, end_date=END,
                           account_size=ACCOUNT, verbose=False)
    bps_open = [t for t in bt_open.trades if t.strategy.value == "Bull Put Spread"]
    print(f"  Disabled-gate BPS trades: {len(bps_open)}")

    # Build signal date → IVP/VIX map (from disabled-gate run since that's the trade source)
    sig_df = pd.DataFrame(bt_open.signals).set_index("date")
    print(f"  Signal stream: {len(sig_df)} days")

    # Restore default
    sel.BPS_NNB_IVP_UPPER = 55

    # Enrich each BPS trade with signal-day IVP/VIX
    rows = []
    for t in bps_open:
        sig = sig_df.loc[t.entry_date] if t.entry_date in sig_df.index else None
        if sig is None:
            continue
        rows.append({
            "entry_date": t.entry_date,
            "exit_date": t.exit_date,
            "exit_reason": t.exit_reason,
            "ivp": float(sig["ivp"]),
            "vix": float(sig["vix"]),
            "regime": sig["regime"],
            "trend": sig["trend"],
            "exit_pnl": t.exit_pnl,
            "pnl_pct": t.pnl_pct,
            "contracts": t.contracts,
            "total_bp": t.total_bp,
        })
    df = pd.DataFrame(rows)

    # Classify by gate status
    df["gate_status"] = df["ivp"].apply(
        lambda x: "BLOCKED (≥55)" if x >= 55 else ("LOW (<43)" if x < 43 else "ALLOWED (43-54)")
    )

    # VIX buckets
    def vix_bucket(v):
        if v < 15: return "1. VIX<15"
        if v < 18: return "2. VIX 15-18"
        if v < 22: return "3. VIX 18-22"
        if v < 28: return "4. VIX 22-28"
        return "5. VIX≥28"
    df["vix_bucket"] = df["vix"].apply(vix_bucket)

    # ── Output 1: distribution table ──
    print("\n" + "=" * 80)
    print("Table 1 — Counts: gate_status × vix_bucket (disabled-gate sample)")
    print("=" * 80)
    cross = df.groupby(["vix_bucket", "gate_status"]).size().unstack(fill_value=0)
    print(cross.to_string())

    # ── Output 2: P&L stats by gate_status × vix_bucket ──
    print("\n" + "=" * 80)
    print("Table 2 — Per (vix_bucket × gate_status) P&L metrics")
    print("=" * 80)
    print(f"{'vix_bucket':<14} {'gate_status':<16} {'n':>4} {'WR%':>6} {'avg_PnL':>9} "
          f"{'med_PnL':>9} {'worst':>9} {'best':>9} {'tail<-1k':>9}")
    print("-" * 110)
    for vb in sorted(df["vix_bucket"].unique()):
        for gs in ["BLOCKED (≥55)", "ALLOWED (43-54)", "LOW (<43)"]:
            sub = df[(df["vix_bucket"] == vb) & (df["gate_status"] == gs)]
            if len(sub) == 0:
                continue
            wr = (sub["exit_pnl"] > 0).mean() * 100
            avg = sub["exit_pnl"].mean()
            med = sub["exit_pnl"].median()
            worst = sub["exit_pnl"].min()
            best = sub["exit_pnl"].max()
            tail = (sub["exit_pnl"] < -1000).sum()
            print(f"{vb:<14} {gs:<16} {len(sub):>4d} {wr:>5.1f}% "
                  f"${avg:>+8.0f} ${med:>+8.0f} ${worst:>+8.0f} ${best:>+8.0f} {tail:>9d}")
        print()

    # ── Output 3: focus on PM's hypothesis ──
    print("=" * 80)
    print("Table 3 — PM hypothesis test: BLOCKED entries by VIX absolute level")
    print("  'If low VIX, blocked entries are still profitable, gate is over-restrictive'")
    print("=" * 80)
    blocked = df[df["gate_status"] == "BLOCKED (≥55)"]
    print(f"\nTotal blocked-by-IVP entries (in disabled-gate run): {len(blocked)}")
    print(f"  Win rate:  {(blocked['exit_pnl'] > 0).mean()*100:.1f}%")
    print(f"  Avg P&L:   ${blocked['exit_pnl'].mean():+.0f}")
    print(f"  Sum P&L:   ${blocked['exit_pnl'].sum():+,.0f}")
    print(f"  Worst:     ${blocked['exit_pnl'].min():+,.0f}")
    print(f"  Best:      ${blocked['exit_pnl'].max():+,.0f}")
    print()
    print("Stratified by VIX-at-entry:")
    for vb in sorted(blocked["vix_bucket"].unique()):
        sub = blocked[blocked["vix_bucket"] == vb]
        wr = (sub["exit_pnl"] > 0).mean() * 100
        avg = sub["exit_pnl"].mean()
        sum_ = sub["exit_pnl"].sum()
        worst = sub["exit_pnl"].min()
        print(f"  {vb}: n={len(sub):>3} WR={wr:>5.1f}% avg=${avg:>+6.0f} sum=${sum_:>+8,.0f} worst=${worst:>+8.0f}")

    # ── Output 4: focused comparison BLOCKED vs ALLOWED in low-VIX ──
    print("\n" + "=" * 80)
    print("Table 4 — Low-VIX focus: BLOCKED vs ALLOWED comparison (VIX < 18)")
    print("=" * 80)
    low_vix = df[df["vix"] < 18]
    print(f"\nAll BPS in VIX < 18 (disabled-gate run): {len(low_vix)} trades")
    for gs in ["BLOCKED (≥55)", "ALLOWED (43-54)", "LOW (<43)"]:
        sub = low_vix[low_vix["gate_status"] == gs]
        if len(sub) == 0:
            continue
        wr = (sub["exit_pnl"] > 0).mean() * 100
        avg = sub["exit_pnl"].mean()
        sum_ = sub["exit_pnl"].sum()
        print(f"  {gs:<18}: n={len(sub):>3} WR={wr:>5.1f}% avg=${avg:>+6.0f} sum=${sum_:>+9,.0f}")

    # ── Output 5: write CSV ──
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"\nWrote {OUT_CSV}")

    # ── Output 6: VIX×IVP heatmap-style verdict ──
    print("\n" + "=" * 80)
    print("Table 5 — Avg PnL per (VIX bucket × IVP bucket)")
    print("=" * 80)
    df["ivp_bucket"] = pd.cut(df["ivp"], bins=[0, 30, 43, 55, 70, 100],
                              labels=["<30", "30-43", "43-55", "55-70", "≥70"])
    pivot = df.pivot_table(values="exit_pnl", index="vix_bucket",
                           columns="ivp_bucket", aggfunc="mean", fill_value=np.nan, observed=False)
    print(pivot.round(0).to_string())

    n_pivot = df.pivot_table(values="exit_pnl", index="vix_bucket",
                             columns="ivp_bucket", aggfunc="count", fill_value=0, observed=False)
    print("\nTrade counts:")
    print(n_pivot.to_string())


if __name__ == "__main__":
    main()
