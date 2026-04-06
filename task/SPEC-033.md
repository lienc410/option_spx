# SPEC-033: Backtest Page — On-Demand Execution & Disk Cache

## 目标

**What**：重构 Backtest 页的加载行为：
1. 移除页面加载时自动触发 `runBacktest()` 的行为
2. 为 `/api/backtest` 新增磁盘缓存（当前只有内存缓存，进程重启即失效）
3. 拆分 `/api/signals/history` 独立 endpoint，SPX 图背景色和信号矩阵不再依赖 backtest 请求
4. 页面首屏加载最近一次磁盘缓存结果（若有），否则显示空状态 CTA

**Why**：
- 当前设计每次进入 Backtest 页都发网络请求并等待响应，即使 cache hit 也有 spinner；
  进程重启后缓存失效，即使参数未变也重跑 26yr 回测
- 为了画 SPX 图背景色，额外发一次 `fetch('/api/backtest?start=2000-01-01')`，
  两次请求并行但耦合在 `runBacktest()` 函数里，逻辑复杂
- 用户每次点 period pill 也触发 `runBacktest()`，等待时间不可控

---

## 功能定义

### F1 — 移除页面加载自动运行

**现状**：`backtest.html` 脚本末尾 `runBacktest()` 直接调用（line 2565）。

**改动**：
- 删除脚本末尾的 `runBacktest()` 自动调用
- 页面初始化时调用 `loadCachedResult()`（见 F4）
- period pill 点击（`setPeriod()`）改为**只设日期，不自动触发 run**，
  去掉 line 1687 的 `runBacktest()` 调用
- 用户必须显式点 **Run** 按钮（或 period pill 选中后点 Run）才触发回测

**Run 按钮行为不变**：点击后仍然完整执行 `runBacktest()`。

---

### F2 — `/api/backtest` 新增磁盘缓存

**缓存文件**：`data/backtest_results_cache.json`

**缓存 key**：`{start_date}__{params_hash}`（双下划线分隔，与 stats cache 格式一致）

**缓存 value**：
```json
{
  "date":        "2026-04-05",
  "params_hash": "abc123def4",
  "computed_at": "2026-04-05T14:23:00",
  "payload":     { "metrics": {...}, "trades": [...] }
}
```

注意：**signals 不再存入 backtest 缓存**（signals 由 F3 的独立 endpoint 处理）。

**缓存有效期**：同一天 + 相同 params_hash（与 stats cache 一致）。

**缓存命中逻辑**（server.py）：
```
1. 检查内存缓存（热路径，5分钟 TTL）
2. 检查磁盘缓存（同天 + 相同 params_hash）
3. 两者都未命中 → 运行 run_backtest()，写入内存 + 磁盘
```

**响应格式变化**：`/api/backtest` 响应新增 `computed_at` 字段（ISO 时间字符串），
前端用于显示"Last computed"。signals 字段从该 endpoint 移除。

---

### F3 — 新增 `/api/signals/history` endpoint

**用途**：仅返回信号历史，不运行 backtest 引擎的交易模拟部分。

**实现**：
`run_backtest()` 内部已生成 signals list。提取信号生成逻辑到独立函数
`run_signals_only(start_date, end_date)`，只跑信号层，不跑策略选择和 trade 模拟。

```python
@app.route("/api/signals/history")
def api_signals_history():
    start = flask_req.args.get("start", "2000-01-01")
    # 独立轻量缓存（内存，TTL 1小时，因 signals 变化频率低）
    # 调用 run_signals_only(start_date=start)
    # 返回 signals list
```

**响应格式**：
```json
{ "signals": [ {"date": "...", "regime": "...", "ivp": ..., "trend": "..."}, ... ] }
```

**前端**：
- 页面初始化时（不是 runBacktest 时）单独调用 `loadSignalHistory()`
- SPX 图的背景色 band 和 Signal History 表格从 `_spxFullSigData` 读取，
  与 backtest trades 结果解耦
- `runBacktest()` 不再并行发 `fetch('/api/backtest?start=2000-01-01')`，
  只发一次 `fetch('/api/backtest?start=${start}')`

**缓存策略**：signals history 数据量大但变化慢（每天仅新增一条），
内存缓存 TTL 设为 3600 秒（1小时），不需要磁盘缓存。

---

### F4 — 首屏加载最近缓存结果

**函数**：`loadCachedResult()`（前端新增，页面初始化时调用）

**逻辑**：
```
GET /api/backtest/latest-cached
→ 若有：返回最近一次磁盘缓存的结果 + computed_at + start_date
→ 若无：返回 { "empty": true }
```

**新增 endpoint** `GET /api/backtest/latest-cached`：
从 `backtest_results_cache.json` 中找最近一次写入的记录（按 `computed_at` 排序取最新）。
返回完整 payload + metadata（start_date、computed_at、params_hash）。

**前端首屏显示**：
- 有缓存结果：渲染所有图表和表格，控件区显示灰色
  `Last computed: 2026-04-05 14:23  ·  params unchanged`  badge
- 无缓存：显示空状态 CTA：
  ```
  No backtest results yet.
  Select a period and click Run to start.
  ```
- 若缓存结果的 params_hash ≠ 当前 params_hash（参数已改变）：显示
  `⚠ Params changed since last run — results may be stale`

---

### F5 — 前端 Run 状态优化

**"Last computed" badge**：
结果区顶部（section-title 旁）显示：
```
Last computed: 2026-04-05 14:23  ·  start 2025-04-05  ·  26yr WR 77%
```

**Run 按钮状态**：
- 页面刚加载（显示缓存结果）：Run 按钮文字改为 `Re-run`
- 无缓存结果：Run 按钮文字为 `Run`
- 运行中：`Running…`（现有行为）

**period pill 行为变化**：
- 点击 pill → 仅设日期到 input，高亮 pill，不触发请求
- 若结果区当前显示的 start_date 与新选的 period 不符，显示淡黄色提示条：
  `Showing results for a different period. Click Run to update.`

---

## 接口定义

### 后端改动（server.py）

| 变化 | 说明 |
|------|------|
| `/api/backtest` 响应去掉 `signals` 字段 | signals 由独立 endpoint 提供 |
| `/api/backtest` 响应新增 `computed_at` 字段 | ISO 时间字符串 |
| `/api/backtest` 内存+磁盘双缓存，key 含 params_hash | 见 F2 |
| 新增 `/api/signals/history?start=` | 仅返回 signals list，独立缓存 |
| 新增 `/api/backtest/latest-cached` | 返回磁盘缓存中最新一条结果 |
| 新增 `run_signals_only(start_date)` 函数 | 从 engine 或 backtest 层提取纯信号生成逻辑 |

### 前端改动（backtest.html）

| 变化 | 说明 |
|------|------|
| 删除脚本末尾 `runBacktest()` 自动调用 | |
| `setPeriod()` 去掉 `runBacktest()` 调用 | 只设日期，不触发请求 |
| 新增 `loadCachedResult()` | 页面初始化时调用 |
| 新增 `loadSignalHistory()` | 页面初始化时调用，获取 SPX 背景信号 |
| `runBacktest()` 去掉并行的 full-history 请求 | 只发一次请求 |
| 新增 "Last computed" badge 和 stale 提示 | |
| Run 按钮文字随状态变化 | `Run` / `Re-run` / `Running…` |

---

## 边界条件与约束

- `/api/backtest` 去掉 signals 是 breaking change：
  前端 `_spxFullSigData` 改为从 `/api/signals/history` 获取，
  不再从 `/api/backtest` 响应中取
- `run_signals_only()` 的实现要轻量：只跑信号生成（VIX/IV/trend），
  不跑 `_build_legs`、`_current_value`、trade exit 判断
- 磁盘缓存文件可能包含多个 key（不同 start_date + params 组合），
  `latest-cached` endpoint 按 `computed_at` 取最新，不限定 start_date
- 参数 panel 的自定义参数（extreme_vix 等）改变时，params_hash 变化，
  stale badge 自动出现（hash 在 params panel 展开时实时计算）
- 不改动 `engine.py` 核心逻辑

---

## 不在范围内

- Experiment runner 的缓存优化（独立研究工具，使用频率低）
- Auto grid search 的行为改动
- 实时回测（websocket / SSE streaming）
- 其他页面（Dashboard / Matrix / Margin）

---

## Review

- 结论：PASS
- AC1–AC9 全部通过代码核查
- Breaking change 迁移确认：`/api/backtest` 已移除 signals，matrix.html 和 backtest.html 两处均已迁移到 `/api/signals/history`
- 额外观察：`runBacktest()` 完成后会额外调一次 `loadSignalHistory()` 刷新 SPX 图，逻辑正确，轻微性能代价可接受
- 注意事项：旧磁盘缓存（`backtest_results_cache.json`）若不存在会自动创建；首次访问无缓存时显示空状态 CTA，用户需手动点 Run

---

## 验收标准

1. **AC1**：进入 Backtest 页不自动发 `/api/backtest` 请求，不出现 spinner
2. **AC2**：有磁盘缓存时，首屏直接渲染上次结果，显示 "Last computed" badge
3. **AC3**：无缓存时，显示空状态 CTA（"Select a period and click Run"）
4. **AC4**：period pill 点击只设日期，不触发 run；需点 Run 按钮才执行
5. **AC5**：`/api/signals/history` 独立返回信号历史，不依赖 backtest 引擎的交易模拟
6. **AC6**：`runBacktest()` 只发一次 fetch（不再并行发 full-history 请求）
7. **AC7**：params_hash 变化时，显示 stale 警告 badge
8. **AC8**：磁盘缓存在进程重启后仍可命中（相同日期 + 相同 params_hash）
9. **AC9**：`/api/backtest/latest-cached` 返回最近一次缓存结果 + metadata

---

Status: DONE
