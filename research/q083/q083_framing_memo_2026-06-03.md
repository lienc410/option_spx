# Q083 Framing — IVR-cell × IVP-gate Dual-Gating Audit

**Date**: 2026-06-03
**Owner**: Quant Researcher
**Status**: FRAMING — pending PM ratification before P0 kickoff
**Trigger**: PM operational complaint 2026-06-03 — "最近几个交易日一直被 gate block ... 一次 vix spike 导致 6-10 月不可交易完全不能接受"
**Approval**: 待 PM 看完本 framing 拍板
**Predecessor**: SPEC-058 / SPEC-060 IVP gates; Q069-Q072 BPS_NNB calibration; Q081/Q082 cash-bound framework

---

## 0. PM complaint (direct quote)

> "现在这个空交集的状态是不是因为同时 gate IVR 和 IVP? 是不是可以适当弱化这个双门设置。
> 现在的设置在我的交易手感上就是永远推荐 wait and reduce。
> 而且这个一次 vix spike 导致 6 到 10 个月不可交易完全不能接受，
> 这个量级的 spike 每年都有，之后半年不交易完全不合理"

Operational symptom: VIX 16.13, IVR 15, IVP 26, trend BULLISH. Matrix wants `NORMAL × IV_LOW × BULL → reduce_wait`. PM stuck there for weeks-to-months.

Pre-framing investigation (this session) established:
- **Two distinct VIX-derived metrics used by selector**:
  - **IVR** (linear position in 252d min-max range): determines `iv_signal ∈ {HIGH, NEUTRAL, LOW}` → cell routing
  - **IVP** (rank percentile in 252d distribution): determines gate permissions (`IVP_LOW_THRESHOLD=40`, `BPS_NNB_LOWER=43`, `BPS_NNB_UPPER=55`, `IVP_HIGH_THRESHOLD=70`)
- **In post-spike wide-range environments**, IVR cuts (30/50) and IVP cuts (40/43/55/70) **point at different VIX values**, creating empty intersection
- Current 252d range [13.47, 31.05] makes NEUTRAL cell (IVR 30-50) = VIX 18.74-22.26, but IVP 43-55 = VIX 16.76-17.38 — **no overlap**

PM hypothesis (worth formalizing as testable):

> "双 gate (IVR-cell + IVP-gate) is redundant or over-restrictive in wide-range regimes;
> relaxing one would restore operational tradability without losing risk protection."

---

## 1. Why this isn't just a complaint to dismiss

Historical 26y data (2000-2026, from `_signal_history_cache.csv`) shows:

| Year | Days routing to reduce_wait | Longest dead stretch |
|---|---:|---:|
| 2003 | 83% | 143d |
| 2008 | 79% | 83d |
| 2012 | 80% | 27d |
| **2017** | **9%** (best year) | 8d |
| **2021** | **87%** (worst year) | 62d |
| 2023 | 62% | 69d |
| 2025 | 65% | 15d |
| 2026 YTD | 65% | 9d |

**26-year average: 40-60% of trading days = reduce_wait**. This is structural, not a 2026-spike artifact.

The corollary: matrix routing was *designed* to be selective. Q069-Q072 research established BPS_NNB_LOWER=43 (premium too cheap below this), BPS_NNB_UPPER=55 (complacency-before-mean-reversion above this), all backed by counterfactual PnL analysis.

**But**: those research projects ran in different VIX regimes than today's wide-range, post-spike environment. The gate design may be locally optimal but globally over-restrictive. That's what Q083 tests.

---

## 2. Testable hypotheses

**H1 (gates necessary + independent)**: IVR-cell-routing and IVP-gate are filtering complementary risks (cell = regime appropriateness; gate = premium adequacy). The empty intersection in 2026 is by design — neither component independently identifies "safe BPS opens", both are required. **Action if H1**: accept current design, document why operational stretches are unavoidable.

**H2 (gates redundant)**: IVR-cell and IVP-gate are filtering substantially the same statistical signal (both derived from VIX 252d distribution). One can be relaxed/removed without losing protection. **Action if H2**: SPEC for relaxation — likely drop the BPS_NNB-specific gate, keep matrix cell routing.

**H3 (gates regime-conditional)**: In narrow-range 252d (stable regimes), IVR and IVP align — dual-gating is fine. In wide-range 252d (post-spike), they desync — dual-gating becomes false-positive (blocks profitable BPS). **Action if H3**: SPEC for regime-conditioned gate (e.g., disable IVP-gate when 252d range > threshold; OR use shorter IVP lookback when 252d range is wide).

The hypothesis space is exhaustive — exactly one is right per the data.

---

## 3. Phase structure (mirror Q081/Q082 conventions)

### **P0** — Baseline gate-state mapping across 26y

**Method**: for each trading day 2000-2026, classify into one of four states:
- (a) Matrix cell = reduce_wait AND IVP-gate would block anyway → "double-blocked, no question"
- (b) Matrix cell = reduce_wait AND IVP-gate would allow → "cell-blocked only"
- (c) Matrix cell = BPS-routing AND IVP-gate blocks → "**gate-blocked only, the disputed zone**"
- (d) Matrix cell = BPS-routing AND IVP-gate allows → "tradable (counterfactual baseline)"

**Output**: `q083_p0_state_counts.csv` — per-year breakdown of (a)/(b)/(c)/(d) frequencies.

**Kill gate**:
- If state (c) — the "matrix-wants-BPS-but-IVP-blocks" zone — is **< 10% of total NORMAL+BULL+NEUTRAL days**, then dual-gating is rarely binding → Q083 verdict likely H1, low ROI
- If state (c) is **≥ 25% of those days**, dual-gating is materially binding → strong case to investigate H2/H3

### **P1** — Counterfactual BPS PnL on state (c) days

**Method**: for each state (c) day (matrix-says-BPS but IVP-gate blocks), synthesize a BPS trade that WOULD have opened. Use:
- Selector's BPS parameter set (21 DTE, short put δ=0.20-0.25 per current SPEC, width $50)
- BS-flat IV using VIX/100 (same methodology as Q082 B-synth)
- Hold to 50% profit OR 21 DTE OR max-loss stop
- Compute exit PnL, % ROE, win rate

**Output**: `q083_p1_counterfactual_bps_trades.csv` + summary stats. Bucket by:
- IVP value in blocked zone (e.g., 25-32 / 33-40)
- 252d VIX range width at entry
- Forward window direction (mirror Q082 §F stratification)

**Decision logic**:
- If counterfactual mean PnL **< 0** OR Sharpe < 0.2 → gate is real protection, H1 supported → matrix unchanged
- If mean PnL **> 0** AND Sortino > 0.5 → gate is over-restrictive → H2 or H3, continue to P2
- If mean PnL positive but tail crater rate > 25% → gate protection is structurally right but threshold may be miscalibrated

### **P2** — Strata: H2 vs H3 distinction

If P1 shows counterfactual edge > 0, partition state (c) days by 252d range width:
- Narrow-range subset: 252d VIX range < median historical range
- Wide-range subset: 252d range > median

Compute counterfactual BPS PnL within each subset.
- If BOTH subsets show positive PnL → H2 (gate redundant in all regimes)
- If only WIDE-range subset shows positive PnL → H3 (regime-conditional)
- If neither shows positive PnL → H1 confirmed (P1 false alarm)

### **P3** — Alternative gate designs (only run if P2 = H2 or H3)

Simulate 4 alternative designs over 26y:
- **D1**: Drop IVP-gate entirely, rely on matrix cell routing only
- **D2**: Drop matrix iv_signal routing, gate by IVP only (consistent metric)
- **D3**: Replace IVP252 with IVP63 (shorter lookback, roll-off faster)
- **D4**: Regime-conditioned: standard gate when 252d range < X, relaxed gate when ≥ X

For each design, compute:
- Total trades opened per year
- Aggregate PnL
- Sortino, Sharpe, max DD
- 26y left-tail (per memory `feedback_strategy_metrics_pack` — marginal $/BP-day, worst trade, disaster window, CVaR)
- Compare to current design as baseline

**Decision logic** (per memory `feedback_noise_threshold`):
- ΔROE > +0.5pp annualized AND Sortino improved AND tail not significantly worse → recommend
- ΔROE within noise → DOCUMENT as "design alternatives explored, no improvement" — DON'T promote
- Any design that BEATS current on 2+ metrics + matches on tail → SPEC candidate

### **P4** — G-review 1 (2nd quant)

Methodology audit:
- BS-flat IV proxy acceptable for counterfactual BPS? (per Q082 precedent yes, but skew sensitivity needs explicit bracket)
- Counterfactual exit assumptions (50% profit, 21 DTE, stop-loss) reasonable?
- 26y synthetic without real chains — caveat sufficient?

### **P5** — Verdict + alternative design SPEC if applicable

Three possible outcomes:
- **H1 confirmed**: matrix unchanged. Document why operational reduce_wait stretches are necessary. PM accepts framework limit.
- **H2 confirmed**: SPEC for IVR-cell removal OR IVP-gate removal (whichever is the redundant one)
- **H3 confirmed**: SPEC for regime-conditioned gate

### **P6** — G-review 2

Per memory `feedback_kill_gate_external_read` — verdict ratification mandatory, especially if H1 (kill-class).

---

## 4. Decision thresholds (operationalized per memory feedback)

Per `feedback_strategy_metrics_pack`: any alternative design comparison must report:
- Marginal $/BP-day
- Worst single trade
- Disaster window (consecutive losing trades / max DD calendar period)
- CVaR (left tail)

Per `feedback_noise_threshold` (debit-vs-beta exception **DOES NOT** apply here — this is short-premium vs short-premium):
- ΔROE < 0.5pp annualized → noise
- Material improvement requires ΔROE ≥ 0.5pp AND tail not worse

Per `feedback_proxy_validity_must_match_conclusion`:
- BS-flat IV synthesizes BPS PnL; the proxy's validity depends on what claim we make
- For "is current gate over-restrictive?" → relative comparison OK (both blocked and counterfactual use same BS-flat)
- For "absolute PnL of unblocked trades" → flag CV1-style skew caveat (already known from Q082)
- Sign of caveat must be quantified before being cited as robustness (per `feedback_unquantified_caveat_sign_risk`)

Per `feedback_status_quo_bias_in_verdicts`:
- If verdict trends toward H1 (status quo), extra scrutiny required — not less
- Cannot use "current research backed by Q069-Q072" as justification without re-validating in current data

---

## 5. Out of scope

- BCD matrix routing (Q082 already audited this in B-synth-full)
- HIGH_VOL × BPS_HV cells (different gate logic, separate study if needed)
- IC routing (separate study)
- BEARISH trend cells (currently route to reduce_wait or specific defensive)
- Changing IVR/IVP **definitions** themselves (only thresholds and combinations)
- Q069-Q072 BPS_NNB underlying research (re-using their conclusions where applicable)
- SPEC-111 cash budget cap (unrelated, separate governance layer)

---

## 6. Files

```
research/q083/
├── q083_framing_memo_2026-06-03.md    ← this file
├── q083_p0_state_counts.{py,csv,md}
├── q083_p1_counterfactual_bps_trades.{py,csv,md}
├── q083_p2_h2_vs_h3_strata.{py,csv,md}
├── q083_p3_alternative_designs.{py,csv,md}
├── q083_p5_verdict_2026-XX-XX.md

task/
├── q083_p1_g1_2nd_quant_review_packet_<date>.md
├── q083_p1_g1_2nd_quant_review_<date>_Review.md
├── q083_p5_g2_2nd_quant_review_packet_<date>.md
├── q083_p5_g2_2nd_quant_review_<date>_Review.md
```

---

## 7. Estimated effort

| Phase | Hours | Calendar |
|---|---:|---|
| P0 baseline | 2 | 2026-06-04 |
| P1 counterfactual | 6-8 | 2026-06-05/06 |
| P2 stratification | 3 | 2026-06-07 |
| G-review 1 + reply cycle | 24-48h reviewer | 2026-06-08-10 |
| P3 alternative designs (only if H2/H3) | 8-12 | 2026-06-11-12 |
| P5 verdict + G-review 2 | 4 + 24h reviewer | 2026-06-13-15 |
| **Total** | **~25-35h + reviewer wait** | **~10 calendar days** |

Lower bound if P1 kill-gates: **~8h** if H1 confirmed quickly.

---

## 8. Anti-patterns to watch (per accumulated memory from Q081/Q082)

Q081 G2 + Q082 G2 surfaced systematic 1st-quant biases. Pre-emptive checklist:

- **Don't strawman PM's claim**: "PM thinks dual-gating is bad" must be tested directly, not turned into a strawman ("PM wants all gates removed")
- **Per-stratum stability**: counterfactual PnL per IVP bucket (25-32 / 33-40) must be reported separately, NOT just aggregate (per `feedback_reviewer_ask_literally`)
- **Quantify caveat signs**: BS-flat IV skew bias must be bracketed before being cited as robustness (per `feedback_unquantified_caveat_sign_risk`)
- **Status-quo default scrutinized**: if verdict is H1 (matrix unchanged), require equal evidence as if recommending change (per `feedback_status_quo_bias_in_verdicts`)
- **Sortino crash flagged as crash**: if any design metric drops > 30% from baseline, that's a regression, not "robust within noise"
- **MA-cross / entry-signal gate proposals dead-on-arrival**: per `feedback_short_dte_entry_signal_cannot_gate_forward`, BPS hold ~21d is short-DTE, entry-signal gates ineffective

---

## 9. PM ratification needed

1. **Framework approved**? Specifically: testing H1/H2/H3 trichotomy via counterfactual + alternative design simulation
2. **Kill-gate at P0**: if state (c) "matrix-says-BPS-but-IVP-blocks" days < 10% historically, accept the dual-gating is rarely binding and stop Q083 there?
3. **2nd quant reviewer**: continuing from Q082 (same person)?
4. **Timing**: 10 calendar days OK? Or faster preferred?
5. **Authorization scope**: P0+P1 first (kill-gate decision), THEN authorize P2-P5 if P1 says proceed?

Reply OK → P0 kicks off 2026-06-04.
