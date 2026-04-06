# SPEC-033 Handoff

## 修改文件
- `backtest/engine.py:1036` — 新增 `run_signals_only()`，把纯信号历史生成从交易仿真里拆出来
- `web/server.py:232` — `/api/backtest` 改为内存 + 磁盘双缓存，响应新增 `computed_at/start_date/params_hash`，并移除 `signals`
- `web/server.py:310` — 新增 `/api/signals/history` 轻量信号历史接口
- `web/server.py:327` — 新增 `/api/backtest/latest-cached`，返回最近一次磁盘缓存结果
- `web/templates/backtest.html:724` — 首屏改为加载 cached result / empty CTA，period pill 不再自动 run，`runBacktest()` 只发一次 `/api/backtest`
- `web/templates/backtest.html:1780` — 新增 `loadSignalHistory()` / `loadCachedResult()` / stale badge / Last computed badge
- `web/templates/matrix.html:774` — breaking change 迁移：不再从 `/api/backtest` 读取 `signals`，改为 `/api/signals/history`
- `tests/test_state_and_api.py:138` — 新增 `/api/backtest` 去掉 `signals`、`/api/signals/history`、`/api/backtest/latest-cached` 回归测试

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8, AC9

## 阻塞/备注
- Breaking change 迁移点：`/api/backtest` 响应已移除 `signals` 字段，前端依赖已迁到 `/api/signals/history`，本次同时修了 `backtest.html` 和 `matrix.html` 两处调用。
