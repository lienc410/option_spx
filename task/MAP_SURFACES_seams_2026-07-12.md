# 三图一表入口关系评估（SPEC-141 收官触发，Quant 2026-07-12）

## 分工现状（健康，无需改动）

| Surface | 回答的问题 | 组织轴 |
|---|---|---|
| State Map（SPEC-141） | 现在在哪 | 四层架构（否决→状态→引擎→资源） |
| Decision Trace（SPEC-135.x） | 为什么是这个结论 | 四泳道因果（开仓→持仓→地形→引擎） |
| Structure Map（SPEC-132.x） | 地形长什么样 | 价格空间（墙/簇/线） |
| Portfolio home | 今天做什么 | 行动优先（hero 条 + Today's Actions） |

验收记录：141 零推送钩子契约兑现（state_surface 零 gateway 引用）✓；hero 条与 trace 锚点内容正交无重复 ✓；页面零 console 错误 ✓；SPEC-142 轴翻转 FYI 合宪（事件语义+quiet+禁建议词）✓。F3 实战复验：7/12 E-Trade 再缺席，头条 −$160(−0.03%) 同口径+标注，无假跌 ✓。

## 接缝三项（小活，PM 路由归属）

1. **缺互链**：State Map Layer 0 灯 ↔ Trace Lane A 对应门节点、Layer 2 引擎卡 ↔ Lane D 行——同源事实零链接，"灯为什么红"需手动导航。建议：灯/引擎卡加 deep link（纯 `<a>`，零逻辑，跨两文件 state_map.html + trace 锚点 id）。
2. **badge 词汇双轨**：State Map 引擎 ON/STANDBY vs Lane D ARMED/HOLD/CALM/NO ENTRY——语义有对应，映射未成文。建议 DESIGN.md badge 词表加一行映射（ON=今日被路由；STANDBY≈ARMED 待命），防漂移。
3. **nav 日期错位**：nav 右上 07-13 vs 页面数据 07-12（疑 UTC 时区）——归 141 lane 核。

另：全量 1140/1141（1 个顺序相关既有 flake，复跑全绿，dev 曾记录）——flake 定位列入下轮清扫池。
