# SPEC-125 — 前端三方 Review 合并修复批（2026-07-06）

**输入**: `task/frontend_content_review_2026-07-06.md`（quant，C1-C6）+ `task/frontend_design_review_2026-07-06.md`（设计，D1-D10 详表）。两文件为真值，此处只列分诊与决策注入。

## P1 — 真 bug 与高危违规（先修）

1. **C1 持仓卡 debit 止盈 50%→60%**（portfolio_home.html:1760,1828）：修复方式**从 API 下发 target 比例**（读 params.profit_target），消灭前端常数；断言批扩展第四镜像（模板 JS 禁止出现 0.50/0.60 字面量）
2. **C2 exit_reason "50pct_profit" 化石**（engine.py:1045）：label 参数化（如 `profit_target`）；迁移注记——历史 trade CSV 的旧 label 映射说明
3. **D1 PAPER badge 双违规**（spx.html:1235 orange；performance.html:127/354 金色 .tag 冒充 LIVE）：统一 badge-obs
4. **D2 matrix 关键 caveat**（matrix.html:860）：--text-muted → --text-2；文案转中文
5. **D4 portfolio_home NLV 状态行 --text-muted**（1954-1987）：**惯犯条款**——修复 + 断言（模板禁止 --text-muted 用于非占位内容，CI grep）
6. **D7 es_backtest.html:243-261 未闭合 .page-hero 嵌套**：真标记 bug

## P2 — 一致性（第二批）

7. **C3 matrix 免责升级**：页脚列出五个已文档化分歧格（SPEC-060 三格 + aftermath 两格归因）
8. **C4 回测页定价披露**（三方定稿文案，PM 过目）：`Precision B — Black-Scholes（sigma=VIX 平坦）。该口径经真实链校准证实高估 credit 结构收入（Q087 B1/SPEC-120）；校准口径重跑见 research/q087。` 
9. **D3 hvladder_backtest Trading Discipline 非规范类名 + 缺类目**：转 canonical .discipline-*，补 Frequency；两回测页补缺指标卡
10. **D5 action-state 词汇统一**：同屏 NO ENTRY vs WAIT 归一（按 DESIGN.md 表）；≥10 个词汇表外 badge 清理或入表
11. **D6 导航单源化**：nav 组件化（单一 include/模板宏），DESIGN.md §Navigation 同步更新；去除 portfolio_home:1093 橙色 RESEARCH 指示（违规）
12. **D8 /ES 生命周期表述统一**（quant 真值注入）：**active，tier=RESEARCH，live=SPEC-061 单张路径**（credit stop bot 监控中）；删除 "Legacy/no longer trading/[archived]" 三处错误表述；ladder 披露文案维持 124 版
13. **D10 Q042 页题改 "Drawdown Overlay"**（路由不动）；标题字号/字族按 DESIGN.md 刻度归一

## P3 — 决策注入项

14. **D9 中文按钮**: 通用页 4 处 `↩ 全局` 改英文；**funds/partnership/etrade_reauth 建议豁免**（个人工具页，PM 默认豁免，异议再改）——豁免写入 DESIGN.md 语言规则
15. **C6 证据流无展示面**: 建议**有意不展示**（后台数据流，PM 需要时看 jsonl/月度摘要），决策记录于 DESIGN.md decisions log

## AC 要点

C1 修复后持仓卡 target 与 engine 参数一字同源（integration 断言）；--text-muted 内容级 CI grep 零命中（占位符白名单）；badge 词汇表回归测试；nav 单源后 12 页 diff 一致；D7 HTML 校验通过；全站视觉抽查（design subagent 复验轮）。
