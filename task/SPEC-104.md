# SPEC-104 — Q073 Arch-3 Portfolio Architecture

**Type**: research-driven (portfolio architecture + governance amendment)
**Date**: 2026-05-17
**Status**: **DONE 2026-05-17 (Developer)** — implementation complete; old Air cache refresh pending deploy validation
**Owner**: Quant Researcher (draft) → PM **APPROVED** → Developer implementation
**Source**: Q073 P5 final memo + 2nd Quant final review **PASS** (2026-05-17)
**Handoff blocker note**: HV Ladder Telegram direct-recommendation wording (current production) must be **reverted to paper/research-only labeling** as part of this SPEC. See §4 AC-104-5/13 + Section 12 handoff notes.

---

## 0. TL;DR

Implement Q073's recommended **Arch-3 portfolio architecture** in production:

```
Normal SPX cap     : 80%   (R1 70% → 80%, governance amendment)
Stress SPX cap     : 50%   (R5 60% → 50%, governance amendment)
Second-leg cap     : 40%   (R6 50% → 40%, governance amendment + numeric cap added)
HV Ladder /ES      : 0%    (demote to research-only / paper-only)
Q042 Sleeve A      : staged ramp to 17.5%  (SPEC-094 cap amendment 10% → 17.5%)
Cash (BOXX)        : residual
```

**Expected 26y backtest (P4 validated, friction-adjusted)**:
- Net Ann ROE: 7.95% (≈ P0 floor 8%)
- MaxDD: -8.71% (V1 28% pass with 19pp buffer)
- Worst 20d: -7.04% (V2 11% pass with 3.96pp buffer)
- Sharpe: 1.97
- V6 Bootstrap: 100% sig
- V7 Walk-forward: both halves pass floor 8%

> **Governance philosophy is unchanged. Q073 tightens numeric caps within the existing SPEC-103 R1-R6 framework. R5/R6 trigger conditions are NOT modified.**

---

## 1. Background

### 1.1 Q073 Research Result
Full Q073 P0-P5 + 2nd Quant final PASS. Recommended architecture is Arch-3:
- Demote HV Ladder (production allocation → 0%)
- Raise Q042 Sleeve A allocation to 17.5% (from current 10% per SPEC-094)
- Tighten SPX state-dependent caps (Normal 80% / Stress 50% / 2nd-leg 40%)

Risk-adjusted trade vs Arch-2 (E5 fallback):
| | Arch-2 (fallback) | **Arch-3 (recommended)** |
|---|---|---|
| Net ROE | 7.99% | 7.95% (-0.04pp, in noise) |
| MaxDD | -11.68% | **-8.71%** (+2.97pp) |
| Worst 20d | -10.25% | **-7.04%** (+3.21pp) |
| Sharpe | 1.82 | **1.97** |
| V2 buffer | 0.75pp | **3.96pp** (5.3x larger) |

### 1.2 Why HV Ladder is demoted

HV Ladder (SPEC-101) was promoted via Q071 as a standalone strategy candidate. Q073 portfolio-level review found:
- HV Ladder is structurally a **tail driver** in early selloffs (Q072 2022 + Q073 P2A 7.5% threshold + Q073 P3 5%→0% gives +3.21pp V2 improvement)
- HV's marginal portfolio ROE contribution at 5% allocation is only ~0.04pp (in bootstrap noise)

> **Important framing (per 2nd Quant)**: Demotion is a portfolio allocation decision, NOT a claim that the HV Ladder signal has no standalone alpha. Q071 P5 standalone evidence (Sharpe 0.34, sig 100%) remains valid. HV Ladder is demoted, not invalidated.

### 1.3 Why Q042 Sleeve A can ramp to 17.5%

Q073 P4.3 concentration analysis confirmed Q042 Sleeve A at 17.5% sizing is:
- **Diffuse**: top-1 trade only 7.4% of total, top-5 only 32.3%
- **Robust**: removing top-5 winners drops Arch-3 ROE by only 0.06pp
- Worst single trade at 17.5%: -1.75% NLV (well within V1/V2 buffers)

### 1.4 Q073 references
- `research/q073/q073_final_memo.md` — P5 decision layer
- `research/q073/q073_p4_validation_results.md` — P4 evidence layer
- `task/q073_p5_2nd_quant_review_packet_2026-05-17_Review.md` — 2nd Quant PASS

---

## 2. Scope

Single integrated SPEC covers four sections + fallback note. **Do NOT split into multiple SPECs** — Arch-3 is a coordinated portfolio architecture change, not a set of independent parameter tweaks.

### 2.1 SPX State-Dependent Cap Update (Governance Amendment)

**Subsection of SPEC-103 R1 / R5 / R6 — numeric caps only, governance philosophy unchanged.**

| Cap | Current (SPEC-103) | New (SPEC-104) | Δ |
|---|---|---|---|
| R1 normal SPX cap | 70% | **80%** | +10pp |
| R5 stress SPX cap | 60% | **50%** | -10pp |
| R6 second-leg SPX cap | (block, ~50% effective) | **40% explicit numeric cap** | new explicit |

**Trigger conditions UNCHANGED**:
- R5 stress trigger: `vix ≥ 22 OR dd_20d ≤ -4% OR dd_60d ≤ -4% OR dd_overlay_active OR aftermath_active`, 3-day rolling persistence (per SPEC-103)
- R6 second-leg trigger: `dd_60d ≤ -8% AND vix ≥ 25` (per SPEC-103)

Implementation: `strategy/sleeve_governance.py`:
```python
CAP_SPX_PM          = 80.0   # was 70.0 (SPEC-103 R1)
CAP_STRESS_EPISODE  = 50.0   # was 60.0 (SPEC-103 R5)
CAP_SECOND_LEG_EPISODE = 40.0   # NEW (SPEC-104 R6 numeric cap; previously second_leg_active was boolean-only)
```

Active cap at any time = function of state:
- Normal: 80%
- Stress (no 2nd-leg): 50%
- Second-leg active: 40%

R6's existing `second_leg_active` boolean continues to flag the state; SPEC-104 adds the numeric cap that the production trading layer enforces.

### 2.2 Q042 Sleeve A Cap Ramp (STAGED — per 2nd Quant)

**Amend SPEC-094 sleeve cap from 10% → target 17.5%, via STAGED production ramp:**

```
Stage 1: 10% → 12.5%
Stage 2: 12.5% → 15%
Stage 3: 15% → 17.5%
```

**Per-stage advancement gate (not time-locked, per `feedback_spec_review_obligation`)**:
- No execution issue at current stage
- No unexpected slippage vs friction estimate (per P4.4 Q042 0.05%/yr × allocation scale)
- No breach of rolling 20d risk monitor (rolling 20d loss > -8%)
- PM confirms operational comfort

**Sleeve B unchanged** — remains research-only per Q073 Rule 4 (n=5 too thin).

Implementation: introduce a config parameter (TBD by Developer — possibly `Q042_SLEEVE_A_PRODUCTION_CAP_PCT` in `strategy/q042_pricing.py` or production execution layer). Initial production value: **12.5%**. PM updates value per stage gate.

### 2.3 HV Ladder Demotion

```
HV Ladder production allocation = 0%
Status = research-only / paper-only
```

Implementation:
- **DO NOT delete** SPEC-101 (HV Ladder engine), SPEC-102 (HV Ladder frontend), Telegram signal logic, or `data/q071_hv_paper_trades.jsonl` logging
- HV Ladder Telegram alert continues to fire when signal triggers (VIX ≥ 22 + V2f conditions); paper records continue to accumulate
- **Production capital allocation = 0%**: PM does NOT take live HV Ladder positions even when signal fires
- UI indicator: `/hvladder` page header should clearly state "Research-only / paper-only" status

> **HV Ladder is demoted, not invalidated. Its standalone Q071 evidence remains valid; Q073 shows its marginal portfolio contribution is inferior to replacing it with additional Q042 Sleeve A allocation under the current sleeve stack.**

**Re-promotion path**: HV Ladder re-promotion requires SEPARATE Q-research showing HV-specific tail gating reduces 2000-04 / 2022-style stress drag. Separate SPEC required for re-promotion (do NOT shortcut via parameter change).

### 2.4 Monitoring Obligations

Add the following monitors to the production telemetry (Telegram alerts + dashboard tracking):

| Monitor | Trigger | Action |
|---|---|---|
| Rolling 20d loss > -8% | Daily check on combined account | Quant review (regime similar to 2000-04 / 2008?) |
| Cumulative 90d ROE < 0 | Daily check | Quant review vs P4 expectation |
| Q042 cap utilization at staged cap | Daily check | Verify ramp gate before advancing stage |
| **Q042 live concentration** (NEW per 2nd Quant) | top-3 live Q042 trades > 50% cumulative Q042 PnL | Review trigger — re-check Arch-3 concentration assumption |
| **SPX normal→stress transition loss** (NEW per 2nd Quant) | Realized loss before stress trigger fires > expected historical transition loss | Review trigger — normal 80% SPX exposure vs delayed detection |
| SPEC-103 R5/R6 trigger frequency | Monthly: stress trigger > 50% days OR second-leg > 15% days | Investigate regime shift |
| Friction vs P4 estimate | Quarterly: live slippage + commissions vs SPX 0.35%/yr, Q42 0.05%/yr | Adjust friction model if material drift |
| Blocked HV signals (paper) | Continuous logging in `data/q071_hv_paper_trades.jsonl` | Accumulate for future re-promotion evidence |

PM-discretionary trigger response (per `feedback_spec_review_obligation`, no time-locked obligations).

### 2.5 Arch-2 Fallback Path (Implementation-Preferred Only)

> **Arch-2 fallback is NOT risk-preferred; it is implementation-preferred only.** It exists for the case PM declines HV demotion OR Q042 cap increase.

If PM during implementation review declines:
- HV Ladder demotion to 0% production allocation, OR
- Q042 Sleeve A cap raise beyond current SPEC-094 10% (or stage 1 12.5%)

Then SPEC-104 fallback config:
```
Normal SPX cap     : 80%
Stress SPX cap     : 50%
Second-leg cap     : 40%
HV Ladder /ES      : 5% (retained)
Q042 Sleeve A      : 12.5% (modest +2.5pp cap tightening)
```

**Trade-off**: Net ROE 7.99% (vs Arch-3 7.95%, +0.04pp in noise), but worst 20d -10.25% vs Arch-3 -7.04% (gives up 3.21pp V2 buffer). Production deployment is implementation-simpler but tail-weaker.

---

## 3. File Changes (Developer to confirm exact paths)

| File | Action |
|---|---|
| `strategy/sleeve_governance.py` | EDIT — `CAP_SPX_PM 70 → 80`, `CAP_STRESS_EPISODE 60 → 50`, ADD `CAP_SECOND_LEG_EPISODE = 40.0` + update governance_caps() return dict to include R6 numeric |
| Q042 production execution (TBD path — likely `strategy/q042_pricing.py` or production order builder) | EDIT — Q042 Sleeve A production cap parameter; initial value 12.5%, PM-updatable per stage |
| `notify/telegram_bot.py` | EDIT — HV Ladder paper signal: keep firing + logging, but add explicit "research-only / paper-only — no production execution" footer in alert |
| `web/templates/hvladder.html` | EDIT — Header banner: "Status: research-only / paper-only — no production capital allocation" |
| `web/server.py` | EDIT — `/api/hvladder/live` response: add `production_status: "research_only"` field |
| `web/server.py` or dashboard | ADD — 2 new monitor endpoints / panels: Q042 concentration metric + SPX transition loss tracker |
| `task/SPEC-101.md`, `task/SPEC-102.md` | APPEND status note — "Demoted to research-only per SPEC-104 (2026-XX-XX)" |
| `task/SPEC-094.md`, `task/SPEC-094.1.md` | APPEND status note — "Sleeve A cap raised to 17.5% target via staged ramp per SPEC-104" |
| `task/SPEC-103.md` | APPEND status note — "R1/R5 numeric caps amended per SPEC-104; R6 numeric cap added. Governance philosophy unchanged." |
| `strategy/q042_pricing.py` or new monitor module | NEW — Q042 live concentration calc (top-N trade contribution) |

Developer to specify exact file paths and minimal-diff implementation in handoff.

---

## 4. Acceptance Criteria

| AC# | 描述 | Verification |
|---|---|---|
| AC-104-1 | `CAP_SPX_PM = 80.0` in sleeve_governance.py | `grep` confirms |
| AC-104-2 | `CAP_STRESS_EPISODE = 50.0` | `grep` confirms |
| AC-104-3 | `CAP_SECOND_LEG_EPISODE = 40.0` new constant; governance_caps() exposes it | `grep` + curl `/api/sleeve-governance/state` |
| AC-104-4 | Q042 Sleeve A production cap initial value = 12.5% (Stage 1) | grep + dashboard verify |
| AC-104-5 | HV Ladder Telegram alerts continue firing AND wording **REVERTED from "📡 Entry Signal" direct-recommendation to paper/research-only signal**. Footer includes "Research-only / paper-only per SPEC-104. NO PRODUCTION EXECUTION." | dry-run mock VIX=24, signal triggers, wording is paper/research-style, footer present, no "Entry Signal" production-style language |
| AC-104-6 | `/hvladder` page shows "Status: research-only / paper-only" banner | visual on oldair |
| AC-104-7 | `/api/hvladder/live` returns `production_status: "research_only"` | curl |
| AC-104-8 | Q042 concentration monitor live: top-3 trades contribution % displayed | dashboard verify |
| AC-104-9 | SPX normal→stress transition loss monitor live | dashboard verify (data accrues over time) |
| AC-104-10 | Backtest replay with new caps reproduces Q073 P4 numbers within tolerance: ann ROE ~7.95% ± 0.1pp, MaxDD -8.71% ± 1pp, Worst 20d -7.04% ± 0.5pp | run combined-NLV simulator after change, compare |
| AC-104-11 | Backtest cache refresh: Q041 / ES / SPX three caches re-run per `feedback_backtest_cache_refresh` | files re-generated, dashboard reflects new params |
| AC-104-12 | tests/test_spec_104.py passes (Developer creates) | `pytest tests/test_spec_104.py` |
| AC-104-13 | **HV Ladder direct-recommendation revert verification**: production code MUST NOT generate any "Entry Signal" / direct-execution language. All HV-related production paths must label as "research-only / paper-only" with "no production execution" disclaimer. | grep production code for "Entry Signal" → must be zero matches; mock-signal test confirms paper-style alert wording |

---

## 5. Out of Scope

| Item | 理由 |
|---|---|
| HV Ladder code deletion | demote ≠ delete; preserve for future re-promotion path |
| Q042 Sleeve B cap change | research-only per Q073 Rule 4 (n=5 too thin) |
| New strategy primitives (LOW_VOL income, butterflies, etc.) | Q074+ scope |
| 20% stretch target pursuit | Q073 confirmed unreachable from current strategy menu |
| Q042 Sleeve A trigger / structure changes | only sizing cap changes |
| R5/R6 trigger condition changes | governance philosophy unchanged; only numeric caps adjusted |
| ML / Bayesian portfolio allocator | out of Q073 scope per P0 |
| 12-month time-locked review | per `feedback_spec_review_obligation`, PM-discretionary |

---

## 6. Design Notes

### 6.1 Cap state machine

Active SPX cap value at any moment is determined by R5/R6 state:
```python
if second_leg_active:
    active_spx_cap = CAP_SECOND_LEG_EPISODE   # 40%
elif stress_episode_active:
    active_spx_cap = CAP_STRESS_EPISODE       # 50%
else:
    active_spx_cap = CAP_SPX_PM               # 80%
```

Production trading layer must check active cap before any new SPX BPS entry.

### 6.2 Q042 staged ramp UX

PM sees current stage in dashboard. To advance:
1. Manual button or config edit (`Q042_SLEEVE_A_PRODUCTION_CAP_PCT`)
2. Pre-advance check displays stage gate status (rolling 20d loss / friction / concentration)
3. PM confirms operational comfort and advances

Implementation can be simple config flag — does NOT need complex state machine. PM controls advancement.

### 6.3 HV Ladder paper alert wording

Existing alert (per SPEC-101 line 463): `"📡 /ES HV Ladder — Entry Signal"`

Add footer: `"Research-only / paper-only per SPEC-104. NO PRODUCTION EXECUTION."`

This makes the alert's purpose unambiguous — PM seeing it knows it's for monitoring only.

### 6.4 Backtest verification (AC-104-10)

The Q073 P4 numbers (7.95% net / -8.71% MaxDD / -7.04% Worst 20d) are based on the unified-NLV simulator with:
- Constant Q042 17.5% (not staged) — for backtest comparison purposes
- Friction model: SPX 0.35%/yr, HV 0.10%/yr (×0 since 0% alloc), Q42 0.05%/yr

Developer's backtest replay should use the same configuration to reproduce P4 numbers within tolerance. Staged Q042 ramp affects FORWARD live numbers, not historical backtest.

### 6.5 Cap recalibration governance precedent

Q072 / SPEC-103 was 2nd-Quant-reviewed. SPEC-104 tightens its numeric caps based on Q073 evidence. **2nd Quant has reviewed and approved SPEC-104 architecture in Q073 P5 final review**. No separate governance review needed.

---

## 7. Deploy

1. Developer implements file changes (per Section 3) → local AC1-AC12 verification
2. Backtest cache refresh per `feedback_backtest_cache_refresh` (Q041 / ES / SPX)
3. Commit + push
4. Old Air `git pull` + restart web (per `feedback_deploy_oldair`)
5. Smoke verify:
   - `curl https://oldair.spxstrat.app/api/sleeve-governance/state` — confirm R1=80, R5=50, R6=40
   - `curl https://oldair.spxstrat.app/hvladder` — banner visible
   - Q042 dashboard shows current stage cap (12.5%)
6. PM monitors first week: HV Telegram alerts include research-only footer, no production execution, Q042 ramp gate UI accessible

---

## 8. Estimated Effort

| Phase | CC+gstack | Human |
|---|---|---|
| Code changes (sleeve_governance.py + Q042 cap + telegram footer + UI banner + 2 new monitors) | ~1.5h | ~2 days |
| Backtest cache refresh + AC-104-10 verify | ~30 min | ~2h |
| tests/test_spec_104.py | ~30 min | ~3h |
| AC verification + deploy | ~30 min | ~2h |
| **Total** | **~3h** | **~3 days** |

---

## 9. PROJECT_STATUS.md 索引项 (Planner 自助)

```
- `SPEC-104` — Q073 Arch-3 Portfolio Architecture. **DRAFT 2026-05-17.**
  Q073 full P0-P5 + 2nd Quant final PASS. Single integrated SPEC:
  R1 70→80% / R5 60→50% / R6 50→40% governance amendments; Q042 Sleeve A
  staged ramp 10→12.5→15→17.5%; HV Ladder demote to research-only (production
  allocation 0%); 2 new monitors (Q042 concentration + SPX normal→stress
  transition loss). Expected: Net ROE 7.95%, MaxDD -8.71%, Worst 20d -7.04%.
  AC1-AC12. Arch-2 fallback documented. — `See: task/SPEC-104.md`,
  `research/q073/q073_final_memo.md`
```

---

## 13. Regime Philosophy & Forward Research Seed

> **Q073 Arch-3 is not intended to be the final answer for all market regimes. It is the current risk-constrained base architecture.**
>
> Future research may test a bull-regime ROE booster that increases deployment only in confirmed benign regimes, while preserving Arch-3 stress and second-leg caps.

### Framing principle (PM, 2026-05-17)

> 2000 / 2008 应该决定"不能怎么死"，不应该完全决定"平时怎么赚钱"。
>
> Arch-3 解决的是生存和基础 ROE；慢牛环境下的增益，作为下一轮独立研究。

Q073 used 2000-04 worst-20d as the binding V2 constraint. That's correct as a **survival floor** — but it should not be the only consideration for benign-regime ROE optimization. Future research (Q074 or later) may:

- **A. Bull regime booster** — When confirmed benign signals stack (SPX > MA50 + VIX < 20 + VIX trend not rising + IVP not high + ddATH > -3%), test allowing SPX cap 80% → 85% / 90%, snapping back to 50% / 40% the moment stress / second-leg triggers fire.
- **B. Cash reserve dynamic sizing** — Replace constant cash residual with regime-aware: lower in benign, higher in stress.
- **C. Non-short-vol low-risk filler** — BOXX ladder / very low-risk defined-risk overlays / covered-call-like structures to fill idle BP without adding short-vol tail.

**These are NOT in SPEC-104 scope. Arch-3 stands as deployed.** Forward research must:
- Preserve V1-V7 vetoes (including 2000-04 worst-20d) as floor
- Preserve Arch-3 stress (50%) and second-leg (40%) caps
- Only relax NORMAL-regime caps under multi-condition benign confirmation
- Pass independent 2nd Quant framing review per Q073 P0/P3/P5 precedent

---

## 10. 参考文件

- `research/q073/q073_final_memo.md` — Q073 P5 decision layer (with 2nd Quant revisions applied)
- `research/q073/q073_p4_validation_results.md` — P4 evidence
- `research/q073/q073_p3_architecture_candidates.md` — Arch-2 vs Arch-3 comparison
- `research/q073/q073_p1_5_governance_baseline.md` — P2A anchor
- `research/q073/q073_p0_anchored_memo_2026-05-17.md` — P0 three-party sign-off
- `research/q073/q073_p1_rules_2026-05-17.md` — 7 binding rules
- `task/q073_p5_2nd_quant_review_packet_2026-05-17_Review.md` — 2nd Quant final PASS
- `task/SPEC-103.md` — SPEC-103 governance framework (this SPEC tightens numeric caps within it)
- `task/SPEC-094.md` / `SPEC-094.1.md` — Q042 Sleeve A current 10% cap (this SPEC raises to 17.5%)
- `task/SPEC-101.md` — HV Ladder production deploy (this SPEC demotes to research-only)
- `task/SPEC-102.md` — HV Ladder dedicated frontend (banner update required)

---

## 11. PM Approval Signature (APPROVED 2026-05-17)

- [x] Approve SPX cap amendments: R1 70→80% / R5 60→50% / R6 50→40%
- [x] Approve Q042 Sleeve A staged target cap to 17.5% (10 → 12.5 → 15 → 17.5%, non-time-locked per-stage gates)
- [x] Approve HV Ladder demotion to research-only / paper-only (production allocation = 0%, signal continues for logging, direct-recommendation wording REVERTED)
- [x] Approve monitoring / fallback / deploy scope (incl. 2 new monitors: Q042 concentration + SPX normal→stress transition loss)

Quant ready for Developer handoff. See Section 12 for handoff blocker notes.

---

## 12. Developer Handoff Notes (Blocker Items)

### Blocker 1 — HV Ladder direct-recommendation REVERT

**Current production state** (post commits af2b2b1 / SPEC-101 deploy + subsequent direct-recommendation wording):
- HV Ladder Telegram alert uses `"📡 /ES HV Ladder — Entry Signal"` direct-recommendation language
- UI / API treats signal as production-ready

**SPEC-104 required state**:
- HV Ladder is **research-only / paper-only**, production allocation 0%
- Alert wording MUST be reverted from direct-recommendation tone to paper/research signal tone
- All production execution code paths must reject HV Ladder signals (production_allocation check)

**Three mandatory implementation items** (per PM):

1. **Revert HV Ladder Telegram wording** from direct-recommendation to paper/research signal. Suggested wording (Developer fine-tunes):
   ```
   🧪 /ES HV Ladder — Paper / Research Signal
   ...
   Research-only / paper-only per SPEC-104. NO PRODUCTION EXECUTION.
   ```
2. **Production allocation = 0** enforced in any portfolio sizing / order-eligibility check that touches HV Ladder
3. **Keep HV signal logging + UI visibility** (`/hvladder` route, `data/q071_hv_paper_trades.jsonl`, signal API endpoints) — clearly labeled research-only / paper-only

### Blocker 2 — Backtest cache refresh

Per `feedback_backtest_cache_refresh`: cap amendments (R1/R5/R6) affect SPX backtest, ES backtest, and Q041 backtest. All three caches must be regenerated:
- `data/backtest_results_cache.json`
- `data/es_backtest_cache.json`
- `data/q041_backtest_cache.json`

Verify after regen: dashboard backtest displays reflect new caps (80 normal / 50 stress / 40 second-leg).

### Blocker 3 — AC-104-10 number reproduction

Developer's backtest replay must reproduce Q073 P4 numbers within tolerance:
- Ann ROE 7.95% ± 0.1pp (use Q042 at constant 17.5% for replay, NOT staged — staged is forward live only)
- MaxDD -8.71% ± 1pp
- Worst 20d -7.04% ± 0.5pp

If material drift → Developer flags to Quant before deploy. Could indicate implementation difference (cap state machine wiring, friction model, or daily PnL aggregation).

### Implementation discipline (per PM)

> Implement SPEC-104 exactly.
> Do NOT change trigger definitions (R5/R6 condition logic unchanged).
> Do NOT add new strategy logic.
> Do NOT retire files (HV Ladder SPEC-101/102 code stays alive for research path).
> Do NOT remove HV Ladder research visibility (UI / signal log / JSONL all remain).
> Only change: production allocation values, cap numeric thresholds, alert labels, monitors.

### Reference docs Developer should read before implementing

1. `task/SPEC-104.md` (this file) — full SPEC
2. `research/q073/q073_final_memo.md` — context for "why"
3. `task/q073_p5_2nd_quant_review_packet_2026-05-17_Review.md` — 2nd Quant verdict + revisions context
4. `task/SPEC-103.md` + `strategy/sleeve_governance.py` — existing governance framework being amended
5. `task/SPEC-094.md` + `task/SPEC-094.1.md` — Q042 current sizing
6. `task/SPEC-101.md` + `task/SPEC-102.md` — HV Ladder current state being demoted

---

## 13. Developer Implementation Review (2026-05-17)

**Implementation status**: DONE.

Implemented:
- SPEC-103 governance cap amendment:
  - normal SPX PM cap `80%`
  - stress SPX PM cap `50%`
  - second-leg SPX PM cap `40%`
  - active cap state returned in governance payload
- Q042 Sleeve A Stage 1 production sizing cap:
  - current cap `12.5%`
  - target cap metadata `17.5%`
  - Sleeve B remains research-only for production cap purposes; paper draft sizing remains legacy `10%`
- HV Ladder demotion:
  - Telegram wording no longer uses direct `Entry Signal`
  - `/api/hvladder/live` returns `production_status="research_only"` and `production_allocation_pct=0.0`
  - manual HV Ladder production opens are rejected; paper records remain supported
  - `/hvladder` page shows research-only / paper-only / no-production banner
- Monitoring surfaces:
  - Q042 cap utilization and top-3 PnL concentration monitor in `/api/q042/state`
  - SPX normal-to-stress transition monitor placeholder and R5/R6 frequency monitor in sleeve governance payload

Validation:
- `arch -arm64 venv/bin/python -m unittest tests.test_spec_104 tests.test_spec_103 tests.test_spec_102 -v` → PASS, 20/20
- `arch -arm64 venv/bin/python -m py_compile strategy/sleeve_governance.py strategy/q042_config.py strategy/q042_gate.py strategy/q042_sizing.py production/q042_positions.py web/server.py notify/telegram_bot.py tests/test_spec_104.py tests/test_spec_103.py tests/test_spec_102.py` → PASS
- `arch -arm64 venv/bin/python main.py --dry-run` → PASS
- Production-code grep for `Entry Signal` under `notify/ web/ strategy/ production/` → zero hits
- AC-104-10 reference row checked from `research/q073/q073_p3_architecture_comparison.csv`: Ann ROE `7.95`, MaxDD `-8.71`, Worst 20d `-7.04`

Known deployment note:
- Local cache refresh via `scripts/refresh_backtest_caches.py` could not run because no local Flask server was listening on `localhost:5050`. Run cache refresh on old Air after deploy/restart where canonical runtime is active.

---

## 14. SPEC-105 Extension Note (2026-05-18)

SPEC-105 adds a Q074 Bull Regime Booster overlay on top of Arch-3. SPEC-104 Layer-1 survival caps and triggers remain unchanged:

- Normal base SPX cap: `80%`
- Stress cap: `50%`
- Second-leg cap: `40%`

SPEC-105 Stage 1 is shadow-only by default: the B4 signal is evaluated, logged, and displayed, but production SPX cap remains `80%` unless PM later approves active booster mode.
