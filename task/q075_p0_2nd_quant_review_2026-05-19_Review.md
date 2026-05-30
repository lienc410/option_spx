# Q075 P0 — 2nd Quant Review (Reply)

**Reviewer**: 2nd Quant
**Date**: 2026-05-19
**Source**: `research/q075/q075_p0_anchored_memo_2026-05-19.md`
**Verdict**: **PASS — P0 scope is properly locked. Quant can start P1 attribution.**

---

## Final verdict statement

> Q075 P0 is well-scoped and ready for P1. The research correctly treats IVP-blocked normal-state days as a Layer-3 replacement problem, not as a Gate F relaxation. Primary/Secondary samples are separated, cash/BOXX is a valid endpoint, candidate priority is data-driven, and portfolio-level validation is required before SPEC. Proceed to P1 attribution.

---

## Three things done well

1. **Primary vs Secondary sample separation** — avoids conflating "pure IVP/vol blocked" with "trend already broken"
2. **Cash / BOXX is valid endpoint** explicit in TL;DR — research will not over-fit to "must find a trade"
3. **P1 attribution first, no pre-set candidate priority, no implementation-cost ordering**

---

## Required revision before/during P1

### Revision A — soften §6 transition rejection wording

**Current §6 wording (too absolute)**:
> "any candidate that loses money on the way into stress is REJECTED regardless of mean PnL"

**Required revision**:
> "any candidate with material or repeated transition-loss concentration is rejected, per §8.2 thresholds"

**Reason**: Any defined-risk premium strategy will produce small transition losses on some episodes (Q074 B4 had failed-benign episodes but PASSED because losses were small + total contribution positive). Mechanical rejection on any single loss would falsely kill viable candidates. Align §6 with §8.2 quantitative thresholds.

### Sanity check — Type A/D in Primary sample

P1 attribution should include an automatic sanity check:

```
If Type A or Type D exceeds 5% of Primary sample,
pause and review sample construction before P2.
```

Not a blocker; just a guardrail. Primary sample by construction excludes (VIX < 15) and (SPX <= MA50, ddATH <= -6%), so Type A and Type D should be near-empty in Primary. If they aren't, something is wrong upstream (Gate F deploy bug, IVP_252 calculation drift, etc.).

---

## P1 execution priorities (2nd Quant guidance, not blocker)

### What P1 memo first-screen should show

```
Primary sample count
Type B count / % (transition warning)
Type C count / % (high-vol controlled)
Type A/D sanity count / %  (should be near 0)
forward stress 5d / 10d / 20d (per Type)
forward SPX / VIX (per Type)
cash baseline
best hypothetical payoff by Type (informational only)
```

### Branching logic after P1

```
If Type B dominates + stress prob high + hypothetical tails ugly:
  → Q075 likely DOCUMENT outcome (blocked days are cash days)
  → may skip P2 entirely

If Type C dominates + VIX flat/falling + stress prob manageable + IC or low-delta BPS beats cash:
  → proceed to P2 with C-targeted candidates
```

### Hypothetical PnL realism requirement

P1's H2-H6 are hypothetical, but must include:
```
estimated bid/ask/friction
defined max loss
stop assumption
holding period assumption
cluster rule assumption
```

Especially C2 short-DTE BPS — must NOT confuse "shorter holding" with "lower tail risk." Gamma / gap risk must be measured separately.

---

## G-review schedule confirmed

```
G2 — P1 attribution light review
G3 — P2 candidate prototype review (mandatory)
G4 — Final PROMOTE / DOCUMENT / REJECT review (mandatory before any SPEC)
```

Confirmed. Q075 risk profile justifies mandatory G3 + G4.

---

## 2nd Quant Sign-off

- [x] P0 scope locked
- [x] All 6 framing revisions confirmed applied
- [x] Primary/Secondary separation accepted
- [x] 4-Type partition accepted
- [x] Cash/BOXX endpoint accepted
- [x] Q075-specific success thresholds accepted
- [x] §6 wording revision required (mechanical)
- [x] Type A/D sanity check required (informational guardrail)
- [x] No additional blockers

→ Quant proceeds to P1 attribution after applying §6 wording revision + Type A/D sanity check.
