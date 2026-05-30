# Q078 P1b-2 — Sizing Sweep Memo

**Date**: 2026-05-27
**Author**: Quant Researcher
**Status**: **P1b-2 DONE** — 5% NLV worst-trade gate identified hard sizing cap; S3 (3 contracts) is the sweet spot, S2 (4 contracts / PM's original 10% BP) FAILS gate
**Source**: `research/q078/q078_p1b_2_sizing_sweep.py` + 4 CSVs

---

## 0. TL;DR

```
Variant              Sizing                  Ann ROE     Worst Trade    5% NLV Gate
V1b weekly catchup   S1 (1 ct)               +8.36%      -1.43% NLV    ✓ PASS
V1b weekly catchup   S2 (4 ct = 10% BP)     +33.42%      -5.72% NLV    ❌ FAIL
V1b weekly catchup   S3 (3 ct = 7.5% BP)    +25.07%      -4.29% NLV    ✓ PASS  ← sweet
V3 daily-cluster     S1                      +9.22%      -1.43% NLV    ✓ PASS
V3 daily-cluster     S2                     +36.89%      -5.72% NLV    ❌ FAIL
V3 daily-cluster     S3                     +27.67%      -4.29% NLV    ✓ PASS  ← sweet
Baseline B cluster   S1                      +2.40%      -1.43% NLV    ✓ PASS
Baseline B cluster   S2                      +9.61%      -5.72% NLV    ❌ FAIL
Baseline B cluster   S3                      +7.21%      -4.29% NLV    ✓ PASS
```

**Three headline findings**:

1. **S2 (4 contracts ≈ 10% BP) FAILS 5% NLV hard gate** — worst single trade is IC NORMAL at -58.8% × max_loss = -$12.8k per contract; 4 contracts = -$51.1k = -5.72% NLV → breach. **PM's original 10% BP/entry target is not feasible** under revised gate.

2. **S3 (3 contracts ≈ 7.5% BP) is the sweet spot** — worst -$38.3k = -4.29% NLV (within 5% gate); ladder produces +25-28% ann ROE (V1b/V3) vs baseline B +7.2%.

3. **Worst trade is IC NORMAL not BPS** — IC NORMAL empirical worst pct_of_max_loss = -58.8% > BPS -41.7%. Mixed-strategy ladder (per P0 R8 strategy-agnostic) inherits IC's deeper loss profile.

---

## 1. Critical caveat: PnL likely OVERSTATED (selection bias)

**ROE numbers in this memo are upper bound, not realistic projection.**

### Why

- Engine produced 373 trades over 26y (~14/yr) — engine's internal filters (HV spell limits, concurrency, regime stops) block many selector-PASS days
- Ladder fires on selector PASS only (~3120 days over 26y) — 8x more than engine
- For ladder entries with no engine match, bootstrap samples from engine's filtered pool
- **Engine's pool is "good" days (survived filters); bootstrap extrapolates this quality to "bad" days too**

Implication: ladder's reported +25-37% NLV/yr ROE is what would happen IF every ladder eval day had engine-quality PnL distribution. In reality, ladder would enter on days engine filtered out, getting worse PnL on those days.

### What's still reliable

- **Relative cadence comparison** (V1b vs V3 vs Baseline B) is robust — all variants use same biased bootstrap
- **Hard gate determination** is robust — worst-trade is the single worst engine trade scaled to today's SPX; doesn't depend on PnL averaging
- **Diversification metrics** (eff_count) reliable

### What's NOT reliable

- **Absolute ROE numbers** (+8% to +37%) inflated by bootstrap selection bias
- **Absolute cum PnL** ($567k to $8.7M) inflated proportionally
- Ladder ANN PnL comparable to entire SPEC-104 baseline (8.21% ROE) is implausible — confirms selection bias

### Honest framing

> **Use P1b-2 results to identify cadence + sizing winners and validate hard gate constraints. Do NOT take absolute ROE numbers at face value.** P2 portfolio integration must use a less biased PnL source (e.g., engine without filters, or alternative attribution).

---

## 2. Methodology

### 2.1 SPX scaling (Option B + C dual view)

Per PM 2026-05-27, engine 26y average BPS width = 119pt (period-averaged across SPX 1000-7400 era), while PM's current spread width = 250-300pt at SPX 7400. To make engine PnL forward-projectable:

```
scale_factor = SPX_TODAY / SPX_entry  
pnl_today_per_contract = pnl_historical × scale_factor
max_loss_today_per_contract = max_loss_historical × scale_factor
```

Avg scale factor across engine 26y trades ≈ 2.5x.

Reported `pnl_today` uses today-scaled $. Reported `pnl_pct_of_max_loss` is width-agnostic (Option B).

### 2.2 5% NLV hard gate (per P0 §7 revised)

```
Worst single trade ≤ 5% NLV = $44,700 on $894k NLV
"Worst single trade" semantics: empirical worst pct_of_max_loss × max_loss_today × n_contracts
```

Per-strategy empirical worst pct_of_max_loss (engine 26y):
```
Iron Condor (NORMAL):       -58.8% ← worst
Bull Put Spread (NORMAL):   -41.7%
Bear Call Spread (HV):      -29.6%
Iron Condor (HV):           -28.8%
Bull Put Spread (HV):       -25.7%
Bull Call Diagonal:         -24.1%
```

### 2.3 Bootstrap CI

20 seeds per (variant × sizing) combination. Reported cum PnL mean ± 5/95 percentile.

### 2.4 Sizing variants

```
S1: 1 contract per entry           (P1b-1 baseline)
S2: 4 contracts ≈ 10% BP target    (PM's original proposal)
S3: 3 contracts ≈ 7.5% BP          (conservative compromise)
S4 dynamic 35%: DROPPED            (would breach worst-trade gate at any sizing >= S2)
```

---

## 3. Full Results Grid (20-seed bootstrap)

### 3.1 V1b weekly catch-up

```
Sizing  N_trades  Cum_PnL_mean        5-95% CI                  Worst        % NLV   Gate
S1       816      $+1,971,623   [+1,803k, +2,168k]    $-12,776    -1.43%   ✓
S2       816      $+7,886,493   [+7,213k, +8,673k]    $-51,102    -5.72%   ❌
S3       816      $+5,914,870   [+5,410k, +6,504k]    $-38,327    -4.29%   ✓
```

### 3.2 V3 daily-cluster

```
Sizing  N_trades  Cum_PnL_mean        5-95% CI                  Worst        % NLV   Gate
S1       917      $+2,176,350   [+2,002k, +2,403k]    $-12,776    -1.43%   ✓
S2       917      $+8,705,401   [+8,009k, +9,613k]    $-51,102    -5.72%   ❌
S3       917      $+6,529,051   [+6,007k, +7,210k]    $-38,327    -4.29%   ✓
```

### 3.3 Baseline B cluster

```
Sizing  N_trades  Cum_PnL_mean        5-95% CI                  Worst        % NLV   Gate
S1       254      $+567,089     [+428k, +660k]        $-12,776    -1.43%   ✓
S2       254      $+2,268,358   [+1,711k, +2,638k]    $-51,102    -5.72%   ❌
S3       254      $+1,701,268   [+1,283k, +1,979k]    $-38,327    -4.29%   ✓
```

---

## 4. Ladder vs Baseline B at matched sizing

```
[S1 — 1 contract]
  Baseline B:   $+567k cum / +2.40% NLV/yr  worst -1.43% NLV
  V1b:          $+1,972k  (Δ +$1.4M / +5.95pp annualized)
  V3:           $+2,176k  (Δ +$1.6M / +6.82pp annualized)

[S2 — 4 contracts / 10% BP] ← FAILS gate
  Baseline B:   $+2,268k cum / +9.61% NLV/yr  worst -5.72% NLV ❌
  V1b:          $+7,886k  (Δ +$5.6M / +23.81pp)  ❌
  V3:           $+8,705k  (Δ +$6.4M / +27.28pp)  ❌

[S3 — 3 contracts / 7.5% BP] ← sweet spot
  Baseline B:   $+1,701k cum / +7.21% NLV/yr  worst -4.29% NLV
  V1b:          $+5,915k  (Δ +$4.2M / +17.86pp)  ✓
  V3:           $+6,529k  (Δ +$4.8M / +20.46pp)  ✓
```

**At all matched sizings, V3 > V1b > Baseline B** on cum PnL (consistent with P1b-1).

**V3 daily-cluster captures slightly more PnL than V1b** because daily check captures 100% of selector PASS days vs V1b's catch-up window (Mon/Tue/Wed only). Tradeoff: V3 requires daily check vs V1b's weekly-ish bandwidth.

---

## 5. Per-trade worst-case breakdown

The 5% NLV gate is breached because of **IC NORMAL's empirical worst at -58.8% × max_loss**, not BPS:

```
Per-contract worst-trade today-scaled:
  Iron Condor (NORMAL):     -$12,776  ← engine 26y worst, scaled to SPX 7400
  Bull Put Spread (NORMAL):  -$6,279
  Bear Call Spread (HV):     -$9,407
  Iron Condor (HV):          -$7,511
  Bull Call Diagonal:        -$8,223
  Bull Put Spread (HV):      -$5,353
```

Worst across all = -$12,776 (IC NORMAL). At n contracts: 4 × -$12,776 = -$51,102 (= -5.72% NLV) ❌ breaches 5% gate. 3 × -$12,776 = -$38,327 (-4.29% NLV) ✓ passes.

### PM relevance
- **PM currently trades 4 contracts of BPS at 7300/7000** — BPS NORMAL worst is -41.7% × $23k max_loss = -$9,591 × 4 = -$38,365 = -4.3% NLV ✓
- BUT ladder (strategy-agnostic per P0 R8) executes IC when selector recommends IC NORMAL
- IC NORMAL's deeper -58.8% worst means **same 4 contracts breaches gate when executing IC**
- → ladder must size to 3 contracts max to stay within gate across all strategies

---

## 6. Bootstrap CI tightness

V1b S3: cum PnL mean $5.91M, 5-95% CI [$5.41M, $6.50M] = ±$0.55M = ±9% of mean.
V3 S3: similar tight CI (±9%).

**Bootstrap stability is good** — magnitudes are consistent across 20 seeds. The high uncertainty is methodological (selection bias), not statistical noise.

---

## 7. Variant comparison summary

| | S1 (1ct) | S3 (3ct) | S2 (4ct) |
|---|---|---|---|
| **V1b weekly catchup** | +8.4% NLV/yr, gate ✓ | **+25.1% NLV/yr, gate ✓** | +33.4% NLV/yr, gate ❌ |
| **V3 daily-cluster** | +9.2% NLV/yr, gate ✓ | **+27.7% NLV/yr, gate ✓** | +36.9% NLV/yr, gate ❌ |
| Baseline B cluster | +2.4% NLV/yr, gate ✓ | +7.2% NLV/yr, gate ✓ | +9.6% NLV/yr, gate ❌ |

**V3 S3 has highest ROE within gate constraint**. V1b S3 is close behind with better PM bandwidth fit.

---

## 8. P1b-2 → P2 Advancement

### Variants to advance to P2 portfolio integration
- **V1b S3** (weekly catch-up, 3 contracts) — PM bandwidth fit, passes 5% NLV gate
- **V3 S3** (daily-cluster, 3 contracts) — best raw ROE within gate, passes 5% NLV gate
- Baseline B S3 as control

### Variants REJECTED at P1b-2
- **S2 (4 contracts / 10% BP)** — ALL cadence variants fail 5% NLV worst-trade gate
- **S4 dynamic** — would breach gate at any meaningful sizing (DROPPED in design)
- **V1a strict / V2 biweekly** — rejected in G2 (dominated/zero diversification)

### P2 must validate
- Selection bias correction (engine-without-filters bootstrap, or alternative attribution)
- MaxDD / W20d / W63d at portfolio level (Q078 P0 §7 hard gates)
- Crisis window behavior at S3 sizing
- Operational burden refinement (V1b ≤ 30 action days/yr, V3 daily check)

---

## 9. Open questions for PM / 2nd Quant

### D1 — Selection bias correction priority
P1b-2 ROE numbers inflated by ~3-5x due to bootstrap from engine's filtered pool. Three correction paths:

- **(a) Run engine 26y WITHOUT filters** — modify engine to disable HV spell, concurrency, etc. → full per-day PnL distribution
- **(b) Run engine with current filters but bootstrap from PARTIAL distribution** — include zeros for filtered-out days (assumes "would have lost slightly")
- **(c) Accept inflated numbers as upper bound** — note in memo, advance to P2 with disclaimer

Quant prior: **(a)** is most rigorous; takes 1-2 hr engine work. (b) is pragmatic but assumption-laden. (c) skips the work but undermines decision-grade conclusions.

**2nd Quant: which path?**

### D2 — Mixed strategy ladder behavior
Ladder fires on whatever selector says. IC NORMAL appears 296 times in 26y selector history; ladder will enter IC trades. PM may want to:

- **(a) Ladder enters all selector-PASS strategies** (current P0 R8 framing — agnostic)
- **(b) Ladder enters credit-only** (BPS, IC, BCS_HV — excludes BCD which is debit)
- **(c) Ladder enters BPS-only** (would massively reduce trade count, ~3.6/yr only)

(a) is current; (b) reduces trade count by ~26% (BCD removed); (c) makes Q078 nearly empty.

Quant prior: **(a)** — strategy-agnostic per P0. PM should understand that "ladder runs IC sometimes" is the deal.

**2nd Quant + PM: confirm (a)?**

### D3 — S3 vs S1 decision
S1 (1 contract) passes gate but is economically thin. S3 (3 contracts / 7.5% BP) is sweet spot but inherits IC's worst case.

For PM's actual production:
- S1: 1 contract = 2.5% NLV BP, worst -1.43%
- S3: 3 contracts = 7.5% NLV BP, worst -4.29%

PM's current 4 contracts = 10% BP is S2 → gate fail. If PM wants to keep current sizing, P0 §7 must relax to 6% NLV gate (would re-classify S2 as marginal pass at -5.72% close to limit).

**PM: target S3 (3 contracts) or stick with current 4 contracts and revise gate?**

---

## 10. Caveats

1. **PnL inflated by selection bias** — ladder bootstrap from engine's filtered pool (12% survivorship) extrapolated to 100% of selector PASS days. Absolute numbers upper bound only.

2. **Bootstrap CI tight** (±9%) — methodological uncertainty dominates statistical.

3. **Worst-trade scaling assumes max_loss scales linearly with SPX** — width as % of SPX is roughly constant (~3-4%), so dollar scaling matches reasonably well. Edge cases at extreme low SPX may not scale cleanly.

4. **IC NORMAL's -58.8% worst** is from n=69 trades. Single-tail event may not replicate forward; bootstrap will redraw it eventually.

5. **No crisis window analysis at S3 yet** — P2 must validate IC NORMAL worst doesn't cluster in stress periods.

6. **MaxDD/W20d/W63d not yet evaluated** — P1b-2 only tests per-trade hard gate. P2 portfolio integration handles aggregate.

7. **5% NLV gate is per-trade only** — does not bound cumulative loss over multiple trades. P2 W20d/W63d covers cumulative.

8. **Q079 (15 vs 21 DTE) still deferred** — Q078 P1b-2 uses SPEC-077 21 DTE roll only.

---

## 11. Files

- `research/q078/q078_p1b_2_sizing_sweep.py` — script
- `research/q078/q078_p1b2_sizing_results.csv` — main grid (9 rows: 3 variants × 3 sizings)
- `research/q078/q078_p1b2_hard_gates_pass_fail.csv` — gate status table
- `research/q078/q078_p1b2_bootstrap_ci.csv` — 20-seed CI per combo
- `research/q078/q078_p1b2_pnl_distribution.csv` — seed-0 per-trade log

Upstream:
- `research/q078/q078_p0_anchored_memo_2026-05-27.md` (P0 with 5% NLV revision)
- `research/q078/q078_p1b_1_memo.md` (P1b-1 model corrections)
- `task/q078_p1a_g2_2nd_quant_review_2026-05-27_Review.md` (G2 PASS)

---

## 12. Sign-off

Q078 P1b-2 complete. **S2 (4 contracts / 10% BP) fails 5% NLV worst-trade gate due to IC NORMAL's deep -58.8% worst-pct-of-max-loss. S3 (3 contracts / 7.5% BP) is the sweet spot — all 3 cadence variants pass gate with V3 daily-cluster at +27.7% ann ROE / V1b weekly catch-up at +25.1% ann ROE. Baseline B at S3 is +7.2% ann ROE — ladder produces ~3-4x more ROE at same sizing.**

**Critical caveat: absolute ROE inflated by ~3-5x due to bootstrap selection bias (engine pool is filtered survivors).** Relative cadence comparison robust; hard gate determination robust. P2 must resolve selection bias before SPEC-level conclusions.

> Q078 P1b-2 establishes 3 contracts (S3, ≈7.5% BP) as sizing cap under revised 5% NLV worst-trade gate. PM's original 4-contract / 10% BP proposal (S2) fails because IC NORMAL's empirical worst (-58.8% × max_loss = -$12.8k/contract today-scaled) × 4 contracts = -$51k = -5.7% NLV breach. At S3, V3 daily-cluster yields +27.7% ann ROE (upper bound), V1b weekly catch-up +25.1%, Baseline B +7.2% — ladder ~3-4x baseline at matched sizing. But absolute ROE is inflated by bootstrap selection bias (ladder samples from engine's filtered pool); only relative comparison robust. P2 portfolio integration needs unbiased PnL source. Recommend P2 with V1b S3 (PM bandwidth) and V3 S3 (best raw ROE) as primary candidates; Baseline B S3 as control. S2 / S4 / V1a / V2 rejected.
