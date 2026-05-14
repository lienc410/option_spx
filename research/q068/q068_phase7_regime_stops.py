"""Q068 Phase 7 — Regime Stops on BPS NNB Variants
2026-05-13

PM question (2026-05-13):
> 对于 MA5 / MA10 测试，有没有加止损？如果 VIX 继续上涨或 SPX close 跌穿 MA10，
> 进行止损，回测结果如何？

Test 4 stop configurations × 4 entry variants = 16 cells:

Stops (additive, applied via engine research-mode flags):
  S0  no regime stop (existing engine defaults only — 50% profit, -2× credit stop, 21DTE roll)
  S1  vix rise stop: exit if vix > entry_vix × 1.20
  S2  ma10 stop: exit if SPX_close < SPX_10dMA
  S3  S1 OR S2 combined

Entry variants:
  V0  baseline (IVP ≥ 55 block)
  P6A narrow MA10 override
  P6B narrow MA5 override
  P6C narrow MA5 OR MA10 override

Key question: do regime stops salvage P6B/P6C (which had worst trade
-$15,119 in Phase 6 → fail hard check)? Or do they cut profit before
trades recover?

Apply stops to BPS strategies only (params.regime_stop_bps_only=True).
Min hold 1 day (params.regime_stop_min_hold_days=1) — fire immediately on
post-entry breach.
"""
from __future__ import annotations

import os
import sys
import pickle
from pathlib import Path
from collections import defaultdict
from dataclasses import replace

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import strategy.selector as sel
from backtest import engine as engine_mod
from backtest.engine import run_backtest
from strategy.selector import IVSignal, Regime, StrategyName, DEFAULT_PARAMS

START = "2007-01-01"
END = "2026-05-10"
ACCOUNT = 150_000.0
FULL_YEARS = (pd.Timestamp(END) - pd.Timestamp(START)).days / 365.25
OUT_DIR = Path(__file__).parent

# ─── Reuse Phase 6 gate factories ───────────────────────────────────────────
# Re-load features for the gates
spx_pkl = REPO / "data" / "market_cache" / "yahoo__GSPC__max__1d.pkl"
vix_pkl = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"
spx = pickle.loads(spx_pkl.read_bytes())
vix = pickle.loads(vix_pkl.read_bytes())
spx.index = pd.to_datetime(spx.index).tz_localize(None)
vix.index = pd.to_datetime(vix.index).tz_localize(None)
features = pd.DataFrame({"spx": spx["Close"]})
features["vix"]  = vix["Close"].reindex(features.index).ffill()
features["ma5"]  = features["spx"].rolling(5).mean()
features["ma10"] = features["spx"].rolling(10).mean()
features["ma50"] = features["spx"].rolling(50).mean()
features["spx_5d_return"] = features["spx"].pct_change(5)
features = features.dropna()

BLOCK_THRESHOLD = 55.0
VIX_LOW_MAX     = 20.0
MA_LOWER_PCT    = 0.99
MA_UPPER_PCT    = 1.005
RETURN_5D_MIN   = -0.02

def _row_lookup(date_str):
    ts = pd.Timestamp(date_str)
    if ts in features.index:
        return features.loc[ts].to_dict()
    idx = features.index[features.index <= ts]
    if len(idx) == 0:
        return None
    return features.loc[idx[-1]].to_dict()

def _low_vol_bullish_pullback(row, ma_col):
    if row["vix"] >= VIX_LOW_MAX: return False
    if row["spx"] <= row["ma50"]: return False
    ma = row[ma_col]
    if row["spx"] < ma * MA_LOWER_PCT: return False
    if row["spx"] > ma * MA_UPPER_PCT: return False
    if row["spx_5d_return"] <= RETURN_5D_MIN: return False
    return True

def make_baseline_gate():
    def gate(vix_value, ivp, date_str):
        return ivp >= BLOCK_THRESHOLD
    return gate

def make_narrow_override_gate(ma_cols):
    def gate(vix_value, ivp, date_str):
        if ivp < BLOCK_THRESHOLD:
            return False
        row = _row_lookup(date_str)
        if row is None:
            return True
        if any(_low_vol_bullish_pullback(row, col) for col in ma_cols):
            return False
        return True
    return gate

ENTRY_VARIANTS = [
    ("V0_baseline",      make_baseline_gate),
    ("P6A_MA10",         lambda: make_narrow_override_gate(["ma10"])),
    ("P6B_MA5",          lambda: make_narrow_override_gate(["ma5"])),
    ("P6C_MA5or10",      lambda: make_narrow_override_gate(["ma5", "ma10"])),
]

STOP_CONFIGS = [
    ("S0_no_stop",       {"regime_stop_vix_rise": 0.0,  "regime_stop_below_ma10": False}),
    ("S1_vix_rise20",    {"regime_stop_vix_rise": 0.20, "regime_stop_below_ma10": False}),
    ("S2_ma10",          {"regime_stop_vix_rise": 0.0,  "regime_stop_below_ma10": True}),
    ("S3_both",          {"regime_stop_vix_rise": 0.20, "regime_stop_below_ma10": True}),
]

# ─── Engine patcher ────────────────────────────────────────────────────────
def _make_patcher(gate_fn, base_select):
    BPS = StrategyName.BULL_PUT_SPREAD
    def patched(vix, iv, trend, params=DEFAULT_PARAMS):
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
                "Q068 Phase 7 gate blocks BPS NNB",
                vix, iv, trend, macro_warn=not trend.above_200,
                canonical_strategy=BPS.value, params=params,
            )
        return rec
    return patched

orig_select = sel.select_strategy
orig_engine_select = engine_mod.select_strategy
orig_upper = sel.BPS_NNB_IVP_UPPER
sel.BPS_NNB_IVP_UPPER = 999

# ─── Run 4 entry × 4 stop = 16 configs ──────────────────────────────────────
results: dict[tuple[str, str], object] = {}
print(f"\n{'='*94}")
print(f"  Q068 Phase 7 — 4 entry variants × 4 stop configs ({len(ENTRY_VARIANTS) * len(STOP_CONFIGS)} runs)")
print(f"{'='*94}\n")

for entry_name, factory in ENTRY_VARIANTS:
    sel.select_strategy = _make_patcher(factory(), orig_select)
    engine_mod.select_strategy = sel.select_strategy
    for stop_name, stop_kwargs in STOP_CONFIGS:
        print(f"  ▸ {entry_name}  ×  {stop_name}")
        custom_params = replace(DEFAULT_PARAMS, **stop_kwargs,
                                regime_stop_bps_only=True,
                                regime_stop_min_hold_days=1)
        try:
            bt = run_backtest(start_date=START, end_date=END,
                              account_size=ACCOUNT, verbose=False,
                              params=custom_params)
        except TypeError:
            # Engine may not support custom params kwarg; fall back to global swap
            sel.DEFAULT_PARAMS = custom_params
            bt = run_backtest(start_date=START, end_date=END,
                              account_size=ACCOUNT, verbose=False)
            sel.DEFAULT_PARAMS = DEFAULT_PARAMS
        results[(entry_name, stop_name)] = bt

sel.select_strategy = orig_select
engine_mod.select_strategy = orig_engine_select
sel.BPS_NNB_IVP_UPPER = orig_upper

# ─── Stats ──────────────────────────────────────────────────────────────────
def _stats(bt, start=None, end=None):
    def in_range(t):
        if start and t.entry_date < start: return False
        if end and t.entry_date > end: return False
        return True
    bps = [t for t in bt.trades if t.strategy.value == "Bull Put Spread" and in_range(t)]
    pnls = [t.exit_pnl for t in bps]
    # Stop reason counts
    by_reason = defaultdict(int)
    for t in bps:
        by_reason[t.exit_reason] += 1
    return {
        "bps_n":     len(bps),
        "wr_%":      round(sum(1 for p in pnls if p > 0)/max(len(bps),1)*100, 1),
        "total":     int(sum(pnls)),
        "avg":       int(sum(pnls)/max(len(bps),1)),
        "worst":     int(min(pnls, default=0)),
        "all_total": int(sum(t.exit_pnl for t in bt.trades if in_range(t))),
        "reasons":   dict(by_reason),
    }

# ─── Full sample matrix ─────────────────────────────────────────────────────
print(f"\n{'='*120}")
print("  FULL SAMPLE 2007-2026 — BPS metrics by (entry × stop)")
print(f"{'='*120}\n")
print(f"{'Entry':<14} {'Stop':<16} {'n':>4} {'WR%':>6} {'total':>9} {'avg':>7} {'worst':>9} {'all_ann':>9}")
print("-" * 90)
rows = []
for entry_name, _ in ENTRY_VARIANTS:
    for stop_name, _ in STOP_CONFIGS:
        s = _stats(results[(entry_name, stop_name)])
        ann = int(s["all_total"] / FULL_YEARS)
        print(f"{entry_name:<14} {stop_name:<16} {s['bps_n']:>4} {s['wr_%']:>5.1f}% "
              f"${s['total']:>+7,d} ${s['avg']:>+5,d} ${s['worst']:>+7,d} ${ann:>+7,d}")
        rows.append({"entry": entry_name, "stop": stop_name, **s, "all_ann": ann})

# ─── Recent 2y ──────────────────────────────────────────────────────────────
print(f"\n{'='*120}")
print("  RECENT 2y (2024-2026)")
print(f"{'='*120}\n")
print(f"{'Entry':<14} {'Stop':<16} {'n':>4} {'WR%':>6} {'total':>9} {'worst':>9}")
print("-" * 70)
for entry_name, _ in ENTRY_VARIANTS:
    for stop_name, _ in STOP_CONFIGS:
        s = _stats(results[(entry_name, stop_name)], start="2024-01-01")
        print(f"{entry_name:<14} {stop_name:<16} {s['bps_n']:>4} {s['wr_%']:>5.1f}% "
              f"${s['total']:>+7,d} ${s['worst']:>+7,d}")

# ─── Stop reason distribution (full sample) ─────────────────────────────────
print(f"\n{'='*120}")
print("  EXIT REASON DISTRIBUTION (full sample)")
print(f"{'='*120}\n")
all_reasons = set()
for r in rows:
    all_reasons.update(r["reasons"].keys())
all_reasons = sorted(all_reasons)
print(f"{'Entry':<14} {'Stop':<16}  " + "  ".join(f"{r:>15}" for r in all_reasons))
for entry_name, _ in ENTRY_VARIANTS:
    for stop_name, _ in STOP_CONFIGS:
        r = next(x for x in rows if x["entry"] == entry_name and x["stop"] == stop_name)
        counts = "  ".join(f"{r['reasons'].get(reason, 0):>15}" for reason in all_reasons)
        print(f"{entry_name:<14} {stop_name:<16}  {counts}")

# ─── Decision matrix vs S0 baseline ─────────────────────────────────────────
print(f"\n{'='*120}")
print("  DECISION MATRIX — does each (entry, stop) combo improve over (V0, S0)?")
print(f"{'='*120}\n")
bl = next(x for x in rows if x["entry"] == "V0_baseline" and x["stop"] == "S0_no_stop")
print(f"  V0 × S0 reference: n={bl['bps_n']}  total=${bl['total']:+,d}  "
      f"worst=${bl['worst']:+,d}  ann=${bl['all_ann']:+,d}\n")

for r in rows:
    if r["entry"] == "V0_baseline" and r["stop"] == "S0_no_stop":
        continue
    d_total = r["total"] - bl["total"]
    d_worst = r["worst"] - bl["worst"]
    d_ann   = r["all_ann"] - bl["all_ann"]
    pnl_ok    = d_total >= -14000  # ~ -$750/yr × 19yr
    worst_ok  = d_worst >= -2000
    verdict = "✅" if (pnl_ok and worst_ok) else "⚠" if (pnl_ok or worst_ok) else "❌"
    print(f"  {r['entry']:<14} × {r['stop']:<16}: "
          f"Δtot ${d_total:>+7,d}  Δworst ${d_worst:>+7,d}  "
          f"Δann ${d_ann:>+6,d}/yr  {verdict}")

# ─── Save ──────────────────────────────────────────────────────────────────
df = pd.DataFrame(rows)
df.to_csv(OUT_DIR / "q068_phase7_regime_stops_results.csv", index=False)
print(f"\n  Saved: q068_phase7_regime_stops_results.csv")
print("\n[Phase 7 done]")
