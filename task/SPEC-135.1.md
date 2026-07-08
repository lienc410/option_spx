# SPEC-135.1 — Lane A 层级化渲染（PM 反馈 2026-07-07 晚）

**问题**: Lane A 14 行全部同级平铺，结论与依据格式无区别，无法一眼抓重点。

## Trace schema 增量（代码侧，反镜像：层级信息由代码吐，前端零硬编码）

每个 trace 节点新增两个字段（**纯附加**，路由 bit-identical 由既有 gate 恒等合同保障）：
- `kind`: `"verdict"`（阶段结论）| `"evidence"`（支撑检查）| `"final"`（今日结论）
- `stage`: 分组键（market_read / routing / gates / capital / governance / final）——evidence 归属其 verdict 的 stage

## 渲染规则

```
● 手册路由 → Bull Call Diagonal 候选                ← verdict：粗体、大一号、状态图标（●通过/⛔拦截）
    ✓ 波动率在 15-18 温和带（VIX 16.13）             ← evidence：缩进、小一号、--text-2
    ✓ 趋势向上
    ✓ 无宏观预警 · ✓ 死格检查通过                    ← 短 evidence 可同行并列
⛔ 安全刹车 → 暂停开新仓，等待复核                    ← verdict（拦截 = 红/警示色）
    · 家族 18 个月合计 −$6,006，跌破 0 触发线
    · 预注册说明：良好策略每周期约四成概率误踩（要求复核 ≠ 宣布失效）
▶ 今日结论：不开新仓（观望）                          ← final：最大最粗，顶部锚点色条
    附注：同家族敞口 33.5%（阈值 30%）——若今日开仓推荐，语气也会降级
```

- verdict/final 行常显；evidence 组**可折叠**（默认展开桌面/折叠移动端），点击 verdict 行切换
- hover 三件套保留在 evidence 行（135 v3 规则不变）
- 市场读数 stage 无 verdict 语义 → 渲染为单行汇总（读数并列），不折叠

## AC

7/7 固定用例渲染出**恰好 3 个 verdict/final 锚点**（候选→刹停→观望）+ evidence 全部缩进归组；前端零硬编码 stage/gate 清单断言扩展（层级纯由 kind/stage 字段驱动）；kind/stage 字段 strict-JSON + 纯附加（trace 既有字段逐字节不变断言）；折叠交互 + 双主题；/api/decision-trace 向后兼容（无 kind 的历史行按 evidence 渲染降级）。
