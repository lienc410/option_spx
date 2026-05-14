"""Q067 Phase 2 — Test collapsed-unblock / multi-horizon / cross-window gate variants
2026-05-13

Three families of variants (per Q067 memo + 2nd Quant analysis):

  V0 Baseline       : block if IVP_252 >= 55  (current production)
  V1 Hysteresis     : block if IVP > 55; unblock only if IVP < 50 for N TD
                      (N=3 / 5 / 10)
                      — TIGHTENS unblock criterion, NOT loosens block
  V2 Multi-horizon  : block if IVP_252 >= 55 AND IVP_63 >= 50
  V3 Cross-window   : block if any of (IVP_126, IVP_252, IVP_504) >= 55
                      ("any" — most conservative)

Forbidden (per Q063 Phase 5): any variant that loosens block threshold
(e.g., IVP > 60). Those revert to rejected territory.

For each variant, two parallel measurements:
  A. Daily flip rate over the full 4871 TD VIX series (Q067-style)
  B. Engine backtest 2007-2026 — total PnL / worst BPS trade / trade count

Success criteria (proposed):
  - Historical Ann ROE: >= baseline - $750/yr (~0.5pp on $150k account)
  - Daily flip rate: < 3%  (vs baseline 7.37%)
  - Worst trade: not worse than baseline
"""

from __future__ import annotations

import os
import sys
import pickle
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
import yfinance as yf

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

# ─── Precompute rolling IVPs at multiple windows ─────────────────────────────
def _load_vix() -> pd.Series:
    """Load VIX from production cache; fall back to yfinance."""
    pkl = REPO / "data" / "market_cache" / "yahoo__VIX__max__1d.pkl"
    if pkl.exists():
        df = pickle.loads(pkl.read_bytes())
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df["Close"].dropna().sort_index()
    raw = yf.download("^VIX", start="2003-01-01", end="2026-05-14",
                      auto_adjust=False, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    s = raw["Close"].dropna().sort_index()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    return s

def _rolling_ivp(series: pd.Series, window: int) -> pd.Series:
    arr = series.values
    out = np.full(len(arr), np.nan)
    for i in range(window, len(arr)):
        out[i] = (arr[i - window : i] < arr[i]).mean() * 100.0
    return pd.Series(out, index=series.index)

print("Loading VIX + precomputing IVP windows...")
vix_series = _load_vix()
print(f"  VIX: {vix_series.index[0].date()} → {vix_series.index[-1].date()}  ({len(vix_series)} TD)")

features = pd.DataFrame({
    "vix":     vix_series,
    "ivp_63":  _rolling_ivp(vix_series, 63),
    "ivp_126": _rolling_ivp(vix_series, 126),
    "ivp_252": _rolling_ivp(vix_series, 252),
    "ivp_504": _rolling_ivp(vix_series, 504),
}).dropna()
print(f"  Features ready: {len(features)} TD after warmup ({features.index[0].date()} → "
      f"{features.index[-1].date()})")

# ─── Gate variants ─────────────────────────────────────────────────────────
BLOCK_THRESHOLD = 55.0
UNBLOCK_THRESHOLD = 50.0

def _features_lookup(date_str: str) -> dict:
    """Lookup features row by date string (yyyy-mm-dd). Falls back to nearest <= date."""
    ts = pd.Timestamp(date_str)
    if ts in features.index:
        return features.loc[ts].to_dict()
    idx = features.index[features.index <= ts]
    if len(idx) == 0:
        return {}
    return features.loc[idx[-1]].to_dict()

def make_baseline_gate():
    """V0: block if IVP_252 >= 55 (production)."""
    def gate(vix_value: float, ivp: float, date_str: str) -> bool:
        return ivp >= BLOCK_THRESHOLD
    return gate

def make_hysteresis_gate(unblock_n: int):
    """V1: block if IVP > 55; unblock only if IVP < 50 for N consecutive TD."""
    state = {"blocked": False, "days_below_50": 0, "last_date": None}
    def gate(vix_value: float, ivp: float, date_str: str) -> bool:
        # Re-init if going backward in time (e.g., parallel backtest runs)
        if state["last_date"] is not None and date_str < state["last_date"]:
            state["blocked"] = False
            state["days_below_50"] = 0
        state["last_date"] = date_str
        if state["blocked"]:
            if ivp < UNBLOCK_THRESHOLD:
                state["days_below_50"] += 1
                if state["days_below_50"] >= unblock_n:
                    state["blocked"] = False
                    state["days_below_50"] = 0
            else:
                state["days_below_50"] = 0
        else:
            if ivp >= BLOCK_THRESHOLD:
                state["blocked"] = True
                state["days_below_50"] = 0
        return state["blocked"]
    return gate

def make_multihorizon_gate():
    """V2: block if IVP_252 >= 55 AND IVP_63 >= 50."""
    def gate(vix_value: float, ivp: float, date_str: str) -> bool:
        if ivp < BLOCK_THRESHOLD:
            return False
        row = _features_lookup(date_str)
        ivp_63 = row.get("ivp_63", ivp)  # fallback: assume agreement if missing
        return ivp_63 >= UNBLOCK_THRESHOLD
    return gate

def make_crosswindow_any_gate():
    """V3: block if ANY of (IVP_126, IVP_252, IVP_504) >= 55."""
    def gate(vix_value: float, ivp: float, date_str: str) -> bool:
        row = _features_lookup(date_str)
        if not row:
            return ivp >= BLOCK_THRESHOLD
        return any(row.get(k, 0) >= BLOCK_THRESHOLD for k in ("ivp_126", "ivp_252", "ivp_504"))
    return gate

VARIANTS = [
    ("V0_baseline",        make_baseline_gate()),
    ("V1a_hyst_N3",        make_hysteresis_gate(3)),
    ("V1b_hyst_N5",        make_hysteresis_gate(5)),
    ("V1c_hyst_N10",       make_hysteresis_gate(10)),
    ("V2_multihorizon",    make_multihorizon_gate()),
    ("V3_crosswin_any",    make_crosswindow_any_gate()),
]

# ─── A. Daily-flip-rate measurement (independent of backtest engine) ────────
print(f"\n{'='*94}")
print("  A. DAILY FLIP-RATE MEASUREMENT (4871 TD VIX series)")
print(f"{'='*94}\n")

flip_results = []
for name, gate_fn in VARIANTS:
    # Reset hysteresis state by recreating gate
    if name.startswith("V1"):
        n = int(name.split("N")[1])
        gate_fn = make_hysteresis_gate(n)

    blocks = []
    for idx, row in features.iterrows():
        date_str = idx.strftime("%Y-%m-%d")
        blocks.append(int(gate_fn(row["vix"], row["ivp_252"], date_str)))
    blocks = np.array(blocks)

    n_total = len(blocks)
    n_block = int(blocks.sum())
    flips = np.abs(np.diff(blocks))
    n_flips = int(flips.sum())
    flip_rate = n_flips / n_total * 100

    # Tight flip-flop (reverse within 5 TD)
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
        "flip_flop": flip_flop,
    })

df_flip = pd.DataFrame(flip_results)
print(df_flip.to_string(index=False))

# ─── B. Engine backtest for each variant ────────────────────────────────────
print(f"\n{'='*94}")
print(f"  B. ENGINE BACKTEST (2007-01-01 → 2026-05-10, account=${ACCOUNT:,.0f})")
print(f"{'='*94}\n")

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
                "Phase 2 variant blocks BPS NNB",
                vix, iv, trend, macro_warn=not trend.above_200,
                canonical_strategy=BPS.value, params=params,
            )
        return rec
    return patched

orig_select = sel.select_strategy
orig_engine_select = engine_mod.select_strategy
orig_upper = sel.BPS_NNB_IVP_UPPER
sel.BPS_NNB_IVP_UPPER = 999  # disable internal gate; all gating goes through patcher

bt_results = {}
for name, _ in VARIANTS:
    print(f"  ▸ Running {name}...")
    # Recreate gate to reset hysteresis state for each fresh run
    if name == "V0_baseline":
        gate = make_baseline_gate()
    elif name.startswith("V1"):
        n = int(name.split("N")[1])
        gate = make_hysteresis_gate(n)
    elif name == "V2_multihorizon":
        gate = make_multihorizon_gate()
    elif name == "V3_crosswin_any":
        gate = make_crosswindow_any_gate()
    sel.select_strategy = _make_patcher(gate, orig_select)
    engine_mod.select_strategy = sel.select_strategy
    try:
        bt = run_backtest(start_date=START, end_date=END,
                          account_size=ACCOUNT, verbose=False)
    finally:
        sel.select_strategy = orig_select
        engine_mod.select_strategy = orig_engine_select
    bt_results[name] = bt

sel.BPS_NNB_IVP_UPPER = orig_upper

# ─── Compute stats ──────────────────────────────────────────────────────────
def _stats(bt):
    bps = [t for t in bt.trades if t.strategy.value == "Bull Put Spread"]
    pnls_bps = [t.exit_pnl for t in bps]
    all_pnls = [t.exit_pnl for t in bt.trades]
    return {
        "bps_n":     len(bps),
        "bps_wr":    round(sum(1 for p in pnls_bps if p > 0)/max(len(bps),1)*100, 1),
        "bps_total": int(sum(pnls_bps)),
        "bps_avg":   int(sum(pnls_bps)/max(len(bps),1)),
        "bps_worst": int(min(pnls_bps, default=0)),
        "all_total": int(sum(all_pnls)),
        "all_ann":   int(sum(all_pnls)/FULL_YEARS),
    }

bt_stats = {name: _stats(bt) for name, bt in bt_results.items()}
df_bt = pd.DataFrame([{"variant": k, **v} for k, v in bt_stats.items()])
print()
print(df_bt.to_string(index=False))

# ─── C. Decision table (vs baseline) ────────────────────────────────────────
print(f"\n{'='*94}")
print(f"  C. DECISION TABLE (vs V0 baseline)")
print(f"{'='*94}\n")

bl = bt_stats["V0_baseline"]
bl_flip = next(r for r in flip_results if r["variant"] == "V0_baseline")
print(f"  Baseline V0: BPS_n={bl['bps_n']}  WR={bl['bps_wr']}%  "
      f"all_ann=${bl['all_ann']:+,d}  worst=${bl['bps_worst']:+,d}  "
      f"flip={bl_flip['flip_rate_%']}%\n")

for name, _ in VARIANTS:
    if name == "V0_baseline":
        continue
    s = bt_stats[name]
    f = next(r for r in flip_results if r["variant"] == name)
    delta_ann = s["all_ann"] - bl["all_ann"]
    delta_worst = s["bps_worst"] - bl["bps_worst"]
    delta_flip = f["flip_rate_%"] - bl_flip["flip_rate_%"]
    delta_n = s["bps_n"] - bl["bps_n"]
    pnl_pass = delta_ann >= -750
    flip_pass = f["flip_rate_%"] < 3.0
    worst_pass = delta_worst >= 0
    overall = "✅ PASS" if (pnl_pass and flip_pass and worst_pass) else \
              "⚠ PARTIAL" if (pnl_pass and (flip_pass or worst_pass)) else "❌ FAIL"
    print(f"  {name:<22}: Δn={delta_n:>+4}  Δann=${delta_ann:>+7,d}/yr  "
          f"Δworst=${delta_worst:>+7,d}  flip_rate={f['flip_rate_%']}% ({delta_flip:+.2f}pp)  "
          f"→ {overall}")
    print(f"    PnL≥-$750/yr: {'✅' if pnl_pass else '❌'}  "
          f"flip<3%: {'✅' if flip_pass else '❌'}  "
          f"worst≥baseline: {'✅' if worst_pass else '❌'}")

# ─── Save outputs ───────────────────────────────────────────────────────────
df_flip.to_csv(OUT_DIR / "q067_phase2_flip_rates.csv", index=False)
df_bt.to_csv(OUT_DIR / "q067_phase2_backtest_stats.csv", index=False)
print(f"\n  Saved: q067_phase2_flip_rates.csv + q067_phase2_backtest_stats.csv")
print("\n[Phase 2 done]")
