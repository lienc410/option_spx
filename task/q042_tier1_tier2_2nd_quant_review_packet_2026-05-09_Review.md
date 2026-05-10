# Q042 Tier 1 + Tier 2 — 2nd Quant Review

## Overall Verdict

**APPROVE WITH ADJUSTMENTS.**

我认可 Q042 从 seed 晋升到 Tier 3 / DRAFT Spec 前的总体方向：**long-premium directional overlay 是当前 short-premium 主策略的合理补充候选**，Tier 1 和 Tier 2 的研究链条总体 sound，winner config 也有清晰依据。

但我不建议直接把当前 winner config 原样写成 DRAFT Spec。需要三个关键调整：

1. **dd12 + MA50 reclaim 可以作为 lead trigger，但 dd15 naive 应作为 benchmark / fallback 同步保留。**
2. **DTE30 不应无条件定为最终 winner；Tier 3 必须加入 DTE60/90 的 timing-tolerance 对比。**
3. **Q042 sleeve cap 应从 20% 下调到 5–10% 初始治理 cap；20% 只应作为 future scale-up upper bound，不应进入 MVP。**

---

# Q1 — P1 trigger grid：dd12 + MA50 reclaim vs dd15 naive

## Verdict: **PASS with benchmark requirement**

我同意把 **dd12 + MA50 reclaim** 作为 lead trigger。理由是：

* 12m median `+42.7%` 明显强；
* 3m median `+11.0%`，说明它不是只靠远期恢复；
* OOS split `88.2% / 95.8%` 方向稳定；
* 它避免了 dd20 那种 falling-knife risk；
* 它更接近 Q042 的真实逻辑：**不是简单抄底，而是 drawdown 后等待技术恢复确认。**

但我不建议完全淘汰 dd15 naive。原因：

* dd15 naive 样本 `n=192`，是 dd12+reclaim 的 4.7 倍；
* 12m positive `97.9%`，更稳定；
* 不依赖 30-day reclaim wait，少一个 path dependency；
* 如果 Tier 3 实际期权收益显示 dd12+reclaim 的 DTE30 timing 太窄，dd15 naive 可能反而更稳。

**结论：**

> dd12 + MA50 reclaim 是 lead candidate；dd15 naive 是 required benchmark，不是 finalist replacement。

Tier 3 / DRAFT Spec 应明确同时报告：

```text
Lead: dd12 + MA50 reclaim
Benchmark: dd15 naive
Secondary benchmark: dd10 + MA50 reclaim
```

---

# Q2 — P2 structure：DTE30 是否被 $/BP-day 过度偏爱？

## Verdict: **REVISE**

这是我最重要的 challenge。

`$/BP-day` 对一个 capital-efficient overlay 很有价值，但它天然偏向短 DTE。对 Q042 这种 **directional recovery overlay**，不能只优化 capital-time efficiency。还必须看：

* 是否抓住 recovery window；
* 是否对 entry timing error 有容忍度；
* 是否在二次探底 / 横盘后仍保留 convex exposure；
* 是否对 1–5 天 entry drift 敏感。

DTE30 winner 的问题是：
它可能在 `$ / BP-day` 上胜出，但在 **path tolerance** 上过窄。

Q042 的 trigger 是 drawdown + reclaim，不是精确底部预测。即使 MA50 reclaim 成功识别 recovery，市场也可能：

* reclaim 后回踩；
* 30 天内横盘；
* 60–90 天后才真正恢复；
* 先下跌再上涨。

这些路径下，DTE30 可能因为 timing window 太窄而失败，而 DTE60/90 可能更适合组合目标。

**我建议 Tier 3 必须做 DTE sensitivity，不应默认 DTE30。**

最低要求：

```text
Same trigger: dd12 + MA50 reclaim
Same structure: ATM/+5% call spread
Test DTE: 30 / 60 / 90
Metrics:
- total PnL
- median / mean PnL per trade
- win rate
- max consecutive losses
- $/BP-day
- account-level ROE
- worst 5 trades
- 30d / 60d / 90d forward SPX return alignment
```

我的先验判断：

* DTE30 可能是 efficiency winner；
* DTE60 可能是 production winner；
* DTE90 可能是 robustness benchmark。

所以 Q2 的结论是：

> DTE30 可以进入 Tier 3，但不能直接进入 DRAFT Spec final parameter。DTE60/90 必须作为 path-tolerance candidates 一起测试。

---

# Q3 — Ratio 1×2 是否值得重看？

## Verdict: **REJECT as finalist; keep research-note only**

我不建议 ratio 1×2 进入 finalist set。

原因不是 BP proxy 一个问题，而是结构本身和 Q042 目标冲突。

Q042 的价值是：

> defined-risk directional convex sleeve。

但 ratio 1×2 本质会引入：

* short extra upside convexity；
* runaway rally 下的 undefined / hard-to-govern tail；
* PM margin highly path-dependent；
* 解释复杂；
* 和"简单、有限损失、组合补充"的定位不一致。

你说 ratio worst-case 被截断到 `-$30`，但这是模型/假设下的结构表现，真实 PM margin 和实盘路径可能完全不同。尤其在 Q042 触发后，如果出现 sharp recovery / melt-up，short 2× OTM calls 的风险管理会变成新的问题。

**结论：**

> Ratio 1×2 不应作为 MVP / DRAFT Spec finalist。
> 它可以保留为 future research note，但不应阻塞 call spread route。

Q042 的第一版应该保持 **net debit, defined-risk, capped-loss, low-governance complexity**。

---

# Q4 — P3 BP gate：20% cap 是否太高？

## Verdict: **REVISE**

我同意 P3 的发现：当前 main strategy 在 Q042 trigger dates 的 BP 很低，所以 `60% - main_bp%` gate 当前 0% firing 是真实结果。Tier 1 "HIGH_VOL overlap = BP collision severe" 的初始 framing 已被正确修正。

但我不赞成 MVP 用 **20% account cap**。

理由：

1. Q042 是新 long-premium sleeve，sample 只有 `n=41` lead trigger。
2. Long call spread 最大损失是 100% debit；20% sleeve 理论上就是 20% account loss tail。
3. 实际 entry frequency 约 2.2 trades/year，不需要 20% cap 来表达 edge。
4. 20% cap 会让未来 scale-up 太容易，治理上不够保守。
5. 主策略和 Q041/Q036 的部署状态仍会变化，未来 BP envelope 未必和现在一致。

我建议：

```text
MVP per-entry size: 0.5%–1.0% account
MVP sleeve cap: 5%
Tier 3 stress cap: 10%
20%: research-only future upper bound, not MVP governance cap
```

更具体：

* 初版 DRAFT Spec：**1% per entry, 5% sleeve cap**
* 若 Tier 4 / live paper trading 显示稳定，再考虑 10%
* 20% 不进入初始 governance

**结论：**

> Gate can remain as governance backstop, but absolute cap should be materially lower for MVP.

---

# Q5 — Tier 3 unknowns 是否够？是否缺第 7 项？

## Verdict: **REVISE — add execution timing / trigger-to-fill drift as required unknown**

你列的 6 个 unknowns 大体合理：

1. Live SPX chain pricing
2. Ratio margin reality check
3. Re-trigger spacing
4. Exit rule
5. SPX vs XSP
6. Account-scale activation threshold

但至少缺一个必须项：

## 7. Trigger-to-execution timing / fill convention

这是结构性重要项，不是实现小细节。

当前 trigger 是：

```text
SPX close <= dd threshold
within 30 days first close > MA50
```

但交易执行可能是：

* same close impossible unless signal computed before close；
* next open；
* next close；
* next day mid；
* alert after EOD, execute next morning。

对 DTE30 call spread，1 天 entry drift 很可能很重要，尤其在 drawdown-reclaim 后市场 gap up/down 时。

Tier 3 必须测试至少：

```text
Entry:
- next open
- next close
- next day VWAP proxy / midpoint if available
```

如果没有 intraday data，至少要用 daily proxy：

```text
T signal close price
T+1 open proxy
T+1 close proxy
```

这比税务、FOMC blackout 更重要。

---

## 其他可选 unknowns

### Tax / wash sale

不是 Tier 3 blocker。可以写入 caveat，但不应阻塞 spec。

### FOMC / earnings blackout

对 SPX-level 30D overlay，不是首轮 blocker。若未来发现 event clustering，再处理。

### Correlation with main-strategy directional bias

值得加入 portfolio appendix，但 P3 BP overlap 已覆盖一部分。建议作为 Tier 3 metric，而非 new unknown。

### Gap after trigger

这其实归入 **trigger-to-fill drift**，必须纳入。

---

# Q6 — Hidden failure mode 是否遗漏？

## Verdict: **PASS with two additions**

你列出的 failure modes 基本完整。由于它是 debit call spread，理论最大损失就是 debit paid，不存在 naked-margin 爆炸，也没有 dividend assignment 问题（如果是 SPX/SPXW 欧式现金结算，更没有 early assignment）。

但我建议补两个 failure modes：

---

## Failure Mode 1 — Vol crush + delayed recovery

你写了 sideways grinding，但要更明确：

> trigger fires during elevated IV; SPX does not fall further, but recovery is slow; IV crush + theta decay kills DTE30 spread before directional move arrives.

这不是普通 sideways，而是 Q042 的核心风险之一。因为策略 entry 通常在 HIGH_VOL after drawdown，long premium 的成本可能被高 IV 抬高。即使方向最终对，DTE30 也可能先亏完。

这正是我在 Q2 要求 DTE60/90 对比的原因。

---

## Failure Mode 2 — Repeated small losses in multi-leg bear market

如果 secular bear / prolonged chop 中多次 dd12 + reclaim 触发，每次 call spread 都亏 1%，单笔 capped risk 没问题，但 sequence risk 可能显著。

你提到 5 consecutive losses = -5%，这个是对的，但 Tier 3 应正式输出：

```text
max consecutive Q042 losses
worst rolling 12m Q042 sleeve loss
worst rolling 24m Q042 sleeve loss
```

对 long-premium sleeve 来说，sequence bleed 比单笔 blow-up 更真实。

---

# REVIEW_TEMPLATE §6.1 applicability

同意：short-premium 标准检查不直接适用，因为 Q042 是 net debit / long-premium spread。

但有三个 adapted checks 必须保留：

1. **execution drift sensitivity** — 必须，不可豁免；
2. **scale / sleeve cap** — 必须；
3. **stress-capital equivalent** — 用 max sleeve loss / consecutive loss 而不是 margin expansion。

我不同意完全豁免 execution drift。
因为 Q042 虽然是 daily-close mechanical trigger，但现实执行仍是 trigger 后下一个可交易时点，DTE30 对 timing 很敏感。

---

# Final Recommendation

## Proceed to Tier 3 / DRAFT Spec preparation, but with required revisions.

### Approved

* Q042 direction is valid.
* Call spread > LEAP / ratio as MVP structure is defensible.
* dd12 + MA50 reclaim is a good lead trigger.
* BP-stacking gate is currently inert but worth keeping as governance backstop.
* Ratio 1×2 should not block progress.

### Required adjustments before DRAFT Spec

1. Keep `dd15 naive` as required benchmark.
2. Add DTE `30 / 60 / 90` comparison before locking DTE30.
3. Reduce MVP sleeve cap from `20%` to `5%`, with `10%` as future scale-up review level.
4. Add execution timing / trigger-to-fill drift as Tier 3 unknown.
5. Add sequence-loss metrics: max consecutive losses, worst rolling 12m / 24m sleeve loss.
6. Treat ratio 1×2 as research-note only, not finalist.

---

# Final Verdict

**APPROVE WITH ADJUSTMENTS — Q042 should proceed, but not with the current winner config locked.**

正式表述：

> Q042 is a valid long-premium directional overlay candidate and deserves Tier 3 / DRAFT Spec work. The lead thesis — dd12 + MA50 reclaim followed by a defined-risk call spread — is sound. However, the current winner config over-optimizes $/BP-day and may understate timing-window risk. Tier 3 must compare DTE30/60/90, retain dd15 naive as a benchmark, lower the initial sleeve cap to 5%, and explicitly test trigger-to-fill execution drift before PM receives a DRAFT Spec.
