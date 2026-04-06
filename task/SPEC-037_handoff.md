# SPEC-037 Handoff

## 修改文件
- `performance/live.py:42` — 新增 `compute_live_performance()`，按 resolved trade log 聚合 summary / by_strategy / monthly / recent_closed / open_positions，并可选叠加 Schwab live 数据
- `web/server.py:174` — 新增 `/performance` 页面路由与 `GET /api/performance/live` endpoint
- `web/templates/performance.html:1` — 新增 Live Trade Performance 页面，展示 metric cards、monthly/cumulative 图、by-strategy、open positions、recent closed trades
- `web/templates/index.html:514` — Dashboard 导航新增 `Performance`
- `web/templates/matrix.html:371` — Matrix 导航新增 `Performance`
- `web/templates/backtest.html:700` — Backtest 导航新增 `Performance`
- `web/templates/margin.html:231` — Margin 导航新增 `Performance`
- `tests/test_live_performance.py:8` — 新增 live performance 聚合与 API 回归测试，覆盖 void/open-only/Schwab enrichment

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8
