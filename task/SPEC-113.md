# SPEC-113 — Carve `NORMAL × IV_LOW × BULLISH × VIX<18` to Bull Call Diagonal

**Type**: matrix routing / strategy carve-in
**Date**: 2026-06-03
**Status**: **RATIFIED** by 2nd Quant Reviewer (G-review P15 round, 2026-06-03) + PM (floor性质 = 警惕线, 2026-06-03). Ready for dev handoff.
**Cross-reference**: `research/q083/q083_p15_today_params_net.py` (today's-params net settlement), `task/q083_p15_g_review_today_params_2026-06-03.md` (final G-review packet).
**Parent**: `strategy/selector.py::select_strategy` matrix routing + `strategy/catalog.py::CANONICAL_MATRIX`
**Sibling**: SPEC-111 (cash floor governs new opens; this SPEC scales below-floor duration by +30%, PM ratified as 警惕线 acceptable暂态)
**Owner**: Quant Researcher (this draft) → Developer (implementation)

---

## 0. TL;DR

Add **one matrix cell** for BCD entry: `NORMAL × IV_LOW × BULLISH × VIX<18`. Same BCD legs as the existing `LOW_VOL × BULLISH` cell (long 90 DTE δ0.70 CALL + short 45 DTE δ0.30 CALL). VIX ≥ 18 in the same regime/iv/trend triple continues to route `reduce_wait`.

**Why**: PM's operational痛点 — "近几个交易日一直被各种 gate block，VIX spike 后 6-10 月不可交易". Q083 root-cause analysis (P10): IVR cell-routing (67.5% of NORMAL × BULL blocks fall into IV_LOW) dominates over IVP gate. The NORMAL × IV_LOW × BULL cell is structurally different from LOW_VOL × BULL — higher forward 21d vol-expansion frequency (29.6% vs 24.3%), where BCD's +vega cushion is structurally rewarded. Carve to VIX<18 selected for robustness: survives +8vp short-leg skew bracket with Sortino 0.860 (vs full 15-22 range 0.513).

**Today's-params net**: +$8,857/yr after QQQ 10% opp cost on PM's actual $37k liquid / $22.2k SPEC-111 cap scale (3.13x historical scale). Below-floor cash duration rises 89 → 117 trading days/yr (PM ratified as 警惕线 — see §6).

---

## 1. Background

### 1.1 Q083 trigger

PM operational complaint 2026-06-02: VIX spike-then-decay states (typical NORMAL × IV_LOW × BULLISH after a 20+ vol event) leave the matrix stuck at `reduce_wait` for 6-10 months while VIX decays back to LOW_VOL range. PM: "改造完的通过率只有2%? 那跟不改有什么不同？基本还是不能开仓" (rejecting SPEC-112 minor lookback shortening).

### 1.2 Diagnosis (Q083 P10)

In 26y data, NORMAL × BULL blocks split by IV signal:
- IV_LOW: **67.5%** (1,023 of 1,515 blocks)
- IV_NEUTRAL: 15.4%
- IV_HIGH: 17.1%

IV_LOW dominates because post-spike VIX decays into the [15, 25] NORMAL band while sitting in the lower part of its 252d distribution. The existing matrix routes ALL NORMAL × IV_LOW × BULLISH to `reduce_wait` (line 1202-1208 of selector.py), so PM is shut out of 2/3 of NORMAL × BULL days.

### 1.3 Why BCD here (not BPS or BCS)

Forward-21d outcomes from NORMAL × IV_LOW × BULL entries:
- 29.6% see VIX rise ≥+5vp within 21 days (higher than LOW_VOL × BULL's 24.3%)
- 16.7% see max SPX drop > 5%

BCD is +vega (long 90 DTE call dominates). Higher forward vol-expansion frequency means BCD's +vega cushion is structurally rewarded relative to LOW_VOL × BULL — empirically confirmed in P11 (n=82, win 73.2%, mean +$1,410, Sortino +0.768 baseline).

BPS is NET SHORT VEGA → opposite. BCS would be lower premium (IV_LOW). BCD is the natural fit.

### 1.4 Why VIX<18 carve (not full NORMAL band)

Per-bucket sensitivity to short-leg skew (+8vp pessimistic bracket, Q083 P13):

| VIX bucket | n | +8vp mean PnL/contract |
|---|---:|---:|
| [15, 16) | 17 | +$2,179 |
| [16, 17) | 17 | +$1,023 |
| [17, 18) | 12 | +$1,177 |
| [18, 19) | 11 | **+$150** (weak) |
| [19, 20) | 9 | **+$157** (weak) |
| [20, 21) | 2 | small n |
| [21, 22) | 14 | +$1,500 |

VIX 18-20 sub-bucket becomes WEAK (but not negative) under pessimistic skew. Carving to **VIX<18** keeps the 46 highest-quality trades, drops the 36 marginal ones. +8vp Sortino: 0.860 (vs full-range 0.513). Conservative.

### 1.5 Net settlement at today's parameters (PM $37k liquid / $22.2k cap)

@ QQQ 10%/yr (PM-stated hurdle, Q081):

| Annual ($/yr at today's params, 3.13x historical scale) | Pre | Post | Δ |
|---|---:|---:|---:|
| BCD PnL | $15,747 | $25,020 | **+$9,273** |
| Opp cost | $1,007 | $1,422 | +$416 |
| **Net** | **$14,741** | **$23,597** | **+$8,857** |

@ SGOV 5%/yr (conservative): net +$9,066/yr.

Δ opp cost as % of Δ BCD PnL: 4.5% (ratio holds; absolute under today's params is the relevant figure).

---

## 2. Specification

### 2.1 New matrix cell

| Regime | IV signal | Trend | VIX condition | Strategy |
|---|---|---|---|---|
| NORMAL | LOW | BULLISH | VIX < 18 | `bull_call_diagonal` |
| NORMAL | LOW | BULLISH | VIX ≥ 18 | `reduce_wait` (no change) |
| NORMAL | LOW | NEUTRAL | (any) | `reduce_wait` (no change) |
| NORMAL | LOW | BEARISH | (any) | `reduce_wait` (no change) |

VIX threshold parameter: `SPEC_113_VIX_THRESHOLD = 18.0`. Read at open-decision time from `VixSnapshot.vix`. Defined as module constant in `strategy/selector.py`.

### 2.2 BCD legs (unchanged from LOW_VOL × BULL cell)

| Leg | Side | Right | DTE | Δ target | Note |
|---|---|---|---|---|---|
| 1 | BUY  | CALL | 90 | 0.70 | Long leg — deep ITM, high delta |
| 2 | SELL | CALL | 45 | 0.30 | Short leg — OTM, collects theta |

Identical to existing `BULL_CALL_DIAGONAL` legs (`strategy/selector.py` line 1082-1085).

### 2.3 Size & gates

- `_compute_size_tier(BULL_CALL_DIAGONAL, iv, vix, iv_s, t)` — same sizing rule as LOW_VOL × BULL BCD.
- SPEC-079 BCD comfortable-top filter applies (same as LOW_VOL × BULL): if 3-feature risk_score=3, downgrade to reduce_wait.
- SPEC-111 cash budget cap applies (cap=60% liquid, alert=75%, floor=$30k). Single BCD ≈ $22.2k under cap; sequential ladder behavior unchanged.
- Local spike detection (LOCAL_SPIKE_IVP63_MIN / LOCAL_SPIKE_IVP252_MAX) applies identically.

### 2.4 CANONICAL_MATRIX representation (frontend display)

`strategy/catalog.py::CANONICAL_MATRIX` cell becomes a **dict** instead of a string for the changed cell:

```python
"NORMAL": {
    "HIGH":    {"BULLISH": "bull_put_spread",  "NEUTRAL": "iron_condor",  "BEARISH": "iron_condor"},
    "NEUTRAL": {"BULLISH": "bull_put_spread",  "NEUTRAL": "iron_condor",  "BEARISH": "iron_condor"},
    "LOW":     {
        "BULLISH": {"VIX_LT_18": "bull_call_diagonal", "VIX_GE_18": "reduce_wait"},
        "NEUTRAL": "reduce_wait",
        "BEARISH": "reduce_wait",
    },
},
```

`matrix_payload()` extended to render dict-cells in `/api/strategy-matrix` as `{label: "bull_call_diagonal if VIX<18 else reduce_wait", strategy: "bull_call_diagonal", condition: "VIX_LT_18"}` shape (precise contract per dev). Frontend matrix renders the sub-condition visibly in the cell.

### 2.5 Selector branch change

In `strategy/selector.py::select_strategy`, the existing NORMAL × IV_LOW × BULLISH branch (currently line 1202-1208) gains a VIX gate:

```python
if iv_s == IVSignal.LOW:
    if t == TrendSignal.BULLISH:
        # SPEC-113 carve: VIX<18 routes to BCD
        if vix.vix < SPEC_113_VIX_THRESHOLD:
            # SPEC-079 BCD comfortable-top filter applies (same as LOW_VOL × BULL)
            if not params.disable_entry_gates and _is_comfortable_top(...):
                return _reduce_wait("SPEC-113 BCD carve but comfortable-top filter blocks", ...)
            return _build_recommendation(
                StrategyName.BULL_CALL_DIAGONAL,
                vix=vix, iv=iv, trend=trend,
                legs=[
                    Leg("BUY",  "CALL", 90, 0.70, "Long leg — deep ITM, high delta"),
                    Leg("SELL", "CALL", 45, 0.30, "Short leg — OTM, collects theta"),
                ],
                size_rule=_compute_size_tier(
                    StrategyName.BULL_CALL_DIAGONAL.value, iv, vix, iv_s, t
                ),
                rationale=(
                    f"NORMAL + IV LOW + BULLISH + VIX={vix.vix:.1f} < {SPEC_113_VIX_THRESHOLD} "
                    f"(SPEC-113 carve) — spike-decay state where BCD +vega cushion is structurally rewarded "
                    f"(P11 +18.5% period-ROE on 46 carved trades, +8vp Sortino 0.860)"
                ),
                position_action=...,
                macro_warning=macro_warn,
            )
        return _reduce_wait(
            f"NORMAL + IV LOW + BULLISH + VIX={vix.vix:.1f} >= {SPEC_113_VIX_THRESHOLD} — "
            f"SPEC-113 carve gate (VIX too high for +vega cushion to dominate under pessimistic skew)",
            vix, iv, trend, macro_warn,
            canonical_strategy=StrategyName.BULL_CALL_DIAGONAL.value,
            params=params,
        )
```

(Dev: factor the BCD construction out of the LOW_VOL × BULL branch if it's not already reused, to avoid duplicate leg/sizing definitions.)

### 2.6 Module constants

Added to `strategy/selector.py` near other SPEC-aware constants:

```python
# SPEC-113: NORMAL × IV_LOW × BULLISH carve-in
SPEC_113_VIX_THRESHOLD = 18.0   # VIX < 18 routes to BCD; VIX >= 18 stays reduce_wait
```

---

## 3. Acceptance Criteria

### AC-1 — New cell routing (positive case)

`select_strategy(vix=15.5, iv=NORMAL × LOW with ivp ∈ [0, 40)), trend=BULLISH, ...)` returns `BULL_CALL_DIAGONAL` recommendation. Legs match §2.2.

### AC-2 — New cell VIX gate (negative case at 18.0)

`select_strategy(vix=18.0, iv=NORMAL × LOW × BULLISH, ...)` returns `reduce_wait` (NOT BCD). At VIX=17.99 returns BCD; at VIX=18.0 returns reduce_wait. Exact threshold boundary tested both sides.

### AC-3 — Pre-existing comfortable-top filter still binds

`select_strategy(vix=16.0, NORMAL × IV_LOW × BULLISH, trend with SPEC-079 risk_score=3)` returns `reduce_wait` with reason citing SPEC-079, not BCD. Filter precedence preserved.

### AC-4 — SPEC-111 cash cap still binds

Mock `evaluate_debit_cash_budget` to return accepted=False (cap breach). `select_strategy` returns BCD recommendation, but `sleeve_governance.evaluate_candidate` downgrades it to `reduce_wait` with reason `debit_cash_budget: ...`. Net effect: no debit opened. (This is existing SPEC-111 behavior; SPEC-113 must not bypass it.)

### AC-N — bit-identical regression on string-valued cells

For each of the **26** matrix combinations whose `CANONICAL_MATRIX` value REMAINS a string after the dict-handling refactor (i.e., all `(regime, iv, trend)` triples except `NORMAL.LOW.BULLISH`), the selector lookup must return a **bit-identical** Recommendation before and after the refactor on identical inputs.

Test: enumerate `(regime, iv_signal, trend)` ∈ {LOW_VOL, NORMAL, HIGH_VOL, EXTREME_VOL} × {HIGH, NEUTRAL, LOW} × {BULLISH, NEUTRAL, BEARISH} = 36 combinations. Exclude `NORMAL × LOW × BULLISH`. For each: synthesize matching VixSnapshot / IVSnapshot / TrendSnapshot at known inputs (e.g., VIX 17.0 NORMAL, ivp 50 NEUTRAL), call `select_strategy` BEFORE the refactor (snapshot via git) and AFTER (current branch), assert equality of canonical_strategy, legs (right/side/DTE/delta), size_rule, rationale, position_action.

Rationale: the lookup gains dict-handling for one cell only. AC-N guards against an "I only touched one cell" refactor silently impacting unrelated cells — protects SPEC-103/104/105 stack from regression.

### AC-5 — 26y backtest non-regression on existing cells

Run full 26y backtest BEFORE SPEC-113 deployment and AFTER. For each strategy_key OTHER THAN `bull_call_diagonal`, total PnL / trade count / Sortino must match within floating-point tolerance (existing strategies unaffected). `bull_call_diagonal` count rises (LOW_VOL × BULL + new carve cell trades), PnL rises proportionally to P11 expectation (+46 trades over 26y, +$1,490 mean/contract @ +8vp bracket).

### AC-6 — Cash time-coverage check (live)

After deployment, in first 30 calendar days, log per-trading-day: (open BCDs, ΣBCD debit, ΣBCD debit / liquid_cash). Aggregate at 30 days: time-coverage rate should approximate ~46.4% (within ±10pp tolerance — small-sample noise expected). If observed coverage is materially higher (>60%) for the new cell specifically, file a follow-up issue.

### AC-7 — Sub-cell unit tests

Tests in `tests/test_spec_113_carve.py`:
- VIX threshold 18.0 exactly (returns reduce_wait)
- VIX = 17.99 (returns BCD)
- IV signal HIGH in NORMAL × BULLISH (returns BPS, unaffected by SPEC-113)
- Regime LOW_VOL × IV_LOW × BULL (returns BCD via original branch, NOT via SPEC-113 carve — verify branch hit via trace logging or rationale text)

---

## 4. Files to change

| File | Change |
|---|---|
| `strategy/selector.py` | Add `SPEC_113_VIX_THRESHOLD = 18.0` constant; modify NORMAL × IV_LOW × BULLISH branch per §2.5 |
| `strategy/catalog.py` | Modify `CANONICAL_MATRIX["NORMAL"]["LOW"]["BULLISH"]` to dict per §2.4; extend `matrix_payload()` to render dict-cells |
| `web/templates/strategy_matrix.html` (or equivalent matrix-rendering template) | Render dict-cell sub-condition visibly (frontend) |
| `tests/test_spec_113_carve.py` (new) | Unit tests per AC-7 |
| `tests/test_strategy_unification.py` | Update existing matrix-shape assertions if they assume cell values are strings (line 59-60 iterates `iv_map.values()`); add dict-handling |
| `task/SPEC-113.md` | This file |
| 3 backtest caches (per `feedback_backtest_cache_refresh`) | Stale after change — see §7 |

---

## 5. Test plan

1. Run AC-7 unit tests locally — verify VIX threshold boundary, branch precedence, regime isolation.
2. Run AC-1 / AC-2 / AC-3 / AC-4 as integration tests on the updated selector.
3. Run AC-N regression: snapshot pre-refactor `select_strategy` outputs for 35 (regime × iv × trend) combinations excluding the changed cell. After refactor, replay and assert exact equality.
4. Run AC-5: full 26y backtest pre / post. Confirm non-BCD strategies are unchanged within floating-point tolerance.
5. After deploy: AC-6 first 30-day cash time-coverage check.

---

## 6. PM 知情确认 — Cash floor as 警惕线

**PM has explicitly acknowledged and accepted** the following as part of SPEC-113 approval (2026-06-03):

> SPEC-113 deployment will cause the account's liquid cash to sit at **$14,800 (below the $30k SPEC-111 floor by $15,200)** for approximately **117 trading days per year** (46.4% of trading days), up from the current pre-SPEC-113 baseline of **89 trading days/yr** (35.5%). The +27 days/yr marginal increase is an accepted consequence.

**PM's interpretation of the $30k floor (Q081 P5 verdict)** is therefore confirmed as a **警惕线 (caution threshold)**, NOT a **硬底线 (hard floor)**:
- $30k threshold blocks NEW debit opens below it (existing SPEC-111 behavior — unchanged).
- BCD's bounded loss (max debit lost = $22.2k cap) and 24-day median hold mean below-floor cash is an acceptable 暂态 (transient state) during a single BCD hold.
- The acceptable暂态 interpretation is contingent on BCD being the ONLY debit strategy in the account. See §6.2 forward dependency.

**Date of PM confirmation**: 2026-06-03 (this SPEC document — PM responded to AskUserQuestion on floor character, selected "警惕线 (ratify SPEC-113)").

### 6.2 Forward dependency — re-audit floor when ADDING a 2nd debit strategy

**Owner**: Future Quant Researcher / PM at time of next debit-strategy addition.

**Trigger**: any proposal to add a second debit strategy (e.g., BCD on NDX in addition to SPX, or any other debit-class strategy) to the matrix.

**Re-audit obligation**: at that future time, MUST verify SPEC-111's cash floor mechanism (currently `block-open-only`, NOT `force-close`) remains adequate for cross-strategy concurrent cash occupation. Today, sequential ladder + SPEC-111 floor are REDUNDANT (selector enforces max 1 concurrent BCD, floor enforces it again from a different angle). When a 2nd debit strategy is added, selector's "max concurrent BCD = 1" becomes per-strategy, not cross-strategy — the redundancy disappears, and SPEC-111 floor becomes the SOLE cross-strategy concurrent-cash safeguard.

**Specific question to answer at that future time**:
- Does `block-open-only` floor still suffice when 2+ debit strategies can be open simultaneously and their combined cash occupation can persist for joint duration > single-trade duration?
- Or does SPEC-111.x need a force-close clause, dynamic floor adjustment, or per-strategy max-concurrent enforcement?

This is documented per `feedback_kill_gate_external_read` — today's "redundant safety" is tomorrow's "假阴性不可观测" if not flagged forward.

---

## 7. Rollout

### 7.1 Backtest cache refresh

Per `feedback_backtest_cache_refresh`, all three 26y backtest caches must be regenerated AFTER selector.py change is deployed:

- `data/q041_backtest_cache.json`
- `data/es_backtest_cache.json` (if SPEC-113 affects ES routing — it does NOT, but verify)
- `data/spx_backtest_cache.json`

Cache invalidation is REQUIRED before AC-5 backtest non-regression check is meaningful. Dev should add cache fingerprint mechanism if not already present.

### 7.2 Deployment order

1. Dev: implement §2.4 / §2.5 / §2.6 changes.
2. Dev: run AC-1 through AC-7 + AC-N locally; all green required.
3. Dev: refresh backtest caches (§7.1).
4. Dev: run AC-5 backtest non-regression — confirm non-BCD strategies bit-identical PnL.
5. Quant: spot-check P11 expected ROE — should match 26y backtest BCD count Δ.
6. PM: confirm cash time-coverage live-check schedule set for T+30 days (AC-6).
7. Deploy to old Air (per `feedback_deploy_oldair`).
8. Telegram notify on first SPEC-113-routed trade (rationale text contains "SPEC-113 carve" for traceability).

### 7.3 Live observation window

First 30 calendar days post-deploy:
- AC-6 cash time-coverage check.
- Verify carve-cell trades show expected mean PnL (target ~$1,490/contract @ +8vp bracket equivalent — but live spot is SPX 5000+ scale, so apply 3.13x → expect ~$4,665/trade mean over a sample of N≥5 trades; CI is wide on small N, treat as direction-check only).

### 7.4 Tripwire conditions (revert clause)

Within first 90 days, if any of:
- Cash time-coverage materially > 55% (vs 46.4% target),
- 3+ consecutive SPEC-113-routed BCD trades close at full max loss,
- SPEC-111 75% concurrent debit alert fires due to SPEC-113-routed open,

then escalate: Quant Researcher reviews whether VIX threshold needs tightening or carve needs withdrawal. NOT auto-revert — review-trigger only.

---

## 8. Related work

- **Q081**: cash-bound account framing (`project_account_cash_bound`)
- **Q082**: BCD 26y synth reconstruction (`research/q082/q082_p6_bcd_synth_reconstruction.py`)
- **Q083 phases P0-P15**: this SPEC's research (3 withdrawals, 4 ratify-gates, 2 today's-params recompute)
- **SPEC-111**: cash budget governance (cap=60%, floor=$30k)
- **SPEC-079**: BCD comfortable-top filter (applies unchanged)
- **Memory entries** (lessons accumulated during Q083):
  - `feedback_post_withdrawal_proposals_front_load_robustness`
  - `feedback_absolute_at_today_scale_not_historical_ratio`
  - `feedback_decision_type_governs_significance_standard`
  - `feedback_status_quo_bias_in_verdicts`
  - `feedback_stratum_cutpoint_overfit`
  - `feedback_circular_metric_validation`

---

## 9. Self-note (process)

Q083 took 15 phases + 3 withdrawals + 4 ratify-gates + 2 today's-params recomputes + 2 same-pattern reviewer catches to converge. Final SPEC is a single matrix cell + threshold constant. Three lessons preserved as memory entries for future research:

1. **Post-withdrawal proposals front-load robustness** (P12 catch).
2. **Today-scale absolute, not historical ratio** (P14 + P15 catches — same pattern, 88.9%→46.4% then 4-5%→$8,857).
3. **Decision-type governs significance standard** (P9 catch — alpha vs execution-constraint thresholds are different).

Reviewer's meta-observation in P15: "the meta-pattern is more valuable than SPEC-113 itself — it's a portable rule against ratio-based bias in cash-bound decisions". Recorded.
