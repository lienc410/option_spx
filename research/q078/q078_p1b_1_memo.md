# Q078 P1b-1 — Model Corrections Memo

**Date**: 2026-05-27
**Author**: Quant Researcher
**Status**: **P1b-1 DONE** — engine-calibrated PnL **INVERTS P1a's PnL conclusion**; diversification finding confirmed and amplified
**Source**: `research/q078/q078_p1b_1_model_corrections.py` + 5 CSVs
**Supersedes**: P1a PnL numbers (analytical model had 3 bugs)

---

## 0. TL;DR — P1a finding REVERSED on PnL

```
Variant              Trades  CumPnL      AnnPnL%    MaxConc%  EffCount  HitRate
V1b_weekly_catchup    816   +$773,793   +3.28%     50.9%     3.17      68.8%
V3_daily_cluster      917   +$781,978   +3.31%     47.8%     3.42      68.8%
BaselineB_cluster     254   +$284,836   +1.21%     93.3%     1.15      72.0%
```

**Headline**:

| Metric | P1a (buggy) | P1b-1 (corrected) | Implication |
|---|---|---|---|
| Ladder vs Baseline B PnL | Ladder LOSES -$148k | **Ladder GAINS +$489k** | INVERTED |
| Ann PnL diff | -56% | **+2.07pp ROE/yr** | Engine actually generates ~3-4x P1a's analytical |
| Effective expiry count | 1.55 (V1b) | **3.17 (V1b)** | Diversification AMPLIFIED |
| Hit rate | 42-48% | **68.8%** | Engine: many small wins |
| Worst trade | $0 (BCD placeholder) | -$5,191 (real engine BPS) | Real tail surfaced |

**3 fixes (all applied)**:
- Fix 1: BCD placeholder → engine empirical PnL (n=94 BCD trades, avg +$1,103)
- Fix 2: Sizing uniform → Baseline B at 1 contract/entry (not 4)
- Fix 3: MTM bias → engine actual PnL (24-39% exact match) or bootstrap from empirical distribution

---

## 1. Methodology

### 1.1 Engine 26y trade log
Ran `backtest.engine.run_backtest("2000-01-01")` once → 373 trades:

```
Strategy                       n     avg PnL      median    worst       best        avg BP
Bull Put Spread (High Vol)    42   +$529        +$488     -$1,481     +$2,664     $6,843
Iron Condor (High Vol)       112   +$895        +$709     -$4,066     +$3,877    $13,858
Bear Call Spread (High Vol)   18   +$210        +$448     -$1,737     +$1,633     $6,533
Iron Condor                   69   +$602        +$611     -$2,349     +$3,381     $7,112
Bull Call Diagonal            94   +$1,103      +$377     -$4,539     +$10,664   $10,550
Bull Put Spread               38   +$867        +$1,012   -$5,191     +$3,349     $9,062
```

**Critical observation**: 38 BPS trades in 26y from engine vs 96 BPS "PASS days" in selector history. Engine has additional filters (regime stops, hv_spell, concurrency limits) beyond selector verdict. Ladder fires more often than engine.

### 1.2 PnL lookup logic
For each ladder eval-PASS day:
1. **Engine exact match** (±2 trading days, same strategy) → use engine's actual `exit_pnl_usd`
2. **Bootstrap fallback** → random sample from empirical distribution of that strategy
3. **No data** → skip (warning logged)

**PnL source breakdown**:
```
Variant            Engine exact  Bootstrap   Engine match %
V1b weekly catchup    195         621            24%
V3 daily-cluster      254         663            28%
Baseline B            99          155            39%
```

Baseline B has highest engine match rate (~39%) because its eval days (~10/yr) overlap more frequently with engine entries (which also cluster around quarterly windows). Ladder variants fire on ~30/yr and many of those days the engine internal filter blocks → bootstrap fills.

### 1.3 Uniform 1-contract sizing (View 1)
All variants use **1 contract per entry**. This is the cadence-isolated comparison. BP-normalized (View 2) deferred to P1b-2 sizing sweep.

### 1.4 Selector signal source
Same as P1a: `run_signals_only("2000-01-01")` → 6639 daily verdicts.

---

## 2. The Reversal — why ladder now wins PnL

Mechanical reason: **ladder fires more frequently than Baseline B at uniform sizing**.

```
Baseline B:  cluster proxy every ~30 cal days → 254 trades over 26y (9.6/yr)
V1b:         weekly catch-up + selector PASS  → 816 trades over 26y (30.9/yr)
V3:          daily-conditional + 5d gap       → 917 trades over 26y (34.7/yr)
```

At uniform 1-contract size, **trade count × avg PnL = total PnL**:
- Baseline B: 254 × $1,121 avg = $284k (high avg due to engine-match concentration)
- V1b: 816 × $948 avg = $774k (more trades, slightly lower avg from bootstrap noise)
- V3: 917 × $853 avg = $782k

**Why P1a got this backwards**:
P1a used "4 contracts/cluster" for Baseline B but "1 contract/entry" for Ladder, making Baseline B's total trade-contract count similar to Ladder's. At uniform 1-contract this asymmetry disappears.

---

## 3. Diversification finding AMPLIFIED

```
Variant              Mean MaxConc  Eff Count
V1b weekly catchup     50.9%       3.17
V3 daily-cluster       47.8%       3.42  ← BEST
BaselineB cluster      93.3%       1.15
```

P1a showed eff_count 1.36-1.61. P1b-1 shows **3.17-3.42**. Why higher?

Mechanism: with more trades (816 vs 560 for V1b), concurrent active positions span more expirations. Engine's BP per contract is much higher than my P1a analytical estimate → fewer concurrent positions per dollar means each expiry holds proportionally less concentration.

**Reading**: at uniform 1-contract scale, ladder produces ~3.2 effective expiries vs Baseline B's 1.15. **The diversification benefit is real and large**.

---

## 4. Tail behavior surfaced

```
Variant              Worst Trade   PnL Std (approx from worst)
V1b weekly catchup   -$5,191      (real BPS worst, n=816)
V3 daily-cluster     -$5,191      (same worst as V1b — likely same trade sampled)
BaselineB cluster    -$3,661      (smaller worst because fewer total trades)
```

Engine's worst BPS trade in 26y is **-$5,191** (Q42 era stress). This trade appears in ladder simulations because bootstrap samples it. Baseline B happens not to sample it in its smaller pool of 254 entries.

**Important**: this is sample-bound. Real worst-trade tail risk should be evaluated at scaled sizing in P1b-2 (S3/S4 may amplify worst-trade dollar impact).

---

## 5. BP utilization (uniform 1ct)

```
Variant              BP Mean (concurrent)  BP p95  % NLV mean  % NLV p95
V1b weekly catchup   $40,963              $85,681  4.6%        9.6%
V3 daily-cluster     $43,787              $89,292  4.9%       10.0%
BaselineB cluster    $12,105              $30,725  1.4%        3.4%
```

At 1 contract/entry sizing:
- Ladder uses ~4.6-4.9% NLV avg BP (mean concurrent)
- Baseline B uses 1.4% (fewer concurrent positions)

**To reach the 35% NLV selector strategy ceiling**, scaling factor needed:
- V1b: 35 / 4.6 = ~7.6x
- V3: 35 / 4.9 = ~7.1x

At 7x scale, all dollar metrics scale linearly. Ann PnL would be +3.28% × 7 = ~23% NLV/yr for V1b. That's not how it actually works — at larger sizing, worst-trade also scales (−$5,191 × 7 = −$36,337 = -4% NLV per trade, well above 1% NLV worst-trade limit). **P1b-2 sizing sweep will surface this realistic tradeoff**.

---

## 6. PM operational burden (R-additional from P0)

```
Variant              Entries/yr  Action days/yr
V1b weekly catchup    30.9        30           ← ≤1/wk, occasional Tue/Wed
V3 daily-cluster      34.7        35           ← Daily check, ~1 entry/8 days
BaselineB cluster      9.6         9           ← Sparse cluster days
```

- V1b: 30 action days/yr fits PM 1hr/day, mostly Mondays
- V3: requires daily selector check (PM 1hr/day OK), 35 trade days
- Baseline B: lowest operational burden but worst diversification

Per G2 §8 "operational burden as soft promotion gate": V1b and V3 both within bandwidth. V2 bi-weekly and V1a strict already rejected in G2.

---

## 7. Headline finding & limitations

### Headline
**At uniform 1-contract sizing, ladder (V1b or V3) generates 2-3x more cumulative PnL than Baseline B over 26y, with 3x better expiry diversification.** Annualized ROE delta is +2.07pp (V1b) to +2.11pp (V3) over Baseline B at this scale.

### Critical limitations

1. **Bootstrap sample noise**: 76% of V1b ladder entries are bootstrap (only 24% engine-matched). Bootstrap draws from small per-strategy empirical samples (n=38 BPS, 69 IC, 94 BCD, etc.). At smaller samples, bootstrap variance is high.

2. **Uniform 1-contract is NOT PM's actual sizing**. PM proposed 10% BP/entry. P1b-2 will run S2 (10%), S3 (15%), S4 (dynamic) to see if scaling preserves PnL advantage or hits tail limit.

3. **Worst trade -$5,191 is real but limited sample**: at 7x scale = -$36k = -4% NLV. Breaches Q078 P0 §7 "worst single trade ≤ 1% NLV". P1b-2 must size to keep worst < 1% NLV.

4. **Strategy mix shifts with cadence**: Baseline B's cluster proxy (every 30d) tends to land on BCD days (large strategy in selector). V1b/V3's higher frequency includes more IC and HV variants. The "average PnL per strategy" advantage Baseline B has on engine-match is partially strategy mix effect.

5. **Engine match rate 24-39%** — most ladder entries don't have an exact engine trade to match. The bootstrap assumption "ladder entry has similar PnL distribution as engine entry of same strategy" is plausible but unverified.

6. **No transition forensic in P1b-1** — P3 will probe stress-front behavior.

7. **Engine's own selectivity**: engine produces 373 trades over 26y = 14/yr. That's even sparser than Baseline B's 9.6/yr. Engine has stricter entry rules than selector PASS alone.

---

## 8. P1a vs P1b-1 comparison table

```
Metric                P1a (buggy)         P1b-1 (engine-calibrated)
PnL model             Analytical mtm_at   Engine actual + bootstrap
BCD treatment         $0 placeholder      Empirical distribution
Baseline B sizing     4 contracts/cluster 1 contract/cluster (uniform)
MTM at 21 DTE         (20/30)^0.7 = 0.76  Engine realized
V1b cum PnL           +$188k              +$774k       (4.1x higher)
V1b avg per trade     +$240               +$948        (4.0x higher)
V1b worst trade       $0                  -$5,191      (real tail surfaced)
V1b hit rate          48.0%               68.8%        (engine has more small wins)
V1b eff_count         1.55                3.17         (2x better diversification)
BaselineB cum PnL     +$267k              +$285k       (similar — uniform 1ct fix)
BaselineB max_conc    100.0%              93.3%        (sample-bound)
Ladder vs Baseline    LOSES               WINS +$489k  (REVERSED)
```

P1a is **fully superseded** for PnL conclusions. Diversification direction was right but magnitude was understated.

---

## 9. P1b-1 → P1b-2 recommendation

### Greenlight P1b-2 sizing sweep

Per 2nd Quant G2 §11 P1b success criteria, P1b-1 satisfies preliminary gates:
- ✓ Expiry concentration materially improves (eff_count 3.17 vs 1.15 baseline)
- ✓ No PnL collapse after fixes (REVERSE: ladder PnL much higher)
- ✓ Operational burden acceptable (V1b: 30 action days/yr)
- ⚠ Worst trade -$5,191 needs sizing constraint (P1b-2 must cap)

### P1b-2 sizing variants to run

```
Cadence: V1b weekly catch-up (primary), V3 daily-cluster (alternative), Baseline B (control)
Sizing:
  S1: 1 contract/entry         (P1b-1 baseline)
  S2: 10% BP target            (PM original proposal)
  S3: 15% BP target            (selector default)
  S4: dynamic to fill 35% ceiling (CAUTION per G2 §9)

For each combo:
  - Net ann ROE
  - MaxDD / Worst 20d / Worst 63d (V1/V2/V3 hard gates)
  - Worst single trade per Q078 P0 §7 (≤1% NLV = ≤$8,940)
  - BP utilization timeline
  - Expiry concentration (eff_count vs Baseline B)
  - Operational burden
  - Crisis window behavior
```

### Hard gate enforcement at sizing

```
At each sizing level S, REJECT if:
  Worst single trade > 1% NLV = > $8,940
  W20d degradation > +0.25pp
  W63d degradation > +0.25pp
  Any crisis-window cum loss > $10k
```

S4 dynamic almost certainly fails worst-trade at 7x scale (since 1ct worst is already -$5,191).

S2 10% BP: contracts = 0.10 × $894k / $9k per BPS = ~10 contracts/entry. Worst trade × 10 = -$51,910 = -5.8% NLV. **Breaches 1% NLV easily.**

This suggests P1b-2 may show:
- Cadence advantage (PnL improvement) is REAL at small sizing
- But ladder cannot be scaled to PM's "10% BP" target without breaching tail limits
- Honest outcome: **DOCUMENT ladder discipline at sub-1% NLV worst-trade size**, not "ladder enables 10% BP utilization"

This would be the cash-equivalent DOCUMENT verdict from a different angle.

---

## 10. Open questions for PM/2nd Quant

### D1 — Worst-trade limit interpretation
P0 §7 says "Worst single trade ≤ 1% NLV". At engine-realized -$5,191 worst BPS trade:
- 1 contract: -0.58% NLV ✓
- 2 contracts: -1.16% NLV ❌
- More aggressive sizing breaches

Should P1b-2 enforce per-entry max contracts to keep worst-trade < 1% NLV? Quant prior: **yes**, this is the right hard gate.

### D2 — Bootstrap noise tolerance
76% of V1b ladder entries use bootstrap from small per-strategy samples (n=38-94). Should we run multiple seeds and report PnL distribution + CI?

Quant prior: **for P1b-2 yes, 20-seed bootstrap CI is essential**.

### D3 — Engine vs selector cadence
Engine produces 373 trades over 26y (14/yr) — significantly sparser than ladder's 30-34/yr at selector PASS rate. Engine's internal filters block some PASS days.

Should ladder respect engine's filters too (= effectively running engine cadence) or just selector PASS (Quant current approach)?

Quant prior: **selector PASS only**. Engine's filters were designed for engine's own cadence; transplanting to ladder may over-restrict.

**2nd Quant: confirm or override?**

---

## 11. Files

- `research/q078/q078_p1b_1_model_corrections.py` — script
- `research/q078/_engine_trades_26y_cache.csv` — 373 engine trades
- `research/q078/q078_p1b1_engine_trades.csv` — engine 26y trade log (export)
- `research/q078/q078_p1b1_empirical_pnl_distribution.csv` — per-strategy stats
- `research/q078/q078_p1b1_cadence_results_corrected.csv` — corrected summary
- `research/q078/q078_p1b1_entry_timing.csv` — per-entry log with pnl_source
- `research/q078/q078_p1b1_expiry_dispersion.csv` — diversification metrics
- `research/q078/q078_p1b1_bp_timeline.csv` — weekly BP snapshots

Upstream:
- `task/q078_p1a_g2_2nd_quant_review_2026-05-27_Review.md` — G2 PASS w/ 3 fixes
- `research/q078/q078_p1a_memo.md` — P1a (now superseded for PnL)

---

## 12. Sign-off

Q078 P1b-1 complete. **Engine-calibrated PnL reverses P1a's ladder-vs-Baseline-B comparison**: ladder now generates +2.07pp annualized ROE over Baseline B at uniform 1-contract sizing, with 3x better expiry diversification (eff_count 3.17-3.42 vs 1.15). Real worst-trade tail surfaced at -$5,191 (BPS). Operational burden acceptable for both V1b and V3.

**But: scaling to PM's proposed 10% BP per entry breaches worst-trade limit (1% NLV) easily**. P1b-2 sizing sweep will quantify the size-vs-tail tradeoff and likely show ladder economics are constrained to small sizing.

> Q078 P1b-1 fixes three P1a limitations (BCD placeholder, sizing non-normalized, MTM bias) by using engine's 26y per-trade PnL log (373 trades) with bootstrap fallback. At uniform 1-contract sizing, V1b weekly catch-up and V3 daily-cluster both materially outperform Baseline B on PnL (+$489-497k cum, +2.07-2.11pp annualized) AND diversification (eff_count 3.17-3.42 vs 1.15). The cadence advantage is real. But engine worst-trade -$5,191 means scaling to PM's 10% BP/entry breaches the 1% NLV hard gate. P1b-2 sizing sweep must enforce worst-trade < 1% NLV as constraint, and will likely show ladder's PnL advantage holds only at sub-1ct equivalent sizing. Outcome may still be DOCUMENT (operational discipline) rather than PROMOTE.
