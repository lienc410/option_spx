# SPEC-094.3: Q042 Fill 确认闭环（幽灵仓位防护）

## 目标

消除「有 state 无真仓」的幽灵仓位形态：executor fire 时即写 `active_position_id`（假设 PM 会执行 alert），但 PM 可能不执行——2026-03-12 trigger 即为实例（PM 未下单，幽灵 state 存活至 6 月，挡住 2026-06-10 真实触发，counterfactual ≈ +$95-115k，见 `research/q095/q095_p3_bcd_postmortem_2026-07-11.md` §4 修正框）。这是 SPEC-094.2 N7（有真仓无 state）的镜像方向。

## 策略/信号逻辑

无策略逻辑变更。trigger/armed/re-arm 语义一字不动（armed 消耗 = 研究定义，SPEC-094.2 已确认）。本 spec 只管 **position slot 与现实的对账**。

## 接口定义

### F1 — pending fill 跟踪

executor EOD（settle 与状态级到期清理**之后、`update_sleeve_*` 之前**）扫描两账本中 `fill_debit == null` 且未 settle 的 open 记录：
*（Errata 2026-07-12：初稿"末段"与 AC-94.3-2 的"释放同日可 fire"自相矛盾——fire 条件含 `not has_pos`，扫描放末段则当日 fire 必被幽灵槽位挡掉。Quant 裁决按 AC 语义取位，Developer handoff §④-1。）*

- **每日确认（PM 2026-07-12 修订：替换原 T+2 单次提醒）**：自 entry_target_date 起，**每个交易日 EOD** 发确认提醒（dedupe `q042_fill_reminder_{trade_id}_{date}`，每日一条）："Q042 [sleeve] 触发单第 N 天未确认——已执行请回填 fill_debit；未执行请回复释放（或等 T+5 自动释放）"。
- **T+5** 仍 null → **自动释放槽位（兜底，PM 2026-07-12 确认保留）**：清 `state[sleeve].active_position_id`/`active_position_expiry` + 账本记录打 `phantom: true`（不删，保审计链）+ ACTION 告警："幽灵仓位已释放，sleeve 恢复可触发；若实际已成交请立即补录并手工恢复 state"。连续 5 日提醒未获响应即释放——兜底存在的理由：6 月案例正是零响应场景。
- armed 状态**不回补**（触发已按研究语义消耗；释放的只是 no-overlap 槽位）。

### F2 — 手动 open 端点回写 state（SPEC-094.2 N7 可选项转正式）

`/api/q042/position/open` 成功记录后回写 `state[sleeve].active_position_id = trade_id`、`active_position_expiry = expiry`（幂等：已有相同 id 不动；不同 id 时告警不覆盖——双仓疑似，人工裁决）。使 N7 方向（人工入场→state 同步）与本 spec 方向（state→现实对账）闭环。

## 边界条件与约束

- T+2/T+5 均按交易日；计数起点 = `entry_target_date`。
- dry-run 下 F1 只报告不落盘不告警（沿 SPEC-094.2 F4/B6 语义）。
- `phantom: true` 记录被 F6 committed 计算、settle、lifetime stats 一律跳过（视同 void）。
- 不改 trigger/re-arm/sizing/cap；不改 AC14.1 告警格式（新告警为独立消息）。

## 不在范围内

- 自动撤销/重发 trigger（armed 语义不动）；Broker API 自动 fill 检测（需 order automation，独立 SPEC）；Sleeve B。

## Prototype
（无）

## Review
- 结论：**PASS（Quant fidelity review 2026-07-12）**
  - AC-94.3-1..6 全 PASS（13 tests + 094.2 硬 invariant 22 tests，Quant 亲跑 35 passed）；相邻回归 64+140 零失败；真实 repo dry-run 零落盘。
  - Handoff §④ 11 项取舍逐条裁决全部认可：④-1 F1 取位（update_sleeve 之前）按 AC 语义正确，spec"末段"记 errata；④-2 Sleeve B 纳入扫描（out-of-scope 指策略语义不变）；④-3 槽位 id 不匹配保守不清动；④-6 假日表 2027 到期入运维项。
  - handoff：`task/SPEC-094.3_handoff.md`。
- 审批链：PM 2026-07-11"同意继续推进"（立项）→ 2026-07-12 修订 F1 为每日确认 → 2026-07-12"保留兜底"（APPROVED）→ 同日实施 + review PASS。

## 验收标准

| AC# | 描述 | 验证 |
|---|---|---|
| AC-94.3-1 | 合成 pending（fill null，entry T-3）→ EOD 跑后收到 FYI 提醒且 state 不动 | pytest |
| AC-94.3-2 | 合成 pending（fill null，entry T-6）→ 槽位释放（state 双字段清空）+ 记录 `phantom:true` + ACTION；同日 ddATH ≤ -4% 场景下 sleeve 可正常 fire | pytest 端到端 |
| AC-94.3-3 | fill_debit 已回填的记录 → T+5 后不受任何影响 | pytest |
| AC-94.3-4 | phantom 记录不进 F6 committed / settle / lifetime stats | pytest |
| AC-94.3-5 | F2：手动 open → state 回写；state 已有不同 id → 告警不覆盖 | pytest |
| AC-94.3-6 | dry-run：全部 F1 动作零落盘零推送 | pytest（hash 比对，沿 AC-94.2-5 模式） |

## Handoff Contract

1. **What changes**：`production/q042_executor.py`（F1）、`web/server.py`（F2，仅 open 端点尾部）、`production/q042_positions.py`（phantom 过滤）；账本 schema 增可选 `phantom` 字段。
2. **Invariants**：trigger/armed/re-arm/sizing/cap；AC14.1 告警格式；AC16 隔离；SPEC-094.2 全部 AC 继续绿。
3. **Acceptance checks**：AC-94.3-1..6（正向 AC-2 释放后可 fire；边界 AC-3 已回填不受扰）。
4. **Out of scope**：见上节。
5. **Failure / rollback**：部署后首次 T+5 释放若误清真实仓位（PM 已成交但未回填）→ 按 ACTION 告警指引补录+手工恢复 state；连续 2 次误释放 → 回 Quant 复核 T+5 参数。

---
Status: DONE
