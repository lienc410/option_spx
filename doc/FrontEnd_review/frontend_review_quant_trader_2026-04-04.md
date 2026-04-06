# Frontend Review — Quant Trader Perspective

Date: 2026-04-04
Repo: `SPX_strat`
Reviewer lens: discretionary/quant options trader using the UI for daily decision support, risk review, and post-trade research

## Executive Summary

Current frontend quality is solid and already above a typical internal dashboard. It is not just a visualization layer anymore; it is a usable decision-support interface.

Overall score: `7.5 / 10`

Main judgment:
- The current frontend works well as a strategy research dashboard
- It is not yet fully optimized as an execution-first trading console
- The strongest areas are signal clarity, matrix explanation, and visual hierarchy
- The weakest areas are top-level risk surfacing, execution prioritization, and counterfactual clarity

## What Is Working Well

### 1. Information architecture is directionally correct

The current flow is intuitive for a trader:
- signals first
- recommendation second
- supporting context after that

This mirrors the actual workflow:
1. What regime are we in?
2. What is the system recommending right now?
3. Why?
4. What are the constraints / exceptions?

The current dashboard is much closer to a useful terminal than a generic analytics page.

### 2. Signal readability is strong

The signal cards do a good job of making regime, IV, and trend legible at a glance. A trader can scan the page in a few seconds and understand the current state.

Strengths:
- concise labels
- consistent color semantics
- readable numerics
- enough spacing to prevent cognitive overload

### 3. Recommendation presentation is clear and credible

The recommendation card is one of the strongest parts of the UI. It presents:
- strategy name
- legs
- max risk
- target
- roll rule
- rationale

This is the right object model for an options trader. It moves beyond “signal dashboard” into “trade construction assistant.”

### 4. Matrix page is genuinely valuable

The matrix page is not just decorative. It serves as:
- a strategy map
- a model explainability surface
- a regime-to-strategy reference

The distinction between:
- canonical matrix path
- current signal cell
- live override

is especially important. That was the right design correction.

### 5. Visual language is coherent

The current typography and palette are well chosen for this product category.

Notable strengths:
- `Newsreader` gives strategy identity and seriousness
- `JetBrains Mono` makes values feel precise and operational
- dark palette reduces dashboard glare and fits terminal-adjacent usage
- gold/green/red/blue usage is broadly intuitive

This is a more distinctive and intentional visual system than most internal quant dashboards.

## Main Weaknesses From a Trader’s View

### 1. The dashboard is not yet execution-first

A trader opening the page during market hours usually wants these answers immediately:
- What should I do now?
- Why now?
- What blocks the canonical trade?
- What would need to change for the blocked trade to become valid?
- What risk is already on in the book?

The current UI contains much of this information, but it is still somewhat distributed across sections.

Implication:
- good for review
- slightly slower than ideal for live decision-making

### 2. Risk is not surfaced early enough

For a quant trader, the first screen should emphasize not only signal state, but also portfolio risk state.

Right now, the frontend is still more recommendation-centric than risk-centric.

What feels underexposed:
- backwardation state
- macro warning
- guardrail status
- overlay status
- shock exposure
- BP utilization / remaining headroom
- whether the system is in a throttle/freeze state

These are decision-critical. A trader often wants to know “why not trade?” before “what to trade?”

### 3. Matrix is informative, but not yet counterfactual enough

The matrix now handles canonical vs live better than before, but a trader still wants stronger counterfactual guidance.

For example:
- canonical = `Bear Call Spread (High Vol)`
- live = `Reduce / Wait`
- blocked by = `VIX RISING`

That is good, but the next question is:
- what exact condition would re-enable the canonical strategy?

Without that, the matrix explains the current override but does not yet help the trader plan the next state transition.

### 4. Backtest/research outputs are probably underutilized in the frontend

The backend now has richer research data than the frontend appears to expose.

From a quant trader perspective, the highest-value research widgets would include:
- `pnl_per_bp_day`
- strategy attribution
- regime attribution
- OOS vs IS split
- current params hash / experiment id
- shock hit-rate summary
- overlay impact summary

If those are only available in scripts or raw APIs, then the frontend is leaving research value on the table.

## Quant Trader Priorities the Frontend Should Reflect More Strongly

### 1. Action-first hierarchy

Top of screen should answer:
- `LIVE recommendation`
- `Action`
- `Blocking guardrail`
- `Next eligible state`

This should be readable in under 3 seconds.

### 2. Risk-first hierarchy

Before a trader enters a position, they want to know:
- is the current recommendation valid?
- is it blocked by guardrails?
- what is portfolio risk already?
- are we close to a capital or shock limit?

This is especially important for a multi-position options book.

### 3. Scenario awareness

A quant trader often thinks in conditional states:
- if VIX flattens, then X
- if SPX recovers above MA50, then Y
- if backwardation clears, then Z

The UI should support that style of reasoning more explicitly.

### 4. Capital efficiency, not just raw PnL

Options traders care about:
- return on capital
- buying power efficiency
- risk-adjusted deployment quality

So `pnl_per_bp_day`, BP usage, and position efficiency should be visually prominent, not hidden in deeper analytics.

## Recommended Improvements

## Priority 1 — Decision Strip on the Dashboard

Add a top-of-screen “decision strip” with:
- `LIVE: Reduce / Wait`
- `Reason: HIGH_VOL + BEARISH + VIX RISING`
- `Canonical: Bear Call Spread (High Vol)`
- `Blocked by: VIX RISING`
- `Next eligible: if VIX trend = FLAT/FALLING`

Why:
- fastest possible trader read
- removes ambiguity between matrix and live execution state
- turns explanation into actionability

## Priority 2 — Add a Portfolio Risk Bar

Create a compact risk summary near the top showing:
- BP used / BP headroom
- overlay level
- shock state
- backwardation
- macro warning
- short-gamma count

Why:
- traders first care whether they are allowed to add risk
- current UI is more strategy-forward than risk-forward
- this would rebalance it properly

## Priority 3 — Upgrade Matrix to Show Counterfactual Logic

For the highlighted cell, show:
- current signal cell
- canonical strategy
- live strategy
- exact guardrail trigger
- explicit re-enable condition

Example:
- `Canonical: Bear Call Spread (HV)`
- `Live: Reduce / Wait`
- `Override: VIX RISING`
- `Re-enable when VIX trend becomes FLAT or FALLING`

Why:
- this is how traders think
- it reduces confusion
- it makes the matrix a tactical planning tool

## Priority 4 — Elevate Research Metrics in the Backtest UI

The backtest page should prioritize:
- Ann Return
- Sharpe
- Calmar
- Max Drawdown
- CVaR95
- `pnl_per_bp_day`
- attribution by strategy
- attribution by regime
- OOS vs IS summary
- params hash / experiment id

Why:
- those are the metrics that matter for strategy governance
- they are more trader-relevant than a generic performance summary

## Priority 5 — More Explicit “Why Not” Messaging

The system is now sophisticated enough that “no trade” can result from:
- guardrails
- backwardation
- rising VIX
- overlay freeze
- shock limit
- spell throttle

The frontend should state this in a direct hierarchy:
- `No trade because X`
- `Secondary blockers: Y, Z`

Why:
- avoiding trade is itself a signal
- traders need to trust non-action as much as action

## Suggested Product Reframing

Right now the frontend behaves mostly like:
- a strategy dashboard

The best next step is to make it behave like:
- a risk-aware options decision console

That does not require a visual redesign. The visual system is already good enough. The main opportunity is information hierarchy and decision framing.

## Final Assessment

This frontend is already materially better than a typical internal quant UI because:
- it has a coherent visual language
- it surfaces the recommendation object clearly
- it now separates canonical logic from live logic
- it is built around actual strategy decisions rather than generic KPI charts

But from a trader’s perspective, the next level is clear:
- less “what the model says in general”
- more “what I should do now, why, what blocks it, and what changes next”

If the frontend evolves in that direction, it can become a true daily operating console rather than just a strong research dashboard.
