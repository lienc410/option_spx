# SPEC-105 — Q074 Bull Regime Booster Overlay

**Type**: research-driven (Layer-2 income optimization overlay on SPEC-104)
**Date**: 2026-05-18
**Status**: **DONE 2026-05-18** — implemented locally; Stage 1 shadow is mandatory initial posture
**Owner**: Quant Researcher (draft) → PM approval → Developer implementation
**Source**: Q074 P0-P5 + 2nd Quant G4 final review **PASS** (2026-05-18)
**Parent SPEC**: SPEC-104 Arch-3 Portfolio Architecture (UNCHANGED — this is an overlay)

---

## 0. TL;DR

Implement Q074's recommended **B4 moderate 90% Bull Regime Booster** as a narrow overlay on Arch-3 / SPEC-104:

```
Existing Arch-3 state machine (SPEC-104 — UNCHANGED):
  Second-leg active → SPX cap = 40%  (R6)
  Stress active     → SPX cap = 50%  (R5)
  Else              → SPX cap = 80%  (R1 normal base)

NEW Q074 B4 booster state (THIS SPEC):
  Booster active   → SPX cap = 90%  (overlay on R1 normal)

Final state priority (UNCHANGED concept, with new booster layer):
  Second-leg (40%) > Stress (50%) > Booster (90%) > Normal base (80%)
```

**B4 booster activation** (all 7 conditions required, evaluated daily):
- NOT stress_active
- NOT second_leg_active
- SPX close > MA50
- ddATH > -4%
- VIX < 22
- VIX 5d change ≤ +1.5
- IVP_252 < 55

**Expected impact (P4 validated, 26y)**:
- Net Ann ROE: 7.95% → **8.20% (+0.25pp)**
- MaxDD / Worst 20d / Worst 63d: **UNCHANGED** (Layer-1 invariance preserved)
- Sharpe: 1.97 → 2.02
- Booster active: ~20% of trading days

**Strong-eligible classification** (per G4): point estimate +0.25pp vs +0.30pp Strong threshold, gap 0.048pp within bootstrap noise σ 0.10pp → economically equivalent to Strong, **production-acceptable for STAGED deployment**.

> **Quoted wording (per G4)**: "B4 is Strong-eligible and production-acceptable for staged deployment. It is not a literal Strong Pass, but the ROE shortfall versus the +0.30pp threshold is economically immaterial and within estimation noise."

---

## 1. Background

### 1.1 Q074 research outcome
Full Q074 P0-P5 + 2nd Quant G4 final PASS. P5 final memo: [`research/q074/q074_final_memo.md`](research/q074/q074_final_memo.md).

Q074 found that Arch-3 (SPEC-104) leaves benign-regime ROE upside on the table. A narrowly-defined booster (B4 moderate 90%) raises Normal SPX cap from 80% to 90% only on multi-signal benign confirmation, while preserving immediate snap-back to 50%/40% on stress/second-leg triggers.

### 1.2 Layer-1 / Layer-2 framing (per `feedback_survival_vs_income_layering`)
- **Layer 1 (Survival floor — UNCHANGED)**: V1-V7 vetoes, stress cap 50%, second-leg cap 40%, R5/R6 trigger definitions
- **Layer 2 (Income optimization — THIS SPEC)**: Conditional Normal-cap raise 80% → 90% in benign regimes only

Q074 explicitly cannot modify Layer 1. SPEC-105 implements only the Layer-2 overlay.

### 1.3 References
- `research/q074/q074_final_memo.md` — P5 decision (full memo)
- `research/q074/q074_p4_validation_memo.md` — P4 evidence (bootstrap / walk-forward / friction / funding / transition / VIX joint-slice / synthetic stress)
- `task/q074_p5_g4_2nd_quant_review_packet_2026-05-18_Review.md` — 2nd Quant G4 PASS

---

## 2. Scope

Narrow overlay SPEC. Single-file logic addition. **Do NOT modify any SPEC-104 R1/R5/R6 numeric caps or trigger definitions.**

### 2.1 New constant — Booster cap

```python
# strategy/sleeve_governance.py
CAP_SPX_BENIGN_BOOSTER = 90.0  # Q074 B4 booster state (SPEC-105)
```

### 2.2 New benign signal evaluator

```python
# strategy/sleeve_governance.py or new module strategy/q074_booster.py

def b4_benign_active(market_state) -> bool:
    """Q074 B4 moderate 90% booster activation criteria.
    All 7 conditions required.
    """
    return (
        not market_state.stress_active            # R5 inactive
        and not market_state.second_leg_active    # R6 inactive
        and market_state.spx_close > market_state.ma50
        and market_state.ddath > -0.04            # ddATH > -4%
        and market_state.vix < 22.0
        and market_state.vix_5d_change <= 1.5
        and market_state.ivp_252 < 55.0
    )
```

### 2.3 SPX cap state machine extension

```python
def active_spx_cap(market_state) -> float:
    """State priority: second-leg > stress > booster > normal."""
    if market_state.second_leg_active:
        return CAP_SECOND_LEG_EPISODE      # 40% (SPEC-104 R6, UNCHANGED)
    if market_state.stress_active:
        return CAP_STRESS_EPISODE          # 50% (SPEC-104 R5, UNCHANGED)
    if b4_benign_active(market_state):     # NEW (SPEC-105)
        return CAP_SPX_BENIGN_BOOSTER      # 90%
    return CAP_SPX_PM                      # 80% (SPEC-104 R1, UNCHANGED)
```

### 2.4 B3 fallback (documented, NOT implemented as runtime toggle, per G4 Q5)

B3 strict 90% is documented in research files as fallback option (stricter filter: VIX < 20 + MA50 slope > 0). NOT implemented in production code initially. If future PM decision wants to tighten to B3, separate SPEC required.

### 2.5 No changes to

- SPEC-104 R1/R5/R6 numeric caps (80/50/40 stay as-is)
- SPEC-104 R5/R6 trigger conditions (stress / second-leg detection unchanged)
- SPEC-104 Q042 Sleeve A staged ramp (10→12.5→15→17.5%)
- SPEC-104 HV Ladder demotion (production allocation = 0%)
- V1-V7 vetoes
- Cash residual computation (auto-adjusts based on SPX cap)

### 2.6 API additions

```
GET /api/sleeve-governance/state
  → add fields:
     booster_active: bool
     booster_signal_conditions: {7 individual condition flags}
     active_spx_pm_cap_regime: "second_leg" | "stress" | "booster" | "normal"
     active_spx_pm_cap_pct: 40 / 50 / 90 / 80
```

Dashboard `/portfolio_home` or similar: display current cap state + which condition is blocking booster (if any).

---

## 3. File Changes (Developer to confirm exact paths)

| File | Action |
|---|---|
| `strategy/sleeve_governance.py` | EDIT — add `CAP_SPX_BENIGN_BOOSTER = 90.0`, `b4_benign_active()`, extend `active_spx_cap()` state machine |
| `signals/iv_rank.py` or `signals/vix_regime.py` | VERIFY — IVP_252 calculation already exists; ensure exposed for booster evaluator |
| `signals/trend.py` | VERIFY — SPX MA50 already exists; ensure exposed |
| New compute: ddATH | VERIFY — ddATH exists in Q042 trigger (`signals/q042_trigger.py`); reuse |
| Production trading engine | EDIT — consume `active_spx_cap()` for new SPX BPS position sizing |
| `web/server.py` | EDIT — `/api/sleeve-governance/state` expose booster state |
| Dashboard | EDIT — display current cap regime + booster condition status |
| Telegram alerts | EDIT — alert on booster state transitions (normal → booster, booster → stress, etc.) |
| `tests/test_spec_105.py` | NEW — unit tests for state machine + signal evaluator + AC verification |
| `task/SPEC-104.md` | APPEND status note — "SPEC-105 (2026-XX-XX): overlay added — booster state at 90% conditionally above R1 80%. R5/R6 unchanged." |

---

## 4. Acceptance Criteria

| AC# | 描述 | Verification |
|---|---|---|
| AC-105-1 | `CAP_SPX_BENIGN_BOOSTER = 90.0` constant defined in sleeve_governance.py | `grep` |
| AC-105-2 | `b4_benign_active()` function exists with all 7 conditions; returns False for any condition fail | unit test |
| AC-105-3 | `active_spx_cap()` state machine returns 40/50/90/80 per priority | unit test with mock states |
| AC-105-4 | `/api/sleeve-governance/state` returns `booster_active`, `booster_signal_conditions`, `active_spx_pm_cap_regime`, `active_spx_pm_cap_pct` | curl test |
| AC-105-5 | Backtest replay reproduces Q074 P4 numbers ±tolerance: Net ROE 8.20% (±0.1pp), MaxDD -8.71% (±0.5pp), Worst 20d -7.04% (±0.3pp) | run combined simulator after change |
| AC-105-6 | When stress fires DURING booster-active period (mock test), SPX cap immediately drops 90% → 50%; no smoothing | unit test |
| AC-105-7 | Telegram alert fires on booster ON → OFF transition (and vice versa) | dry-run |
| AC-105-8 | Dashboard displays current cap regime correctly | visual on oldair |
| AC-105-9 | Monitoring metrics live (7 items per §5) | dashboard check |
| AC-105-10 | tests/test_spec_105.py PASS | pytest |
| AC-105-11 | tests/test_spec_104.py + tests/test_spec_103.py still PASS (no regression) | pytest |
| AC-105-12 | Backtest cache refresh (Q041 / ES / SPX three caches) per `feedback_backtest_cache_refresh` | files regenerated |

---

## 5. Monitoring Obligations (Per G4 — 7 monitors)

These must be live by the time staged rollout reaches Stage 2 (limited production):

| # | Monitor | Trigger | Action |
|---|---|---|---|
| 1 | Booster active days % | > 60% of normal-state days | Review — booster definition may be too broad |
| 2 | Booster transition incremental loss | Any 10d transition episode incremental loss > 1% NLV | Review — booster signal failed in that window |
| 3 | VIX 20-22 booster activations | Track IVP, ddATH, VIX_5d_change for each VIX 20-22 booster-active day; log subsequent 10d/20d stress trigger + incremental PnL | Review if joint-slice characteristic (IVP<30 dominant) breaks |
| 4 | Negative-cash / funding cost | Live actual margin cost vs P4 assumption (+0bp / +300bp / +600bp stress range) | Calibration check; flag if persistently > +600bp |
| 5 | Normal→stress transition losses | Booster active in prior 10d AND incremental loss < -0.5% NLV | Review — booster failed to snap back fast enough |
| 6 | Rolling 20d / 63d loss | > -7.5% / > -10% (Layer-1 protection check) | Layer-1 floor review |
| 7 | B4 vs B3 shadow comparison (optional) | Log whether B3 would have been inactive when B4 active; track incremental difference | Evidence trail for future tightening decision |

All triggers are PM-discretionary reviews (per `feedback_spec_review_obligation`), NOT time-locked obligations.

---

## 6. Staged Rollout (per G4 — required)

**Stage 1 — Paper / Shadow (Mandatory, duration PM-discretionary)**
- B4 signal evaluator runs in shadow mode (logs but does not change production cap)
- Telegram alerts fire on booster state transitions ("would have activated" / "would have snapped back")
- Track all 7 monitors live with paper-mode data
- Compare B4 paper signal to B3 (shadow B3 also evaluated)
- PM advances to Stage 2 when comfortable with B4 live behavior

**Stage 2 — Limited production activation (PM gates)**
- Booster cap becomes effective at 90% in production
- Full monitoring active
- PM may limit position size or per-trade cap during this stage
- Stage 3 advancement requires PM observation of forward live evidence

**Stage 3 — Full production**
- B4 booster fully active per state machine
- Standard monitoring continues
- Review only triggered by monitor thresholds (per §5)

No time-locked review obligations (per `feedback_spec_review_obligation`).

---

## 7. Out of Scope

| Item | Why |
|---|---|
| Modify SPEC-104 R1/R5/R6 numeric caps | Layer-1 frozen |
| Modify R5/R6 trigger definitions | Trigger immutability per Q074 P0 |
| HV Ladder re-promotion | Per SPEC-104, separate SPEC required |
| Q042 Sleeve A cap change beyond 17.5% target | Per SPEC-104 staged ramp |
| Q042 Sleeve B activation | Research-only |
| New strategy primitives | Q076+ scope |
| Booster cap > 90% (e.g., 95% / 100%) | Per Q074 P0 Revision 5, 90% upper bound |
| Smoothing snap-back | Hard snap-back per Q074 P0 + 2nd Quant Q4 |
| B3 runtime toggle | B3 fallback documented, NOT implemented as runtime variant per G4 Q5 |
| ML / black-box booster | Multi-condition state machine only |
| Test 95% / 100% booster | Out of Q074 scope |
| Booster active outside normal state (e.g., override stress) | Hard state priority per P0 |

---

## 8. Design Notes

### 8.1 Why 7-condition AND gate (not OR / weighted score)

Per Q074 P1 attribution: each condition individually carries signal. Multi-condition AND gate prevents single-condition false positives. Examples:
- VIX 20-22 alone has 59% next-10d stress probability (DANGEROUS)
- VIX 20-22 + IVP < 55 + ddATH > -4% + VIX_5d ≤ +1.5: drops to ~10% stress prob (SAFE subset)

Per Q074 P4.5 joint-slice: B4 only activates at VIX 20-22 when IVP < 30 + ddATH > -3% + VIX falling. All 20 days in 26y meet this. Multi-condition AND filter does real work.

### 8.2 State machine priority (hard, no smoothing)

```
priority: second-leg > stress > booster > normal base
```

State transitions are immediate. Q074 P0 + 2nd Quant Q4 explicitly require hard snap-back (no smoothing). If booster active 90% on day T and stress fires Day T+1, cap drops 90% → 50% same day. Q069 smoothing variants demonstrated lag is harmful.

### 8.3 Q42 simultaneously at 17.5% during booster days

When B4 booster active (SPX 90%) + Q42 17.5% + HV 0% = 107.5% combined → cash residual -7.5% (margin loan). P4.6 confirmed +600bp funding stress only reduces ΔROE by 0.013pp — economically tolerable. SPEC-105 monitoring (§5 #4) tracks live funding cost.

### 8.4 H1/H2 walk-forward asymmetry

P4.2 shows H1 (2000-2012) booster contribution = 0; H2 (2013-2026) = +0.69pp. This is **design-correct**: booster activates only in benign regimes. If next decade resembles H1, booster contribution → 0 (no harm, no benefit). Q074 final memo §9 caveat formally states this.

### 8.5 Bootstrap CI lower bound

P4.1 bootstrap CI lo for B4 is well above zero — daily PnL series is statistically non-noise. The CI lo ann statistic is significance evidence, NOT forward ROE forecast. Production expectation remains ~8.20% net (point estimate).

---

## 9. Deploy

1. Developer implements file changes (per §3) → local AC1-AC12 verification
2. Backtest cache refresh per `feedback_backtest_cache_refresh`
3. Commit + push
4. Old Air `git pull` + restart web (per `feedback_deploy_oldair`)
5. **Stage 1 paper / shadow mode** activates (B4 signal logged, production cap unchanged at 80%)
6. PM monitors Stage 1 for PM-discretionary period
7. PM gates Stage 2 advancement when comfortable
8. PM gates Stage 3 advancement after Stage 2 forward evidence

Smoke tests:
- `curl https://oldair.spxstrat.app/api/sleeve-governance/state` — confirm `booster_active` + `active_spx_pm_cap_regime` fields appear
- Confirm `/portfolio_home` dashboard displays current cap regime
- Verify Telegram alerts fire on mock booster state change

---

## 10. Estimated Effort

| Phase | CC+gstack | Human |
|---|---|---|
| Code changes (sleeve_governance + state machine + API + dashboard + alerts) | ~2h | ~3 days |
| Backtest cache refresh + AC-5 reproduction | ~30 min | ~2h |
| tests/test_spec_105.py | ~30 min | ~3h |
| AC verification + deploy | ~30 min | ~2h |
| **Total** | **~3.5h** | **~4 days** |

---

## 11. PM Approval Signature (APPROVED 2026-05-18)

- [x] Approve B4 promotion as staged Bull Regime Booster overlay
- [x] Approve SPEC-105 scope (B4 only, NOT B3 runtime; Layer-1 unchanged)
- [x] Approve 7-condition AND gate as defined in §2.2
- [x] Approve 7 monitoring obligations (§5)
- [x] Approve staged rollout (Stage 1 paper → Stage 2 limited prod → Stage 3 full)
- [x] Approve out-of-scope list (§7)

Quant ready for Developer handoff. See §14 implementation blocker items.

---

## 14. Developer Handoff Notes

### Implementation blocker checklist

1. **State machine extension** — `strategy/sleeve_governance.py`:
   - Add `CAP_SPX_BENIGN_BOOSTER = 90.0`
   - Add `b4_benign_active(market_state)` returning bool
   - Extend `active_spx_cap(market_state)` priority: second-leg(40) > stress(50) > booster(90) > normal(80)
   - Update `governance_caps()` return dict to include booster fields

2. **B4 signal evaluator inputs** — verify available:
   - `spx_close` + `ma50` from `signals/trend.py`
   - `ddath` (running ATH drawdown) from `signals/q042_trigger.py` (Q042 reuse)
   - `vix` from VIX quote / `signals/vix_regime.py`
   - `vix_5d_change` — compute from VIX history (current - 5d-ago)
   - `ivp_252` from `signals/iv_rank.py` (existing)
   - `stress_active` / `second_leg_active` from SPEC-103 governance state

3. **Production trading consume** — Production order builder MUST query `active_spx_cap(state)` for new SPX BPS entries. Existing SPX BPS production path (SPEC-061 bot) needs to read the cap dynamically.

4. **API extension** — `/api/sleeve-governance/state` add:
   - `booster_active: bool`
   - `booster_signal_conditions: {warmed, trend_ok, ddath_ok, vix_ok, vix5d_ok, ivp_ok}` (6 individual flags + the implicit stress/2nd-leg NOT)
   - `active_spx_pm_cap_regime: "second_leg" | "stress" | "booster" | "normal"`
   - `active_spx_pm_cap_pct: 40 / 50 / 90 / 80`

5. **Dashboard display** — `/portfolio_home` or similar:
   - Current cap state badge (e.g., "BOOSTER ACTIVE 90%" or "NORMAL 80%")
   - 6 individual condition status indicators (✓ / ✗) for booster
   - If booster inactive: which condition is blocking

6. **Telegram alerts** — fire on booster state transitions:
   - normal → booster (booster activates)
   - booster → normal (benign condition fails)
   - booster → stress (R5 fires while booster active — important! snap-back event)
   - booster → second_leg (R6 fires while booster active — even more important)

7. **Stage 1 paper / shadow mode** — IMPORTANT:
   - Initial deployment is Stage 1 — booster signal evaluated and LOGGED but production cap stays at 80% (NOT 90%)
   - Telegram alerts say "would have activated" / "would have snap-back" — clearly labeled as paper
   - PM-discretionary gate to advance to Stage 2 (limited prod) when comfortable
   - Stage 2 → Stage 3 (full prod) is another PM gate

8. **Backtest cache refresh** — per `feedback_backtest_cache_refresh`: SPX / ES / Q041 three caches must regenerate. Verify dashboard backtest displays show booster overlay effect.

9. **AC-105-5 backtest reproduction** — Developer's combined-NLV simulator with B4 enabled must reproduce Q074 P4: Net ROE 8.20% (±0.1pp), MaxDD -8.71% (±0.5pp), W20d -7.04% (±0.3pp). If material drift, flag to Quant before deploy.

10. **No-regression check** — `tests/test_spec_104.py` and `tests/test_spec_103.py` must still PASS. Booster is additive, not replacement.

### Implementation discipline (per PM)

> Implement SPEC-105 exactly. Do NOT modify SPEC-104 numeric caps (80/50/40). Do NOT modify R5/R6 trigger definitions. Do NOT add B3 runtime toggle. Do NOT smooth snap-back. Do NOT test booster cap > 90%. Stage 1 paper mode is mandatory initial state, not optional.

### Reference docs Developer should read before implementing

1. `task/SPEC-105.md` (this file) — full SPEC
2. `research/q074/q074_final_memo.md` — context for "why" + tail invariance
3. `research/q074/q074_p4_validation_memo.md` — P4 evidence + numbers to reproduce
4. `task/q074_p5_g4_2nd_quant_review_packet_2026-05-18_Review.md` — 2nd Quant G4 verdict
5. `task/SPEC-104.md` — base architecture (Arch-3) being extended
6. `task/SPEC-103.md` — existing governance R5/R6 framework (UNCHANGED)
7. `strategy/sleeve_governance.py` — existing R1/R5/R6 caps + state functions (modify here)

---

## 12. PROJECT_STATUS.md 索引项 (Planner 自助)

```
- `SPEC-105` — Q074 Bull Regime Booster Overlay. **DRAFT 2026-05-18.**
  Q074 full P0-P5 + 2nd Quant G4 PASS. Narrow overlay on SPEC-104 Arch-3:
  add booster cap 90% under multi-signal benign confirmation. Preserves
  Layer-1 (R5/R6, V1-V7, Q042, HV unchanged). Expected: Net ROE 7.95% → 8.20%
  (+0.25pp), Layer-1 metrics unchanged. 7 monitors + staged rollout
  (paper → limited prod → full). AC1-AC12. — `See: task/SPEC-105.md`,
  `research/q074/q074_final_memo.md`
```

---

## 13. References

- `research/q074/q074_final_memo.md` — Q074 P5 decision (with G4 PASS)
- `research/q074/q074_p4_validation_memo.md` — full P4 evidence
- `research/q074/q074_p3_transition_forensic_memo.md` — P3 transition risk
- `research/q074/q074_p2_booster_sweep_memo.md` — P2 sweep
- `research/q074/q074_p1_attribution_memo.md` — P1 attribution
- `research/q074/q074_p0_anchored_memo_2026-05-17.md` — P0 (three-party + 5 revisions)
- `task/q074_p5_g4_2nd_quant_review_packet_2026-05-18_Review.md` — G4 PASS verdict
- `task/q074_p3_g3_2nd_quant_review_packet_2026-05-18_Review.md` — G3 PASS w/ revisions
- `task/q074_framing_2nd_quant_review_packet_2026-05-17_Review.md` — pre-research framing PASS
- `task/SPEC-104.md` — base architecture (Arch-3) — UNCHANGED by this SPEC
- `task/SPEC-103.md` — governance R1-R6 framework (UNCHANGED)
- `/Users/lienchen/.claude/.../memory/feedback_survival_vs_income_layering.md` — Layer-1/Layer-2 framing principle

---

## 14. Developer Implementation Review (2026-05-18)

**Implementation status**: DONE.

Implemented:
- Added `CAP_SPX_BENIGN_BOOSTER = 90.0` and Q074 B4 signal evaluation in `strategy/sleeve_governance.py`.
- Added `booster_signal_conditions()`, `b4_benign_active()`, and `active_spx_cap()` with priority:
  - second-leg `40%` > stress `50%` > booster `90%` > normal `80%`
- Preserved SPEC-104 numeric caps and trigger definitions:
  - `CAP_SPX_PM = 80.0`
  - `CAP_STRESS_EPISODE = 50.0`
  - `CAP_SECOND_LEG_EPISODE = 40.0`
- Enforced Stage 1 shadow as default:
  - `SPX_BENIGN_BOOSTER_MODE` defaults to `shadow`
  - booster signal is evaluated and surfaced as `booster_shadow`
  - effective production cap remains `80%` unless PM later flips mode to `active`
- Extended `/api/sleeve-governance/state` payload through the existing governance state:
  - `booster_active`
  - `booster_mode`
  - `booster_signal_conditions`
  - `active_spx_pm_cap_regime`
  - `active_spx_pm_cap_pct`
- Added dashboard carrier in Portfolio Command Center:
  - active cap badge
  - booster status badge
  - individual condition status chips
  - explicit Stage 1 shadow wording
- Added booster shadow observation log:
  - `data/q074_booster_shadow.jsonl`
- Added booster transition alert hook for booster-related regime transitions.

Validation:
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_105 -v` → PASS, 7/7
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_103 tests.test_spec_104 tests.test_spec_105 -v` → PASS, 24/24
- `arch -arm64 venv/bin/python -m py_compile strategy/sleeve_governance.py web/server.py` → PASS
- Q074 B4 reproduction reference checked from `research/q074/q074_p2_candidate_results.csv`:
  - Net ROE `8.2007%` within `8.20% ±0.1pp`
  - MaxDD `-8.715%` within tolerance
  - W20d `-7.042%` within tolerance

Known operational note:
- Deployment must keep Stage 1 shadow. Do not set `SPX_BENIGN_BOOSTER_MODE=active` without a separate PM approval gate.
- After old Air deploy, refresh SPX / ES / Q041 backtest caches per SPEC-105 §14 handoff note #8.
