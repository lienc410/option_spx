# SPEC-135.5 — Lane D：Sleeve 决策引擎泳道（审计后解锁，2026-07-11）

**前置已满足**: q042×aftermath×主策略协同审计完结（doc/q042_aftermath_synergy_audit_2026-07-07.md）+ Q093 P1/P2 CLOSED + SPEC-094.2 部署——sleeve 关系与状态面已是审计后的真值，可渲染。PM 原始需求（7/7）："aftermath 和 DDOverlay 是否也该加进 Decision Trace"。

## 设计（第四泳道，与 A/B/C 并列）

**Lane D「其它决策引擎今天的状态」**——每台 sleeve 引擎一行（人话主行 + hover 三件套 + kind/stage 沿 135.1 契约，`stage="sleeve"`）：

1. **DD Overlay**（数据源 `/api/q042/state` + gate log 最新行，全部既有 API 禁旁路）：
   - 主行例：`DD Overlay：双 sleeve 待命中（回撤 −0.9%，距 A 触发线还差 3.3%）`；fire/挂仓时显示仓位与到期
   - **联动线（本泳道的灵魂，PM 问的"相互关系"可视化）**：`与主策略的联动：主策略 BP 占用 15.8% > 12.5% → DD Overlay 本档容量被压缩`（数据 = gate log 的 main_bp/cap/src——094.2 刚修活的 F3 联合门，第一次有可视化面）
   - ATH degraded 时显式标注（F7 语义）
2. **Aftermath**（selector `is_aftermath` 同函数 + /aftermath 数据）：`Aftermath 余波窗口：未激活（需 HIGH_VOL 后 N 日内，当前 NORMAL）`；激活时显示窗口剩余天数与特批结构
3. **Sleeve 压力状态机**（sleeve_governance）：stress episode（stress|dd_overlay|aftermath 合成）、booster/ladder 模式、warm-up 条件读数（ddATH>-4% 等逐条 hover）
4. **ES Ladder**：slots 占用 + blocked 原因人话（现首页已有卡，Lane D 行与卡同源 copy，不重复维护）

## 渲染与边界

- 位置：/spx 完整 trace 第四泳道 + 首页 SPX 卡下方一行摘要（样式同 Lane C 但语义标注不同：**「决策引擎状态」——它们真实决策，区别于 Lane C 的"只描述"**）
- 人话铁律 §0 全套（label_human 与逻辑同居代码、术语英文保留、代号降 hover）
- 各 sleeve 状态词用既有 badge 词表（ARMED/WATCHING/NO ENTRY 等，DESIGN.md Signal-outcome states）

## AC

数据全同源既有 API/生产函数（静态断言零旁路重推）；联动线数值与 gate log 最新行逐字段一致；人话+三件套+双主题+零 console；7/11 快照做固定测试用例（双 sleeve armed + main_bp 15.8%>cap 联动线）；A/B/C 三泳道零回归（135.x 全套复跑）；首页摘要行与 /spx 行同 copy 源。

## 交付约束

worktree 隔离；推分支 `spec-135-5` 不碰 main 不部署；Quant 合并验收（browse 实看双主题整页）后统一部署。
