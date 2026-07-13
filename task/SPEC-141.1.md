# SPEC-141.1 — 三图接缝三项（PM 批准 2026-07-12）

来源: task/MAP_SURFACES_seams_2026-07-12.md。三件半小时级小活，纯展示层，零逻辑变更。

## 1. State Map ↔ Decision Trace 互链

- trace 卡节点加**稳定 DOM id**（trace_render.js：`id="trace-<check>"`，check 即节点 check 名——已是稳定标识符）
- State Map：Layer 0 四灯 → `/spx#trace-<对应门 check>`（extreme→极端波动刹车节点、second_leg→对应门、caps→治理、cash_floor→资金层 cash_floor）；Layer 2 三引擎卡标题 → `/spx#trace-<lane_d check>`（dd_overlay / aftermath_window / es_ladder；Premium 引擎无单一 lane_d 行则链到 Lane D 区块锚）
- 目标端滚动定位 + 短暂高亮（CSS :target 即可，禁 JS 重逻辑）；链接样式循 DESIGN.md（--text-2 hover --text，不喧宾）
- **AC**: 每灯/卡可点、目标存在断言（id 集合与 trace 节点 check 名同源生成，防漂移）；hover title 注明"查看决策链对应节点"

## 2. badge 词汇映射入 DESIGN.md

Signal-outcome states 节加一小表：

| State Map（引擎运行态） | Lane D/词表 | 语义 |
|---|---|---|
| ON | （无对应，当日被路由） | 今天主策略路由到该引擎 |
| STANDBY | ARMED / CALM / NO ENTRY | 待命，未被路由 |

明确：ON/STANDBY 是 State Map 专用的"路由态"轴，与 Action State 词表（持仓/信号态）**并存不互替**；页面内不得混用两轴词。
- **AC**: DESIGN.md 表落地 + Decisions Log 行；state_map/trace 模板静态扫描无跨轴借词

## 3. nav 日期错位修复

nav 右上日期显示 07-13 而页面数据 07-12——定位时区根因（疑 UTC/date() 无 TZ），统一为 **ET 交易日语义**（与全站数据口径一致）。
- **AC**: 根因写进 commit message；周日晚 ET 断言显示 ET 日期；nav 单源（_nav.html）改一处全站生效

## 交付约束

worktree 隔离；推分支 `spec-141-1` 不碰 main 不部署；测试用 repo venv；全量零新增失败；Quant 合并验收（browse 实点互链）后统一部署。回报：commits+AC 逐条+SPEC 与现实冲突不静默改。
