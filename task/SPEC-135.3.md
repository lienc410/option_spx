# SPEC-135.3 — Trace 语义修复 + 搬家首页（PM 发现呈现缺陷 2026-07-07 深夜，P0）

**缺陷**: decision_trace.py:194 敞口提示节点 degraded 时 outcome="veto"——词汇表缺"提示不拦"档位，UI 渲染成红色拦截，位置又在末尾附注组 → 被读成"最终拦截理由"。PM 实测误读。决策逻辑无恙（selector bit-identical + final verdict 与 rationale 相等断言均在），纯呈现语义缺陷。

## 1. Outcome 词汇表补档（P0）

- 新增 `"advisory"`：评估为真、改变语气/通知、**不阻止任何东西**
- `family_exposure_degrade` degraded → **advisory**（琥珀 ⚠，图例文字"提示"）；pass 不变
- **红色 ⛔ 只留给真拦截**（halt / 会阻止推荐或需 pm_override 的 veto）——cash_floor/cash_budget 的 veto 语义保留（它们在 open API 有真实拦截路径 + override），但 detail 文案补"手动单可 override"说明
- AC：outcome=advisory 的节点断言 label/detail 含"不拦"语义且 UI 类非红；**7/7 固定用例重渲染全图恰好一个红节点（G2）**；exposure degraded 生产向量 ⚠ 渲染

## 2. Decision Trace 搬家首页（PM 指令）

- **Portfolio Command Center 顶部新增 Lane A 锚点摘要卡**：3 锚点行（135.1 渲染规则）+ "展开完整决策链"进全 trace 区块（全图可留 /spx 或首页折叠，dev 定，移动端注意）
- 首页 SPX 策略卡的理由区**改为渲染 trace 锚点序列**（候选→刹车→结论 的浓缩行），弃用单独截取的 rationale 长文本——**与 trace 同一 copy 源**（PM 指出的"不完整也不一致"根因是双源）
- AC：首页锚点摘要与 /api/decision-trace 锚点逐字一致断言；G2 文案不再以裸长文本出现在 SPX 卡（由锚点行 + hover 承载完整 detail 含 pm-clear 命令）

## 3. 图例（人话）

图例常显：`● 通过 · ⚠ 提示（不拦） · ⛔ 拦截 · ▶ 今日结论`——一行教会读图。

## 边界

不动 selector/exposure 计算逻辑（纯 trace 组装与渲染层）；135.1 恒等合同沿用（outcome 值变更仅限 exposure 节点 degraded 分支，测试向量同步重生成并注明）。
