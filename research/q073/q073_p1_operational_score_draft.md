# Q073 P1 — Operational ROE Score (DRAFT / pre-compute)

> **Status: DRAFT / pre-compute snapshot.**
> **This is NOT a completed P1 deliverable.**
> Qualitative scoring based on Quant's review of code / SOP / Telegram bot logic / PM-side intervention frequency.
> PM should adjust scores based on actual daily experience.
> Full P1 quantitative version (entry frequency, manual override count, alert latency, etc.) still pending.

**Date**: 2026-05-17
**Parent**: `q073_p0_anchored_memo_2026-05-17.md`

---

## Scoring Framework (per 2nd Quant Blind Spot 3)

每个策略 4 个维度，0-10 评分 (0 = lowest cost / highest readiness, 10 = highest cost / least automated):

| Dimension | 含义 |
|---|---|
| **Daily attention** | 每天平均 PM 需投入注意力 (盯盘 / decision / fill confirmation) |
| **Execution complexity** | 入场 / 平仓 / roll 操作复杂度 (legs / 强平时机 / margin 检查) |
| **Failure mode severity** | 一旦操作错误 / 漏看, 最坏可能损失多大 |
| **Automation readiness** | 当前是 fully automated (0) / Telegram alert + manual (5) / 纯人工 (10) |

总 operational cost ≈ 加权和 (建议 PM 看完后给 weighting)。

---

## Strategy Scores (Quant 初评 — PM 请修订)

### SPX BPS Main (Q041 family)

| Dimension | Score | 理由 |
|---|---|---|
| Daily attention | 4 | Daily recommendation API output + 偶尔 PM 介入。仓位较稳, BPS 1 周左右一笔 |
| Execution complexity | 5 | Spread 4-leg pricing / strike scanner / fill 时机选择, 但有 dashboard 辅助 |
| Failure mode severity | 7 | Stop_mult=2.0 已 enforced, 但 IVP gate 失误或 size 错可见 5-10% NLV loss (今天的浮亏即是) |
| Automation readiness | 5 | Telegram + dashboard 推荐, 但 fill 仍需 PM 手动确认 |
| **Subtotal** | **21/40** | Medium operational cost; main income engine 应有的负担 |

### V3-A Aftermath Overlay

| Dimension | Score | 理由 |
|---|---|---|
| Daily attention | 2 | aftermath window 触发频率低, 触发期间才需关注 |
| Execution complexity | 7 | Broken-wing IC 4-leg + V3-A 特殊 strike 选择 + spell limits 复杂 |
| Failure mode severity | 4 | IC_HV_MAX_CONCURRENT=2 + spell throttle 已限风险 |
| Automation readiness | 6 | Telegram 触发, 但 V3-A 结构需 PM 理解 broken-wing payoff |
| **Subtotal** | **19/40** | Cost vs marginal benefit 需 P1 evaluate |

### HV Ladder /ES (SPEC-101)

| Dimension | Score | 理由 |
|---|---|---|
| Daily attention | 3 | VIX ≥ 22 触发频率低 (~20% trading days). 当前无 signal |
| Execution complexity | 6 | /ES chain scan + naked put fill on ES futures + delta target + multiple slots concurrent |
| Failure mode severity | 6 | naked /ES short put, V2F_STOP_MULT=15 fail-safe 较宽 |
| Automation readiness | 5 | Telegram signal + manual /ES execution (PM 决定 manual 或 paper) |
| **Subtotal** | **20/40** | Trigger 稀疏, 但 trigger 来了操作不简单 |

### Q042 Sleeve A (dd4 lenient)

| Dimension | Score | 理由 |
|---|---|---|
| Daily attention | 3 | Trigger daily check, 实际触发频率低 |
| Execution complexity | 4 | ATM/+2.5% call spread, 2-leg, fill 简单 |
| Failure mode severity | 5 | 10% per-sleeve sizing cap, max loss bounded |
| Automation readiness | 6 | Paper mode, Telegram + manual |
| **Subtotal** | **18/40** | 中等 |

### Q042 Sleeve B (dd15 + MA10 reclaim)

| Dimension | Score | 理由 |
|---|---|---|
| Daily attention | 4 | Watching mode 期间需追 MA10 cross |
| Execution complexity | 5 | 与 Sleeve A 类似但 + watch window 时机判断 |
| Failure mode severity | 5 | 同 sleeve A bounded |
| Automation readiness | 6 | Paper mode, manual |
| **Subtotal** | **20/40** | n=5 thin sample, operational cost 不算高 |

### Q019 Signal 2 sidecar

| Dimension | Score | 理由 |
|---|---|---|
| Daily attention | 5 | A/B 实证期需追 Signal 1 vs Signal 2 差异 |
| Execution complexity | 2 | Sidecar 不入场, 仅 log |
| Failure mode severity | 1 | Sidecar 无 trading 风险, 仅 cognitive load |
| Automation readiness | 4 | Hourly check + Telegram + log file |
| **Subtotal** | **12/40** | 主要成本是 PM 认知 / 决策时间, 不是 trading risk |

### LOW_VOL / IVP-gate idle states

| Dimension | Score | 理由 |
|---|---|---|
| Daily attention | 1 | 无操作 |
| Execution complexity | 0 | 无 |
| Failure mode severity | 0 | 无 |
| Automation readiness | 0 | N/A |
| **Subtotal** | **1/40** | Zero operational cost (但 zero alpha 也是 issue) |

---

## Overall Operational Burden Ranking (PM 默认 weighting 2026-05-17)

**PM lock 的 weighting (per 校准答复 Q7)**:
- failure mode severity: 40%
- execution complexity: 25%
- daily attention: 20%
- automation readiness: 15%

Weighted score per strategy (满分 10):

| Rank | Strategy | Failure×0.4 | Complexity×0.25 | Attention×0.2 | Automation×0.15 | Weighted |
|---|---|---|---|---|---|---|
| 1 | SPX BPS Main | 7×0.4=2.80 | 5×0.25=1.25 | 4×0.2=0.80 | 5×0.15=0.75 | **5.60** |
| 2 | HV Ladder /ES | 6×0.4=2.40 | 6×0.25=1.50 | 3×0.2=0.60 | 5×0.15=0.75 | **5.25** |
| 3 | Q042 Sleeve B | 5×0.4=2.00 | 5×0.25=1.25 | 4×0.2=0.80 | 6×0.15=0.90 | **4.95** |
| 4 | Q042 Sleeve A | 5×0.4=2.00 | 4×0.25=1.00 | 3×0.2=0.60 | 6×0.15=0.90 | **4.50** |
| 5 | V3-A Aftermath | 4×0.4=1.60 | 7×0.25=1.75 | 2×0.2=0.40 | 6×0.15=0.90 | **4.65** |
| 6 | Q019 Signal 2 | 1×0.4=0.40 | 2×0.25=0.50 | 5×0.2=1.00 | 4×0.15=0.60 | **2.50** |
| 7 | LOW_VOL/IVP idle | 0×0.4=0 | 0×0.25=0 | 1×0.2=0.20 | 0×0.15=0 | **0.20** |

**Qualitative summary**: operational burden 中等, 主要集中在 SPX BPS / HV Ladder / Q042 / V3-A 四块。**不要把 weighted score 当作精确量化** — 仅用于 promotion/demotion 讨论, 不进 ROE 数学优化 (per 2nd Quant P0 review)。

---

## Critical Observations

1. **SPX BPS + HV Ladder + Q042 三个 active engine 占 80% operational burden**。如果 P3 决定 retire 某一个 (radical Arch-3), operational burden 显著下降。
2. **V3-A operational cost (19) 与其 standalone PnL 不匹配** — 它是 permission module, marginal value 在 enable other trades. P1 attribution 需算 marginal value / operational cost ratio
3. **Q019 Signal 2 的 12 分主要是 PM cognitive load** — 如果 P1 评估 A/B 实证速度极慢, retire Signal 2 几乎无 trading impact, 释放 PM cognitive
4. **idle states 的 1 分操作成本** vs 大量 idle BP × yield gap — P2A 引入 idle fallback 时, operational cost 会显著上升, 需 trade-off vs ROE upside

---

## Open questions for PM

1. PM 对 Quant 的 4-dim weighting 有 preference 吗? (e.g. failure mode 权重高于 daily attention?)
2. SPX BPS daily attention=4 — PM 实际感受是 "比这低" / "差不多" / "更高"?
3. HV Ladder execution complexity=6 — PM 是否觉得 manual /ES 入场实际更复杂 (8-9)?
4. Q019 Signal 2 PM cognitive load=5 — PM 是否真的每天追 A/B? 还是 PM 现在已经不太看 Signal 2 输出?

---

## What this DRAFT does NOT include (need full P1 compute)

- Actual entry / trigger frequency over 26y per strategy
- Manual override / correction log analysis (从 telegram_bot 和 trading log 抽)
- Alert latency measurement (Signal 1 publish → PM see → fill)
- Failure incident retrospective (历史上有几次 "我漏看了" / "我执行错了")
- Total architecture operational cost expressed in PM-hours / week
