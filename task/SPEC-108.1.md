# SPEC-108.1 — Selector-Gated SPX Execution Ladder (R1-R7 Revision Package)

**Type**: revision SPEC layered on SPEC-108 (DONE 2026-05-28)
**Date**: 2026-05-29
**Status**: **APPROVED** — PM signed 2026-05-29, pending Developer implementation
**Owner**: Quant Researcher (draft) → PM approval → Developer implementation
**Parent**: [`task/SPEC-108.md`](task/SPEC-108.md) (selector-gated SPX execution ladder, Stage 1 shadow currently deployed)
**Source**:
- ChatGPT 2nd Quant external review (2026-05-29) — 8 challenges, 7 actionable
- Q080 methodology primitives calibration (2026-05-29) — Sharpe correction + p05 disclosure
- See: [`task/chatgpt_review_packet_2026-05-28_to_05-29.md`](task/chatgpt_review_packet_2026-05-28_to_05-29.md), [`task/chatgpt_review_response_2026-05-29.md`](task/chatgpt_review_response_2026-05-29.md), [`research/q080/q080_memo.md`](research/q080/q080_memo.md)

---

## 0. TL;DR

External 2nd Quant review + Q080 primitives calibration identified **7 hardening revisions** to SPEC-108. None invalidate the +1.80pp ROE thesis (Q080 P1/P2 confirm it). All R-items address risk-disclosure, monitoring gaps, and Stage-2 advancement quality. Stage 1 shadow continues unchanged; this SPEC unfreezes Stage 2 advancement *path* by adding the missing gates.

```
R1: Portfolio-stress overnight gap gate (Layer-1 cluster-risk control)
R2: V1b parallel shadow (cheap test of alternative cadence)
R3: Stage 2 advancement → regime-coverage gate (replace ≥10 absolute)
R4: Per-strategy drift monitor (catch selector-bias amplification)
R5: Bias wording "resolves" → "defers" (SPEC-108 §0 — DONE inline)
R6: Sharpe number +1.20 → +0.48 (SPEC-108 §0 — DONE inline)
R7: Block-bootstrap p05 disclosure on tail metrics (SPEC-108 §0 — DONE inline)
```

R5/R6/R7 are documentation-only and have already been applied directly to SPEC-108 §0. **This SPEC-108.1 implements R1-R4 (code/monitoring/SPEC changes).**

---

## 1. Background

### 1.1 Why this revision

SPEC-108 deployed 2026-05-28 (commit 50a72df). On 2026-05-29 we ran two parallel checks:

1. **External 2nd Quant review** (ChatGPT) of the entire Q078 → SPEC-108 + SPEC-109 + Q079 packet (`task/chatgpt_review_packet_2026-05-28_to_05-29.md`). 20 questions, 16 ACCEPT + 2 ACCEPT-mild + 2 no-action.
2. **Q080 methodology primitives calibration** — re-tested daily-MTM smoothing (P1), block bootstrap (P2), 0.5pp noise threshold σ-calibration (P3). Confirms ROE claim, exposes Sharpe inflation + tail p05 disclosure gap.

Combined, 7 R-items are actionable. R5/R6/R7 already applied to SPEC-108 §0. R1-R4 are the code/SPEC scope of this revision.

### 1.2 What does NOT change

- SPEC-108 §2.1 ladder constants (LADDER_SIZING_CONTRACTS=3, CLUSTER_DAYS=5, BP_CEILING=35%)
- SPEC-108 §2.2 `v3_ladder_eligible()` core logic
- SPEC-108 §2.3 strategy-agnostic ladder design
- SPEC-108 §2.4 SPEC-077 exit logic
- Stage 1 shadow-only default (`LADDER_MODE_DEFAULT="shadow"`)
- All 18 existing ACs (AC-108-1 to AC-108-18) — new ACs add on top
- All 8 existing monitoring obligations — new monitor #9 adds on top

---

## 2. Scope — R1 to R4

### R1 — Portfolio-stress overnight gap gate (ChatGPT Q1)

**Problem**: SPEC-108 §6 Stage 2 advancement gate #2 reads "No single shadow trade projected loss > 5% NLV." ChatGPT flagged that 5% NLV per trade is a single-event ceiling, but **the real tail risk is cluster correlated loss** — e.g., 8 BPS spreads all blown through on -7% SPX overnight gap. A per-trade gate doesn't catch this.

**Fix**: Add a portfolio-stress overnight-gap gate to the Stage 2 advancement criteria AND to standing monitoring.

**Definition**:

```
Portfolio overnight-gap stress test:
  Hypothetical scenario: SPX gaps -7% overnight (close-to-open)
  Compute MTM mark-loss of:
    - All open SPX positions (including ladder + Q042 + baseline SPX_PM sleeve)
    - At -7% gap, use BS reprice with IV +50% (typical gap response)
  Aggregate to portfolio level

Gate: aggregate portfolio mark-loss must NOT exceed 12% NLV.
```

**Why 12% NLV**: PM tolerance for single-day portfolio mark-loss; 2.4× the per-trade 5% gate to leave room for ~2 concurrent strategies in same direction; calibrated from PM PM-margin auto-liquidation risk at ~20% NLV mark-loss (Schwab PM margin call threshold).

**Implementation**:
- New function `portfolio_stress_overnight_gap()` in `strategy/sleeve_governance.py`
- Inputs: current open positions (read from `data/strategy_state.json` or similar), -7% SPX shock, IV +50% shock
- Output: aggregate mark-loss in % NLV
- Add to Stage 2 advancement gate criteria (SPEC-108 §6) as condition #8

### R2 — V1b parallel shadow (ChatGPT Q6)

**Problem**: SPEC-108 §8.7 documents V1b weekly catch-up as historical alternative; SPEC explicitly forbids Developer from implementing V1b. ChatGPT challenged: even though V3-vs-V1b portfolio diff is < 0.5pp (noise per recalibrated `feedback_noise_threshold.md`), V1b shows slightly better tail metrics. Live shadow data is cheap and informative.

**Fix**: Implement V1b cadence evaluator alongside V3; run both in parallel shadow; PM gets two side-by-side shadow streams to compare.

**Definition**:

```
V1b cadence rule:
  Weekly check (e.g., Wed 09:35 ET as the canonical weekly anchor day)
  If selector PASS on weekly anchor: enter
  If selector R/W on weekly anchor: skip until next week
  No catch-up on missed weeks; no cadence_gap within the week

S3 sizing (3 contracts) shared with V3.
Production gates (concurrency + 35% BP ceiling) shared with V3.

Default LADDER_V1B_MODE = "shadow" (mirror of V3 default).
Stage 1: both V3 and V1b shadow side-by-side.
Stage 2: PM picks one to activate (V3 OR V1b, NOT both at production).
```

**Implementation**:
- New file `strategy/q078_ladder_v1b.py` mirroring `strategy/q078_ladder.py` structure
- `v1b_ladder_eligible(market_state, ladder_state)` function
- `data/q078_ladder_v1b_shadow.jsonl` shadow log
- API extension: `/api/sleeve-governance/state` add `ladder_v1b_*` fields parallel to `ladder_*` (~11 new fields)
- Dashboard panel mirror beneath V3 panel
- Telegram alert mirror

### R3 — Stage 2 advancement gate: regime-coverage (ChatGPT Q7)

**Problem**: SPEC-108 §6 Stage 2 minimum-evidence gate is "≥ 10 shadow candidate entries OR PM waiver." ChatGPT challenged: 10 entries is ~3.5 months at 35/yr cadence, almost certainly all in same VIX regime. Strategy-agnostic ladder needs to be observed across regime branches (NORMAL/HIGH_VOL/IC_HV/BCD) before Stage 2.

**Fix**: Replace flat ≥10 with regime+strategy-coverage:

**Definition**:

```
Stage 2 advancement minimum evidence (revised):

ALL must hold:
  A. Total shadow entries ≥ 10 (preserved as floor)
  B. At least ONE of the following coverage profiles, OR explicit PM waiver:
     (i)   ≥3 entries each in ≥2 distinct VIX regimes (LOW_VOL, NORMAL, HIGH_VOL)
     OR
     (ii)  ≥3 entries each in ≥2 distinct strategy branches (BPS, IC, BCD, BPS_HV, IC_HV, BCS_HV)
     OR
     (iii) PM explicitly waives, citing operational reason
```

**Rationale**: PM's account at NLV $894k means even 35 entries/yr at S3 = ~$2.6M cumulative max-loss exposure/yr. Confirming the ladder behaves correctly across regime/strategy branches before activating production captures most of the systemic risk for a small upfront delay.

**Implementation**:
- Update `task/SPEC-108.md` §6 Stage 2 advancement gate text
- Update `tests/test_spec_108.py` or add `tests/test_spec_108_1.py` to verify gate logic if shadow-counter functions are written

### R4 — Per-strategy drift monitor (ChatGPT Q8)

**Problem**: Strategy-agnostic ladder consumes selector verdict and mechanically executes. If selector has a systematic bias (e.g., over-weights IC in some regime), ladder amplifies it ~35×/year. SPEC-108 §5 monitoring covers signal rate / skip reasons / W20d/W63d / Q042 overlap, but **no per-strategy distribution drift detection**.

**Fix**: Add monitor #9 to SPEC-108 §5 monitoring obligations: per-strategy ladder trigger distribution vs historical baseline.

**Definition**:

```
Monitor #9 — Per-strategy ladder trigger distribution drift

Reference (historical baseline, from 26y signal cache):
  BPS:         ~45-55% of selector PASS days
  IC:          ~15-25%
  BCD:         ~15-25%
  BPS_HV:      ~3-5%
  IC_HV:       ~3-5%
  BCS_HV:      ~1-2%

Trigger: any strategy's rolling 90-day share deviates from its historical band
         by > 15pp.

Action: PM-discretionary review. If drift is regime-explained (e.g., VIX
        regime shifted), no action. If unexplained, investigate selector
        before continuing shadow / production.
```

**Implementation**:
- New function `strategy_distribution_check()` in `strategy/sleeve_governance.py` or new file `strategy/q078_ladder_monitors.py`
- Reads shadow log (rolling 90 days) + computes strategy share %
- Compares to hardcoded historical bands (from `research/q078/_signal_history_cache.csv` analysis)
- Exposed via `/api/sleeve-governance/state` → new field `ladder_strategy_drift_alert` (bool) + `ladder_strategy_distribution_90d` (dict)
- Dashboard panel adds drift status chip
- Telegram alert daily summary includes drift status

---

## 3. File Changes

| File | Action |
|---|---|
| `task/SPEC-108.md` | EDIT — §0 already updated; §5 add monitor #9; §6 update Stage 2 gate; §11 add SPEC-108.1 acknowledgement checkbox |
| `task/SPEC-108.1.md` | **NEW** (this file) |
| `strategy/sleeve_governance.py` | EDIT — add `portfolio_stress_overnight_gap()` + invoke from Stage 2 gate logic |
| `strategy/q078_ladder.py` | EDIT — no logic change; just verify nothing breaks |
| `strategy/q078_ladder_v1b.py` | **NEW** — V1b cadence evaluator + state + shadow log |
| `strategy/q078_ladder_monitors.py` | **NEW** — per-strategy distribution drift check |
| `web/server.py` | EDIT — `/api/sleeve-governance/state` add ~13 new fields (11 V1b mirror + 2 drift) |
| `web/templates/portfolio_home.html` | EDIT — add V1b panel below V3 panel; add strategy-drift chip |
| `notify/telegram_bot.py` | EDIT — V1b shadow alert mirror + drift status in daily summary |
| `data/q078_ladder_v1b_shadow.jsonl` | NEW (runtime-created) |
| `data/q078_ladder_v1b_runtime.json` | NEW (runtime-created) |
| `tests/test_spec_108_1.py` | **NEW** — ACs for R1-R4 |

---

## 4. Acceptance Criteria

| AC# | Verification |
|---|---|
| **AC-108.1-1** | `portfolio_stress_overnight_gap(state)` returns aggregate mark-loss % NLV; pytest |
| **AC-108.1-2** | Stage 2 gate logic includes R1 gate (mark-loss > 12% NLV → block); pytest |
| **AC-108.1-3** | `strategy/q078_ladder_v1b.py` `v1b_ladder_eligible()` returns (eligible, reason) with weekly anchor logic; pytest unit |
| **AC-108.1-4** | `LADDER_V1B_MODE_DEFAULT = "shadow"`; pytest |
| **AC-108.1-5** | `/api/sleeve-governance/state` returns 11 new `ladder_v1b_*` fields + 2 new `ladder_strategy_drift_*` fields; curl test |
| **AC-108.1-6** | Stage 2 advancement gate text in SPEC-108 §6 updated to regime-coverage formulation; visual review |
| **AC-108.1-7** | `strategy_distribution_check()` reads shadow log + flags drift > 15pp; pytest with seeded log |
| **AC-108.1-8** | Dashboard `/portfolio_home` shows V1b panel mirror beneath V3 panel; visual |
| **AC-108.1-9** | Dashboard `/portfolio_home` shows strategy-drift chip on V3 panel; visual |
| **AC-108.1-10** | Telegram alert daily summary includes V1b shadow + drift status; dry-run |
| **AC-108.1-11** | `production_order_allowed()` still enforces shadow-default for BOTH V3 and V1b (no V1b production path until PM explicit env var `LADDER_V1B_MODE=active`); pytest CI test (mirror of AC-108-17/18) |
| **AC-108.1-12** | Existing SPEC-108 18 ACs all still PASS (no regression); pytest |
| **AC-108.1-13** | SPEC-103/104/105/106/107 tests still PASS (no regression); pytest |

---

## 5. Out of Scope

| Not done | Why |
|---|---|
| Change SPEC-108 ladder constants (S3=3, 5-day cluster, 35% BP ceiling) | SPEC-108 design locked |
| Change SPEC-077 exit | Layer-1 frozen |
| Change SPEC-104/105v2 baseline | Layer-1 frozen |
| Implement V1b in production (not just shadow) | R2 is *parallel shadow* only |
| Re-implement P4 with portfolio-stress gate | R1 is a Stage-2 gate, not a P4 metric |
| Change V3 vs V1b decision (V3 remains primary) | R2 adds V1b shadow for observation, not promotion |
| Add VIX=22 / IVP=40 / IVP=70 boundary research | Q079 dropped VIX=15; others are independent open questions |
| Modify SPEC-109 attribution chart | Independent track |
| Sharpe-aware Q078 P4 re-run | Q080 P1 already done; no new sim needed |

---

## 6. Staged Rollout (preserves SPEC-108 staging)

**Stage 0 — Deploy SPEC-108.1**
- Code changes per §3 deploy alongside Stage 1 SPEC-108 shadow
- Both V3 and V1b shadow streams begin running
- Strategy-drift monitor begins running
- Portfolio-stress overnight-gap function begins running (computed daily but not enforced until Stage 2)

**Stage 1 (continues, no change)**
- V3 shadow continues per SPEC-108 §6
- V1b shadow added in parallel

**Stage 2 (gated entry)**
- PM picks V3 OR V1b to activate (NOT both)
- Stage 2 gate now includes:
  - All 7 SPEC-108 §6 conditions (R5 ≥10 entries replaced by R3 regime-coverage; PM waiver remains)
  - **NEW condition 8**: portfolio-stress overnight-gap < 12% NLV
- Per-strategy drift status must not be alerting at time of PM signoff

**Stage 3 (unchanged)**
- PM-discretionary after Stage 2 forward evidence

---

## 7. Monitoring Obligations (SPEC-108 §5 + new)

Adds Monitor #9 to existing 8:

| # | Monitor | Trigger | Action |
|---|---|---|---|
| 9 | **Per-strategy ladder trigger distribution drift** (R4) | Rolling 90-day share of any strategy > historical band ± 15pp | PM-discretionary review; if unexplained, investigate selector before continuing shadow / production |

---

## 8. PM Approval Signature

**PM signed 2026-05-29** (single "A" affirms all 7 items below)

- [x] Approve R1: portfolio-stress overnight-gap gate (12% NLV ceiling) as Stage 2 gate criterion #8
- [x] Approve R2: V1b parallel shadow implementation alongside V3
- [x] Approve R3: Stage 2 advancement gate revision — regime-coverage replaces flat ≥10
- [x] Approve R4: Monitor #9 per-strategy drift (rolling 90d ± 15pp from historical band)
- [x] Acknowledge R5/R6/R7 already applied to SPEC-108 §0 (bias defers wording; Sharpe correction; p05 disclosure)
- [x] Confirm V1b remains shadow-only until separate explicit Stage 2 V1b promotion decision
- [x] Confirm SPEC-108 §6 Stage 2 freeze can lift after SPEC-108.1 deployed AND Stage 1 R3 coverage criterion met

---

## 9. Developer Handoff Notes

### Implementation checklist

1. **Read SPEC-108 first**, then this revision
2. **Portfolio stress gate** (`strategy/sleeve_governance.py`):
   - Function `portfolio_stress_overnight_gap(state: dict) -> dict`
   - Returns `{"mark_loss_pct_nlv": float, "components": {...per-position breakdown...}, "gate_pass": bool}`
   - Inputs: current state (positions + NLV + market)
   - SPX -7% shock; IV +50% multiplier; BS reprice each open spread leg
   - For ladder-active positions: use entry mark + apply shock; compute new mark; diff = mark-loss
   - For Q042 long calls: shock direction reversed (long gamma benefits)
   - Aggregate across all sleeves
3. **V1b ladder** (`strategy/q078_ladder_v1b.py`):
   - Mirror structure of `strategy/q078_ladder.py`
   - Cadence: weekly anchor (Wed). If today is Wed and selector PASS → eligible. Else skip.
   - `v1b_ladder_eligible(market_state, v1b_state)` parallel signature to `v3_ladder_eligible`
   - `production_order_allowed_v1b()` mirror of V3 production-order guard
   - Shadow log to `data/q078_ladder_v1b_shadow.jsonl`
   - Runtime state in `data/q078_ladder_v1b_runtime.json`
   - All gates (concurrency, BP ceiling) shared with V3 (NOT separate caps; same physical position pool)
4. **Strategy distribution monitor** (`strategy/q078_ladder_monitors.py`):
   - Read shadow log (rolling 90 days)
   - Compute % share per strategy
   - Compare to historical bands (hardcoded from `research/q078/_signal_history_cache.csv`)
   - Return `{"drift_alert": bool, "distribution_90d": {strategy: pct}, "drift_detail": {strategy: dev_pp}}`
5. **API** (`web/server.py`):
   - Add to `/api/sleeve-governance/state`:
     - `ladder_v1b_mode`, `ladder_v1b_last_entry_date`, `ladder_v1b_cadence_eligible`, ... (11 fields mirror)
     - `ladder_strategy_drift_alert` (bool), `ladder_strategy_distribution_90d` (dict)
6. **Dashboard** (`web/templates/portfolio_home.html`):
   - Add V1b panel below V3 panel — identical structure; use yellow/orange tint to distinguish from V3 gold
   - Add drift status chip on V3 panel head: `[drift: none]` (green) / `[drift: BPS +18pp]` (orange)
   - Follow DESIGN.md; use `var(--text-2)`, NEVER `--text-muted` (per `feedback_text_muted_banned`)
7. **Telegram** (`notify/telegram_bot.py`):
   - Add V1b shadow alert mirror (same template, V1b prefix)
   - Add drift status one-line in daily summary
8. **Tests** (`tests/test_spec_108_1.py`):
   - Cover AC-108.1-1 through AC-108.1-13
   - Mirror style of `tests/test_spec_108.py`

### Stage gating discipline

- V1b shadow is **shadow-only by default**. `LADDER_V1B_MODE_DEFAULT = "shadow"`.
- V1b NEVER auto-activates production. Stage 2 activation is PM-discretionary AND must be explicit env-var (`LADDER_V1B_MODE=active`) AND mutually exclusive with V3 active (cannot both be "active" at once — last to be set wins, with warning).
- Per-strategy drift monitor is informational; does NOT block production. PM decides response.
- Portfolio stress gate at Stage 2 IS a hard block: if mark-loss > 12% NLV when ladder eligibility evaluated, ladder skip with reason "portfolio_stress_block".

### Reference docs

1. `task/SPEC-108.md` (parent, DONE)
2. `task/SPEC-108.1.md` (this file)
3. `research/q080/q080_memo.md` (calibration findings)
4. `task/chatgpt_review_response_2026-05-29.md` (R-item provenance)
5. `~/.claude/.../memory/feedback_methodology_primitives.md`, `feedback_sharpe_smoothing_artifact.md`

---

## 10. Estimated Effort

| Phase | CC+gstack | Human |
|---|---|---|
| portfolio stress gate (sleeve_governance) | ~1h | ~3h |
| V1b ladder module + state + shadow log | ~1.5h | ~4h |
| Strategy drift monitor + historical band derivation | ~1h | ~2h |
| API extension (13 new fields) | ~30 min | ~1.5h |
| Dashboard V1b panel + drift chip | ~1h | ~3h |
| Telegram V1b + drift integration | ~30 min | ~1h |
| `tests/test_spec_108_1.py` (13 ACs) | ~1h | ~4h |
| Backtest cache refresh + AC validation + deploy oldair | ~1h | ~2h |
| **Total** | **~7.5h** | **~5-6 days** |

Larger than original SPEC-108 (~5h) because adding 4 features (gate + V1b + monitor + dashboard mirror) vs 1 ladder.

---

## 11. References

- Parent: `task/SPEC-108.md`
- Audit chain: `task/chatgpt_review_packet_2026-05-28_to_05-29.md`, `task/chatgpt_review_response_2026-05-29.md`
- Calibration: `research/q080/q080_memo.md`, `research/q080/q080_p1_unsmoothed_mtm.py`, `research/q080/q080_p2_block_bootstrap.py`, `research/q080/q080_p3_sigma_calibration.py`
- Memory: `~/.claude/.../memory/feedback_noise_threshold.md` (calibrated), `~/.claude/.../memory/feedback_methodology_primitives.md` (new), `~/.claude/.../memory/feedback_sharpe_smoothing_artifact.md` (new), `~/.claude/.../memory/feedback_boundary_research_dual_threshold.md` (new), `~/.claude/.../memory/feedback_kill_gate_external_read.md` (new)
- Memory: `~/.claude/.../memory/feedback_text_muted_banned.md`, `feedback_theme_convention.md`, `feedback_deploy_oldair.md`, `feedback_backtest_cache_refresh.md`

---

## Review

（待 Developer 完成实施后由 Quant Researcher 填写）

- 结论：N/A（pending Developer handoff）
- 问题：N/A

---

Status: DRAFT
