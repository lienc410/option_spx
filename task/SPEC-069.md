# SPEC-069: Artifact + UI `open_at_end` for Unclosed Positions

Status: APPROVED

## 目标

**What**：在 backtest artifact 与研究 / margin UI 中显式区分"已正常平仓的交易"与"回测末尾仍未平仓的持仓"。后者标记 `open_at_end=True`，UI 用橙色 `OPEN` badge 显示。

**Why**：
- 当前回测引擎只记录 `Trade`（completed 交易），未把回测结束时仍在 `positions[]` 中的持仓写入输出
- 副作用：研究视图与 UI 错误地"丢失"末尾未平仓持仓，导致：
  - 研究者可能误以为某个 spell / aftermath 没产生交易（实际只是未到 exit 条件）
  - live 端做风险拼接时，找不到最近一笔尚未到 50% / 21DTE / stop-loss 的持仓
- MC v3 handoff 列为 artifact / UI 主线复现项

---

## 核心原则

- **不改变 `Trade` 已完成交易的语义**：现有 `Trade` 字段不动；新增 `open_at_end: bool = False` 字段
- **不改变 exit / roll / stop 逻辑**：本 SPEC 只补全 reporting 口径
- **末尾未平仓的"虚拟 trade"**：以当日 mark-to-market 价格作为 `exit_pnl` 的占位，`exit_reason="open_at_end"`，`exit_date=回测最后一日`，`open_at_end=True`
- **UI 用橙色 OPEN badge**：与正常 closed trade 在视觉上即时区分

---

## 功能定义

### F1 — `Trade` 字段扩展

**[backtest/engine.py:85-106](backtest/engine.py#L85-L106)**：

新增字段：
```python
open_at_end: bool = False
```

放在 `bp_pct_account` 之后；保持向后兼容（默认 `False`）。

### F2 — 回测结束时合成虚拟 Trade

**[backtest/engine.py](backtest/engine.py)** 主循环结束之后（`run_backtest` 主体最后、`compute_metrics` 调用之前）：

```python
# Per SPEC-069: synthesise virtual trades for positions still open at end.
last_date = pd.Timestamp(df.index[-1])
last_spx = float(df.iloc[-1]["spx"])
last_sigma = float(df.iloc[-1]["vix"]) / 100.0
for position in positions:
    current_val = _current_value(position.legs, last_spx, last_sigma, position.days_held)
    pnl = current_val - position.entry_value
    short_leg = _short_leg(position.legs)
    short_dte = max(short_leg[3] - position.days_held, 0)
    virtual = Trade(
        strategy=position.strategy,
        underlying=position.underlying,
        entry_date=position.entry_date,
        exit_date=str(last_date.date()),
        entry_spx=position.entry_spx,
        exit_spx=last_spx,
        entry_vix=position.entry_vix,
        entry_credit=-position.entry_value,   # match _close_position convention
        exit_pnl=pnl * _position_contracts(position, account_size) * 100,
        exit_reason="open_at_end",
        dte_at_entry=short_leg[3],
        dte_at_exit=short_dte,
        spread_width=position.spread_width,
        bp_per_contract=position.bp_per_contract,
        contracts=_position_contracts(position, account_size),
        total_bp=_position_total_bp(position, account_size),
        bp_pct_account=_position_total_bp(position, account_size) / account_size,
        open_at_end=True,
    )
    trades.append(virtual)
```

Developer 注：上面是参考实现；具体字段填充需对齐已有 `_close_position` 内部约定，避免双计 `contracts × 100`。

### F3 — `compute_metrics` 中区分 open_at_end

**[backtest/engine.py:504-...](backtest/engine.py#L504)**：

`compute_metrics` 默认对所有 trades 计算。需要决定：
- (a) 把 `open_at_end` trades 排除在 metrics 之外（更保守，避免 mark-to-market PnL 污染 final metrics）
- (b) 包含 `open_at_end`，metrics 反映"如果今日强平的真实状态"

**SPEC 选择 (a)**：metrics 默认排除 `open_at_end=True`；同时在 metrics dict 中新增 `n_open_at_end` 字段记录数量。

```python
closed = [t for t in trades if not t.open_at_end]
# ... existing metric computation runs over `closed`
metrics["n_open_at_end"] = len(trades) - len(closed)
```

### F4 — UI badge 区分

**research view 与 margin 页面**：未平仓 trade 显示橙色 `OPEN` badge。

具体文件 Developer 实施时确认（HC 当前 frontend 主入口在 `web/templates/`）：
- 列表 / 表格中若 `open_at_end=True`，渲染 `<span class="badge orange">OPEN</span>`
- 表格筛选下拉新增 `open_at_end` 选项

---

## In Scope

| 项目 | 说明 |
|---|---|
| `Trade.open_at_end` 字段新增 | 默认 `False`，向后兼容 |
| 回测末尾合成虚拟 Trade | F2 |
| `compute_metrics` 排除 `open_at_end` | F3，新增 `n_open_at_end` |
| UI 橙色 `OPEN` badge | F4 |
| 研究 view artifact JSON 透传 `open_at_end` 字段 | `data/research_views.json` 再生 |

## Out of Scope

| 项目 | 理由 |
|---|---|
| 改变 exit / roll / stop 逻辑 | 仅 reporting 补全 |
| 改变 PnL 计算方法 | 用现有 `_current_value` |
| 引入"如果不强平继续到期"的 simulation projection | 不在范围 |
| live 端的 `open_at_end` UI 处理 | live 端有独立的 open positions display，不属本 SPEC |

---

## 边界条件与约束

- **数量预期**：HC 当前 baseline 末日 positions 列表大小取决于回测结束日 `df.index[-1]` 是否恰好是 exit day；通常 1-3 笔
- **PnL 占位口径**：以最后一日 mark-to-market 计算；不预测未来；研究侧需理解这是"如果今天就平掉"的快照，不是 expected final PnL
- **CSV / JSON 列向后兼容**：旧脚本读取 trade_log.csv 时新字段 `open_at_end` 会作为额外列出现；需要确认现有研究 prototype 不会因列数不匹配崩溃

---

## 数据契约

| 字段 | 来源 | 说明 |
|---|---|---|
| `Trade.open_at_end` | engine.py | 新字段，bool |
| `metrics.n_open_at_end` | compute_metrics | 新字段，int |
| `data/research_views.json.views.*.trades[*].open_at_end` | research_views.py 再生 | 透传 |

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | `Trade` dataclass 包含 `open_at_end: bool = False` | 代码审查 |
| AC2 | 全回测结束后，对每个仍开仓的 position 都合成一条 virtual Trade，且 `open_at_end=True` `exit_reason="open_at_end"` | 跑回测后 grep trade_log.csv |
| AC3 | `compute_metrics` 排除 `open_at_end=True`；`metrics.n_open_at_end` 等于 virtual trade 数量 | metrics.json 检查 |
| AC4 | trade_log.csv 列头包含 `open_at_end` | 一行 head 命令 |
| AC5 | UI 在 research view / margin 页面对 `open_at_end=True` 的 trade 显示橙色 `OPEN` badge | 浏览器 visual check |
| AC6 | `data/research_views.json` 再生后透传 `open_at_end` | jq 检查 |
| AC7 | 既有 closed trades 的 metrics 与 SPEC-070 v2 后基线对比无变化（排除 virtual 后）| Quant cascade report |
| AC8 | py_compile / 单元测试通过 | 一行命令 |

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-04-24 | 初稿 — MC v3 handoff 同步项；artifact + UI 双补全 | DRAFT |
| 2026-04-24 | PM 批量预批，交 Developer 实施 | APPROVED |
