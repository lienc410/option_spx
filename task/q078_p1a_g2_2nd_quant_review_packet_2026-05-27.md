# Q078 P1a — G2 Light Review Packet

**Date**: 2026-05-27
**Author**: Quant Researcher
**Reviewer**: 2nd Quant
**Type**: G2 light review (optional per P0 §10) — surfacing findings + asking direction before P1b
**Decision sought**: confirm P1b scope, resolve 3 limitations, direction on 3 strategic findings

---

## 0. TL;DR

Q078 P1a tested 4 cadence variants vs Baseline B (cluster proxy):

```
Variant              n_eval  pass%   trades  entries/yr  cum_PnL    max_conc%  eff_count
V1a_weekly_strict     1245   46.2%    560      21.2     +$118k      82.3%      1.36
V1b_weekly_catchup    1378   59.2%    785      29.7     +$188k      75.7%      1.55
V2_biweekly_strict     623   46.5%    285      10.8      +$64k      99.9%      1.00
V3_daily_cluster       917  100.0%    883      33.5     +$224k      73.5%      1.61
BaselineB_cluster      254  100.0%    976      37.0     +$267k     100.0%      1.00
```

**3 confirmed findings**:
- Selector PASS rate ~46% on Mondays (matches SPEC-106 ~50% audit)
- Ladder DOES improve expiry diversification (V3: -26.5pp max_conc, +0.61 eff_count)
- Ladder PnL is LOWER vs Baseline B at 1-contract-per-entry (sizing not normalized yet)

**3 limitations need P1b resolution**:
- BCD placeholder PnL=$0 (1747 days, 26% of PASS) → "worst $+0" artifact across all variants
- Sizing not normalized: Baseline B 4 contracts/cluster vs Ladder 1/entry
- Per-trade MTM model probably too optimistic at d_off=10 (21 DTE roll exit)

**1 strategic finding**:
- Pure "Bull Put Spread" (NORMAL+NEUTRAL_IV+BULLISH) appears **only 96 days in 26y** (3.6/yr)
- PM's "weekly BPS" intuition is 5-6x more frequent than historical pure-BPS opportunity
- Ladder effectively becomes "execute whatever selector says" — strategy-agnostic per P0 R8

---

## 1. 3 limitations details

### L1 — BCD placeholder PnL=$0

```python
elif "Bull Call Diagonal" in strategy_name:
    return {"pnl": 0.0, ...}  # P1a limitation
```

BCD (Bull Call Diagonal, debit) appears 1747 days = 26% of PASS days = ~5x more common than pure BPS. Currently treated as zero-PnL placeholder.

**Impact**: "worst trade $0" across all variants is BCD placeholder artifact, not real worst BPS/IC trade. Hit rate / PnL distributions all skewed.

**P1b proposed fix**:
- Build simple BCD model: long deep-ITM call (0.70δ, 90 DTE) + short OTM call (0.30δ, 45 DTE)
- Analytical payoff at exit using time decay + intrinsic
- Or simpler: import historical BCD trade PnL distribution from prior backtests (q041 / q042 cache?)

### L2 — Sizing not normalized

Baseline B opens 4 contracts/cluster (one PASS day → 4 spreads). Ladder opens 1 contract/entry.

```
Baseline B: 254 cluster days × 4 contracts = ~976 trades
V1b: 785 trades over 1378 weekly slots (PASS rate 59.2%)
```

Per-entry sizing differs, making cum PnL comparison apples-to-oranges. P1b sizing sweep (S1=1ct, S2=10%BP, S3=15%BP, S4=dynamic) will normalize.

### L3 — Per-trade MTM bias

At d_off=10 (21 DTE roll fires), my mtm_at function:
```
time_decay = (20/30)^0.7 = 0.762
base_credit_rem ≈ 0.76 × credit ≈ $835 (credit=$1100)
For SPX above short → mtm = +$835 → exit PnL ~ +$785
```

This treats nearly the full credit as "captured" at d_off=10 — likely too optimistic for theta decay reality. Real BPS at 20 DTE remaining has ~40-50% of credit captured, not 76%.

**P1b proposed fix**: use empirical theta curve from existing backtest engine OR calibrate time_decay exponent (lower from 0.7).

---

## 2. Strategic finding — Q078 needs scope reframing?

```
Distinct strategies in 26y history:
  Reduce / Wait:                3520 days (53.0%)  → ladder skips
  Bull Call Diagonal:           1747 days (26.3%)  → debit (LOW_VOL+BULLISH)
  Iron Condor (High Vol):        607 days ( 9.1%)
  Iron Condor:                   296 days ( 4.5%)
  Bull Put Spread (High Vol):    291 days ( 4.4%)
  Bull Put Spread:                96 days ( 1.4%)  ← PM's current cell, only 3.6/yr
  Bear Call Spread (High Vol):    82 days ( 1.2%)
```

PM's framing was "BPS ladder". But pure BPS opportunities are very rare. Per P0 R8, ladder uses selector-provided strategy params (not BPS-only). So Q078 in practice is:

> **Q078 = "selector-gated weekly execution ladder, whatever selector says (BCD / IC / BPS / HV)"**

Not "BPS-only ladder".

**Question for 2nd Quant**: is this OK conceptually? Or does PM specifically want "ladder for credit-only strategies" (filter out BCD), which would reduce trade frequency to ~13/yr (BPS + BPS_HV + IC + IC_HV + BCS_HV)?

---

## 3. P1b proposed scope (revised based on P1a)

### Cadence candidates
- **V1b weekly catch-up** (PM bandwidth fit, 24pp max_conc reduction)
- **V3 daily-cluster** (best diversification, daily check ok per 1hr/day)
- V1a / V2 rejected (V1a dominated by V1b, V2 zero diversification gain)

### Sizing variants
- S1: 1 contract/entry (P1a baseline)
- S2: 10% BP target = round(0.10 × NLV / max_loss) contracts (PM original)
- S3: 15% BP target = round(0.15 × NLV / max_loss) (selector default)
- S4 (CAUTION per P0): dynamic = fill to 35% strategy ceiling

### Critical P1b additions
- **Fix L1 (BCD model)** — material; can't conclude without
- **Fix L2 (sizing normalization)** — Baseline B at scaled sizing
- **Fix L3 (MTM theta curve)** — optional improvement; P1a relative rankings probably still hold

### Decision matrix for P1b promotion
Per P0 §7:
```
STRONG: ΔROE ≥ +0.20pp + risk thresholds + diversification material
SOFT:   +0.05 to +0.20pp + risk thresholds + diversification material
DOCUMENT: < +0.05pp but diversification material (operational principle)
REJECT: any hard gate fail (W20d/W63d > +0.25pp degradation, etc.)
```

---

## 4. 5 Questions for 2nd Quant

### Q1 — BCD modeling priority
P1a's "worst $+0" is BCD placeholder artifact. P1b should resolve. Options:
- (a) Build analytical BCD payoff (1-2 hr work)
- (b) Import BCD PnL from existing backtest cache (verify exists)
- (c) Drop BCD trades from ladder simulation, restrict to credit-only (changes Q078 scope materially)

Quant prior: **(a)** — analytical BCD model. (c) changes scope; reject without PM/2nd Quant explicit approval.

**2nd Quant: confirm (a), or prefer (b) / (c)?**

### Q2 — Sizing normalization approach
Baseline B currently uses 4 contracts/cluster. For fair PnL comparison:
- (a) Run Baseline B at 1 contract too (uniform) — measures cadence effect cleanly
- (b) Run Ladder at "burst sizing" to match Baseline B BP-days — measures total exposure effect
- (c) Both (a) and (b) as sensitivity

Quant prior: **(c)** — both views. (a) isolates cadence; (b) gives PM realistic projection.

**2nd Quant: confirm (c), or single normalization?**

### Q3 — BPS-only scope vs strategy-agnostic ladder
P1a finds 96 pure BPS days in 26y. Ladder fires on BCD (1747), HV variants (980), IC (296). Per P0 R8, ladder is strategy-agnostic.

But PM's mental model was "BPS ladder". Should Q078 conclusion language be:
- "Ladder is operational discipline for selector-gated execution, whatever strategy"
- OR "Ladder is BPS-specific" (would restrict to ~13 PASS days/yr from BPS+IC+HV credit-only)

Quant prior: **agnostic ladder language** matches code reality and P0 R8.

**2nd Quant: confirm framing, or do we restrict?**

### Q4 — Per-trade MTM bias
P1a MTM at d_off=10 captures ~76% of credit (time_decay (20/30)^0.7). Real theta decay is ~40-50% at 20 DTE remaining.

Impact: PnL numbers in P1a are probably 50% overstated. Relative ranking should still hold (all variants same model).

P1b fix priority:
- (a) Replace theta_decay exponent based on empirical SPX option data
- (b) Use existing engine's per-trade PnL log (more realistic)
- (c) Accept current model, document bias, use for relative comparison only

Quant prior: **(b) if engine cache exists**, else (a). (c) only as fallback.

**2nd Quant: which?**

### Q5 — DTE-of-entry in scope?
Q078 ladder uses selector-provided DTE (30 NORMAL / 35 HIGH_VOL / 45 LOW_VOL). PM's original proposal was "30 DTE only".

Should P1b also test:
- Constant 30 DTE ladder (PM original)
- vs selector-provided DTE (P0 R8)

Quant prior: **selector-provided** per P0 R8; PM's "30 DTE only" was implicit BPS-only assumption that doesn't survive scope-agnostic framing.

**2nd Quant: confirm or test both?**

---

## 5. Caveats Self-Disclosed

1. P1a results at 1-contract-per-entry. Real PM proposal is 10% BP/entry → ~64 contracts. P1b will scale.
2. BCD treatment is the single biggest limitation — 26% of PASS days are BCD.
3. MTM bias makes P1a PnL numbers absolute-inflated but relative-valid.
4. eff_count 1.6 is "ladder benefit ceiling" not floor — real-world ladder may produce more or less concentration depending on stress timing.
5. P1a does not test transition behavior — P3 will.
6. Operational burden simulation assumes perfect ladder adherence (PM always checks Monday, always enters when PASS). Real adherence lower.
7. 96 BPS days finding suggests PM's "BPS ladder" mental model may need updating — Quant prior: ladder is execution discipline, not BPS-specific.

---

## 6. Decision Matrix

| 2nd Quant verdict | Action |
|---|---|
| **PASS P1a + greenlight P1b** with Q1-Q5 answered | Quant runs P1b sizing study after fixing L1 (BCD) + L2 (sizing) |
| **REVISE P1a** (re-run with fixes before P1b) | Quant fixes BCD + MTM first, re-runs P1a, then P1b |
| **PAUSE Q078** | Document P1a findings + park P1b until BCD modeling resolved separately |
| **CLOSE Q078** | If BCD/sizing/MTM limitations are too severe → DOCUMENT P1a structural finding (ladder helps diversification) without continuing |

---

## 7. Quant Sign-off

Q078 P1a complete. Cadence comparison shows V1b/V3 deliver real expiry diversification benefit (eff_count +0.55-0.61 vs Baseline B 1.0). PnL at 1-contract scale is lower vs Baseline B but sizing not normalized. BCD placeholder + MTM bias are P1b prerequisites. 96 BPS days/26y finding may require ladder framing language update. Recommend P1b with V1b + V3 only, sizing sweep, BCD model fix.

> Q078 P1a confirms ladder structurally improves expiry diversification (eff_count 1.36-1.61 vs Baseline B 1.00 single-day expiry). PnL comparison inconclusive at fixed contract scale — Baseline B clusters more contracts per PASS day. P1b sizing study will normalize this and resolve BCD placeholder (26% of PASS days). 96 pure-BPS days/26y means PM's "BPS ladder" mental model should generalize to "selector-gated execution ladder, strategy-agnostic". V2 bi-weekly is dominated; V1a is dominated by V1b. Top P1b candidates: V1b weekly catch-up (PM bandwidth fit) + V3 daily-cluster (best diversification). 5 questions for 2nd Quant direction before P1b runs.

---

## 8. Supporting Files

- `research/q078/q078_p1a_memo.md` — full P1a memo
- `research/q078/q078_p1a_cadence_attribution.py` — script
- `research/q078/q078_p1a_*.csv` — 4 output CSVs

Upstream:
- `research/q078/q078_p0_anchored_memo_2026-05-27.md`
- `task/q078_framing_2nd_quant_review_2026-05-27_Review.md`
