# Q082 P10 G2 Follow-up — 2nd Quant Final Re-ratify

**From**: 2nd Quant Reviewer
**To**: 1st Quant Researcher
**Re**: Final re-ratify on three computations + revised Z verdict
**Date received**: 2026-06-02
**概览**: 三个数全部接受 · Y 放弃 RATIFY · Z（cap 50%）RATIFY · SPEC-111 联动 RATIFY · 但 close 前必须升级两个 finding 的地位（见末尾）· **一处对我自己预判的纠正**

---

## 先承认：你纠正了我两次，这两次纠正都对

我的 G2 预判里有两个判断被你的数据推翻了，我明确收回：

**1. 我以为 Y（MA-cross gate）可能有用。** 你算出来 Y 只能挡 2/32 = 6.2% 的 DOWN 窗口，aggregate 几乎不动（+9.71 vs +9.70）。**Y 被干净地证伪。** 我当时说"倾向 Z 保底 + Y 视反事实决定"——反事实出来了，Y 无效。接受。

**2. CV1 的方向我和 1st quant 都猜反了。** 我在 G2 里复述了你的 CV1 论证（skew steepening → short-leg 对冲变大 → 真实 DOWN drag 比 −19 浅），还据此要求你做 bracket "把定性猜测变成数字"。结果 bracket 显示方向是**反的**：skew steepening 让 short-leg σ 涨得比 long-leg 快，而 BCD 是 **long-leg 多张、short-leg 少张** 的结构，net vega 是正的（cushion），skew 的不均匀上涨**侵蚀**这个 cushion 而非增厚——DOWN drag 加深到 −21pp。

这个发现的意义比"cap 该设多少"大得多，下面单独讲。

**这正是 G-review 机制的价值**：我没有比 1st quant 更懂 BCD 的 vega 结构，我只是坚持"把那个对你有利的定性 caveat 变成可证伪的数字"。证伪它的不是我的洞察，是那个被强制跑出来的 bracket。**机制 > 个人判断**，这条值得记。

---

## 逐条 ratify

**Q1 方法学 — RATIFY（条件已满足）。** 你接受了"aggregate 稳、DOWN 绝对值需独立验证"的拆分，并用 skew bracket 把 DOWN 的不确定性显式化了。条件满足。

**Q2 per-stratum 稳定性 — RATIFY（维持强）。** 用 n=137 自身分层，不 port 3 年。这条 process learning 进 memory 是对的。

**Q3 verdict 结构 — 接受 Z，X 确已不可辩护。** 三条理由都成立：DOWN drag 真实且紧（CI [−22.3, −16.5]）、Y 证伪、cap 是唯一杠杆。X 死于"用管单笔幅度的工具回应频率/方向结构问题"——我 G2 的核心反对，现在有数据支撑。

**Q4 skew 敏感性 — RATIFY，且这是整包最有价值的一步。** 见下方 finding。

**Q5 block bootstrap CI — RATIFY。** [−22.3, −16.5] 落在我说的"[−15,−23] 则结构清晰"区间内。DOWN drag 是 **tight、reliable** 的估计，不是估计误差——"1/4 的 BCD 交易会可靠地跑输 QQQ 16-22pp"这个表述准确。block_size=4 对 ladder 间隔合理。

---

## CHALLENGE（不是拦 close，是拦"close 得太干净"）：两个 finding 的地位被低估了

verdict 收敛到 Z 我同意。但 P10 把两个本质性发现当成了"支持 cap=50% 的论据"，而它们其实是**独立于 cap、更重要、该单独立项**的结论。如果就这么 close，它们会被埋进一个参数调整里。

### Finding 1：你证明了一件比 BCD 更普适的事——"短 DTE 策略的 forward 方向无法被进场信号 gate"

P10 §1 那句话被你轻轻放过了：

> "point-in-time entry signal cannot predict forward 24-day window direction is structural to short-DTE strategies. Trend-filter gating doesn't help."

**这不是 Q082 的脚注，这是一条横跨整个策略矩阵的结构性结论。** 它的含义：你们矩阵里**所有**用 point-in-time regime（VIX/IVP/trend）路由的策略，都共享这个局限——entry 信号管"进场时的状态"，但管不住"forward 窗口的演化"。Q082 只是在 BCD 上撞到了它。

这直接回连到 **Q081 G2 我拦下的那个问题**：当时我担心"+8pp 是不是杠杆 beta"。现在答案完整了——是的，BCD 是 regime-conditional 杠杆 beta，UP +28 / DOWN −19，而**没有任何进场信号能提前区分你将进入哪种窗口**。这意味着 BCD 的 DOWN 风险**不可被择时消除，只能被 sizing 限制**。

**要求**：把这条作为**独立 finding 写进 Q082 close memo 的 headline**，并交叉引用到所有 point-in-time 路由的策略（不只 BCD）。下一次有人提议"加个 trend gate 改善某策略尾部"时，这条 finding 应该被先调出来——Q082 已经用 137 笔证明了这类 gate 在短 DTE 上无效。**否则这个 6.2% 的证伪会被遗忘，三个月后有人重新提 MA-cross gate。** 这正是你们 `feedback_kill_gate_external_read` 担心的"假阴性不可观测"的反面——一个**有价值的真阴性**（gate 无效）如果不显式登记，也会丢失。

### Finding 2：CV1 方向猜反，暴露了一个比"status quo bias"更具体的方法论风险

你把 P8 的教训记成了 `feedback_status_quo_bias_in_verdicts`（倾向维持现状）。这条对，但 CV1 事件揭示的是一个**更精确、更危险**的模式，值得单独记：

> **定性 caveat 的方向断言，在没算之前，连符号都可能是错的——而且错的方向恰好"对自己的 verdict 有利"。**

CV1 不只是"猜错了方向"。它是：1st quant 提出一个 caveat，**自然地把它的方向解读成支持自己结论**（"caveat bias-against BCD，所以真实 edge 更大，false-positive 不可能"）。这个"caveat 都对我有利所以结论更稳"的论证**形式上极有说服力**，我在 G2 里也差点买账（我复述了它，只是要求量化）。结果一量化，符号是反的。

**这比 status quo bias 更隐蔽**：status quo bias 是"懒得改"，容易自查；而"把未量化的 caveat 朝有利方向解读"是**穿着严谨外衣的确认偏误**——它看起来像在做保守性论证（"连最坏情况都对我有利"），实则在用一个没验证的符号给自己背书。

**要求**：单独记一条 memory，比如 `feedback_unquantified_caveat_sign_risk`：**任何"caveat 方向有利于本 verdict"的论证，在 caveat 被量化（哪怕是粗 bracket）之前，不得作为 verdict 稳健性的支撑。** 规则化：caveat 的符号要么算出来，要么在 verdict 里按"符号未知"处理（即两个方向都要 verdict 成立）。这条比泛泛的"status quo bias"可操作得多，且能拦住一类具体的错误论证。

---

## Z 参数本身 — 一个小确认，不拦 close

cap=50% vs 40% 的权衡（50% 保 UP 结构 alpha、40% 砍掉一半上行暴露）逻辑成立。一个确认项：

**50% × $37k = $18.5k debit，但 Q081 baseline 单笔 debit 是 $24k。** P10 说 "sizing reduces ~17%"——但 $24k → $18.5k 是 **−23%**，不是 −17%。§E 里"~17% smaller"和 cross-reference 里"§AC7 sizing adjustment now ~17%"这个数字对不上 50% cap 的实际含义。请在 SPEC-111 更新时核对：到底是 cap 锚在 $37k（→ $18.5k，−23%）还是锚在别的现金基数。这个数字会进 dev handoff，别让一个 −17/−23 的口径误差传下去。（不影响 verdict，纯参数核对。）

---

## 最终 ratify + close 清单

**RATIFY，可 close Q082**，附三个 close 前动作：

1. **Y 从 verdict options 移除** — agree，数据证伪（2/32）。
2. **Z（cap 50%）** — RATIFY，但核对 §E 的 −17% / −23% 口径矛盾（上条）。
3. **SPEC-111 60%→50% 联动** — RATIFY 交叉引用；注意这使 SPEC-111 不再完全独立于 Q082，close 时两个 doc 互相记一笔。

**close 前必须升级的两个 finding（这是我这轮的核心要求）：**

4. **Finding 1** —"短 DTE 策略 forward 方向不可被进场信号 gate"提升为 Q082 headline 独立结论，交叉引用所有 point-in-time 路由策略，作为未来 trend-gate 提案的预设反驳。
5. **Finding 2** — 新增 `feedback_unquantified_caveat_sign_risk` memory，比 status-quo-bias 更精确：未量化的 caveat 方向断言不得作为 verdict 稳健性支撑。

**aggregate 层 B-1**（+9.7pp、n=137、caveat 量化后仍 +9.13pp）—— 已稳，Q081 P5 可标记为 "ratified at aggregate, refined to cap=50% via Q082 Z path"。

执行轨迹评价：proxy collapse 被拦 → 真重建 → 重建推翻原结论 → 诚实上报 → 我的两个预判（Y 有用、CV1 方向）又被你的数据推翻 → 你照实记录。**这是 G-review 双向起作用的完整范例——reviewer 也被纠正了两次。** 补上 #4 #5 两个 finding 登记，即可 close。无需再返工。
