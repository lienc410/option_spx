# Q081 P1 — BCD Historical Cash Deployment + Crowd-Out Events

**Date**: 2026-06-01
**Owner**: Quant Researcher
**Status**: COMPLETE
**Prior**: P0 verdict — cash-bound confirmed, steady-state baseline = $37,046
**Next**: P2 left-tail cash-ROE distribution

---

## Verdict

**Zero historical crowd-out under steady-state baseline.** BCDs ran as a
strict sequential ladder (21 trades, one at a time, rolling at 21 DTE) over
2023-06 → 2026-01. No date had two genuine BCDs in force simultaneously.

**Single-position cash consumption is high but never forced QQQ sale.**
Average cash consumed when BCD open: **66% of $37k = $24.4k**, leaving $12.6k
slack. Tight but never breached.

**Cumulative opportunity cost = $2,497 over 3y** (~$830/yr, ~$119/trade), or
**6.6% of gross BCD PnL ($37,714)**. Net of opp cost: $35,217.

---

## Method

1. Load 21 BCD trades from `data/backtest_trades_3y_2026-04-29.csv`.
2. For each weekday in 2023-06-02 → 2026-01-20 (373 trading days w/ BCD in
   force), enumerate positions with `[entry_date, exit_date)` containing
   that day. (Same-day rolls excluded — close AM, open PM = cash wash, not
   double-count.)
3. Compare daily aggregate debit vs P0's steady-state $37,046 baseline.
4. Compute daily opp cost = `debit × 10% / 365` per PM-ratified hurdle.

Outputs:
- `q081_p1_bcd_cash_timeline.csv` — 373 rows, one per BCD-active trading day
- `q081_p1_crowdout_events.csv` — 0 rows (header only)

---

## Findings

### 1. Sequential ladder structurally prevents crowd-out
21 BCD trades over 2.5y, mean hold 34 days. The roll-at-21-DTE convention
ensures only one position open at any time. Backtest's initial "9 crowd-out
days" all turned out to be same-day rolls (close + reopen on same date,
backtest sums both as in-force). After fixing to half-open interval
`[entry, exit)`, zero overlap.

### 2. But every single BCD position is operationally tight
Single BCD typical debit $23-25k against $37k cash baseline. Avg
consumption 66%; max 76%. PM has $12-14k slack while a BCD is open. Any
ADDITIONAL cash need (margin call, dividend reinvestment shortfall, BPS
opportunity that needs cash collateral, etc.) bites against thin slack.

### 3. Opportunity cost is real but small relative to mean PnL
$2,497 cumulative / 21 trades = $119/trade
Mean BCD PnL = $1,796/trade
Opp cost is 6.6% drag on gross PnL. Net BCD remains positive
($1,677/trade).

### 4. Worst trade unchanged
Worst BCD trade (-$3,248) is much larger than any plausible opp cost
adjustment. Tail risk dominates opp cost concerns for sizing decisions.

---

## Implications for verdict paths

| Path | Case post-P1 |
|---|---|
| **Conclusion 1 (cash budget cap)** | **WEAK**. No historical crowd-out under current 1-at-a-time ladder. A cap would only bite if matrix or sleeve rules ever allowed 2+ concurrent BCDs. |
| **Conclusion 2 (cash hurdle gate)** | **NEUTRAL, awaits P3**. Per-trade opp cost is small ($119). Whether the gate would have rejected any historical BCD depends on per-trade BCD ROE vs same-window QQQ ROE (P3). |
| **Status quo** | **DEFENSIBLE so far**. BCD net of opp cost still positive, no operational stress. |

**Forward**: P3's comparison of BCD per-trade ROE vs QQQ same-window ROE is
the decisive evidence. P1 alone does not warrant a SPEC change.

---

## Side observation (sizing, not matrix)

Avg 66% cash consumption per BCD is high. If PM ever wanted to run a BCD
alongside a different cash-consuming activity (e.g., dividend cycle, equity
rebalance, BPS that needs collateral), the $12k slack is thin. Could
consider sizing BCD smaller (lower BP budget per BCD → smaller debit →
lower cash hit). This is a separate optimization, not part of Q081's
matrix-selection scope.

---

## Files
- `q081_p1_bcd_cash_timeline.py` — script
- `q081_p1_bcd_cash_timeline.csv` — daily timeline
- `q081_p1_crowdout_events.csv` — empty (no events)
- `q081_p1_memo.md` — this file

---

## Next: P2

Compute per-trade BCD cash-ROE annualized:
- `cash_roe = pnl / debit × 365 / hold_days_calendar`
- Report mean / median / p25 / **p05 / p01** / worst
- Sub-bucket by IVP / VIX bucket (n small, report with caveat)
- Bootstrap CI for p05 (n=21 is borderline — G-review 1 candidate question)

Then schedule G-review 1 with 2nd quant on left-tail methodology before
moving to P3 hurdle comparison.
