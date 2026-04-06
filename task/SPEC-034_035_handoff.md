# SPEC-034_035 Handoff

## 修改文件
- `logs/trade_log_io.py:1` — 新增 append-only trade log 读写与 trade_id 生成
- `strategy/state.py:100` — `write_state/close_position/roll_position/add_note` 扩展为可保存真实成交字段，同时保留旧调用兼容
- `web/server.py:202` — 新增 `/api/position/open|close|roll|note` 和 `/api/trade-log`
- `web/templates/index.html:375` — Dashboard 新增 position action bar、4 个 modal、open/close/roll/note 前端提交流程
- `schwab/auth.py:1` — 新增 Schwab token 管理、refresh、setup 所需 OAuth helper
- `schwab/client.py:1` — 新增 Schwab read-only client、缓存、live position/balance 聚合
- `schwab/setup.py:1` — 新增 `venv/bin/python -m schwab.setup` 一次性授权入口
- `web/server.py:302` — 新增 `/api/schwab/status|positions|balances`，并把 `schwab_live` 挂到 `/api/position`
- `web/templates/index.html:887` — Position Panel 新增 Live Greeks (Schwab) 显示
- `web/templates/margin.html:223` — Margin 页新增 Live BP (Schwab) 区块与降级提示
- `tests/test_state_and_api.py:195` — 新增 open/close/roll/trade-log 与 Schwab degrade 回归测试

## 收尾
- 缓存清除：否　Web 重启：否

## 验收结果
- 通过：SPEC-034 AC2, AC3, AC4, AC5, AC7；SPEC-035 AC2, AC6（未配置降级路径）
- 未通过：SPEC-034 AC1, AC6 → 代码已实现，未做浏览器手动验收
- 未通过：SPEC-035 AC1, AC3, AC4, AC5, AC7, AC8, AC9 → 需要先在 Schwab Developer Portal 创建 app 并提供 `client_id / client_secret` 后执行 `venv/bin/python -m schwab.setup` 才能做真实联调验收

## 阻塞/备注
- 035 setup 前置条件：先在 Schwab Developer Portal 创建 app，配置本机 redirect URI，再设置 `SCHWAB_CLIENT_ID` / `SCHWAB_CLIENT_SECRET`（可选 `SCHWAB_REDIRECT_URI`）后运行 `venv/bin/python -m schwab.setup`
