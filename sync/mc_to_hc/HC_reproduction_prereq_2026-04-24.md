A. 决策类（必须 PM 落锤，否则 Quant/Dev 无法继续）
A1. 解决 §6 拍板表的 D1–D6（D7=Q019 与本轮无关）

| 序 | 决策 | 选项 | 默认建议 |
|---|---|---|---|
| D1 | C4（SPEC-070 v2 delta-based 长腿）是否在 HC 复现 | (a) 复现 / (b) 不复现 | **(a) 必须复现**——HC 端语义错配真实存在 |
| D2 | C3（SPEC-068 per-strategy spell throttle）是否在 HC 复现 | (a) 复现（防御性）/ (b) 不复现，记 reopen trigger | **(a) 复现（防御性）** |
| D3 | C5（SPEC-071 broken-wing）是否在 HC 复现 | (a) 复现 / (b) 不复现 | **(a) 复现**——但必须先 D1 |
| D4 | MC SPEC-071 的"short delta 0.12（vs HC 0.16）"是否被 PM 默认接受 | (a) 接受 / (b) 追问 MC 文档漂移 | **(b) 先追问**——v3 文档未显式列出 |
| D5 | C6（SPEC-073 BEAR_CALL_DIAGONAL 清理）是否在 HC 复现 | (a) 复现 / (b) 不做 | **(a) 复现**——0 行为变化、低风险 |
| D6 | HC 是否补建 SPEC-068/070v2/071/072/073 的 HC-side spec 文件 | (a) 全补建走 APPROVED / (b) PM 直接接受 MC spec 文本 | **(a) 补建**——保持治理一致性 |
| D7 | Q019 走 A / B / C | A / B / C | 之后决定 |


A2. Spec 编号占用策略

HC 是否直接沿用 MC 编号 SPEC-068 / 069 / 070 / 071 / 072 / 073，有冲突编号，把MC的编号后加“-MC”


A3. Live 影响窗口
C4（delta-based 长腿）一旦合入，old Air 上 com.spxstrat.bot 实时推荐里 IC_HV 的 long strike 会立刻变化 
PM 必须选定：(a) 先在 staging 跑、对照一段时间再 ship；(b) 选一个市场低波动窗口直接 ship；(c) freeze 当前 live 直到全部 C4+C5 ready 一次性 ship
选C

==========
B. 信息类（PM 需要找 MC 拿回答，再启动复现）
现在空缺

C. 安全类（动手前必须就位）
C1. 基线快照 / 回滚预案

在动 engine.py:_build_legs 前打一个 git tag（建议 pre-spec070-baseline-2026-04-24）
记录当前 SPEC-066 全历史 trade log 作为 regression baseline（行数、PnL、Sharpe、MaxDD、2026-03-09/10 两笔的精确 strike）
这是后面验证 C4 改动副作用的唯一参照系
PM 只需口头同意即可，由 Quant 执行 -- Approved

C2. SPEC-067 / /ES runtime safeguards 的优先级

PROJECT_STATUS.md 把它列为 B1 顶级阻塞
PM 要选：(a) 先做 SPEC-067，HC 复现排在它后面；(b) 并行；(c) HC 复现优先，SPEC-067 后置
选C