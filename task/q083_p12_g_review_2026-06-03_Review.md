# Q083 P12 G-review — 2nd Quant Review (SPEC-113 Proposal)

**From**: 2nd Quant Reviewer
**To**: Quant Researcher (1st quant)
**Re**: `NORMAL × IV_LOW × BULL → BCD` cell route addition
**Date**: 2026-06-03
**Verdict 概览**: 诊断 RATIFY · SPEC commit **挂起**，缺四个 ratify-gate 前置（非 commit-gate）· Q-G3-1 AGREE · Q-G3-2 **该 block** · Q-G3-3 用数据切 · Q-G3-4 见 process 提醒 · Q-G3-5 AGREE-no

---

## 0. 先承认：这一轮你纠正了我们共同的方向

P10 的 root-cause 分解（n=1515）是这条线四轮里最重要的一个发现：被推 reduce_wait 的主因是 **cell-routing 占 67.5%**，IVP gate 只占 23.6%。这意味着**前三轮——包括我上一轮帮 PM 力推的"立刻换 IVP126 止血"——都在 debug 那个只占 23.6% 的次要 blocker**。换窗口救不了决定性的 67.5%，因为那 67.5% 根本没走到 IVP 这一层就被 matrix 的硬编码 `reduce_wait` 拦掉了。

**你这一轮的诊断比我上一轮的 review 更接近 PM 痛点的根因。** 我明确收回"换窗口止血"的方向。记一功。

而 §3 的刻画也和 PM 体感闭环：那 1023 个被堵的日子（中位 VIX 17.74、21d 内 29.6% 概率 vol 再涨 ≥5vp）正是 PM 说的"一次 VIX 上涨之后那段时间"——而它们恰好是 BCD（long vega）结构上受益的环境，matrix 却给了 reduce_wait。痛点机制讲通了。

---

## 1. 但这次"对得太顺"——你有把 `feedback_decision_type_governs_significance_standard` 用过头的迹象

你引用的判断标准（执行约束工具用比较标准、不用 vs-零显著性）是对的，是 PM 上一轮逼出来的正确标准。**但"不需要 vs-零显著性"不等于"不需要稳健性检查"。** 这一轮有三处把"执行约束决策"当成了豁免稳健性检查的理由，而它们恰恰是 Q082 栽过的坑。逐条说。

---

## 2. Q-G3-2 / §6.1 — skew bracket 必须 ratify 前跑，不是 commit-gate（决定性 CHALLENGE）

你 Q-G3-2 问"skew 该 block commit 还是当 commit-gate validation"。**答案：该 block，且必须前移到 ratify 之前。** 理由全部是你自己写的 Q082 教训：

1. Q082 P10 我们三个人把 skew 方向猜反过——BS-flat 在 vol-expansion 环境给错了符号，skew steepening 侵蚀（而非增厚）net vega。
2. 这个格子比 Q082 更危险：§3 自己说这是 spike-后、regime-transition 天，put-skew 在这种环境最陡、最易失真。Q082 的 LOW_VOL 格子 skew 还没这么极端。
3. **最关键**：你 §6.1 自己估的悲观情形 **30% haircut → $987，已经低于基线 $1,016**。也就是说，**整个提案"BCD 优于 baseline"的成败，就压在 skew haircut 的真实大小上**——这是决定性变量，不是边角验证。

**要求**：skew bracket（+3/+5/+8 三档，per-leg pricing，对齐 Q082 P7 方法）在 ratify 前跑完。

---

## 3. Q-G3-3 — carve-out VIX<18 用 skew 后数据决定

你 §4 的 VIX 分层显示 18-19（+$424）、19-20（+$328）比 15-16（+$2,241）弱一个数量级。你 Q-G3-3 问要不要 carve out，并说"no cliff, 18-20 仍为正"。

**纠正一个隐藏前提**："仍为正"是 BS-flat 下的为正。结合 §2：这些最弱的 sub-bucket 恰恰最经不起 skew haircut——**+$328 扣 30% 就接近零甚至转负**。

**要求**：先跑 §2 的 skew bracket，看 18-20 bucket 在 +8 档下是否转负。
- 若转负 → carve out VIX<18
- 若仍稳健为正 → 保留全 15-22

---

## 4. §6.3 — cash-bound 频率检查（PM 约束，轻描淡写了）

BCD 频率从 ~6/年 提到 ~10/年（+67%）。PM 是 cash-bound。你说"SPEC-111 cap bounds per-trade"——但 cap 管单笔幅度，不管频率叠加的现金时间占用。

关键风险：Q081 验证的"0 crowd-out / sequential ladder 一次一个"是在 6/年 频率下成立的。提到 10/年后，**两笔 BCD 时间重叠的概率上升**，sequential ladder 的"一次一个"假设可能开始漏。

**要求**：在 10/年频率下，回测历史上"前一笔 BCD 未平、新信号触发"的重叠次数，以及重叠时的合计现金占用。

---

## 5. Q-G3-2 附带 — bootstrap CI 同样前置

§6.2 你自己说 n=82 的 aggregate CI 没算。虽然这是比较决策，但 CI 仍是判断差距稳定性的必要信息——尤其在 skew haircut 后差距收窄时。block-bootstrap（block_size=4，对齐 Q082）成本很低，ratify 前一并给。

---

## 6. Q-G3-4 — process check

被多次撤回的提案，稳健性只能前置不能后移。这条建议记入 memory：`feedback_post_withdrawal_proposals_front_load_robustness`。

---

## 7. 放行清单

**RATIFY（不必返工）**：
- P10 cell-routing root-cause 诊断（67.5% 是真 blocker）
- §3 的格子刻画（spike-后 regime-transition、BCD long-vega 结构受益）
- 比较标准（Q-G3-1）、NEUTRAL 不扩展（Q-G3-5）、SPEC-111 cap 作为单笔兜底

**挂起、ratify 前必须补（四个 ratify-gate）**：
1. skew bracket +3/+5/+8（§2）—— 决定性
2. carve-out VIX<18 用 skew 后数据决定（§3）
3. cash 频率重叠检查（§4）
4. block-bootstrap aggregate CI（§5）

**不能现在做**：draft SPEC-113、把 skew/CI 当 commit-gate 后置。

补齐后我可在 24h 内 ratify + 决定最终 SPEC 范围（全 15-22 还是收到 15-18）。
