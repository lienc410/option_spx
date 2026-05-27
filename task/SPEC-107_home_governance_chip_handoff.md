# Portfolio Command Center — Intraday Governance Chip Handoff

**Date**: 2026-05-26
**Owner**: Frontend Engineer
**Status**: Backend API already exposes the data; frontend rendering pending
**Source SPEC**: SPEC-107 (DONE, deployed old Air commit `00c551b`)

---

## Context

SPEC-107 (Intraday Recommendation Governance) is live. The full UI lives on `/spx`. PM wants the same governance state surfaced as a **small summary chip on the Portfolio Command Center home page** (`/`, template `web/templates/portfolio_home.html`) so the current "is the dashboard actionable right now?" state is visible from the home dashboard without navigating to `/spx`.

Scope is **additive only** — do not duplicate the full SPX recommendation UI. One compact chip near the top of the home page is enough.

---

## Backend data — already shipped

Endpoint: `GET /api/recommendation`

Response contains `intraday_governance` object with these fields (full list, but only a few are needed for the chip):

```json
"intraday_governance": {
  "actionable": false,
  "is_scheduled_bar": false,
  "is_bypass_event": false,
  "bypass_type": null,
  "bypass_reason": null,
  "final_priority_layer": 7,
  "final_priority_name": "raw_selector",
  "next_actionable_decision_at": "2026-05-27T10:30:00-04:00",
  "last_actionable_decision_at": "2026-05-26T15:30:00-04:00",
  "governed_strategy": "Reduce / Wait",
  "governed_position_action": "WAIT",
  "regime": "NORMAL",
  ...
}
```

For the chip you only need:
- `actionable` (bool)
- `is_bypass_event` (bool)
- `bypass_type` (string or null) — values: `manual_override / broker_stop_loss / lifecycle_exit / spec_103_r5 / spec_103_r6 / extreme_vol / selector_hard_exit / stale_data_failsafe`
- `next_actionable_decision_at` (ISO timestamp, normally non-null)
- `final_priority_name` (string, optional — for tooltip)
- `governed_strategy` (string, optional — for tooltip)

---

## UI requirement

### Three states, three visual styles

| State | Condition | Chip label | Color |
|---|---|---|---|
| **Hard Exit** | `is_bypass_event=true` AND `bypass_type` is set | `🚨 Hard Exit · {humanized bypass_type}` | red (per SPEC-103 banner convention) |
| **Actionable Decision** | `actionable=true` AND `is_bypass_event=false` | `⚡ Actionable Decision` | orange/green (per existing SPEC-103 governance panel convention) |
| **State Observation** | otherwise (`actionable=false`) | `📊 State Observation · next 10:30 / 15:30 ET` | gray / muted |

Humanized `bypass_type` mapping (use these labels, not raw enum):

| bypass_type enum | Display |
|---|---|
| `manual_override` | `Manual Override` |
| `broker_stop_loss` | `Broker Stop-Loss` |
| `lifecycle_exit` | `Lifecycle Exit (Roll / TP / DTE 21)` |
| `spec_103_r5` | `SPEC-103 R5 Stress Cap` |
| `spec_103_r6` | `SPEC-103 R6 Second-Leg Block` |
| `extreme_vol` | `EXTREME_VOL (VIX ≥ 40)` |
| `selector_hard_exit` | `Selector Hard Exit` |
| `stale_data_failsafe` | `Stale Data Failsafe` |

### Where to place the chip

Top of the home page header area, near (or inside) the existing **Sleeve Stress Governance** panel from SPEC-103. Two acceptable layouts — pick whichever fits the existing visual rhythm:

**Option A (preferred)**: a new row inside the existing `Sleeve Stress Governance` panel, labelled `Intraday Governance`:
```
Sleeve Stress Governance
  R1 SPX PM     | 32.4 / 70.0 %  ✓
  R2 /ES SPAN   |  0.0 / 80.0 %  ✓
  R3 Combined   | 16.1 / 60.0 %  ✓
  R5 Stress     | inactive
  R6 Second-Leg | inactive
  Intraday Gov  | 📊 State Observation · next 10:30 ET    ← new row
```

**Option B (alternative)**: standalone chip in the page header strip alongside other status indicators.

I have a small preference for Option A because it co-locates all governance signals (account-layer R1-R6 + recommendation-layer SPEC-107) under one panel — easier for PM to scan.

### Countdown formatting (the `📊 State Observation` case)

For `next_actionable_decision_at`:
- If `next_actionable_decision_at` is **today** and the time is in the future:
  `📊 State Observation · next 10:30 ET in 2h 14m`
  (relative countdown)
- If it's a **different day**:
  `📊 State Observation · next 10:30 ET tomorrow`
  (or `next 10:30 ET Mon 06-02` for further-out)
- If `next_actionable_decision_at` is `null`:
  `📊 State Observation · next time unavailable`
  (calendar failure — should be rare; log a console.warn)

### Tooltip (hover)

On hover, show:
```
Governed: {governed_strategy} ({governed_position_action})
Priority: layer {final_priority_layer} · {final_priority_name}
Last actionable: {humanized timestamp}
```

Optional — skip if you'd rather keep the chip simple.

### Click behavior

Clicking the chip should navigate to `/spx` (where the full SPEC-107 UI lives). Use a soft hover indicator to suggest clickability.

---

## What NOT to do

- **Do not** duplicate the full SPX recommendation card on the home page. Keep this to a single chip.
- **Do not** modify any backend code — the data is already in `/api/recommendation.intraday_governance`.
- **Do not** invent new fields. If something is missing, ping Quant.
- **Do not** treat `last_actionable_decision_at == null` as an error during the first ~30 days after deploy (state is just empty initially). Show as "—" or omit.
- **Do not** modify SPEC-103 governance panel layout/logic — only add a new row to it (Option A) or place a separate chip elsewhere (Option B).
- **Do not** subscribe to bypass-event Telegram independently — the SPX page + bot already handle that; this chip is read-only display.

---

## Sample fetch + render skeleton (JS, illustrative)

```javascript
async function loadIntradayGovernance() {
  try {
    const res = await fetch('/api/recommendation');
    const data = await res.json();
    const gov = data?.intraday_governance;
    if (!gov) return;  // fail-soft: API may be unavailable

    let label, cls, tooltip;
    if (gov.is_bypass_event && gov.bypass_type) {
      label = `🚨 Hard Exit · ${humanizeBypass(gov.bypass_type)}`;
      cls = 'gov-chip gov-chip-danger';
    } else if (gov.actionable) {
      label = '⚡ Actionable Decision';
      cls = 'gov-chip gov-chip-active';
    } else {
      const next = formatCountdown(gov.next_actionable_decision_at);
      label = `📊 State Observation · ${next}`;
      cls = 'gov-chip gov-chip-muted';
    }

    tooltip = `Governed: ${gov.governed_strategy} (${gov.governed_position_action})\n`
            + `Priority: layer ${gov.final_priority_layer} · ${gov.final_priority_name}\n`
            + `Last actionable: ${formatTime(gov.last_actionable_decision_at) || '—'}`;

    renderChip(label, cls, tooltip);
  } catch (e) {
    console.warn('intraday_governance fetch failed', e);
    // Fail silently — do not break the home page
  }
}
```

Refresh cadence: poll every 1 minute (or piggy-back on whatever existing `/api/recommendation` poll already runs on the home page).

---

## Sanity check after deploy

```bash
# 1. Verify API returns intraday_governance
curl -s http://127.0.0.1:5050/api/recommendation | \
  python3 -m json.tool | grep -A 3 intraday_governance

# Expected output includes:
#   "actionable": false / true,
#   "next_actionable_decision_at": "2026-05-27T10:30:00-04:00",
#   "final_priority_name": "...",
```

Then visually verify in browser:

| Time of day | Expected chip |
|---|---|
| Between bars (e.g. 11:00 ET) | `📊 State Observation · next 15:30 ET in 4h 30m` (gray) |
| Right at 10:30 ET | `⚡ Actionable Decision` (orange/green) |
| If SPEC-103 R6 fires | `🚨 Hard Exit · SPEC-103 R6 Second-Leg Block` (red) |

---

## No regression risk

This is **additive on the home page only**. No backend code touched. No SPX-page UI touched. No SPEC-103 panel logic touched. If anything breaks, the chip can be hidden by removing the call to `loadIntradayGovernance()` without affecting anything else.

`tests/test_spec_107.py` (11 tests) covers all backend governance behavior already. No new tests required for this chip unless you want to add a frontend smoke test.

---

## Quant sign-off contact

Quant will validate the chip is reading the right fields after deploy. If anything in the API response doesn't match the field names above, ping me — could indicate API drift since 00c551b deployment.
