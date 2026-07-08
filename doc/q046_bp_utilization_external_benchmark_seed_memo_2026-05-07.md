# Q046 — External Benchmarking of BP Utilization and Account-Level Deployment Efficiency

> **⚠ SUPERSESSION STAMP (2026-07-07, PM-批准 reaudit)**
> "把平均 BP 使用率推向外部 20-30%" 的目标句**作废**:Q081 (2026-06-01) 实测账户为
> cash-bound + BP-rich,BP 利用率是输出不是目标;外部对标账本多以 BP 为资本约束
> (Reg-T/naked 账本),与本账户"NLV 养 beta + 期权做 overlay"结构不可比。
> **仍然有效**:机制排序 C(扩覆盖)>A(加 sizing)、per-trade vs book-level 口径校正。
> 注意:本 memo 指向的 Q041 扩覆盖轴,其 T2 现落地为 cash-secured——消耗稀缺现金而非
> 富余 BP,资源错配详见 `task/bp_utilization_thread_reaudit_2026-07-07.md` §3.1 与
> `task/spec111_review_2026-07-07.md` §4。

Date: 2026-05-07
Status: seed / research entry
Owner: Planner / Quant Researcher

## Trigger

PM raised a high-importance account-level question after `SPEC-084` went live: even after the joint `bp_target` lift, the system still appears materially under-deployed at the portfolio level. Internal `Q045` research lifted average BP utilization only to roughly `15.9%`, while external practitioner discourse often references portfolio-level short-premium usage closer to `20%–30%` or higher.

The question is not whether to immediately raise live sizing again. The question is whether our current book is still structurally under-deployed relative to mainstream short-premium practice, and if so, which path should be studied next:

- increase per-strategy sizing further,
- relax concurrency / overlap constraints,
- broaden the strategy / underlying set,
- or reconsider regime-level ceilings.

## Why This Matters

This directly affects the project’s current top-level objective:

- **reasonably maximize account-level ROE under explicit risk guardrails**

`Q045` already showed that the main bottleneck is not purely local rule efficiency; it is **book-level deployment efficiency**. If external benchmark practice says a mature short-premium book often works at materially higher average BP than our current `~16%`, this becomes a first-order research question, not a side note.

## Current Internal Baseline

From `Q045`:

- baseline time-weighted avg BP usage: `11.09%`
- post-`SPEC-084` / J3 expected avg BP usage: `~15.93%`
- peak BP after J3: `43%` (still within `HIGH_VOL ceiling = 50%`)
- major remaining gap: roughly `19pp` of idle BP even after the J3 lift

This means the current system is **still conservative at the portfolio level**, even after the largest ROE optimization so far.

## External Benchmark Scan — Initial Takeaways

Initial external scan suggests the commonly cited `~30%` figure is **not crazy**, but it usually refers to **portfolio-level buying power in use**, not to a single-trade target.

### Practitioner / Educational Sources

1. **tastylive — allocation-throughout-the-years framing**
   - Short-premium portfolio allocation is often discussed in a regime-aware `25%–50%` total buying-power-at-work framework.
   - A `~30%` working allocation appears as a normal example in elevated-volatility environments.
   - Source: https://www.tastylive.com/shows/market-measures/episodes/allocation-throughout-the-years-04-14-2022

2. **tastylive — trading-too-big framing**
   - Warns that large account-level allocation and concentration, not just strategy expectancy, drive tail-risk failure.
   - `30%`-scale exposure can already be “too big” depending on structure and concentration.
   - Source: https://www.tastylive.com/shows/best-practices/episodes/trading-too-big-04-04-2016

3. **Option Alpha — maximum capital usage framing**
   - Advises retaining substantial dry powder; practical reading is often “do not deploy everything, keep ~40–50% cash available.”
   - This is consistent with a total active options allocation range that can still be materially above our current average usage.
   - Source: https://optionalpha.com/lessons/maximum-capital-usage

### Community Evidence

Reddit / ThetaGang discussions are noisier, but the central band is consistent:

- common portfolio-margin usage anecdotes cluster around `20%–30%` in normal conditions,
- `30%+` in higher-volatility windows,
- and many users still treat `50%` as a psychological or risk-management upper zone rather than a default target.

Representative threads:
- https://www.reddit.com/r/thetagang/comments/pl1jup/what_of_your_options_buying_power_do_you/
- https://www.reddit.com/r/thetagang/comments/1bqvptu/portfolio_margin_usage/
- https://www.reddit.com/r/thetagang/comments/so2mji/what_percentage_of_your_buying_power_do_you_have/
- https://www.reddit.com/r/options/comments/10lxf23/tastytrade_capital_allocation_guidelines/

## Important Framing Correction

This research must **not** confuse:

- **per-trade BP target** (`bp_target_normal = 15%`)
with
- **portfolio-level average BP usage** (`~15.9%` post-J3)

These are different layers.

The external benchmark question is primarily about **book-level deployment**, not just single-position sizing.

## Core Research Question

Under our current strategy matrix and explicit risk guardrails, what is the most robust path to move average account-level BP usage from `~16%` closer to the external-practice range (`~20%–30%`), without unacceptable deterioration in:

- Sharpe,
- worst-trade / tail outcomes,
- concentration,
- concurrency stress,
- or operational complexity?

## Candidate Mechanism Buckets

The research should explicitly compare at least four mechanism families:

1. **Further sizing of existing strategies**
   - e.g. BCD / IC / BPS / IC_HV beyond current J3

2. **Concurrency / overlap relaxation**
   - same-strategy overlap or broader concurrent-position rules

3. **Broader strategy / underlying coverage**
   - especially `Q041` as the diversification / idle-BP capture axis

4. **Ceiling changes**
   - NORMAL / HIGH_VOL ceiling reconsideration

These should be treated as separate mechanisms, not collapsed into “make the account bigger.”

## Suggested Quant Scope

Recommended next study shape:

- **Tier 2 or light Tier 3** depending PM/Planner judgment
- first deliverable should be a **benchmark + mechanism map**, not a new Spec candidate

### Phase 1

External benchmark normalization:
- distinguish per-position sizing vs total book utilization
- distinguish Reg-T vs PM
- distinguish defined-risk, CSP, and naked-short frameworks

### Phase 2

Internal comparison pack:
- baseline
- post-`SPEC-084`
- current idle-day / single-strategy-day / overlap-day structure

### Phase 3

Mechanism ranking:
- which family is most likely to move average BP usage toward external norms with the lowest tail-risk cost?

## Explicit Non-Goals

This entry does **not** authorize:

- immediate further live sizing increases
- retroactive resizing of existing real trades
- ceiling changes
- new Spec drafting
- re-opening `SPEC-084`

## Recommended Next Step

Open a dedicated Quant research task on:

- **external BP-utilization benchmark vs current internal deployment efficiency**

The output should answer:

1. Is our current `~16%` average BP usage unusually low relative to relevant short-premium practice?
2. If yes, which mechanism family is the most promising next axis?
3. Which axis should be researched first, and which should remain deferred?


## Quant Conclusion (2026-05-07)

### One-line conclusion

Our post-`SPEC-084` book-level BP usage of `~16%` looks lower than the raw external `25%–30%` headline, but once normalized into a PM defined-risk framework the real gap compresses to roughly `~5–10pp`, not `15pp+`; the next mechanism worth promoting is **C: broader strategy / underlying coverage**, because only C can directly attack the `17%` fully idle days.

### Key Normalization Result

The headline comparison must distinguish:

- per-trade BP target,
- portfolio-level average BP in use,
- Reg-T vs PM,
- and defined-risk vs CSP / naked-short books.

Under a PM defined-risk lens, our current `~15.9%` average BP usage is not dramatically below a conservative-to-neutral external peer; it is only moderately low. The stronger under-deployment gap shows up relative to more aggressive PM books, not to the entire practitioner universe.

### Mechanism Ranking

#### A — More sizing of existing strategies
- Can push average BP somewhat higher, but `Q045` already harvested most of this value.
- Further increases run into ceiling cliffs and larger tail losses.
- Best viewed as deferred unless paired with a broader ceiling decision.

#### B — More concurrency / overlap
- Can increase average BP on single-strategy days, but does nothing for fully idle days.
- Carries concentration / correlation risk and overlaps conceptually with `Q036`-style logic.
- Deferred.

#### C — Broader strategy / underlying coverage
- **Primary recommendation.**
- Only mechanism that can directly address the `17%` fully idle days.
- Improves deployment by diversification rather than by concentration.
- Already has a live implementation carrier: `Q041` paper trading.

#### D — Higher ceilings
- Enabler only, not a standalone axis.
- Does not raise average BP by itself.
- Only meaningful if A or B is later promoted.

### Practical Planning Result

- `Q046` should be treated as a **benchmark + mechanism map completed**, not as a new Spec candidate.
- `Q041` should be re-framed from “paper-trading support / overlap-validation branch” to **the primary post-`Q045` account-level deployment-efficiency axis**.
- No new live sizing change, no ceiling change, and no `SPEC-084` reopening is recommended from this result alone.

### Recommended Next Step

Keep `Q041` on its current paper-trading / overlap-monitoring track, but elevate its planning status: after `4–8` weeks of real paper-trading accumulation, run a focused **BP-fill quantification** asking how many percentage points of average BP usage `Q041` actually adds over the post-`SPEC-084` baseline.
