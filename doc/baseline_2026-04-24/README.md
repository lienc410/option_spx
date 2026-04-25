# Baseline 2026-04-24 — Pre-SPEC-070 v2 Snapshot

Reference output captured at git tag `pre-spec070-baseline-2026-04-24` (HC main HEAD `a7f938e`).
Used to verify behavioural deltas introduced by SPEC-068 / 070 v2 / 071 / 069 / 072 / 073 during HC reproduction.

## Scope

- Period: 2023-01-01 → today (EOD, daily interval).
- Defaults: `account_size=150000`, `risk_pct=0.02`, `params=DEFAULT_PARAMS`.

## Files

- `run_baseline.py` — runner. Re-execute under same git tag to reproduce.
- `metrics.json` — headline metrics (PnL, Sharpe, Calmar, by_strategy).
- `trade_log.csv` — full trade ledger (no leg detail; `Trade` dataclass only stores roll-up).
- `signals.csv` — daily `signal_history` rows.
- `selector_dump_2026-03-{09,10}.json` — per-day selector decision context.
- `2026-03-strikes.json` — IC_HV legs constructed on the 2026-03 double-spike days, captured by monkey-patching `_build_legs`.

## Headline numbers

- 59 trades, win rate 74.6%, total PnL $93,890, Sharpe 2.36, max DD $-9,807.
- IC_HV: n=10, win rate 100%, avg PnL $2,401.

## Known properties baseline locks in

- IC_HV `_build_legs` uses **wing-based** long legs: `wing = max(50, round(spx * 0.015 / 50) * 50)`.
  - 2026-03-09 (SPX=6795.99): call short 7672, call long 7772; put short 6192, put long 6092 — wing=100.
  - 2026-03-10 (SPX=6781.48): call short 7636, call long 7736; put short 6192, put long 6092 — wing=100.
- `hv_spell_trade_count` is a single scalar (not per-strategy).
- Aftermath IC_HV short delta = 0.16 (selector line 815 in `strategy/selector.py` at this tag).
- `BEAR_CALL_DIAGONAL` still present in `_build_legs`.

## How to use

After applying any SPEC implementation, re-run `run_baseline.py` and diff:
- `trade_log.csv` for entry/exit cascade changes.
- `metrics.json` for headline impact.
- `2026-03-strikes.json` for SPEC-070 v2 long-leg shift.

Diffs in BP cascade are expected; AC4 of SPEC-066 explicitly accepts this.
