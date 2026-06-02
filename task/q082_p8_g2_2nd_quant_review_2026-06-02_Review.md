# Q082 P8 G-review 2 Reply

**From**: 2nd Quant Reviewer
**To**: 1st Quant Researcher
**Re**: B-synth-full verdict (P8 packet 2026-06-02)
**Date received**: 2026-06-02

---

## 概览

Q1 RATIFY（附条件）· Q2 RATIFY-强 · Q3 **CHALLENGE**（核心，X 不够，倾向 Z 且需补一步）· Q4 ADD（缺一个 skew 敏感性）· Q5 CHALLENGE（CI 不能 skip，但方法要换）

---

## 先肯定两件事

**1. 你没有绕过上一轮的 challenge。** 上一包我说"用 SPX forward 代理会塌缩，要 BCD-vs-QQQ 裁决就得加回真实/合成 PnL"。你（和 PM）选了 B-synth-full，真的重建了 137 笔。这是对的路径，且执行干净（exit at 21 DTE short leg、sequential ladder 对齐 matrix 行为、matched-window QQQ）。

**2. 你报告了一个推翻自己原 P5 的发现，且主动归因给我的 challenge。** DOWN stratum diff 从 3 年的 −3.4pp 深化到 26 年的 **−19.0pp（5.6x）**——这证明原 P5 把 3 年 per-stratum 投影到 26 年是 unsound 的。**你本可以淡化这个数字**（它让 verdict 难看），但你把它放在 headline 第 2 条。这种诚实正是 kill-class verdict 该有的。Q2 我**强 RATIFY**：per-stratum 小样本投影不可靠，verdict 必须用 n=137 自己的分层估计，不能 port 3 年值。这条 process learning 应进 memory。

---

## Q1 — BS-flat IV 重建是否够格 —— **RATIFY，但附一个必须澄清的条件**

BS-flat 作为这类重建的标准做法可接受，n=137 是无重大新工具下的最佳重建。但你 CV1 的**方向性论证有一个我不能照单全收的跳跃**，它直接关系到 Q3。

你的核心论点（贯穿 caveat section 和 Q1/Q3）是：**CV1+CV2 bias-against-BCD，所以真实 edge 比合成的 +9.7pp 还大，false-positive 结构上不可能。** 这个"caveat 都对我不利、所以结论更稳"的论证很漂亮，但**对 aggregate 成立，对 DOWN stratum 不成立**——而 Q3 的争议恰恰在 DOWN stratum。

拆开看 CV1："down move 时 short-leg OTM call IV 比 long-leg 涨得快，真实 BCD 的 short-leg 对冲比合成的大，所以真实 DOWN drag 是 −10~−15pp 而非 −19pp。" 这个方向我同意——**但它正好削弱你用来支撑 X 的那个论证**。你在 Q3 用"aggregate +9.7pp robust + caveat bias-against"来 ratify status quo（X）。可是：

- 如果 caveat 让 **DOWN drag 从 −19 缩到 −12**，那 aggregate edge 会**变大**（DOWN 是唯一拖累项）——这支持 X。
- 但同一个 caveat 也意味着**你对 DOWN stratum 真实行为的整个估计是软的**：合成说 0/32 win，真实因为 skew cushion 可能没那么惨。**那么 Q3 里"0/32 DOWN crater rate 是 PM 已接受的成本"这个论断，建立在一个你自己说被低估了的合成数字上。**

换句话说：你不能同时主张"DOWN drag 被合成高估了（CV1）"和"0/32 DOWN crater 是已知接受的成本（Q3 支持 X）"——前者说 DOWN 数字不可信（偏惨），后者把那个不可信的数字当作 X 的安全垫。**这两个论证方向打架。**

**RATIFY 条件**：方法学本身够格，但 verdict 必须明确——**aggregate edge 的结论稳（caveat 对它有利），DOWN stratum 的绝对数值不稳（caveat 对它的方向你自己都不确定，−19 还是 −12）。** 不能把"aggregate 稳"的稳定性借给"DOWN 成本可接受"那个论断。这直接推到 Q3。

---

## Q2 — per-stratum 稳定性 —— **RATIFY（强）**

如上。用 n=137 自身分层，不 port 3 年。这条是整个 Q082 最有价值的 process 产出：**小 n 的 per-stratum diff 不稳定，跨 mix-share 投影不可靠。** 这也回头验证了 Q081 G2 我拦 +8pp 时的担忧是对的方向——只是真相比我当时想的更尖锐：不是"+8pp 是 artifact"，而是"+8pp 是真的，但它由一个 +28pp 的 UP 暴利和一个 −19pp 的 DOWN 暴亏拼成"。aggregate 掩盖了一个**双峰、强 regime-conditional 的结构**。这点 Q3 要正面处理。

---

## Q3 — verdict 结构 —— **CHALLENGE：X 不充分，倾向 Z，且 X/Y/Z 都漏了一个该先算的数**

这是我必须拦的一条。你推荐 X（status quo + SPEC-111 cap 兜单笔尾部），理由是 aggregate +9.7pp / Sortino +0.9 robust。问题有三层：

**第一层：Sortino 从 3 年的 +2.349 暴跌到 26 年的 +0.896，你 headline 列了这个数但没解读它。** 这是个**警报**，不是"robust"。Sortino 掉了 62%。+0.9 的 Sortino 对一个**消耗 cash-bound 账户稀缺现金**的策略来说，是平庸的——它意味着下行波动几乎吃掉了大半超额。你在 takeaway 里写"Sortino +0.9 robust", 但 robust 的意思是"相对 3 年没崩"——它崩了一半。一个掉了 62% 的风险调整指标不能作为"维持现状"的支柱。

**第二层：0/32 的 DOWN win rate 是结构性的，cap 管不住它。** 你用 SPEC-111 cap 作为 X 的安全网，但 **cap 管的是单笔美元损失，不管"每次进入 DOWN 窗口都 100% 输给 QQQ"这个频率事实**。32 次 DOWN 窗口，BCD 0 次跑赢 QQQ，平均 −19pp（或 caveat 调整后 −12pp）。这不是"偶发尾部"，这是**每 4 次进场就有 1 次系统性地把稀缺现金喂给一个确定跑输 QQQ 的结果**。cap 把单笔损失从 46% 削到 60%×liquid，但它不改变"这 1/4 的钱本该留在 QQQ"这个事实。**X 用一个管单笔幅度的工具，去回应一个关于频率和方向的结构问题——工具错配。**

**第三层（最关键，X/Y/Z 都漏了）：Y 的方向 gate 能不能避开 DOWN 窗口，是一个可以直接算的数，但 packet 没算。** 你把 Y（SPX 30d/200d MA cross 阻止 BCD 开仓）当作"defensible 但不推荐"，却**没有给出 Y 的反事实**：如果对那 137 笔施加 MA-cross gate，能挡掉 32 个 DOWN 窗口中的多少个?这是决定 Y 价值的**唯一**数字，而它就在你已有的数据里——你有每笔的进场日和 forward 窗口方向，加一列"进场日 SPX 30d MA vs 200d MA"即可。

- 如果 MA-cross gate 能挡掉 32 个 DOWN 里的大部分（比如 ≥20 个），同时只误杀少量 UP/FLAT → **Y 显著优于 X**，因为它直接打击那个 0/32 的结构性失败源，而不是事后限制损失幅度。
- 如果 MA-cross gate 挡不住（DOWN 窗口的进场日当时 MA 还是多头排列，即 point-in-time 信号正常但 forward 变坏）→ 那 Y 无效，**这反而是支持 X 的最强证据**，而且这个证据现在不存在。

**没有这个反事实，X vs Y 的选择是没有依据的。** 你推荐 X 的理由全是"aggregate 好 + cap 兜底",但从没验证过那个本该是 Y 核心的 gate 到底有没有用。

**Q3 verdict：CHALLENGE。在 Y 的 MA-cross 反事实算出来之前，不能 ratify X。** 我的预判（需数据确认）：

- **倾向 Z（cap 收到 50%）作为最低限度**，无论 Y 结果如何——因为 DOWN stratum 的真实数值你自己都说不稳（CV1），在一个 Sortino 仅 0.9 的策略上，对 cash-bound 账户多留 headroom 是廉价保险。这与 Q081 G2 我建议 60% 的逻辑一致，现在 26 年数据显示尾部比 3 年深 5.6x，进一步支持收紧。
- **Y 是否叠加，取决于那张缺失的反事实表。** 如果 gate 能挡 DOWN，Y+Z；如果挡不住，Z-only 且明确记录"方向风险无法用进场信号 gate 掉，只能靠 sizing 限制"——后者本身是个有价值的 finding。

---

## Q4 — caveat 是否遗漏 —— **ADD：缺 skew 敏感性，且它不是可选项**

你列的 CV1-CV4 完整，但 Q4 里你把"σ 敏感性测试"当作"adds time without changing directional verdict"而想 skip。**不能 skip，理由就是 CV1 自己。**

你整个 verdict 的稳健性论证依赖"CV1+CV2 bias-against-BCD"这个**方向性断言**。但这是个**定性猜测，没有量化**。CV1 说真实 DOWN drag 是 −10~−15pp 而非 −19pp——这个区间是你估的，不是算的。而 X vs Z 的选择对这个数字敏感：DOWN drag 是 −12 还是 −19，决定了 aggregate edge 是 +12pp 还是 +9.7pp，也决定了 DOWN 成本到底多严重。

**最低限度的 skew 敏感性**：不需要完整 IV surface，跑两个 bracketing 场景即可——(i) short leg σ 在 DOWN 窗口 +X vol points（模拟 skew steepening），(ii) long-leg σ 用 VIX×contango factor。看 DOWN stratum diff 和 aggregate 在这两个 bracket 下的范围。如果 verdict（无论最终是 X/Y/Z）在 bracket 两端都成立 → 真 robust；如果 bracket 一端就翻盘 → 你现在的点估计 verdict 是脆的。**这是把"caveat bias-against 所以更稳"那个定性论证变成可证伪数字的唯一方法**，而你正把它当可选项。**ADD,不可 skip。**

---

## Q5 — bootstrap CI 是否 skip —— **CHALLENGE：不能 skip，但你说对了方法问题**

你想 skip CI，理由是"sequential ladder 的 bootstrap 因自相关而 awkward"。**自相关问题你诊断对了，但结论错了——awkward 不等于 skip。** 这正是 Q081 G1 我提过的 **block bootstrap** 该上场的地方：按时间块重采样（block 长度覆盖典型自相关尺度，比如 ladder 的平均间隔），就能在保留序列结构的同时给出 per-stratum diff 的 CI。

为什么不能 skip：DOWN stratum n=32、且是 0/32 这种**边界值**（win rate 触底）。点估计 −19pp 在 n=32 上的不确定性可能很大，而整个 Q3 争议都压在 DOWN stratum 的严重程度上。**在决定要不要为 DOWN 风险改 cap/加 gate 之前，必须知道 −19pp 的 CI 是 [−15,−23] 还是 [−8,−30]。** 前者结构清晰、后者说明你对 DOWN 行为其实所知甚少。block bootstrap 成本很低（你数据都在），**CHALLENGE skip,要 block-bootstrap CI on DOWN stratum diff 至少。**

---

## 跨 Q 收尾 + 给 PM 的把关意见

这条研究线的**执行轨迹是健康的**：proxy collapse 被拦 → 没绕、真重建 → 重建推翻了自己的原结论 → 诚实上报。这是 G-review 机制起作用的样子，记一功。

但 **P8 的 verdict 框架有一个系统性倾向：把所有不确定性都解读成"对 BCD 有利"或"已被 SPEC-111 兜住"**，于是收敛到最省事的 X。三处体现：(i) Sortino 掉 62% 被读成"robust"；(ii) caveat 不确定性被读成"bias-against 所以更稳", 却没注意它同时让 DOWN 数值不可信；(iii) Y 的核心反事实根本没算就被降级为"不推荐"。这三处合起来，让 X 看起来比证据支持的更稳。**这跟 Q081 G2 我拦下的那个假阴性是同一个机构性倾向——倾向于宣布"无需改动"。**

**放行清单：**

- **不可现在 close Q082、不可 ratify X。** 缺三个数：(1) Y 的 MA-cross 反事实（能挡掉多少 DOWN 窗口）；(2) DOWN stratum diff 的 block-bootstrap CI；(3) skew 的 bracket 敏感性。三个都用现有数据，合计估计 3-4h。
- **aggregate edge 的结论可以先 ratify**（+9.7pp、caveat 对它有利、n=137 充分）——B-1 在 **aggregate 层**成立，这点不挂起。
- **挂起的是 verdict 结构（X/Y/Z）**，等上述三个数。我的预判是 **Z（cap 50%）保底 + Y 视反事实决定**，但用数据定，不用预判定。
- **SPEC-111 独立性**：同意 cap+alert 作为独立治理不受 Q082 影响——但如果最终走 Z，SPEC-111 的 cap 参数要从 60% 联动改到 50%，这两者就不再完全独立了，close 时需在两个 doc 间记一笔交叉引用。

补三个数后我可在 24h 内 ratify verdict 结构并 close。aggregate 层、reconstruction 方法、Q2 process learning 均无需返工。
