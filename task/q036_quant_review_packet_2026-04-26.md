# Q036 2nd Quant Review Packet

- Date: 2026-04-26
- Prepared by: Planner
- Audience: 2nd Quant
- Topic: `Q036 — Idle BP Deployment / Capital Allocation`
- Current branch state: `ready for PM decision packet` candidate, but **not** yet promoted to DRAFT overlay spec discussion

---

## 1. Review Request

Please review the full `Q036` research line as a **capital-allocation layer** question, not a rule-replacement question.

We are **not** asking:

- whether `V_D` / any other sizing-up rule should replace `V_A / SPEC-066`
- whether `Q021` should be reopened
- whether production should change now

We **are** asking:

> Given the current objective of reasonably maximizing account-level ROE under explicit risk guardrails, is the `Q036` evidence now strong enough to justify a PM decision packet around a narrow overlay candidate?

Current lead candidate:

- `Overlay-F_sglt2`
- `2x` iff:
  - `idle BP >= 70%`
  - `VIX < 30`
  - `pre-existing short-gamma count < 2`

---

## 2. Top-Level PM Objective

PM has reset the project’s top-level objective to:

> reasonably maximize account-level ROE

“Reasonably” currently means:

- avoid unacceptable drawdown
- avoid margin stress / forced-liquidation risk
- avoid hidden concentration / short-gamma stacking
- avoid deploying capital in a way that crowds out better uses

Current opportunity-cost baseline:

- `A`: if no better use exists, idle BP may remain idle

This is why `Q036` is evaluated against the **idle-capital baseline**, not against `V_A`’s rule-layer `PnL/BP-day`.

---

## 3. Boundary vs Q021

`Q021` already answered the rule-layer question:

- `V_A / SPEC-066` remains the canonical aftermath rule
- `V_D / V_E / V_J / V_G` do **not** earn promotion to new canonical rule

So `Q036` is **not**:

- “should we replace `SPEC-066`?”

It is:

- “given large persistent idle BP, should the system add a controlled overlay to improve account-level ROE?”

`Q021` therefore remains:

- rule-layer evidence base
- pilot input
- not the parent frame for `Q036`

---

## 4. Source Pack

### Detail-layer docs

- `doc/q036_framing_and_feasibility_2026-04-26.md`
- `doc/q036_phase3_guardrail_refinement_2026-04-26.md`
- `doc/q036_phase4_short_gamma_guard_2026-04-26.md`
- `doc/q036_phase5_overlay_f_confirmation_2026-04-26.md`
- `doc/q021_phase4_sizing_curve_2026-04-26.md`
- `doc/q021_variant_matrix_2026-04-26.md`

### Prototypes

- `backtest/prototype/q036_phase1_idle_bp_baseline.py`
- `backtest/prototype/q036_phase2_overlay_pilots.py`
- `backtest/prototype/q036_phase3_guardrail_refinement.py`
- `backtest/prototype/q036_phase4_short_gamma_guard.py`
- `backtest/prototype/q036_phase5_overlay_f_confirmation.py`

### Index / planner context

- `PROJECT_STATUS.md`
- `RESEARCH_LOG.md`
- `sync/open_questions.md`

---

## 5. Executive Summary

Current planner interpretation of the full branch:

1. `Q036` is a legitimate research branch because idle BP is structurally large and persistent.
2. Raw overlay economics are positive relative to the idle-capital baseline.
3. The real branch risk is not deploy capacity, but short-gamma stacking and tail-cost discipline.
4. Early overlay variants (`A/B/C`) were positive but not strong enough for escalation.
5. Guardrail refinement eventually produced one credible compromise candidate:
   - `Overlay-F_sglt2`
6. Final confirmation suggests `Overlay-F` is:
   - not a single-year artifact
   - not cheating its own guardrails
   - still positive in `2018+`
7. Current branch state is therefore:
   - **do not drop**
   - **do not widen the tree further**
   - **ready for PM decision packet**
   - still **not automatically DRAFT-ready**

---

## 6. Phase-by-Phase Research Progress

### Phase 1 — Feasibility / Idle BP Baseline

Reference:

- `doc/q036_framing_and_feasibility_2026-04-26.md`
- `backtest/prototype/q036_phase1_idle_bp_baseline.py`

Core question:

- Is idle BP large and persistent enough to justify overlay research at all?

Key findings:

- average BP used: `8.68%`
- average idle BP: `91.32%`
- max BP used across full sample: `30%`
- aftermath days with `>= 70%` idle BP: `100%`
- disaster windows still retained large idle BP:
  - `2008 GFC`: mean idle `97.2%`
  - `2020 COVID`: mean idle `92.3%`
  - `2025 Tariff`: mean idle `86.5%`

Most important new risk finding:

- aftermath days with pre-existing `>= 2` short-gamma positions:
  - full sample: `47%`
  - recent slice: `54%`

Interpretation:

- deploy capacity is **not** the bottleneck
- short-gamma stacking **is**

Planner takeaway:

- Phase 1 justified continuing the branch
- it also forced no-overlap / disaster-aware guardrails into the next phase

---

### Phase 2 — Narrow Pilot Overlays

Reference:

- `backtest/prototype/q036_phase2_overlay_pilots.py`
- summarized in `RESEARCH_LOG.md` / `sync/open_questions.md`

Pilot set:

- `Overlay-A`: `1.5x` first-entry conditional
- `Overlay-B`: `2x` conditional + disaster cap
- `Overlay-C`: `2x` conditional + no-overlap

All variants keep:

- `idle BP >= 70%` gating

Baseline:

- total PnL: `+$403,850`
- annualized ROE: `8.67%`
- positive years: `25/27`

Phase 2 results:

| Variant | Total PnL | Annualized ROE | Uplift vs baseline | Disaster Net | Peak BP% | SG>=2 fire rate |
|---|---:|---:|---:|---:|---:|---:|
| `Overlay-A` | `+$410,630` | `8.73%` | `+0.054pp` | `-561` | `31%` | `16%` |
| `Overlay-B` | `+$414,556` | `8.76%` | `+0.088pp` | `+302` | `38%` | `20%` |
| `Overlay-C` | `+$413,214` | `8.75%` | `+0.077pp` | `-99` | `34%` | `0%` |

Shared observations:

- all three are positive vs idle baseline
- all three slightly worsen full-sample `CVaR 5%` (`-4,382` vs baseline `-4,309`)
- crowd-out check reported `OK`
- idle-BP utilization is very low (`0.39%` to `0.46%`)

Interpretation:

- `A` is weakest and mostly discardable
- `B` is best on raw uplift and disaster net, but dirtiest on residual stacking and peak BP
- `C` is cleaner, but gives up some return and disaster-window quality

Planner takeaway:

- continue research
- narrow to `B` and `C`
- do not move to DRAFT spec discussion

---

### Phase 3 — Guardrail Refinement (`B + C`)

Reference:

- `doc/q036_phase3_guardrail_refinement_2026-04-26.md`
- `backtest/prototype/q036_phase3_guardrail_refinement.py`

Question:

- Can we combine `B`’s disaster cleanliness with `C`’s stacking cleanliness without sacrificing too much uplift?

New variants:

- `Overlay-D_hybrid` = `Overlay-B + Overlay-C`
- `Overlay-E_hyb80` = `Overlay-D + idle BP >= 80%`

Results:

| Variant | Total PnL | Annualized ROE Uplift | Disaster Net | Peak BP% | SG>=2 fire rate |
|---|---:|---:|---:|---:|---:|
| `Overlay-B` | `+$414,556` | `+0.088pp` | `+301` | `38%` | `20%` |
| `Overlay-D` | `+$409,492` | `+0.046pp` | `+301` | `34%` | `0%` |
| `Overlay-E` | `+$409,492` | `+0.046pp` | `+301` | `34%` | `0%` |

Interpretation:

- `D` proves stacking can be engineered away
- but the uplift is cut roughly in half
- `E` is inert relative to `D`, so the stricter `80%` idle gate adds no value in practice

Planner takeaway:

- `D` is governance-clean but economically too thin
- next question should not be “more variants,” but “can we relax the guardrail in a more account-level way?”

---

### Phase 4 — Short-Gamma-Count Guard

Reference:

- `doc/q036_phase4_short_gamma_guard_2026-04-26.md`
- `backtest/prototype/q036_phase4_short_gamma_guard.py`

Question:

- Can we replace the blunt `no IC_HV open at all` guard with something closer to actual account-level risk?

New variants:

- `Overlay-F_sglt2` = `2x` iff `idle BP >= 70%`, `VIX < 30`, and `pre-existing short-gamma count < 2`
- `Overlay-G_sg0` = same but require `short-gamma count == 0`

Results:

| Variant | Total PnL | Annualized ROE Uplift | Disaster Net | Peak BP% | SG>=2 fire rate |
|---|---:|---:|---:|---:|---:|
| `Overlay-B` | `+$414,556` | `+0.088pp` | `+301` | `38%` | `20%` |
| `Overlay-D` | `+$409,492` | `+0.046pp` | `+301` | `34%` | `0%` |
| `Overlay-F` | `+$412,855` | `+0.074pp` | `+301` | `34%` | `0%` |
| `Overlay-G` | `+$405,876` | `+0.016pp` | `+301` | `31%` | `0%` |

Interpretation:

- `F` is the first convincing compromise:
  - far better than `D` economically
  - much cleaner than `B`
  - not overly narrow like `G`

Planner takeaway:

- `Overlay-F` becomes the lead candidate
- still not DRAFT-ready
- but now merits one final narrow confirmation

---

### Phase 5 — Final Narrow Confirmation on `Overlay-F`

Reference:

- `doc/q036_phase5_overlay_f_confirmation_2026-04-26.md`
- `backtest/prototype/q036_phase5_overlay_f_confirmation.py`

Goal:

- Confirm that `Overlay-F` is not a fragile artifact before moving to PM decision stage

#### Top-line

| Metric | Baseline | Overlay-F | Delta |
|---|---:|---:|---:|
| Total PnL | `+$403,850` | `+$412,855` | `+$9,005` |
| Annualized ROE | `8.675%` | `8.748%` | `+0.074pp` |
| MaxDD | `-10,323` | `-9,749` | improved |
| CVaR 5% | `-4,309` | `-4,382` | worse by `74` |

#### Yearly attribution

- positive delta years: `11 / 27`
- negative delta years: `4 / 27`
- zero years: `12 / 27`
- largest single-year contributor:
  - `2022 +$1,896`
  - only `17.6%` of absolute yearly delta
- remove strongest `1` year:
  - still `+$7,111`
- remove strongest `2` years (`2022`, `2008`):
  - still `+$5,285`

Interpretation:

- uplift is **sparse but distributed**
- not a one-year or one-case illusion

#### Fire distribution

- total fires: `23`
- regime:
  - `HIGH_VOL: 23`
- VIX bucket:
  - `20-25: 5`
  - `25-30: 18`
- pre-existing short-gamma count:
  - `0: 9`
  - `1: 14`
  - `>=2: 0`
- mean idle BP at fire:
  - `80.5%`

Interpretation:

- guardrail behavior is coherent with design
- no hidden `SG>=2` leakage

#### Recent-era (`2018+`)

| Metric | Baseline | Overlay-F | Delta |
|---|---:|---:|---:|
| Total PnL | `+$164,958` | `+$169,353` | `+$4,395` |
| Annualized ROE | `5.544%` | `5.583%` | `+0.040pp` |
| MaxDD | `-9,405` | `-9,392` | flat/slightly better |
| CVaR 5% | `-3,798` | `-3,798` | flat |
| Peak BP% | `30%` | `34%` | worse |

Interpretation:

- still positive in recent era
- but thinner than full-sample uplift

Planner takeaway:

- stop expanding the research tree
- `Q036` is now best understood as **ready for PM decision packet**

---

## 7. Consolidated Candidate Ranking

This is the current planner synthesis of the branch:

| Candidate | Economic quality | Guardrail quality | Current status |
|---|---|---|---|
| `Overlay-A` | weak | weak | effectively eliminated |
| `Overlay-B` | best raw uplift | dirtiest residual stacking | useful reference, not current favorite |
| `Overlay-C` | decent | cleanest among Phase 2 | useful reference, superseded by F |
| `Overlay-D` | too thin | very clean | intermediate proof, not lead |
| `Overlay-E` | same as D | same as D | inert / no independent value |
| `Overlay-F` | best compromise | clean enough (`SG>=2 = 0`) | **lead candidate** |
| `Overlay-G` | too thin | very clean | overly restrictive |

---

## 8. Planner’s Current Interpretation

What appears settled:

1. `Q036` should not be dropped as a false branch.
2. Idle BP is real and persistent enough to matter.
3. Raw overlay economics are positive vs the idle baseline.
4. Stacking governance is the real control problem.
5. `Overlay-F` is the strongest compromise discovered so far.
6. There is no evidence that continuing to widen the variant tree is worthwhile.

What does **not** appear settled:

1. The uplift is still small in absolute account terms.
2. Full-sample `CVaR 5%` remains slightly worse.
3. Recent-era uplift is thinner, not stronger.
4. It is still not obvious that this should become a production-governance project.

Therefore the branch appears to have moved from:

- “open research”

to:

- “ready for PM decision packet”

but **not** to:

- “ready for DRAFT overlay spec discussion”

---

## 9. Questions for 2nd Quant Review

Please answer as a reviewer, not by reopening the entire research tree.

### Q1. Framing check

Do you agree that `Q036` has stayed within the correct frame:

- capital-allocation layer
- account-level ROE under guardrails
- not a disguised `Q021` rule-replacement branch

### Q2. Evidence sufficiency

Do you agree that the current evidence is now strong enough to support:

- `ready for PM decision packet`

even if it is still **not** strong enough to support:

- `ready for DRAFT overlay spec discussion`

### Q3. Candidate quality

Do you agree that `Overlay-F_sglt2` is now the correct lead candidate?

If not, please state the minimum concrete reason:

- methodology concern
- metric interpretation concern
- hidden concentration concern
- recent-era robustness concern
- or another specific issue

### Q4. Remaining blocker

If you do **not** agree that this is ready for PM decision packet, what is the smallest remaining blocker?

Please keep it narrow and specific.

### Q5. Review verdict

Please end with one clear verdict:

- `PASS — ready for PM decision packet`
- `CHALLENGE — continue research before PM decision packet`
- `FAIL — framing or evidence insufficient`

---

## 10. Planner Recommendation to 2nd Quant

Current planner recommendation is:

> `Overlay-F_sglt2` has survived the full narrowing process. It is not a knockout case for spec escalation, but it is no longer an open-ended exploration branch either. The most useful 2nd Quant task now is to judge whether the evidence is sufficient for PM governance review, not to reopen broad variant search.

---

## 11. Methodology Note — Short-Gamma Counting (Post-Review Addendum)

Added 2026-04-26 by Quant Researcher after synthesis of 2nd / 3rd Quant reviews. Verdict on packet readiness: `PASS WITH CAVEAT`.

### The inconsistency

- **Gate** (`_preexisting_short_gamma_count`, `backtest/prototype/q036_phase4_short_gamma_guard.py:33-35`) uses a **family-deduplicated** count: it builds `set(catalog_key(...))` over open positions, then counts how many of those distinct families are short-gamma.
- **Framing metric and cleanliness report** (`backtest/engine.py:1073` → `DailyPortfolioRow.short_gamma_count`, consumed by Phase 1 stacking measurement and Phase 5 fire-distribution report at `backtest/prototype/q036_phase5_overlay_f_confirmation.py:67`) use a **position-count**: every open short-gamma position is counted, no dedup.

The Phase 5 §3 cleanliness claim — `Fires with pre-existing SG>=2: 0/23` — is computed from the **position-count** metric (the stricter one).

### Empirical impact in this sample

In the 2000–2026 sample, the 23 overlay fires admitted by the family-dedup gate distribute as `pre-existing SG = 0: 9` and `SG = 1: 14` under the **position-count** metric, with `SG >= 2: 0`. The cleanliness claim therefore holds under both counting conventions in this sample. The two conventions would only diverge if multiple positions of the same short-gamma family were open simultaneously at fire time, which never occurred.

### Why this is a caveat, not a blocker

This is a **presentation issue, not a numerical issue**. Q036 is a PM **governance-decision** packet, not a productization packet. The empirical claim "SG≥2 = 0" stands under the stricter metric we report.

Should PM elect to escalate `Overlay-F` toward spec drafting, the gate must be aligned to position-counting (one-line change in `_preexisting_short_gamma_count` — drop the `set(...)` dedup) and Phase 4 / Phase 5 numbers re-verified, before any SPEC discussion. This alignment is **deferred to the productization stage** and is not required to admit the current packet to PM review.

