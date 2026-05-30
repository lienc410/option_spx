# Q077 — Structure-Aware Strike Placement (Framing Stub, PARKED)

**Date**: 2026-05-26
**Status**: **PARKED** — pending real-world trigger or PM bandwidth recovery
**Author**: Quant Researcher
**Source**: PM observation of TradingView "Flat Top & Bottom Indicator v2" (TREESinvest) + cross-AI review + Quant evaluation (2026-05-26)
**Decision**: Defer P0; archive methodology improvements and proxy candidates for future activation

---

## 0. Why PARKED, not REJECTED

The cross-AI reviewer's own prior:
> "大概率结果: edge ≈ 0 或 very small;
>  小概率: 对 tail trade 有 marginal improvement (< 5%)"

Per `feedback_layer_n_replacement_outcome` (Q075 2026-05-20):
> 如果一个 Layer-N 替代研究结果**结构性 clean 但 sub-threshold**，正确 outcome 是 DOCUMENT，不是 scaling 或继续推。

Reviewer's own expected outcome falls below Soft threshold (+0.05pp ROE). In our framework, this is **P0-priority below worth-doing-now**, not P0-priority worth-doing-but-low.

PM bandwidth at time of decision (2026-05-26):
- SPEC-106 matrix consistency (FE 实施中)
- Frontend audit Batch 1/2/3
- SPEC-105 v2 Stage 1 shadow monitoring
- Q042 DD-4% trigger watch
- Booster IVP buffer monitoring (53/55)

5 parallel threads. Adding a low-EV P0 = bandwidth dilution.

---

## 1. Activation Trigger Conditions

Activate Q077 P0 when **any** of these fires:

1. **SPEC-106 deployed + stable for ≥ 2 weeks** AND current frontend audit threads collapsed to ≤ 2
2. **Observed worst-trade episode** where a psychological / structural level cleanly predicted breach in hindsight (real-world prompt, not academic curiosity)
3. **PM explicitly allocates research bandwidth** for low-priority feature engineering exploration

**Do NOT activate based on**: market commentary, social media indicator mentions, vendor pitches.

---

## 2. Methodology Improvements (Accepted from Reviewer)

These three methodological corrections improve Q077 framing rigor IF activated:

### M1 — Event vs State distinction
- ❌ Don't frame as: "intraday signal → useless for 30 DTE"
- ✅ Frame as: "intraday raw signal useless, intraday-derived state variable may influence entry-time RV distribution"
- MBS CPR analogy: loan-level events aggregate to monthly CPR predictors

### M2 — SPEC-030 not transferable as veto
- SPEC-030 tested intraday-data-as-decision-trigger (binary timing, 0% advance)
- Q077 tests structure-as-state-feature (continuous state)
- Different question class. SPEC-030 informs prior but doesn't decide.

### M3 — Distance-to-structure as continuous state variable
- Reviewer's formulation (more rigorous than my "consider psychological levels"):
  ```
  D = distance(short_strike, nearest_support_level)
  P(breach | D bucket)
  P(max_DD | D bucket)
  E[loss | D bucket]
  ```
- Direct input to P0 attribution table

---

## 3. Daily-Data Feature Candidates

**Constraint**: NO intraday data. Use existing 26y SPX EOD bars + computed features.

| Feature | Definition | Hypothesis |
|---|---|---|
| **Level Clustering** | Past N-day frequency of close within ±x% band of given price level | High clustering → "price acceptance" → mean-reverting tape → lower forward RV |
| **Range Compression** | Rolling ATR percentile / realized vol decay over N days | Compression → dealer long gamma / low realized vol regime |
| **Bounce Symmetry** | Rejection count / penetration count from a price level over lookback | Asymmetric bounce → directional bias signal |
| **Distance to Recent Pivot** | Short-strike distance to recent N-day swing low / 30-day low / integer round number | Larger distance → safer entry; smaller → tail risk |

### Sample bucketing for P0 attribution

```
For each historical BPS trade (from existing engine):
  - Compute Distance-to-Structure D at entry time (multiple definitions)
  - Compute Level Clustering Score at entry
  - Compute Range Compression percentile
Group trades by:
  D ∈ {<1%, 1-2%, 2-3%, 3-5%, >5%}
  Clustering Score ∈ {low, mid, high}
  Compression ∈ {low, mid, high}
For each bucket report:
  n, hit rate, avg PnL, worst trade, P(breach), P(max DD > 5%)
Test:
  Does any structure-feature bucket show statistically significant improvement
  vs unconditional baseline?
  At what feature-threshold level?
```

---

## 4. Expected Outcome (Reviewer Prior, Pre-Activation)

```
Most likely: edge ≈ 0 to +0.02pp annualized
  → DOCUMENT outcome (cash-equivalent contribution)
Small probability: marginal tail improvement (<5% reduction in worst trades)
  → Possibly DOCUMENT + structural observation; potential later integration if other signals align
```

Per `feedback_layer_n_replacement_outcome`: this prior alone is **NOT** sufficient to motivate the research given current bandwidth.

---

## 5. What is NOT in Q077 scope (when activated)

- **No intraday data** (we don't have tick / sub-1-min)
- **No order-book / dealer gamma estimation** (no OPRA tick feed, no GEX/DIX subscription)
- **No reference to original TradingView indicator** (intellectual lineage acknowledged in §0; framing is independent)
- **No live execution layer changes** until P4 portfolio integration passes Q075-style criteria
- **No new tooling subscriptions** (use existing 26y EOD + computed features only)

---

## 6. Predecessor Context (for future Quant who picks this up)

This stub captures analysis from 2026-05-26 conversation:
- PM observed TradingView "Flat Top & Bottom Indicator v2" by TREESinvest
- Cross-AI assessment proposed 4 use cases (entry timing / regime classifier / strike placement / RV forecasting)
- Quant evaluated: 3 of 4 not applicable (time-scale mismatch, no data, SPEC-030 prior)
- Reviewer (second cross-AI) flagged 3 methodology improvements (event/state distinction, SPEC-030 transferability nuance, distance-as-state formulation)
- Quant accepted methodology improvements but argued for defer based on:
  - Reviewer's own sub-threshold prior
  - PM bandwidth occupied by SPEC-106 + frontend audit + monitoring threads
  - `feedback_layer_n_replacement_outcome` framework: sub-threshold expected outcome → don't open

If activated later, this stub provides:
- Methodology corrections to apply (§2)
- Daily proxies to test (§3)
- Outcome priors to anchor (§4)
- Scope boundaries to respect (§5)

---

## 7. Files

- `task/q077_structure_feature_framing_stub_2026-05-26.md` (this file)

References:
- `~/.claude/.../memory/feedback_layer_n_replacement_research.md` (research sequencing)
- `~/.claude/.../memory/feedback_layer_n_replacement_outcome.md` (DOCUMENT discipline)
- `~/.claude/.../memory/feedback_survival_vs_income_layering.md` (Layer-N framing)
- `~/.claude/.../memory/research_intraday_data.md` (SPEC-030 prior on intraday signals)
- `task/SPEC-106.md` (in-flight; must land before Q077 activation)

---

## 8. Re-activation Path

When trigger condition fires:

1. PM signals readiness (explicit "open Q077" message)
2. Quant reads this stub + checks SPEC-106 status + frontend audit status
3. Quant writes Q077 framing packet → 2nd Quant pre-review
4. If PASS → Q077 P0 anchored memo using methodology in §2 and features in §3
5. Continue per Q075-style cycle (P1 attribution → P2/P3/P4 if signal exists)

**Default outcome assumption (must be honest)**: DOCUMENT after P0/P1, no SPEC drafted, structure-feature finding archived as research note.
