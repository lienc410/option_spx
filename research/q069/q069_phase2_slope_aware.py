"""Q069 Phase 2 — Slope-aware IVP Gate
2026-05-13

Per 2nd Quant input (2026-05-13): Phase 1 smoothing failed because
smoothing LAGS risk signals. Slope-aware approach is a genuinely
different hypothesis: don't smooth, but distinguish "high & rising"
(real risk) from "high but falling" (dissipating noise).

Hypothesis:
  block if IVP > 55 AND direction == "rising"
  allow if IVP > 55 BUT direction == "falling"

This may avoid Phase 1's lag failure mode because it doesn't average
across time — it reads the current direction.

Variants:
  V0  raw IVP_252 ≥ 55 (production baseline)
  M1  IVP > 55 AND IVP_3d_change > 0           (level + slope)
  M2  IVP_3d_avg > 55 AND avg_3d_change > 0    (smoothed level + smoothed slope)
  M3  IVP > 55 AND VIX_5d_change > +1.0        (level + VIX absolute slope)
  M4  IVP > 55 AND VIX_5d_change > +1.5        (level + larger VIX slope)

Adopting 2nd Quant's three-tier verdict matrix:
  Strong pass: Full + OOS + Recent all improve, worst not worse, 2/25 blocked
  Soft pass:   Full flat, OOS flat/+, Recent improves, worst not worse, 2/25 blocked
  Fail:        Full worse OR worst worse OR 2/25 allowed

Hard guardrail:
  2026-02-25 (Q063 known bad trade entry day) MUST remain blocked.
"""
from __future__ import annotations

import os
import sys
import pickle
from pathlib import Path

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

# ─── Load VIX + compute features ───────────────────────────────────────────
print("Loading VIX + precomputing features...")
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

features = pd.DataFrame({"vix": vix_series})
features["ivp"]            = _rolling_ivp(vix_series, 252)
features["ivp_3d_avg"]     = features["ivp"].rolling(3).mean()
# 3d change of raw IVP (today - 3d ago)
features["ivp_3d_change"]  = features["ivp"] - features["ivp"].shift(3)
features["ivp_3d_avg_change"] = features["ivp_3d_avg"] - features["ivp_3d_avg"].shift(3)
features["vix_5d_change"]  = features["vix"] - features["vix"].shift(5)
features = features.dropna()
print(f"  Features ready: {len(features)} TD ({features.index[0].date()} → {features.index[-1].date()})")

# ─── Gate definitions ──────────────────────────────────────────────────────
def _lookup(date_str):
    ts = pd.Timestamp(date_str)
    if ts in features.index:
        return features.loc[ts].to_dict()
    idx = features.index[features.index <= ts]
    if len(idx) == 0:
        return None
    return features.loc[idx[-1]].to_dict()

def make_baseline_gate():
    def gate(vix_value, ivp, date_str):
        return ivp >= BLOCK_THRESHOLD
    return gate

def make_M1():
    """Block if IVP > 55 AND IVP rising (3d change > 0)."""
    def gate(vix_value, ivp, date_str):
        if ivp < BLOCK_THRESHOLD:
            return False
        row = _lookup(date_str)
        if row is None: return True
        return row["ivp_3d_change"] > 0
    return gate

def make_M2():
    """Block if 3d_avg > 55 AND 3d_avg rising."""
    def gate(vix_value, ivp, date_str):
        row = _lookup(date_str)
        if row is None: return ivp >= BLOCK_THRESHOLD
        if row["ivp_3d_avg"] < BLOCK_THRESHOLD: return False
        return row["ivp_3d_avg_change"] > 0
    return gate

def make_M3():
    """Block if IVP > 55 AND VIX 5d change > +1.0."""
    def gate(vix_value, ivp, date_str):
        if ivp < BLOCK_THRESHOLD: return False
        row = _lookup(date_str)
        if row is None: return True
        return row["vix_5d_change"] > 1.0
    return gate

def make_M4():
    """Block if IVP > 55 AND VIX 5d change > +1.5."""
    def gate(vix_value, ivp, date_str):
        if ivp < BLOCK_THRESHOLD: return False
        row = _lookup(date_str)
        if row is None: return True
        return row["vix_5d_change"] > 1.5
    return gate

VARIANTS = [
    ("V0_baseline",      make_baseline_gate),
    ("M1_lvl_slope",     make_M1),
    ("M2_avg_slope",     make_M2),
    ("M3_lvl_vix5d_1.0", make_M3),
    ("M4_lvl_vix5d_1.5", make_M4),
]

# ─── A. Daily flip-rate measurement ────────────────────────────────────────
print(f"\n{'='*94}")
print(f"  A. DAILY FLIP-RATE on slope-aware variants (2007-2026)")
print(f"{'='*94}\n")

f_2007 = features[features.index >= pd.Timestamp("2007-01-01")]
flip_results = []
for name, factory in VARIANTS:
    gate = factory()
    blocks = []
    for ts, row in f_2007.iterrows():
        date_str = ts.strftime("%Y-%m-%d")
        blocks.append(int(gate(row["vix"], row["ivp"], date_str)))
    blocks = np.array(blocks)
    n_total = len(blocks)
    n_block = int(blocks.sum())
    flips = np.abs(np.diff(blocks))
    n_flips = int(flips.sum())
    flip_idx = np.where(flips == 1)[0]
    flip_flop = 0
    for i, j in enumerate(flip_idx[:-1]):
        for k in flip_idx[i+1:]:
            if k - j > 5: break
            if blocks[j+1] != blocks[k+1]:
                flip_flop += 1
                break
    flip_results.append({
        "variant": name, "block_days": n_block,
        "block_%": round(n_block/n_total*100, 1),
        "flips": n_flips,
        "flip_rate_%": round(n_flips/n_total*100, 2),
        "flip_flop_5TD": flip_flop,
    })

df_flip = pd.DataFrame(flip_results)
print(df_flip.to_string(index=False))

# ─── B. Hard check: 2026-02-25 and 2026-05-04 / 2026-05-12 ────────────────
print(f"\n{'='*94}")
print(f"  HARD CHECK: 2026-02-25 MUST remain blocked; 2026-05-04/12 reported")
print(f"{'='*94}\n")

hard_dates = ["2026-02-24", "2026-02-25", "2026-02-26",
              "2026-05-04", "2026-05-07", "2026-05-12", "2026-05-13"]

print(f"{'Date':<12} {'VIX':>5} {'IVP':>5} {'IVP_3d':>6} {'IVP_3dΔ':>7} {'VIX_5dΔ':>7}  ", end="")
print("  ".join(f"{n:<14}" for n, _ in VARIANTS))
for dt in hard_dates:
    ts = pd.Timestamp(dt)
    if ts not in features.index:
        print(f"  {dt}: non-trading")
        continue
    row = features.loc[ts]
    print(f"{dt:<12} {row['vix']:>5.1f} {row['ivp']:>5.1f} {row['ivp_3d_avg']:>6.1f} "
          f"{row['ivp_3d_change']:>+7.2f} {row['vix_5d_change']:>+7.2f}  ", end="")
    for name, factory in VARIANTS:
        gate = factory()
        blocked = gate(row["vix"], row["ivp"], dt)
        print(f"{'BLK' if blocked else 'OK':<14}", end="  ")
    print()

# ─── C. Engine backtest ────────────────────────────────────────────────────
def _make_patcher(gate_fn, base_select):
    BPS = StrategyName.BULL_PUT_SPREAD
    def patched(vix, iv, trend, params=DEFAULT_PARAMS):
        rec = base_select(vix, iv, trend, params)
        if rec.strategy != BPS: return rec
        from strategy.selector import _effective_iv_signal, _reduce_wait
        if not (vix.regime == Regime.NORMAL
                and _effective_iv_signal(iv) == IVSignal.NEUTRAL
                and trend.signal.value == "BULLISH"):
            return rec
        block = gate_fn(vix.vix, iv.iv_percentile, vix.date)
        if block:
            return _reduce_wait("Q069 P2 slope-aware blocks",
                                vix, iv, trend, macro_warn=not trend.above_200,
                                canonical_strategy=BPS.value, params=params)
        return rec
    return patched

orig_select = sel.select_strategy
orig_engine_select = engine_mod.select_strategy
orig_upper = sel.BPS_NNB_IVP_UPPER
sel.BPS_NNB_IVP_UPPER = 999

print(f"\n{'='*94}")
print(f"  C. ENGINE BACKTEST (2007-2026)")
print(f"{'='*94}\n")
bt_results = {}
for name, factory in VARIANTS:
    print(f"  ▸ {name}...")
    sel.select_strategy = _make_patcher(factory(), orig_select)
    engine_mod.select_strategy = sel.select_strategy
    try:
        bt = run_backtest(start_date=START, end_date=END, account_size=ACCOUNT, verbose=False)
    finally:
        sel.select_strategy = orig_select
        engine_mod.select_strategy = orig_engine_select
    bt_results[name] = bt

sel.BPS_NNB_IVP_UPPER = orig_upper

def _stats(bt, start=None):
    bps = [t for t in bt.trades if t.strategy.value == "Bull Put Spread"
           and (start is None or t.entry_date >= start)]
    pnls = [t.exit_pnl for t in bps]
    all_trades = [t for t in bt.trades if (start is None or t.entry_date >= start)]
    return {
        "bps_n": len(bps),
        "wr_%": round(sum(1 for p in pnls if p > 0)/max(len(bps),1)*100, 1),
        "total": int(sum(pnls)),
        "avg": int(sum(pnls)/max(len(bps),1)),
        "worst": int(min(pnls, default=0)),
        "all_total": int(sum(t.exit_pnl for t in all_trades)),
    }

# ─── Results ────────────────────────────────────────────────────────────────
print(f"\n{'='*94}")
print(f"  RESULTS — FULL 19yr / OOS / Recent 2y")
print(f"{'='*94}\n")

print(f"{'Variant':<18} {'BPS_n':>6} {'WR%':>6} {'Total':>9} {'Worst':>9} {'all_ann':>9}  OOS(2018+)  Recent2y")
print("-" * 110)
rows = []
for name, _ in VARIANTS:
    sf = _stats(bt_results[name])
    so = _stats(bt_results[name], start="2018-01-01")
    sr = _stats(bt_results[name], start="2024-01-01")
    ann = int(sf["all_total"]/FULL_YEARS)
    print(f"{name:<18} {sf['bps_n']:>6} {sf['wr_%']:>5.1f}% "
          f"${sf['total']:>+7,d} ${sf['worst']:>+7,d} ${ann:>+7,d}  "
          f"${so['total']:>+7,d}    ${sr['total']:>+7,d}")
    rows.append({"variant": name, **sf, "all_ann": ann,
                 "oos_total": so["total"], "oos_worst": so["worst"],
                 "recent2y_total": sr["total"], "recent2y_worst": sr["worst"]})

# ─── Check 2026-02 trades in each variant ──────────────────────────────────
print(f"\n{'='*94}")
print(f"  TRADE-LEVEL 2026-02 CHECK (Q063 known bad trade was around 2026-02-25)")
print(f"{'='*94}\n")
for name, _ in VARIANTS:
    bps = [t for t in bt_results[name].trades if t.strategy.value == "Bull Put Spread"
           and "2026-02" in t.entry_date]
    if not bps:
        print(f"  {name}: no BPS entries in 2026-02 ✅")
    else:
        for t in bps:
            print(f"  {name}: entry={t.entry_date} exit={t.exit_date} PnL=${t.exit_pnl:+,.0f}")

# ─── Decision matrix per 2nd Quant 3-tier ──────────────────────────────────
print(f"\n{'='*94}")
print(f"  DECISION MATRIX (per 2nd Quant 3-tier: Strong pass / Soft pass / Fail)")
print(f"{'='*94}\n")

bl = next(r for r in rows if r["variant"] == "V0_baseline")
print(f"  V0 baseline: full=${bl['total']:+,d}  worst=${bl['worst']:+,d}  "
      f"OOS=${bl['oos_total']:+,d}  recent2y=${bl['recent2y_total']:+,d}\n")

for r in rows:
    if r["variant"] == "V0_baseline": continue
    d_full   = r["total"] - bl["total"]
    d_oos    = r["oos_total"] - bl["oos_total"]
    d_recent = r["recent2y_total"] - bl["recent2y_total"]
    d_worst  = r["worst"] - bl["worst"]

    # Check trade-level 2026-02-25
    bps_feb = [t for t in bt_results[r["variant"]].trades
               if t.strategy.value == "Bull Put Spread"
               and "2026-02" in t.entry_date]
    has_225_trade = any("2026-02-25" in t.entry_date for t in bps_feb)

    # 3-tier verdict
    full_improves = d_full >= 0
    full_flat     = abs(d_full) < 14000  # tolerance ~$750/yr × 19yr
    oos_improves  = d_oos >= 0
    recent_improves = d_recent >= 0
    worst_ok      = d_worst >= -1000  # 2nd Quant: not worse by more than ~$1k
    block_225     = not has_225_trade

    if not block_225 or not worst_ok or (d_full < -14000):
        verdict = "❌ FAIL"
        reason = []
        if not block_225: reason.append("2/25 allowed")
        if not worst_ok: reason.append("worst worse > $1k")
        if d_full < -14000: reason.append("full worse")
        verdict_detail = " / ".join(reason)
    elif full_improves and oos_improves and recent_improves and worst_ok and block_225:
        verdict = "✅ STRONG PASS"
        verdict_detail = "all improve, worst preserved, 2/25 blocked"
    elif full_flat and (oos_improves or abs(d_oos) < 5000) and recent_improves and worst_ok and block_225:
        verdict = "🟢 SOFT PASS"
        verdict_detail = "full flat, OOS ≈ or +, recent +, worst preserved, 2/25 blocked"
    else:
        verdict = "⚠ MIXED"
        verdict_detail = f"partial: full {'+' if full_improves else 'flat' if full_flat else '-'}, OOS {'+' if oos_improves else '-'}, recent {'+' if recent_improves else '-'}"

    print(f"  {r['variant']:<18}: full ${d_full:>+7,d}  OOS ${d_oos:>+7,d}  "
          f"recent2y ${d_recent:>+7,d}  worst ${d_worst:>+6,d}  "
          f"2/25_blocked={block_225}")
    print(f"    {verdict} — {verdict_detail}")
    print()

# ─── Save ──────────────────────────────────────────────────────────────────
pd.DataFrame(rows).to_csv(OUT_DIR / "q069_phase2_slope_aware_bt.csv", index=False)
df_flip.to_csv(OUT_DIR / "q069_phase2_slope_aware_flip.csv", index=False)
print(f"  Saved: q069_phase2_slope_aware_bt.csv + q069_phase2_slope_aware_flip.csv")
print("\n[Phase 2 done]")
