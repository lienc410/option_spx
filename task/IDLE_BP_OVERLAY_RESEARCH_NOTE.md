# IDLE_BP_OVERLAY_RESEARCH_NOTE

**Date:** 2026-04-26  
**From:** 2nd Quant Reviewer  
**To:** Claude Quant Researcher  

## 1. Objective Reset

Project objective is now:

> **Primary goal: maximize ROE reasonably.**

“Reasonably” means:
- control risk exposure
- avoid large drawdowns
- avoid margin stress / forced liquidation risk
- avoid hidden concentration in bad regimes

This objective is **not identical** to maximizing:
- Sharpe
- PnL/BP-day
- semantic purity of the rule

Those remain useful supporting metrics, but are no longer the top-level objective.

---

## 2. Why This Note Exists

Q021 Phase 4 established:

- `V_D` is **not** a smarter rule than baseline `V_A`
- its marginal `$/BP-day` is below baseline
- therefore it fails as a **rule upgrade**

However, that does **not** automatically imply it is economically useless.

A separate question remains:

> If baseline leaves meaningful BP idle, and that idle BP has no better use, should some of it be deployed through an aftermath sizing overlay to improve account-level ROE?

This is a **different** question from:
> Should `V_D` replace `V_A`?

---

## 3. Core Distinction: Rule Quality vs Capital Allocation

### 3.1 Rule Layer
Question:
- Is this a better canonical rule?
- Does it create higher-quality edge?
- Does it improve capital efficiency per unit BP?

Under this standard:
- `V_A` remains preferred
- `V_D` / `V_G` / other sizing-up variants do not win

### 3.2 Capital Allocation Layer
Question:
- After baseline rule and baseline size are already applied,
- if meaningful BP remains unused,
- should some additional capital be deployed into the same high-conviction setup?

This is not a strategy replacement problem.
It is a **capital deployment overlay** problem.

---

## 4. Correct Framing of the Open Question

Do **not** frame the next research pass as:

> “Should V_D replace V_A?”

That question is already answered: **No.**

Instead, frame it as:

> “Should we add a controlled IC_HV aftermath sizing overlay on top of the baseline system when idle BP is persistently underutilized?”

That is the right economic question under the updated project objective.

---

## 5. Why the ROE Argument Is Legitimate

2nd Quant view:

A strategy with lower marginal `$/BP-day` can still be economically rational if:

1. the incremental return remains positive
2. idle BP would otherwise remain unused
3. no better alternative use of BP exists
4. extra tail risk remains acceptable at account level

In that case:

> higher total PnL with slightly worse unit efficiency may still improve account-level ROE rationally

So the decision boundary is **not**:

> “Is this smarter per unit BP?”

It is:

> “Does this improve account-level ROE without creating unacceptable liquidation / margin / drawdown risk?”

---

## 6. New Research Objective

The next research cycle should evaluate:

> **Idle BP Deployment Overlay**

Candidate use case:
- IC_HV aftermath first entry
- after baseline rule and baseline size are already applied
- only when account still has spare deployable BP
- with explicit risk guardrails

This should be treated as an **overlay layer**, not a replacement of `SPEC-066`.

---

## 7. Required Research Questions

Claude Quant should answer:

### Q1. Is idle BP actually persistent enough to matter?
Need evidence on:
- average unused BP under current baseline
- distribution of idle BP over time
- how often idle BP is large enough for overlay to matter
- whether idle BP tends to appear in good or dangerous regimes

If idle BP is rarely available, overlay research has low value.

### Q2. Does overlay improve account-level ROE?
Need to compare:
- baseline ROE
- baseline + overlay ROE

Not just:
- overlay PnL/BP-day

### Q3. What is the incremental tail cost?
Need:
- incremental max drawdown
- incremental CVaR / disaster window damage
- margin stress under worst windows
- worst-case BP concentration
- liquidation-risk proxy under severe adverse moves

This must be evaluated at **account level**, not just per trade.

### Q4. Is overlay better than alternative uses of BP?
Possible alternatives:
- leave BP idle
- reserve BP for later baseline entries
- reserve BP for hedges
- reserve BP for future alternative strategies

Overlay should be approved only if it beats realistic opportunity cost.

---

## 8. Required Metrics (Overlay Evaluation Pack)

Future overlay research should include:

### Account-Level Return Metrics
- Total PnL
- ROE
- annualized ROE
- positive-year proportion

### Capital Use Metrics
- baseline BP utilization
- overlay incremental BP-days
- idle BP utilization rate
- incremental ROE per incremental BP-day

### Risk Metrics
- MaxDD
- CVaR 5%
- worst trade
- disaster-window net
- peak BP%
- margin stress proxy
- concurrent overlay days
- overlap with existing short-gamma exposure

### Decision Metrics
- incremental ROE
- incremental MaxDD
- incremental CVaR
- incremental return / incremental tail-risk ratio

---

## 9. Required Risk Guardrails

Any overlay candidate must explicitly answer:

### Guardrail A — No hidden leverage drift
Overlay must not silently transform the system into a much more levered short-vol posture than intended.

### Guardrail B — No margin stress near liquidation boundary
If VIX spikes while overlay is on, how close does the account move toward unacceptable BP compression?

### Guardrail C — No crowding out of better trades
If overlay consumes BP and later blocks better baseline trades, economics may reverse.

### Guardrail D — Tail cost must be visible
A small increase in average ROE is not worth it if worst-case account damage rises sharply.

---

## 10. Candidate Overlay Variants Worth Testing

Do **not** reopen the full Q021 semantic tree.
Focus narrowly on overlay forms.

### Overlay-1: Simple 1.5x aftermath first-entry overlay
- smaller than `V_D`
- likely better risk/return tradeoff

### Overlay-2: 2.0x first-entry overlay with no overlap
- avoid simultaneous amplified IC_HV posture

### Overlay-3: 2.0x first-entry overlay only when idle BP exceeds threshold
- makes overlay conditional on actual unused capital

### Overlay-4: 2.0x first-entry overlay with disaster-risk downgrade
- if stress flag active, revert to baseline size

### Overlay-5: Split-entry overlay
- 1x initially
- optional top-up only if follow-through remains acceptable

These should be tested as **capital deployment overlays**, not promoted as new canonical strategy rules.

---

## 11. Explicit Non-Goals

The next research pass should **not** try to prove:
- `V_D` is a better rule than `V_A`
- sizing-up is more capital efficient than baseline
- semantic purity is improved

Those questions are already closed enough for current purposes.

The new question is narrower:

> can controlled overlay deployment improve reasonable ROE?

---

## 12. Recommended Output Structure for Claude Quant

Claude should answer in this order:

1. How much BP is truly idle under baseline?
2. Is idle BP economically worth targeting?
3. Which overlay form gives the best incremental ROE?
4. What is the incremental tail cost?
5. Under what guardrails would overlay be acceptable or unacceptable?

---

## 13. Bottom Line

**2nd Quant conclusion:**

- `V_D` fails as a rule upgrade
- but may still be viable as an **idle-BP deployment overlay**
- the correct research standard is now:

> **maximize ROE reasonably, with explicit protection against excessive drawdown, margin stress, and liquidation-like scenarios**

The next step is not “promote V_D.”

The next step is:

> **evaluate whether a controlled aftermath sizing overlay can improve account-level ROE without creating unacceptable account-level risk.**
