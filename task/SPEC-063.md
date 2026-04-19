# SPEC-063: Research View — SPX 时序图联动

Status: APPROVED

## 目标

**What**：Research View pill 切换时，SPX Price — Trade Entry / Exit 图的交易标记同步切换为当前 view 对应的 trades。

**Why**：
- SPEC-062 实现的 Research View 只联动了 trade log 和 metric cards
- PM 需要在 SPX 价格时序图上直观看到研究交易的 entry/exit 位置，才能建立时间-价格-交易的空间直觉
- 当前 SPX 图始终显示 production trades，与下方 Research trade log 不一致，造成认知断裂

---

## 核心原则

- **只换 trade markers**——SPX 价格线、signal overlay、窗口滑块行为不变
- **增量修改**——不重构 `renderSpxChart()`，只替换输入数据源 `_spxChartData`
- **蓝色标记**——Research view 的 markers 使用蓝色系，与 production 的绿/红三角区分

---

## 功能定义

### F1 — Pill 切换触发 SPX chart 重绘

当用户点击 Research View pill（Q015 / Q016）时：

1. 用 research view 的 trades 重新构建 `_spxChartData`（events / ptRadius / ptColors / ptRotation / siblingIdx）
2. 调用已有的 `renderSpxChart()` 重绘
3. SPX 价格底线数据（`_spxFullSigData`）和 overlay 状态不变

切回 Production pill 时，恢复 production trades 的 `_spxChartData`。

### F2 — Research marker 视觉区分

Research view 激活时，trade markers 样式变更：

| 属性 | Production | Research |
|---|---|---|
| Entry marker 颜色 | `--green` (#42CC7C) | `--blue` (#4888E8) |
| Exit marker 颜色 | 红/绿（按 PnL） | 蓝深/蓝浅（按 PnL）|
| marker 形状 | triangle | triangle（保持一致）|

具体色值：
- Research entry: `#4888E8`（蓝）
- Research exit win: `#4888E8`（蓝）
- Research exit loss: `#E08040`（橙，与蓝互补，在深色背景上可区分）

### F3 — 图标题联动

SPX chart 的 `section-title` 文字：

- Production 时：`SPX Price — Trade Entry / Exit`（不变）
- Research 时：`SPX Price — {view.label} Entry / Exit`
  - 例如：`SPX Price — Q016: Dead Zone A Recovery BPS Entry / Exit`

### F4 — Hover connector 保持

已有的 sibling highlight 插件（entry↔exit 连接线）在 Research view 中保持工作。`siblingIdx` 从 research trades 重建即可。

---

## In Scope

| 项目 | 说明 |
|---|---|
| Pill 切换触发 SPX chart 重绘 | 替换 `_spxChartData` + 调用 `renderSpxChart()` |
| Research marker 蓝色 / 橙色 | 视觉区分 |
| 图标题联动 | 显示 research view label |
| Hover connector | 保持 sibling highlight 工作 |

## Out of Scope

| 项目 | 理由 |
|---|---|
| Production + Research 叠加显示 | 第一版只显示当前选中 view 的 markers |
| Equity curve 联动 | 仍只显示 production equity |
| Signal overlay 变化 | overlay 逻辑与 trades 无关，保持不变 |
| 年度 PnL chart 联动 | 保持 production 不变 |
| SPX 窗口滑块行为变化 | 保持不变 |

---

## 技术实现要点

现有数据流：

```
api_backtest trades → buildEvents() → _spxChartData → renderSpxChart()
```

Research 数据流：

```
api/research/views trades → buildEvents() 复用 → _spxChartData 替换 → renderSpxChart()
```

`buildEvents()` 的输入是 trades array（同 schema），所以 research trades 可以直接喂入，无需修改 `buildEvents()` 本身。唯一变化是 marker 颜色逻辑需要接受一个 `isResearch` flag。

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | 点击 Q015 pill 后 SPX 图只显示 Q015 交易的 entry/exit markers | 视觉检查 |
| AC2 | 点击 Q016 pill 后 SPX 图只显示 Q016 的 12 笔交易 markers | 视觉检查 |
| AC3 | 切回 Production pill 后 SPX 图恢复 production markers | 来回切换 |
| AC4 | Research markers 为蓝/橙色，与 production 绿/红有明显区分 | 视觉检查 |
| AC5 | SPX 价格线和 signal overlay 在切换时不变 | 切换前后对比 |
| AC6 | 图标题显示 research view label | 文字检查 |
| AC7 | Hover 时 entry↔exit connector 线正常工作 | 鼠标悬停测试 |

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-04-19 | 初始草稿 | DRAFT |
