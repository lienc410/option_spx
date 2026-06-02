# Q082 Framing — BCD Multi-Regime Validation (continuation of Q081 B-2)

**Date**: 2026-06-01
**Owner**: Quant Researcher
**Status**: FRAMING — pending PM start signal
**Trigger**: Q081 P5 Verdict B-1 chosen by PM 2026-06-01 (keep BCD in matrix with "regime-conditional leveraged-beta" characterization); B-2 path deferred to Q082 for longer-horizon validation
**Predecessor**: Q081 (research/q081/) — closed; SPEC-111 drafted for Verdict A
**Approval**: PM authorized continuation in 2026-06-01 session ("先做A+B1，完成后继续B2研究")

---

## 0. Why Q082 exists

Q081 closed with PM ratification of B-1: keep BCD in LOW_VOL × BULL matrix
cells with explicit honest characterization as "regime-conditional
leveraged-beta + vega cushion", NOT unconditional structural alpha. The
B-1 path accepted a structural risk:

> **若未来市场系统性变成"跌多涨少"，BCD 的"优势"会消失甚至变劣势。**

Q081's 3y sample (2023-06 → 2026-01) happened to be 48% up windows + 43%
down windows (roughly balanced). BCD's +8pp aggregate edge came from
up-window concentration. Across a longer / more-adverse-regime sample,
the edge may invert.

Q082 stress-tests the B-1 acceptance.

---

## 1. Core question

**Does BCD's net edge over QQQ (with current matrix routing) survive
historical regimes that Q081's 3y sample doesn't cover?**

Specifically:
- **2008** (GFC bear market): if BCD had run through 2007-2009, would net
  edge over QQQ remain positive?
- **2018 Q4** (vol expansion): would BCD's vega cushion in this episode
  compensate for delta drag?
- **2020 Mar** (COVID flash crash): vol expansion + price crash — BCD
  long-leg vega should help, but short-leg gap risk in 45 DTE is real
- **2022** (rate-driven decline, no major vol spike): BCD's vega cushion
  weak, delta drag full force
- **Sustained bull markets** (2017, 2021): BCD's up-window edge confirmed?

---

## 2. Method

### 2.1 Sample construction

**Challenge**: backtest engine currently has 3y window (2023-06 →). Need
longer sample. Options:

**Option A — Synthetic BCD reconstruction from q041 chain data**:
- q041 has option chain history going back further (need to verify
  exact coverage)
- For each historical LOW_VOL × BULL day, construct synthetic BCD entry
  (long 90 DTE δ0.70 + short 45 DTE δ0.30), simulate hold to 21 DTE
  short-leg roll, compute PnL
- Use historical SPX + VIX series for matched-window QQQ comparison
- Cost: 2-3 days tooling

**Option B — Use existing backtest engine extended back**:
- `backtest/engine.py` may support longer windows via param
- May lack chain depth for synthetic BCD
- Cost: 1 day if straightforward, else fall to Option A

**Default**: try B first (cheap), fall to A if needed.

### 2.2 Phase plan

**P1 — Sample coverage assessment**: enumerate dates where (LOW_VOL × BULL
× trend filter) was true historically, from earliest available chain
data. Per year, by regime classification. **Kill gate**: if no usable
data before 2018, downgrade Q082 scope.

**P2 — Per-trade BCD reconstruction**: build the synthetic BCD ladder
following current selector params + matrix rules. Output per-trade
debit, hold, exit PnL.

**P3 — Stratified BCD vs QQQ matched-window** (mirror Q081 §F):
- Per trade compute QQQ same-window return
- Stratify by SPX same-window direction (up/flat/down)
- Compute mean, median, Sortino within stratum
- **Compare to Q081's 3y sample**: does the up-bias persist across
  longer sample? Or was 2023-2026 anomalously up-biased?

**P4 — Stress-period drill-down**: for 2008, 2018 Q4, 2020 Mar, 2022,
report:
- # of BCD entries during each event window
- Aggregate PnL vs aggregate QQQ comparison
- Worst single-trade outcome
- Vega cushion contribution (long-leg pnl decomposition)

**P5 — Verdict**: does B-1 framing hold?
- **B-1 confirmed**: aggregate edge persists across regimes → keep BCD
  matrix routing, retire Q082 as confirmation
- **B-1 partially refuted**: aggregate edge erodes in adverse regimes;
  consider directional refinement (e.g., add VIX-trend-up gate)
- **B-1 fully refuted**: BCD net loses to QQQ across full sample →
  matrix change warranted; new SPEC

### 2.3 G-review points

- **G1 (after P1)**: sample coverage adequate? Methodology for synthetic
  BCD reconstruction acceptable?
- **G2 (after P5)**: final verdict ratification. Per memory
  `feedback_kill_gate_external_read`.

Default reviewer: continuing 2nd quant from Q081 G-reviews 1 + 2.

---

## 3. Decision thresholds (Q082 → Q081 update)

- **BCD aggregate edge > 0 across full sample, stable across regimes** →
  B-1 confirmed, Q081 verdict permanent
- **Aggregate edge > 0 but concentrated in benign regimes; adverse
  regimes drag near zero** → B-1 with caveat; add monitoring rule for
  regime indicators
- **Aggregate edge near zero (within bootstrap CI of 0)** → B-1 refuted;
  matrix change to "cash → QQQ unconditionally" or add hurdle gate
- **Aggregate edge negative** → matrix change; replace BCD with cash

Threshold for "near zero": p20 of bootstrap distribution of aggregate
edge crosses 0 (per memory `feedback_noise_threshold` debit-vs-beta
exception — use distribution overlap, not 0.5pp).

---

## 4. Files (planned)

```
research/q082/
├── q082_framing_memo_2026-06-01.md   ← this file
├── q082_p1_sample_coverage.{py,csv,md}
├── q082_p2_bcd_reconstruction.{py,csv,md}
├── q082_p3_stratified_comparison.{py,csv,md}
├── q082_p4_stress_period_drill.{py,csv,md}
├── q082_p5_verdict_2026-XX-XX.md
task/
├── q082_p1_g1_2nd_quant_review_packet.md
├── q082_p1_g1_2nd_quant_review_Review.md
├── q082_p5_g2_2nd_quant_review_packet.md
├── q082_p5_g2_2nd_quant_review_Review.md
```

---

## 5. Out of scope

- Changing SPEC-111 cap (Verdict A) — that's independent and shipped
  regardless
- Re-doing Q081 P2-P4 with current sample (those results stand)
- Multi-strategy comparison beyond BCD vs QQQ
- Forward sample generation (synthetic Monte Carlo); use historical only
- Sizing optimization for BCD

---

## 6. Estimated effort

| Phase | Hours |
|---|---|
| P1 sample coverage | 3 |
| P2 BCD reconstruction (if synthetic) | 16-24 |
| P3 stratified comparison | 4 |
| P4 stress drill | 6 |
| G-reviews + memos | 6 |
| P5 verdict | 4 |
| **Total** | **~5-7 working days** (depending on Option A vs B path) |

---

## 7. PM start signal needed

- Confirm Q082 scope as defined above
- Greenlight P1 sample coverage assessment
- Q082 timing: after SPEC-111 ships? Or in parallel?

My recommendation: SPEC-111 to dev now (1.5 dev days). Q082 P1 starts in
parallel (quant-side, no dev dependency). When SPEC-111 deploys, Q082
continues in P2+.
