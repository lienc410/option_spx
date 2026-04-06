# SPEC-038 Handoff

## 修改文件
- `logs/trade_log_io.py:75` — `resolve_log()` 为每条 resolved trade 顶层新增 `paper_trade`
- `web/server.py:223` — `POST /api/position/open` 接收 `paper_trade` 并写入 state + trade log
- `web/server.py:333` — `GET /api/position/open-draft` 返回默认 `paper_trade: false`
- `web/server.py:449` — open correction 可修正 `paper_trade`
- `web/server.py:601` — `GET /api/performance/live` 支持 `?include_paper=1`
- `performance/live.py:42` — live performance 聚合新增 `include_paper` 过滤、`paper_trade_count`、open position row 的 `paper_trade`
- `web/templates/index.html:893` — 当前 open position 显示 `PAPER` badge；Open Position modal 新增 checkbox 并提交 `paper_trade`
- `web/templates/performance.html:203` — Performance 页面新增 `Exclude Paper Trades` toggle 与 PAPER 标识
- `tests/test_live_performance.py:95` — 新增 include/exclude paper trades 的聚合与 API 测试
- `tests/test_state_and_api.py:324` — 新增 paper trade open/correction 流测试

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8
