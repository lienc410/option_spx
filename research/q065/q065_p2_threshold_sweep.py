"""
Q065 P2 — Threshold variant sweep + trap-rate analysis
2026-05-12

For 4 candidate thresholds (baseline 40, 42, 45, peak×0.85), compute:
  • Extra aftermath days enabled (relative to baseline 40)
  • Trap rate: of extra-enabled days, how many have VIX rebound ≥ 45 within
    next 5 trading days (proxy for "entered then immediately re-tailed")
  • Merged windows: total independent aftermath windows under each variant
  • Per-event impact: which historical events (2008/2020/2025...) are affected
"""

import os
import sys
import pandas as pd
import numpy as np
import yfinance as yf

# ── Parameters (mirror selector.py baseline) ───────────────────────────────
AFTERMATH_PEAK_VIX_10D_MIN = 28.0
AFTERMATH_OFF_PEAK_PCT     = 0.10
LOOKBACK_DAYS              = 10

# Sweep variants: name, extreme_threshold_func(vix, peak_10d) → bool (True = blocked)
VARIANTS = [
    ("baseline_40",        lambda v, peak: v >= 40.0),
    ("loosen_42",          lambda v, peak: v >= 42.0),
    ("loosen_45",          lambda v, peak: v >= 45.0),
    ("peak_x_0.85",        lambda v, peak: v >= peak * 0.85),  # block only if v > 15% above floor
]

# Trap definition: after a newly-enabled aftermath day, does VIX rebound to
# RE_TAIL_THRESHOLD within REBOUND_LOOKAHEAD trading days?
RE_TAIL_THRESHOLD     = 45.0
REBOUND_LOOKAHEAD_TD  = 5

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Load VIX ────────────────────────────────────────────────────────────────
print("Loading VIX...")
raw = yf.download("^VIX", start="2006-01-01", end="2026-05-13",
                  auto_adjust=False, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
vix_series = raw["Close"].dropna().sort_index()
vix_series.index = pd.to_datetime(vix_series.index).tz_localize(None)
vix_series = vix_series[vix_series.index >= "2007-01-01"]
vix_arr = vix_series.values
dates   = vix_series.index.to_list()
n       = len(vix_arr)
print(f"  {len(vix_series)} trading days")

# ── Precompute peak_10d for each day ───────────────────────────────────────
peak10d = np.empty(n)
for i in range(n):
    lo = max(0, i - LOOKBACK_DAYS + 1)
    peak10d[i] = float(np.max(vix_arr[lo : i + 1]))

# ── For each variant, compute is_aftermath flags and merge into windows ───
def compute_flags(extreme_fn):
    flags = np.zeros(n, dtype=bool)
    for i in range(n):
        v = float(vix_arr[i]); peak = peak10d[i]
        if peak < AFTERMATH_PEAK_VIX_10D_MIN:
            continue
        if v > peak * (1.0 - AFTERMATH_OFF_PEAK_PCT):
            continue
        if extreme_fn(v, peak):
            continue
        flags[i] = True
    return flags

def windows_from_flags(flags):
    """Continuous True runs → windows."""
    wins = []
    in_w = False
    s = None
    for i in range(n):
        if flags[i] and not in_w:
            in_w = True; s = i
        elif not flags[i] and in_w:
            wins.append((s, i - 1))
            in_w = False
    if in_w:
        wins.append((s, n - 1))
    return wins

# ── Trap rate: was day i followed by VIX rebound to >= RE_TAIL within 5 TD? ─
def is_trap(i):
    hi = min(n, i + 1 + REBOUND_LOOKAHEAD_TD)
    return bool(np.any(vix_arr[i + 1 : hi] >= RE_TAIL_THRESHOLD))

# ── Sweep ──────────────────────────────────────────────────────────────────
print(f"\n{'='*92}")
print(f"  Threshold variant sweep")
print(f"  Trap = day i followed by VIX ≥ {RE_TAIL_THRESHOLD} within {REBOUND_LOOKAHEAD_TD} TD")
print(f"{'='*92}\n")

baseline_flags = compute_flags(VARIANTS[0][1])
baseline_days  = baseline_flags.sum()

sweep_rows = []
for name, fn in VARIANTS:
    flags = compute_flags(fn)
    n_days = int(flags.sum())
    wins   = windows_from_flags(flags)
    n_wins = len(wins)

    # Days unique to this variant (vs baseline)
    new_days_idx = np.where(flags & ~baseline_flags)[0]
    n_new = len(new_days_idx)

    # Trap classification of new days
    if n_new > 0:
        traps = np.array([is_trap(i) for i in new_days_idx])
        n_trap = int(traps.sum())
        trap_rate = n_trap / n_new * 100
    else:
        n_trap = 0
        trap_rate = 0.0

    # 1-day windows under this variant
    n_1day = sum(1 for s, e in wins if e == s)

    sweep_rows.append({
        "variant": name,
        "aftermath_days": n_days,
        "delta_vs_baseline_days": n_days - baseline_days,
        "n_windows": n_wins,
        "n_1day_windows": n_1day,
        "new_days_vs_baseline": n_new,
        "new_days_traps_5TD_45": n_trap,
        "trap_rate_%": round(trap_rate, 1),
    })

df_sweep = pd.DataFrame(sweep_rows)
print(df_sweep.to_string(index=False))

# ── Show per-event detail for the "new days" enabled by loosening ──────────
print(f"\n{'='*92}")
print(f"  Per-event detail: which historical events do the new days belong to?")
print(f"{'='*92}\n")

for name, fn in VARIANTS[1:]:  # skip baseline
    flags = compute_flags(fn)
    new_days_idx = np.where(flags & ~baseline_flags)[0]
    if len(new_days_idx) == 0:
        continue
    new_dates = [dates[i] for i in new_days_idx]
    df_new = pd.DataFrame({
        "date": new_dates,
        "vix":  [vix_arr[i] for i in new_days_idx],
        "peak_10d": [peak10d[i] for i in new_days_idx],
        "off_peak_%": [(1 - vix_arr[i]/peak10d[i]) * 100 for i in new_days_idx],
        "is_trap_5TD_45": [is_trap(i) for i in new_days_idx],
    })
    df_new["year"] = pd.to_datetime(df_new["date"]).dt.year
    by_year = df_new.groupby("year").agg(
        n_days=("date", "count"),
        n_trap=("is_trap_5TD_45", "sum"),
        vix_max=("vix", "max"),
        vix_median=("vix", "median"),
    )
    print(f"  ── {name}: {len(new_dates)} new days ──")
    print(by_year.to_string())

    # Save per-variant detail CSV
    out = os.path.join(OUT_DIR, f"q065_p2_new_days_{name}.csv")
    df_new["date"] = pd.to_datetime(df_new["date"]).dt.strftime("%Y-%m-%d")
    df_new.to_csv(out, index=False)
    print(f"  Saved: {out}\n")

# ── Decision table ─────────────────────────────────────────────────────────
print(f"{'='*92}")
print(f"  DECISION TABLE")
print(f"{'='*92}\n")
print("  Criterion: trap_rate < 20% (acceptable false-positive rate for SPEC-064 entry)")
print("             AND not a wholesale entry-rule change\n")
for r in sweep_rows:
    if r["variant"] == "baseline_40":
        continue
    rec = "✅ candidate for P3 backtest" if r["trap_rate_%"] < 20 else "❌ trap rate too high"
    print(f"  {r['variant']:<14}: trap_rate={r['trap_rate_%']}%, "
          f"+{r['delta_vs_baseline_days']} days, "
          f"{r['n_1day_windows']} 1-day windows (vs baseline) → {rec}")

# ── Save sweep CSV ─────────────────────────────────────────────────────────
out_sweep = os.path.join(OUT_DIR, "q065_p2_threshold_sweep.csv")
df_sweep.to_csv(out_sweep, index=False)
print(f"\n  Saved: {out_sweep}")
print("\n[P2 done]")
