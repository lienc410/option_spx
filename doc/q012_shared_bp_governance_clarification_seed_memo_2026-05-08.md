# Q012 — `/ES` Shared-BP Governance Clarification Seed Memo

Date: 2026-05-08  
Role: Planner  
Status: open (Phase A+B+C complete; ready only for a narrow monitoring-spec, not a full governance spec)

## One-Line Conclusion

`Q012` has now completed enough research to answer the real design question, and the answer is more conservative than the earlier Phase A+B read:

> At the current live scale (`1` `/ES` contract on a `$500k` account), the correct next step is **not** a full shared-BP governance framework. The right narrow landing is a **SPAN post-entry visibility / monitoring surface**. A true governance framework only becomes justified when `/ES` grows into a meaningfully competing sleeve (`~3–5+` contracts).

## Why The Conclusion Changed

Phase A and Phase B made the problem look like a governance-rule question:

- SPAN expands materially under stress
- `/ES` and SPX Credit overlap frequently
- `HIGH_VOL` collision is structurally dangerous under the tested proxy assumptions

But Phase C answered the more important portfolio question:

> Does any of that meaningfully change account-level ROE or account-level behavior **at current size**?

The answer is effectively **no**.

## Phase A — SPAN Expansion Model

Phase A remains valid and important as a stress reference.

### Key Anchor Points

| Scenario | VIX | SPAN (new entry) | SPAN (10d held) | Double-pressure read |
|---|---:|---:|---:|---:|
| Normal | 19 | `$20,529` | `$19,648` | `$19,648` |
| Stress | 30 | `$33,853` | `$46,107` (`2.25x`) | `$52,101` (`10.4% NLV`) |
| Extreme | 40 | `$46,541` | `$70,533` (`3.44x`) | `$84,319` (`16.9% NLV`) |
| Crisis | 60 | `$73,367` | `$117,456` (`5.72x`) | `$148,400` (`29.7% NLV`) |

### Historical Distribution Read

- `P75 VIX = 22.8`
- `P90 VIX = 28.6` → SPAN roughly `~$49k` (`2.4x`)
- `P99 VIX = 46.8` → SPAN roughly `~$84k` (`4.1x`)

### Useful Operational Bands

**Pre-entry stress buffer**

- `VIX < 22` → static `$20,529`
- `VIX 22–30` → `1.3x`
- `VIX 30–40` → `1.6x`
- `VIX > 40` → `2.0x`

**Post-entry SPAN correction**

- `VIX < 22` → no correction
- `VIX 22–30` → `1.4x`
- `VIX > 30` → `1.8x`

These numbers still matter, but Phase C changes **how** they should be used in the current product stage.

## Phase B — Same-Day Competition Frequency

Phase B remains directionally true but turns out to be insufficient on its own.

### Collision Frequency

- `/ES` bullish days: `62.1%`
- SPX Credit entry days: `71.9%`
- Collision days: `39.1%` (`~1,901`, roughly `98`/year)
- Collision days breaching the tested cap: `27.1%`

### Regime Split

| Regime | Collision Days | Cap Breach Rate |
|---|---:|---:|
| `LOW_VOL (VIX < 15)` | `288` | `0%` |
| `NORMAL (VIX 15–25)` | `1,390` | `21.1%` |
| `HIGH_VOL (VIX 25–35)` | `195` | `100%` |
| `EXTREME_VOL (VIX > 35)` | `28` | `100%` |

The Phase B intuition was:

- below `VIX 25`, stress-adjusted Rule A+
- at/above `VIX 25`, Rule D regime-priority blocking

That was a reasonable intermediate interpretation. Phase C is what ultimately tells us whether that logic deserves to become product behavior **today**.

## Phase C — Architecture Comparison

### Headline Result

The governance architecture barely matters at current scale.

| Architecture | `/ES` Trades | Marginal ROE Contribution | SPAN Breach Events |
|---|---:|---:|---:|
| `Arch-0` baseline (SPX Credit only) | `0` | — | `0` |
| `Arch-1` simple overlay (`20%` cap) | `158` | `~0pp` | `82` |
| `Arch-2` dynamic budget (stress-adjusted) | `163` | `-0.002pp` | `78` |
| `Arch-3` regime-gated (`HIGH_VOL` lockout) | `152` | `-0.006pp` | `79` |

### Three Counterintuitive Findings

1. **Governance architecture has almost no ROE effect at `1` contract scale.**
   - All three architectures land within roughly `±0.01pp` of baseline.
   - This is not “the wrong governance rule”; it is “the sleeve is too small for architecture choice to matter at the account level.”

2. **Regime-gating is actually the weakest of the three architectures.**
   - Phase B made `HIGH_VOL` collision look like the obvious block regime.
   - Phase C shows that those same periods are where `/ES` premium is richest.
   - Blocking them cuts off the best opportunities without delivering meaningful account-level protection at current size.

3. **SPAN breach events are real, frequent, and severe — but still mostly a monitoring problem at 1 contract.**
   - `82 / 158` trades experienced SPAN expansion beyond `1.5x`
   - max expansion reached `6.74x` (`~$138k`, `27%` NLV) during COVID-style stress
   - at `1` contract scale, that is serious enough to warrant visibility, but not yet evidence that a full governance architecture changes account-level outcomes enough to justify itself

## The Real Research Question, Reframed

Phase C changes the question from:

- “Which shared-BP governance rule should we implement now?”

to:

- “At what `/ES` scale does a formal governance framework become worth its own complexity?”

### Size Threshold Framing

| `/ES` Size | Approx BP Share of NLV | Practical Meaning | Governance Complexity Justified? |
|---|---:|---|---|
| `1` contract | `~4%` | small sleeve / mostly noise at book level | `No` |
| `3` contracts | `~12%` | meaningful but still secondary | `Maybe; simple rules only` |
| `5` contracts | `~20%` | real competition with SPX Credit | `Yes` |
| `10` contracts | `~40%` | dominant sleeve / major allocator problem | `Definitely` |

Current live posture sits on the **first row**.

## Integrated Research Conclusion

### What Should Not Be Done Now

Do **not** open a broad governance spec now for:

- dynamic budget architecture
- regime-priority entry blocking
- `/ES` vs SPX Credit full crowding framework

That would be correct theory at the wrong scale.

### What Should Be Done Now

At the current live scale, the correct narrow landing is:

> **SPAN post-entry visibility**

When `/ES` has an active live position, the platform should surface:

- static entry-time BP / SPAN proxy
- current estimated stressed SPAN
- the ratio between them

This is a **monitoring-layer** requirement, not a governance-layer allocator.

### Why This Is The Right Scope

- The risk is real (`82/158` stress expansions), so doing nothing is wrong
- But the architecture-level benefit is negligible at current size, so building a full rule framework now is overdesign
- The first real `/ES` live position in varying VIX conditions is more valuable for future calibration than another layer of simulation abstraction

## What Future Scale Would Change

If `/ES` expands toward `3–5+` contracts, the conclusion changes:

- then `Arch-2` (dynamic budget + stress correction) becomes the preferred candidate framework
- Phase A SPAN bands + Phase C architecture comparison already provide a credible design source for that future spec
- but it should be activated only after real Schwab data is available and the sleeve is large enough to matter

## Remaining Caveats

1. Phase B used an **SPX Credit proxy model**, not the final canonical engine path.
2. Phase C still evaluates architectures under modeled rather than broker-certified real-time Schwab behavior.
3. The first real `/ES` live position remains the highest-value calibration source for:
   - `mark` field unit
   - practical stressed-BP behavior
   - whether Phase A threshold bands need shifting

## Planner Implication

`Q012` is **not** ready for a full shared-BP governance spec at current size.

It **is** ready for a **narrow monitoring-spec** focused on one thing:

1. when `/ES` live position exists, surface **current estimated stressed SPAN vs static entry SPAN**

That spec should stay explicitly narrow:

- monitoring-layer only
- no entry gating changes
- no shared allocator
- no dynamic budget engine

## Explicit Out-of-Scope

This memo still does **not** reopen:

- `/ES` alpha research
- `/ES` entry logic redesign
- `/ES` Layer 1 / Layer 3 implementation
- broker write or automatic liquidation logic
- immediate full governance architecture implementation

## Recommendation

- Treat Phase A+B+C as sufficient to **shrink**, not widen, the implementation path
- Open only a **narrow DRAFT Spec for SPAN post-entry visibility**
- Defer the real governance-framework spec until:
  - `/ES` size expands materially (`3–5+` contracts), and/or
  - first real `/ES` live-position Schwab data has been observed and used for calibration
