# Q081 P5 G2 — 2nd Quant Review

**From**: 2nd Quant Reviewer
**Re**: Final verdict + SPEC recommendation
**Date received**: 2026-06-01
**Verdict 概览**: Q1 **CHALLENGE**（核心问题，先读这条）· Q2 RATIFY-65%（但口径要改）· Q3 RATIFY-60% · Q4 CHALLENGE-add（缺一个 forward monitor）

---

## Q1 — "matrix unchanged" 是否结构上成立 —— **CHALLENGE**

这是整包最关键的一条，也是我必须拦下的一条。问题不在你的结论，而在**你引用我 G1 指导的方式**，以及由此产生的一个 verdict 内部矛盾。

**先纠正一个事实引用。** 你写"2nd quant pre-framing said 'use p05 as the threshold'，strictly applied, that argues for BCD-vs-QQQ gate"。我 G1 的原话不是"用 p05 当阈值去 gate BCD"——而是"**BCD vs QQQ 比较时，要扣掉左尾后再比，不能只比均值**"。这是两件不同的事：

- 我的本意：**警告不要被均值优势迷惑**，因为 BCD 是上行参与结构、QQQ 是 beta，均值差很可能是样本窗口的方向 bias（我 G1 Q1 补充明确要求你加"21 个窗口的 SPX/QQQ 同期 return 分布"那一栏——**P3 memo 里做了吗?packet 没提**）。
- 你的转述：把它读成"p05 是硬 gate 阈值"，然后再论证 p05 差距可接受、所以 unchanged。

**这个转述把我的方法论警告变成了一个稻草人**，然后你把它推翻了。我没说 p05 是硬阈值。所以你 Q1 的二选一（"接受 mean dominance" vs "把我的话当硬规则上 gate"）是个**假二分**——两个选项都不对。

**真正要回答的问题是：那个 +8pp / +$1,719 的均值优势，扣掉窗口方向 bias 之后还剩多少？** 这正是我 G1 让你加那一栏的原因，而 packet 里完全没出现这个对照。在这个数字给出来之前，"mean dominance"这个 verdict 的**整个基础是未经验证的**。具体担忧：

> 21 笔 BCD 全部来自 LOW_VOL × BULLISH cell。BULLISH 选股 + LOW_VOL 期 = 样本系统性偏上行窗口。同窗口 QQQ 也涨。BCD 作为带杠杆的上行参与工具，在上行窗口里"跑赢 QQQ +8pp"几乎是**结构必然**，不是 edge——它只是说"在 SPX 涨的时候，一个加了 delta 杠杆的工具比裸 beta 涨得多"。这不证明 BCD 应该继续被路由，只证明它在上行时有更高 beta。**真正的检验是下行/震荡窗口**，而那恰恰是 p05 暴露的（BCD 下行 p05 −11.6% vs QQQ −5.5%，差一倍）。

把这两点合起来：**BCD 上行时多赚（+8pp mean）、下行时多亏（p05 翻倍）——这不是"mean dominance + bounded tail disadvantage"，这是"更高 beta + 更肥左尾"，即一个被加了杠杆的 QQQ。** 在一个 cash-bound、且 PM 整个命题就是"现金本可稳稳放 QQQ"的账户里，用稀缺现金买一个"上行多赚、下行多亏"的杠杆化 beta，**hurdle 不是 QQQ 的均值，而是 QQQ 的风险调整后回报**。你现在的对比把 BCD 的高 beta 算作 alpha 了。

**我不是说 verdict 一定错，是说它现在缺一块决定性证据。** ratify "unchanged" 之前，P3 必须补：

1. **21 个持仓窗口的 SPX/QQQ 同期 return 分布**（G1 已要求，未交付）——量化样本的上行 bias 有多重。
2. **窗口方向分层**：把 21 笔按其持仓窗口 SPX return 分成 up / flat / down 三组，分别看 BCD vs QQQ。如果 BCD 的 +8pp 全部来自 up 窗口、在 flat/down 窗口 BCD 反而输——那"unchanged"就站不住，应该 gate（或至少加方向条件）。
3. **风险调整对比**：+$1,719 mean uplift vs −$1,920 p05 disadvantage，你称"roughly symmetric"——但这是**错误的对称性**。均值是你大部分时候拿到的，p05 是尾部你偶尔吃的，两者频率/效用不对称。正确的比法是 BCD 同窗口 QQQ 的 **Sharpe 或 Sortino**，不是 mean 和 p05 两个点的绝对值相减。

**Q1 verdict：在 #1 和 #2 交付前，CHALLENGE，不能 ratify "unchanged"。** 如果分层后 BCD 在 flat/down 窗口仍不输 QQQ（即 +8pp 不是纯方向 bias），我立刻 ratify。如果 +8pp 主要来自 up 窗口，verdict 应改为"matrix unchanged **但加 BCD-vs-QQQ 方向 gate**"或保留 cap-only。这是可证伪的，给我那两张分层表即可定夺。

---

## Q2 — 65% liquid cash cap 的标定 —— **RATIFY 65%，但口径必须是 % liquid，不能换成 % NLV**

65% 的标定逻辑合理（13k→18.5k slack 的边际价值 > 强制缩小 BCD 的边际成本）。**反对你 Q2 里提的"换成 5% NLV = $62k"那个备选。**

理由直接来自 P0：账户是 **cash-bound**，稀缺资源是 liquid cash（$37k），不是 NLV。用 % NLV 做 cap 会犯一个口径错误——$62k 的 NLV-based cap 比整个 liquid cash 池（$37k）还大，**等于没有 cap**。cap 的分母必须是它要保护的那个稀缺资源。% liquid cash 是对的，% NLV 在这个账户里是失效口径。这点你 G1 时我已经强调过（"cash-bound 账户的正确分母是 % liquid cash"），保持一致。

唯一补充：cap 应基于 **steady-state liquid cash（$37k）还是实时 liquid cash**?建议实时（% of current liquid），这样 Q3(a) 的自适应才成立——如果写死成 65%×$37k 的绝对美元数，PM 一旦 rebalance 现金它就失效了。确认 SPEC 用的是动态百分比而非固化美元值。

---

## Q3 — 一个 cap 是否够 / 要不要更保守留 headroom —— **RATIFY 60%**

同意降到 **60%**，给未来多 debit 策略留 headroom。你 (b) 场景的自我分析是对的：cap 跨所有 debit 策略聚合，结构上 future-proof，但 65% 是按"1 BCD = 主消费者"标定的，将来加第二个 debit 策略时每个都得缩小。

在 60% vs 65% 之间，考虑到：(i) 65%→60% 的 slack 代价很小（多留 ~$1,850 现金，BCD 缩一点点）；(ii) cash-bound 账户对"意外现金需求"的脆弱性高（slack 是真期权价值）；(iii) Q081 的 actionable 产出就这一条，宁可保守。**选 60%。** 这也比"re-audit cap when matrix adds debit strategies"那个纯文档方案稳——文档约束依赖未来有人记得去 re-audit，而 60% 是结构性预留，不依赖人。

---

## Q4 — verdict 漏了什么 —— **CHALLENGE-add：缺一个 forward crowd-out monitor**

P4 light 的 structural-only ratify 我接受（BPS 在 LOW_VOL 的 −vega + mean-reversion 劣势是定性清楚的，不需要深挖）。但你 Q4 自己问的"是否需要 secondary verdict"——答案是**需要，且 packet 里漏了它**。

P1 判定"组合层 crowd-out = 0（历史）"，P3 §E 又确认"单笔层 forward 风险存在（8.8% of cash）"。这两条之间有个**未被任何东西守住的缝**：sequential ladder 的"0 crowd-out"是**历史行为的产物，不是结构保证**。如果未来 BCD 出现频率上升、或持仓窗口拉长导致两笔 BCD 时间上重叠，组合层 crowd-out 就会从 0 变正——而 cap（单笔现金上限）**管不住并发笔数**。cap 限制的是单笔 debit ≤ 60% liquid，但两笔各 50% 就会合计 100%，cap 不触发，crowd-out 却发生了。

**建议加一条 secondary verdict（不是新 SPEC，是 monitor）**：一个 **concurrent-debit cash-utilization alert**——当所有在场 debit 仓合计现金占用超过某阈值（比如 75% liquid）时告警。这守住的正是 P1 的"0 crowd-out"假设在未来失效的那个场景，而你 Q3(b) 自己也识别到了这个风险点，却只用"cap 聚合所以 safe in principle"带过——但聚合 cap 管总量不管"总量逼近上限"的预警。一个 alert threshold 是廉价的保险。

这也回应你们 Q079 横切 Q19 的那个教训：**false negative 不可观测**。"组合层 crowd-out = 0"如果将来悄悄变正，没有 monitor 就没人发现——直到某天真的现金不够。这正是该装一个观测点的地方。

---

## 跨 Q 收尾 + 给 PM ratification 的把关意见

两个 pattern，请在 SPEC drafting 前处理：

**1. verdict 的承重证据缺失（Q1）。** "matrix unchanged" 目前压在 "+8pp mean dominance" 上，而这个 +8pp 很可能是样本上行 bias 下的高 beta，不是 edge——G1 要求的窗口方向对照表至今未交付。**在那张表出来之前，这个 verdict 不该进 PM ratification。** 这不是吹毛求疵：你们的规则说 kill-class verdict 需要外部读，正是因为"宣布无需改动"的假阴性最贵——而这里的假阴性恰恰是"BCD 其实是杠杆 beta、不配占用 cash-bound 账户的稀缺现金，但我们宣布维持路由"。

**2. 但好消息是：即使 Q1 翻盘，actionable 产出（cash cap）依然成立。** 无论 BCD 该不该继续被路由，"debit 仓单笔 ≤ 60% liquid cash + 并发告警"这条治理都是对的、独立于路由结论。所以 SPEC drafting 可以**拆成两步**：cap + alert 这条（Q2/Q3/Q4）现在就可以 ratify 进 SPEC；matrix routing 这条（Q1）挂起，等窗口分层表出来再定。**不要把两者捆在一个 verdict 里一起送 PM**——否则一个未验证的路由结论会搭着一个扎实的 cap 结论一起被 ratify。

具体放行清单：
- **可进 SPEC（现在）**：`debit_cash_budget_cap ≤ 60% liquid cash`（动态百分比口径）+ concurrent-debit 75% alert。
- **挂起待补**：matrix-unchanged 结论 → 需 P3 补窗口方向分层表（up/flat/down × BCD-vs-QQQ）+ 风险调整对比（Sortino，非 mean/p05 点对点）。补齐后我可在 24h 内 ratify 或转 gate 建议。

无需重跑全分析，按上述补两张表 + 拆 verdict 即可。
