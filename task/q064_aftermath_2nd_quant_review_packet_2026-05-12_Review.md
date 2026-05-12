# Q064 Aftermath Routing — 2nd Quant Review

## Overall Verdict

**APPROVE WITH ONE REQUIRED PRE-SPEC TEST.**

我同意 First Quant 的核心结论：**current aftermath routing to V3-A IC HV should not remain the default. Evidence strongly favors reverting aftermath routing to BPS HV.** The evidence is directionally consistent across raw per-contract, equal-BP, and $/BP-day comparisons: V3-A uses much more BP, earns less absolute P&L, and only wins in a small subset of defensive cases. 

但我不建议直接写 SPEC 只做 blind revert。SPEC 前应补一个小测试：

> **Test BPS HV aftermath + VIX re-cross stop.**

如果这个 stop 能保留 BPS HV 的大部分收益，同时覆盖 V3-A 唯一有价值的 tail-protection scenario，那么 revert 结论会更干净。

---

# 1. Q1 — Counterfactual validity

## Verdict: **PASS**

P3 counterfactual 是合理的。用相同 aftermath entry dates 比较 V3-A 与 BPS HV，正好回答当前问题：

> Given the same aftermath timing signal, which structure should receive the trade?

这不是在重新评估 aftermath detection，也不是重新选择 entry dates。Q064 的问题是 **routing**，所以 same-date structure substitution 是正确方法。

关键条件是：如果没有 V3-A override，这些日期是否本来会走 BPS HV。根据 packet 描述，aftermath logic 只是在 `is_aftermath() + HIGH IV + HIGH_VOL/BEARISH/NEUTRAL` 情况下从 standard BPS HV 改路由到 V3-A。因此 BPS HV 是正确 counterfactual。

**Caveat:** 这仍然是结构 counterfactual，不是 full-system rerun。SPEC 前最好确认 selector route tree 中没有其他 guardrail 会在移除 V3-A 后把部分 trade 改成 Reduce/Wait 或其他 strategy。但从 packet 逻辑看，BPS HV 是 valid counterfactual。

---

# 2. Q2 — Equal-BP scaling

## Verdict: **PASS**

P4 的 per-trade BP normalization 是公平的。它回答的是：

> For each trade opportunity, if both structures consume the same BP budget, which one produces better payoff?

这正是 routing decision 需要的 capital-efficiency comparison。

P4 结果非常强：equal-BP 后 V3-A avg P&L 比 BPS HV 低 `57%`，median 低 `63%`，$/BP-day 低 `63%`，total PnL 只有 `$15.5k` vs BPS `$36.4k`。这不是边际差异。

Portfolio-level scaling 大概率不会改变结论。因为 V3-A 每笔 BP 更高，实际整数合约环境下只会更不利：0.52 fractional contract 在真实账户里无法交易，如果 round to 1 contract，就又回到更高 BP usage。packet 已经正确指出这一点。

---

# 3. Q3 — Sample size adequacy

## Verdict: **PASS FOR PRE-SPEC; CAUTION FOR PRODUCTION CLAIM**

`n=15` 很小，不能宣称统计显著。但对于这个 routing decision，我认为已经足够支持 opening a revert SPEC，原因是：

1. 结果 across frames 一致：P3 raw、P4 equal-BP、$/BP-day 都指向 BPS HV。
2. 差距很大，不是 5–10% 的噪声，而是 V3-A equal-BP P&L 大约只有 BPS 的 42.5%。
3. 结构解释清楚：V3-A 的 call wing 太宽，导致 BP 接近 BPS 的 1.9×，但没有带来对应收益。
4. V3-A 的优势集中在少数 defensive cases，不是主分布优势。

所以我不会要求 paper trading 才能 action。Aftermath routing 是 low-frequency but repeated production logic；如果 evidence shows current route systematically wastes BP, reverting is justified.

**但 SPEC 应避免过度表述。**
建议措辞：

> Evidence supports reverting to BPS HV as default aftermath routing, subject to a small VIX re-escalation stop test and post-change shadow monitoring.

---

# 4. Q4 — Missing failure modes

## Verdict: **PASS WITH ONE WATCHPOINT**

你列的潜在场景合理，但我认为没有一个足以推翻 P3/P4 结论。

### (a) Prolonged VIX re-escalation during hold

这是 V3-A 最可能胜出的场景。V3-A 的 100% win rate 和 near-zero worst trade 说明它对 reversal / re-escalation 有防御价值。

但它不是免费保险：为了这类少数场景，V3-A 在大多数 aftermath trades 上牺牲 57–63% capital efficiency。这种 tradeoff 不划算。更合理做法是测试 BPS HV + VIX re-cross stop，而不是常态性使用宽 call-wing IC。

### (b) Very deep aftermath with VIX >35 entry

当前 `is_aftermath()` 已排除 `VIX >= 40`，且 aftermath median VIX 约 26。非常深 aftermath 样本可能少，但这不支持 V3-A default。更合理是如果 VIX entry >35，route to Reduce/Wait or smaller BPS, not necessarily V3-A.

### (c) Post-2022 rate regime

可能存在，但目前没有证据支持 V3-A 更优。2022 rate regime 也更可能惩罚 BP-inefficient structures。除非 forward data 显示 call-side premium consistently pays for wide call wing，否则不应保留 V3-A default。

**Watchpoint:**
Aftermath + sharp bear-market rally could make call side relevant. But if the call wing is average 195 pts wide, it behaves more like expensive unused margin than efficient protection in most cases.

---

# 5. Q5 — VIX stop alternative

## Verdict: **REVISE — quantify before SPEC**

我认为 **VIX re-cross stop should be tested before SPEC is written**.

First Quant 的 intuition 是对的：V3-A 的主要优势是 tail protection during VIX reversal. If BPS HV + VIX re-cross stop can capture most of that protection, BPS HV becomes clearly superior.

但 stop threshold `VIX > 28` 不能凭直觉写进 SPEC。它需要一个 narrow test：

```text
Candidate BPS aftermath stop:
- close BPS HV if VIX re-crosses 28 during hold
- alternative thresholds: 28 / 30 / entry_vix + 10%
- compare vs no-stop BPS HV and V3-A
```

Minimum metrics:

* total PnL
* avg PnL
* worst trade
* $/BP-day
* number of stop fires
* how many BPS losing trades avoided
* how many winning trades prematurely cut

This is not a big research branch. It is a **pre-SPEC hygiene test**.

If stop test fails, still revert to BPS HV may be justified, but SPEC should not claim VIX stop can replicate V3-A protection.

---

# 6. Q6 — Structural diagnosis: is asymmetric call wing the core problem?

## Verdict: **PASS, but do not delay revert for symmetric IC**

Yes, the asymmetric call wing appears to be the core design problem. V3-A's average call wing is 195 pts, 3.4× the put wing, and PM BP is governed by the larger wing. That means the call side dominates BP, while the aftermath thesis is mostly about put-side risk after vol retreat.

A symmetric IC might perform better than V3-A. But I do **not** think it must be tested before reverting to BPS HV.

Reason:

* The current production question is whether V3-A should remain. Evidence says no.
* A symmetric IC is a new candidate, not a defense of current V3-A.
* Testing symmetric IC could become another branch and delay a clear fix.
* If the goal is aftermath routing efficiency, BPS HV is the clean baseline; symmetric IC can be a future research note.

My recommendation:

> Revert default to BPS HV. Optionally open a later low-priority Q for "aftermath symmetric IC variant," but do not block revert SPEC.

---

# Final Recommendation

## Decision

**Proceed toward SPEC to revert aftermath routing from V3-A IC HV to BPS HV, but first run a narrow BPS HV + VIX re-cross stop test.**

### Required before SPEC

1. Confirm selector counterfactual: removing V3-A override routes those 15 cases to BPS HV, not Reduce/Wait.
2. Run VIX re-cross stop test on same aftermath sample:

   * no-stop BPS HV
   * VIX > 28 stop
   * VIX > 30 stop
   * maybe VIX > entry_vix × 1.10 or entry_vix + 3
3. Report whether stop materially reduces worst trade without killing most P&L.

### Not required before SPEC

* Symmetric IC test
* Full redesign of aftermath detection
* New trigger thresholds
* Paper trading before reverting

---

# Final Verdict

**APPROVE WITH ADJUSTMENT — evidence supports BPS HV revert; quantify VIX stop before SPEC.**

Formal wording:

> Q064 provides sufficient evidence that V3-A IC HV is BP-inefficient as the default aftermath route. Equal-BP comparison shows V3-A earns materially less than BPS HV while consuming nearly twice the BP in raw routing. The likely structural cause is the oversized call wing, which creates expensive protection that is only valuable in a minority of reversal cases. Default aftermath routing should revert to BPS HV, but a narrow pre-SPEC test should evaluate whether a VIX re-cross stop can preserve the limited defensive benefit V3-A historically provided.
