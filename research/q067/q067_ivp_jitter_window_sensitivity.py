"""
Q067 — IVP > 55 Gate: Threshold Jitter + Window Length Sensitivity
2026-05-13

PM Concerns (from 2nd Quant analysis):
  1. IVP 55 is an empirical rank-jump artifact, not an economic cliff.
     Small absolute VIX moves in the 15-18 cluster region can cause
     large IVP jumps → potential flip-flop near 55.
  2. IVP is window-length sensitive (6mo / 1yr / 2yr give different values
     from the same VIX series).

Goal: quantify how often the IVP > 55 decision in production would actually
flip in live operation, and how stable the gate is across window choices.

Measures:
  A. Jitter zone density: % of trading days where IVP is in [50, 65]
  B. Cross-threshold flip rate (within ±2 TD, ±5 TD)
  C. Window sensitivity: compare IVP_252 (production) vs IVP_126 (6mo)
     vs IVP_504 (2yr) — pairwise disagreement on the 55 threshold
  D. Window-induced gate flip: how often production (252d) and alternative
     windows disagree on block / allow

Production lookback: LOOKBACK_DAYS = 252 (signals/iv_rank.py:34)
"""
import os
import sys
import numpy as np
import pandas as pd
import yfinance as yf

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Production parameters ──────────────────────────────────────────────────
GATE_THRESHOLD = 55.0
PROD_WINDOW    = 252
ALT_WINDOWS    = [126, 252, 504]   # 6mo, 1yr (prod), 2yr
JITTER_BAND    = (50.0, 65.0)
FLIP_LOOKAHEAD = [2, 5]   # ± TD around threshold crossings

# ── Load VIX ────────────────────────────────────────────────────────────────
print("Loading VIX history...")
raw = yf.download("^VIX", start="2003-01-01", end="2026-05-14",
                  auto_adjust=False, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
vix = raw["Close"].dropna().sort_index()
vix.index = pd.to_datetime(vix.index).tz_localize(None)
print(f"  VIX range: {vix.index[0].date()} → {vix.index[-1].date()}  ({len(vix)} TD)")

# ── Compute IVP for each window ─────────────────────────────────────────────
def ivp_rolling(series: pd.Series, window: int) -> pd.Series:
    """Production-compatible IVP: % of historical window strictly below today's VIX."""
    arr = series.values
    out = np.full(len(arr), np.nan)
    for i in range(window, len(arr)):
        wnd = arr[i - window : i]
        cur = arr[i]
        out[i] = (wnd < cur).mean() * 100.0
    return pd.Series(out, index=series.index)

print("Computing rolling IVP for windows 126 / 252 / 504...")
ivp_by_window = {w: ivp_rolling(vix, w) for w in ALT_WINDOWS}

# Trim to common window where all three are defined (after 504-day warmup)
max_window = max(ALT_WINDOWS)
common_idx = vix.index[max_window:]
analysis_start = pd.Timestamp("2007-01-01")
common_idx = common_idx[common_idx >= analysis_start]
n_total = len(common_idx)
print(f"  Analysis window: {common_idx[0].date()} → {common_idx[-1].date()}  ({n_total} TD)")

df = pd.DataFrame({
    "vix":      vix.loc[common_idx].values,
    "ivp_126":  ivp_by_window[126].loc[common_idx].values,
    "ivp_252":  ivp_by_window[252].loc[common_idx].values,
    "ivp_504":  ivp_by_window[504].loc[common_idx].values,
}, index=common_idx)

# ── A. Jitter zone density ─────────────────────────────────────────────────
print(f"\n{'='*92}")
print(f"  A. JITTER ZONE DENSITY — IVP in [{JITTER_BAND[0]}, {JITTER_BAND[1]}]")
print(f"{'='*92}\n")
for col in ["ivp_126", "ivp_252", "ivp_504"]:
    series = df[col]
    in_band   = ((series >= JITTER_BAND[0]) & (series <= JITTER_BAND[1])).sum()
    above_55  = (series > GATE_THRESHOLD).sum()
    below_55  = (series <= GATE_THRESHOLD).sum()
    pct_band  = in_band / n_total * 100
    pct_above = above_55 / n_total * 100
    print(f"  {col:<10}: in [50,65] = {in_band:>5} TD ({pct_band:5.1f}%)  "
          f"| above 55: {above_55:>5} ({pct_above:5.1f}%)  | total: {n_total}")

# Drill: production window VIX distribution by IVP band
print(f"\n  ── Production (IVP_252) VIX distribution by IVP band ──")
bins = [(0, 50), (50, 55), (55, 60), (60, 65), (65, 70), (70, 100)]
for lo, hi in bins:
    mask = (df["ivp_252"] >= lo) & (df["ivp_252"] < hi)
    n = int(mask.sum())
    if n == 0:
        continue
    vmean = df.loc[mask, "vix"].mean()
    vmed  = df.loc[mask, "vix"].median()
    vmin  = df.loc[mask, "vix"].min()
    vmax  = df.loc[mask, "vix"].max()
    print(f"  IVP_252 [{lo:>2}, {hi:>2}): n={n:>5} | VIX  min={vmin:5.2f}  "
          f"median={vmed:5.2f}  mean={vmean:5.2f}  max={vmax:5.2f}")

# ── B. Cross-threshold flip rate (production window) ───────────────────────
print(f"\n{'='*92}")
print(f"  B. THRESHOLD FLIP RATE — production IVP_252 around 55")
print(f"{'='*92}\n")

ivp_prod = df["ivp_252"]
block    = (ivp_prod > GATE_THRESHOLD).astype(int)
# Detect daily decision changes
decision_change = block.diff().abs().fillna(0).astype(int)
n_changes = int(decision_change.sum())
print(f"  Total daily decision changes (block ↔ allow): {n_changes} / {n_total} TD "
      f"= {n_changes/n_total*100:.2f}% of days")

# Cluster flips: how many flips occur within N TD of another flip?
flip_idx = np.where(decision_change.values == 1)[0]
for ahead in FLIP_LOOKAHEAD:
    n_cluster = 0
    for j, idx in enumerate(flip_idx):
        # other flips within ±ahead TD (excluding self)
        nbr = flip_idx[(flip_idx >= idx - ahead) & (flip_idx <= idx + ahead) & (flip_idx != idx)]
        if len(nbr) > 0:
            n_cluster += 1
    pct = n_cluster / max(len(flip_idx), 1) * 100
    print(f"  Flips with another flip within ±{ahead} TD: "
          f"{n_cluster}/{len(flip_idx)} = {pct:.1f}%")

# Tight flip-flop: same-direction flip-back within 5 TD
flip_back = 0
for i, idx in enumerate(flip_idx[:-1]):
    for nxt in flip_idx[i+1:]:
        if nxt - idx > 5:
            break
        # opposite direction (e.g., block→allow then allow→block)
        if block.iloc[idx] != block.iloc[nxt]:
            flip_back += 1
            break
print(f"  Tight flip-flop (reverse within 5 TD): {flip_back}/{len(flip_idx)} "
      f"= {flip_back/max(len(flip_idx),1)*100:.1f}%")

# ── C. Window sensitivity: pairwise disagreement on gate ───────────────────
print(f"\n{'='*92}")
print(f"  C. WINDOW SENSITIVITY — pairwise gate disagreement")
print(f"{'='*92}\n")

block_by_w = {w: (df[f"ivp_{w}"] > GATE_THRESHOLD).astype(int) for w in ALT_WINDOWS}

for w1 in ALT_WINDOWS:
    for w2 in ALT_WINDOWS:
        if w1 >= w2:
            continue
        diff = (block_by_w[w1] != block_by_w[w2]).sum()
        pct  = diff / n_total * 100
        print(f"  IVP_{w1} vs IVP_{w2}: disagree on {diff:>5} TD ({pct:5.2f}%)")

# Direction of disagreement: when 126 says block but 252 says allow, etc.
print(f"\n  ── IVP_252 (prod) vs IVP_126 (6mo) direction breakdown ──")
df["prod_block"] = block_by_w[252]
df["alt6m_block"] = block_by_w[126]
both_block = ((df["prod_block"] == 1) & (df["alt6m_block"] == 1)).sum()
prod_only  = ((df["prod_block"] == 1) & (df["alt6m_block"] == 0)).sum()
alt6m_only = ((df["prod_block"] == 0) & (df["alt6m_block"] == 1)).sum()
neither    = ((df["prod_block"] == 0) & (df["alt6m_block"] == 0)).sum()
print(f"    both block (agree):     {both_block:>5}  ({both_block/n_total*100:5.1f}%)")
print(f"    prod block only:        {prod_only:>5}  ({prod_only/n_total*100:5.1f}%)  ← 6mo says allow")
print(f"    6mo block only:         {alt6m_only:>5}  ({alt6m_only/n_total*100:5.1f}%)  ← prod says allow")
print(f"    both allow (agree):     {neither:>5}  ({neither/n_total*100:5.1f}%)")

print(f"\n  ── IVP_252 (prod) vs IVP_504 (2yr) direction breakdown ──")
df["alt2y_block"] = block_by_w[504]
both_block = ((df["prod_block"] == 1) & (df["alt2y_block"] == 1)).sum()
prod_only  = ((df["prod_block"] == 1) & (df["alt2y_block"] == 0)).sum()
alt2y_only = ((df["prod_block"] == 0) & (df["alt2y_block"] == 1)).sum()
neither    = ((df["prod_block"] == 0) & (df["alt2y_block"] == 0)).sum()
print(f"    both block (agree):     {both_block:>5}  ({both_block/n_total*100:5.1f}%)")
print(f"    prod block only:        {prod_only:>5}  ({prod_only/n_total*100:5.1f}%)  ← 2yr says allow")
print(f"    2yr block only:         {alt2y_only:>5}  ({alt2y_only/n_total*100:5.1f}%)  ← prod says allow")
print(f"    both allow (agree):     {neither:>5}  ({neither/n_total*100:5.1f}%)")

# ── D. The two-question case: is jitter dominant in disagreement? ──────────
print(f"\n{'='*92}")
print(f"  D. JOINT VIEW — disagreement located in jitter zone?")
print(f"{'='*92}\n")

# Of all days where 126 and 252 disagree, what fraction has IVP_252 in [40, 70]?
disagree_6m_prod = (df["prod_block"] != df["alt6m_block"])
in_extended_zone = ((df["ivp_252"] >= 40) & (df["ivp_252"] <= 70))
joint = (disagree_6m_prod & in_extended_zone).sum()
print(f"  6mo vs prod disagreement days: {int(disagree_6m_prod.sum())}")
print(f"    of which IVP_252 in [40, 70]: {int(joint)} "
      f"= {joint/max(int(disagree_6m_prod.sum()),1)*100:.1f}%")
print(f"  → window-induced disagreement is concentrated in jitter zone: "
      f"{'YES' if joint/max(int(disagree_6m_prod.sum()),1) > 0.8 else 'NO/MIXED'}")

# ── E. Recent year detail (PM operational concern) ──────────────────────────
recent = df[df.index >= "2025-05-01"]
n_recent = len(recent)
print(f"\n{'='*92}")
print(f"  E. RECENT YEAR ({recent.index[0].date()} → {recent.index[-1].date()}, {n_recent} TD)")
print(f"{'='*92}\n")
in_band_recent = (((recent["ivp_252"] >= 50) & (recent["ivp_252"] <= 65)).sum())
print(f"  Days IVP_252 in [50, 65]: {int(in_band_recent)} / {n_recent} "
      f"= {in_band_recent/n_recent*100:.1f}%")
block_recent = (recent["ivp_252"] > 55).astype(int)
n_change_recent = int(block_recent.diff().abs().fillna(0).sum())
print(f"  Daily decision changes:   {n_change_recent} / {n_recent} = "
      f"{n_change_recent/n_recent*100:.1f}%")

# ── Save ────────────────────────────────────────────────────────────────────
df_out = df.copy()
df_out["date"] = df_out.index.strftime("%Y-%m-%d")
df_out = df_out[["date", "vix", "ivp_126", "ivp_252", "ivp_504",
                 "prod_block", "alt6m_block", "alt2y_block"]]
df_out.to_csv(os.path.join(OUT_DIR, "q067_daily_ivp_windows.csv"), index=False)
print(f"\n  Saved: q067_daily_ivp_windows.csv")
print("\n[Q067 done]")
