# SPEC-103 — Aftermath Annotation Layer on Governance Backtest Chart

**Date**: 2026-05-17
**Owner**: Frontend Engineer (post-Quant handoff)
**Status**: Backend API extended; frontend rendering pending

---

## Context

PM observed (2026-05-17) that the Research view — SPEC-103 governance rule backtest 页面 does not show aftermath signal fires for March 2026 (or any other historical period). The underlying data does contain `aftermath_active` (SPEC-064 / Q070 BPS_HV permission gate), but the `/api/governance/timeline` API was not exposing it.

**Aftermath is NOT a SPEC-103 governance regime** — it is a strategy-layer permission signal (BPS_HV entry gate). It can coexist with R5 stress / R6 second-leg regimes. Therefore the right UX is a **separate annotation layer**, not a 4th regime enum.

---

## Backend changes (already done — commit pending)

Extended `/api/governance/timeline` response with two new fields:

```json
{
  "status": "available",
  "dates":            ["2007-01-03", ...],       // existing
  "vix":              [12.04, ...],              // existing
  "regimes":          ["normal", "stress", ...], // existing (normal/stress/second)
  "spx":              [...],                     // existing
  "spx_ma10":         [...],                     // existing
  "hv_entries":       [...],                     // existing
  "hv_blocked":       [...],                     // existing
  "daily_curve":      [...],                     // existing
  "aftermath_flags":  [false, true, false, ...], // NEW — bool per date, parallel to `dates`
  "aftermath_dates":  ["2026-03-09", "2026-03-10", ...]  // NEW — date list of fires
}
```

19y data: **518 aftermath-active days total**, concentrated in stress periods.

---

## Frontend asks

### What to render

1. **On the governance backtest chart timeline** (regime band):
   - Add a thin highlight band or dotted marker layer for `aftermath_dates`
   - Suggested color: amber/yellow (distinct from `stress` orange and `second` red)
   - Tooltip on hover: "Aftermath — BPS_HV permission active (SPEC-064)"

2. **Recommended visual approach** (suggestion, not prescriptive):
   - Sparse dots/triangles above the VIX line at aftermath dates
   - Or a thin colored band along the bottom of the chart, parallel to the regime band
   - Or chart annotation with vertical lines at `aftermath_dates`

3. **Optional legend entry**:
   ```
   Aftermath (BPS_HV permission): N days · 18.1% of stress episodes
   ```
   (statistic: 518 aftermath days / 2862 stress days ≈ 18% — but compute from current data, not hardcode)

### What NOT to do

- **Do not** rename `regimes` enum to include "aftermath" — aftermath can coexist with stress/second, so it's not mutually exclusive
- **Do not** modify the 3-column regime card (Normal / Stress / Second Leg) — those describe SPEC-103 R1-R6 only
- **Do not** block aftermath rendering when `second_leg` is active — they can fire simultaneously

### Edge cases

- `aftermath_flags` is always parallel to `dates` (same length). Safe to zip.
- `aftermath_dates` is a derived list (subset of `dates` where flag is true) — convenience for sparse rendering.
- If API returns `aftermath_flags: []` (empty), treat as no aftermath data available — fail-soft.

---

## Reference: 2026-03 aftermath fires (sanity check expected on UI)

| Date range | Days | VIX context |
|---|---|---|
| 2026-03-09 → 03-11 | 3 | VIX peak 29.49 on 03-06, off-peak 13-18% |
| 2026-03-16 → 03-19 | 4 | VIX peak 29.49 holding, off-peak 10-24% |
| 2026-03-31 → 2026-04-13 | 9 | VIX new peak 31.05 on 03-27, off-peak 18%+ |

If the chart renders March 2026 correctly, these 16 days should be visibly highlighted.

---

## Aftermath definition (for completeness)

Per SPEC-064 + Q070 (do NOT modify these constants):
```
AFTERMATH_PEAK_VIX_10D_MIN = 28
AFTERMATH_OFF_PEAK_PCT     = 0.10
AFTERMATH_VIX_UPPER        = 40

is_aftermath(vix_today, vix_peak_10d) =
    (vix_peak_10d >= 28)
    AND (vix_today / vix_peak_10d <= 0.90)   # ≥10% off peak
    AND (vix_today < 40)
```

The backend already computes this in `selector.is_aftermath()` and persists to `q072_p1_daily_flags.csv.aftermath_active`.

---

## Test sanity check

```bash
curl -s http://127.0.0.1:5050/api/governance/timeline | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  print('aftermath_dates in 2026-03:', \
  [x for x in d['aftermath_dates'] if x.startswith('2026-03')])"
```

Expected:
```
aftermath_dates in 2026-03: ['2026-03-09', '2026-03-10', '2026-03-11',
                              '2026-03-16', '2026-03-17', '2026-03-18',
                              '2026-03-19', '2026-03-31']
```

---

## No regression risk

This change is **additive** to `/api/governance/timeline` only. No existing fields modified. No governance logic changed. No daemon impact. SPEC-103 tests still 9/9 PASS post-change (verified locally before commit).
