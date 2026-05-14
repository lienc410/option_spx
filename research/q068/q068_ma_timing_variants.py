"""Q068 — MA-Based Entry Timing Variants for BPS NNB Gate
2026-05-13

PM hypothesis (2026-05-13):
  "The IVP gate misses short-term opportunities. When SPX dips slightly,
   VIX nudges up, IVP crosses 55, and gate blocks. Then SPX rallies,
   VIX falls, IVP drops below 55, and gate allows entry at higher price.
   Then small VIX uptick → reduce → low sell. For a 9-day hold this
   high-buy/low-sell churn destroys PnL. Test whether SPX 5dMA / 10dMA
   timing improves entries."

Two design families tested:

  V4 TIGHTENING (safe wrt Q063 Phase 5):
    Keep IVP < 55 gate, ALSO require SPX ≤ NdMA to enter.
    Hypothesis: better dip-timing improves avg PnL/trade.

  V5 CONDITIONAL RELAXATION (directly tests PM's intuition):
    Block if IVP ≥ 55 AND SPX > NdMA.
    If SPX ≤ NdMA (at/below MA), bypass IVP gate → allow entry on dips.
    Hypothesis: captures profitable dip entries blocked by IVP rank-jump.

Variants:
  V0  Baseline:                 block if IVP ≥ 55
  V4a Tighten + 5dMA:           block if (IVP ≥ 55) OR (SPX > 5dMA)
  V4b Tighten + 10dMA:          block if (IVP ≥ 55) OR (SPX > 10dMA)
  V5a Relax on 10dMA buffer:    block if (IVP ≥ 55) AND (SPX > 10dMA * 1.005)
  V5b Relax on 5dMA:            block if (IVP ≥ 55) AND (SPX > 5dMA)
  V5c Relax on 10dMA:           block if (IVP ≥ 55) AND (SPX > 10dMA)

Note: V5 variants directly contradict Q063 Phase 5 logic (which rejected
gate relaxations). But the relaxation factor here (MA proximity) is a
DIFFERENT signal from what Phase 5 tested (SPX_DRAWDOWN_EXPANDING).
Worth empirical test.
"""
from __future__ import annotations

import os
import sys
import pickle
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import strategy.selector as sel
from backtest import engine as engine_mod
from backtest.engine import run_backtest
from strategy.selector import IVSignal, Regime, StrategyName

START = "2007-01-01"
END = "2026-05-10"
ACCOUNT = 150_000.0
FULL_YEARS = (pd.Timestamp(END) - pd.Timestamp(START)).days / 365.25
OUT_DIR = Path(__file__).parent

# ─── Load SPX features ──────────────────────────────────────────────────────
print("Loading SPX from production cache...")
spx_pkl = REPO / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
spx = pickle.loads(spx_pkl.read_bytes())
spx.index = pd.to_datetime(spx.index).tz_localize(None)
spx_df = pd.DataFrame({"close": spx["Close"]})
spx_df["ma5"]  = spx_df["close"].rolling(5).mean()
spx_df["ma10"] = spx_df["close"].rolling(10).mean()
spx_df = spx_df.dropna()
print(f"  SPX features ready: {len(spx_df)} TD ({spx_df.index[0].date()} → "
      f"{spx_df.index[-1].date()})")

def _ma_lookup(date_str: str) -> dict:
    """Return SPX close, 5dMA, 10dMA for date_str (fallback to nearest <= date)."""
    ts = pd.Timestamp(date_str)
    if ts in spx_df.index:
        return spx_df.loc[ts].to_dict()
    idx = spx_df.index[spx_df.index <= ts]
    if len(idx) == 0:
        return {}
    return spx_df.loc[idx[-1]].to_dict()

# ─── Gate variants ──────────────────────────────────────────────────────────
BLOCK_THRESHOLD = 55.0

def make_baseline_gate():
    def gate(vix_value, ivp, date_str):
        return ivp >= BLOCK_THRESHOLD
    return gate

def make_tighten_gate(ma_col: str):
    """V4: block if (IVP ≥ 55) OR (SPX > MA) — additional restriction."""
    def gate(vix_value, ivp, date_str):
        if ivp >= BLOCK_THRESHOLD:
            return True
        row = _ma_lookup(date_str)
        if not row:
            return False
        return row["close"] > row[ma_col]
    return gate

def make_relax_gate(ma_col: str, buffer: float = 1.0):
    """V5: block if (IVP ≥ 55) AND (SPX > MA × buffer) — relax on dips."""
    def gate(vix_value, ivp, date_str):
        if ivp < BLOCK_THRESHOLD:
            return False
        row = _ma_lookup(date_str)
        if not row:
            return True  # block when MA unknown (conservative)
        return row["close"] > row[ma_col] * buffer
    return gate

VARIANTS = [
    ("V0_baseline",        make_baseline_gate),
    ("V4a_tight_5dMA",     lambda: make_tighten_gate("ma5")),
    ("V4b_tight_10dMA",    lambda: make_tighten_gate("ma10")),
    ("V5a_relax_10dMA1pct",lambda: make_relax_gate("ma10", buffer=1.005)),
    ("V5b_relax_5dMA",     lambda: make_relax_gate("ma5",  buffer=1.0)),
    ("V5c_relax_10dMA",    lambda: make_relax_gate("ma10", buffer=1.0)),
]

# ─── Engine patcher (reuse Q067 Phase 2 pattern) ────────────────────────────
def _make_patcher(gate_fn, base_select):
    BPS = StrategyName.BULL_PUT_SPREAD
    def patched(vix, iv, trend, params=sel.DEFAULT_PARAMS):
        rec = base_select(vix, iv, trend, params)
        if rec.strategy != BPS:
            return rec
        from strategy.selector import _effective_iv_signal, _reduce_wait
        if not (vix.regime == Regime.NORMAL
                and _effective_iv_signal(iv) == IVSignal.NEUTRAL
                and trend.signal.value == "BULLISH"):
            return rec
        block = gate_fn(vix.vix, iv.iv_percentile, vix.date)
        if block:
            return _reduce_wait(
                "Q068 MA timing variant blocks BPS NNB",
                vix, iv, trend, macro_warn=not trend.above_200,
                canonical_strategy=BPS.value, params=params,
            )
        return rec
    return patched

orig_select = sel.select_strategy
orig_engine_select = engine_mod.select_strategy
orig_upper = sel.BPS_NNB_IVP_UPPER
sel.BPS_NNB_IVP_UPPER = 999  # bypass internal gate; everything goes via patcher

# ─── Run all variants ──────────────────────────────────────────────────────
print(f"\n{'='*94}")
print(f"  ENGINE BACKTEST (2007-01-01 → 2026-05-10, account=${ACCOUNT:,.0f})")
print(f"{'='*94}\n")

bt_results = {}
for name, factory in VARIANTS:
    print(f"  ▸ Running {name}...")
    sel.select_strategy = _make_patcher(factory(), orig_select)
    engine_mod.select_strategy = sel.select_strategy
    try:
        bt = run_backtest(start_date=START, end_date=END,
                          account_size=ACCOUNT, verbose=False)
    finally:
        sel.select_strategy = orig_select
        engine_mod.select_strategy = orig_engine_select
    bt_results[name] = bt

sel.BPS_NNB_IVP_UPPER = orig_upper

# ─── Stats ──────────────────────────────────────────────────────────────────
def _stats(bt):
    bps = [t for t in bt.trades if t.strategy.value == "Bull Put Spread"]
    pnls = [t.exit_pnl for t in bps]
    return {
        "bps_n":     len(bps),
        "wr_%":      round(sum(1 for p in pnls if p > 0)/max(len(bps),1)*100, 1),
        "total":     int(sum(pnls)),
        "avg":       int(sum(pnls)/max(len(bps),1)),
        "worst":     int(min(pnls, default=0)),
        "all_total": int(sum(t.exit_pnl for t in bt.trades)),
        "all_ann":   int(sum(t.exit_pnl for t in bt.trades)/FULL_YEARS),
    }

print(f"\n{'='*94}")
print("  RESULTS TABLE")
print(f"{'='*94}\n")
rows = []
for name, _ in VARIANTS:
    s = _stats(bt_results[name])
    rows.append({"variant": name, **s})
df = pd.DataFrame(rows)
print(df.to_string(index=False))

# ─── Decision table (vs baseline) ──────────────────────────────────────────
print(f"\n{'='*94}")
print("  DECISION TABLE (vs V0 baseline)")
print(f"{'='*94}\n")
bl = _stats(bt_results["V0_baseline"])
print(f"  V0 baseline: BPS_n={bl['bps_n']}  WR={bl['wr_%']}%  "
      f"avg=${bl['avg']:+,d}  total=${bl['total']:+,d}  worst=${bl['worst']:+,d}  "
      f"all_ann=${bl['all_ann']:+,d}\n")

for name, _ in VARIANTS:
    if name == "V0_baseline":
        continue
    s = _stats(bt_results[name])
    d_n      = s["bps_n"] - bl["bps_n"]
    d_avg    = s["avg"] - bl["avg"]
    d_total  = s["total"] - bl["total"]
    d_worst  = s["worst"] - bl["worst"]
    d_ann    = s["all_ann"] - bl["all_ann"]
    avg_improved = d_avg > 0
    total_ok     = d_ann >= -750
    worst_ok     = d_worst >= 0
    verdict = "✅ PASS" if (avg_improved and total_ok and worst_ok) else \
              "⚠ MIXED" if avg_improved or total_ok else "❌ FAIL"
    print(f"  {name:<22}: Δn={d_n:>+4}  Δavg=${d_avg:>+5,d}  "
          f"Δtotal=${d_total:>+7,d}  Δworst=${d_worst:>+6,d}  "
          f"Δann=${d_ann:>+7,d}/yr  → {verdict}")
    print(f"    avg/trade ↑: {'✅' if avg_improved else '❌'}  "
          f"ann ≥ -$750: {'✅' if total_ok else '❌'}  "
          f"worst ≥ baseline: {'✅' if worst_ok else '❌'}")

# ─── Drill PM's specific observation: 5/7 and 5/12 events ──────────────────
print(f"\n{'='*94}")
print("  DRILL: PM's specific observations — 2025-05-07 and 2025-05-12 SPX dips")
print(f"{'='*94}\n")

# Need VIX too for IVP context
vix_pkl = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"
vix_raw = pickle.loads(vix_pkl.read_bytes())
vix_raw.index = pd.to_datetime(vix_raw.index).tz_localize(None)
vix_series = vix_raw["Close"].dropna()

# Compute ivp_252 for context
def _ivp_at(date_ts):
    arr = vix_series.loc[:date_ts].values
    if len(arr) < 253:
        return None
    window = arr[-253:-1]
    cur = arr[-1]
    return (window < cur).mean() * 100.0

for dt_str in ["2025-04-30", "2025-05-01", "2025-05-02", "2025-05-05", "2025-05-06",
               "2025-05-07", "2025-05-08", "2025-05-09", "2025-05-12", "2025-05-13"]:
    try:
        ts = pd.Timestamp(dt_str)
        if ts not in spx_df.index:
            continue
        row = spx_df.loc[ts]
        ivp = _ivp_at(ts)
        v = float(vix_series.loc[ts]) if ts in vix_series.index else None
        spx_v = row["close"]; ma5 = row["ma5"]; ma10 = row["ma10"]
        below_5  = spx_v <= ma5
        below_10 = spx_v <= ma10
        gate_blocks = ivp is not None and ivp >= 55
        v5_allows_10 = ivp is not None and ivp >= 55 and below_10
        print(f"  {dt_str}: SPX={spx_v:.0f} 5dMA={ma5:.0f} 10dMA={ma10:.0f}  "
              f"VIX={v:.1f if v else 'NA'}  IVP={ivp:.1f if ivp else 'NA'}  "
              f"≤5MA={below_5}  ≤10MA={below_10}  V0_block={gate_blocks}  "
              f"V5c_relax_to_allow={v5_allows_10}")
    except Exception as e:
        print(f"  {dt_str}: error {e}")

# ─── Save ───────────────────────────────────────────────────────────────────
df.to_csv(OUT_DIR / "q068_ma_timing_results.csv", index=False)
print(f"\n  Saved: q068_ma_timing_results.csv")
print("\n[Q068 done]")
