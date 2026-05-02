# SPEC-078 Handoff

## 范围
- 本次仅完成 **可脚本化 smoke 验收**
- 浏览器 / DevTools 人工部分未执行，保留给 PM

## 前置处理
- `data/backtest_results_cache.json`
  - 已备份到 `data/backtest_results_cache.pre-spec078.json`
  - 原 cache 已删除，强制走新代码 path
- 本地 `5050` 端口原有 web 进程存在但不健康
  - 发现 PID `87255` 占端口但 HTTP 不响应
  - 经 PM 确认后重启本地 dev server

## 服务状态
- 本地 dev server 已启动并可访问
- 已确认：
  - `http://localhost:5050/` → `200`
  - `http://localhost:5050/backtest` → `200`

## 验证结果

### AC1 — API 返回字段检查

`GET /api/backtest?start=2023-01-01`
- `metrics.annualized_roe` 存在，类型为 number
- `metrics.annualized_roe_basis == "final_equity_compound"`
- `metrics.period_years` 存在，类型为 number
- 结果：`PASS`

`GET /api/backtest?start=2007-01-01`
- `metrics.annualized_roe` 存在，类型为 number
- `metrics.annualized_roe_basis == "final_equity_compound"`
- `metrics.period_years` 存在，类型为 number
- 结果：`PASS`

### AC4 — server 结果与 JS 公式 byte-identical 复算

公式：
`(((100000 + total_pnl) / 100000) ** (1 / years) - 1) * 100`

`start=2023-01-01`
- `total_pnl = 80614.16111641344`
- `first_entry = 2023-01-03`
- `last_exit = 2026-05-01`
- `period_years (API) = 3.323751`
- `expected_period_years = 3.323750855578371`
- `annualized_roe (API) = 19.466903`
- `expected_roe = 19.466903311251073`
- `diff = 3.1125107469165414e-07`
- 结果：`PASS`

`start=2007-01-01`
- `total_pnl = 345304.1489743933`
- `first_entry = 2007-01-03`
- `last_exit = 2026-05-01`
- `period_years (API) = 19.323751`
- `expected_period_years = 19.32375085557837`
- `annualized_roe (API) = 8.035839`
- `expected_roe = 8.035838883685354`
- `diff = 1.1631464502670497e-07`
- 结果：`PASS`

### AC2 / 浏览器手工部分
- 未执行
- 保留给 PM 在浏览器内完成：
  - DevTools Local Overrides 删除 `metrics.annualized_roe`
  - 确认 fallback 触发 `console.warn`

## 总结
- 脚本化部分：`PASS`
- 浏览器人工部分：`待 PM 手工验收`

