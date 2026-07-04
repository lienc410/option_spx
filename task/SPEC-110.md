# SPEC-110 — E*Trade Historical NLV Backfill (Statement Import + Transaction Audit)

**Type**: data integration / observability
**Date**: 2026-05-30
**Status**: **APPROVED** — PM signed 2026-05-30, pending Developer implementation
**Owner**: Quant Researcher (draft) → PM approval → Developer implementation
**Source**: PM request 2026-05-30 — "I need to see ~1 year of E*Trade monthly NLV"; Quant scoping shows current `etrade/client.py` only exposes real-time `get_account_balances()`; PyEtrade `list_transactions` supports 2y but does NOT directly yield NLV
**Parent**: SPEC-089 (E*Trade PM integration, DEPLOYED 2026-05-08 commit `adf4c13`) — unchanged

---

## 0. TL;DR

PM needs **1+ year of historical monthly NLV** for the E*Trade PM account. E*Trade's public API has no endpoint for "monthly NLV history" — the only reliable source is E*Trade's own **Web Statements** (downloadable as PDF/CSV from etrade.com).

Two-track SPEC:

| Track | What | Coverage | Effort |
|---|---|---|---|
| **T1 — Manual statement import (PRIMARY)** | PM downloads monthly statement CSV/PDF from etrade.com; we provide an importer that parses and persists NLV time series | **Historical back to E*Trade account inception** (PM-controlled) | bulk import ~30 min one-time + parser ~2h |
| **T2 — Auto continuation (SECONDARY)** | `scripts/daily_snapshot.py` already captures `etrade_nlv` daily; add a monthly-end aggregator that auto-promotes month-end daily snapshot into the historical series | **Forward-only (from SPEC-110 deploy date onward)** | ~1h |
| **T3 — Transaction cross-check (AUDIT)** | Use PyEtrade `list_transactions` (2y window) to derive monthly net cash flow + realized P&L; cross-check against statement NLV deltas for reconciliation | **2 years backward (audit only, not source-of-truth)** | ~2h |

```
historical NLV   ←  T1 (manual import, source-of-truth)
                ←  T3 (transaction-derived monthly Δ, audit cross-check)
forward NLV      ←  T2 (daily snapshot month-end aggregator, auto)
display          ←  /journal NLV chart extended to multi-year; /portfolio_home account card adds "YTD" + "12M" NLV summary
```

---

## 1. Background

### 1.1 PM use case

PM wants to see how E*Trade NLV has evolved month-by-month over the past year+. Use cases:
- Validate SPEC-108.1 Stage 2 advancement context (BP utilization vs NLV trajectory)
- Annual return / drawdown sanity checks against tax / brokerage statements
- Communicate to outside parties (CPA, financial planner) standardized NLV history

### 1.2 What E*Trade API actually exposes (verified 2026-05-30)

PyEtrade SDK methods on `ETradeAccounts`:

| Method | Returns | Time range |
|---|---|---|
| `get_account_balance()` | Real-time NLV, cash, margin | now |
| `list_transactions()` | Transactions (trades, deposits, withdrawals, fees, dividends) | **2 years** |
| `list_transaction_details()` | Single transaction breakdown | per-transaction |
| `list_accounts()` | Account list (one-time) | static |
| `get_account_portfolio()` | Current positions | now |

**Notable absence**: no `get_account_statement()`, no `get_nlv_history()`, no `get_performance_history()`. E*Trade's monthly statements are NOT API-accessible — only via Web (etrade.com → My Statements).

### 1.3 Why transaction-based NLV reconstruction is impractical as source-of-truth

To reconstruct daily NLV from `list_transactions` alone you would need:
- Holdings at every point in time (derivable from transaction log) ✓
- Per-position price on every relevant date (NOT in transactions; needs historical chain quote data) ✗
- Cash balance evolution (derivable) ✓
- Margin interest accruals (partial; some are transactions, some aren't) ✗
- Pending settlement / unsettled trades (NOT reliably exposed) ✗

Cost: 1-2 weeks dev work for a fragile reconstruction. Value: low (PM already has trustworthy NLV in Web Statement).

**Conclusion**: T3 transaction-derived monthly Δ is **audit/cross-check only**, not source-of-truth.

---

## 2. Scope

### 2.1 Data model

New file: `data/etrade_monthly_nlv.jsonl` (append-only, idempotent on `month_end_date`)

```json
{
  "month_end_date": "2025-06-30",
  "account": "etrade",
  "nlv": 487231.55,
  "cash": 12345.67,
  "maintenance_margin": 34521.10,
  "total_buying_power": 950000.00,
  "source": "manual_import" | "daily_snapshot_eom" | "transaction_derived",
  "source_file": "filename.csv" | null,
  "imported_at": "2026-05-30T14:00:00Z",
  "month_pnl": 8211.30,
  "month_cash_flow": 0.00,
  "notes": "string | null"
}
```

Fields not always available (cash, margin, BP) can be null when source = `manual_import` from a brief statement.

### 2.2 T1 — Manual statement importer (NEW script)

`scripts/etrade_import_monthly_statements.py`

CLI:
```
arch -arm64 venv/bin/python scripts/etrade_import_monthly_statements.py \
    --input ~/Downloads/etrade_monthly_2025.csv \
    [--format csv|json|tab] \
    [--dry-run]
```

Behavior:
- Parses input file (one row per month)
- Validates each row has `month_end_date` + `nlv` (other fields optional)
- For each parsed row: check if `month_end_date` already exists in `data/etrade_monthly_nlv.jsonl`
  - If yes + `--overwrite` flag → replace
  - If yes + no overwrite → log skip
  - If no → append with `source = "manual_import"`
- Print summary: N rows parsed / M imported / K skipped

Supported input format (CSV, header row required):

```csv
month_end_date,nlv,cash,maint_margin,bp,notes
2024-06-28,452000.00,8500.00,28000.00,890000.00,
2024-07-31,461500.00,8200.00,30000.00,895000.00,
...
```

JSON format:
```json
[
  {"month_end_date": "2024-06-28", "nlv": 452000.00, ...},
  ...
]
```

PDF parsing: **out of scope** (T1 v1). PM can OCR / manually extract NLV from PDF statement → produce CSV themselves.

### 2.3 T2 — Auto monthly-end aggregator

`scripts/etrade_monthly_aggregator.py`

CLI: invoked from cron / scheduled job; or manually `arch -arm64 venv/bin/python scripts/etrade_monthly_aggregator.py`

Behavior:
- Reads `data/daily_snapshot.jsonl` (existing, written daily by `daily_snapshot.py`)
- For each calendar month with daily snapshots: find the **last trading day of that month** in the data
- Promote that day's E*Trade NLV to `data/etrade_monthly_nlv.jsonl` with `source = "daily_snapshot_eom"`
- Skip months where a `manual_import` entry already exists (manual wins)
- Idempotent: re-running on same dataset produces same result
- Cron schedule: run on 1st of each month at 06:00 ET (covers prior month)

### 2.4 T3 — Transaction-derived audit (NEW client method)

Extend `etrade/client.py` with:

```python
def list_transactions_for_period(start_date, end_date, account_id=None):
    """Wraps PyEtrade list_transactions with paging. Returns normalized list of dicts."""

def derive_monthly_pnl_from_transactions(start_date, end_date, account_id=None):
    """Group transactions by month; classify deposits/withdrawals/trades/fees/dividends.
    Returns: per-month {cash_flow_in, cash_flow_out, realized_trade_pnl, fees, dividends, net_change}.
    Used as cross-check against manual_import NLV deltas — NOT source-of-truth for NLV.
    """
```

Add CLI script `scripts/etrade_audit_monthly.py`:
- Compares `etrade_monthly_nlv.jsonl` month-over-month NLV delta vs T3 derived `net_change`
- Discrepancy > $1k flagged with audit_warning row

### 2.5 API

`web/server.py` add:

```
GET /api/etrade/monthly-nlv?months=N (default 24, 'all')
  → returns sorted-ascending list of monthly NLV records
  → includes source attribution + audit warnings (if any)
```

Existing `/api/portfolio/daily-history` unchanged (continues to serve daily resolution).

### 2.6 UI

`web/templates/portfolio_home.html` (PRIMARY surface):
- New widget on the E*Trade account card: **"12M NLV trend"** — small inline sparkline + "+X% YTD / +Y% 12M" delta chips
- Click-through: opens a modal with full monthly NLV table + source attribution column
- If `audit_warning` count > 0: orange chip "audit: N discrepancies"

`web/templates/journal.html` (SECONDARY):
- NLV chart already exists; extend window selector to include "all" / "1Y" / "2Y" so PM can see multi-year context
- When window > daily-snapshot coverage, show shaded "from monthly import" portion vs "daily" portion

DESIGN.md compliance:
- Use `var(--theme-lit-049)` (existing brand blue) for ETrade NLV line
- Sparkline cells use `var(--text-2)` for labels — NOT `--text-muted` (per `feedback_text_muted_banned`)
- Reuse `--theme-purple` (existing ETrade positions color per `feedback_frontend_color_account`) for ETrade account section

### 2.7 NOT changed

- `etrade/auth.py` — unchanged (OAuth flow stays the same)
- `etrade/client.py` `get_account_balances()` real-time — unchanged
- `scripts/daily_snapshot.py` — unchanged (T2 reads its output but doesn't modify)
- All SPEC-108 / SPEC-108.1 / SPEC-109 production code paths — unchanged
- Schwab account data flow — unchanged (Schwab has its own NLV history; out of scope for this SPEC)
- Production trading / order paths — unchanged (this is observability only)

---

## 3. File Changes

| File | Action |
|---|---|
| `scripts/etrade_import_monthly_statements.py` | **NEW** — T1 CSV/JSON importer |
| `scripts/etrade_monthly_aggregator.py` | **NEW** — T2 daily-snapshot → monthly promotion |
| `scripts/etrade_audit_monthly.py` | **NEW** — T3 transaction audit cross-check |
| `etrade/client.py` | EDIT — add `list_transactions_for_period()` + `derive_monthly_pnl_from_transactions()` |
| `web/server.py` | EDIT — add `/api/etrade/monthly-nlv` route |
| `web/templates/portfolio_home.html` | EDIT — add 12M NLV trend widget on E*Trade account card + modal |
| `web/templates/journal.html` | EDIT — extend NLV chart window selector + shaded source attribution |
| `data/etrade_monthly_nlv.jsonl` | NEW (runtime) — primary data store |
| `tests/test_spec_110.py` | **NEW** — ACs for importer + aggregator + API + idempotency |
| `Library/LaunchAgents/com.spxstrat.etrade-monthly.plist` | **NEW (optional)** — monthly cron entry for T2 aggregator |

---

## 4. Acceptance Criteria

| AC# | Verification |
|---|---|
| AC-110-1 | `scripts/etrade_import_monthly_statements.py --input X.csv` parses CSV and writes `data/etrade_monthly_nlv.jsonl` rows with `source="manual_import"` | pytest |
| AC-110-2 | Re-running same import produces no duplicates (idempotent on `month_end_date`) | pytest |
| AC-110-3 | `--overwrite` flag replaces existing rows for matching dates | pytest |
| AC-110-4 | `--dry-run` flag parses + validates without writing | pytest |
| AC-110-5 | Invalid CSV (missing required fields) errors with clear message; no partial write | pytest |
| AC-110-6 | `scripts/etrade_monthly_aggregator.py` reads `data/daily_snapshot.jsonl`, picks last trading day per month, writes rows with `source="daily_snapshot_eom"` | pytest with seeded jsonl |
| AC-110-7 | Aggregator skips months where `manual_import` entry exists (manual wins) | pytest |
| AC-110-8 | `etrade/client.py:list_transactions_for_period(start, end)` pages through PyEtrade and returns normalized list | pytest with mocked PyEtrade |
| AC-110-9 | `derive_monthly_pnl_from_transactions()` classifies into cash_flow_in/out/realized_trade_pnl/fees/dividends | pytest |
| AC-110-10 | `scripts/etrade_audit_monthly.py` flags monthly NLV deltas where `\|manual_nlv_delta − transaction_derived_net_change\| > $1000` | pytest |
| AC-110-11 | `/api/etrade/monthly-nlv?months=12` returns sorted-asc list with `source` field | curl test |
| AC-110-12 | `/api/etrade/monthly-nlv?months=all` returns full history | curl test |
| AC-110-13 | Dashboard E*Trade card shows 12M NLV sparkline + "+X% YTD / +Y% 12M" deltas | visual on oldair |
| AC-110-14 | Click-through opens modal with full monthly NLV table including `source` column | visual |
| AC-110-15 | `/journal` NLV chart window selector includes "all" / "1Y" / "2Y" options; shaded region distinguishes monthly-import from daily-source | visual |
| AC-110-16 | DESIGN.md compliance: no `--text-muted` on PM-facing content; reuses `--theme-purple` for ETrade section per `feedback_frontend_color_account` | grep + visual |
| AC-110-17 | SPEC-103 ~ SPEC-108.1 + SPEC-109 regressions all PASS | pytest |
| AC-110-18 | E*Trade real-time `/api/portfolio/snapshot` field shapes unchanged (no break to existing consumers) | curl diff |

---

## 5. Out of Scope

| Not done | Why |
|---|---|
| PDF statement OCR / parsing | v1: PM converts PDF → CSV manually; PDF parsing is fragile and brittle vs PDF format changes |
| Daily NLV reconstruction from transactions | Infeasible without historical chain quote integration; T3 only does monthly Δ as audit |
| Schwab monthly NLV import | Schwab has its own historical NLV API (separate SPEC if needed) |
| Performance attribution (return decomposition by strategy / position) | Separate task; this SPEC is NLV trajectory only |
| Tax-lot accounting / 1099 reconciliation | Out of scope; use TurboTax / etrade tax docs directly |
| Real-time E*Trade NLV streaming | Existing `get_account_balances()` is sufficient |
| Manual import GUI (file-upload web form) | v1: CLI only. Web upload form is v2 if PM wants it later |
| Backfill SPX_PM intra-month NLV from daily snapshot | T2 already does month-end snapshot; intra-month daily is what `/journal` already shows |

---

## 6. Staged Rollout

**Single deployment** — no shadow/staged required:

- This SPEC is **read-only observability + data import**. No trading code path changed. No risk to live positions.
- Stage 0: Developer implements code + tests
- Stage 1: PM does one-time manual import of historical statements (CLI command, ~10 min)
- Stage 2: Monthly cron starts auto-promoting daily-snapshot month-end records (LaunchAgent or manual)
- Dashboard immediately shows historical + forward NLV

---

## 7. Design Notes

### 7.1 Why "manual import" is the primary track

E*Trade Web Statements are **the source-of-truth** for historical NLV — they are what E*Trade reports to the IRS and what PM sees on monthly emails. Any derived/reconstructed NLV (from transactions, daily snapshots, etc.) is a model that will drift from official numbers. By making manual statement import primary, the data store matches E*Trade's official record.

### 7.2 Why T3 transaction audit is worth doing despite not being source-of-truth

If `manual_import` month-over-month NLV delta doesn't match `transaction_derived` net change (within $1k tolerance), something is wrong:
- Missed month in import
- Typo / OCR error in CSV
- Unexpected non-cash event (corporate action, etc.)

Audit catches these without requiring PM to manually reconcile every month.

### 7.3 Why no shadow stage

This is observability — no production trading affected. Even if importer has bugs, worst case is wrong NLV chart on dashboard (PM can see + correct). Shadow stage would add ceremony without risk reduction.

### 7.4 Why $1k audit tolerance

PM account scale ~$500k; $1k = 0.2% NLV. Catches material reconciliation gaps without alerting on intra-month volatility / pending settlements / cash sweep delays.

### 7.5 Why daily-snapshot month-end (not avg / first / median)

Convention with E*Trade Web Statement: statements report NLV as of last trading day of month. Using same convention enables apples-to-apples cross-check.

### 7.6 PM-facing data integrity

Dashboard 12M trend widget MUST show source attribution chip near the chart ("source: 80% manual statement / 20% daily snapshot"). PM should never be confused about whether a number is official vs derived.

---

## 8. Deploy

1. Developer implements §3 file changes
2. Run `pytest tests/test_spec_110.py tests/test_spec_103.py tests/test_spec_104.py tests/test_spec_105.py tests/test_spec_106.py tests/test_spec_107.py tests/test_spec_108.py tests/test_spec_108_1.py` — all PASS (AC-110-17)
3. Commit + push
4. Deploy oldair (per `feedback_deploy_oldair.md`)
5. PM does one-time manual import: download monthly statements from etrade.com → convert to CSV → run importer
6. T2 monthly aggregator: PM sets up LaunchAgent (or runs manually first 1-2 months to validate)
7. Smoke test:
   - `curl https://oldair.spxstrat.app/api/etrade/monthly-nlv?months=24 | jq '.records | length'` returns > 0
   - Visit `/portfolio_home` see E*Trade card with NLV trend widget
   - Visit `/journal` see extended NLV chart with multi-year window

---

## 9. Estimated Effort

| Phase | CC+gstack | Human |
|---|---|---|
| T1 importer (CLI + CSV/JSON parsers + idempotency) | ~1.5h | ~3h |
| T2 monthly aggregator (read daily snapshot + month-end pick) | ~45 min | ~1.5h |
| T3 transaction wrapper + monthly aggregator + audit script | ~2h | ~4h |
| `/api/etrade/monthly-nlv` route + tests | ~30 min | ~1h |
| Dashboard 12M widget + click-through modal | ~1.5h | ~4h |
| `/journal` NLV chart window extension | ~45 min | ~2h |
| `tests/test_spec_110.py` (18 ACs) | ~1h | ~3h |
| LaunchAgent plist + manual setup | ~15 min | ~30 min |
| Deploy + smoke + PM one-time import | ~30 min | ~1h |
| **Total** | **~8.5h** | **~5-6 days** |

Comparable to SPEC-108.1 (~7.5h) but with more UI surface area.

---

## 10. PM Approval Signature

**PM signed 2026-05-30** (single "A" affirms all 9 items below)

- [x] Approve manual-statement-import primary track (T1) with CSV/JSON format
- [x] Approve daily-snapshot month-end aggregator secondary track (T2)
- [x] Approve transaction-based audit (T3) with $1k discrepancy tolerance
- [x] Approve new `/api/etrade/monthly-nlv` endpoint
- [x] Approve E*Trade card 12M NLV widget on `/portfolio_home`
- [x] Approve `/journal` NLV chart window extension to 1Y / 2Y / all
- [x] Confirm PDF OCR is **NOT** in v1 (PM converts PDF→CSV manually)
- [x] Confirm Schwab side is separate SPEC
- [x] Acknowledge single-stage deploy (no shadow gate; observability-only)

---

## 11. Developer Handoff Notes

### Implementation checklist

1. **Read parent**: `task/SPEC-089.md` (E*Trade integration) + `etrade/client.py` + `scripts/daily_snapshot.py`
2. **T1 importer**: CSV (headers required: `month_end_date,nlv` + optional `cash,maint_margin,bp,notes`); JSON list of objects; tab-separated as bonus; idempotency by `month_end_date`; `--dry-run` validates without writing; `--overwrite` replaces
3. **T2 aggregator**: read `data/daily_snapshot.jsonl`, group by `month_end_date.year_month`, pick max date per month, transform into monthly record with `source="daily_snapshot_eom"`; skip if month already has `manual_import`
4. **T3 client extensions**:
   - `list_transactions_for_period(start, end)`: wrap PyEtrade `list_transactions` with 50-per-page paging
   - `derive_monthly_pnl_from_transactions()`: classify transactions into 5 buckets (cash_in/out/trade_pnl/fees/dividends); group by month
5. **T3 audit script**: load `etrade_monthly_nlv.jsonl`, compute month-over-month NLV delta, compare to transaction-derived `net_change`, flag > $1k discrepancies
6. **API**: `/api/etrade/monthly-nlv` reads jsonl, returns sorted-asc; supports `?months=N` and `?months=all`; includes `audit_warning` field per record
7. **Dashboard**: E*Trade card adds 12M widget (sparkline + delta chips); click-through opens modal with table; reuse `--theme-purple` per `feedback_frontend_color_account`; NO `--text-muted`
8. **Journal**: extend NLV chart window selector; shaded region for monthly-import portion
9. **Tests**: 18 ACs in `tests/test_spec_110.py`
10. **LaunchAgent**: create plist for monthly cron (06:00 ET on day 1 of each month)
11. **Backtest cache**: NOT required (no algorithm change)

### Implementation discipline (per PM)

> Implement SPEC-110 exactly. **Do NOT** change `etrade/auth.py` OAuth flow. **Do NOT** modify `scripts/daily_snapshot.py`. **Do NOT** change any SPEC-108 / 108.1 / 109 production trading code. **Do NOT** OCR PDF statements (out of scope). **Do NOT** rely on T3 transaction-derived NLV as source-of-truth — always defer to manual_import. **Do NOT** auto-import / scrape etrade.com web statements (TOS / authentication concerns).

### Reference docs Developer should read

1. `task/SPEC-110.md` (this file)
2. `task/SPEC-089.md` (parent E*Trade integration; if exists)
3. `etrade/client.py` lines 76+ (current normalized payload structure)
4. `scripts/daily_snapshot.py` (T2 reads its output schema)
5. `DESIGN.md`
6. `~/.claude/.../memory/feedback_frontend_color_account.md` (ETrade color = `--theme-purple`)
7. `~/.claude/.../memory/feedback_text_muted_banned.md`
8. `~/.claude/.../memory/feedback_deploy_oldair.md`
9. `~/.claude/.../memory/feedback_spec_integration_test.md` (E*Trade integration AC must include non-mocked integration smoke test)

---

## 12. References

- `etrade/client.py` — current `get_account_balances()` implementation
- `etrade/auth.py` — OAuth flow (unchanged)
- `scripts/daily_snapshot.py` — daily NLV capture (T2 reads its output)
- `web/portfolio_surface.py` — current E*Trade NLV display path
- PyEtrade SDK — `ETradeAccounts.list_transactions(account_id_key, start_date, end_date, sort_order, marker, count)` returns up to 50/page; 2-year history per docstring
- `~/.claude/.../memory/project_etrade_integration.md` — SPEC-089 status

---

## Review

（待 Developer 完成实施后由 Quant Researcher 填写）

- 结论：N/A (pending Developer handoff)
- 问题：N/A

---

Status: DRAFT
