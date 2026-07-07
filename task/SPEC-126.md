# SPEC-126 — 统一通知网关（PM 2026-07-06 批准方向与两项决策）

**问题**: 8 个代码位直连 Telegram，无分类/去重/频控/失败处理；语义层混叠（HOLD vs Reduce/Wait 无上下文标签）致 PM 收到"矛盾"消息；15:30/16:03/16:15 三条定时推送重叠。

## 1. 网关 `notify/gateway.py`

唯一发送入口 `push(category, about, title, body, dedupe_key, priority=...)`：
- **category 四分类（强制）**: 🔴 ALERT（需 PM 行动，如 credit stop TRIGGER）/ 🟡 ACTION（建议动作 OPEN/CLOSE/ROLL）/ 🔵 STATE（持仓状态 HOLD 等）/ ⚪ FYI（裁决/快照/例行）
- **about 首行自报（强制）**: `关于新开仓` / `关于持仓 <标识>` / `系统状态`——彻底消灭 HOLD-vs-WAIT 类混淆
- **词汇对齐 DESIGN.md action states**: 新仓裁决推送用 `NO ENTRY`（可注 strategy 名 Reduce/Wait），禁自由文本状态词；DESIGN.md 增补 push-vocabulary 节
- **去重/频控**: dedupe_key 当日一条，仅升级重发；解除类（如 mark 回落）仅跟随当日曾发出的警报，低调（disable_notification）
- **失败处理**: parse 失败→纯文本重发；一次重试；成功/失败计数落盘供 heartbeat 断言（H-4 的网关化收编）
- **静音级**: FYI/STATE 默认 disable_notification（不响铃）；ALERT/ACTION 响铃

## 2. 时段重构

- **保留**: 9:35 晨报（开盘前计划）；日内监控仅在 ALERT/ACTION 条件下发声
- **新增 15:55 收盘前 digest（PM 定点）**: 合并原 15:30 governance + 16:03 snapshot + 16:15 overlay 三条定时推送为一条——结构：今日新仓裁决 / 持仓动作清单 / 治理状态一行 / 异常区（无异常则不出现）。原三条定时任务退役
- **默认降级（PM ratified）**: 治理例行决策、overlay 例行评估**不再单独推送**（进 digest；状态变化时才单推 ALERT/ACTION）；paper/shadow 维持事件驱动静默

## 3. 迁移

8 个现有发送点全部过网关（含 SPEC-123 降级状态机/手动单提示的新推送——若 123 先落地则其后补迁移）；CI 断言：notify/ 与 web/ 内禁止出现网关外的 `send_message` 直连。

## 4. AC

- 分类/about 缺失即 raise；digest 集成测试（三源合并 + 空异常区省略）；parse-fallback 否定测试（构造坏 HTML → 纯文本送达）；去重当日幂等测试；迁移完备 grep 断言；静默日零推送回归；DESIGN.md push-vocabulary 节 + decisions log 条目
- 上线验收：连续 3 个交易日 PM 收件量 ≤ 晨报 1 + digest 1 + 事件驱动 N（N 仅 ALERT/ACTION）

## 5. 验收注记（SPEC-130 补记，2026-07-07）

INCIDENT 2026-07-07：验收期间（7/6-7/7）dev 机 pytest 即污染源——测试夹具推送
经真 token 直达 PM（7/6 sent=68、7/7 sent=187，oldair 同期零发送），两日收件量
数据全部作废。**密闭性先于验收**：SPEC-130 主机 guard（SPX_PUSH_ENABLE
deny-by-default）落地次日起，"连续 3 个交易日收件量" 验收时钟重新计 day 1。
