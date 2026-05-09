# Q051 — `/ES` Performance Salvage Under Honest Assumptions Seed Memo

Date: 2026-05-08
Owner: Planner
Status: closed at current account scale

## Why Q051 Exists

The current `/es-backtest` surface now shows much weaker standalone performance than the original `/ES` research narrative implied:

- `Trend Filter ON — /ES Short Put 45d Δ0.20`
- Sharpe near `0.00`
- annualized return / ROE near `0%` or slightly negative

This is not obviously a UI bug. It is the result of the project having recently made the `/ES` line more honest and more production-comparable:

- stop semantics unified to `3.0x credit`
- sizing fixed to `1` contract
- `/ES` parameters unified in `strategy/es_params.py`
- current backtest surface uses hybrid actual-pricing logic where available

The correct next question is therefore not “why does the page look ugly?” but:

> Under the new honest assumptions, does the `/ES` line still contain a recoverable structural edge, and if so, which part of the original thesis is still worth saving?

## What Q051 Is

`Q051` is a **research-driven performance-salvage question** for the `/ES` strategy line.

It is intended to help Quant re-interpret the original `/ES` work now that the minimal production-comparable cell has become much weaker.

## What Q051 Is Not

`Q051` is **not**:

- a new `/ES` implementation Spec
- a reopening of `/ES` shared-BP governance (`Q012`)
- a broker/runtime maintenance task
- a portfolio allocator question (`Q050`)
- a generic “do more `/ES` alpha research” bucket

## Current Observed Problem

The currently surfaced `/ES` backtest result reflects the **minimal cell**, not the full historical three-layer thesis:

- `45 DTE`
- `Δ0.20`
- trend filter on
- `stop_mult = 3.0`
- `n_contracts = 1`

Planner direct checks on the current code path indicate that this minimal cell is indeed weak enough to take seriously:

- long-window annualized performance is slightly negative
- Sharpe is near zero or negative
- the page reading (`Sharpe 0.00`, `ROE -0.11%`) is directionally consistent with the current research code

## Original `/ES` Thesis vs Current Surface

The important distinction is:

- the **current page** shows the minimal Phase-1-like standalone cell
- the **original research** in `research/strategies/ES_puts` described a broader thesis including:
  - trend filter
  - DTE laddering
  - VIX leverage table
  - Layer 1 / Layer 3 framing
  - possible diversification value relative to SPX Credit

So the weak current page result most naturally means:

- the current **minimal cell** is weak
- it does **not yet prove** that the broader `/ES` thesis is dead

## The Narrow Research Question

`Q051` should answer:

1. Does the weak current result only invalidate the minimal `45d / Δ0.20 / 1-contract` cell?
2. Which part of the original `/ES` thesis still has the highest chance of carrying edge under the new honest assumptions?
3. If the line is salvageable, what is the most promising next axis?

## Candidate Salvage Axes

Quant should compare at least these four axes:

1. **DTE ladder revalidation**
   - Re-run the original ladder intuition under the new honest assumptions
   - Check whether a single-cell view is simply the wrong implementation shape

2. **Delta / DTE reselection**
   - Test whether `Δ0.20 / 45 DTE` is no longer the best point once stop and sizing are made production-comparable
   - Reasonable first scan:
     - delta: `0.15 / 0.20 / 0.25`
     - DTE: `30 / 35 / 45`

3. **Exit structure review**
   - Determine whether the current trio
     - `3.0x` stop
     - `10%` profit target
     - current gamma/expiry logic
   - is overly compressing the distribution

4. **Narrower regime gating**
   - Re-test whether `/ES` is better understood as an opportunistic sleeve than as a broad always-on production candidate

## Quant Initial Judgment

### One-Line Conclusion

**original thesis still alive but current cell is the wrong implementation**

The weak `/es-backtest` result should be taken seriously, but it only disqualifies the **current minimal cell** under the honest assumptions. It does **not** yet disprove the broader original `/ES` thesis.

## What The Weak Result Actually Invalidates

Quant's current judgment is:

- the current weak result is **real enough to take seriously**
- it invalidates the current:
  - `45 DTE`
  - `Δ0.20`
  - `1` contract
  - `STOP_MULT = 3.0`
  - single-slot implementation
- it does **not** yet invalidate:
  - DTE ladder effects
  - VIX leverage table effects
  - BSH / Layer 3 tail-payoff effects
  - low-correlation portfolio value relative to SPX Credit

### Why The Current Cell Looks Worse Than The Old Research

Two honest-parameter shifts matter:

1. **Stop semantics tightened**
   - `STOP_MULT` moved from `4.0` to `3.0`
   - this increases stop frequency and makes the distribution more realistic

2. **Production-comparable sizing shrank**
   - old research-side BP sizing implied about `~2.44` contracts on a `$500k` account
   - production-comparable mode is now fixed at `1` contract
   - this is the dominant performance drag on account-level ROE

So the current weak page result is best read as:

> at `$500k`, with `1` contract and `3.0x` stop semantics, the `45d / Δ0.20` single-slot implementation does not independently generate repeatable alpha

## What The Original Thesis Was Actually About

Quant's framing is that the original `/ES` thesis was never simply “a single naked-put cell should print strong standalone alpha.”

It was a broader three-layer idea:

- **Layer 1**: Long SPY / market beta
- **Layer 2**: short-put theta overlay
- **Layer 3**: BSH / tail protection

Under that framing, the meaningful potential alpha sources were:

1. trend filter as a risk-control gate
2. DTE laddering as a way to improve frequency / statistical stability
3. BSH payoff improving Sortino / tail survivability
4. low correlation vs SPX Credit as a portfolio-level diversification source

The current page only tests a narrow subset of that thesis.

## Final Closure

The original `/ES` thesis line is now closed at the current `$500k` account scale.

The final combined research conclusion is:

- the thesis is statistically valid only in its larger full-system form
- that full-system form is scale-dependent
- at the current account size it is not production-plausible
- the current `1`-contract `/ES` deployment should therefore remain a live-data / visibility / operational-calibration cell rather than an active ROE engine

This means:

- no further active thesis research should continue under `Q051`
- active ROE-expansion attention should redirect to `Q041`
- any future `/ES` work should be treated as a **new branch** under `Q052`, not as a continuation of this line

## Priority-Ranked Salvage Axes

### 1. First priority — re-run Phase 2 DTE ladder under the honest assumptions

This is Quant's highest-value next step.

Why:

- old Phase 2 was the first place where the bootstrap evidence became meaningfully positive
- it is the lowest-cost way to test whether the thesis survives once:
  - `STOP_MULT = 3.0`
  - `1` contract per slot
  - hybrid pricing
are enforced

Recommended rerun shape:

- five-slot ladder
- `[21 / 28 / 35 / 42 / 49]`
- `1` contract per slot
- `STOP_MULT = 3.0`

Interpretation:

- if this remains statistically positive, the thesis survives and the current page is simply the wrong implementation slice
- if this also fails, then the production-comparable constraints may have severed the thesis materially

### 2. Second priority — stop-level sensitivity

Quant recommends a research-side sensitivity scan of:

- `3.0`
- `3.5`
- `4.0`

not to overturn the live `3.0x` production rule, but to understand how much of the performance collapse comes specifically from the tighter stop.

This would clarify whether there is a known research/live gap that should be documented rather than ignored.

### 3. Third priority — delta / DTE reselection

Useful, but lower priority than ladder revalidation.

Good first scan:

- delta: `0.15 / 0.20 / 0.25`
- DTE: `30 / 35 / 45`

This should happen only if the Phase 2 rerun does not already resolve the question.

### 4. Deferred — opportunistic regime gating

This idea still has value, but Quant does **not** recommend starting here.

Reason:

- before Phase 2 is rerun, it is too early to collapse `/ES` into a narrow opportunistic sleeve
- `Q012 Phase C` already showed that HIGH_VOL is not obviously the wrong place to be; premium can be richest there

## Recommended Planning Posture

`Q051` is now beyond seed-only status, but still:

- research-only
- not ready for DRAFT Spec
- narrower than `Q050`
- orthogonal to `Q012`

The current correct next step is:

> re-run the original Phase 2 DTE ladder under the honest assumptions before opening any new `/ES` implementation scope

## Final Research Conclusion

### One-Line Conclusion

**The original `/ES` thesis is only still alive as a full-system hypothesis; the current `1`-contract production path is structurally disconnected from that thesis.**

### Three Core Conclusions

1. **The 1-contract live path and the original thesis are structurally different things**
   - The current production deployment (`1` contract per slot) is not a valid proxy for the original `/ES` thesis.
   - It is correctly reclassified as:
     - live data collection
     - visibility / monitoring
     - runtime semantics / operational calibration
   - This is consistent with `Q012 Phase C`, where architecture choice moved account-level ROE by only about `±0.01pp`.

2. **BSH economics are scale-dependent**
   - Estimated BSH annual cost is roughly `$10k`
   - At `1` contract × `5` slots, annual theta income is only about `$5k–$8k`
   - Therefore BSH is not a universal tail hedge for this line; it only becomes economically viable when dynamic leverage creates enough theta income to finance it.
   - This is a materially new research conclusion: BSH should not be treated as a generic modular add-on.

3. **Statistical significance is not reachable under the current honest scale**
   - `STOP = 3.0 / 3.5 / 4.0` all remain non-significant
   - `2`-contract diagnostics scale PnL and variance proportionally and do not fix the distribution-shape problem
   - Therefore the issue is not a tiny parameter miss; it is a structural high-variance / low-scale problem in the current naked-put path

## Full-Thesis Rerun Result

PM selected the former `Option B`, and the full-thesis rerun is now complete.

### One-Line Conclusion

**The thesis is validated only in its full-system form, and the next real blocker is leverage-table recalibration rather than further 1-contract salvage.**

### Full-System Result Summary

| Config | System Form | STOP | Bootstrap CI | Significant | AnnROE | Sortino |
|---|---|---:|---|---|---:|---:|
| A | P3 cost-only | 3.0x | `[+2, +343]` | Yes | `-0.26%`† | `-0.017` |
| B | P4 + BSH | 3.0x | `[-12, +404]` | No | `1.00%` | `0.018` |
| C | P4 + BSH | 3.5x | `[+31, +460]` | Yes | `1.26%` | `0.022` |
| D | P4 + BSH | 4.0x | `[+80, +515]` | Yes | `1.40%` | `0.025` |

† Config A is negative because it includes BSH cost without BSH payoff; this is a Phase-3 cost-only construct rather than the full thesis.

### Key Implications

1. The thesis **does validate statistically** in the full-system form.
2. BSH is economically viable **only at the larger dynamic-leverage scale**, not at the current `1`-contract production scale.
3. `STOP = 3.0` is a borderline threshold; `3.5` and `4.0` are the first clearly significant full-system configurations.
4. The real production blocker is no longer “does the thesis work?” but:
   - how to recalibrate the VIX leverage table for current SPX / SPAN levels
   - whether PM accepts the large worst-year risk

### Updated Planner Interpretation

The current research line no longer supports additional incremental patching of the `1`-contract cell.

The correct next step is also no longer another generic `/ES` salvage pass.

Instead, the next research gate is:

- **a narrow Tier 1–2 leverage-table recalibration study**
- focused on current SPX / SPAN levels
- with explicit peak-SPAN and worst-year constraints
