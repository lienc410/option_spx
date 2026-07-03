# Q083 P16 — Lockout 度量正式验收 + 2021 post-COVID 侧重评估（收尾附录）

**日期**: 2026-07-03
**来源**: Fable 外部独立 review（`task/q083_fable_external_review_2026-07-03.md`）发现 Q083 全程未用 PM 原始度量（可交易频率 / 锁死时长）验收 SPEC-113。本文档补齐该验收，并按 PM 指示以 2021 post-COVID 环境为侧重复评。
**复现**: `research/q083/q083_p16_lockout_metrics.py`（数据源 `research/q078/_signal_history_cache.csv`，生产 selector 全量输出 2000-2026，6,639 交易日，pre-SPEC-113 基线）

---

## 1. Lockout before/after 正式验收表

| 度量（PM 原始度量） | Before | After | Δ |
|---|---|---|---|
| 可交易日频率（26y） | 3,119 (47.0%) | 3,681 (55.4%) | +562 天 / +8.5pp |
| spike→首笔可交易（29 episode 中位） | ~2td | ~2td | 不变（从来不是问题：spike 期 HV 策略照常开） |
| spike 后 250td blocked 密度（均值） | 154 | 131 | **-15%** |
| spike 后 250td blocked 密度（中位） | 164 | 129 | **-21%** |
| 零改善 episode | — | — | 9/29 |
| p95 连续锁死段 | 24td | 17td | -29% |
| 历史 ~7 个月锁死（2 段） | 155td / 155td | **35td** / 155td | 2002-03 型修复；2008-09 型保留 |
| carve 零触发年份 | — | — | 12/27 年 |

**SPEC-079 修正（本次新发现）**: comfortable-top filter 在 carve 内**结构性失效**——risk_score=3 需三条全中，第一条 VIX≤15 在 NORMAL carve（VIX∈[15,18)）内仅 2/562 天可满足（min VIX=15.0）。因此上表 "after" 不是上界，是**精确值**（仅 SPEC-111 现金门未建模）。

## 2. 2021 post-COVID 侧重评估（PM 指示 2026-07-03）

**核心事实：2021 是 26 年样本中 pre-fix 锁死最严重的一年**——blocked 220/252 天（87.3%），比 2008（200）和 2003（209）都严重。PM 的体感抱怨在数据上精确成立：post-COVID decay 年就是历史最锁死年。

| 2021 度量 | Before | After |
|---|---|---|
| blocked 天数 | 220/252 (87.3%) | 116/252 (46.0%)，**-104 天，全样本最大年度改善** |
| 年内最长锁死段 | 62td | **15td** |

Carve 天分布：2021-04 至 2021-12 横跨 9 个月（104 天），VIX 中位 16.72，IVR 中位 4.9（典型 post-spike IVR 地板）。

**交易层面（P11 sim，~25 天持有，串行 ladder）**：2021 年 8 笔，6/8 胜，合计 **+$18,895**，中位 debit ~$19.9k。逐笔：4/12 (+$4,184)、5/7 (-$725)、6/2 (+$4,375)、6/29 (+$5,930)、7/26 (+$1,096)、10/18 (+$7,545)、11/12 (+$955)、12/23 (-$4,465)。

**SPEC-111 叠加（$37k 基线现金）**：8 笔中 1 笔（2021-12-23，debit $22,876 > $22.2k cap）会被 cap 挡掉——恰好是最差一笔（-$4,465，n=1 巧合，不作为 cap 有效性证据）。实际可执行 7/8。

**2020 本身零 carve 天**：carve 在 spike 后 ~12-14 个月（VIX 衰减进 [15,18) 且 IVR 仍地板）才激活；spike 年本身靠 HV 策略（2020 blocked 仅 42%）。未来 COVID 型事件的预期时间线：spike 年 HV 策略部分可交易 → 间隙 → decay 年 carve 接管。

**脚注**：P11 carve 内 46 笔按 raw PnL>0 计胜率 31/46=67%，与 SPEC-113 packet 报告的 73% 有口径差（P13 skew-bracket 记账），不影响结论，记录备查。

## 3. 结论变更评估：**不变，且被强化**

- 总 verdict 维持 PARTIAL SOLVE；对 2021 型（post-COVID QE-decay）环境单独评估升级为 **SUBSTANTIALLY SOLVED**（blocked -47%，最长锁死段 62→15td，年度 +$18.9k 序列可兑现）。
- 原 review 的"上界"caveat 移除（SPEC-079 在 carve 内失效）。
- 唯一实质性 conditional：SPEC-111 现金状态。现金 <$37k 时 cap 逐步挡掉高 debit 笔；当前 $16.9k < $30k floor 时 carve 完全 inert。

## 4. PM 决定记录（2026-07-03）

1. **2008 型 Layer-1 锁死正式列入"不修范围"**——PM 原始抱怨中"一次 spike 锁死 6-10 个月"的 2008 型实例（2008-09-04→2009-04-16，155td）为求生 veto 设计意图，永久保留，不再作为未解决项追踪。
2. **VIX 18-20 sub-bucket 复检 = 条件项**（非排期任务）：触发条件为更好的 skew 面数据可得、或该 VIX 段样本显著扩大。触发前该段维持 reduce_wait。
3. **Q084 立项注册**：NORMAL×LOW×NEUTRAL 非方向策略研究（见 `research/q084/q084_framing_memo_2026-07-03.md`）。
