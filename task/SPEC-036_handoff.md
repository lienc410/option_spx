# SPEC-036 Handoff

## 修改文件
- `logs/trade_log_io.py:45` — 新增 `resolve_log()`，对 correction / void 做 resolved 视图折叠
- `strategy/state.py:173` — 新增 `update_open_position()`，用于 correction 后同步当前 open state 而不重置 `opened_at`
- `web/server.py:427` — `/api/trade-log` 默认返回 resolved 结果，`?raw=1` 返回原始事件流
- `web/server.py:451` — 新增 `POST /api/position/correction`，包含当前 open state 同步与 close `actual_pnl` 自动重算
- `web/server.py:532` — 新增 `POST /api/position/void`，支持 void 当前 open trade 并清空 state
- `web/templates/index.html:918` — Dashboard Position Panel 新增 `[Correct]` / `[Void]` 按钮与 modal
- `tests/test_state_and_api.py:299` — 新增 correction / void / resolved-log / auto-recalc 回归测试

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8, AC9

## 阻塞/备注
- PM 已确认默认假设：当 `target_event = "roll"` 且同一 `trade_id` 存在多次 roll 时，correction 默认 patch 最近一条 roll 事件。
