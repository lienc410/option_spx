# SPEC-065: Research View Pill — SPEC-064 Aftermath IC_HV

Status: APPROVED

## 目标

**What**：在 SPEC-062 已有的 Research View pill bar 上新增第 4 个 pill，展示 SPEC-064 `HIGH_VOL aftermath` IC_HV bypass 在全历史回测中新增的边际交易集合。

**Why**：
- SPEC-064 已 ship 到生产（commit `0615c97`），但 PM 目前只能在 terminal 对比 handoff 的 32 笔逐笔列表
- Q015 / Q016 pill 已建立"marginal trade set"的浏览范式；SPEC-064 aftermath 同样是 production 相对旧行为的增量，复用同一范式即可
- 未来审计 / 年度复盘需要能在同一张 SPX / PnL 日期轴上直观看到 aftermath 触发点

---

## 核心原则

- **完全复用 SPEC-062 架构**——pill UI、JSON artifact、API endpoint 不新建
- **只加第 4 个 pill**——不重构 pill bar、不改颜色方案、不引入新视觉语言
- **数据口径统一**——同样用"current production ∖ aftermath-disabled variant"的 diff 方法，与 Q015 / Q016 对齐
- **不改回测引擎**——generator 通过 monkey-patch `sel.AFTERMATH_PEAK_VIX_10D_MIN` 关闭 aftermath 即可

---

## 功能定义

### F1 — Generator 增加第 4 个 view

在 [backtest/research_views.py](backtest/research_views.py) 的 `build_research_views()` 中：

```python
# 现有三个 view：baseline, q015_ivp55_marginal, q016_dza_recovery_bps
# 新增：
bt_no_aftermath = _run_with_aftermath_disabled()
no_aftermath_ids = {_trade_identity(t) for t in _closed_trades(bt_no_aftermath.trades)}
spec064_trades = [
    t
    for t in baseline_closed
    if _trade_identity(t) not in no_aftermath_ids
    and t.strategy.value == StrategyName.IRON_CONDOR_HV.value
    and "aftermath" in t.rationale
]
```

新 helper：

```python
def _run_with_aftermath_disabled() -> BacktestResult:
    import strategy.selector as sel
    orig = sel.AFTERMATH_PEAK_VIX_10D_MIN
    sel.AFTERMATH_PEAK_VIX_10D_MIN = 999.0  # 禁用 aftermath 判定
    try:
        return run_backtest(start_date="2000-01-01", verbose=False)
    finally:
        sel.AFTERMATH_PEAK_VIX_10D_MIN = orig
```

**注意**：筛选同时用 `strategy == IRON_CONDOR_HV` 和 `"aftermath" in rationale`，可以精确命中 SPEC-064 bypass 触发的交易（排除 displacement 带来的误杂入）。预期 trade 数 ≈ 32（与 SPEC-064 handoff 一致）。

### F2 — JSON schema 扩展

`data/research_views.json.views` 增加一个 key：

```json
{
  "spec064_aftermath_ic_hv": {
    "label": "SPEC-064: Aftermath IC_HV",
    "description": "HIGH_VOL aftermath (10d peak VIX ≥ 28, ≥5% off peak, VIX < 40) 窗口 IC_HV bypass 触发的边际交易",
    "trades": [ <trade_obj>, ... ]
  }
}
```

`<trade_obj>` 复用 SPEC-062 既有字段；`source_view` 填 `"spec064_aftermath_ic_hv"`。

### F3 — 前端 pill 增补

在 [web/templates/backtest.html:942-949](web/templates/backtest.html#L942-L949) 的 pill bar 末尾加一个按钮：

```html
<button class="research-pill" data-view="spec064_aftermath_ic_hv" onclick="setResearchView('spec064_aftermath_ic_hv', this)">SPEC-064 Aftermath</button>
```

切换行为、蓝色高亮、banner 逻辑与现有 pill 完全一致（SPEC-062 F3 + F4 已覆盖）。

### F4 — SPX 图表 marker 联动（SPEC-063 兼容）

SPEC-063 已实现"切换 pill 时同步 SPX chart marker"。因本 pill 数据符合同一 schema（`entry_date` / `exit_date` / `strategy_key`），应**自动兼容**，不需额外改动。

需验证：
- 切换到 SPEC-064 pill 时 SPX chart 出现对应的蓝色 entry / 橙色 exit marker
- 日期范围需涵盖 trade 时间段（与 Q015/Q016 同样的注意事项：10Y 或 All period 才能看到跨年数据）

---

## In Scope

| 项目 | 说明 |
|---|---|
| Generator 新增 `_run_with_aftermath_disabled` helper | monkey-patch 关闭 aftermath |
| JSON view key `spec064_aftermath_ic_hv` | 32 条 IC_HV aftermath 交易 |
| 前端第 4 个 pill 按钮 | 复用现有蓝色 research-pill 样式 |
| SPEC-063 SPX chart marker 联动 | 自动兼容（无需改动）|

## Out of Scope

| 项目 | 理由 |
|---|---|
| 单独颜色方案区分 | 与 Q015/Q016 同属 post-ship 边际视图，无需区分 |
| 显示 displaced baseline IC_HV（12 笔）| 第一版只展示 bypass 新增触发，不展示置换损失 |
| Generator 自动触发 | 仍手动跑 `python -m backtest.research_views generate` |
| Research equity curve | 沿用 SPEC-062 决定，trade log + metric cards 即可 |
| 修改 SPEC-062 已有 3 个 pill 的定义 | 本 SPEC 仅新增 |
| 命名改 pill 文案、改 banner 模板 | 沿用 SPEC-062 模式 |

---

## Data Contract

### 输入
- `run_backtest(start_date="2000-01-01")` baseline（sel.AFTERMATH_PEAK_VIX_10D_MIN=28.0，即当前生产默认）
- `_run_with_aftermath_disabled()` variant（sel.AFTERMATH_PEAK_VIX_10D_MIN=999.0）
- diff 逻辑：`baseline.trades ∖ variant.trades` 后再用 `strategy == IRON_CONDOR_HV and "aftermath" in rationale` 收尾过滤

### 输出
- `data/research_views.json` 多一个 key（`spec064_aftermath_ic_hv`），预期增量 ~32 trades × ~200B = ~6KB
- 总体 artifact 仍 < 100KB

---

## 边界条件

- **generator 不能改 AFTERMATH 三阈值**（28 / 10 / 0.05）——只能开关（`999` vs `28`）；未来若要参数 sweep，另行新建 SPEC
- **筛选双条件必需**：`strategy == IC_HV AND "aftermath" in rationale`。只用 diff 会混入 displacement effects；只用 rationale 匹配在 bypass 没生效时是空集——双条件才精确
- **与 Q015 pill 无交互**：两者都基于 current baseline 的 closed trades，互不干扰

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | `python -m backtest.research_views generate` 成功再生，JSON 包含 4 个 view key | jq |
| AC2 | `spec064_aftermath_ic_hv.trades` 数量 = 32 ± 3（容差允许市场数据微动）| JSON 数组长度 |
| AC3 | 每笔 trade 的 `strategy == "Iron Condor (High Vol)"` | jq 筛选 |
| AC4 | 所有 trades 的 `entry_date` 日期对应 rationale 含 `aftermath` 字符串 | 采样验证 |
| AC5 | Backtest page 出现第 4 个 pill，按钮文案 `SPEC-064 Aftermath` | 页面加载 |
| AC6 | 点击 pill 后 trade log 切到 aftermath 子集，banner 显示对应 label/description | 手动点击 |
| AC7 | Metric cards 显示 aftermath 子集汇总（n=32，total PnL 正，win rate ≈ 跟 handoff 数据一致）| 数值核对 |
| AC8 | 切换到 SPEC-064 pill 时 SPX chart 自动显示蓝色/橙色 marker（SPEC-063 联动）| 视觉检查 |
| AC9 | 切换回 Production / Q015 / Q016 三个 pill 行为不变 | 回归点击 |

---

## Prototype / Reference

- SPEC-062 pill 架构：[task/SPEC-062.md](task/SPEC-062.md)
- SPEC-063 SPX marker 联动：[task/SPEC-063.md](task/SPEC-063.md)
- SPEC-064 aftermath 32 笔原始数据：[task/SPEC-064_handoff.md](task/SPEC-064_handoff.md) L31-L62
- Generator 现状：[backtest/research_views.py](backtest/research_views.py)

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-04-19 | 初始草稿 — SPEC-064 ship 后，Research View 第 4 个 pill | DRAFT |
| 2026-04-19 | PM 批准 | APPROVED |
