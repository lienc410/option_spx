# Q078 P1b (P1b-1 + P1b-2) — G2.5 Light Review Packet

**Date**: 2026-05-28
**Author**: Quant Researcher
**Reviewer**: 2nd Quant
**Type**: G2.5 light review (optional per P0 §10) — between P1b sizing study and P2 portfolio integration
**Decision sought**: confirm D1 (selection bias path), D2 (mixed-strategy framing), D3 (sizing target); greenlight P2

---

## 0. TL;DR

P1b-1 fixed all 3 G2 limitations (BCD placeholder, sizing non-uniform, MTM bias) by using engine 26y per-trade PnL log + bootstrap fallback. **P1a's PnL conclusion REVERSED**: at uniform 1-contract sizing, V1b/V3 produces 3-4x more cum PnL than Baseline B, with eff_count 3.17-3.42 vs 1.15.

P1b-2 ran sizing sweep with **5% NLV worst-trade gate** (revised from 1% per PM 2026-05-27, aligned with PM's empirical 4-contract risk tolerance). **S2 (4 contracts ≈ 10% BP) FAILS 5% NLV gate** due to IC NORMAL's deep -58.8% empirical worst-pct-of-max-loss; **S3 (3 contracts ≈ 7.5% BP) is the sweet spot**.

```
P1b-2 sweep summary (SPX-scaled to 7400):
Variant       S1 (1ct)     S3 (3ct)         S2 (4ct)
V1b           +8.4% / ✓   +25.1% / ✓ ←    +33.4% / ❌
V3            +9.2% / ✓   +27.7% / ✓ ←    +36.9% / ❌
Baseline B    +2.4% / ✓   +7.2%  / ✓      +9.6%  / ❌
```

**Critical caveat**: PnL inflated ~3-5x by bootstrap selection bias (engine pool is filtered survivors at 12% rate vs ladder's 100% selector PASS). Relative cadence comparison robust; absolute ROE not decision-grade.

---

## 1. What P1b-1 fixed

Per G2 PASS 2026-05-27 required 3 fixes:

| Fix | Method | Result |
|---|---|---|
| BCD placeholder PnL=$0 | Use engine 26y 94 BCD trades, avg +$1,103/contract | BCD now contributes realistic PnL distribution |
| Sizing non-uniform | Baseline B at 1 contract/entry (same as Ladder) | Apples-to-apples cadence comparison |
| MTM analytical bias (76% theta capture) | Use engine actual `exit_pnl_usd` (24-39% exact match) + bootstrap fallback | Realistic theta + tail behavior |

**Effect**: P1a's "Ladder LOSES PnL vs Baseline B" REVERSED to "Ladder WINS +$489k cum / +2.07pp annualized" at uniform 1-contract.

---

## 2. What P1b-2 produced

### 2.1 SPX scaling (Option B+C dual view per PM 2026-05-27)
- Engine 26y BPS avg width = 119pt at SPX 1000-7400 mixed
- PM today at SPX 7400 with 0.30/0.15δ delta target = 250-300pt width
- Scale factor = SPX_TODAY / SPX_entry, avg ≈ 2.5x across 26y
- Report dual: `pnl_pct_of_max_loss` (width-agnostic, Option B) + `pnl_today_scaled $` (Option C)

### 2.2 5% NLV gate failure points
Per-contract empirical worst (today-scaled):
```
Iron Condor (NORMAL):     -$12,776  ← deepest worst
Bull Put Spread (NORMAL):  -$6,279
Bear Call Spread (HV):     -$9,407
Iron Condor (HV):          -$7,511
Bull Call Diagonal:        -$8,223
Bull Put Spread (HV):      -$5,353
```

Mixed-strategy ladder inherits IC NORMAL's -$12.8k worst:
- 1 contract: -1.43% NLV ✓
- 3 contracts (S3): -4.29% NLV ✓
- **4 contracts (S2 = PM original 10% BP): -5.72% NLV ❌**

### 2.3 Headline ranking at S3

```
V3 daily-cluster S3:    +27.7% ann ROE (upper bound)
V1b weekly catchup S3:  +25.1% ann ROE
Baseline B cluster S3:  +7.2% ann ROE
```

Both ladders ~3.5-3.9x baseline at matched sizing. V3 marginally higher (more entries) but requires daily check.

---

## 3. Critical methodology issue — bootstrap selection bias

Engine produces 373 trades over 26y (~14/yr). Selector PASS days = ~3120 (~118/yr). **Engine internal filters block 88% of PASS days** as bad-quality entries. 

Ladder enters on selector PASS only (no engine filters). For each ladder entry, bootstrap pulls PnL from engine's pool — but engine's pool is FILTERED SURVIVORS (the "good" days that passed engine's gates).

**Consequence**: bootstrap extrapolates "engine-quality" PnL to all selector PASS days, systematically overestimating ladder's true PnL. The ~3-5x ROE inflation in P1b-2 numbers vs realistic baseline.

### Quantitative estimate
Engine 26y total PnL at average sizing (~10 contracts) ≈ $4.4M over 26y = ~$169k/yr = ~19% NLV/yr. But this is at engine's smaller cadence (14 trades/yr) — at ladder's larger cadence (~30/yr) with bootstrapped engine quality, PnL scales linearly to ~50% NLV/yr.

True ladder ROE realistic estimate (manually deflated):
- Ladder enters 88% of selector PASS days that engine filtered out
- Assume those days have 50% of engine-quality PnL (rough guess — likely zeros + losses)
- Realistic V1b S3 ≈ 25% × 0.4 = ~10% NLV/yr (still material)
- Realistic Baseline B S3 ≈ 7.2% × 0.5 = ~3.6% NLV/yr (cluster strategy is closer to engine cadence)
- Realistic ladder advantage: ~+6pp vs baseline (vs reported +18pp)

Still potentially material but not the dramatic +20pp shown.

---

## 4. Three decisions for 2nd Quant

### D1 — Selection bias correction (most important)

Three paths to resolve:

**(a) Run engine 26y WITHOUT filters** — modify `run_backtest` to disable HV spell, concurrency limit, regime stops → 100% of selector PASS days produce engine-quality PnL. Then bootstrap is unbiased.
- Effort: ~1-2 hr engine work + re-run
- Output: clean P2 with no selection bias caveat

**(b) Engine filters preserved but bootstrap from PARTIAL distribution** — include zeros for filtered-out days as proxy.
- Effort: ~30 min code change
- Output: more conservative P2 but assumes "filtered days would have lost slightly"
- Assumption-laden

**(c) Accept inflated numbers as upper bound** — note in P2 memo, advance with disclaimer.
- Effort: zero
- Output: P2 conclusions decision-uncertain; PROMOTE / REJECT may not be reliable

**Quant prior: (a)** — only path that produces decision-grade P2. (b) is band-aid. (c) undermines Q078.

**2nd Quant: confirm (a)?**

### D2 — Mixed-strategy ladder confirmation

P0 R8 says ladder is strategy-agnostic (executes whatever selector recommends). P1b results show this means ladder enters:
- BCD on 1747 days (26% of all PASS) ← LOW_VOL regime debit
- IC HV on 607 (9%)
- IC NORMAL on 296 (4.5%)
- BPS HV on 291 (4.4%)
- BPS NORMAL on 96 (1.4%)
- BCS HV on 82 (1.2%)

PM's mental model: "weekly BPS ladder". Reality: ladder mostly does BCD (debit, LOW_VOL) and IC, rarely BPS.

Three options:
- **(a) Strategy-agnostic (current P0 R8)** — ladder runs IC/BCD/HV variants per selector
- (b) Credit-only — exclude BCD (debit). Reduces trade count by ~26%.
- (c) BPS-only — trade count drops to ~3.6/yr; Q078 nearly empty

**Quant prior: (a)** — strategy-agnostic. PM should understand "ladder runs IC sometimes" is the deal. Worst-trade gate enforcement ensures no surprise tail.

**2nd Quant + PM (implicit): confirm (a)?**

### D3 — Sizing target for P2

Three sizing options remain:
- **S1 (1 contract)**: -1.43% NLV worst, +9% ann ROE (upper bound) — too small to move PM portfolio meaningfully
- **S3 (3 contracts / 7.5% BP)**: -4.29% NLV worst, +25-28% ann ROE — passes 5% gate
- ~~S2 (4 contracts / 10% BP)~~: -5.72% NLV worst — FAILS 5% gate

PM currently runs 4 contracts at BPS 7300/7000 (BPS-only, not full ladder). For BPS-only worst: -41.7% × $23k × 4 = -$38.4k = -4.3% NLV ✓ — within gate.

If PM wants to keep 4-contract sizing, two options:
- **(α) Accept S3 (3 contracts) for ladder; current 4-contract BPS-only entries OK separately**
- (β) Revise 5% NLV gate to 6% NLV to accommodate S2; would marginally pass IC worst at 4 contracts

**Quant prior: (α)** — keep 5% NLV gate as is, target S3 for ladder.

**PM via 2nd Quant: confirm S3 as ladder target?**

---

## 5. P2 readiness

If 2nd Quant approves D1 (option a — engine without filters), Quant proceeds to:

```
P2 — Portfolio Integration
  Run engine 26y w/o filters → unbiased PnL distribution
  Re-run P1b-2 sweep with corrected bootstrap
  Compute:
    - Net ann ROE (corrected, no selection bias)
    - MaxDD / W20d / W63d at portfolio level
    - Worst 20d/63d degradation vs Baseline B (≤ +0.25pp hard gate)
    - Crisis window behavior at S3 sizing
    - Bootstrap CI on portfolio metrics
    - Walk-forward H1 / H2
    - Operational burden (entries/yr, action days, ≤30 preferred)
    - Capital competition with Q042
```

Outcome:
- STRONG PROMOTE: ΔROE ≥ +0.20pp + all hard gates
- SOFT PROMOTE: +0.05 to +0.20pp
- DOCUMENT: < +0.05pp + diversification material (operational discipline only)
- REJECT: any hard gate fail

---

## 6. Caveats Self-Disclosed

1. **P1b-2 PnL upper bound only**: 3-5x inflated by bootstrap selection bias. Real magnitudes depend on D1 path.
2. **IC NORMAL -58.8% worst** is from n=69 trades — small sample, single-tail event may have outlier influence.
3. **SPX scaling linear assumption**: pnl_per_contract × (SPX_today / SPX_entry). Assumes width scales linearly with SPX. Approximate; edge cases at extreme SPX may not hold.
4. **No portfolio-level metrics yet**: P1b-2 only checks per-trade worst gate. P2 handles MaxDD/W20d/W63d.
5. **Crisis windows not analyzed at S3**: P2 must validate IC NORMAL worst doesn't cluster in stress periods.
6. **Bootstrap CI tight (±9%)** — but that's statistical uncertainty only; methodological uncertainty (selection bias) dominates.
7. **PM bandwidth check pending**: V1b ≤ 30 action days/yr ✓; V3 daily check ✓ (within 1hr/day). Confirmed in P1b-1.
8. **Q079 (15 vs 21 DTE)** still parked; P2 uses SPEC-077 21 DTE only.

---

## 7. Decision Matrix

| 2nd Quant verdict | Action |
|---|---|
| **PASS + greenlight P2** + D1(a) + D2(a) + D3(α) | Quant runs engine-without-filters re-bootstrap → P2 unbiased portfolio integration |
| **REVISE D1** to (b) or (c) | Quant runs P2 with caveated bias / disclaimer |
| **REVISE D2** to (b) | Quant restricts ladder to credit-only (excludes BCD); re-runs P1b sweep |
| **REVISE D3** to S2 + gate to 6% NLV | Quant re-runs P1b with new gate, then P2 |
| **REJECT / DOCUMENT** | Q078 closes with documented finding (ladder improves diversification, ROE TBD without unbiased PnL) |

---

## 8. Quant Sign-off

Q078 P1b complete (P1b-1 model corrections + P1b-2 sizing sweep). Key empirical finding: at 5% NLV worst-trade gate, 3 contracts per entry is the maximum sustainable sizing for strategy-agnostic ladder (driven by IC NORMAL's -58.8% empirical worst-pct-of-max-loss × 3 = -4.29% NLV). At S3 sizing, V1b weekly catch-up and V3 daily-cluster outperform Baseline B by 3-4x cum PnL with eff_count 3.17-3.42 vs 1.15.

**But absolute ROE numbers inflated by bootstrap selection bias.** Engine 26y produced 373 trades from ~3120 selector PASS days (12% survivorship). Ladder bootstraps from engine's filtered "good" pool, extrapolating engine-quality to all PASS days. P2 must resolve this before SPEC-level conclusions.

> Q078 P1b finds: at uniform sizing + 5% NLV worst-trade gate, S3 (3 contracts / 7.5% BP) is the sustainable maximum; S2 (4 contracts / 10% BP per PM original) fails gate due to IC NORMAL's deep empirical worst. At S3, V1b weekly catch-up and V3 daily-cluster both materially outperform Baseline B with eff_count 3+ vs 1.15. PnL magnitudes are upper bound due to bootstrap selection bias (engine 12% pool extrapolated to 100% selector PASS). Three decisions needed: (D1) selection bias correction path, (D2) confirm strategy-agnostic ladder, (D3) confirm S3 target. P2 ready upon 2nd Quant verdict.

---

## 9. Supporting Files

- `research/q078/q078_p1b_1_memo.md` — P1b-1 model corrections (3 fixes applied)
- `research/q078/q078_p1b_2_memo.md` — P1b-2 sizing sweep (5% NLV gate validation)
- `research/q078/q078_p1b_1_model_corrections.py`
- `research/q078/q078_p1b_2_sizing_sweep.py`
- `research/q078/q078_p0_anchored_memo_2026-05-27.md` (5% NLV gate revision)
- All `research/q078/q078_p1b*_*.csv` (engine trade log, distributions, results grid, etc.)

Upstream:
- `task/q078_framing_2nd_quant_review_2026-05-27_Review.md` — framing PASS
- `task/q078_p1a_g2_2nd_quant_review_2026-05-27_Review.md` — G2 PASS w/ 3 fixes
- `research/q078/q078_p1a_memo.md` — P1a (superseded for PnL by P1b-1)
