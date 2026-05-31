# SPEC-110 Developer Handoff

**Commit**: `4e80d5a`
**Deployed**: 2026-05-30 (Old Air confirmed: `/api/etrade/monthly-nlv` returns `{status: ok, count: 0}`)
**Status**: All 18 ACs PASS; 117 regression tests PASS

---

## Files Modified / Created

| File | Action | Description |
|---|---|---|
| `scripts/etrade_import_monthly_statements.py` | **NEW** | T1 importer: CSV/JSON/tab → `data/etrade_monthly_nlv.jsonl` |
| `scripts/etrade_monthly_aggregator.py` | **NEW** | T2 aggregator: daily snapshot month-end → monthly store |
| `scripts/etrade_audit_monthly.py` | **NEW** | T3 audit: transaction-derived cross-check, $1k threshold |
| `etrade/client.py` | EDIT | Added `list_transactions_for_period()` + `derive_monthly_pnl_from_transactions()` |
| `web/server.py` | EDIT | Added `/api/etrade/monthly-nlv?months=N` endpoint |
| `web/templates/portfolio_home.html` | EDIT | E*Trade card: 12M NLV sparkline widget + click-through modal |
| `web/templates/journal.html` | EDIT | NLV chart: +1Y (365d) +2Y (730d) buttons; monthly-import shading (purple) |
| `tests/test_spec_110.py` | **NEW** | 38 tests covering AC-110-1 through AC-110-18 |
| `Library/LaunchAgents/com.spxstrat.etrade-monthly.plist` | **NEW** | T2 monthly cron: day 1 of each month 11:00 UTC (06:00 ET winter) |

---

## PM: How to Import Historical Statements (T1)

**Step 1**: Download your E*Trade monthly statements from etrade.com → My Statements (PDF or account summary)

**Step 2**: Convert to CSV with this format (header row required):
```csv
month_end_date,nlv,cash,maint_margin,bp,notes
2024-06-28,452000.00,8500.00,28000.00,890000.00,
2024-07-31,461500.00,8200.00,30000.00,895000.00,
2024-08-30,471000.00,,,,
```
Only `month_end_date` and `nlv` are required. Others are optional.

**Step 3**: Run the importer:
```bash
arch -arm64 venv/bin/python scripts/etrade_import_monthly_statements.py \
    --input ~/Downloads/etrade_2024_2025_monthly.csv
```

**Step 4**: Verify:
```bash
arch -arm64 venv/bin/python scripts/etrade_import_monthly_statements.py \
    --input ~/Downloads/etrade_2024_2025_monthly.csv --dry-run
```

Re-running the same file is safe (idempotent). Use `--overwrite` to correct a typo.

---

## T2 Auto-Aggregator (Forward Coverage)

After the first `daily_snapshot.jsonl` entry with E*Trade data is written, T2 will auto-promote month-end records on the 1st of each month.

**Activate LaunchAgent** (first time only):
```bash
launchctl load ~/Library/LaunchAgents/com.spxstrat.etrade-monthly.plist
```

**Run manually** (e.g. to backfill from existing daily snapshots):
```bash
arch -arm64 venv/bin/python scripts/etrade_monthly_aggregator.py
```

---

## T3 Audit

```bash
arch -arm64 venv/bin/python scripts/etrade_audit_monthly.py --months 24
```

Flags months where `|NLV delta - transaction net_change| > $1,000`. Informational only — never modifies source data.

---

## API

`GET /api/etrade/monthly-nlv?months=12` (or `?months=all`)

Returns:
```json
{
  "status": "ok",
  "records": [{"month_end_date": "...", "nlv": ..., "source": "manual_import|daily_snapshot_eom", ...}],
  "count": N,
  "sources": {"manual_import": N, "daily_snapshot_eom": M},
  "audit_warnings": [],
  "audit_warning_count": 0
}
```

---

## Dashboard

- **`/portfolio_home`** E*Trade view → shows "12M NLV Trend" widget with sparkline + YTD/12M delta chips. Click → full monthly table modal with source attribution.
- **`/journal`** → NLV chart window selector now has 1Y (365d) and 2Y (730d). In E*Trade view with extended window, monthly-import records shown with purple shading.

---

## Test Results

```
tests/test_spec_110.py   38 passed  (AC-110-1 to AC-110-18)
tests/test_spec_103.py    9 passed
tests/test_spec_104.py    7 passed
tests/test_spec_105.py   13 passed
tests/test_spec_108.py   10 passed
tests/test_spec_108_1.py 40 passed  (includes 4 subtests)
──────────────────────────────────────
Total                    117 passed
```

---

## Design Compliance

- E*Trade NLV widget uses `--theme-purple` per `feedback_frontend_color_account` ✓
- No `--text-muted` in PM-facing content ✓
- No new `:root` tokens ✓

---

## Standing Notes

- `data/etrade_monthly_nlv.jsonl` is the source-of-truth file. Append-only in normal operation; `--overwrite` rewrites to correct errors.
- `manual_import` rows are never overwritten by T2 aggregator (manual wins).
- T3 transaction-derived P&L is audit-only — never source-of-truth.
- LaunchAgent plist runs on 1st of each month at 06:00 ET (11:00 UTC). Adjust `Hour` key if DST matters.

---

待 Quant Researcher review，结论写回 `task/SPEC-110.md` `## Review` 字段。
