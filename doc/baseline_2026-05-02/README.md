# Baseline 2026-05-02 — SPEC-077 default lift (profit_target=0.60)

Reference output captured after SPEC-077 raised `StrategyParams.profit_target`
from 0.50 → 0.60 ([strategy/selector.py:68](../../strategy/selector.py#L68)).
Compare against `doc/baseline_2026-04-24/` (profit_target=0.50, the
MC-divergent baseline).

## Scope

- Period: 2023-01-01 → today (EOD, daily interval). 3.3y window.
- Defaults: `account_size=150000`, `risk_pct=0.02`, `params=DEFAULT_PARAMS`.
- Only behavioural delta vs 2026-04-24 baseline: `profit_target` 0.50 → 0.60.

## Files

- `run_baseline.py` — runner.
- `metrics.json` — headline metrics dict.
- `trade_log.csv` — full trade ledger.
- `signals.csv` — daily `signal_history` rows.
- `selector_dump_2026-03-{09,10}.json` — per-day selector decision context.
- `2026-03-strikes.json` — IC_HV legs (no SPEC-070 v2 leg-shift expected since
  selector logic unchanged from 2026-04-24 baseline).

## Headline numbers vs old baseline (2026-04-24)

| Metric | Old (PT=0.50) | New (PT=0.60) | Δ |
|---|---|---|---|
| Closed trades | 59 | 58 | -1 |
| Open at end | 0 | 2 | +2 |
| Win rate | 74.6% | 75.9% | +1.3pp |
| Total PnL (closed) | $93,890 | $80,614 | **-$13,276** |
| Avg win | $2,809 | $2,474 | -$335 |
| Avg loss | -$1,982 | -$2,016 | -$34 |
| Sharpe | 2.36 | 2.07 | **-0.29** |
| Calmar | 9.57 | 9.11 | -0.46 |
| Max DD | -$9,808 | -$8,850 | +$958 (improved) |
| Skew | -0.127 | +0.12 | +0.25 |
| CVaR5 | -$4,750.65 | -$4,750.65 | 0 |

Exit-reason migration:
- `50pct_profit` (label retained but logic now =60%): 19 → 16  (-3)
- `roll_21dte`: 28 → 32  (+4)
- `trend_flip`: 10 → 9  (-1)
- `roll_up`: 0 → 1  (+1)
- `end_of_backtest`: 2 → 0
- `open_at_end`: 0 → 2

## Interpretation

The 3.3y window result **does not directionally match** Q037 Phase 2A's full-
sample +0.91~+1.03pp ann ROE improvement:
- Total realized PnL: **-$13.3k** (-14%).
- Sharpe: **-0.29**.
- Max DD: improved by $958 (consistent with Q037 directionally).
- 2 of the 3 "missing" `50pct_profit` exits are now `open_at_end` — i.e. they
  haven't realized; their unrealized PnL is excluded from `total_pnl`.

**SPEC-077 AC3** specifies "ann ROE 改善 ≥ +0.5pp **全样本**, sharpe 不退化".
This baseline is **not** the full sample — it is the 3.3y release-comparison
window. AC3 verification continues to rest on the Q037 Phase 2A full-sample
data; this baseline's purpose is operational (lock in MC parity for prod
config), not statistical (validate the lift).

PM call required: should the F3 acceptance criterion be tightened to require
Q037 Phase 2A full-sample rerun under HC, or is the 3.3y release diff +
referenced Q037 result sufficient?

## Known properties baseline locks in

- IC_HV `_build_legs` uses **wing-based** long legs (unchanged vs 2026-04-24).
- Aftermath IC_HV short delta = 0.16 (unchanged).
- `BEAR_CALL_DIAGONAL` still present in `_build_legs` (unchanged).
- `profit_target` is the only DEFAULT_PARAMS delta.

## How to use

After applying further SPEC implementations, re-run `run_baseline.py` and diff
against this snapshot.
