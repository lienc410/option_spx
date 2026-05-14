"""Q069 Phase 1 — Smoothed IVP Gate
2026-05-13

Per 2nd Quant Q068 review framing:
> "未来要重开，应该是一个真正不同的研究假设，而不是继续在 hard gate
>  周边加小修小补。"

This is the first such genuinely-different attempt: instead of modifying
the gate logic (Q067 hysteresis) or adding entry filters (Q068 MA timing),
we modify the SIGNAL INPUT — smooth IVP_252 before applying the threshold.

Hypothesis:
  Q067 documented daily flip rate 7.37% with 61% reversing within 5 TD.
  These flips are noise from rank-jump in the 15-18 VIX clustering region.
  A short-window smoothing of IVP_252 should reduce daily noise without
  changing the underlying signal, preserving alpha while reducing jitter.

Variants:
  V0  raw IVP_252 ≥ 55                (production baseline)
  V1  3d SMA of IVP_252 ≥ 55
  V2  5d SMA of IVP_252 ≥ 55
  V3  10d SMA of IVP_252 ≥ 55
  V4  EWM IVP (alpha=0.3, ~3d effective) ≥ 55
  V5  EWM IVP (alpha=0.1, ~10d effective) ≥ 55

For each:
  A. Daily flip-rate on full 4871 TD VIX series (Q067 metric)
  B. Engine backtest 2007-2026 → BPS NNB trade stats
  C. Decision vs V0

Note: smoothing introduces LAG. Concern is whether smoothed signal still
catches genuine VIX repricing in time to block, or lags too much.
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

BLOCK_THRESHOLD = 55.0

# ─── Load VIX + compute IVP variants ───────────────────────────────────────
print("Loading VIX + precomputing IVP variants...")
vix_pkl = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"
vix = pickle.loads(vix_pkl.read_bytes())
vix.index = pd.to_datetime(vix.index).tz_localize(None)
vix_series = vix["Close"].dropna().sort_index()

def _rolling_ivp(s, w=252):
    arr = s.values
    out = np.full(len(arr), np.nan)
    for i in range(w, len(arr)):
        out[i] = (arr[i - w : i] < arr[i]).mean() * 100.0
    return pd.Series(out, index=s.index)

ivp_raw = _rolling_ivp(vix_series, 252)
ivp_sma3 = ivp_raw.rolling(3).mean()
ivp_sma5 = ivp_raw.rolling(5).mean()
ivp_sma10 = ivp_raw.rolling(10).mean()
ivp_ewm30 = ivp_raw.ewm(alpha=0.3, adjust=False).mean()
ivp_ewm10 = ivp_raw.ewm(alpha=0.1, adjust=False).mean()

# Build features df
features = pd.DataFrame({
    "vix": vix_series,
    "ivp_raw": ivp_raw,
    "ivp_sma3": ivp_sma3,
    "ivp_sma5": ivp_sma5,
    "ivp_sma10": ivp_sma10,
    "ivp_ewm30": ivp_ewm30,
    "ivp_ewm10": ivp_ewm10,
}).dropna()
features_after_2007 = features[features.index >= pd.Timestamp("2007-01-01")]
print(f"  Full features: {len(features)} TD; analysis window 2007+: {len(features_after_2007)} TD")

VARIANTS = [
    ("V0_raw",       "ivp_raw"),
    ("V1_sma3",      "ivp_sma3"),
    ("V2_sma5",      "ivp_sma5"),
    ("V3_sma10",     "ivp_sma10"),
    ("V4_ewm_a0.3",  "ivp_ewm30"),
    ("V5_ewm_a0.1",  "ivp_ewm10"),
]

# ─── A. Daily flip-rate measurement on each smoothed IVP ───────────────────
print(f"\n{'='*94}")
print(f"  A. DAILY FLIP-RATE on smoothed IVP variants (2007-2026 window)")
print(f"{'='*94}\n")

flip_results = []
for name, col in VARIANTS:
    series = features_after_2007[col]
    blocks = (series >= BLOCK_THRESHOLD).astype(int).values
    n_total = len(blocks)
    n_block = int(blocks.sum())
    flips = np.abs(np.diff(blocks))
    n_flips = int(flips.sum())
    flip_rate = n_flips / n_total * 100

    # Tight flip-flop within 5 TD
    flip_idx = np.where(flips == 1)[0]
    flip_flop = 0
    for i, j in enumerate(flip_idx[:-1]):
        for k in flip_idx[i+1:]:
            if k - j > 5:
                break
            if blocks[j+1] != blocks[k+1]:
                flip_flop += 1
                break
    flip_results.append({
        "variant": name,
        "block_days": n_block,
        "block_%": round(n_block/n_total*100, 1),
        "flips": n_flips,
        "flip_rate_%": round(flip_rate, 2),
        "flip_flop_5TD": flip_flop,
        "flip_flop_%": round(flip_flop/max(n_flips,1)*100, 1),
    })

df_flip = pd.DataFrame(flip_results)
print(df_flip.to_string(index=False))

# ─── Quick agreement check: smoothed vs raw on each day ────────────────────
print(f"\n{'='*94}")
print(f"  AGREEMENT — how often does smoothed gate differ from V0 raw?")
print(f"{'='*94}\n")

v0_block = (features_after_2007["ivp_raw"] >= BLOCK_THRESHOLD)
for name, col in VARIANTS:
    if name == "V0_raw":
        continue
    v_block = (features_after_2007[col] >= BLOCK_THRESHOLD)
    diff = (v0_block != v_block).sum()
    pct = diff / len(features_after_2007) * 100
    # split into "smoothed allows but raw blocks" vs "smoothed blocks but raw allows"
    smooth_allow_raw_block = ((~v_block) & v0_block).sum()
    smooth_block_raw_allow = (v_block & (~v0_block)).sum()
    print(f"  {name}: {diff} TD differ ({pct:.2f}%)  | "
          f"smooth allows + raw blocks: {smooth_allow_raw_block}  | "
          f"smooth blocks + raw allows: {smooth_block_raw_allow}")

# ─── B. Engine backtest for each variant ───────────────────────────────────
def _gate_factory(col_name):
    series = features[col_name]
    def gate(vix_value, ivp, date_str):
        ts = pd.Timestamp(date_str)
        if ts in series.index:
            smoothed = series.loc[ts]
        else:
            idx = series.index[series.index <= ts]
            if len(idx) == 0:
                return ivp >= BLOCK_THRESHOLD
            smoothed = series.loc[idx[-1]]
        if pd.isna(smoothed):
            return ivp >= BLOCK_THRESHOLD
        return smoothed >= BLOCK_THRESHOLD
    return gate

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
                "Q069 smoothed IVP gate blocks BPS NNB",
                vix, iv, trend, macro_warn=not trend.above_200,
                canonical_strategy=BPS.value, params=params,
            )
        return rec
    return patched

orig_select = sel.select_strategy
orig_engine_select = engine_mod.select_strategy
orig_upper = sel.BPS_NNB_IVP_UPPER
sel.BPS_NNB_IVP_UPPER = 999  # bypass internal gate; all gating via patcher

print(f"\n{'='*94}")
print(f"  B. ENGINE BACKTEST (2007-01-01 → 2026-05-10, account=${ACCOUNT:,.0f})")
print(f"{'='*94}\n")

bt_results = {}
for name, col in VARIANTS:
    print(f"  ▸ {name} ({col})...")
    sel.select_strategy = _make_patcher(_gate_factory(col), orig_select)
    engine_mod.select_strategy = sel.select_strategy
    try:
        bt = run_backtest(start_date=START, end_date=END,
                          account_size=ACCOUNT, verbose=False)
    finally:
        sel.select_strategy = orig_select
        engine_mod.select_strategy = orig_engine_select
    bt_results[name] = bt

sel.BPS_NNB_IVP_UPPER = orig_upper

def _stats(bt, start=None, end=None):
    def in_range(t):
        if start and t.entry_date < start: return False
        if end and t.entry_date > end: return False
        return True
    bps = [t for t in bt.trades if t.strategy.value == "Bull Put Spread" and in_range(t)]
    pnls = [t.exit_pnl for t in bps]
    return {
        "bps_n":     len(bps),
        "wr_%":      round(sum(1 for p in pnls if p > 0)/max(len(bps),1)*100, 1),
        "total":     int(sum(pnls)),
        "avg":       int(sum(pnls)/max(len(bps),1)),
        "worst":     int(min(pnls, default=0)),
        "all_total": int(sum(t.exit_pnl for t in bt.trades if in_range(t))),
    }

# ─── Results tables ─────────────────────────────────────────────────────────
print(f"\n{'='*94}")
print(f"  RESULTS — full 19yr")
print(f"{'='*94}\n")
print(f"{'Variant':<14} {'BPS_n':>6} {'WR%':>7} {'Total':>10} {'Avg':>8} {'Worst':>10} {'all_ann':>10}")
print("-" * 75)
rows = []
for name, _ in VARIANTS:
    s = _stats(bt_results[name])
    ann = int(s["all_total"] / FULL_YEARS)
    print(f"{name:<14} {s['bps_n']:>6} {s['wr_%']:>6.1f}% "
          f"${s['total']:>+8,d} ${s['avg']:>+6,d} ${s['worst']:>+8,d} ${ann:>+8,d}")
    rows.append({"variant": name, **s, "all_ann": ann})

print(f"\n{'='*94}")
print(f"  OOS (2018-2026)")
print(f"{'='*94}\n")
for name, _ in VARIANTS:
    s = _stats(bt_results[name], start="2018-01-01")
    print(f"  {name:<14}: n={s['bps_n']:>3}  WR={s['wr_%']:>5.1f}%  "
          f"total=${s['total']:>+7,d}  worst=${s['worst']:>+7,d}")

print(f"\n{'='*94}")
print(f"  Recent 2y (2024-2026)")
print(f"{'='*94}\n")
for name, _ in VARIANTS:
    s = _stats(bt_results[name], start="2024-01-01")
    print(f"  {name:<14}: n={s['bps_n']:>3}  WR={s['wr_%']:>5.1f}%  "
          f"total=${s['total']:>+7,d}  worst=${s['worst']:>+7,d}")

# ─── Decision table vs V0 ───────────────────────────────────────────────────
print(f"\n{'='*94}")
print(f"  DECISION TABLE (vs V0_raw baseline)")
print(f"{'='*94}\n")
bl = next(r for r in rows if r["variant"] == "V0_raw")
bl_flip = next(r for r in flip_results if r["variant"] == "V0_raw")
print(f"  V0_raw: BPS_n={bl['bps_n']} WR={bl['wr_%']}% total=${bl['total']:+,d} "
      f"worst=${bl['worst']:+,d} ann=${bl['all_ann']:+,d} flip_rate={bl_flip['flip_rate_%']}%\n")
for r in rows:
    if r["variant"] == "V0_raw":
        continue
    f = next(x for x in flip_results if x["variant"] == r["variant"])
    d_n      = r["bps_n"] - bl["bps_n"]
    d_total  = r["total"] - bl["total"]
    d_worst  = r["worst"] - bl["worst"]
    d_ann    = r["all_ann"] - bl["all_ann"]
    d_flip   = f["flip_rate_%"] - bl_flip["flip_rate_%"]
    # Strict dominance: PnL within $750/yr × 19y = $14k, worst not worse, flip lower
    pnl_ok    = d_ann >= -750
    worst_ok  = d_worst >= 0
    flip_ok   = f["flip_rate_%"] < 3.0
    flip_better = d_flip < 0
    if pnl_ok and worst_ok and flip_better:
        verdict = "✅ DOMINATES V0"
    elif pnl_ok and flip_ok and worst_ok:
        verdict = "✅ PASS (flip<3% goal)"
    elif (pnl_ok and worst_ok) or flip_ok:
        verdict = "⚠ MIXED"
    else:
        verdict = "❌ FAIL"
    print(f"  {r['variant']:<14}: Δn={d_n:>+4}  Δtot=${d_total:>+7,d}  "
          f"Δworst=${d_worst:>+7,d}  Δann=${d_ann:>+6,d}/yr  "
          f"flip={f['flip_rate_%']:>4.2f}% ({d_flip:+.2f}pp)  → {verdict}")
    print(f"    PnL ann ≥-$750: {'✅' if pnl_ok else '❌'}  "
          f"worst ≥ baseline: {'✅' if worst_ok else '❌'}  "
          f"flip < 3%: {'✅' if flip_ok else '❌'}  "
          f"flip < V0: {'✅' if flip_better else '❌'}")

# ─── Save ──────────────────────────────────────────────────────────────────
pd.DataFrame(rows).to_csv(OUT_DIR / "q069_phase1_smoothed_ivp_bt.csv", index=False)
df_flip.to_csv(OUT_DIR / "q069_phase1_smoothed_ivp_flip.csv", index=False)
print(f"\n  Saved: q069_phase1_smoothed_ivp_bt.csv + q069_phase1_smoothed_ivp_flip.csv")
print("\n[Phase 1 done]")
