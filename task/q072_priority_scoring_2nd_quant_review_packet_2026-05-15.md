# Q072 — Priority Scoring & Blocked-Entry Design (Round 2)
## 2nd Quant Review Packet

**Date**: 2026-05-15
**Prepared by**: Quant Researcher
**Audience**: 2nd Quant Reviewer
**Round**: 2nd (round 1 review at `task/q072_sleeve_global_eval_design_review_2026-05-15_Review.md` PASSED with revisions, all incorporated)
**Stage**: Last gate before launching P1 — focused review on the only piece round 1 did **not** cover in detail
**Reviewer response**: `task/q072_priority_scoring_2nd_quant_review_packet_2026-05-15_Review.md`

---

## 0. TL;DR

Round 1 review confirmed Q072 P1–P4 framework with revisions. All revisions have been incorporated into the brief at `research/q072/q072_research_brief_2026-05-15.md`.

The **only new design element round 1 did not stress-test** is PM's instruction for P4C's blocked-entry counterfactual:

> 入场优先级：**按信号质量 × 回报 profile 决定**，不按 main-first 默认。

Round 1 left the BP-arbitration rule as "TBD with PM". PM has now answered, and the rule has been spec'd into `P4C.1` (priority formula) + `P4C.3` (sensitivity & control rules). **This packet asks 2nd Quant to stress-test that specific design before P1 launches.**

P1–P3 + P4A/B 设计本轮不复审；如 reviewer 发现 P4C 反推回前序 phase 有遗漏，请明确指出。

---

## 1. P4C.1 — Priority Scoring 设计

每个交易日 BP available < 当日全部 candidate 总需求时触发；按 priority 从高到低分配 BP，至剩余 BP 不足下一 candidate 为止。

### Formula

```
priority = w_q × signal_quality + w_r × expected_return_per_bp − w_t × tail_penalty
```

**初版权重**：`w_q = 0.4, w_r = 0.4, w_t = 0.2`（P4C.3 内做 sensitivity）。

### 三个分量

所有分量按 candidate 所属策略的历史分布 z-score 化（避免量纲冲突）。

| 分量 | 定义 | 数据来源 | 分桶维度 |
|---|---|---|---|
| `signal_quality` | candidate 当下 entry condition 与历史最优入场区间的拟合度 | 19y backtest 入场分位（每策略 separately） | VIX bucket / IVP bucket / regime / ddATH bucket |
| `expected_return_per_bp` | 历史"相似入场条件"的 median $/BP-day | 19y baseline + sleeve trade lists | 同上分桶 |
| `tail_penalty` | 历史"相似入场条件"的 worst trade + \|CVaR 5%\|（per BP）| 同上 | 同上 |

**分桶具体方案**（草案，请 reviewer 评）：

- VIX bucket: `[<15, 15-18, 18-22, 22-26, 26-30, 30-40, ≥40]`
- IVP bucket: `[<30, 30-43, 43-55, 55-70, ≥70]`
- regime: `LOW_VOL / NEUTRAL / HIGH_VOL / EXTREME_VIX`
- ddATH bucket: `[<2%, 2-5%, 5-10%, ≥10%]`

每个 candidate 入场点用 4 维 key 查表，落到桶内取该桶的 median $/BP-day 和 worst/CVaR；若桶内 n < 5，向最近邻桶聚合。

### Tier 平手逻辑

priority 数值平手时（差距 < ε），按 Tier 排序：

| Tier | 含义 | 成员 |
|---|---|---|
| 1 | 稀缺触发信号 | Aftermath（19y 仅 15 笔）, DD Overlay dd15（罕见 stress reclaim）|
| 2 | HV 常规 | HV Ladder, BPS HV normal |
| 3 | 稳定常规 | main BPS NNB, IC, DD Overlay dd4 |

---

## 2. P4C.3 — 对照组

主组（P4C.1 priority-based）vs 三个对照：

| 组 | 规则 |
|---|---|
| A | main-first（production 当前默认）|
| B | sleeve-first（stress 期 sleeve 抢 BP）|
| C | FCFS（先到先得，按 candidate trigger 时序）|
| **主** | priority-based（P4C.1）|

对比指标：portfolio total P&L / Sharpe / max DD / CVaR 5% / blocked-entry 数量与质量 / worst 20d window。

**Sensitivity**：`(w_q, w_r, w_t)` baseline `(0.4, 0.4, 0.2)` 加 4 组扰动：`(0.5, 0.3, 0.2), (0.3, 0.5, 0.2), (0.4, 0.3, 0.3), (0.4, 0.5, 0.1)`，看 ranking 稳定性。

---

## 3. 已识别风险与开放问题

请 reviewer 直接判断每条是否需要修订。

1. **过拟合**：分桶查表 + z-score 都使用 19y 全样本，会导致 priority 在 in-sample 上 "完美" 排序。是否需要做 walk-forward（如前 13y 训练桶，后 6y 测试）？这会显著增加实施成本。
2. **小样本桶不稳定**：Aftermath 在 19y 只 15 笔，按 4 维分桶大概率每桶 n=1–2。向最近邻聚合是否够稳健？是否需要改用 Bayesian shrinkage？
3. **Z-score 跨策略可比性**：每策略 separately z-score 化后跨策略比较 priority 是否有意义？例如 main BPS NNB 的 +1σ 信号 vs HV Ladder 的 +1σ 信号，二者的"质量绝对值"不同。是否应该改成跨策略归一化（如所有 candidate 一起 rank-percentile）？
4. **Tail penalty 单边**：现在 `tail_penalty` 是 worst trade + |CVaR|。但 sleeve 在 stress 期亏损本身可能就是其设计意图（DD Overlay 抓 rebound 失败时本就该亏）。是否需要把 tail penalty 改成 "conditional on regime" 而不是全样本？
5. **w_t = 0.2 偏低**：tail risk 权重只占 20%，意味着高回报但高尾部的 candidate 容易胜出。这是否符合 PM 的风险偏好？
6. **没有引入 portfolio-level 约束**：priority ranking 只看单 candidate vs 单 candidate，没有考虑"加这笔后 portfolio Greek / CVaR 是否恶化"。是否需要加 portfolio marginal CVaR penalty？
7. **HV Ladder 在 P1/P2 用 V2f baseline 占位 → P4 priority 表是否要重算一次** 当 Q071 final lock 后？这是必然的，但工作量上需要 reviewer 确认能否分两阶段交付。
8. **Production 落地路径**：若 P4C 结论支持 priority-based ranking，意味着 production 也要改成同款 BP 分配规则。这超出 Q072 研究范围，但是否要在 brief / memo 里预先标注 "如采用此规则，需开 SPEC-xxx"？

---

## 4. Review Questions（请明确回答）

**Q1 — Formula 合理性**
priority = 0.4·signal_quality + 0.4·return_per_bp − 0.2·tail_penalty 这个 linear additive 形式是否合适？还是应该用 multiplicative（如 `return_per_bp / (1 + tail_penalty)`）以避免负 priority？

**Q2 — 分桶维度**
4 维 (VIX / IVP / regime / ddATH) 是否过细？若改为 2 维 (regime / IVP) 是否会丢关键信号？或反过来是否还需要加 VIX slope / VIX term 维度？

**Q3 — 小样本与过拟合**
风险 #1 和 #2（过拟合 + 小样本桶）哪个更需要立即解决？walk-forward 必须做还是可以放到 future work？

**Q4 — Z-score 跨策略可比性**
风险 #3——你认为 per-strategy z-score 后再加权排序是否会让"高方差策略容易刷分"？是否应该换成全 candidate 池的 rank-percentile？

**Q5 — Portfolio-level 约束**
风险 #6——priority ranking 只看单 candidate 边际属性，不看入场后 portfolio 状态。这会不会让 P4C 模拟出来的"最优分配"实际上是个高度集中的尾部炸弹？要不要在 priority 公式之外再加一层 portfolio CVaR ceiling？

**Q6 — Tier 平手逻辑**
Tier 1 (稀缺信号) > Tier 2 (HV 常规) > Tier 3 (稳定常规) 这个固定优先级是否过于 ad-hoc？或者应该让稀缺度自然通过 signal_quality z-score 体现，不要再额外加 Tier？

**Q7 — 对照组充分性**
对照 A/B/C 是否够？要不要加一个 "static cap per sleeve"（如 main 70% / DD 10% / Aftermath-BPS_HV 15% / HV Ladder 独立）作为简单 baseline 验证 priority 是否真比 hard cap 好？

**Q8 — 开 P1 前的 blocker**
有没有任何 P4C 设计问题严重到需要 **stop P1 launch** 直到修复？还是 P4C 的修订可以与 P1/P2 并行做（反正 P4 在 P3 之后才跑）？

---

## 5. 不在范围（本轮 review）

- P1 episode 定义、P2 entry profile、P3 path/Greek/co-loss、P4A/B 口径——round 1 已 PASS
- Greek 重建方法、scenario decomposition——round 1 已 PASS
- HV Ladder 时机分阶段——round 1 已 PASS

---

## 6. 参考

```
research/q072/q072_research_brief_2026-05-15.md       ← 完整 brief（含本轮焦点 P4C.1/C.3）
task/q072_sleeve_global_eval_design_review_2026-05-15.md       ← Round 1 packet
task/q072_sleeve_global_eval_design_review_2026-05-15_Review.md ← Round 1 review (PASS w/ revisions)
research/q042/baseline_19y_trades.csv                 ← P4C priority 分桶数据源
research/q064/q064_p1_daily_flags.csv                 ← P1/P4C BP 竞争日识别
research/q066/q066_memo_2026-05-12.md                 ← Greek snapshot / co-firing 原型
```
