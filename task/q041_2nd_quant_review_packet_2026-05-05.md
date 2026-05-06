# Q041 2nd Quant Review Packet

- Date: 2026-05-05
- Prepared by: Planner
- Audience: 2nd Quant
- Topic: `Q041 — Large-Cap Equity Option Income Overlay`
- Current branch state: `Phase 1 COMPLETE; Phase 2 COMPLETE; ready for 2nd Quant review on next-stage execution prep, candidate governance, and paper-trading routing`

---

## 1. Review Request

Please review the full `Q041` branch as a **next-stage execution-prep / candidate-governance** question.

We are **not** asking:

- to reopen broad Phase 1 / Phase 2 variant search
- to reinterpret `Q041` as already production-ready
- to force all candidates into the same decision bucket
- to treat overlap validation as already finished

We **are** asking:

> Given the current evidence, which `Q041` candidates are strong enough to move into the next-stage execution-prep / paper-trading lane, which must remain caveated, and which should stay observe-only?

Current planner interpretation:

- `SPX CSP Δ0.20 DTE30` = **formal candidate**
- `GOOGL CSP Δ0.20 DTE21` / `AMZN CSP Δ0.25 DTE21` = **borderline formal candidates**
- `COST/JPM` earnings iron condor = **observe-only candidates**

This packet asks you to validate or challenge that routing.

---

## 2. Top-Level PM Objective

PM’s current top-level objective remains:

> reasonably maximize account-level ROE

“Reasonably” currently means:

- preserve drawdown discipline
- avoid unacceptable tail concentration
- avoid hidden leverage / overlap artifacts
- prefer candidates that can survive paper-trading and governance review
- avoid promoting signal-rich but fragile branches too early

This means `Q041` is not being judged by Sharpe alone.

The next question is:

- which candidates are strong enough for the **next operational step**
- and what that step should actually be

---

## 3. Source Pack

### Core summary / planner context

- `task/q041_phase2_planner_context.md`
- `doc/q041_phase2_summary_2026-05-05.md`
- `PROJECT_STATUS.md`
- `RESEARCH_LOG.md`
- `sync/open_questions.md`

### Phase 1 detail layer

- `doc/q041_d1_data_sanity_report_2026-05-03.md`
- `doc/q041_d2_benchmark_replication_2026-05-04.md`
- `doc/q041_d3_module_ab_backtest_2026-05-04.md`
- `doc/q041_d4_module_c_earnings_2026-05-04.md`

### Phase 2 detail layer

- `doc/q041_p2_p01_dte45_overlap_corrected_2026-05-04.md`
- `doc/q041_p2_p02_costjpm_4yr_reframe_2026-05-05.md`
- `doc/q041_p2_p11_ivr_filter_2026-05-05.md`
- `doc/q041_p2_p12_googl_amzn_4yr_reframe_2026-05-05.md`
- `doc/q041_p2_p21_spx_csp_bearmarket_2026-05-05.md`
- `doc/q041_p2_p22_iv_regime_2026-05-05.md`

### Dual-source data / overlap work

- `doc/q041_data_alignment_note_2026-05-03.md`
- `doc/q041_overlap_validation_protocol_2026-05-03.md`

---

## 4. Executive Summary

Planner’s current synthesis of the full branch:

1. `Q041` is no longer a data-feasibility or broad-screening problem.
2. `Phase 1` and `Phase 2` are both complete enough to support candidate stratification.
3. The branch now has one clean leader:
   - `SPX CSP Δ0.20 DTE30`
4. The single-name CSP branch is promising but still caveated:
   - `GOOGL CSP Δ0.20 DTE21`
   - `AMZN CSP Δ0.25 DTE21`
5. Earnings IC has alpha signal, but not enough confidence to promote:
   - `COST`
   - `JPM`
6. `SPX DTE45` is no longer an active candidate branch:
   - `CC DTE45` eliminated
   - `CSP DTE45` observe-only
7. Overlap validation remains active, but it should be treated as:
   - stitched dataset admission / reconciliation work
   - not a reason to reopen completed historical candidate ranking

---

## 5. Current Candidate Stack

| Candidate | Current planner status | Why it still matters | Main caveat |
|---|---|---|---|
| `SPX CSP Δ0.20 DTE30` | **Formal candidate** | Survived `2022` bear-stress; cleanest full-window profile; best balance of signal, sample size, and governance simplicity | `2022 Jan–Apr` missing; still benefits from explicit sizing discipline |
| `GOOGL CSP Δ0.20 DTE21` | **Borderline formal** | Strong Sharpe / low drawdown profile in available window | Missing `2019–2021 / COVID` crisis tail |
| `AMZN CSP Δ0.25 DTE21` | **Borderline formal** | Strong enough signal to stay in progression lane | Same missing pre-2022 / COVID tail |
| `COST` earnings IC `T-3 1.0×` | **Observe-only** | Good per-event economics; strongest earnings-IC name with JPM | `N=15`, no COVID sample, earnings-event fragility |
| `JPM` earnings IC `T-3 1.0×` | **Observe-only** | Best raw ROE/event in earnings-IC branch | `N=9`, tiny sample, optional `IMR>=33%` is weak / secondary |

### Explicitly not in active candidate track

- `SPX CC DTE45` — eliminated
- `SPX CSP DTE45` — observe-only
- `META` earnings IC — structurally excluded
- earnings put spreads — structurally fail

---

## 6. Candidate-by-Candidate Evidence Snapshot

### A. SPX CSP Δ0.20 DTE30

Current planner read:

- strongest clean candidate
- Phase 2 did not weaken it
- `2022` bear-stress read supports keeping it at the front of the queue

Most important evidence:

- Phase 1 baseline candidate
- `P2-1` confirms only `1` losing cycle in `2022`
- full-window Sharpe / drawdown profile remains the cleanest in the stack
- risk-management interpretation is now “size correctly,” not “add brittle static filters”

Open caveats:

- no data before `2022-05-06`
- `2022-08-19` “IV compression trap” remains the key cautionary case

Planner default next-step:

- move into **paper-trading / execution-prep** lane

### B. GOOGL / AMZN CSP

Current planner read:

- signals are strong enough to avoid downgrading to observe-only
- but evidence is not long-history clean enough to treat as fully formal

Most important evidence:

- GOOGL Sharpe `2.28`
- AMZN Sharpe `1.50`
- 4-year sample already includes `2022` bear regime
- still clearly stronger than the earnings-IC branch on evidence quality

Open caveats:

- no `2019–2021 / COVID`
- single-name tail risk remains under-validated

Planner default next-step:

- allow **borderline-formal paper-trading progression**
- require explicit tail caveat in all downstream docs

### C. COST / JPM Earnings IC

Current planner read:

- real signal exists
- confidence is not high enough for promotion

Most important evidence:

- `P0-2` confirms historical extension is blocked; accept 4-year window only
- `P2-2` shows `VIX < 15` is a real weak-loss regime
- `VIX >= 15` improves aggregate behavior
- `JPM IMR>=33%` is only a secondary / optional paper-trading rule

Open caveats:

- `COST N=15`, `JPM N=9`
- no COVID-era earnings sample
- event-driven tail risk remains structurally harder to trust

Planner default next-step:

- keep in **observe-only / cautious paper-trading** lane
- do not promote to formal candidate yet

---

## 7. Data / Method Constraints That Still Matter

These constraints should remain visible in the 2nd Quant review:

1. Massive pre-2022 history is unavailable (`403 Forbidden`)
2. `GOOGL / AMZN / COST / JPM` all inherit that history limit
3. overlap validation is still active for the stitched dataset
4. raw full-chain key-match should not be used as the decisive overlap denominator
5. `SPX` Massive Greeks / IV remains a structural single-source exception

Current planner position:

- these constraints do **not** reopen the completed historical ranking work
- but they do affect how confidently we promote candidates into the next lane

---

## 8. Specific Questions For 2nd Quant

Please answer these directly.

### Q1. SPX CSP DTE30

Is the evidence now strong enough to treat `SPX CSP Δ0.20 DTE30` as:

- ready for next-stage execution prep / paper trading
- still too fragile and should stay research-only
- or somewhere in between

If you think it is not ready, what is the single strongest reason?

### Q2. GOOGL / AMZN CSP

Do `GOOGL CSP Δ0.20 DTE21` and `AMZN CSP Δ0.25 DTE21` deserve the current planner label:

- **borderline formal candidates**

Or should they instead be:

- downgraded to observe-only
- or promoted to the same lane as `SPX CSP DTE30`

### Q3. COST / JPM Earnings IC

Is the current observe-only routing correct?

And do you agree with the current planner treatment of:

- `VIX >= 15` as a real governance / entry candidate
- `IMR >= 33%` for `JPM` as optional paper-trading-only refinement

### Q4. Overlap validation vs candidate promotion

Do you agree with the current separation:

- overlap validation continues for stitched dataset admission
- but historical candidate ranking can already be used for next-lane preparation

If not, what should still be considered blocked?

### Q5. Next-stage packaging

Which of these is the correct next lane for `Q041`?

- `A` — execution-prep / paper-trading packet for `SPX CSP DTE30` only
- `B` — packet for `SPX + GOOGL/AMZN` together, with tiered caveats
- `C` — keep all of `Q041` in research-only until overlap validation completes

Please choose one and explain briefly.

---

## 9. Planner Default Recommendation To 2nd Quant

Current planner recommendation is:

- **do not reopen broad research**
- accept that `Q041 Phase 2` is complete
- validate the current tiering unless there is a strong reason not to
- most likely next operational path:
  - `SPX CSP Δ0.20 DTE30` → next-stage execution prep / paper-trading lane
  - `GOOGL/AMZN CSP` → same lane but clearly labeled as tail-caveated
  - `COST/JPM` earnings IC → observe-only / cautious paper-trading lane

So the main 2nd Quant job is not to invent more candidates.
It is to judge whether this tiering is robust enough for PM governance and next-stage routing.

---

## 10. Proposed Reply Format

Please structure your reply as:

1. One-line overall verdict
2. `SPX CSP DTE30`
3. `GOOGL / AMZN CSP`
4. `COST / JPM earnings IC`
5. `Overlap validation interaction`
6. Final routing recommendation: `A / B / C`

Keep the review focused on next-stage candidate governance, not on restarting Phase 2 research.
