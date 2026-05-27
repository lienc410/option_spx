# Q076 Phase 2 — PM Verdict on 2nd Quant Review

**Date**: 2026-05-26
**Reviewer source**: `task/q076_phase2_2nd_quant_review_2026-05-26.md` + Quant P2 memo `research/intraday/q076_p2_findings_2026-05-26.md`
**PM verdict**: **A2a + B accepted as Q076 Phase 2 verdict**

---

## Top-line

> **Q076 只做 execution governance，不改 selector 本身。Low-IVP entry-only 另开 SPEC / research。**
>
> **"先修什么时候可以交易的治理层，不要顺手改策略本身什么时候该关的语义层。"**

---

## Decision

| 选项 | 评价 |
|---|---|
| **A2a + B** | ✅ **ACCEPTED** — governance-only, 不动 selector semantics |
| A2b 单独 | ❌ 拒绝 — 改 selector semantics，out-of-Q076-scope |
| A2b + B | ❌ 拒绝 — 同时推两件会让 audit 混乱 |
| B only | ❌ 不通过 hard targets，但保留作为 cadence 层 |

### Edge clarification

- A2a + B 与 A2b 在本 21-day 样本数据等价（同 3 round-trips / -53% flips / 90.5% EOD agreement）—— 选 A2a + B 是**治理边界**判断，不是数据偏好
- A2a 单独 -40% flips FAIL hard target 是因为 production "low-IVP 强制 close" 设计本身贡献 churn —— 但**这个设计语义不在 Q076 范围**，由另开的 SPEC 处理

---

## Four-step execution path

### Step 1 — 写正式 P2 memo ✅ 已完成
`research/intraday/q076_p2_findings_2026-05-26.md`

明确写：
- A2a + B 是 governance verdict
- A2b 是 economically interesting 但 out-of-scope
- B only 不解决 root cause 但保留作为 scheduled-action layer

### Step 2 — P3 robustness（待启动）
扩展 6-12 个月 hourly 数据，验证 A2a + B 不在其他 regime 误伤：

- HIGH_VOL（VIX ≥ 22）期：governance 不应在 IVP 锁高位时频繁 fire
- Deep LOW_VOL（VIX < 14）期：A2a 的 IVP < 35 close 是否突然激活
- Shock 期（2024-08 vol spike / 2025-04 tariff shock）：hysteresis 是否反应太慢
- Hard exits（stop / stress / second-leg / R6）：必须仍然即时

### Step 3 — 起 SPEC（P3 通过后）
**SPEC name**: Intraday Recommendation Governance

Scope:
1. 双侧 IVP hysteresis state machine（entry 42-53 / hold 35-57）
2. Scheduled actionable evaluation at 10:30 / 15:30 ET
3. Hourly UI 降级为 state observation（snapshot, not actionable command）
4. Stop / stress / second-leg 保持 immediate hard exit
5. Override logging（baseline says X but executed Y because hysteresis）

### Step 4 — 另开 low-IVP semantics research（独立轨道）
**Research seed**: Low-IVP Entry-Only Semantics Review

核心问题：
- IVP < 40 / 35 时，是只阻止新开 BPS，还是也应该关闭已有 BPS？

19y backtest 验证：
1. 哪些历史 trades 因 low-IVP wait 被提前 close？
2. 如果继续 hold，PnL / MaxDD / Worst-20d 怎么变？
3. 对 BPS_NNB / BPS_HV / Aftermath / SPEC-105 booster 影响？
4. 是否改善 theta capture？
5. 是否增加 low-premium / poor risk-reward 持仓风险？

PM prior: 低 IVP 更像 entry block，不一定应该强制 close —— 但需 backtest 验证。

---

## 边界声明（important）

- **不选 C（同时推 governance + selector semantics）** —— 防止未来表现变化时分不清是 hysteresis / cadence 起作用，还是 low-IVP semantics 改动起作用
- Step 2 和 Step 4 可以**并行**：P3 robustness 是 Q076 自身；low-IVP research 是另一条独立轨道
- Step 3 SPEC 起草等 P3 通过后才动
- A2b 永远不直接进 production；如果将来 Step 4 research 证明 entry-only 是对的，那是 SPEC-XXX 的 strategy semantics 变更，不是 Q076 governance SPEC 的一部分

---

## 一句话

> **Q076 = execution governance only. Low-IVP semantics = separate research. 两个轨道，两个边界，不混。**
