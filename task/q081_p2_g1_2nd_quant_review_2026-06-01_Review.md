# Q081 P2 G1 — 2nd Quant Review

**From**: 2nd Quant Reviewer
**To**: 1st Quant Researcher
**Re**: Pre-P3 methodology ratification (packet 2026-06-01)
**Date received**: 2026-06-01

---

## Verdict 概览

- Q1 RATIFY（附一个补充）
- Q2 RATIFY-A（但 P1 数据改变了理由）
- Q3 CHALLENGE → 重新表述
- Q4 RATIFY-include（强烈，且应升级）

---

## 先说一个 P0/P1 引出的框架问题（在回 Q1-Q4 之前必须摆上桌）

P1 的结果实质上**部分推翻了原始 framing 的前提**，这件事比 4 个方法论问题都重要，请先确认我们没有在一个已经松动的前提上继续。

**原始命题**（来自 PM 备忘 §1）：账户 cash-bound，BCD 占稀缺现金挤占 QQQ，是真机会成本。

**P1 实测给出**：
- 0 historical crowd-out（sequential ladder，从没真的挤掉过 QQQ 配置）
- steady-state liquid cash 仅 $37k（3% NLV）
- 累计机会成本 = gross PnL 的 6.6%

这三条合在一起说明：**cash-bound 在账户标签上成立，但挤占从未实际发生**——因为 BCD 是 sequential ladder，节奏本身就避开了并发占用。也就是说，PM 最初担心的"BCD 吃光本该进 QQQ 的现金"在历史上没发生过。这把整个研究的 verdict 空间收窄了：

**真正还活着的问题不再是"BCD 是否在挤占 QQQ"（答案：历史上没有），而退化为两个更小的问题**：

(i) **单笔 BCD 的现金效率本身**是否跑赢把那块现金留在 QQQ（纯 ROE 比较，与挤占无关）

(ii) **是否存在未来某种 regime** 会让 sequential ladder 失效、产生并发挤占（前瞻性风险，P1 的历史 0 不保证未来 0）

请在 P3 memo 开头**显式记录这个 reframing**，否则 P5 verdict 会被误读成"回答了挤占问题"，而实际上挤占问题已被 P1 判为 non-issue。这跟 Q078 中途 thesis reframing（diversification → cadence overlay）是同一类情况，按那个先例处理。

**另外提醒一句方法论卫生**：6.6% cumulative opp cost 这个数字本身要小心——它是 BCD 占现金期间"假设那块现金在 QQQ 会赚多少"的反事实，**强依赖于该期间 QQQ 的实际走势**。3 年里 QQQ 大涨，这个 6.6% 是被一段特定 beta 行情抬高的，不是结构常数。P3 比较时这点会再次咬人（见 Q1 补充）。

---

## Q1 — Period-ROE for tail comparison

**RATIFY.**

年化短持仓损失把 p05 放大到 -454% 是无意义的 artifact，period-ROE 是对的。对 21 笔逐笔取同持仓窗口的 QQQ 收益再比 period 分布，方法干净。

**补充一个必须加的对照**（不是反对，是补强）：BCD 是 long-vol/上行参与结构，QQQ 是纯 beta，两者在同一持仓窗口比 period-ROE 时，**结果会被该窗口 SPX/NDX 的方向强烈污染**——如果 21 笔恰好多数落在上行窗口，QQQ 同窗口也涨，你比的是"两个上行参与工具谁参与得多"，而不是 BCD 的结构 edge。

请在 P3 加一栏：**21 个持仓窗口的 SPX/QQQ 同期 return 分布**，让我们看清这批样本的方向 bias。如果窗口本身偏上行，BCD 跑赢 QQQ 就要打折读。

---

## Q2 — n=21 vs 扩到 n=60-100

**RATIFY Option A（n=21），但理由要换**。

你的理由是"n=21 已清晰显示结构，扩样主要收紧 CI 不改形状"——这个理由单独不充分，因为 borderline 的 15% relative SE **恰恰是在 p05（尾部）上**，而尾部正是整个研究的判据所在；"形状已清晰"对尾部估计的说服力最弱。

真正支持 A 的理由是 P1 给的：**挤占问题已被判 non-issue（0 crowd-out），verdict 空间收窄**，因此不再需要一个高精度的尾部估计去支撑一个高风险的矩阵改动——剩下的决策（见下 Q3/Q4）对尾部 CI 宽度不敏感。在这个收窄后的范围里，n=21 的宽 CI 是可接受的。**用这个理由 ratify A，不要用"形状已清晰"。**

但 Q2 里藏着的 Option B 的副产品（populate IVP_HIGH bucket）是真有价值的——这点合并到 Q3 一起处理。

---

## Q3 — 空的 IVP_HIGH bucket：(a) accept binding vs (b) synthesize

**CHALLENGE。两个选项都不完全对，verdict 要重新表述。**

你倾向 (a)，理由是"verdict 问的是 current routing 不是 redesign"。这个理由有一个隐藏缺陷：**(a) 会让 Q081 在结构上无法证伪矩阵当前的路由**。如果样本 100% 是 IVP<67，你只能回答"BCD 在它被允许开的地方表现如何"，但**永远无法回答 PM 真正在审的那个矩阵设计问题**——IVP≥67 时路由去 BPS 而不是 BCD，这个选择对不对。换句话说，(a) 把矩阵当成不可质疑的约束，那 Q081 就只是在矩阵内部做体检，没有触及 PM 审计矩阵的初衷。

但 (b) 你说是 Q082-class scope，这点我同意——做完整 synthetic BCD 反事实确实超纲。

**重新表述（第三条路）**：不做 (b) 的完整合成，但在 P3 做一个**轻量的单点 sanity probe**——只回答一个问题：

> "IVP≥67 时 BPS 的 ROE-on-cash（≈0 占现金）vs 假设性 BCD 的 cash 占用，在 cash-bound 框架下，路由去 BPS 是否显然更优？"

这个不需要重建 60-100 笔合成 BCD，只需要论证：在 IVP≥67、premium 充裕时，credit 策略（不占现金）在 cash-bound 账户里对 debit 策略有结构性的资源优势，**与 ROI 谁高无关**。如果这个结构论证成立（我预期成立），那矩阵的 IVP≥67→BPS 路由就被定性地证伪不了——你不需要数据就能 ratify 那条路由，因为它正是 PM 整个 cash-bound 命题的直接推论。

**结论**：采纳 (a) 作为**定量 verdict 的 scope**，但 P3 必须附一段**定性论证**说明为什么 IVP≥67→BPS 在 cash-bound 框架下结构上正确，从而显式回答 PM 的矩阵审计问题，而不是回避它。完整合成留给 Q082。这样既不超纲，又不让 verdict 在结构上无法触及初衷。

---

## Q4 — P5 是否含 sizing recommendation

**RATIFY-include，且强烈建议升级为主 verdict 之一，不要 defer。**

理由：worst trade -$3,248 = **8.8% of liquid cash baseline**。注意这个口径——你引的 5% NLV gate 是 sub-noise，但那是 % NLV；**在 cash-bound 账户里真正咬人的分母是 % liquid cash**，而 8.8% of $37k cash 是一个实质性的单笔现金冲击。

P1 说稳态闲置 cash 只有 12-14k slack，一笔 outsized BCD（debit $24k，worst-case -$3,248）就能吃掉一大块 slack——这恰恰是 PM 最初担心的"挤占"**在单笔层面的真实版本**（虽然 P1 说 sequential ladder 在组合层面没挤占，但单笔层面的 cash 冲击是另一回事）。

所以 **sizing 不是 P5 的附属建议，它是这个研究真正活着的 actionable 结论**。回到我开头的 reframing：挤占问题（组合层）已 non-issue，IVP≥67 路由（Q3）可定性 ratify——那么 Q081 剩下**唯一能产生矩阵不变但仍有价值的产出**，就是 sizing/cash-budget cap。请把它放进 P5 主 verdict。

**具体形式建议**：用 **% of liquid cash 而非 % NLV** 作为 cap 口径（cash-bound 账户的正确分母），形式上对齐 PM 备忘里建议的 `cash_budget_pct` ——即"全部 debit 仓占用现金 ≤ X% liquid cash"。X 的标定可以借 P2 的分布：让最坏单笔 cash draw 控制在 slack 之内。

**不 defer 到单独 sleeve SPEC 的理由**：defer 会让 Q081 close 时没有任何 actionable 产出（矩阵不变 + 挤占 non-issue + 路由 ratify = 一个"什么都不用改"的 verdict），而真实的可改进点（单笔 cash 冲击）会掉进缝里没人接。这正是上一包 Q079 横切问题 Q19 担心的"假阴性比假阳性更难发现"——一个 close 得太干净的研究，恰好把唯一该落地的东西漏掉了。

---

## 跨 Q 收尾

一个 pattern：P1 的两个结果（0 crowd-out、$37k cash）**安静地改变了整个研究的重心**，但 G1 packet 仍按原 framing 在问 Q1-Q4。这不是错，但有风险——4 个问题都还在围绕"如何精确测量 BCD 尾部"，而 P1 其实已经把"尾部精度"的决策权重调低了（因为高风险的矩阵改动已不在桌上）。

建议 P3 开头花**半页做一次 thesis recentering**：明确写出"挤占→non-issue、verdict 收窄为 single-trade cash sizing + 定性路由确认"，否则 P3-P5 会继续投入精力在一个已经降权的维度（尾部 CI）上。这跟 Q078 的中途 reframe 是同构的，按那个先例办即可。

verdict 之外无需重跑分析，Q1-Q4 按上述 ratify/challenge 即可推进 P3。
