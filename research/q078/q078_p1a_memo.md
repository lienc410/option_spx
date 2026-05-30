# Q078 P1a — Cadence Attribution Memo

**Date**: 2026-05-27
**Author**: Quant Researcher
**Status**: **P1a DONE** — cadence comparison complete; expiry-concentration tradeoff identified; P1b sizing study unlocked
**Source**: `research/q078/q078_p1a_cadence_attribution.py` + 5 CSVs
**G2 light review**: optional per P0 §10 schedule

---

## 0. TL;DR

```
Variant              n_eval  pass%   n_trades  entries/yr  cum_PnL   max_conc%  eff_count
V1a_weekly_strict     1245   46.2%      560      21.2     +$118k     82.3%      1.36
V1b_weekly_catchup    1378   59.2%      785      29.7     +$188k     75.7%      1.55
V2_biweekly_strict     623   46.5%      285      10.8      +$64k     99.9%      1.00
V3_daily_cluster       917  100.0%      883      33.5     +$224k     73.5%      1.61
BaselineB_cluster     254  100.0%      976      37.0     +$267k    100.0%      1.00
```

**Three headline findings**:

1. **Selector PASS rate ~46% on Mondays** — matches SPEC-106 audit (50% cells gated). PM's intuition of "weekly entry" is gated by selector ~half the time.

2. **Ladder DOES improve expiry concentration**:
   - Baseline B: max_conc 100%, eff_count 1.00 (single-day expiry, same as PM observed 8-at-6/18)
   - V1b weekly catch-up: max_conc 76%, eff_count 1.55 (≈ 1.5 effective expiries)
   - V3 daily-cluster: max_conc 73%, eff_count 1.61 (≈ 1.6 effective expiries) ← BEST

3. **But ladder REDUCES absolute cum PnL** at fixed per-entry sizing:
   - Baseline B captures more trades-per-PASS-day (burst of 4 contracts) vs Ladder 1 contract
   - V1a -56% cum PnL vs Baseline B; V1b -29%; V3 -16%; V2 -76%
   - This is at 1-contract-per-entry simulation; **at sized comparison (P1b) may differ**

**Quant verdict on P1a**:
- Ladder vs cluster tradeoff is **diversification vs absolute PnL**
- V3 daily-cluster and V1b catch-up are top candidates by diversification
- V2 bi-weekly is dominated (same max_conc as Baseline B but less PnL)
- Sizing not yet normalized; P1b will resolve this dimension

---

## 1. Methodology

### 1.1 Sample
- Selector signals run across 26.4y (2000-01-03 → 2026-05-27), n=6639 daily snapshots
- All variants use same selector verdicts (no parallel simulation drift)

### 1.2 Strategy mix in historical sample

```
'Reduce / Wait':                3520 days  (53.0%)  → ladder skips
'Bull Call Diagonal':           1747 days  (26.3%)  → BCD (debit, PnL placeholder)
'Iron Condor (High Vol)':        607 days  ( 9.1%)
'Iron Condor':                   296 days  ( 4.5%)
'Bull Put Spread (High Vol)':    291 days  ( 4.4%)
'Bull Put Spread':                96 days  ( 1.4%) ← PM's current cell
'Bear Call Spread (High Vol)':    82 days  ( 1.2%)
```

**Critical observation**: pure "Bull Put Spread" (NORMAL+NEUTRAL_IV+BULLISH) appears only **96 days over 26y** (3.6/yr). PM's intuition of "weekly BPS" entry is **5-6x more frequent than historical opportunity for that exact cell**. Most ladder fires are BCD or HV variants.

### 1.3 Per-trade simulation
- BPS / IC: analytical short spread, SPEC-077 21 DTE roll + 60% profit take min 10d held, forced exit on stress (2x slippage + IV+20% shock)
- BCD (1747 days, 26% of all PASS days): **PnL placeholder = $0** (P1a limitation; debit math not yet modeled)
- 1 contract per entry (Ladder) / 4 contracts per cluster (Baseline B)

### 1.4 Known limitations
1. **BCD placeholder PnL=$0** → "worst trade $0" artifact across all variants (BCD trades dominate worst). Real BCD PnL would be different.
2. **Sizing not normalized between Ladder and Baseline B** — Baseline B uses 4 contracts/cluster, Ladder uses 1 contract/entry. P1b sizing study fixes this.
3. **Weekly BP/expiry snapshot grid (1378 dates) misses intra-week peaks** — fine for diversification trend, less precise for daily BP utilization.

---

## 2. Selector PASS Rate by Cadence — KEY FINDING

```
Cadence            Eval days  PASS days  PASS rate
V1a weekly strict   1245       575       46.2%
V1b weekly catchup  1378       816       59.2%
V2 biweekly strict   623       290       46.5%
V3 daily cluster     917       917      100.0% (filtered)
Baseline B cluster   254       254      100.0% (filtered)
```

**Observation**: V1b catch-up has **+13pp PASS rate** vs V1a strict because it can capture Tue/Wed PASS days when Monday is WAIT. This is real value of catch-up rule.

**Interpretation**: If PM only checks Monday, ~half the time selector says WAIT and the week is skipped. Catch-up to Tue/Wed reduces this from 54% wait to 41% wait.

---

## 3. Expiry Concentration Tradeoff — THE STRUCTURAL FINDING

```
Variant            max_conc%   eff_count   reduction vs Baseline B
V1a weekly strict   82.3%       1.36       -17.7pp / +0.36 eff
V1b weekly catchup  75.7%       1.55       -24.3pp / +0.55 eff
V2 biweekly         99.9%       1.00       -0.1pp / +0.00 eff   (dominated)
V3 daily cluster    73.5%       1.61       -26.5pp / +0.61 eff   ← best
Baseline B cluster 100.0%       1.00       0pp / 0pp baseline
```

**Reading**:
- Baseline B = current PM behavior (all 8 spreads at 6/18) = 100% max_conc, eff_count 1.0
- V3 daily-cluster reduces max_conc 26.5pp and adds 0.6 effective expiries
- V1b weekly catch-up gets 24.3pp reduction and +0.55 eff_count — close to V3 with simpler ops
- V2 bi-weekly gives **zero diversification benefit** (entries too sparse to overlap, single cohort dominates)

**Eff_count interpretation**:
- 1.00 = all trades in one expiry
- 1.55 = effectively 1.5 expiries (e.g., 60% / 40% split)
- 1.61 = effectively 1.6 expiries
- 2.00 = effectively 2 evenly-split expiries

V3/V1b deliver ~1.6 effective expiries on average. **Not full 4-expiry diversification** because:
- Selector PASS rate ~46% means many weeks skip
- 21 DTE roll closes positions before they overlap with later cohorts much
- Active concurrent position count is typically 1-2, not 4

---

## 4. PnL Tradeoff — RAW COMPARISON

```
Variant            Cum PnL    Avg/trade   Entries/yr  Annualized $/yr
V1a weekly strict  +$118,171   +$211       21.2        +$4,476/yr
V1b weekly catchup +$188,144   +$240       29.7        +$7,127/yr
V2 biweekly         +$64,491   +$226       10.8        +$2,443/yr
V3 daily cluster   +$223,519   +$253       33.5        +$8,467/yr
Baseline B cluster +$266,853   +$273       37.0        +$10,107/yr  ← highest
```

**Important caveat**: this is at **1 contract per entry** for Ladder and **4 contracts per Baseline B cluster day**. Comparison is at fixed contract scale, NOT fixed BP utilization.

If we normalize to "same BP-days consumed":
- Baseline B uses 4× more contracts per active day → fewer active days needed for same BP-days
- Ladder spreads contracts across more days → more entries but smaller positions
- At equivalent total BP-days, Baseline B and Ladder should produce similar gross PnL

**P1b sizing study** will normalize this comparison.

---

## 5. Trade Frequency vs PM Bandwidth

```
Variant            Entries/yr  Action days/yr
V1a weekly strict    21.2        21          ← 1 day/wk avg, manageable
V1b weekly catchup   29.7        30          ← ≤1 day/wk, occasional Tue/Wed
V2 biweekly          10.8        11          ← 1 day every 5 weeks
V3 daily cluster     33.5        34          ← 1 day every ~7 calendar days
Baseline B cluster   37.0         9          ← 4 entries on ~9 cluster days
```

**Operational note**: V3 daily-cluster requires daily selector check (PM 1hr/day OK), V1a/V1b are weekly. Baseline B is "infrequent burst" — fewer action days but more decisions per action.

V1b is the most realistic for PM (≤30 action days/yr, mostly Mondays, occasional Tue/Wed when Monday WAIT).

---

## 6. BP Utilization — Insufficient signal at 1-contract

```
Variant            BP mean    BP p95     %NLV mean   %NLV p95
V1a weekly strict   $742      $2,500     0.08%       0.28%
V1b weekly catchup  $941      $2,809     0.11%       0.31%
V2 biweekly         $373      $1,250     0.04%       0.14%
V3 daily cluster   $1,011     $3,750     0.11%       0.42%
Baseline B          $989      $5,000     0.11%       0.56%
```

At 1-contract-per-entry, BP utilization is **trivially small** (<1% NLV). All values are far below the 35% strategy ceiling.

**This confirms P0 §0 caveat**: BP utilization improvement is NOT automatic. Even daily-conditional ladder produces only ~0.4% NLV BP utilization at 1-contract scaling. To reach research baseline 35% would require ~88 contracts per active concurrent position — that's a P1b sizing study question, not a cadence-rule property.

---

## 7. Critical Caveats / Limitations

1. **BCD placeholder PnL = $0** → worst-trade $0 across all variants. Real BCD trades (1747 days, 26% of PASS) have unknown PnL signature. P1a cannot validate full ROE comparison.

2. **Sizing not normalized** — Baseline B uses 4 contracts/cluster, Ladder 1/entry. P1b sizing study will normalize.

3. **96 BPS days in 26y** — pure "Bull Put Spread" cell (PM's current focus) is rare. Most ladder fires are BCD or HV variants. Ladder is effectively a "whatever selector says" execution layer, not "BPS-only ladder".

4. **Per-trade mtm too optimistic** — high time_decay factor at d_off=10 (where 21 DTE roll fires) makes PnL skew positive. Real production execution may have different exit MTM.

5. **No transition forensic in P1a** — Q078 P3 will probe stress-front-edge behavior.

6. **PM observation match**: real PM behavior (8 at 6/18) matches Baseline B max_conc 100%, eff_count 1.00 — the simulated baseline is realistic.

---

## 8. P1a Findings vs P0 Pre-decision Pre-rejects

P0 said:
> "Ladder may improve expiry dispersion without improving average BP utilization. BP utilization improvement is an empirical question, not an assumption."

**P1a confirms BOTH halves**:
- ✓ Ladder improves expiry dispersion (eff_count 1.36-1.61 vs Baseline B 1.00)
- ✓ Ladder does NOT improve BP utilization at fixed contract size
- ✓ "Filling 80% cap via weekly ladder" is structurally not achievable at 1 contract/entry (and probably not without large sizing increase)

---

## 9. P1a → P1b Recommendation

### Top cadence candidates for P1b sizing study

| Rank | Variant | Why |
|---|---|---|
| 1 | **V1b weekly catch-up** | Best PM-bandwidth fit (≤30 action days/yr) + 24.3pp max_conc reduction + 0.55 eff_count |
| 2 | **V3 daily-cluster** | Best diversification (eff_count 1.61) but requires daily check |

### Rejected from P1b

- V1a weekly strict: dominated by V1b (catch-up captures more without significant ops cost)
- V2 bi-weekly: zero diversification benefit (eff_count 1.00) — dominated
- Baseline B (cluster): keeps as baseline comparator, not P1b candidate

### P1b scope (when greenlit)

```
Apply V1b + V3 to sizing variants:
  S1: 1 contract/entry (current baseline)
  S2: contracts = round(0.10 × NLV / max_loss) — 10% BP target (PM original)
  S3: contracts = round(0.15 × NLV / max_loss) — selector default
  S4: dynamic = contracts to fill current capacity headroom to strategy ceiling 35%

Measure:
  ΔROE vs Baseline B normalized BP utilization
  Tail behavior (W20d / W63d degradation)
  Operational burden (action days/yr × contracts/action)
```

---

## 10. Action Items

- [x] P1a cadence + cluster rule done
- [ ] PM: review P1a findings, decide if P1b sizing worth running
- [ ] Quant (if PM approves P1b): fix BCD placeholder, normalize sizing, run sizing sweep
- [ ] Optional G2 light review with 2nd Quant

### Open questions for PM/2nd Quant before P1b

- D1: Is 1-contract → 10% BP sizing scaling valid? (i.e., scaling PnL linearly may overstate at large sizes due to liquidity)
- D2: Should P1b also test "Baseline B + sized to match Ladder" for fair comparison?
- D3: Is BCD modeling needed for Q078 conclusions, or "BPS+IC ladder" focus sufficient?

---

## 11. Files

- `research/q078/q078_p1a_cadence_attribution.py` — script
- `research/q078/_signal_history_cache.csv` — selector signal history (cached)
- `research/q078/q078_p1a_cadence_results.csv` — main summary (5 rows)
- `research/q078/q078_p1a_expiry_dispersion.csv` — max_conc + eff_count per variant
- `research/q078/q078_p1a_selector_pass_rate.csv` — PASS rate per variant
- `research/q078/q078_p1a_entry_timing.csv` — per-trade log
- `research/q078/q078_p1a_bp_timeline.csv` — weekly BP snapshots

Upstream:
- `task/q078_framing_2nd_quant_review_packet_2026-05-27.md`
- `task/q078_framing_2nd_quant_review_2026-05-27_Review.md`
- `research/q078/q078_p0_anchored_memo_2026-05-27.md`

---

## 12. Sign-off

Q078 P1a cadence attribution done. Ladder structurally improves expiry diversification (eff_count 1.36-1.61 vs Baseline B 1.00). PnL at fixed contract scale is lower vs Baseline B due to fewer contracts/PASS day; P1b sizing study will normalize this. V1b weekly catch-up + V3 daily-cluster are top P1b candidates. Pure BPS opportunities are rare (96 days in 26y); most ladder fires are BCD/HV variants. BCD PnL placeholder is the main P1a limitation — P1b should resolve before final conclusions.

> Q078 P1a confirms: (1) ladder cadence rules (V1b catch-up / V3 daily-cluster) improve expiry diversification (eff_count +0.5-0.6 vs single-expiry Baseline B) but (2) do not automatically improve BP utilization — that's a sizing question deferred to P1b. (3) PM's "weekly BPS" intuition is 5-6x more frequent than historical pure-BPS opportunity (96 days in 26y); most ladder entries will be BCD/IC/HV variants per selector. (4) V2 bi-weekly is dominated (zero diversification gain). (5) V1b catch-up is the best fit for PM 1hr/day bandwidth. Recommend P1b sizing study with V1b + V3 only. BCD placeholder limitation must be resolved before P3 transition forensic.
