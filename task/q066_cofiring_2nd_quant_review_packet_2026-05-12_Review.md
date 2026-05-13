# Q066 Aftermath vs Q042 Co-firing — 2nd Quant Review

## Top-line verdict

**PASS WITH CAVEAT — 接受"保持双 addon，不合并、不竞争"的结论；不要求立即启动 PnL correlation 研究。**

Q066 的 day-level overlap、event-level overlap、signal-space 差异和 Greek 方向差异，已经足够支持当前 PM 决策：**Aftermath / SPEC-064 和 Q042 不应合并，也不应互相淘汰。** 但我会调整措辞：这不是严格意义上的"portfolio risk fully hedged / 完全正交"，而是：

> **两个 addon 的触发空间高度不重叠，收益来源和 Greek 方向不同，因此当前不应合并；但 co-fire 场景下仍存在同向亏损路径，需作为 future monitoring，而不是当前 blocker。**

---

# Q7.1 — ±5 TD co-firing window 是否合理？

## Verdict: **PASS**

±5 TD 是合理的 first-pass co-firing 定义。原因是：

* Aftermath window 平均只有约 5.8 calendar days；
* Q042-A 是 30-DTE call spread，入场后前几天的方向和 IV 变化最关键；
* 如果两个 addon 在 ±5 TD 内触发，才更像"同一交易事件 / 同一风险簇"。

如果扩大到 ±10 TD，co-fire 比例会上升，但语义会改变。那不再是"是否同时触发"，而是：

> 是否属于同一个 broader stress / recovery cluster。

所以 ±10 TD 不会推翻"两个信号不重复"的结论，只会说明它们有时处在同一个宏观波动事件附近。这个是正常现象，不代表应合并。

我的建议：

```text
Primary co-fire metric: ±5 TD
Secondary cluster metric: ±10 TD, monitor only
```

不需要因为 ±10 TD 可能更高就重开结论。

---

# Q7.2 — Sample size adequacy

## Verdict: **PASS for Q042-A; REVISE wording for Q042-B**

### Q042-A

Q042-A 有 35 个 events，19 年样本下虽然不大，但足够支持方向性判断：

* 26 / 35，即 74% 与 aftermath ±5 TD 异步；
* day-level overlap 只有 0.9%；
* aftermath windows 视角下，只有 13 / 90 与 Q042-A ±5 TD 配对。

这些数字合在一起，足够说明：

> Q042-A 不是 aftermath 的重复表达。

### Q042-B

Q042-B 只有 5 个 events，4 / 5 co-fire 的 80% 不能作为强结论。这里必须明确标注：

> Q042-B co-firing ratio is unrobust due to N=5.

但这不影响整体"保持双 addon"结论，因为 Q042-B 是极低频 sleeve，且它的逻辑是深 drawdown + MA10 reclaim，和 aftermath 的 VIX structure 仍然不是同一个触发器。

建议在 memo 中把 Q042-B 改写为：

```text
Q042-B has high observed co-fire with aftermath in this sample, but N=5 is too small for stable inference. Treat B as "monitor as sample grows," not as evidence of redundancy.
```

---

# Q7.3 — 是否存在叠加风险场景？

## Verdict: **REVISE — add explicit co-loss scenario**

是的，存在同向亏损路径，必须写清楚。

最重要的场景是：

> Aftermath IC 入场后，VIX 没有继续 mean revert，而是再度上行；同时 SPX 继续下跌。
> 结果：Aftermath broken-wing IC 的 put side 受损，Q042 long call spread 也可能归零。

这不是理论小概率；它是一个真实 failure mode：

```text
VIX peak → VIX off-peak → aftermath IC enters
SPX drawdown / rebound signal → Q042 enters
then second-leg selloff:
    VIX re-expands
    SPX breaks lower
    IC put-side loses
    call spread expires worthless
```

在这个路径下，Greek "反向"并不会保证 hedge。原因是：

* Q042 long vega 可能帮一部分 IV expansion；
* 但如果 SPX 下跌足够多，call spread delta / intrinsic 损失会主导；
* Aftermath IC put wing 也可能受损；
* 两者在 PnL 上可以同向亏损。

所以我不同意把 co-fire 风险描述成"天然 partial hedge"。更准确是：

> Greek directions reduce some dimension of risk, but not all path risk. In a second-leg selloff, both addons can lose.

这不要求合并或关闭，但应作为 portfolio failure mode 记录。

---

# Q7.4 — Greek "partial hedge" 是否真实？

## Verdict: **REVISE wording**

Greek 方向相反这个论证是有价值的，但不能过度解释。

我同意：

* Aftermath IC：short vega / short gamma / theta positive；
* Q042 call spread：long delta / long gamma / long vega / theta negative；
* 方向上它们不是同一个 trade。

但我不同意把这直接等价为：

> portfolio-level hedge.

更准确应写成：

> **Greek sign orthogonality supports non-redundancy, but does not guarantee PnL hedge effectiveness.**

原因：

* vega exposure 的 strike location 不同；
* gamma profile 不同；
* Q042 的 long vega 对 SPX 下跌时的保护有限，因为 call spread delta 受损；
* IC 的 short vega 和 short gamma 在 adverse move 下会非线性扩大；
* 两个 addon 的 notional / BP / premium size 不同，不能只看符号。

所以 Greek 论证可以支持"不重复"，但不足以支持"co-fire 风险自然缓和"。

建议把文档中 "partial hedge" 改为：

```text
Greek directions are opposite and therefore the two sleeves are not mechanically redundant. However, Greek sign offset is not a reliable hedge claim because magnitude and strike localization differ.
```

---

# Q7.5 — 未做 PnL correlation 是否 fatal flaw？

## Verdict: **NOT FATAL**

不是 fatal flaw。

本次 PM 的问题是：

> 是否两个 addon 功能重复，是否应合并或淘汰一个？

对这个问题，触发频率 + signal space + payoff structure + Greek direction 已经足够支持"不合并"。PnL correlation 是更高阶 portfolio risk 问题，不是当前 decision blocker。

但 PnL correlation 是 future nice-to-have，尤其在两个条件下值得做：

1. Q042 sleeve 进入实际 paper trading / active deployment；
2. Q042-B 样本增加，或者 co-fire 事件显著增多；
3. PM 准备提高 Q042 sleeve cap；
4. Aftermath / Q042 在同一周同向亏损出现 live evidence。

所以我建议不启动 Q067 作为必做项，但加入 standing monitoring：

```text
If co-fire count increases or Q042 sleeve scales above initial cap, run co-fire PnL attribution / correlation study.
```

---

# Q7.6 — Final recommendation

## Verdict: **A — 接受保持双 addon，不需 PM 进一步操作**

我推荐：

> **A. 接受"保持双 addon"结论，不合并、不竞争；同时补充 co-loss failure mode 与 Greek wording caveat。**

不建议 B 立即启动 Q067。原因：

* day-level overlap 只有 0.9%；
* Q042-A 74% 异步；
* aftermath windows 86–93% 没有 Q042 配对；
* addon 结构和 Greeks 确实不同；
* BP cap 已有机制化处理。

这足以支持 PM 现在不做合并/淘汰动作。

---

# Required edits before final archival

我建议对 Q066 memo 做三处文字修订：

## 1. 把"empirically + theoretically orthogonal"改弱一点

建议：

```text
The two addons are empirically low-overlap and structurally non-redundant.
```

而不是：

```text
fully orthogonal
```

因为 Greek / PnL 层面还没证明完全正交。

---

## 2. 明确 Q042-B 样本不足

加入：

```text
Q042-B co-fire rate is not statistically stable due to N=5 and should be monitored as more events accumulate.
```

---

## 3. 增加 co-loss failure mode

加入：

```text
Co-fire downside scenario:
If aftermath fires after VIX off-peak and Q042 fires after drawdown, then a second-leg selloff can cause both sleeves to lose: the aftermath IC loses through put-side stress while the Q042 call spread decays or expires worthless. Greek sign opposition does not eliminate this path risk.
```

---

# Final verdict

**PASS WITH CAVEAT.**

正式表述：

> Q066 provides sufficient evidence that SPEC-064 Aftermath and Q042 Drawdown Overlay are not redundant and should not be merged or forced to compete. Same-day overlap is negligible, Q042-A is mostly vol-quiet drawdown exposure not captured by aftermath, and most aftermath windows are vol-only events not captured by Q042. However, the conclusion should be framed as "low-overlap / non-redundant," not "fully orthogonal." Greek sign opposition supports non-redundancy but does not prove portfolio hedge effectiveness. Co-fire downside scenarios remain possible and should be monitored, but they are not blockers to keeping both addons.
