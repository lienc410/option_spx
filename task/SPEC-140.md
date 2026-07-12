# SPEC-140 — 推送-泳道对齐：真值源合并（PM 提问驱动 2026-07-12）

**判定**: 不做结构合并（推送≠页面，预算不动、不加新推送）；做**文案单源 + 映射契约**——136 对 final verdict/治理门做过的事，推广到 Lane B/D 并把隐式映射写成契约。

## 1. Lane B/D 文案单源（核心）

- trace 装配层的 label 生成函数升格为唯一 copy 源（`decision_trace` 内已有 Lane B 行文与 Lane D 行文）
- 改造消费方 import 同一函数：`bcd_governance` H-5 ACTION 正文（现自写"CLOSE 或 ROLL"版）、digest 持仓行、q042 executor alert 的状态行、ES ladder 状态（135.5 已同源 status_human，验收沿用）
- **AC**: 同一触发器在推送与 /api/decision-trace 对应节点的人话主文**逐字相等**断言（Lane B 21-DTE/collapse 各一例、Lane D halt/联动线各一例）

## 2. Digest 重排为四泳道镜像

15:55 digest 新结构（内容同源，不新增信息量）：
- **A** 今日新仓结论一行（已同源，保持）
- **B** 每个 open 仓一行 = Lane B label 同源（触发器语义入 digest：`持仓 X：短腿 9 天 → 平掉或滚动（已提醒）`），无仓写"今天没有 open 仓位"
- **D** 引擎状态一行 = Lane D 摘要条同源（`DD Overlay ARMED×2 · Aftermath 未激活 · 压力机 CALM · ES Ladder HOLD 1/5`）+ 联动线仅在非"未压缩"档时附一行
- **C 明确不推**（Q090 封账口径），gateway/digest docstring 写死此规则
- 异常区保留（reauth/halt 等 actionable 才升 ACTION 的现行为不变）

## 3. about↔lane 契约 + 深链

- DESIGN.md Push Vocabulary 节加映射表：`关于新开仓=Lane A ／ 关于持仓 X=Lane B ／ 系统状态=Lane D ／ Lane C 永不推送`；gateway docstring 同步
- 推送尾部统一加 `完整决策链 → https://spx.portimperialventures.com/spx`（单用户工具直链；晨报与 digest 加，事件类可选）

## 4. outcome↔category 显式映射

散落实践成文（代码内常量 + 断言）：`halt/veto → ALERT 或 ACTION（真拦截才响铃）；advisory → 语气降级 → STATE/FYI（131 先例）；pass/info → 不推`。防未来新门自行发明严重度。

## 5. 推送哲学入宪（PM 提问驱动 2026-07-13，State Map 判例）

DESIGN.md Push Vocabulary 节新增 doctrine 段（与 §3 映射表同批落）：

> **Telegram = 打断权，预算稀缺**（晨报 1 + digest 1 + 事件铃，PM-ratified）。**推"事件"不推"状态"**：状态活在网页（Decision Trace=为什么 / State Map=现在在哪 / Structure Map=地形），状态跃迁且需行动才配打断；描述层永不推送（Q090 判例）。**三级信息架构**：PUSH（秒级读完，行动导向）→ DIGEST（每日四泳道快照）→ WEB（完整地图，按需拉取）；推送永远是摘要+深链，真值单源在代码。**新 surface 默认零新推送**——新页面不自带推送；其定义的新"需行动事件"按 §4 outcome↔category 映射进入现有预算。判例：SPEC-141 State Map 四层活版 = 纯拉取，零推送钩子；其各层内容的事件语义已由既有推送覆盖（否决灯翻灯→ALERT/digest、引擎=Lane D digest 行、双池=慢变量 digest 级、"贴近触发"≠行动信号不推）。

**AC-5**: DESIGN.md doctrine 段落地 + SPEC-141 实现中零 gateway import 断言（State Map 模块不得携带推送钩子——写进 141 的验收由该 lane 执行，本 spec 提供契约文字）。

## AC 汇总

§1 逐字相等断言×4；§2 digest 快照测试更新（结构 A/B/D + C 缺席断言）+ 收件预算不变断言（分类与 dedupe 行为零变化）；§3 DESIGN.md 表 + 深链渲染；§4 映射常量 + 全 gateway 调用点分类合规扫描；SPEC-136 既有同源断言全部沿用不回退；全量 pytest 零新增。

## 交付约束

worktree 隔离；推分支 `spec-140` 不碰 main 不部署；Quant 合并验收（digest 实发一条对照网页逐字 + browse）后统一部署。
