# Baseline Post SPEC-069

This directory stores the post-`SPEC-069` HC baseline snapshot.

Purpose:
- compare against `doc/baseline_post_spec068/`
- confirm `open_at_end` reporting adds terminal virtual trade rows without changing closed-trade metrics

## Quant-style compare summary

Reference:
- old baseline: `doc/baseline_post_spec068/`
- new baseline: `doc/baseline_post_spec069/`

### Structural result

- total trade rows: `60 -> 60`
- closed trades: `58 -> 58`
- newly explicit `open_at_end` virtual rows: `2`
  - `Iron Condor` — `2026-04-08 -> 2026-04-24`, mark-to-market `+$150.38`
  - `Bull Put Spread` — `2026-04-17 -> 2026-04-24`, mark-to-market `+$548.73`
- `trade_log.csv` now includes the new `open_at_end` column

Interpretation:
- pre-`SPEC-069` baseline already had two end-of-backtest rows
- `SPEC-069` does not create new economic outcomes; it re-labels those terminal rows as explicit `open_at_end` snapshots and exposes them in artifacts/UI

### Closed-trade metric diff

Using the correct compare basis:
- old baseline = `doc/baseline_post_spec068/trade_log.csv` filtered to exclude `exit_reason="end_of_backtest"`
- new baseline = `doc/baseline_post_spec069/metrics.json` (already excludes `open_at_end`)

Result:
- total PnL: `80,765.71 -> 80,765.71` (no change)
- Sharpe: `2.14 -> 2.14` (no change)
- MaxDD: `-9,391.92 -> -9,391.92` (no change)

### Interpretation

`SPEC-069` behaves as intended:
- reporting now distinguishes closed trades from terminal mark-to-market placeholders
- metrics remain strictly closed-trade-only
- research artifacts/UI can show unfinished positions without polluting portfolio statistics
