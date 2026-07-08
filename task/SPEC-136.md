# SPEC-136 — 全站人话化批 A：推送线（audit by quant 2026-07-08 凌晨）

**风格契约**: HUMANIZE_charter 五条 + **单源原则**：凡 trace/governance 已有 label_human 的内容，推送必须同源取用，禁止第二套字符串。

## 改写表（原文 → 人话；出处 file:line 以 grep 为准）

| # | 位置 | 原文 | 改为 |
|---|---|---|---|
| 1 | 晨报头部 | `Action: REDUCE_WAIT / Strategy / Why:...` 平铺 | **第一行 = trace final verdict 人话锚点**（"今日结论：不开新仓"——与 /api/decision-trace final 节点同源 copy），随后才是结构化明细；Why 行保留（本就是 rationale 同源） |
| 2 | 晨报 IVR 失真注 | `(IVP 27.9 used — IVR distorted)` | `期权贵贱按 IVP 27.9（约一年内第 28 百分位）；IVR 本期失真，已改用 IVP`（hover 无处放就直接写全） |
| 3 | ES credit stop | `Credit Stop TRIGGERED [×3 mark]` | `止损触发：权利金已翻至入场价 3 倍（入场 2.50 → 现在 7.50）——规则要求平仓`；Watch 版同理（"接近止损线"） |
| 4 | digest 治理位 | `quote-gate 3/10` 等缩写 | 从 `evaluate_gates_detailed` 的 label_human 同源取（如"低波回归报价门：已积累 3/10 天"）——禁手写第二套 |
| 5 | Ladder drift | `Ladder drift alert: BPS +12pp — review strategy distribution` | `策略分布漂移提醒：BPS 占比高出 90 天常态 12 个百分点——建议看一眼分布` |
| 6 | VIX spike / SPX drop | 英文骨架可留（数字带上下文 ✓） | 仅审 advice 变量文案为完整中文句 + 确认走 gateway about 首行 |
| 7 | 遗留 direct senders 文案 | etrade_status_notify / chain collector alerts | 迁 gateway（137 同批）时顺手人话化 |

## AC

晨报首行与 trace final verdict label 逐字同源断言；digest 治理位与 governance label_human 同源断言；改写表逐条截图/样例入回报；SPEC-126 词表与预算契约不动（仅文案）；测试向量脚本重生成。

## 批 A2（前端字符串）预告

135.4 落地后另行 audit（避免与在飞改动冲突）；trace/结构地图/表单已合规（135 §0 治下），预计残余在旧页面 badge/tooltip。
