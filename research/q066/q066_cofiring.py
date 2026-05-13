"""
Q066 — Aftermath vs Q042 Co-firing Frequency Analysis
2026-05-12

Quantify daily/event-level overlap between SPEC-064 Aftermath and Q042
Sleeve A/B triggers over 2007-2026, to confirm the two addons capture
distinct opportunities and are not redundant.

Outputs:
  - q066_daily_flags.csv : per-day aftermath / Q042-A-arm / Q042-A-trigger / Q042-B-watch / Q042-B-trigger flags
  - q066_event_overlap.csv : event-level cluster overlap (within ±5 TD)
  - Console: confusion matrix + clustered fire-event table
"""
import os
import sys
import pandas as pd
import numpy as np
import yfinance as yf

# ── Parameters mirroring production ─────────────────────────────────────────
# Aftermath (selector.py)
AF_PEAK_VIX_10D_MIN = 28.0
AF_OFF_PEAK_PCT     = 0.10
AF_EXTREME_VIX      = 40.0
AF_LOOKBACK_DAYS    = 10

# Q042 (signals/q042_trigger.py)
Q42_DD4   = -0.04
Q42_DD15  = -0.15
Q42_REARM = -0.02
Q42_WATCH_DAYS = 30
Q42_MA10  = 10

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Load data ───────────────────────────────────────────────────────────────
print("Loading VIX + SPX...")
vix_raw = yf.download("^VIX", start="2006-06-01", end="2026-05-13",
                      auto_adjust=False, progress=False)
spx_raw = yf.download("^GSPC", start="2006-06-01", end="2026-05-13",
                      auto_adjust=False, progress=False)
for raw in (vix_raw, spx_raw):
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

vix = vix_raw["Close"].dropna().sort_index()
spx = spx_raw["Close"].dropna().sort_index()
vix.index = pd.to_datetime(vix.index).tz_localize(None)
spx.index = pd.to_datetime(spx.index).tz_localize(None)

# Align both on intersection
common = vix.index.intersection(spx.index)
vix = vix.loc[common]
spx = spx.loc[common]

# Q042 production seed date: ATH starts from 2007-01-01
analysis_start = pd.Timestamp("2007-01-01")
df = pd.DataFrame({"vix": vix.values, "spx": spx.values}, index=common)
df = df[df.index >= analysis_start]
n = len(df)
print(f"  Trading days: {n}  range {df.index[0].date()} → {df.index[-1].date()}")

# ── Aftermath flags ─────────────────────────────────────────────────────────
vix_arr = df["vix"].values
peak10d = np.empty(n)
for i in range(n):
    lo = max(0, i - AF_LOOKBACK_DAYS + 1)
    peak10d[i] = float(np.max(vix_arr[lo : i + 1]))

aftermath = np.zeros(n, dtype=bool)
for i in range(n):
    v, peak = float(vix_arr[i]), peak10d[i]
    if peak < AF_PEAK_VIX_10D_MIN: continue
    if v > peak * (1.0 - AF_OFF_PEAK_PCT): continue
    if v >= AF_EXTREME_VIX: continue
    aftermath[i] = True

# ── Q042 flags ──────────────────────────────────────────────────────────────
spx_arr = df["spx"].values
ath = np.maximum.accumulate(spx_arr)
ddath = spx_arr / ath - 1.0  # negative when below ATH
ma10 = pd.Series(spx_arr).rolling(Q42_MA10).mean().values

# Sleeve A state machine
q42_a_armed       = np.zeros(n, dtype=bool)
q42_a_trigger     = np.zeros(n, dtype=bool)
armed_a = True
has_pos_a_until = -1  # bar idx until which "active position" mocked; treat as cleared after 30 TD (sleeve A 30 DTE)
for i in range(n):
    if not armed_a and ddath[i] >= Q42_REARM:
        armed_a = True
    if armed_a and ddath[i] <= Q42_DD4 and i > has_pos_a_until:
        q42_a_trigger[i] = True
        armed_a = False
        has_pos_a_until = i + 30  # mock 30 TD hold (DTE)
    q42_a_armed[i] = armed_a

# Sleeve B state machine
q42_b_armed       = np.zeros(n, dtype=bool)
q42_b_watching    = np.zeros(n, dtype=bool)
q42_b_trigger     = np.zeros(n, dtype=bool)
armed_b = True
in_watch_b = False
watch_start_idx = -1
has_pos_b_until = -1
for i in range(n):
    if not armed_b and ddath[i] >= Q42_REARM:
        armed_b = True
    # Outer trigger
    if armed_b and not in_watch_b and ddath[i] <= Q42_DD15 and i > has_pos_b_until:
        in_watch_b = True
        watch_start_idx = i
    # Inner trigger
    if in_watch_b:
        days_in_watch = i - watch_start_idx
        # MA10 reclaim
        if not np.isnan(ma10[i]) and spx_arr[i] > ma10[i]:
            q42_b_trigger[i] = True
            armed_b = False
            in_watch_b = False
            has_pos_b_until = i + 90  # mock 90 DTE
        elif days_in_watch > Q42_WATCH_DAYS:
            in_watch_b = False
    q42_b_armed[i] = armed_b
    q42_b_watching[i] = in_watch_b

# ── Daily flags dataframe ──────────────────────────────────────────────────
df_flags = pd.DataFrame({
    "date": df.index.strftime("%Y-%m-%d"),
    "vix": np.round(vix_arr, 2),
    "spx": np.round(spx_arr, 2),
    "ddath_%": np.round(ddath * 100, 2),
    "vix_peak_10d": np.round(peak10d, 2),
    "aftermath": aftermath,
    "q42_a_trigger": q42_a_trigger,
    "q42_b_watching": q42_b_watching,
    "q42_b_trigger": q42_b_trigger,
})

# ── Day-level statistics ────────────────────────────────────────────────────
n_after        = int(aftermath.sum())
n_a_trigger    = int(q42_a_trigger.sum())
n_b_watching   = int(q42_b_watching.sum())
n_b_trigger    = int(q42_b_trigger.sum())

print(f"\n{'='*88}")
print("  DAILY FIRE COUNTS (2007-2026)")
print(f"{'='*88}\n")
print(f"  Aftermath fire days   : {n_after}")
print(f"  Q042 A trigger days   : {n_a_trigger}")
print(f"  Q042 B watching days  : {n_b_watching}")
print(f"  Q042 B trigger days   : {n_b_trigger}")

# Day-level overlap: aftermath ∩ Q042-A-trigger
both_a_aftermath = aftermath & q42_a_trigger
print(f"\n  Same-day overlap:")
print(f"    Aftermath ∩ Q042-A-trigger  : {int(both_a_aftermath.sum())} days")
print(f"    Aftermath ∩ Q042-B-watching : {int((aftermath & q42_b_watching).sum())} days")
print(f"    Aftermath ∩ Q042-B-trigger  : {int((aftermath & q42_b_trigger).sum())} days")

# ── Event-level: cluster within ±5 TD ──────────────────────────────────────
WINDOW_TD = 5

def is_near(flag_array, idx, w=WINDOW_TD):
    lo = max(0, idx - w); hi = min(n, idx + w + 1)
    return bool(np.any(flag_array[lo:hi]))

# For each Q042-A trigger, did aftermath fire within ±5 TD?
a_events = np.where(q42_a_trigger)[0]
a_with_aftermath = sum(is_near(aftermath, i) for i in a_events)
print(f"\n{'='*88}")
print(f"  EVENT-LEVEL OVERLAP (±{WINDOW_TD} TD window)")
print(f"{'='*88}\n")
print(f"  Q042-A trigger events: {len(a_events)}")
print(f"    co-fire with Aftermath (±{WINDOW_TD} TD): {a_with_aftermath} "
      f"({a_with_aftermath/max(len(a_events),1)*100:.0f}%)")

b_events = np.where(q42_b_trigger)[0]
b_with_aftermath = sum(is_near(aftermath, i) for i in b_events)
print(f"  Q042-B trigger events: {len(b_events)}")
print(f"    co-fire with Aftermath (±{WINDOW_TD} TD): {b_with_aftermath} "
      f"({b_with_aftermath/max(len(b_events),1)*100:.0f}%)")

# For each aftermath window, did Q042-A fire within ±5 TD?
# Group aftermath into windows first
af_windows = []
in_w = False; start = None
for i in range(n):
    if aftermath[i] and not in_w:
        in_w = True; start = i
    elif not aftermath[i] and in_w:
        af_windows.append((start, i - 1))
        in_w = False
if in_w:
    af_windows.append((start, n - 1))

aw_with_a = sum(any(q42_a_trigger[max(0, s - WINDOW_TD):min(n, e + WINDOW_TD + 1)]) for s, e in af_windows)
aw_with_b = sum(any(q42_b_trigger[max(0, s - WINDOW_TD):min(n, e + WINDOW_TD + 1)]) for s, e in af_windows)
print(f"\n  Aftermath windows: {len(af_windows)}")
print(f"    co-fire with Q042-A trigger (±{WINDOW_TD} TD of window): "
      f"{aw_with_a} ({aw_with_a/max(len(af_windows),1)*100:.0f}%)")
print(f"    co-fire with Q042-B trigger (±{WINDOW_TD} TD of window): "
      f"{aw_with_b} ({aw_with_b/max(len(af_windows),1)*100:.0f}%)")

# ── Event table: each Q042-A/B trigger with nearest aftermath ──────────────
def nearest_aftermath_distance(idx):
    af_idx = np.where(aftermath)[0]
    if len(af_idx) == 0: return None
    diffs = af_idx - idx
    j = np.argmin(np.abs(diffs))
    return int(diffs[j])

ev_rows = []
for i in a_events:
    nd = nearest_aftermath_distance(i)
    ev_rows.append({"date": df.index[i].strftime("%Y-%m-%d"),
                    "sleeve": "A",
                    "spx": round(spx_arr[i], 2),
                    "vix": round(vix_arr[i], 2),
                    "ddath_%": round(ddath[i] * 100, 2),
                    "nearest_aftermath_dist_TD": nd,
                    "cofire_within_5TD": abs(nd) <= 5 if nd is not None else False})
for i in b_events:
    nd = nearest_aftermath_distance(i)
    ev_rows.append({"date": df.index[i].strftime("%Y-%m-%d"),
                    "sleeve": "B",
                    "spx": round(spx_arr[i], 2),
                    "vix": round(vix_arr[i], 2),
                    "ddath_%": round(ddath[i] * 100, 2),
                    "nearest_aftermath_dist_TD": nd,
                    "cofire_within_5TD": abs(nd) <= 5 if nd is not None else False})
df_events = pd.DataFrame(ev_rows).sort_values("date").reset_index(drop=True)

print(f"\n{'='*88}")
print("  Q042 TRIGGER EVENTS — each with nearest aftermath distance")
print(f"{'='*88}\n")
print(df_events.to_string(index=False))

# ── Confusion matrix: 4 cells ──────────────────────────────────────────────
print(f"\n{'='*88}")
print("  DAY-LEVEL CONFUSION MATRIX")
print(f"{'='*88}\n")
q42_any = q42_a_trigger | q42_b_trigger
both    = (aftermath & q42_any).sum()
only_af = (aftermath & ~q42_any).sum()
only_q  = (~aftermath & q42_any).sum()
neither = (~aftermath & ~q42_any).sum()
print(f"                      Q042 (A or B) trigger")
print(f"                      YES           NO")
print(f"  Aftermath  YES   {both:>6}        {only_af:>6}")
print(f"             NO    {only_q:>6}        {neither:>6}")
print(f"  ── totals: {n} days")
print(f"  same-day overlap rate (of either firing): "
      f"{both/max(both+only_af+only_q,1)*100:.1f}%")

# ── Save ────────────────────────────────────────────────────────────────────
df_flags.to_csv(os.path.join(OUT_DIR, "q066_daily_flags.csv"), index=False)
df_events.to_csv(os.path.join(OUT_DIR, "q066_event_overlap.csv"), index=False)
print(f"\n  Saved: q066_daily_flags.csv, q066_event_overlap.csv")
print("\n[Q066 done]")
