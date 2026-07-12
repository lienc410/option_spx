# SPEC-142: 状态转换通知（结构轴/Vol 轴翻转 FYI）

## 目标

PM 2026-07-13：「即使只是及时告诉我现在不是单边了，这个信号也是有意义的」。把 state_surface 已日更的状态在**发生翻转的当天**推送 FYI——纯当下事实的态势感知，不承担任何前瞻/建议职能。

## 策略/信号逻辑

无路由/参数变更。消费 state_surface 日志（16:50 job 已落盘），当日与前日比对。

## 接口定义

**F1 转换检测与推送**：`scripts/daily_snapshot.py` 的 state_surface hook 之后：比对今日 vs 上一交易日的 `structure_state` 与 `vol_state`；任一变化 → gateway FYI（dedupe `state_flip_{axis}_{date}`）。正文模板：
- 结构轴：`结构轴翻转：{旧} → {新}` + 新状态的当下事实行（RANGE：`已确认：过去 {N}TD 困于 {lo}–{hi}（{band}% 箱）`；TREND：`{方向}破箱 @ {价}`）
- 进入 RANGE 附加弹药行（既有正当配对）：`历史 89% 的 dip 触发源于此状态 → 弹药检查：liquid ${X} vs reserve $78.6k {✓/✗}`
- Vol 轴：`Vol 轴翻转：{旧} → {新}（VIX {x}）`
**F2 禁令（Q098 教训制度化）**：正文**禁止出现任何结构建议词**（IC/BPS/BCD/建议/优先/更适合等）——状态通知只说是什么，不说做什么。
**F3 失败语义**：state_surface 任一字段 n/a → 该轴跳过比对不误报；backfill 行不触发。

## 边界条件与约束

FYI 级（非 ACTION）；每轴每日至多一条；dry-run 沿 094.x 语义零落盘零推送；094.2/3/4 + 141 全部测试保持绿。

## 不在范围内

任何路由/gate/结构建议；日内检测（日频 EOD 即可，与 state_surface 同节奏）。

## Review
- 结论：N/A

## 验收标准

| AC# | 描述 |
|---|---|
| AC-142-1 | 合成日志对（TREND→RANGE / RANGE→TREND / NORMAL→HIGH）→ 各触发一条 FYI，模板字段正确 |
| AC-142-2 | **负向断言**：推送正文不含 {IC, BPS, BCD, 建议, 优先, 更适合, 适合做}（F2 禁令） |
| AC-142-3 | 进入 RANGE 附弹药行；liquid n/a 时弹药行显示 n/a 不阻塞 |
| AC-142-4 | 无变化日/backfill 行/n-a 字段 → 零推送 |
| AC-142-5 | dedupe 幂等；dry-run 零落盘零推送 |
| AC-142-6 | 094.2(22)+094.3(13)+094.4(13)+141(26) 全绿 |

## Handoff Contract

1. **What changes**：`scripts/daily_snapshot.py`（比对+推送 hook）或独立小模块 `strategy/state_flip_notify.py`（Developer 择优，倾向后者便于测试）；零其他文件。
2. **Invariants**：state_surface 计算不动；selector/executor/governance 零 diff；既有告警格式不动。
3. **Acceptance**：AC-142-1..6（关键 = 2 的负向断言）。
4. **Out of scope**：见上。
5. **Rollback**：摘 hook 一行即回退，零策略影响。

---
Status: DRAFT
