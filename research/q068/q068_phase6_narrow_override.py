"""Q068 Phase 6 — Low-vol Dip-Entry Override (Narrow Design per 2nd Quant)
2026-05-13

2nd Quant proposes a much narrower override than Q068 Round 1's blanket V5
variants. The hypothesis is:

  IVP > 55 gate may be too conservative in LOW-VOL BULLISH PULLBACK setups,
  causing missed short-term BPS entries near MA support.

But override must NOT re-admit known bad trades (e.g., 2026-02-25 BPS loss).

Override 触发条件（A 主测，B/C 对照）：

  A) MA10 narrow override:
       VIX < 20
       AND SPX_close > SPX_MA50
       AND SPX_close in [MA10 × 0.99, MA10 × 1.005]   (within -1% to +0.5%)
       AND SPX 5d return > -2%
     → 即使 IVP ≥ 55 也允许 BPS NNB entry

  B) MA5 narrow override: 同 A 但用 MA5

  C) MA5 OR MA10 narrow override: 任一 MA condition 满足

Hard checks (Go/No-Go):
  - Override must NOT allow the 2026-02-25 BPS loss
  - Override should allow 2025-05-07 / 2025-05-12 style dips
  - Full-sample PnL > baseline (or within $750/yr)
  - OOS 2018-2026 PnL > baseline
  - Worst override trade not materially worse than baseline
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

# ─── Load SPX + VIX features ────────────────────────────────────────────────
print("Loading SPX + VIX...")
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
print(f"  Features ready: {len(features)} TD ({features.index[0].date()} → "
      f"{features.index[-1].date()})")

def _row_lookup(date_str: str) -> dict | None:
    ts = pd.Timestamp(date_str)
    if ts in features.index:
        return features.loc[ts].to_dict()
    idx = features.index[features.index <= ts]
    if len(idx) == 0:
        return None
    return features.loc[idx[-1]].to_dict()

# ─── Override condition functions ──────────────────────────────────────────
BLOCK_THRESHOLD = 55.0
VIX_LOW_MAX     = 20.0
MA_LOWER_PCT    = 0.99    # SPX >= MA × 0.99
MA_UPPER_PCT    = 1.005   # SPX <= MA × 1.005
RETURN_5D_MIN   = -0.02   # SPX 5d return > -2%

def _low_vol_bullish_pullback(row, ma_col) -> bool:
    """Return True if override conditions met for given MA column."""
    if row["vix"] >= VIX_LOW_MAX:                 return False
    if row["spx"] <= row["ma50"]:                  return False
    ma = row[ma_col]
    if row["spx"] < ma * MA_LOWER_PCT:             return False
    if row["spx"] > ma * MA_UPPER_PCT:             return False
    if row["spx_5d_return"] <= RETURN_5D_MIN:      return False
    return True

# ─── Gate variants ──────────────────────────────────────────────────────────
def make_baseline_gate():
    def gate(vix_value, ivp, date_str):
        return ivp >= BLOCK_THRESHOLD
    return gate

def make_narrow_override_gate(ma_cols: list[str]):
    """Block if IVP ≥ 55 EXCEPT when low-vol bullish pullback override fires."""
    def gate(vix_value, ivp, date_str):
        if ivp < BLOCK_THRESHOLD:
            return False
        row = _row_lookup(date_str)
        if row is None:
            return True
        # If any specified MA narrow override condition holds → allow
        if any(_low_vol_bullish_pullback(row, col) for col in ma_cols):
            return False
        return True
    return gate

VARIANTS = [
    ("V0_baseline",      make_baseline_gate),
    ("P6A_narrow_MA10",  lambda: make_narrow_override_gate(["ma10"])),
    ("P6B_narrow_MA5",   lambda: make_narrow_override_gate(["ma5"])),
    ("P6C_narrow_MA5or10", lambda: make_narrow_override_gate(["ma5", "ma10"])),
]

# ─── Pre-flight: which days would each variant allow that baseline blocks? ──
print(f"\n{'='*94}")
print("  PRE-FLIGHT: override-fire day inventory (full sample)")
print(f"{'='*94}\n")

# Compute IVP_252 for full sample
def _rolling_ivp(s, w):
    arr = s.values
    out = np.full(len(arr), np.nan)
    for i in range(w, len(arr)):
        out[i] = (arr[i - w: i] < arr[i]).mean() * 100.0
    return pd.Series(out, index=s.index)

ivp_252 = _rolling_ivp(features["vix"], 252)
features["ivp_252"] = ivp_252
features = features.dropna()

for name, factory in VARIANTS:
    if name == "V0_baseline":
        continue
    gate = factory()
    override_fires = []
    for ts, row in features.iterrows():
        date_str = ts.strftime("%Y-%m-%d")
        baseline_blocks = row["ivp_252"] >= BLOCK_THRESHOLD
        variant_blocks  = gate(row["vix"], row["ivp_252"], date_str)
        if baseline_blocks and not variant_blocks:
            override_fires.append({
                "date": date_str, "spx": row["spx"], "vix": row["vix"],
                "ivp": row["ivp_252"], "ma5": row["ma5"], "ma10": row["ma10"],
                "ma50": row["ma50"], "spx_5d_ret": row["spx_5d_return"] * 100,
            })
    df_fires = pd.DataFrame(override_fires)
    print(f"  {name}: {len(df_fires)} override-fire days (vs baseline)")
    if len(df_fires) > 0:
        df_fires["year"] = pd.to_datetime(df_fires["date"]).dt.year
        by_year = df_fires.groupby("year").size().to_dict()
        years_summary = " ".join(f"{y}:{n}" for y, n in sorted(by_year.items()))
        print(f"     by year: {years_summary}")

# ─── Hard check: 2026-02-25 + 2025-05-07/12 specific dates ──────────────────
print(f"\n{'='*94}")
print("  HARD CHECK: 2026-02-25 (must remain blocked) + 2025-05-07/12 (should allow)")
print(f"{'='*94}\n")
check_dates = ["2025-05-07", "2025-05-08", "2025-05-12", "2025-05-13",
               "2026-02-24", "2026-02-25", "2026-02-26"]
for dt in check_dates:
    ts = pd.Timestamp(dt)
    if ts not in features.index:
        print(f"  {dt}: not in features (likely non-trading day)")
        continue
    row = features.loc[ts]
    spx_v = row["spx"]; vix_v = row["vix"]; ivp = row["ivp_252"]
    ma5 = row["ma5"]; ma10 = row["ma10"]; ma50 = row["ma50"]
    ret5d = row["spx_5d_return"] * 100
    cond_vix      = vix_v < VIX_LOW_MAX
    cond_bullish  = spx_v > ma50
    cond_ma10_dip = (spx_v >= ma10 * MA_LOWER_PCT) and (spx_v <= ma10 * MA_UPPER_PCT)
    cond_ma5_dip  = (spx_v >= ma5  * MA_LOWER_PCT) and (spx_v <= ma5  * MA_UPPER_PCT)
    cond_5d_ret   = ret5d > RETURN_5D_MIN * 100
    bl_block = ivp >= BLOCK_THRESHOLD
    p6a_allow = bl_block and cond_vix and cond_bullish and cond_ma10_dip and cond_5d_ret
    p6b_allow = bl_block and cond_vix and cond_bullish and cond_ma5_dip  and cond_5d_ret
    p6c_allow = p6a_allow or p6b_allow
    print(f"  {dt}: SPX={spx_v:.0f} VIX={vix_v:.1f} IVP={ivp:.1f}  "
          f"5dRet={ret5d:+.1f}%  baseline_blocks={bl_block}")
    print(f"     conditions: VIX<20={cond_vix}  >MA50={cond_bullish}  "
          f"MA10_dip={cond_ma10_dip}  MA5_dip={cond_ma5_dip}  5dRet>-2%={cond_5d_ret}")
    print(f"     P6A allow={p6a_allow}  P6B allow={p6b_allow}  P6C allow={p6c_allow}")

# ─── Engine backtest ────────────────────────────────────────────────────────
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
                "Q068 Phase 6 narrow override blocks BPS NNB",
                vix, iv, trend, macro_warn=not trend.above_200,
                canonical_strategy=BPS.value, params=params,
            )
        return rec
    return patched

orig_select = sel.select_strategy
orig_engine_select = engine_mod.select_strategy
orig_upper = sel.BPS_NNB_IVP_UPPER
sel.BPS_NNB_IVP_UPPER = 999

print(f"\n{'='*94}")
print(f"  ENGINE BACKTEST")
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
def _stats(bt, start=None, end=None):
    def in_range(t):
        if start and t.entry_date < start: return False
        if end and t.entry_date > end: return False
        return True
    bps = [t for t in bt.trades if t.strategy.value == "Bull Put Spread" and in_range(t)]
    all_trades = [t for t in bt.trades if in_range(t)]
    pnls = [t.exit_pnl for t in bps]
    return {
        "bps_n":     len(bps),
        "wr_%":      round(sum(1 for p in pnls if p > 0)/max(len(bps),1)*100, 1),
        "total":     int(sum(pnls)),
        "avg":       int(sum(pnls)/max(len(bps),1)),
        "worst":     int(min(pnls, default=0)),
        "all_total": int(sum(t.exit_pnl for t in all_trades)),
    }

# ─── Full sample + OOS + recent windows ────────────────────────────────────
print(f"\n{'='*94}")
print("  FULL SAMPLE 2007-2026")
print(f"{'='*94}\n")
for name, _ in VARIANTS:
    s = _stats(bt_results[name])
    print(f"  {name:<22}: n={s['bps_n']:>3}  WR={s['wr_%']:>5.1f}%  "
          f"avg=${s['avg']:>+5,d}  total=${s['total']:>+7,d}  "
          f"worst=${s['worst']:>+6,d}  all_total=${s['all_total']:>+8,d}")

print(f"\n{'='*94}")
print("  OOS (Test 2018-01-01 → 2026-05-10)")
print(f"{'='*94}\n")
for name, _ in VARIANTS:
    s = _stats(bt_results[name], start="2018-01-01")
    print(f"  {name:<22}: n={s['bps_n']:>3}  WR={s['wr_%']:>5.1f}%  "
          f"avg=${s['avg']:>+5,d}  total=${s['total']:>+7,d}  "
          f"worst=${s['worst']:>+6,d}  all_total=${s['all_total']:>+8,d}")

print(f"\n{'='*94}")
print("  RECENT WINDOWS")
print(f"{'='*94}\n")
for label, sd in [("last 5y", "2021-01-01"),
                  ("last 3y", "2023-01-01"),
                  ("last 2y", "2024-01-01"),
                  ("last 1y", "2025-05-11")]:
    print(f"  {label}:")
    for name, _ in VARIANTS:
        s = _stats(bt_results[name], start=sd)
        print(f"    {name:<22}: n={s['bps_n']:>3}  WR={s['wr_%']:>5.1f}%  "
              f"total=${s['total']:>+7,d}  worst=${s['worst']:>+6,d}")

# ─── Check whether 2026-02-25 made it into trades ──────────────────────────
print(f"\n{'='*94}")
print("  TRADE-LEVEL 2026-02-25 CHECK")
print(f"{'='*94}\n")
for name, _ in VARIANTS:
    bps = [t for t in bt_results[name].trades if t.strategy.value == "Bull Put Spread"]
    near_225 = [t for t in bps if "2026-02" in t.entry_date]
    print(f"  {name}: BPS entries in 2026-02:")
    for t in near_225:
        print(f"    entry={t.entry_date} exit={t.exit_date}  PnL=${t.exit_pnl:+,.0f}")
    if not near_225:
        print(f"    none")

# ─── Decision table ────────────────────────────────────────────────────────
print(f"\n{'='*94}")
print(f"  DECISION TABLE (vs V0 baseline)")
print(f"{'='*94}\n")

bl_full   = _stats(bt_results["V0_baseline"])
bl_oos    = _stats(bt_results["V0_baseline"], start="2018-01-01")
bl_recent = _stats(bt_results["V0_baseline"], start="2024-01-01")
print(f"  V0 baseline (full): n={bl_full['bps_n']} total=${bl_full['total']:+,d} "
      f"worst=${bl_full['worst']:+,d}  ann/yr=${int(bl_full['all_total']/FULL_YEARS):+,d}\n")

for name, _ in VARIANTS:
    if name == "V0_baseline":
        continue
    sf = _stats(bt_results[name])
    so = _stats(bt_results[name], start="2018-01-01")
    sr = _stats(bt_results[name], start="2024-01-01")
    ann_full = int(sf["all_total"]/FULL_YEARS)
    ann_bl   = int(bl_full["all_total"]/FULL_YEARS)
    d_full   = sf["total"] - bl_full["total"]
    d_oos    = so["total"] - bl_oos["total"]
    d_recent = sr["total"] - bl_recent["total"]
    d_worst  = sf["worst"] - bl_full["worst"]
    d_ann    = ann_full - ann_bl
    full_ok  = sf["total"] > bl_full["total"] - 14000  # ~$750/yr × 19yr
    oos_ok   = so["total"] > bl_oos["total"]
    worst_ok = d_worst >= -2000  # tolerate small worst-trade increase
    verdict = "✅ PASS" if (full_ok and oos_ok and worst_ok) else \
              "⚠ MIXED" if (full_ok or oos_ok) else "❌ FAIL"
    print(f"  {name:<22}:")
    print(f"    Δ full   ${d_full:>+7,d}  | Δ OOS ${d_oos:>+7,d}  | Δ recent2y ${d_recent:>+6,d}")
    print(f"    Δ worst  ${d_worst:>+6,d}  | Δ ann ${d_ann:>+6,d}/yr  → {verdict}")
    print(f"    full ≥ -$14k: {'✅' if full_ok else '❌'}  "
          f"OOS > 0: {'✅' if oos_ok else '❌'}  "
          f"worst ≥ -$2k: {'✅' if worst_ok else '❌'}")

# ─── Save ──────────────────────────────────────────────────────────────────
out_csv = OUT_DIR / "q068_phase6_results.csv"
rows = []
for name, _ in VARIANTS:
    rows.append({"variant": name, **_stats(bt_results[name])})
pd.DataFrame(rows).to_csv(out_csv, index=False)
print(f"\n  Saved: {out_csv}")
print("\n[Phase 6 done]")
