# Q083 / SPEC-113 外部独立 Review（Fable model）— "没有交易窗口"问题是否被真正解决

**日期**: 2026-07-03
**Reviewer**: Fable（外部独立视角，per `feedback_kill_gate_external_read` 外审要求）
**Review 对象**: Q083 P0-P15 研究线 + SPEC-113（NORMAL × IV_LOW × BULLISH × VIX<18 → BCD carve）
**数据基础**: `research/q078/_signal_history_cache.csv`（生产 selector `run_signals_only()` 2000-2026 全量输出，6,639 交易日，2026-05-27 生成 = pre-SPEC-113 基线）
**复现脚本**: scratchpad `spec113_lockout_review.py`（本文所有数字可由该脚本 + cache 复现）

---

## 总 Verdict: **PARTIAL SOLVE** — 对真实现象是实质改善，但 PM 字面抱怨的最坏历史实例原样保留，且该修复当前处于 operationally inert 状态

---

## 核心新发现（回答 Q3：此前无人计算的度量）

**Q083 全程 15 个 phase 没有任何一个用 PM 自己的度量（可交易频率、锁死时长）验证过 SPEC-113 的 before/after。** 这是本 review 的最重要 finding——研究线用 Sortino/$净收益/win rate 验收了一个以"交易窗口太窄"为出发点的抱怨。本次补算结果：

### 1. 可交易日频率（26 年，6,639 交易日）

| | Before | After（上界） | Δ |
|---|---|---|---|
| 可交易日 | 3,119 (47.0%) | 3,681 (55.4%) | **+562 天 = +8.5pp** |

"上界"因为 SPEC-079 comfortable-top filter 仍套在 carve 上（`strategy/selector.py:1210-1227` 已确认），且 SPEC-111 cash 门未建模，二者只减不增。

### 2. "VIX spike 后多久才能交易第一笔"——**这从来不是问题所在**

29 个 VIX≥30 spike episode（去重后）：spike 日到下一个可交易日的中位数是 **~2 个交易日**，且 before/after 在全部 29 个 episode 上几乎完全相同。原因：spike 期间 regime 进入 HIGH_VOL，IC_HV / BPS_HV / BCS_HV 照常开放。**PM 抱怨的字面表述（"一次 spike 后 X 个月不能交易"）与实际现象错位**——真实现象是 spike 之后 decay 年内的 blocked 密度，不是"第一笔交易等多久"。

### 3. 真实现象：spike 后 250 交易日内的 blocked 密度

| | Before | After | Δ |
|---|---|---|---|
| 均值 blocked 天数 / 250td | 154 | 131 | **-15%** |
| 中位 | 164 | 129 | **-21%** |
| 零改善 episode 数 | — | — | **9/29** |
| p95 连续 blocked stretch | 24td | 17td | -29% |

改善高度集中于 QE-decay 型 episode：2010-2012（-36~-64 天）、2020-2021 链（2021-01-27 episode：228→121）、2025（164→90）。

### 4. 两段历史级 ~7 个月锁死（PM 抱怨的字面场景）——**修复了一段，另一段原封不动**

| 锁死段 | Before | After | 结果 |
|---|---|---|---|
| 2002-05 → 2003 decay | 155td | **35td** | ✅ 修复（IVR-floor decay 型，正是 SPEC-113 目标） |
| **2008-09-04 → 2009-04-16** | 155td | **155td** | ❌ **原样保留** |

2008-09 段不动的原因：该期 VIX 全程 ≥18（carve 条件不满足）+ 主体是 HIGH_VOL × HIGH × BEARISH（after 仍是最大死格，601 天，占全部剩余 blocked 的 20.3%）= Layer-1 求生 veto（per `feedback_survival_vs_income_layering`，2008 决定"how not to die"，by design 不可交易）。

**这在风险上 defensible，但沟通上有缺口**：PM 的原话是"一次 VIX spike 让账户 6-10 个月不能交易完全不可接受"。SPEC-113 之后，历史上最严重的一次该场景（Lehman decay，7.4 个月）依然会原样重演。如果 PM 的"不可接受"包含 2008 型场景，那么答案应该是明确告知"这类锁死是 Layer-1 设计意图，我们永远不会修"——而不是让 SPEC-113 的 ship 隐含"问题已解决"。

### 5. Carve 触发的年份聚簇（体感维度）

562 个 carve 天的年度分布：**12/27 年为零**（2001, 2005-07, 2009, 2014-18, 2020, 2024）。触发集中在 2003-04、2010-12、2021（104 天，最高）、2023、2025、2026YTD（14 天）。

**含义**：在典型年份，PM 的日常体感不会有任何变化；改善只在特定 regime-decay 年份集中兑现。这不是缺陷（问题本来就集中在那些年），但管理预期时必须说清——否则 PM 在 2024 型年份会再次回来抱怨"还是天天 wait-and-reduce"。

---

## 逐问回答

### Q1: 是解决了抱怨，还是只削了一个薄片？

介于两者之间，偏"解决了抱怨中可解决的主体部分"：

- Carve 覆盖了原死格 NORMAL×LOW×BULLISH 的 **55%**（562/1,023 天）。剩余 45%（461 天，VIX≥18 部分）仍死，是最大的"相邻未修"切片。
- NORMAL×LOW×NEUTRAL（182 天）、NORMAL×LOW×BEARISH（185 天）完全未动。BEARISH 格不路由 bull 策略是 defensible；**NEUTRAL 格是真空白**——需要非方向性 low-IV 策略（calendar / double diagonal），Q083 P0 framing 就把 scope 限定在 BULLISH，这是 scope 决策而非 ship 压力，但空白客观存在。
- 6-10 个月锁死场景：两段历史实例修复其一（2002-03 型），保留其一（2008 型，by design）。

### Q2: "收窄 scope 直到回测好看"是否把原问题 curve-fit 掉了？

**基本没有，但有残余风险**。VIX 15-22 → 15-18 的收窄有 P13 悲观 skew sensitivity 的书面风险理由（[18,20) sub-bucket 在 +8vp short-leg skew 下转弱），不是拟合好看数字。且 carve 后窗口仍覆盖原死格 55% 的天数、26 年 562 天——与触发本次抱怨的 0.16 宽 BPS 窗口完全不是一个量级，不是 P9 那种 2% pass-rate 的 token fix。残余风险在于：VIX 18-20 段的拒绝依据是悲观 bracket 下"转弱"而非"转负"，样本又小——该段值得在更好的 skew 数据下复检，而不是永久关闭。

### Q3: 用 PM 的度量量化实际改善

见上文核心发现 §1-4。**finding 成立：此前确实没人算过这个数**，本 review 补算。三句话版本：可交易日 47.0%→55.4%（上界）；spike 后到首笔交易从来只要 ~2 天（HV 策略在 spike 中照常开，字面抱怨错位）；真实的 decay-年 blocked 密度改善 15-21%，29 个 episode 中 9 个零改善，最坏实例（2008，155td）不变。

### Q4: 其他 gate 是否仍能重现"窄交集"抱怨？

**能，且当前正在发生**：

1. **SPEC-111 现金门（当前）**：实测 liquid cash $16,918 < $30k floor → carve 的实际 fire rate **今天 = 0**。SPEC-113 当前 operationally inert。PM 已知情（"预期状态—暂不动"），无沟通隐瞒，但对"问题已解决"的表述应加 **cash-state-conditional** 限定。
2. **SPEC-111 现金门（即使回到基线）**：今日尺度中位 BCD debit ≈ $22.2k = 恰好等于 $37k 基线下的 60% cap——**边际通过**。现金略低于 $37k，cap 就单独挡掉 carve。P15 已披露此账（+27 天/年低于 floor），PM ratify 为"警戒线"，程序上干净；但要认识到 carve 的实际可用性对现金状态高度敏感，回测的 562 天在实盘中会被现金状态进一步稀释。
3. **SPEC-079 comfortable-top filter**：确认套在 carve 上。562 天是 pre-filter 上界；n=46 笔/26 年的成交密度（≈ 每 12 个信号天 1 笔，受 max-concurrent=1 + 90DTE 占用挤压）才是 PM 会"感到"的频率。

结论：窄交集机制没有被拆除，只是最大的一个交集分量（IVR cell-routing）被打开了 55%。在现金紧张状态下，PM 完全可能再次体验"什么都开不了"——但那时的 binding gate 是 SPEC-111，是 PM 自己 ratify 的资金纪律，性质不同于 Q083 诊断的结构性死格。

### Q5: 更完整的修复长什么样，被拒的理由是否 defensible？

| 未做的部分 | 拒绝理由 | 评价 |
|---|---|---|
| VIX 18-20 sub-bucket（461 死天的主体） | P13 悲观 skew 下转弱 | **Defensible**（风险理由 + 书面记录），但建议标为"待更好数据复检"而非永久关闭 |
| NORMAL×LOW×NEUTRAL 非方向策略 | P0 framing 限定 BULLISH scope | Scope 决策，非 ship 压力；但这是下一个最大的可修死格 |
| 2008 型 crisis-decay 锁死 | Layer-1 求生 veto | **正确拒绝**，永远不该修；缺的是向 PM 显式说明 |

关于"第 4 次迭代终于 ship 一个"的担忧：从证据看 SPEC-113 不是 token compromise（覆盖 55% 死天、562 天/26 年、有独立的今日尺度净收益验证）。但迭代压力的痕迹存在于**验收度量的选择**上——最终用 Sortino/净$验收而没回头用 PM 的原始度量对账，这正是本 review 补上的洞。

---

## 建议的下一步（按边际价值排序）

1. **把本文 §核心发现 的 before/after 表并入 Q083 收尾文档**——lockout 度量应成为该研究线的正式验收记录，防止未来引用时只见 Sortino 不见频率。
2. **向 PM 显式二分锁死类型并取得确认**："可修的锁死"（IVR-floor decay 型，SPEC-113 已修其主体）vs "不修的锁死"（Layer-1 crisis 型，2008，by design 保留）。PM 的"完全不可接受"必须落到具体是哪一类。
3. **Q084 候选：NORMAL×LOW×NEUTRAL 非方向 low-IV 策略**（182 死天，当前零覆盖）——下一个结构性增量。
4. **VIX 18-20 sub-bucket 复检**挂起为条件项（更好的 skew 面数据或样本扩大后）。
5. **SPEC-113 效果的实盘验证前提是现金回到 ≥$37k**——在此之前任何"carve 没触发"的观察都不构成对 SPEC-113 的证据（binding gate 是 SPEC-111，不是 selector）。

## Review 局限

- Cache 截至 2026-05 末，2026-03-27 episode 的 250td 窗口截断（仅 ~50td 可观察）。
- "After" 未建模 SPEC-079 filter 与 SPEC-111 门（只减不增，方向明确），562 天为上界。
- Spike episode 定义（VIX≥30，前置 20td<30 去重）是本 review 自选参数；换 25/35 阈值会改变 episode 集合但不改变"字面度量错位 + 2008 不变 + decay 密度改善"三个定性结论。
