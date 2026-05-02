# SPEC-078: Backtest Metrics Single-Source-of-Truth (API-as-Authority)

Status: DRAFT (主体；P12 Fast Path deferred)

## 目标

**What**：把 backtest dashboard 上的 annualized ROE / max drawdown / sharpe / total P&L 等核心 metrics 收口为 **server-side API 唯一权威**；移除 / 替换前端 `impliedAnnualizedRoe` 的客户端二次计算路径，使 PM 在 dashboard 上看到的数字与 `metrics.json` / API response **永远一致**。

**Why**：
- 当前 [web/templates/backtest.html:1965](web/templates/backtest.html#L1965) `impliedAnnualizedRoe(totalPnl, trades, baselineEquity)` 在 JS 端用 `(finalEquity / baselineEquity) ^ (1/years) - 1` 重新计算 ann ROE；服务端 `web/server.py` 也输出 metrics
- 双口径风险：
  - JS 端用 `trades[0].entry_date → trades[-1].exit_date` 算 years；服务端如果用 backtest start/end date 算，会有跨天 / 月差异
  - JS 端 baseline 写死 `100000` ([web/templates/backtest.html:1165](web/templates/backtest.html#L1165))；服务端如果未来支持自定义 initial_equity 会脱钩
  - 任何 P&L 修订（profit_target 改、stop 改）需要 PM 在 dashboard 与 metrics.json 之间手工对账
- MC `SPEC-078 DONE` 的 production 含义就是 "API 返回 ann ROE/sharpe/dd，dashboard 直接展示，不再客户端计算"
- `Q029` `live_scaled_est` 双口径需求 → server-side 统一计算可以同时返回 raw / scaled 两个 ann ROE，前端只展示，不算
- `P12 Fast Path` (research view 子集 metrics 实时计算) 列入 deferred，理由见 §Out of Scope
- 详见 `task/q036_to_q039_hc_reproduction_assessment_2026-05-01.md` §3.5 / §9

---

## 核心原则

- **API 是 source of truth**：server 决定数字；前端只展示；前端不重算
- **不破坏 research subset 子集计算**：`computeSubsetMetrics(trades)` 是 research view 的子集 P&L 显示，与 production ann ROE 不同口径，本 spec 不动这个函数
- **保留 `BACKTEST_BASELINE_EQUITY = 100000`** 常量作为 frontend display fallback（API 失败时给 0），不再用于 ROE 计算
- **不引入 frontend toggle**：default 切换即可；旧 JS 计算函数 `impliedAnnualizedRoe` 改为只在服务端 metrics 缺字段时回退使用，并加 console warning

---

## 功能定义

### F1 — server-side metrics 增加 `annualized_roe` 字段

**[web/server.py](web/server.py)** 内 backtest endpoint metrics 序列化：

新增字段：
- `annualized_roe`：float，单位 %（例如 `7.34`）
- `annualized_roe_basis`: 字符串 `"final_equity_compound"`（默认）；预留 `"linear_pnl_over_capital"` 以兼容旧口径
- `period_years`: float，由 server 计算并返回（基于 trades[0].entry_date → trades[-1].exit_date）

实现：把 `impliedAnnualizedRoe` 的 JS 公式（`(final/base) ^ (1/years) - 1`）port 到 Python，在 metrics 计算入口（`run_backtest` 之后或 metrics aggregator 内）一次性算出。

### F2 — frontend 直接展示 server `annualized_roe`

**[web/templates/backtest.html](web/templates/backtest.html)** `applyMetricCards` 函数：

修改 [:2028-2034](web/templates/backtest.html#L2028-L2034)：
```javascript
// 旧
const impliedRoe = impliedAnnualizedRoe(metrics.total_pnl || 0, trades);
// 新
const impliedRoe = (typeof metrics.annualized_roe === 'number')
  ? metrics.annualized_roe
  : (console.warn('[SPEC-078] server metrics.annualized_roe missing — JS fallback'), impliedAnnualizedRoe(metrics.total_pnl || 0, trades));
```

行为：
- API 返回 `annualized_roe` → 前端直接展示
- API 缺字段（向后兼容期）→ 前端 fallback + console warning，PM 可以发现问题

### F3 — JSDoc 标注 `impliedAnnualizedRoe` 为 deprecated fallback

**[web/templates/backtest.html:1965](web/templates/backtest.html#L1965)** 函数注释：

```javascript
/**
 * @deprecated SPEC-078 — server `metrics.annualized_roe` 是唯一权威。
 *             本函数仅作为 API 缺字段时的 fallback 路径，并会触发 console.warn。
 *             不要在新代码里调用。
 */
function impliedAnnualizedRoe(totalPnl, trades, baselineEquity = BACKTEST_BASELINE_EQUITY) { ... }
```

### F4 — 测试覆盖

新增 [tests/test_metrics_annualized_roe.py](tests/test_metrics_annualized_roe.py)：
1. 给定固定 trades 列表 + `total_pnl`，断言 server 计算的 `annualized_roe` 与 JS 公式 byte-identical（误差 < 1e-6）
2. trades 列表为空 → 断言 `annualized_roe == 0.0`
3. trades 跨 1 天（years ≈ 0.0027）→ 断言不会 ZeroDivisionError 且数字为有限值

### F5 — `RESEARCH_LOG.md` / `PROJECT_STATUS.md` 索引更新

- `RESEARCH_LOG.md`：新增 `SPEC-078: Metrics SoT`
- `PROJECT_STATUS.md`：标注 dashboard metrics 已 SoT 收口

---

## In Scope

| 项目 | 说明 |
|---|---|
| F1 server `annualized_roe` 字段 | metrics aggregator 添加 |
| F2 frontend 切换 | `applyMetricCards` 改 |
| F3 deprecation 注释 | JSDoc |
| F4 unit test | byte-identical with JS 公式 |
| F5 索引更新 | RESEARCH_LOG / PROJECT_STATUS |

## Out of Scope

| 项目 | 理由 |
|---|---|
| **P12 Fast Path** (research view 子集 metrics 实时计算) | MC handoff 已列为 deferred；HC 同 fate；等 production SoT 收口稳定 4-8 周再讨论 |
| `Q029 live_scaled_est` 双口径并列展示 | 与本 spec 兼容但是独立 feature；本 spec 只确保 server SoT，scaled 口径由 Q029 单独 spec 处理 |
| `BACKTEST_BASELINE_EQUITY` 改为可配置 | 与 default lift 无关，未来 PM 自定 equity 时单独 spec |
| `computeSubsetMetrics(trades)` 改造 | 这是 research subset 的临时聚合，不计 ann ROE，与 SoT 收口逻辑无冲突 |
| `margin.html` metrics（如有） | 本 spec 限于 backtest 页 |
| BCD-specific metrics 表格 | SPEC-079 / 080 dashboard pill |

---

## 边界条件与约束

- **回归口径**：F1 落地后 server 计算的 `annualized_roe` 必须与原 JS `impliedAnnualizedRoe` byte-identical；不允许 PM 在 dashboard 上看到任何数字漂移
- **fallback 期限**：F2 的 JS fallback 保留至下一次 dashboard 大改（建议 4 周内移除，由 follow-up spec 处理）
- **无 toggle**：本 spec 落地后默认即 SoT；如发现 server 计算与 JS 不一致，应当成 bug 修而不是 toggle 回退

---

## 数据契约

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `metrics.annualized_roe` | float | server | 单位 % |
| `metrics.annualized_roe_basis` | str | server | `"final_equity_compound"` 默认 |
| `metrics.period_years` | float | server | trades[0].entry → trades[-1].exit |
| `metrics.total_pnl` | float | server | 现有字段，不动 |
| `metrics.max_drawdown` | float | server | 现有字段，不动 |
| `metrics.sharpe` | float | server | 现有字段，不动 |

---

## Acceptance Criteria

| AC | 描述 | 验证方式 |
|---|---|---|
| AC1 | server backtest endpoint response 包含 `annualized_roe` / `annualized_roe_basis` / `period_years` | API 抓包 |
| AC2 | dashboard backtest 页面 ann ROE 数字在 API 正常时来自 server，关闭网络后 fallback 触发 console warning | 浏览器 DevTools 实测 |
| AC3 | `tests/test_metrics_annualized_roe.py` PASS（3 case） | `pytest` |
| AC4 | server 计算与 JS 公式给定相同输入时数字一致 (误差 < 1e-6) | F4 第 1 case |
| AC5 | `RESEARCH_LOG.md` / `PROJECT_STATUS.md` 已更新 SPEC-078 状态 | 文档审查 |
| AC6 | `impliedAnnualizedRoe` JSDoc 含 `@deprecated` 标记 | grep |
| AC7 | `computeSubsetMetrics` 未被改动 | diff 审查 |

---

## 变更记录

| 日期 | 变更 | 状态 |
|---|---|---|
| 2026-05-01 | Quant 起草；F1-F5 主体；P12 Fast Path 列为 deferred；JS 端公式与 baseline 100k 已定位 | DRAFT |
