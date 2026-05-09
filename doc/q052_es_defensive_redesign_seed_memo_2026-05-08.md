# Q052 — `/ES` Defensive Redesign Seed Memo

Date: 2026-05-08
Owner: Planner
Status: research seed

## Why Q052 Exists

`Q012` and `Q051` are now closed at the current `$500k` account scale.

The original `/ES` thesis was validated only in its larger full-system form and was found to be scale-dependent. The current `1`-contract production path remains useful as a live-data / visibility / operational-calibration cell, but it is not a production ROE engine at this account size.

PM nevertheless identified three new `/ES` redesign directions that are materially different from the original thesis and should be preserved as a separate future research branch rather than folded back into `Q012` or `Q051`.

## What Q052 Is

`Q052` is a **future `/ES` redesign branch**.

It asks whether a different structural `/ES` approach could become viable even though the original large-scale thesis is not production-plausible at the current account size.

## What Q052 Is Not

`Q052` is **not**:

- a continuation of the original `/ES` thesis line
- a reopening of `Q012` shared-BP governance
- a reopening of `Q051` performance salvage
- a current implementation spec
- a current queue priority ahead of `Q041`

## Candidate Research Directions

### 1. Technical-risk-off exits

Study whether technical breakdown recognition can trigger earlier defensive action than passive `3x / 4x credit` stop logic.

The key question is:

> Can explicit technical deterioration improve capital preservation enough to change the viability of the `/ES` line at smaller scale?

### 2. Roll-down / roll-out management

Conditional on a technical-risk-off framework, study whether a defensive roll path:

- lower strike
- farther expiry

can preserve more long-run expectancy than direct stop-out.

The key question is:

> Is active roll management structurally better than hard-stop liquidation for this line, or does it simply defer losses?

### 3. Very-far-OTM long-dated short puts

Study whether extremely far OTM, long-dated naked puts (for example, an index near `7000` selling a `~3500` strike six months out) create a meaningfully different distribution than the current `45 DTE / Δ0.20` family.

The key question is:

> Is there a genuinely different low-frequency, catastrophe-premium-harvest design here, or just a weaker version of the original line?

## Current Priority

Low.

`Q052` should stay behind:

- `Q041`
- currently active implementation and runtime follow-up work

It exists so the project does not lose the PM's broader strategic idea, but it is not the next active lane.

## Planner Interpretation

The correct framing is:

- `Q012/Q051` = closed original `/ES` thesis line at current account scale
- `Q052` = new future redesign branch with different structural hypotheses

This separation matters because it avoids pretending that the new ideas are merely parameter tweaks on the old thesis.
