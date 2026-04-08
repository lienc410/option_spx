# SPEC-044: Delta Deviation Display In Open Modal

Status: APPROVED

## 目标

**What**：
1. 在 `Open Position` modal 的 live strike scan 表格中显示 `target delta` 与 `live delta` 的偏差
2. 让用户在录入前一眼看出当前推荐 strike 是否真的接近策略目标

**Why**：
- 当前前端只显示 `Delta`
- 但交易上更关键的是：这个 `live delta` 跟策略要的 `target delta` 差了多少
- 尤其在 `$SPX` live 链质量较差时，用户需要显式看到偏差，而不是只看 scanner 的 `recommended`

---

## 核心原则

- 只改 `web/server.py` 与 `web/templates/index.html`
- scanner 评分与推荐逻辑不变
- 不改 backtest / selector / engine

---

## 功能定义

### F1 — API 增加 delta 对比字段

`/api/position/open-draft` 的 `strike_scan` rows 新增：

```json
{
  "target_delta": 0.20,
  "live_delta": 0.016,
  "delta_gap": 0.184
}
```

说明：
- `target_delta`：该 leg 的目标绝对 delta（正数，如 `0.20`）
- `live_delta`：链返回的实际 delta 的**绝对值**（正数，如 `abs(row["delta"])`）；PUT 原始 delta 为负，取绝对值后统一为正
- `delta_gap`：`abs(live_delta - target_delta)`（始终 >= 0）

三个字段均使用正数，前端无需处理符号。可由 `web/server.py` 在构造 `strike_scan` payload 时补充，不需要改 scanner schema。

---

### F2 — 前端表格列扩展

当前列：
- Strike
- Expiry
- Bid
- Ask
- Spread
- Delta
- OI
- Score

扩展为：
- Strike
- Expiry
- Bid
- Ask
- Spread
- Target Δ
- Live Δ
- Δ Gap
- OI
- Score

---

### F3 — 偏差可视提示

对 `Δ Gap` 增加轻量视觉提示：

- `<= 0.03`：正常
- `0.03 ~ 0.08`：提示
- `> 0.08`：警示

只做颜色或 badge，不新增交互。

---

## 边界条件与约束

- 不改变 scanner 推荐结果
- 不改变点击回填逻辑
- 不新增排序控件
- 不新增 tooltip / modal 二级解释

---

## 不在范围内

- 自动拒绝高 `delta_gap` 候选
- 自动扩大扫描窗口
- 修改评分公式

---

## 验收标准

1. **AC1**：`/api/position/open-draft` 的 `strike_scan` rows 带 `target_delta / live_delta / delta_gap`
2. **AC2**：`Open Position` modal 表格显示新增列
3. **AC3**：推荐/点击回填逻辑保持不变
4. **AC4**：高 `delta_gap` 行有明显视觉提示
5. **AC5**：未配置 Schwab 时页面行为不变

---

## 备注

依赖：
- `SPEC-039`
- `SPEC-040`
- 可选叠加 `SPEC-043`
