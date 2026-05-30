# SPEC-108 — Selector-Gated SPX Execution Ladder

**Type**: research-driven (Q078 ROE-cadence overlay on SPEC-104 + SPEC-105 v2)
**Date**: 2026-05-28
**Status**: **DONE** — Implemented 2026-05-28; Stage 1 shadow-only default enforced
**Owner**: Quant Researcher (draft) → PM approval → Developer implementation
**Source**: Q078 P0-P4 + 2nd Quant G4 final PASS (2026-05-28) + Comprehensive Audit PASS w/ R1-R7 micro-revisions (2026-05-28)
**Parent SPEC**: SPEC-104 Arch-3 + SPEC-105 v2 Gate F (UNCHANGED — this is an execution overlay)

---

## 0. TL;DR

Implement V3 daily-cluster cadence + S3 sizing (3 contracts) as **selector-gated SPX execution ladder** on top of SPEC-104 + SPEC-105 v2 baseline.

```
Cadence:       daily selector evaluation
               at most 1 entry per 5-trading-day cluster
               (≈ 35 action days/year)
Sizing:        S3 = 3 contracts per entry (≈ 7.5% BP per entry)
Strategy:      agnostic — selector-provided per VIX regime
                (BPS, IC, BCD, HV variants)
Exit:          SPEC-077 (21 DTE roll, 60% profit, min 10d held)
Production gates: concurrency (1/strategy, 2 for IC_HV) + BP ceiling (35% NORMAL)
```

**Expected impact (P4 portfolio integration, 26y validated; Q080 block-bootstrap CI overlay)**:

| Metric | Mean | Block-bootstrap p05 / p95 | Note |
|---|---|---|---|
| Net Ann ROE | +1.80pp (8.21% → 10.02%) | p05 +1.68pp / p95 +2.08pp | **robust positive** |
| MaxDD | +1.32pp (-8.71% → -7.40%) | p05 −0.28pp / p95 +3.65pp | 5% prob ladder makes MaxDD slightly worse |
| W20d | +1.16pp (-7.04% → -5.88%) | p05 −0.52pp / p95 +2.18pp | 5% prob ladder makes 20-day tail slightly worse |
| W63d | +3.59pp (-8.66% → -5.06%) | p05 +0.39pp / p95 +4.24pp | marginally positive at lower CI |
| Sharpe | **+0.48 (2.02 → 2.50)** | p05 +0.81 / p95 +1.14 | **corrected from earlier-reported +1.20** |

> ⚠ **Sharpe correction (Q080 P1, 2026-05-29)**: Earlier reported Sharpe Δ +1.20 was inflated by daily-MTM linear smoothing reducing the daily-std denominator. Unsmoothed (exit-day) control gives true Δ **+0.48**. ΔROE / MaxDD / W20d / W63d are invariant under MTM-mode (smoothing artifact isolated to Sharpe).

**5/5 crisis windows improved** (including COVID 2020-02 — combined REDUCES baseline COVID loss by +$15k).

**Bias caveat** (per audit R5; bias-resolution path defers to Stage 1 shadow):
> P4 mean ΔROE is **+1.80pp**. After residual selection-bias deflation (Option B path — bias resolution *deferred* to Stage-1 shadow rather than full engine-without-filters), realistic expected ΔROE is approximately **+0.8pp to +1.3pp**. Stage 1 shadow is mandatory to validate live trade quality before production activation. The shadow data is the only out-of-sample test for the selection-bias question; until it accumulates, bias is *unresolved*, not *resolved*.

**Q078 thesis** (per G4 PASS):
> **Q078 is a ROE-cadence overlay. It does NOT materially improve expiry diversification (eff_count Δ noise). Its value is systematic capture of selector-approved SPX opportunities at controlled sizing.**

> **Quoted wording**: "Q078 does not materially improve expiry diversification after corrected measurement. Its value is systematic capture of selector-approved SPX opportunities at controlled sizing."

**Staged deployment** (mandatory): Stage 1 SHADOW-ONLY → Stage 2 PM-signoff → Stage 3 PM-discretionary full production.

---

## 1. Background

### 1.1 Q078 research outcome
Full Q078 P0-P4 + 2nd Quant G4 PASS. P4 final memo: [`research/q078/q078_p4_memo.md`](research/q078/q078_p4_memo.md).

Q078 found that PM's "8-at-6/18 expiry concentration" symptom is NOT cured by ladder cadence at S3 sizing (eff_count Δ 0.05 = noise). However, V3 daily-cluster cadence with production gates captures more selector-PASS opportunities than current ad-hoc clustering, producing material portfolio-level ROE addition AND risk reduction.

### 1.2 NOT a diversification fix (per R2)

> "Q078 does not materially improve expiry diversification after corrected monthly bucketing measurement. The original PM observation (8 spreads at 6/18 expiry) is empirically real, but cadence + S3 sizing does not solve it (most concurrent positions cluster in same monthly expiry bucket due to 14-day average hold)."

> "The primary thesis is **ROE-cadence**: capturing more selector-PASS opportunities at production-gated sizing produces +1.80pp annualized ROE addition vs SPEC-104+105v2 baseline, with all tail metrics improving."

### 1.3 References
- `research/q078/q078_p0_anchored_memo_2026-05-27.md` — P0 anchored scope
- `research/q078/q078_p1a_memo.md` — cadence attribution (V1b/V3 advance)
- `research/q078/q078_p1b_2_memo.md` — sizing sweep (S3 confirmed)
- `research/q078/q078_p2r_memo.md` — daily MTM smoothing fix
- `research/q078/q078_p3_memo.md` — crisis + walk-forward + bias (standalone analysis)
- `research/q078/q078_p4_memo.md` — portfolio integration (decision-grade)
- `task/q078_p4_g4_resubmit_2026-05-28_Review.md` — 2nd Quant G4 PASS w/ 9 revisions

---

## 2. Scope

Narrow execution-layer SPEC. Adds cadence + sizing overlay on top of SPEC-104+105v2 baseline.

### 2.1 New constants

```python
# strategy/sleeve_governance.py
LADDER_SIZING_CONTRACTS = 3   # S3 fixed per R6 (Q078 SPEC-108)
LADDER_CADENCE_CLUSTER_DAYS = 5   # at most 1 entry per 5-trading-day cluster (V3)
LADDER_BP_CEILING_PCT = 35.0      # NORMAL regime BP ceiling
LADDER_MODE_DEFAULT = "shadow"    # Stage 1 default (per R3)
```

### 2.2 New ladder evaluator

```python
# strategy/q078_ladder.py (new module)

def v3_ladder_eligible(market_state, ladder_state) -> tuple[bool, str]:
    """Q078 V3 daily-cluster cadence + production gates.

    Returns: (eligible, skip_reason_if_not)
    Skip reasons logged per R8: cadence_gap, concurrency_block, bp_ceiling_block,
    selector_wait, etc.
    """
    # Cadence: ≤ 1 entry per 5-trading-day cluster
    if ladder_state.last_entry_date is not None:
        gap_trading_days = trading_days_between(ladder_state.last_entry_date, market_state.date)
        if gap_trading_days < LADDER_CADENCE_CLUSTER_DAYS:
            return False, "cadence_gap"

    # Selector PASS (delegate to selector — strategy-agnostic per R2)
    selector_verdict = market_state.selector_verdict
    if selector_verdict.strategy_name == "Reduce / Wait":
        return False, "selector_wait"

    # Concurrency cap (1 per strategy, 2 for IC_HV)
    cap = 2 if selector_verdict.strategy_name == "Iron Condor (High Vol)" else 1
    same_strategy_open = ladder_state.same_strategy_position_count(selector_verdict.strategy_name)
    if same_strategy_open >= cap:
        return False, "concurrency_block"

    # BP ceiling (35% NORMAL)
    current_bp_pct = ladder_state.current_bp_used_pct_nlv()
    new_max_loss_pct = LADDER_SIZING_CONTRACTS * selector_verdict.max_loss_per_contract / NLV * 100
    if current_bp_pct + new_max_loss_pct > LADDER_BP_CEILING_PCT:
        return False, "bp_ceiling_block"

    return True, ""
```

### 2.3 Strategy agnostic (per R2)

Ladder uses selector-provided strategy type (BPS, IC, BCD, HV variants). Does NOT force BPS. Per VIX regime:
- LOW_VOL + BULLISH → BCD
- NORMAL + NEUTRAL_IV + BULLISH → BPS
- NORMAL + HIGH_IV + NEUTRAL → IC
- HIGH_VOL → BPS_HV, IC_HV, BCS_HV
- etc.

### 2.4 SPEC-077 exit unchanged (per R7)

```
21 DTE roll OR 60% profit (min 10d held) OR stress force exit.
No changes to SPEC-077.
```

### 2.5 API extensions

```
GET /api/sleeve-governance/state
  → add 11 new ladder fields (per audit R6 — field-count corrected):
     ladder_mode: "shadow" | "active" | "off"
     ladder_last_entry_date: ISO date | null
     ladder_cadence_eligible: bool  (today, before strategy gates)
     ladder_strategy_eligible: bool (selector-provided strategy passes)
     ladder_concurrency_block: bool
     ladder_bp_ceiling_block: bool
     ladder_skip_reason: string | null
     ladder_active_positions: int
     ladder_active_total_bp: float
     ladder_active_q042_overlap: bool
     ladder_action_days_ytd: int
```

### 2.6 New shadow log

```
data/q078_ladder_shadow.jsonl

Per selector PASS day:
  {
    "date": "YYYY-MM-DD",
    "ladder_mode": "shadow",                // per audit R7
    "selector_timestamp": "YYYY-MM-DDTHH:MM:SSZ",  // per audit R7 — selector verdict UTC time
    "selector_strategy": "Bull Put Spread",
    "would_enter": false,
    "skip_reason": "cadence_gap",  // or null if would_enter
    "sizing_contracts": 3,
    "theoretical_max_loss": 27000,
    "theoretical_max_loss_pct_nlv": 3.02,
    "theoretical_entry_credit": 540,        // selector-quoted credit per contract (optional)
    "theoretical_exit_rule": "SPEC-077",    // exit logic identifier
    "current_bp_pct_nlv": 8.5,
    "q042_active": false,
    "existing_spx_positions": 2,
    "ladder_action_days_ytd": 23
  }
```

`ladder_mode` and `selector_timestamp` allow Stage-1 shadow data to be compared 1:1 with P4 assumptions when resolving residual bias.

### 2.7 NOT changed

- SPEC-104 Arch-3 state machine (80/50/40 caps) — unchanged
- SPEC-105 v2 Gate F booster — unchanged
- SPEC-077 exit logic — unchanged
- SPEC-103 V1-V7 vetoes — unchanged
- Q042 staged ramp — unchanged
- HV Ladder demoted (0% production) — unchanged
- Selector logic — unchanged (ladder consumes selector verdict)

---

## 3. File Changes (Developer to confirm exact paths)

| File | Action |
|---|---|
| `strategy/sleeve_governance.py` | EDIT — add ladder constants + `LADDER_MODE_DEFAULT` |
| `strategy/q078_ladder.py` | NEW — `v3_ladder_eligible()` + ladder state tracker |
| `data/q078_ladder_shadow.jsonl` | NEW — shadow log file |
| `web/server.py` | EDIT — `/api/sleeve-governance/state` expose ladder fields |
| Production trading engine | EDIT — consume ladder eligibility before SPX BPS entry (only if `LADDER_MODE` = "active") |
| Dashboard `web/templates/portfolio_home.html` | EDIT — display ladder panel (mode, eligible, last_entry, action_days_ytd, skip_reason) |
| `notify/telegram_bot.py` | EDIT — alert on ladder shadow entry signal (so PM can monitor Stage 1) |
| `tests/test_spec_108.py` | NEW — unit tests for ladder evaluator + state + AC verification |
| `task/SPEC-105-v2.md` | APPEND status note — "SPEC-108 (2026-XX-XX): execution-layer overlay added — daily-cluster cadence + S3 sizing. Shadow-only default." |

---

## 4. Acceptance Criteria

| AC# | 描述 | Verification |
|---|---|---|
| AC-108-1 | `LADDER_SIZING_CONTRACTS = 3`, `LADDER_CADENCE_CLUSTER_DAYS = 5`, `LADDER_BP_CEILING_PCT = 35.0` defined in sleeve_governance.py | grep |
| AC-108-2 | `v3_ladder_eligible()` returns (False, "cadence_gap") if last entry < 5 trading days | unit test |
| AC-108-3 | Returns (False, "selector_wait") on REDUCE_WAIT | unit test |
| AC-108-4 | Returns (False, "concurrency_block") when same strategy already open (or IC_HV ≥ 2) | unit test |
| AC-108-5 | Returns (False, "bp_ceiling_block") when projected BP > 35% NORMAL | unit test |
| AC-108-6 | Returns (True, "") on valid entry day | unit test |
| AC-108-7 | `/api/sleeve-governance/state` returns 11 new ladder fields (per audit R6) | curl test |
| AC-108-8 | `LADDER_MODE_DEFAULT = "shadow"` — production cap unchanged from SPEC-104/105v2 baseline when shadow | code review |
| AC-108-9 | `data/q078_ladder_shadow.jsonl` written per selector PASS day | grep latest entries after 1 trading day |
| AC-108-10 | Dashboard displays ladder panel with mode badge + skip reason chips | visual on oldair |
| AC-108-11 | Telegram alert fires on ladder shadow "would enter" event | dry-run |
| AC-108-12 | tests/test_spec_108.py PASS | pytest |
| AC-108-13 | tests/test_spec_103-107 still PASS (no regression) | pytest |
| AC-108-14 | Backtest cache refresh per `feedback_backtest_cache_refresh` | files regenerated |
| AC-108-15 | Stage 1 shadow mode = `LADDER_MODE_DEFAULT="shadow"` ENFORCED at deploy time | env var check |
| AC-108-16 | Action days/year counter tracks ladder eligibility (eligible-but-shadow ≠ skip) | dashboard visual |
| **AC-108-17** | **(per audit R3) Automated CI test** — In absence of explicit `LADDER_MODE=active`, ladder mode resolves to `"shadow"`, production order path is disabled, shadow log still writes would-enter events | **pytest CI test (NOT manual)** |
| **AC-108-18** | **(per audit R3) Negative CI test** — Given `LADDER_MODE_DEFAULT="shadow"`, `v3_ladder_eligible()` may return `eligible=True`, but `production_order_allowed` must be `False` | **pytest CI test (NOT manual)** |

---

## 5. Monitoring Obligations (Stage 1 shadow + post-deploy)

These must be live during Stage 1:

| # | Monitor | Trigger | Action |
|---|---|---|---|
| 1 | Ladder shadow signal rate | < 15/yr OR > 60/yr | Compare to P4 expectation (~35/yr); investigate divergence |
| 2 | Skip reason distribution | concurrency > 50% | Concurrency cap too tight; review |
| 3 | Skip reason: BP ceiling | > 20% | BP allocation conflict with Q042/SPX; review |
| 4 | Theoretical PnL tracking | Live shadow > ±2x P4 expectation | Investigate model drift |
| 5 | Action burden | > 50 days/yr | Operationally heavy; reduce or pause |
| 6 | Q042 / SPX overlap | Combined BP > 80% NLV | Capital competition — review and possibly throttle |
| 7 | Shadow trade quality (when Stage 2 active) | Live W20d/W63d degradation > +0.5pp from baseline | Layer-1 protection check |
| 8 | **Ladder-only incremental tail monitor (per audit R1)** | Rolling 20d ladder-only PnL OR rolling 63d ladder-only PnL degradation > +0.5pp NLV equivalent vs P4 expected range | PM review — does NOT replace portfolio V1/V2/V3, explains whether ladder itself drives deterioration |
| 9 | **Per-strategy ladder trigger distribution drift (per SPEC-108.1 R4)** | Rolling 90-day share of any strategy deviates from historical band by > 15pp | PM-discretionary review; if unexplained by regime shift, investigate selector before continuing shadow / production |

All Stage 1 monitor triggers are PM-discretionary review (per `feedback_spec_review_obligation`).

### 5.1 Ladder-only incremental tail metric definition (per R1)

```
ladder_only_W20d:
  sum(ladder MTM contributions) over rolling 20 trading days
  (baseline + booster contributions excluded)

ladder_only_W63d:
  sum(ladder MTM contributions) over rolling 63 trading days
  (baseline + booster contributions excluded)

Expected ranges (from P4):
  ladder-only contribution to W20d: roughly +1.16pp / 13x ≈ +0.09pp per 20d on average
  ladder-only contribution to W63d: roughly +3.59pp / 4x ≈ +0.90pp per 63d on average

Alert: actual ladder-only W20d/W63d falls > 0.5pp below expected range
```

This monitor MUST be live from Stage 2 onward. During Stage 1 shadow, the theoretical equivalent is computed from the shadow log MTM and tracked alongside.

---

## 6. Staged Rollout (per R3 + R4 + R5 — MANDATORY)

> ✅ **STAGE 2 ADVANCEMENT UNFROZEN (path conditions)** (2026-05-29 update) — Q080 P1 confirmed ΔROE invariant; P2 block-bootstrap p05 = +1.68pp robust positive; P3 calibrated 0.5pp at strategy-comparison level. Sharpe number corrected (see §0). SPEC-108.1 (DRAFT 2026-05-29) adds R1-R4 gates required before actual Stage 2 production activation. **Stage 2 will lift after SPEC-108.1 deployed AND Stage 1 R3 regime-coverage criterion met (per SPEC-108.1 §2 R3) AND portfolio-stress overnight-gap < 12% NLV (per SPEC-108.1 §2 R1)**. Stage 1 shadow continues unchanged. See [`task/SPEC-108.1.md`](task/SPEC-108.1.md), [`task/chatgpt_review_response_2026-05-29.md`](task/chatgpt_review_response_2026-05-29.md), [`research/q080/q080_memo.md`](research/q080/q080_memo.md). — Quant Researcher

**Stage 1 — Shadow only (MANDATORY initial state)**
- `LADDER_MODE = "shadow"` (default per AC-108-15)
- V3 ladder evaluator runs daily; outputs "would-enter" decision + skip reasons
- All trades logged to `q078_ladder_shadow.jsonl`
- NO production order entry from ladder logic
- Telegram alerts say "would have entered" / "skipped because X"
- Dashboard ladder panel shows current state

**Stage 2 — Limited production activation (PM-signoff REQUIRED per R4)**
- PM must explicitly approve `LADDER_MODE = "active"` flip
- **Minimum evidence gate (R5)**: ≥ 10 shadow candidate entries OR explicit PM waiver
- Stage 2 advancement gate (ALL must hold):
  ```
  1. No V1/V2/V3 hard-gate breach in shadow period
  2. No single shadow trade projected loss > 5% NLV
  3. No unexpected Q042 / SPX capital conflict
  4. Realized action burden acceptable to PM
  5. Shadow candidate quality not materially worse than P4 expectation
  6. PM explicitly signs off
  7. ≥ 10 shadow entries observed (floor — preserved from R5)
  8. [SPEC-108.1 R1] portfolio_stress_overnight_gap() returns mark_loss < 12% NLV
  9. [SPEC-108.1 R3] At least ONE coverage profile met, OR PM waiver citing reason:
       (i)  ≥3 entries each in ≥2 distinct VIX regimes (LOW_VOL, NORMAL, HIGH_VOL)
       OR
       (ii) ≥3 entries each in ≥2 distinct strategy branches
            (bull_call_diagonal, iron_condor, iron_condor_hv, bull_put_spread,
             bull_put_spread_hv, bear_call_spread_hv)
       OR
       (iii) PM explicitly waives, citing operational reason
  ```
- On approval: production order entry triggered by ladder eligibility
- All monitoring obligations active

**Stage 3 — Full production (PM-discretionary after Stage 2 forward evidence)**
- Standard monitoring continues
- Review only triggered by monitor thresholds (§5)

No time locks on Stage advancement (per `feedback_spec_review_obligation`). Stage 1 minimum evidence gate (R5) is the only hard requirement.

---

## 7. Out of Scope

| Item | Why |
|---|---|
| Modify SPEC-104 R1/R5/R6 numeric caps | Layer-1 frozen |
| Modify SPEC-105 v2 Gate F booster | Booster is Q074 territory |
| Modify SPEC-077 exit logic (60% profit / 21 DTE roll) | SPEC-077 frozen per Q078 P0 R3 |
| Change S3 sizing (3 contracts) | R6 hard requirement |
| Change cluster rule (5 trading days) | Q078 V3 cadence locked |
| BPS-only / credit-only ladder restriction | Strategy-agnostic per R2 + P0 R8 |
| Q042 / HV Ladder changes | Unrelated SPECs |
| New strategy primitives | Q079+ scope |
| Constant 30 DTE override | Use selector-provided DTE per P0 R8 |
| BCS-style ladder (call side) | Q078 V3 strategy-agnostic already includes BCS_HV |
| Skip-day catchup / weekly variants | V1b / V2 rejected at G2 |
| 4-contract sizing | S2 failed 5% NLV gate at P1b-2 |
| Diversification claim in PM-facing language | NOT a diversification fix per R2 |
| **No booster off-ladder bonus entries (per audit R2)** | SPEC-105 v2 Gate F booster is a separate layer. Q078 ladder only consumes selector-approved opportunities under the V3 cadence rule. Ladder MUST NOT create extra entries just because Gate F is active. |

---

## 8. Design Notes

### 8.1 Why V3 daily-cluster, not weekly cadence

Per R2 / G4 reframing: V3 is a **daily-check system, not a weekly ladder**. PM-facing language must reflect this:
```
Daily selector evaluation.
At most one entry per 5-trading-day cluster.
Expected ~35 action days/year.
```

### 8.2 Why S3 (3 contracts)

Per P1b-2: at PM's spread width (~$23k max-loss per contract), 4 contracts (S2) breaches 5% NLV worst-trade gate (-5.72% NLV per IC NORMAL × 4). S3 (3 contracts × $9.6k worst per contract = -4.29% NLV) stays within gate.

### 8.3 Why strategy-agnostic

Per P0 R8 + G2.5 R2: ladder defers to selector for strategy type. PM's mental model "weekly BPS ladder" is incorrect — pure BPS opportunities are rare (96 days / 26y). Ladder mostly runs BCD, IC, HV variants per selector recommendation.

### 8.4 Why Stage 1 shadow mandatory

Per G4 PASS (2nd Quant 2026-05-28): residual selection-bias uncertainty remains. Stage 1 shadow validates live trade quality against P4 expectations before any production capital commitment. Bias resolution path = real shadow data, not engine modification.

### 8.5 Concurrency + BP gates are production-faithful

Per G2.5 + P2 Layer 2: ladder respects all engine production gates. Same concurrency cap (1 per strategy, 2 for IC_HV) and BP ceiling (35% NORMAL) used by engine's regular trades. This is "execution layer, not strategy override".

### 8.6 Crisis robustness

Per P4: all 5 named crisis windows (DotCom 2000, PreGFC 2007, Vol 2018, COVID 2020, Bear 2022) show COMBINED baseline+ladder PnL improved vs baseline alone. COVID was previous concern; combined REDUCES baseline COVID loss by +$15k.

### 8.7 V1b weekly catch-up — Historical alternative only — NOT implementable under SPEC-108 (per audit R4)

> **Developer prohibition (per audit R4)**: Developer must NOT implement V1b under SPEC-108. SPEC-108 implements V3 daily-cluster cadence ONLY. Any swap from V3 to V1b requires separate PM approval and SPEC amendment (i.e. SPEC-108.1 or SPEC-109). This section is governance memory, NOT an implementation alternative.

Per PM review 2026-05-28, V1b weekly catch-up was tested at portfolio level as comparison:

```
V1b S3 portfolio metrics (20-seed):
  Ann ROE Δ:   +1.743pp (vs V3 +1.802pp — 0.06pp diff = NOISE)
  MaxDD Δ:     +1.742pp BETTER (vs V3 +1.318pp — 0.42pp diff)
  W20d Δ:      +1.686pp BETTER (vs V3 +1.161pp — 0.53pp diff, borderline)
  W63d Δ:      +3.268pp BETTER (vs V3 +3.592pp)
  Sharpe Δ:    +1.152 (vs V3 +1.196)
  Action days: ~30/yr (vs V3 ~35/yr) + weekly check only (no daily monitoring)
```

V1b is operationally lighter with similar metrics (most differences noise-level under 0.5pp framework). PM elected V3 in SPEC-108 because (a) operational burden of daily check acceptable, (b) downstream P4 / crisis / walk-forward all V3-based, (c) ROE differences noise.

**If future operational constraint changes** (PM bandwidth reduction, etc.), V1b is a documented swap-in alternative — same SPEC scope, just cadence rule change. Would require minor revalidation but no new research.

---

## 9. Deploy

1. Developer implements file changes (per §3) → local AC1-AC16 verification
2. Backtest cache refresh per `feedback_backtest_cache_refresh`
3. Commit + push
4. Old Air `git pull` + restart web (per `feedback_deploy_oldair`)
5. **Stage 1 shadow mode activates** by default (`LADDER_MODE_DEFAULT = "shadow"`)
6. PM monitors Stage 1 for PM-discretionary period (≥ 10 shadow entries per R5)
7. PM gates Stage 2 advancement after sign-off all 7 advancement conditions
8. Stage 3 advancement is PM-discretionary after Stage 2 forward evidence

Smoke tests:
- `curl https://oldair.spxstrat.app/api/sleeve-governance/state` — confirm `ladder_mode`, `ladder_cadence_eligible`, `ladder_skip_reason` fields appear
- Confirm `/portfolio_home` dashboard displays ladder panel
- Verify Telegram alerts fire on ladder "would have entered" shadow event
- Verify `data/q078_ladder_shadow.jsonl` entries written per selector PASS day

---

## 10. Estimated Effort

| Phase | CC+gstack | Human |
|---|---|---|
| Code changes (sleeve_governance + ladder evaluator + API + dashboard + alerts + shadow log) | ~3h | ~3 days |
| Backtest cache refresh + AC validation | ~1h | ~2h |
| tests/test_spec_108.py | ~30 min | ~3h |
| AC verification + deploy | ~30 min | ~2h |
| **Total** | **~5h** | **~4 days** |

---

## 11. PM Approval Signature

**PM signed 2026-05-28** (single "approve" affirms all 10 items below)

- [x] Approve V3 daily-cluster cadence with 5-trading-day cluster rule
- [x] Approve S3 sizing fixed at 3 contracts (per R6)
- [x] Approve strategy-agnostic ladder (selector-provided per R2)
- [x] Approve Stage 1 shadow-only initial deployment (per R3)
- [x] Approve Stage 2 PM-signoff advancement gate with ≥ 10 shadow entries (per R4 + R5)
- [x] Approve "Q078 is ROE-cadence overlay, NOT expiry-diversification fix" PM-facing language (per R2)
- [x] Approve monitoring obligations (§5) and staged rollout (§6)
- [x] Approve out-of-scope list (§7)
- [x] Confirm SPEC-108 number (not SPEC-107 which is Intraday Recommendation Governance)
- [x] Acknowledge audit micro-revisions R1-R7 applied (bias caveat, ladder-only W20d/W63d monitor, no booster off-ladder bonus, AC-108-17/18 CI tests, V1b non-implementable, API 11-field count, shadow log ladder_mode + selector_timestamp)

---

## 12. Developer Handoff Notes

### Implementation blocker checklist

1. **New ladder constants** — `strategy/sleeve_governance.py`:
   - `LADDER_SIZING_CONTRACTS = 3`
   - `LADDER_CADENCE_CLUSTER_DAYS = 5`
   - `LADDER_BP_CEILING_PCT = 35.0`
   - `LADDER_MODE_DEFAULT = "shadow"`

2. **New ladder evaluator** — `strategy/q078_ladder.py`:
   - `v3_ladder_eligible(market_state, ladder_state) -> tuple[bool, str]`
   - `LadderState` class tracking last_entry_date, active_positions
   - Cadence check: trading days between last entry and today ≥ 5
   - Concurrency check: same-strategy open count
   - BP ceiling check: current_bp + new_max_loss ≤ 35% NLV

3. **Production trading consume** — when `LADDER_MODE = "active"`:
   - SPX BPS order builder MUST query `v3_ladder_eligible(state, ladder_state)` before entering
   - If `eligible == False`, skip entry, log skip reason
   - If `eligible == True`, enter with selector-provided strategy at S3 sizing

4. **API extension** — `/api/sleeve-governance/state` add 9 ladder fields (§2.5)

5. **Dashboard display** — `/portfolio_home`:
   - Ladder panel with mode badge (shadow / active / off)
   - Today's cadence eligibility status
   - Last entry date
   - Skip reason (if today not eligible)
   - Action days YTD counter
   - Active ladder positions count

6. **Telegram alerts** — Stage 1 shadow mode:
   - Daily alert if `would_enter = True` (so PM sees signal frequency)
   - Periodic summary (weekly?) of skip reason distribution

7. **Shadow log** — `data/q078_ladder_shadow.jsonl`:
   - One JSON line per selector PASS day
   - All fields per §2.6 schema

8. **Stage 1 mandatory shadow** — `LADDER_MODE_DEFAULT = "shadow"` at deploy. PM must explicitly set env var `LADDER_MODE=active` to advance to Stage 2. Do NOT enable production execution by default.

9. **Backtest cache refresh** — per `feedback_backtest_cache_refresh`: SPX / ES / Q041 three caches must regenerate after deployment.

10. **No-regression check** — `tests/test_spec_103/104/105/106/107.py` must still PASS.

### Implementation discipline (per PM)

> Implement SPEC-108 exactly. Do NOT modify SPEC-104 numeric caps, SPEC-105 v2 Gate F booster, SPEC-077 exit logic, or any selector logic. Stage 1 shadow mode is mandatory initial state, NOT optional. Do NOT flip to "active" mode without explicit PM env var change. Do NOT skip cadence/concurrency/BP checks. Strategy is selector-provided (agnostic), NOT BPS-only.

### Reference docs Developer should read before implementing

1. `task/SPEC-108.md` (this file) — full SPEC
2. `research/q078/q078_p4_memo.md` — P4 portfolio integration evidence
3. `task/q078_p4_g4_resubmit_2026-05-28_Review.md` — 2nd Quant G4 PASS w/ 9 revisions
4. `task/SPEC-104.md` + `task/SPEC-105-v2.md` — parent SPECs (UNCHANGED)
5. `task/SPEC-077.md` (if exists) — exit logic (UNCHANGED)
6. `strategy/sleeve_governance.py` — existing R1/R5/R6 caps + state functions

---

## 13. PROJECT_STATUS.md 索引项 (Planner 自助)

```
- `SPEC-108` — Q078 Selector-Gated SPX Execution Ladder. **DRAFT 2026-05-28.**
  Q078 full P0-P4 + 2nd Quant G4 PASS w/ 9 revisions. ROE-cadence overlay on
  SPEC-104+105v2 baseline: V3 daily-cluster cadence (≤1 entry per 5-trading-day
  cluster, ~35 action days/year) + S3 sizing (3 contracts ≈ 7.5% BP per entry).
  Strategy-agnostic (selector-provided per VIX regime). Expected: ROE +1.80pp,
  MaxDD +1.32pp BETTER, W20d +1.16pp BETTER, W63d +3.59pp BETTER, Sharpe +1.20.
  5/5 crisis windows improved (incl COVID). Stage 1 shadow-only MANDATORY;
  Stage 2 advancement requires PM signoff + ≥10 shadow entries. NOT a
  diversification fix (eff_count Δ noise). AC1-AC16. — `See: task/SPEC-108.md`,
  `research/q078/q078_p4_memo.md`
```

---

## Review

**Reviewer**: Quant Researcher
**Date**: 2026-05-28
**Verdict**: **PASS** — implementation matches SPEC fidelity; safe to remain DONE
**Implementation commit**: `50a72df` (feat: SPEC-108 selector-gated SPX execution ladder)
**Handoff doc**: [`task/SPEC-108_handoff.md`](task/SPEC-108_handoff.md)

### Test evidence
- `tests.test_spec_108`: **12/12 PASS** (local re-run 2026-05-28)
- Adjacent regression `tests.test_spec_103..107`: **53/53 PASS** (no breakage)
- Old Air deploy smoke test (per Developer report): API returns 200; `ladder_mode=shadow`, `ladder_production_order_allowed=false`, `ladder_would_enter=false`

### Fidelity audit — 18 AC × implementation cross-check

| AC# | SPEC ask | Implementation | PASS |
|---|---|---|---|
| 1 | constants defined | `sleeve_governance.py:41-44` LADDER_SIZING_CONTRACTS=3, CLUSTER_DAYS=5, BP_CEILING=35.0, MODE_DEFAULT="shadow" | ✅ |
| 2 | cadence_gap < 5 trading days | `q078_ladder.py:202` trading_days_between < cluster_days | ✅ |
| 3 | selector_wait on "Reduce / Wait" string | `q078_ladder.py:118-119` handles both "Reduce / Wait" string + "reduce_wait" key (more robust than SPEC) | ✅ |
| 4 | concurrency block; IC_HV cap 2 / others 1 | `q078_ladder.py:211-213` exact match | ✅ |
| 5 | bp_ceiling > 35% NORMAL | `q078_ladder.py:217-219` exact match | ✅ |
| 6 | valid entry returns (True, "") | `q078_ladder.py:221` | ✅ |
| 7 | 11 R6 fields on `/api/sleeve-governance/state` | `sleeve_governance.py:680-693` all 11 present (+2 derived: ladder_would_enter, ladder_production_order_allowed for shadow-payload exposure) | ✅ |
| 8 | LADDER_MODE_DEFAULT="shadow" + cap unchanged | `sleeve_governance.py:100-103` ladder_mode() validates {shadow/active/off}, falls back to default | ✅ |
| 9 | shadow log written per selector PASS day | `sleeve_governance.py:534-537` commit-gated write via `has_shadow_log_for_date` idempotency | ✅ |
| 10 | dashboard ladder panel | `portfolio_home.html:842-868` panel with mode badge + chips; uses `var(--text-2)` for labels (no `--text-muted` abuse) | ✅ |
| 11 | Telegram shadow alert | `telegram_bot.py:1485-1503` `scheduled_ladder_shadow_push` filters on shadow_log_written + would_enter + mode==shadow | ✅ |
| 12 | tests/test_spec_108.py PASS | 12/12 | ✅ |
| 13 | no regression SPEC-103..107 | 53/53 | ✅ |
| 14 | backtest cache refresh | Developer reports 5/5 endpoints OK on old Air | ✅ |
| 15 | shadow ENFORCED at deploy | Developer confirms no `LADDER_MODE` env on old Air; resolved mode = shadow | ✅ |
| 16 | action_days counter (eligible only) | `q078_ladder.py:280` only `+1 if eligible`; `tests/test_spec_108.py:test_ac108_16` covers | ✅ |
| 17 | CI test — shadow default + production disabled + shadow log still writes | `tests/test_spec_108.py:test_ac108_17` | ✅ |
| 18 | CI test — eligible=True does NOT allow order under shadow | `tests/test_spec_108.py:test_ac108_18` | ✅ |

### Invariant audit (5 mandatory unchanged)
- ✅ SPEC-104 Arch-3 caps — `git diff` confirms no numeric changes
- ✅ SPEC-105 v2 Gate F booster — only status-note 1-line append, no logic change
- ✅ SPEC-077 exit logic — untouched
- ✅ SPEC-103 V1-V7 vetoes — untouched
- ✅ Selector logic (`strategy/selector.py`) — untouched; ladder only consumes verdict
- ✅ Production entry path under LADDER_MODE≠active — `web/server.py:4467,4474` early-return ensures pre-SPEC-108 behavior is unchanged when mode != "active"
- ✅ No booster off-ladder bonus — ladder only reads selector verdict, never inspects Gate F state
- ✅ V1b NOT implemented — only V3 cadence (`q078_ladder.py:196-221`); §8.7 prohibition honored
- ✅ S3=3 contracts and 5-day cluster locked as constants — not parameterized

### Audit micro-revision verification (R1-R7 per audit packet)
- ✅ **R1** ladder-only W20d/W63d monitor — SPEC §5 row 8 + §5.1 metric definition (will activate Stage 2+); not yet a code metric since no live ladder PnL exists in Stage 1
- ✅ **R2** no booster off-ladder bonus — SPEC §7 + code never reads Gate F
- ✅ **R3** AC-108-17/18 CI tests — both PASS, automated
- ✅ **R4** V1b non-implementable — only V3 implemented; SPEC §8.7 prohibition explicit
- ✅ **R5** bias caveat — SPEC §0 displays +1.80pp mean + +0.8 to +1.3pp deflated
- ✅ **R6** 11 API fields — verified above (AC-108-7)
- ✅ **R7** shadow log `ladder_mode` + `selector_timestamp` — `q078_ladder.py:267-268` + `theoretical_entry_credit` + `theoretical_exit_rule` exposed (lines 275-276)

### Notes for future work (NON-blocking)
1. **Holiday list (`q078_ladder.py:16-21`)** covers only 2025-2026 hard-coded. For 2027+ this drifts. Recommend swap to a maintained source (e.g., `pandas_market_calendars` or annual append) before Stage 2 activation.
2. **`_max_loss_per_contract` falls back to $9k** when verdict lacks the field. This is reasonable but masks data-quality issues — recommend logging when fallback fires.
3. **`ladder_action_days_ytd` payload semantic**: `shadow_payload` adds +1 if eligible vs the persisted counter only increments in `mark_entry()` (active mode). In Stage 1 shadow this means dashboard counter is would-be projection, not realized. Document this in §5 monitor #1 expectation calibration before Stage 2 review.
4. **Stage 1 shadow validation gate**: first real shadow event needs a selector PASS day (current state: "Reduce / Wait"). Stage 2 advancement minimum-evidence gate (≥10 entries) starts counting from first shadow_log_written event.
5. **Old Air smoke test** independently re-verified by Quant: blocked by local DNS / cert — relied on Developer's report. Recommend automated CI smoke ping for Stage 2.

### Verdict statement
> SPEC-108 implementation fidelity PASS. All 18 ACs covered; 12/12 SPEC-108 + 53/53 adjacent SPEC tests PASS; 5 invariants honored; R1-R7 audit micro-revisions all reflected in code or SPEC; Stage 1 shadow safety enforced via env-default + `production_order_allowed` guard. SPEC-108 remains **Status: DONE**. Stage 1 shadow data collection now standing-open.

---

## 14. References

- `research/q078/q078_p4_memo.md` — P4 portfolio integration (decision-grade)
- `research/q078/q078_p3_memo.md` — P3 crisis + walk-forward + bias (standalone)
- `research/q078/q078_p2r_memo.md` — P2 REVISED (eff_count + daily MTM fix)
- `research/q078/q078_p1b_2_memo.md` — sizing sweep (S3 confirmed)
- `research/q078/q078_p1b_1_memo.md` — model corrections
- `research/q078/q078_p1a_memo.md` — cadence attribution
- `research/q078/q078_p0_anchored_memo_2026-05-27.md` — P0 anchored scope (5% NLV + noise threshold)
- `task/q078_p4_g4_resubmit_2026-05-28_Review.md` — 2nd Quant G4 PASS verdict
- `task/q078_spec108_comprehensive_audit_packet_2026-05-28.md` — Quant audit packet
- `task/q078_spec108_comprehensive_audit_2026-05-28_Review.md` — 2nd Quant AUDIT PASS w/ R1-R7 micro-revisions (applied above)
- `task/q078_p3_g4_2nd_quant_review_2026-05-28_Review.md` — G4 REVISE (P3 round)
- `task/q078_p1b_g2_5_2nd_quant_review_2026-05-28_Review.md` — G2.5 PASS
- `task/q078_p1a_g2_2nd_quant_review_2026-05-27_Review.md` — G2 PASS
- `task/q078_framing_2nd_quant_review_2026-05-27_Review.md` — framing PASS
- `task/SPEC-104.md` — Arch-3 architecture (UNCHANGED)
- `task/SPEC-105-v2.md` — Gate F booster (UNCHANGED)
- `~/.claude/.../memory/feedback_noise_threshold.md` (NEW 2026-05-28)
